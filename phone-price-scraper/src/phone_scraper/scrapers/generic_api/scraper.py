from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from phone_scraper.core.http import HttpFetcher
from phone_scraper.core.normalize import NormalizedPriceRecord
from phone_scraper.core.rate_limit import DomainRateLimiter
from phone_scraper.scrapers.base import BaseScraper, ParseError
from phone_scraper.scrapers.generic_api.auth import ApiAuthProvider
from phone_scraper.scrapers.generic_api.mapper import extract_items_list, map_api_records
from phone_scraper.scrapers.generic_api.paginator import ApiPaginator

logger = logging.getLogger(__name__)


class GenericApiScraper(BaseScraper):
    """Config-driven JSON API scraper with auth, 401 refresh+retry, pagination, and field mapping."""

    def __init__(
        self,
        config: dict[str, Any],
        fetcher: HttpFetcher | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.source_name = str(config["name"])
        self.url = str(config["url"])
        self.method = str(config.get("method", "GET")).upper()
        self.base_headers: dict[str, str] = {
            str(k): str(v) for k, v in (config.get("headers") or {}).items()
        }
        self.base_params: dict[str, Any] = dict(config.get("params") or {})
        self.body: Any = config.get("body")

        rate_cfg = config.get("rate_limit") or {}
        retry_cfg = config.get("retry") or {}
        timeout = float(config.get("timeout", 20.0))

        self.fetcher = fetcher or HttpFetcher(
            respect_robots_txt=False,
            rate_limiter=DomainRateLimiter(
                min_delay_sec=float(rate_cfg.get("min_delay_sec", 1.0)),
                max_delay_sec=float(rate_cfg.get("max_delay_sec", 3.0)),
                max_concurrency=2,
            ),
            timeout_sec=timeout,
            max_retries=int(retry_cfg.get("max_attempts", 3)),
            transport=transport,
        )
        self.auth = ApiAuthProvider(config.get("auth"), transport=transport)

    @classmethod
    def from_yaml(
        cls,
        yaml_path: Path,
        fetcher: HttpFetcher | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> GenericApiScraper:
        with yaml_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return cls(config=raw, fetcher=fetcher, transport=transport)

    def _request_with_401_retry(
        self,
        target_url: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        req_headers, req_params = self.auth.apply(self.base_headers, params)
        response = self.fetcher.request(
            self.method,
            target_url,
            source=self.source_name,
            headers=req_headers,
            params=req_params,
            json_body=self.body,
            cache_ext="json",
            check_robots=False,
        )
        if response.status_code == 401 and self.auth.refresh():
            logger.info("Received 401 for %s; refreshed token and retrying once", self.source_name)
            req_headers, req_params = self.auth.apply(self.base_headers, params)
            response = self.fetcher.request(
                self.method,
                target_url,
                source=self.source_name,
                headers=req_headers,
                params=req_params,
                json_body=self.body,
                cache_ext="json",
                check_robots=False,
            )
        response.raise_for_status()
        return response

    def collect(self, run_id: str | int) -> list[NormalizedPriceRecord]:
        paginator = ApiPaginator(
            self.config.get("pagination"),
            base_url=self.url,
            base_params=self.base_params,
        )
        response_cfg = self.config.get("response") or {}
        items_path = response_cfg.get("items_path")
        field_map = self.config.get("field_map") or {}

        all_records: list[NormalizedPriceRecord] = []
        spec = paginator.initial_request()
        captured_at = datetime.now(UTC)

        while spec is not None:
            resp = self._request_with_401_retry(spec.url, spec.params)
            payload = resp.json()
            items = extract_items_list(payload, items_path)
            page_records = map_api_records(
                payload,
                source_name=self.source_name,
                source_url=spec.url,
                items_path=items_path,
                field_map=field_map,
                run_id=run_id,
                captured_at=captured_at,
            )
            all_records.extend(page_records)
            spec = paginator.next_request(spec, resp, payload, len(items))

        if not all_records:
            raise ParseError(f"{self.source_name}: zero records collected from {self.url}")

        return all_records
