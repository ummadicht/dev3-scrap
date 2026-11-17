from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from phone_scraper.core.normalize import (
    NormalizedCondition,
    NormalizedPriceRecord,
    normalize_condition,
    parse_ram_gb,
    parse_storage_gb,
    stable_product_id,
)
from phone_scraper.scrapers.base import ParseError
from phone_scraper.scrapers.cashify_sell import selectors


def _clean_model_title(raw_title: str, brand: str) -> str:
    cleaned = re.sub(r"^Sell\s+Old\s+", "", raw_title.strip(), flags=re.I)
    cleaned = re.sub(r"\s*Online\s*&.*$", "", cleaned, flags=re.I)
    if brand and cleaned.lower().startswith(brand.lower()):
        cleaned = cleaned[len(brand) :].strip()
    cleaned = re.sub(r"\s*\(\s*\d+\s*(?:GB|TB).*?\)\s*$", "", cleaned, flags=re.I)
    return cleaned.strip() or raw_title.strip()


def _parse_price_value(raw: str | int | float | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    if not cleaned:
        return None
    val = float(cleaned)
    return val if val > 0 else None


def extract_variant_urls(html: str, base_url: str = "https://www.cashify.in") -> list[str]:
    tree = HTMLParser(html)
    urls: set[str] = set()
    for node in tree.css(selectors.VARIANT_CONTAINER_SELECTOR):
        href = node.attributes.get("href")
        if href:
            urls.add(urljoin(base_url, href.split("?")[0]))
    return sorted(urls)


def parse_cashify_sell_html(
    html: str,
    url: str,
    *,
    run_id: str | int,
    captured_at: datetime | None = None,
) -> list[NormalizedPriceRecord]:
    """
    Pure HTML parser for Cashify 'Sell old phone' pages.
    Extracts storage variants and condition grades from __NEXT_DATA__, condition cards,
    or Schema.org metadata, storing raw_payload alongside each parsed record.
    """
    tree = HTMLParser(html)
    ts = captured_at or datetime.now(UTC)
    records: list[NormalizedPriceRecord] = []

    h1_node = tree.css_first(selectors.TITLE_SELECTOR)
    raw_title = h1_node.text(strip=True) if h1_node else ""
    brand_node = tree.css_first(selectors.BRAND_SELECTOR)
    brand = (
        (brand_node.attributes.get("content") or brand_node.text(strip=True))
        if brand_node
        else ""
    )
    if not brand:
        if "iphone" in raw_title.lower() or "apple" in url.lower():
            brand = "Apple"
        elif "galaxy" in raw_title.lower() or "samsung" in url.lower():
            brand = "Samsung"
        else:
            brand = "Unknown"

    model = _clean_model_title(raw_title or "Unknown Device", brand)

    # 1. Preferred structured source: Next.js __NEXT_DATA__ JSON
    next_script = tree.css_first(selectors.NEXT_DATA_SELECTOR)
    if next_script is not None and next_script.text():
        try:
            next_data: dict[str, Any] = json.loads(next_script.text())
        except json.JSONDecodeError as exc:
            raise ParseError(f"cashify_sell: invalid __NEXT_DATA__ JSON at {url}") from exc

        page_props = next_data.get("props", {}).get("pageProps", {})
        product = page_props.get("product") or {}
        if product:
            brand = str(product.get("brand") or brand).strip()
            model = _clean_model_title(str(product.get("name") or model), brand)
            variants = product.get("variants") or []
            for variant in variants:
                storage_gb = parse_storage_gb(variant.get("storage") or variant.get("name"))
                ram_gb = parse_ram_gb(variant.get("ram"))
                v_url = str(variant.get("url") or url)
                quotes = variant.get("conditionQuotes") or []
                for q in quotes:
                    price = _parse_price_value(q.get("price"))
                    if not price:
                        continue
                    cond_raw = str(q.get("grade") or q.get("label") or "unknown")
                    cond = normalize_condition(cond_raw)
                    pid = str(
                        q.get("id")
                        or variant.get("id")
                        or stable_product_id("cashify_sell", brand, model, storage_gb)
                    )
                    records.append(
                        NormalizedPriceRecord(
                            source="cashify_sell",
                            source_product_id=pid,
                            brand=brand,
                            model=model,
                            storage_gb=storage_gb,
                            ram_gb=ram_gb,
                            color=variant.get("color"),
                            condition=cond,
                            price=price,
                            currency="INR",
                            mrp=None,
                            discount_pct=None,
                            in_stock=None,
                            source_url=v_url,
                            captured_at=ts,
                            run_id=run_id,
                            raw_payload={
                                "product": product.get("name"),
                                "variant": variant,
                                "quote": q,
                            },
                        )
                    )

    # 2. Condition cards in HTML
    if not records:
        storage_gb = parse_storage_gb(raw_title or url)
        ram_gb = parse_ram_gb(raw_title or url)
        for card in tree.css(selectors.CONDITION_CARD_SELECTOR):
            grade_label = card.attributes.get("data-grade") or (
                card.css_first(".grade-name").text(strip=True)
                if card.css_first(".grade-name")
                else ""
            )
            price_el = card.css_first(".grade-price") or card.css_first("[itemprop='price']")
            price = _parse_price_value(
                price_el.attributes.get("content") or price_el.text(strip=True)
                if price_el
                else card.attributes.get("data-price")
            )
            if not price:
                continue
            cond = normalize_condition(grade_label)
            pid = str(
                card.attributes.get("data-sku")
                or stable_product_id("cashify_sell", brand, model, storage_gb)
            )
            records.append(
                NormalizedPriceRecord(
                    source="cashify_sell",
                    source_product_id=pid,
                    brand=brand,
                    model=model,
                    storage_gb=storage_gb,
                    ram_gb=ram_gb,
                    condition=cond,
                    price=price,
                    currency="INR",
                    source_url=url,
                    captured_at=ts,
                    run_id=run_id,
                    raw_payload={"grade_label": grade_label, "price": price, "title": raw_title},
                )
            )

    # 3. Single Schema.org price fallback
    if not records:
        price_node = tree.css_first(selectors.PRICE_SELECTOR)
        if price_node is not None:
            raw_p = price_node.attributes.get("content") or price_node.text(strip=True)
            price = _parse_price_value(raw_p)
            if price:
                storage_gb = parse_storage_gb(raw_title or url)
                ram_gb = parse_ram_gb(raw_title or url)
                records.append(
                    NormalizedPriceRecord(
                        source="cashify_sell",
                        source_product_id=stable_product_id("cashify_sell", brand, model, storage_gb),
                        brand=brand,
                        model=model,
                        storage_gb=storage_gb,
                        ram_gb=ram_gb,
                        condition=NormalizedCondition.EXCELLENT,
                        price=price,
                        currency="INR",
                        source_url=url,
                        captured_at=ts,
                        run_id=run_id,
                        raw_payload={"title": raw_title, "schema_price": raw_p},
                    )
                )

    if not records:
        raise ParseError(f"cashify_sell: no buyback quotes parsed from {url}")

    return records
