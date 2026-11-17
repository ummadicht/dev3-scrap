from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from phone_scraper.core.http import HttpFetcher
from phone_scraper.core.normalize import NormalizedCondition
from phone_scraper.core.rate_limit import DomainRateLimiter
from phone_scraper.scrapers.generic_api.scraper import GenericApiScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXAMPLE_YAML = Path(__file__).resolve().parents[1] / "config" / "sources" / "example_api.yaml"


def test_generic_api_cursor_pagination_and_401_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    page1 = json.loads((FIXTURES_DIR / "generic_api_page1.json").read_text(encoding="utf-8"))
    page2 = json.loads((FIXTURES_DIR / "generic_api_page2.json").read_text(encoding="utf-8"))

    monkeypatch.setenv("PARTNER_OAUTH_CLIENT_ID", "cid-test")
    monkeypatch.setenv("PARTNER_OAUTH_CLIENT_SECRET", "csec-test")

    config = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    config["auth"] = {
        "type": "oauth2_client_credentials",
        "token_url": "https://api.partner-marketplace.example.com/oauth/token",
        "client_id_env": "PARTNER_OAUTH_CLIENT_ID",
        "client_secret_env": "PARTNER_OAUTH_CLIENT_SECRET",
        "scope": "quotes:read",
    }

    token_calls = 0
    page1_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls, page1_calls
        if request.url.path == "/oauth/token":
            token_calls += 1
            tok = "initial-token" if token_calls == 1 else "refreshed-token"
            return httpx.Response(200, json={"access_token": tok})

        if request.url.path == "/v1/phones/buyback-quotes":
            cursor = request.url.params.get("cursor")
            auth_hdr = request.headers.get("Authorization")
            if cursor is None:
                page1_calls += 1
                if page1_calls == 1:
                    assert auth_hdr == "Bearer initial-token"
                    return httpx.Response(401, json={"error": "expired"})
                assert auth_hdr == "Bearer refreshed-token"
                return httpx.Response(200, json=page1)
            if cursor == "cursor-page-2":
                assert auth_hdr == "Bearer refreshed-token"
                return httpx.Response(200, json=page2)

        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    fetcher = HttpFetcher(
        respect_robots_txt=False,
        rate_limiter=DomainRateLimiter(min_delay_sec=0.0, max_delay_sec=0.0, max_concurrency=2),
        max_retries=1,
        transport=transport,
    )
    scraper = GenericApiScraper(config, fetcher=fetcher, transport=transport)
    records = scraper.collect(run_id=77)

    assert token_calls == 2
    assert page1_calls == 2
    assert len(records) == 3

    first = records[0]
    assert first.source == "example_api"
    assert first.source_product_id == "PARTNER-OP12-256-EXC"
    assert first.brand == "OnePlus"
    assert first.model == "OnePlus 12 5G"
    assert first.storage_gb == 256
    assert first.ram_gb == 12
    assert first.color == "Flowy Emerald"
    assert first.condition == NormalizedCondition.EXCELLENT
    assert first.price == 44500.0
    assert first.currency == "INR"
    assert first.mrp == 64999.0
    assert first.discount_pct == 31.54
    assert first.in_stock is True

    last = records[2]
    assert last.brand == "Apple"
    assert last.storage_gb == 1024
    assert last.condition == NormalizedCondition.LIKE_NEW
    assert last.in_stock is False
