from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from phone_scraper.core.normalize import (
    NormalizedCondition,
    NormalizedPriceRecord,
    compute_discount_pct,
    normalize_condition,
    parse_ram_gb,
    parse_storage_gb,
    stable_product_id,
)
from phone_scraper.scrapers.base import ParseError
from phone_scraper.scrapers.generic_api.paginator import get_by_dotted_path


def _to_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = "".join(ch for ch in str(val) if ch.isdigit() or ch in ".-")
    return float(cleaned) if cleaned else None


def _to_int(val: Any) -> int | None:
    f = _to_float(val)
    return int(round(f)) if f is not None else None


def _to_bool(val: Any) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    text = str(val).strip().lower()
    if text in {"true", "1", "yes", "instock", "in_stock", "available"}:
        return True
    if text in {"false", "0", "no", "outofstock", "out_of_stock", "unavailable"}:
        return False
    return None


TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "strip": lambda v: str(v).strip() if v is not None else None,
    "lower": lambda v: str(v).lower() if v is not None else None,
    "upper": lambda v: str(v).upper() if v is not None else None,
    "to_float": _to_float,
    "to_int": _to_int,
    "to_bool": _to_bool,
    "parse_storage_gb": parse_storage_gb,
    "parse_ram_gb": parse_ram_gb,
    "normalize_condition": lambda v: normalize_condition(str(v) if v is not None else None),
}


def apply_transforms(value: Any, transform_names: list[str]) -> Any:
    current = value
    for name in transform_names:
        fn = TRANSFORMS.get(name)
        if fn is None:
            raise ValueError(f"Unknown field_map transform: {name}")
        current = fn(current)
    return current


def extract_items_list(payload: Any, items_path: str | None) -> list[dict[str, Any]]:
    raw = get_by_dotted_path(payload, items_path)
    if raw is None:
        raise ParseError(f"Expected items_path '{items_path}' not found in API payload")
    if not isinstance(raw, list):
        raise ParseError(f"Expected list at items_path '{items_path}', got {type(raw).__name__}")
    return [item for item in raw if isinstance(item, dict)]


def map_api_records(
    payload: Any,
    *,
    source_name: str,
    source_url: str,
    items_path: str | None,
    field_map: dict[str, Any],
    run_id: str | int,
    captured_at: datetime | None = None,
) -> list[NormalizedPriceRecord]:
    items = extract_items_list(payload, items_path)
    if not items:
        return []

    ts = captured_at or datetime.now(UTC)
    records: list[NormalizedPriceRecord] = []

    for item in items:
        mapped: dict[str, Any] = {}
        for target_field, spec in field_map.items():
            if isinstance(spec, str):
                path = spec
                transforms: list[str] = []
            elif isinstance(spec, dict):
                path = str(spec.get("path", ""))
                transforms = [str(t) for t in spec.get("transforms", [])]
            else:
                continue
            raw_val = get_by_dotted_path(item, path)
            mapped[target_field] = apply_transforms(raw_val, transforms)

        brand = str(mapped.get("brand") or "Unknown").strip()
        model = str(mapped.get("model") or "Unknown").strip()
        price = mapped.get("price")
        if price is None or float(price) <= 0:
            continue

        mrp = mapped.get("mrp")
        discount_pct = mapped.get("discount_pct")
        if discount_pct is None and mrp is not None:
            discount_pct = compute_discount_pct(float(price), float(mrp))

        cond = mapped.get("condition")
        if not isinstance(cond, NormalizedCondition):
            cond = normalize_condition(str(cond) if cond is not None else None)

        storage_gb = mapped.get("storage_gb")
        if storage_gb is not None and not isinstance(storage_gb, int):
            storage_gb = parse_storage_gb(storage_gb)

        ram_gb = mapped.get("ram_gb")
        if ram_gb is not None and not isinstance(ram_gb, int):
            ram_gb = parse_ram_gb(ram_gb)

        pid = str(
            mapped.get("source_product_id")
            or stable_product_id(source_name, brand, model, storage_gb, cond.value)
        )

        records.append(
            NormalizedPriceRecord(
                source=source_name,
                source_product_id=pid,
                brand=brand,
                model=model,
                storage_gb=storage_gb,
                ram_gb=ram_gb,
                color=mapped.get("color"),
                condition=cond,
                price=float(price),
                currency=str(mapped.get("currency") or "INR"),
                mrp=float(mrp) if mrp is not None else None,
                discount_pct=float(discount_pct) if discount_pct is not None else None,
                in_stock=mapped.get("in_stock"),
                source_url=str(mapped.get("source_url") or source_url),
                captured_at=ts,
                run_id=run_id,
                raw_payload=item,
            )
        )

    return records
