from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RetryExhaustedError(RuntimeError):
    """Raised when all retry attempts are exhausted."""


def with_retry(
    fn: Callable[[], httpx.Response],
    max_attempts: int = 3,
    backoff_base_sec: float = 1.0,
) -> httpx.Response:
    """Execute an HTTP call with exponential backoff on 429, 5xx, and timeouts."""
    last_exc: Exception | None = None
    last_response: httpx.Response | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = fn()
            if response.status_code not in RETRYABLE_STATUS_CODES:
                return response
            last_response = response
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = backoff_base_sec * (2 ** (attempt - 1))
            logger.warning(
                "Retryable HTTP %d on attempt %d/%d; sleeping %.2fs",
                response.status_code,
                attempt,
                max_attempts,
                delay,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            delay = backoff_base_sec * (2 ** (attempt - 1))
            logger.warning(
                "HTTP transport/timeout error (%s) on attempt %d/%d; sleeping %.2fs",
                type(exc).__name__,
                attempt,
                max_attempts,
                delay,
            )

        if attempt < max_attempts:
            time.sleep(delay)

    if last_response is not None:
        return last_response
    raise RetryExhaustedError(f"HTTP request failed after {max_attempts} attempts") from last_exc
