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
        token_url: str = "https://thesuperiq.com/apps/priceiq/api/oauth/token",
        bulk_url: str = "https://thesuperiq.com/apps/priceiq/api/prices/bulk",
    ):
        self.client_id = client_id or os.getenv("WHOLECELL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("WHOLECELL_CLIENT_SECRET", "")
        self.token_url = token_url
        self.bulk_url = bulk_url
        self._token: Optional[str] = None

    def get_token(self) -> str:
        """Fetch or return cached OAuth2 Bearer token with fallback host support."""
        if self._token:
            return self._token

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Missing PriceIQ credentials. Set WHOLECELL_CLIENT_ID and "
                "WHOLECELL_CLIENT_SECRET in your environment or .env file."
            )

        endpoints = [
            self.token_url,
            "https://thesuperiq.com/apps/priceiq/api/oauth/token",
            "https://wholecellmarket.com/apps/priceiq/api/oauth/token",
        ]
        endpoints = list(dict.fromkeys(endpoints))
        last_err = None

        for ep in endpoints:
            try:
                logger.info("Requesting OAuth2 access token from %s...", ep)
                response = requests.post(
                    ep,
                    auth=(self.client_id, self.client_secret),
                    data={"grant_type": "client_credentials", "scope": "read write"},
                    timeout=15,
                )
                if response.ok:
                    data = response.json()
                    self._token = data.get("access_token")
                    if self._token:
                        logger.info("Successfully acquired PriceIQ OAuth token from %s.", ep)
                        return self._token
                else:
                    logger.warning("OAuth request to %s failed [%d]: %s", ep, response.status_code, response.text)
            except Exception as e:
                logger.warning("Connection error to %s: %s", ep, e)
                last_err = e

        raise RuntimeError(f"Failed to acquire OAuth token from all endpoints: {last_err}")
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



def export_partner_rate_cards(records: List[Dict[str, Any]], export_dir: str) -> Dict[str, str]:
    """
    Export standardized Rate Cards for partner portal upload at /partner/rate-cards
    Matching format expected by components/platform/RateCards.tsx
    """
    import csv

    os.makedirs(export_dir, exist_ok=True)
    matrix_path = os.path.join(export_dir, "partner_rate_card_matrix.csv")
    rows_path = os.path.join(export_dir, "partner_rate_card_rows.csv")

    # 1. Detailed rows format
    with open(rows_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Brand", "Model", "Storage", "Condition", "Buyback Price (INR)", "Market", "Channel", "Currency", "Source"])
        for r in records:
            writer.writerow([
                r.get("brand", ""),
                r.get("model", ""),
                r.get("storage", ""),
                r.get("condition", ""),
                int(round(float(r.get("buyback_price", 0)))),
                "IN",
                "wholesale",
                r.get("currency", "INR"),
                r.get("source_name", "WholeCellMarket"),
            ])

    # 2. Matrix format (Grade A, Grade B, Grade C, Grade D columns)
    device_map = {}
    for r in records:
        key = (r.get("brand", ""), r.get("model", ""), r.get("storage", ""))
        cond = r.get("condition", "")
        price = int(round(float(r.get("buyback_price", 0))))
        if key not in device_map:
            device_map[key] = {"Grade A": 0, "Grade B": 0, "Grade C": 0, "Grade D": 0}

        if "Grade A" in cond or "Flawless" in cond or "Like New" in cond:
            device_map[key]["Grade A"] = price
        elif "Grade B" in cond or "Good" in cond:
            device_map[key]["Grade B"] = price
        elif "Grade C" in cond or "Average" in cond or "Fair" in cond:
            device_map[key]["Grade C"] = price
        elif "Grade D" in cond or "Broken" in cond or "Defective" in cond:
            device_map[key]["Grade D"] = price

    with open(matrix_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Brand", "Model", "Storage", "Grade A (Like New)", "Grade B (Good)", "Grade C (Fair)", "Grade D (Broken)", "Market", "Channel", "Currency"])
        for (brand, model, storage), grades in device_map.items():
            writer.writerow([
                brand, model, storage,
                grades["Grade A"], grades["Grade B"], grades["Grade C"], grades["Grade D"],
                "IN", "wholesale", "INR"
            ])

    logger.info("Exported partner rate cards: %s and %s", matrix_path, rows_path)
    return {"matrix": matrix_path, "rows": rows_path}
