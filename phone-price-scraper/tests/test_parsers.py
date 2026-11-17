from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from phone_scraper.core.http import detect_block
from phone_scraper.core.normalize import NormalizedCondition
from phone_scraper.scrapers.amazon_sell.parser import parse_amazon_sell_html
from phone_scraper.scrapers.base import ParseError
from phone_scraper.scrapers.cashify_buy.parser import parse_cashify_buy_html
from phone_scraper.scrapers.cashify_sell.parser import (
    extract_variant_urls,
    parse_cashify_sell_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXED_TS = datetime(2026, 11, 17, 6, 0, 0, tzinfo=UTC)


def test_parse_cashify_sell_fixture() -> None:
    html = (FIXTURES_DIR / "cashify_sell.html").read_text(encoding="utf-8")
    variant_urls = extract_variant_urls(html)
    assert len(variant_urls) == 2
    assert variant_urls[0].endswith("/sell-old-mobile-phone/used-apple-iphone-15-128gb")

    records = parse_cashify_sell_html(
        html,
        "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-15",
        run_id=101,
        captured_at=FIXED_TS,
    )
    assert len(records) == 5
    first = records[0]
    assert first.source == "cashify_sell"
    assert first.brand == "Apple"
    assert first.model == "iPhone 15"
    assert first.storage_gb == 128
    assert first.ram_gb == 6
    assert first.condition == NormalizedCondition.EXCELLENT
    assert first.price == 42600.0
    assert first.currency == "INR"
    assert first.run_id == 101
    assert "quote" in first.raw_payload


def test_parse_cashify_buy_fixture() -> None:
    html = (FIXTURES_DIR / "cashify_buy.html").read_text(encoding="utf-8")
    records = parse_cashify_buy_html(
        html,
        "https://www.cashify.in/buy-refurbished-mobile-phones/buy-apple-iphone-13",
        run_id=102,
        captured_at=FIXED_TS,
    )
    assert len(records) == 2

    superb, good = records
    assert superb.source == "cashify_buy"
    assert superb.brand == "Apple"
    assert superb.model == "iPhone 13"
    assert superb.storage_gb == 128
    assert superb.ram_gb == 4
    assert superb.color == "Midnight Blue"
    assert superb.condition == NormalizedCondition.LIKE_NEW
    assert superb.price == 38999.0
    assert superb.mrp == 59900.0
    assert superb.discount_pct == 34.89
    assert superb.in_stock is True
    assert superb.raw_payload["warranty"] == "12 Months Warranty"

    assert good.condition == NormalizedCondition.GOOD
    assert good.storage_gb == 256
    assert good.in_stock is False


def test_parse_amazon_sell_fixture() -> None:
    html = (FIXTURES_DIR / "amazon_sell.html").read_text(encoding="utf-8")
    records = parse_amazon_sell_html(
        html,
        "https://www.amazon.in/b?node=tradein",
        run_id=103,
        captured_at=FIXED_TS,
    )
    assert len(records) == 4
    assert records[0].source == "amazon_sell"
    assert records[0].source_product_id == "B0CHX2F5QT"
    assert records[0].brand == "Apple"
    assert records[0].model == "iPhone 15"
    assert records[0].storage_gb == 128
    assert records[0].condition == NormalizedCondition.EXCELLENT
    assert records[0].price == 41500.0

    cracked = [r for r in records if r.condition == NormalizedCondition.POOR]
    assert len(cracked) == 1
    assert cracked[0].price == 19250.0

    samsung = [r for r in records if r.brand == "Samsung"]
    assert len(samsung) == 1
    assert samsung[0].condition == NormalizedCondition.LIKE_NEW
    assert samsung[0].storage_gb == 256


@pytest.mark.parametrize(
    "parser_fn",
    [parse_cashify_sell_html, parse_cashify_buy_html, parse_amazon_sell_html],
)
def test_parsers_fail_loudly_on_empty_structure(parser_fn: object) -> None:
    empty_html = "<html><body><h1>Maintenance</h1></body></html>"
    with pytest.raises(ParseError):
        parser_fn(empty_html, "https://example.invalid/empty", run_id=1)  # type: ignore[operator]


def test_detect_block_catches_captcha_and_login_wall() -> None:
    assert detect_block(200, "Please type the characters you see in this image") is not None
    assert detect_block(403, "<html>Sign in to continue</html>") is not None
    assert detect_block(200, "<html><body><h1>Apple iPhone 15</h1></body></html>") is None
