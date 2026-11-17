from __future__ import annotations

import re
from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from phone_scraper.core.normalize import (
    NormalizedPriceRecord,
    normalize_condition,
    parse_ram_gb,
    parse_storage_gb,
    stable_product_id,
)
from phone_scraper.scrapers.amazon_sell import selectors
from phone_scraper.scrapers.base import ParseError

KNOWN_BRANDS = [
    "Apple",
    "Samsung",
    "OnePlus",
    "Google",
    "Xiaomi",
    "Redmi",
    "Realme",
    "Vivo",
    "Oppo",
    "Motorola",
    "Nothing",
    "iQOO",
]


def _derive_brand(title: str, explicit_brand: str | None = None) -> str:
    if explicit_brand:
        return explicit_brand.strip()
    lower = title.lower()
    for b in KNOWN_BRANDS:
        if b.lower() in lower:
            return b
    if "iphone" in lower:
        return "Apple"
    if "galaxy" in lower:
        return "Samsung"
    if "pixel" in lower:
        return "Google"
    return "Unknown"


def _parse_offer_price(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        return None
    val = float(cleaned)
    return val if val > 0 else None


def _clean_model(title: str, brand: str) -> str:
    clean = re.sub(r"\([^)]*\)", " ", title)
    clean = re.sub(r"\b\d+\s*(?:GB|TB)\b", " ", clean, flags=re.I)
    if brand != "Unknown" and clean.lower().startswith(brand.lower()):
        clean = clean[len(brand) :]
    return re.sub(r"\s+", " ", clean).strip(" -|")


def parse_amazon_sell_html(
    html: str,
    url: str,
    *,
    run_id: str | int,
    captured_at: datetime | None = None,
) -> list[NormalizedPriceRecord]:
    """
    Pure HTML parser for Amazon trade-in / sell-your-phone pricing pages.
    Captures offer price per condition and storage into NormalizedPriceRecord.
    """
    tree = HTMLParser(html)
    ts = captured_at or datetime.now(UTC)
    records: list[NormalizedPriceRecord] = []

    for card in tree.css(selectors.TRADEIN_CARD_SELECTOR):
        title_node = card.css_first(selectors.DEVICE_TITLE_SELECTOR)
        title = (
            card.attributes.get("data-tradein-title")
            or (title_node.text(strip=True) if title_node else "")
        ).strip()
        if not title:
            continue

        brand = _derive_brand(title, card.attributes.get("data-brand"))
        model = _clean_model(title, brand)
        asin = card.attributes.get("data-asin")
        currency = str(card.attributes.get("data-currency") or "INR")
        storage_gb = parse_storage_gb(card.attributes.get("data-storage") or title)
        ram_gb = parse_ram_gb(card.attributes.get("data-ram") or title)
        item_url = card.attributes.get("data-url") or url

        cond_rows = card.css(selectors.CONDITION_ROW_SELECTOR)
        if cond_rows:
            for row in cond_rows:
                cond_raw = row.attributes.get("data-condition") or row.text(strip=True)
                price_node = row.css_first(selectors.OFFER_PRICE_SELECTOR)
                price_raw = row.attributes.get("data-price") or (
                    price_node.text(strip=True) if price_node else None
                )
                price = _parse_offer_price(price_raw)
                if not price:
                    continue
                row_storage = parse_storage_gb(row.attributes.get("data-storage")) or storage_gb
                cond = normalize_condition(cond_raw)
                pid = asin or stable_product_id("amazon_sell", brand, model, row_storage)
                records.append(
                    NormalizedPriceRecord(
                        source="amazon_sell",
                        source_product_id=str(pid),
                        brand=brand,
                        model=model,
                        storage_gb=row_storage,
                        ram_gb=ram_gb,
                        color=row.attributes.get("data-color") or card.attributes.get("data-color"),
                        condition=cond,
                        price=price,
                        currency=currency,
                        mrp=None,
                        discount_pct=None,
                        in_stock=None,
                        source_url=item_url,
                        captured_at=ts,
                        run_id=run_id,
                        raw_payload={
                            "asin": asin,
                            "title": title,
                            "condition_raw": cond_raw,
                            "price_raw": price_raw,
                            "storage_gb": row_storage,
                        },
                    )
                )
        else:
            price_node = card.css_first(selectors.OFFER_PRICE_SELECTOR)
            price_raw = card.attributes.get("data-price") or (
                price_node.text(strip=True) if price_node else None
            )
            price = _parse_offer_price(price_raw)
            if not price:
                continue
            cond = normalize_condition(card.attributes.get("data-condition") or "good")
            pid = asin or stable_product_id("amazon_sell", brand, model, storage_gb)
            records.append(
                NormalizedPriceRecord(
                    source="amazon_sell",
                    source_product_id=str(pid),
                    brand=brand,
                    model=model,
                    storage_gb=storage_gb,
                    ram_gb=ram_gb,
                    color=card.attributes.get("data-color"),
                    condition=cond,
                    price=price,
                    currency=currency,
                    source_url=item_url,
                    captured_at=ts,
                    run_id=run_id,
                    raw_payload={
                        "asin": asin,
                        "title": title,
                        "price_raw": price_raw,
                        "storage_gb": storage_gb,
                    },
                )
            )

    if not records:
        raise ParseError(f"amazon_sell: no trade-in pricing items parsed from {url}")

    return records
