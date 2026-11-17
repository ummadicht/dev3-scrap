from __future__ import annotations

import random
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from collections.abc import Generator
from urllib.parse import urlparse


class DomainRateLimiter:
    """Per-domain rate limiter with random jitter and max concurrency cap."""

    def __init__(
        self,
        min_delay_sec: float = 1.0,
        max_delay_sec: float = 3.0,
        max_concurrency: int = 2,
    ) -> None:
        self.min_delay_sec = max(0.0, min_delay_sec)
        self.max_delay_sec = max(self.min_delay_sec, max_delay_sec)
        self.max_concurrency = max(1, max_concurrency)
        self._lock = threading.Lock()
        self._semaphores: dict[str, threading.Semaphore] = {}
        self._domain_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._last_request_ts: dict[str, float] = {}

    @staticmethod
    def domain_for(url: str) -> str:
        return urlparse(url).netloc.lower() or "default"

    def _get_semaphore(self, domain: str) -> threading.Semaphore:
        with self._lock:
            sem = self._semaphores.get(domain)
            if sem is None:
                sem = threading.Semaphore(self.max_concurrency)
                self._semaphores[domain] = sem
            return sem

    def wait_for_slot(self, url: str) -> None:
        domain = self.domain_for(url)
        dom_lock = self._domain_locks[domain]
        with dom_lock:
            last_ts = self._last_request_ts.get(domain)
            if last_ts is not None and self.max_delay_sec > 0:
                jitter = random.uniform(self.min_delay_sec, self.max_delay_sec)
                elapsed = time.monotonic() - last_ts
                if elapsed < jitter:
                    time.sleep(jitter - elapsed)
            self._last_request_ts[domain] = time.monotonic()

    @contextmanager
    def acquire(self, url: str) -> Generator[None, None, None]:
        domain = self.domain_for(url)
        sem = self._get_semaphore(domain)
        sem.acquire()
        try:
            self.wait_for_slot(url)
            yield
        finally:
            sem.release()
