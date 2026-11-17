from __future__ import annotations

import logging
from datetime import UTC, datetime

from phone_scraper.core.http import HttpFetcher, PlaywrightFetcher
from phone_scraper.core.normalize import NormalizedPriceRecord
from phone_scraper.scrapers.base import BaseScraper
from phone_scraper.scrapers.cashify_sell import selectors
from phone_scraper.scrapers.cashify_sell.parser import (
    extract_variant_urls,
    parse_cashify_sell_html,
)

logger = logging.getLogger(__name__)


class CashifySellScraper(BaseScraper):
    """Collects Cashify 'Sell old phone' quotes across storage variants and condition grades."""

    source_name = "cashify_sell"

    def __init__(
        self,
        urls: list[str],
        *,
        use_playwright: bool = True,
        http_fetcher: HttpFetcher | None = None,
        playwright_fetcher: PlaywrightFetcher | None = None,
    ) -> None:
        self.urls = urls
        self.use_playwright = use_playwright
        self.http_fetcher = http_fetcher or HttpFetcher()
        self.playwright_fetcher = playwright_fetcher or PlaywrightFetcher()

    def _fetch(self, url: str) -> str:
        if self.use_playwright:
            return self.playwright_fetcher.fetch_html(
                url, source=self.source_name, wait_selector=selectors.WAIT_SELECTOR
            )
        resp = self.http_fetcher.request("GET", url, source=self.source_name)
        resp.raise_for_status()
        return resp.text

    def collect(self, run_id: str | int) -> list[NormalizedPriceRecord]:
        captured_at = datetime.now(UTC)
        all_records: list[NormalizedPriceRecord] = []
        seen_urls: set[str] = set()

        for base_url in self.urls:
            if base_url in seen_urls:
                continue
            seen_urls.add(base_url)
            html = self._fetch(base_url)
            variant_urls = extract_variant_urls(html)
            if variant_urls:
                for v_url in variant_urls:
                    if v_url in seen_urls:
                        continue
                    seen_urls.add(v_url)
                    v_html = self._fetch(v_url)
                    all_records.extend(
                        parse_cashify_sell_html(
                            v_html, v_url, run_id=run_id, captured_at=captured_at
                        )
                    )
            else:
                all_records.extend(
                    parse_cashify_sell_html(
                        html, base_url, run_id=run_id, captured_at=captured_at
                    )
                )

        logger.info("cashify_sell collected %d normalized records", len(all_records))
        return all_records
