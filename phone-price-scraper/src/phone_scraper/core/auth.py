from __future__ import annotations

import logging
import os
import re
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "api_key",
    "x-api-key",
    "cookie",
    "set-cookie",
}

TOKEN_PATTERN = re.compile(r"(Bearer\s+|Basic\s+)([A-Za-z0-9._\-+/=]+)", re.IGNORECASE)


def resolve_env_secret(env_var_name: str | None) -> str:
    """Resolve a secret value from an environment variable by name."""
    if not env_var_name:
        return ""
    return os.environ.get(env_var_name, "").strip()


def redact_value(value: Any) -> Any:
    """Recursively redact secrets in dicts/lists/strings before logging."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in value.items():
            if k.lower() in SENSITIVE_KEYS:
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = redact_value(v)
        return sanitized
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return TOKEN_PATTERN.sub(r"\1***REDACTED***", value)
    return value


class SecretRedactingFilter(logging.Filter):
    """Logging filter that strips Bearer/Basic tokens from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = TOKEN_PATTERN.sub(r"\1***REDACTED***", record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(redact_value(a) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = redact_value(record.args)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    redactor = SecretRedactingFilter()
    for handler in root.handlers:
        if not any(isinstance(f, SecretRedactingFilter) for f in handler.filters):
            handler.addFilter(redactor)
