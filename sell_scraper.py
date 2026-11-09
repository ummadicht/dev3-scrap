"""
Cashify Refurbished Sell Price Scraper (Sell Price Tracking Module)
===================================================================
Scrapes mobile phone pricing information from Cashify's "Buy Refurbished Phones" section:
https://www.cashify.in/buy-refurbished-mobile-phones

Features:
1. Independent module dedicated to Refurbished Sell Prices (separate from Buyback).
2. Initial support for Apple iPhone and Samsung Galaxy (modular architecture for adding any brand).
3. Automatically marks devices with 'REFURBISHED' badge/mark.
4. Captures condition grades: Superb, Good, Fair, Best Value.
5. Captures Selling Price, Original MRP, Discount %, Warranty, RAM/Storage variants.
6. Saves records directly into PostgreSQL 'cashify_sell_prices' table.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, REQUEST_TIMEOUT_SECONDS, MAX_RETRIES, RETRY_BACKOFF_FACTOR
from db import DatabaseManager
from models import CashifySellPriceRecord
from exporter import export_sell_report

logger = logging.getLogger("sell_scraper")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Targeted top Apple & Samsung refurbished models for quick direct scans
CURATED_REFURBISHED_TARGETS = {
    "apple": [
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-13",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-14",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-12",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-11",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-15",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-14-pro",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-13-pro",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-15-pro",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-xr",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-apple-iphone-xs",
    ],
    "samsung": [
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-s22-ultra",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-s23-5g",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-s23-ultra-5g",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-s21-ultra-5g",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-z-flip-5",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-z-fold-6-5g",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-s24-ultra",
        "https://www.cashify.in/buy-refurbished-mobile-phones/renewed-samsung-galaxy-m47-5g",
    ],
}


class CashifySellScraper:
    """Independent scraper for Cashify Refurbished Mobile Sales."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.max_retries = max_retries
        self.db = db_manager or DatabaseManager()

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch URL content with retry backoff."""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Fetching refurbished URL (attempt %d/%d): %s", attempt, self.max_retries, url)
                res = self.session.get(url, timeout=self.timeout)
                if res.status_code == 200:
                    return res.text
                if res.status_code == 404:
                    logger.warning("Refurbished page not found (404): %s", url)
                    return None
                logger.warning("HTTP %d for %s", res.status_code, url)
            except requests.RequestException as e:
                logger.error("Request error on %s: %s", url, e)

            if attempt < self.max_retries:
                time.sleep(RETRY_BACKOFF_FACTOR ** attempt)
        return None

    def discover_brand_models(self, brand: str = "apple", limit: Optional[int] = None) -> List[str]:
        """
        Discovers refurbished device URLs for a brand using Cashify sitemaps & brand listing pages.
        """
        brand_clean = brand.strip().lower()
        discovered_urls: set[str] = set()

        # 1. Use curated top models first
        if brand_clean in CURATED_REFURBISHED_TARGETS:
            discovered_urls.update(CURATED_REFURBISHED_TARGETS[brand_clean])

        # 2. Try official Cashify refurbished sitemap
        try:
            for sitemap_idx in range(2):
                sitemap_url = f"https://smp.cashify.in/uzi1/cashify/refurbished/product-{sitemap_idx}.xml"
                res = self.session.get(sitemap_url, timeout=10)
                if res.status_code == 200:
                    matches = re.findall(r'<loc>(https://www.cashify.in/buy-refurbished-mobile-phones/[^<]+)</loc>', res.text)
                    for m in matches:
                        if brand_clean == "apple" and ("apple" in m.lower() or "iphone" in m.lower()):
                            discovered_urls.add(m)
                        elif brand_clean in m.lower():
                            discovered_urls.add(m)
        except Exception as e:
            logger.warning("Could not fetch sitemap for brand %s: %s", brand, e)

        # 3. Try direct brand category page
        try:
            brand_cat_url = f"https://www.cashify.in/buy-refurbished-mobile-phones/{brand_clean}"
            html = self.fetch_page(brand_cat_url)
            if html:
                matches = re.findall(r'href="(/buy-refurbished-mobile-phones/renewed-[^"]+)"', html)
                for m in matches:
                    full = f"https://www.cashify.in{m}"
                    discovered_urls.add(full)
        except Exception as e:
            logger.warning("Could not parse category page: %s", e)

        url_list = sorted(list(discovered_urls))
        if limit and limit > 0:
            url_list = url_list[:limit]
        logger.info("Discovered %d refurbished URLs for brand '%s'.", len(url_list), brand)
        return url_list

    def parse_device_page(self, url: str) -> List[CashifySellPriceRecord]:
        """
        Parses a refurbished device page and returns a list of CashifySellPriceRecord
        representing all available variants, colors, and condition grades.
        """
        html = self.fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        records: List[CashifySellPriceRecord] = []

        # Find application/ld+json scripts containing ProductGroup
        for s in soup.find_all("script", type="application/ld+json"):
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "ProductGroup" and "hasVariant" in item:
                        raw_title = item.get("name", "")
                        # Clean model name: remove " - Refurbished"
                        clean_model = re.sub(r'\s*-\s*Refurbished.*$', '', raw_title, flags=re.IGNORECASE).strip()
                        
                        brand_info = item.get("brand", {})
                        brand_name = brand_info.get("name") if isinstance(brand_info, dict) else "Apple"
                        if not brand_name or brand_name.lower() == "unknown":
                            if "iphone" in clean_model.lower():
                                brand_name = "Apple"
                            elif "galaxy" in clean_model.lower() or "samsung" in clean_model.lower():
                                brand_name = "Samsung"

                        # Series detection
                        model_series = None
                        if "iphone 16" in clean_model.lower():
                            model_series = "iPhone 16 Series"
                        elif "iphone 15" in clean_model.lower():
                            model_series = "iPhone 15 Series"
                        elif "iphone 14" in clean_model.lower():
                            model_series = "iPhone 14 Series"
                        elif "iphone 13" in clean_model.lower():
                            model_series = "iPhone 13 Series"
                        elif "iphone 12" in clean_model.lower():
                            model_series = "iPhone 12 Series"
                        elif "galaxy s2" in clean_model.lower():
                            model_series = "Galaxy S Series"
                        elif "galaxy z" in clean_model.lower():
                            model_series = "Galaxy Z Series"

                        for v in item.get("hasVariant", []):
                            v_name = v.get("name", "")
                            v_desc = v.get("description", "")
                            color = v.get("color")
                            sku = v.get("sku")
                            offers = v.get("offers", {})

                            try:
                                selling_price = int(float(offers.get("price", 0)))
                            except (ValueError, TypeError):
                                continue

                            if selling_price <= 0:
                                continue

                            # Original MRP (ListPrice)
                            original_mrp = None
                            for sp in offers.get("priceSpecification", []):
                                if "ListPrice" in sp.get("priceType", ""):
                                    try:
                                        original_mrp = int(float(sp.get("price", 0)))
                                    except (ValueError, TypeError):
                                        pass

                            discount_percent = None
                            if original_mrp and original_mrp > selling_price:
                                discount_percent = round(((original_mrp - selling_price) / original_mrp) * 100, 1)

                            # Refurbished Condition Grade
                            # Superb: Like New, zero scratches
                            # Good: Minor scratches
                            # Fair: Visible scratches
                            # Best Value: Certified functioning at best discount
                            combined_text = f"{v_name} {v_desc}".lower()
                            if "superb" in combined_text:
                                grade = "Superb"
                            elif "best value" in combined_text:
                                grade = "Best Value"
                            elif "fair" in combined_text:
                                grade = "Fair"
                            elif "good" in combined_text:
                                grade = "Good"
                            else:
                                grade = "Superb"

                            # Variant / RAM & Storage parsing
                            ram = None
                            storage = None
                            # Pattern: "4 GB / 128 GB" or "8 GB / 256 GB" or "12 GB / 1 TB"
                            ram_storage_match = re.search(r'(\d+\s*GB)\s*/\s*(\d+\s*(?:GB|TB))', combined_text, re.IGNORECASE)
                            if ram_storage_match:
                                ram = ram_storage_match.group(1).upper()
                                storage = ram_storage_match.group(2).upper()
                            else:
                                storage_match = re.search(r'(\d+\s*(?:GB|TB))', combined_text, re.IGNORECASE)
                                if storage_match:
                                    storage = storage_match.group(1).upper()

                            variant_str = f"{ram} / {storage}" if ram and storage else (storage or "Standard")
                            network_type = "5G" if "5g" in combined_text else "4G"
                            stock_status = "InStock" if "InStock" in offers.get("availability", "InStock") else "OutOfStock"
                            variant_url = offers.get("url") or url

                            record = CashifySellPriceRecord(
                                brand=brand_name,
                                model=clean_model,
                                model_series=model_series,
                                variant=variant_str,
                                storage=storage,
                                ram=ram,
                                color=color,
                                network_type=network_type,
                                is_refurbished=True,                       # Explicitly Refurbished
                                refurbished_mark="REFURBISHED",            # Prominent visual mark
                                refurbished_grade=grade,
                                device_condition=f"Refurbished - {grade}",
                                selling_price=selling_price,
                                original_mrp=original_mrp,
                                discount_percent=discount_percent,
                                warranty="6 Months Warranty, 15 Days Refund",
                                availability=stock_status,
                                sku=sku,
                                currency="INR",
                                source_url=variant_url,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                            )
                            records.append(record)
            except Exception as e:
                logger.debug("Failed parsing ld+json chunk: %s", e)

        logger.info("Parsed %d refurbished variant quotes for %s", len(records), url)
        return records

    def scrape_and_save_brand(
        self,
        brand: str = "apple",
        max_devices: int = 5,
        save_db: bool = True
    ) -> List[CashifySellPriceRecord]:
        """
        Discovers and scrapes refurbished models for a brand, then upserts to DB.
        """
        urls = self.discover_brand_models(brand, limit=max_devices)
        all_records: List[CashifySellPriceRecord] = []

        for u in urls:
            device_records = self.parse_device_page(u)
            all_records.extend(device_records)
            time.sleep(0.5)  # Respectful crawling

        if save_db and all_records:
            dicts = [r.model_dump() for r in all_records]
            self.db.upsert_sell_records(dicts)
            logger.info("Saved %d refurbished records to database for brand '%s'.", len(all_records), brand)

        return all_records


def main():
    parser = argparse.ArgumentParser(description="Cashify Refurbished Sell Price Scraper")
    parser.add_argument("--brand", choices=["apple", "samsung", "all"], default="apple", help="Brand to scrape")
    parser.add_argument("--limit", type=int, default=5, help="Max devices per brand")
    parser.add_argument("--export", choices=["csv", "excel", "json"], default="csv", help="Export format")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    scraper = CashifySellScraper()
    brands = ["apple", "samsung"] if args.brand == "all" else [args.brand]

    all_records: List[CashifySellPriceRecord] = []
    for b in brands:
        print(f"\n--- Starting Refurbished Scraping for Brand: {b.upper()} ---")
        recs = scraper.scrape_and_save_brand(b, max_devices=args.limit, save_db=True)
        all_records.extend(recs)

    print(f"\nTotal Refurbished Records Scraped: {len(all_records)}")

    if all_records:
        out_name = args.output or f"cashify_sell_refurbished_prices_report.{args.export}"
        out_path = Path(out_name)
        export_sell_report(all_records, out_path, format=args.export)
        print(f"Report exported to: {out_path.resolve()}")


if __name__ == "__main__":
    main()

