"""
WholeCellMarket / SuperIQ PriceIQ Integration Client
=====================================================
Synchronizes mobile buyback pricing intelligence into PriceIQ.

Workflow:
1. Obtains OAuth2 Bearer token using client_credentials grant.
2. Formats scraped mobile pricing records into PriceIQ bulk schema.
3. Supports dry-run validation (writes nothing) and live commit (?commit=1).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PriceIQClient")


class PriceIQClient:
    """Client for WholeCellMarket / PriceIQ Bulk Pricing API."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_url: str = "https://wholecellmarket.com/apps/priceiq/api/oauth/token",
        bulk_url: str = "https://wholecellmarket.com/apps/priceiq/api/prices/bulk",
    ):
        self.client_id = client_id or os.getenv("WHOLECELL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("WHOLECELL_CLIENT_SECRET", "")
        self.token_url = token_url
        self.bulk_url = bulk_url
        self._token: Optional[str] = None

    def get_token(self) -> str:
        """Fetch or return cached OAuth2 Bearer token."""
        if self._token:
            return self._token

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Missing PriceIQ credentials. Set WHOLECELL_CLIENT_ID and "
                "WHOLECELL_CLIENT_SECRET in your environment or .env file."
            )

        logger.info("Requesting OAuth2 access token from %s...", self.token_url)
        response = requests.post(
            self.token_url,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials", "scope": "read write"},
            timeout=15,
        )

        if not response.ok:
            logger.error("OAuth token request failed [%d]: %s", response.status_code, response.text)
            response.raise_for_status()

        data = response.json()
        self._token = data.get("access_token")
        if not self._token:
            raise RuntimeError(f"Token response did not contain access_token: {data}")

        logger.info("Successfully acquired PriceIQ OAuth token.")
        return self._token

    @staticmethod
    def format_records_for_priceiq(
        records: List[Dict[str, Any]],
        only_verified: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Convert internal mobile pricing records into PriceIQ bulk format:
        {"device": "Apple iPhone 11 Pro Max (4 GB/512 GB)", "price": 19500, "comparables": 1}
        """
        rows = []
        for r in records:
            if only_verified and r.get("data_origin") != "verified_scraped":
                continue

            device_name = r.get("model", "").strip()
            # If storage isn't in model title, append it
            storage = r.get("storage", "").strip()
            if storage and storage not in device_name:
                device_name = f"{device_name} ({storage})"

            price = r.get("buyback_price")
            if not price or not isinstance(price, (int, float)) or price <= 0:
                continue

            rows.append({
                "device": device_name,
                "price": int(round(price)),
                "comparables": 1,
            })

        logger.info("Formatted %d rows for PriceIQ sync.", len(rows))
        return rows

    def sync_bulk_prices(
        self,
        rows: List[Dict[str, Any]],
        market: str = "IN",
        channel: str = "wholesale",
        source: str = "own closed deals",
        commit: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload prices in bulk.
        - commit=False: Dry run (writes nothing, returns validation)
        - commit=True: Writes rows to PriceIQ (?commit=1)
        """
        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "defaults": {
                "market": market,
                "channel": channel,
                "source": source,
            },
            "rows": rows,
        }

        url = f"{self.bulk_url}?commit=1" if commit else self.bulk_url
        mode_label = "LIVE COMMIT" if commit else "DRY RUN"
        logger.info("Submitting %d rows to PriceIQ [%s] -> %s", len(rows), mode_label, url)

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if not resp.ok:
            logger.error("PriceIQ sync failed [%d]: %s", resp.status_code, resp.text)
            resp.raise_for_status()

        result = resp.json()
        logger.info("PriceIQ response [%s]: %s", mode_label, json.dumps(result)[:200])
        return result


if __name__ == "__main__":
    # Test loading and formatting existing output.json records
    data_file = Path(__file__).resolve().parent / "output.json"
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        formatted = PriceIQClient.format_records_for_priceiq(records, only_verified=True)
        print(f"Sample formatted row (Total {len(formatted)}):")
        if formatted:
            print(json.dumps(formatted[0], indent=2))
