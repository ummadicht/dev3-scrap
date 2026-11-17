from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest

from phone_scraper.core.auth import SecretRedactingFilter, redact_value
from phone_scraper.core.normalize import (
    NormalizedCondition,
    NormalizedPriceRecord,
    compute_discount_pct,
    normalize_condition,
    parse_ram_gb,
    parse_storage_gb,
    stable_product_id,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Brand New", NormalizedCondition.NEW),
        ("Superb", NormalizedCondition.LIKE_NEW),
        ("Mint", NormalizedCondition.LIKE_NEW),
        ("Very Good", NormalizedCondition.EXCELLENT),
        ("Excellent", NormalizedCondition.EXCELLENT),
        ("Good", NormalizedCondition.GOOD),
        ("Grade B", NormalizedCondition.GOOD),
        ("Fair", NormalizedCondition.FAIR),
        ("Cracked Screen", NormalizedCondition.POOR),
        ("Grade D", NormalizedCondition.POOR),
        (None, NormalizedCondition.UNKNOWN),
        ("Mystery Grade", NormalizedCondition.UNKNOWN),
    ],
)
def test_normalize_condition(raw: str | None, expected: NormalizedCondition) -> None:
    assert normalize_condition(raw) == expected


def test_storage_and_ram_parsers() -> None:
    assert parse_storage_gb("128 GB") == 128
    assert parse_storage_gb("1 TB") == 1024
    assert parse_storage_gb("256") == 256
    assert parse_storage_gb(None) is None
    assert parse_ram_gb("8 GB") == 8
    assert parse_ram_gb("12") == 12
    assert parse_ram_gb("128 GB") is None


def test_discount_and_stable_id() -> None:
    assert compute_discount_pct(35000.0, 50000.0) == 30.0
    assert compute_discount_pct(50000.0, 40000.0) is None
    assert compute_discount_pct(35000.0, None) is None

    id1 = stable_product_id("cashify_sell", "Apple", "iPhone 15", 128)
    id2 = stable_product_id("cashify_sell", " apple ", "iphone 15", 128)
    assert id1 == id2
    assert len(id1) == 24


def test_normalized_record_utc_and_positive_price() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    naive_rec = NormalizedPriceRecord(
        source="cashify_sell",
        source_product_id="abc123",
        brand="Apple",
        model="iPhone 15",
        condition=NormalizedCondition.EXCELLENT,
        price=42000.555,
        currency="inr",
        source_url="https://example.invalid/phone",
        captured_at=datetime(2026, 11, 17, 11, 30, 0, tzinfo=ist),
    )
    assert naive_rec.captured_at.tzinfo == UTC
    assert naive_rec.captured_at.hour == 6
    assert naive_rec.currency == "INR"
    assert naive_rec.price == 42000.56

    with pytest.raises(ValueError):
        NormalizedPriceRecord(
            source="cashify_sell",
            source_product_id="abc123",
            brand="Apple",
            model="iPhone 15",
            price=-100.0,
            source_url="https://example.invalid/phone",
        )


def test_secret_redaction_in_dicts_and_logs() -> None:
    sanitized = redact_value(
        {
            "Authorization": "Bearer super-secret-jwt-123",
            "nested": {"api_key": "xyz", "note": "Basic dXNlcjpwYXNz"},
        }
    )
    assert sanitized["Authorization"] == "***REDACTED***"
    assert sanitized["nested"]["api_key"] == "***REDACTED***"
    assert sanitized["nested"]["note"] == "Basic ***REDACTED***"

    log_filter = SecretRedactingFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Calling endpoint with header Bearer tok_abc123",
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(record) is True
    assert "tok_abc123" not in record.msg
    assert "***REDACTED***" in record.msg
