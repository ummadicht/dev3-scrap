from __future__ import annotations

import logging
from datetime import UTC, datetime

from phone_scraper.core.http import HttpFetcher, PlaywrightFetcher
from phone_scraper.core.normalize import NormalizedPriceRecord
from phone_scraper.scrapers.base import BaseScraper
from phone_scraper.scrapers.cashify_buy import selectors
from phone_scraper.scrapers.cashify_buy.parser import parse_cashify_buy_html

logger = logging.getLogger(__name__)


class CashifyBuyScraper(BaseScraper):
    """Collects Cashify 'Buy refurbished phone' listings."""

    source_name = "cashify_buy"

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

    def collect(self, run_id: str | int) -> list[NormalizedPriceRecord]:
        captured_at = datetime.now(UTC)
        records: list[NormalizedPriceRecord] = []
        for url in self.urls:
            if self.use_playwright:
                html = self.playwright_fetcher.fetch_html(
                    url, source=self.source_name, wait_selector=selectors.WAIT_SELECTOR
                )
            else:
                resp = self.http_fetcher.request("GET", url, source=self.source_name)
                resp.raise_for_status()
                html = resp.text
            records.extend(
                parse_cashify_buy_html(html, url, run_id=run_id, captured_at=captured_at)
            )
        logger.info("cashify_buy collected %d normalized records", len(records))
        return records
