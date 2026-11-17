from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup

from phone_scraper.core.normalize import (
    NormalizedPriceRecord,
    compute_discount_pct,
    normalize_condition,
    parse_ram_gb,
    parse_storage_gb,
    stable_product_id,
)
from phone_scraper.scrapers.base import ParseError
from phone_scraper.scrapers.cashify_buy import selectors


def _parse_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    return float(cleaned) if cleaned else None


def parse_cashify_buy_html(
    html: str,
    url: str,
    *,
    run_id: str | int,
    captured_at: datetime | None = None,
) -> list[NormalizedPriceRecord]:
    """
    Pure parser for Cashify 'Buy refurbished phone' listings.
    Extracts selling price, MRP, discount_pct, storage, color, condition, warranty, and availability.
    """
    soup = BeautifulSoup(html, "html.parser")
    ts = captured_at or datetime.now(UTC)
    records: list[NormalizedPriceRecord] = []

    for script in soup.select(selectors.JSON_LD_SELECTOR):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") != "ProductGroup" or "hasVariant" not in item:
                continue

            raw_model = str(item.get("name") or "Unknown Device")
            clean_model = re.sub(r"\s*-\s*Refurbished.*$", "", raw_model, flags=re.I).strip()
            brand_info = item.get("brand")
            brand = (
                str(brand_info.get("name"))
                if isinstance(brand_info, dict) and brand_info.get("name")
                else ("Apple" if "iphone" in clean_model.lower() else "Samsung")
            )
            if brand and clean_model.lower().startswith(brand.lower()):
                clean_model = clean_model[len(brand) :].strip()

            for variant in item.get("hasVariant", []):
                if not isinstance(variant, dict):
                    continue
                offers = variant.get("offers") or {}
                selling_price = _parse_float(offers.get("price"))
                if not selling_price or selling_price <= 0:
                    continue

                mrp = _parse_float(variant.get("mrp") or offers.get("highPrice"))
                discount_pct = compute_discount_pct(selling_price, mrp)
                v_name = str(variant.get("name") or "")
                v_desc = str(variant.get("description") or "")

                ram_match = re.search(r"(\d+)\s*GB\s*/\s*(\d+\s*(?:GB|TB))", v_name, re.I)
                ram_gb = parse_ram_gb(ram_match.group(1) if ram_match else variant.get("ram"))
                storage_gb = parse_storage_gb(
                    ram_match.group(2) if ram_match else (variant.get("storage") or v_name)
                )

                grade_raw = str(variant.get("conditionGrade") or offers.get("itemCondition") or "")
                if not grade_raw:
                    m_grade = re.search(r"(Superb|Good|Fair|Excellent|Like New)", v_desc, re.I)
                    grade_raw = m_grade.group(1) if m_grade else "good"
                condition = normalize_condition(grade_raw)

                avail_str = str(offers.get("availability") or "").lower()
                in_stock = "instock" in avail_str if avail_str else None
                warranty = str(variant.get("warranty") or "6 Months Warranty")
                sku = str(variant.get("sku") or stable_product_id("cashify_buy", brand, clean_model, storage_gb, variant.get("color")))

                records.append(
                    NormalizedPriceRecord(
                        source="cashify_buy",
                        source_product_id=sku,
                        brand=brand,
                        model=clean_model,
                        storage_gb=storage_gb,
                        ram_gb=ram_gb,
                        color=variant.get("color"),
                        condition=condition,
                        price=selling_price,
                        currency=str(offers.get("priceCurrency") or "INR"),
                        mrp=mrp,
                        discount_pct=discount_pct,
                        in_stock=in_stock,
                        source_url=str(offers.get("url") or url),
                        captured_at=ts,
                        run_id=run_id,
                        raw_payload={
                            **variant,
                            "warranty": warranty,
                        },
                    )
                )

    # HTML card fallback if JSON-LD is absent
    if not records:
        for card in soup.select(selectors.LISTING_CARD_SELECTOR):
            price = _parse_float(card.get("data-price"))
            if not price or price <= 0:
                continue
            mrp = _parse_float(card.get("data-mrp"))
            brand = str(card.get("data-brand") or "Unknown")
            model = str(card.get("data-model") or "Unknown")
            storage_gb = parse_storage_gb(str(card.get("data-storage") or ""))
            ram_gb = parse_ram_gb(str(card.get("data-ram") or ""))
            cond = normalize_condition(str(card.get("data-condition") or "good"))
            in_stock_raw = str(card.get("data-in-stock") or "").lower()
            in_stock = in_stock_raw == "true" if in_stock_raw else None
            pid = str(card.get("data-sku") or stable_product_id("cashify_buy", brand, model, storage_gb, cond.value))
            records.append(
                NormalizedPriceRecord(
                    source="cashify_buy",
                    source_product_id=pid,
                    brand=brand,
                    model=model,
                    storage_gb=storage_gb,
                    ram_gb=ram_gb,
                    color=str(card.get("data-color") or "") or None,
                    condition=cond,
                    price=price,
                    currency="INR",
                    mrp=mrp,
                    discount_pct=compute_discount_pct(price, mrp),
                    in_stock=in_stock,
                    source_url=url,
                    captured_at=ts,
                    run_id=run_id,
                    raw_payload=dict(card.attrs),
                )
            )

    if not records:
        raise ParseError(f"cashify_buy: no refurbished listings parsed from {url}")

    return records
