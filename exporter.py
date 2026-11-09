"""
Exporter module for Cashify Mobile Price Intelligence & Scraping Platform.
Generates two separate, independent reports as requested by team management:
1. Buy Mobile Prices Report (Cashify buyback prices from customers)
2. Refurbished Sell Mobile Prices Report (Cashify refurbished selling prices with prominent REFURBISHED mark)
3. Profit Margin Intelligence Report (Comparing Buy Price vs Refurbished Sell Price)

Supports CSV, Excel (.xlsx), and JSON formats.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd

logger = logging.getLogger("exporter")


def _to_dict(rec: Any) -> dict:
    if hasattr(rec, "model_dump"):
        return rec.model_dump()
    if hasattr(rec, "dict"):
        return rec.dict()
    if isinstance(rec, dict):
        return rec
    return dict(rec)


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepares dataframe for export by converting datetimes to timezone-naive strings."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
        elif out[col].dtype == object:
            # Check if elements are datetime objects
            out[col] = out[col].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if hasattr(x, "strftime") else x)
    return out


# =============================================================================
# 1. Buy Mobile Prices Report (Cashify Buyback Pricing)
# =============================================================================

BUY_REPORT_COLUMNS = [
    "brand",
    "model",
    "model_series",
    "variant",
    "storage",
    "ram",
    "condition",
    "defects",
    "buyback_price",
    "currency",
    "data_origin",
    "confidence_score",
    "source_url",
    "scraped_at",
]

def export_buy_report(
    records: List[Any],
    file_path: Union[str, Path],
    format: str = "csv"
) -> Path:
    """
    Exports independent Cashify Buy Mobile Prices Report to CSV, Excel, or JSON.
    """
    path = Path(file_path)
    data = [_to_dict(r) for r in records]
    
    # Standardize timestamp / scraped_at
    for row in data:
        if "scraped_at" not in row and "timestamp" in row:
            row["scraped_at"] = row["timestamp"]

    df = pd.DataFrame(data)
    # Reindex with standard columns, filling missing with None or empty
    for col in BUY_REPORT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    cols = [c for c in BUY_REPORT_COLUMNS if c in df.columns] + [c for c in df.columns if c not in BUY_REPORT_COLUMNS]
    df = _prepare_df(df[cols])

    fmt = format.lower()
    if fmt in ("xlsx", "excel"):
        if not path.suffix.endswith(".xlsx"):
            path = path.with_suffix(".xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Buyback_Prices")
    elif fmt == "json":
        if not path.suffix.endswith(".json"):
            path = path.with_suffix(".json")
        df.to_json(path, orient="records", indent=2)
    else:  # default csv
        if not path.suffix.endswith(".csv"):
            path = path.with_suffix(".csv")
        df.to_csv(path, index=False, encoding="utf-8")

    logger.info("Exported Buy Mobile Report (%d records) to %s", len(records), path)
    return path


# =============================================================================
# 2. Refurbished Sell Mobile Prices Report (Dedicated Sell Report with REFURBISHED mark)
# =============================================================================

SELL_REPORT_COLUMNS = [
    "refurbished_mark",     # Prominent REFURBISHED mark
    "is_refurbished",       # Boolean TRUE
    "brand",
    "model",
    "model_series",
    "variant",
    "storage",
    "ram",
    "color",
    "network_type",
    "refurbished_grade",    # Superb, Good, Fair, Best Value
    "device_condition",
    "selling_price",        # Cashify Selling Price
    "original_mrp",         # Original List Price
    "discount_percent",     # % Discount vs MRP
    "warranty",             # 6 Months Cashify Warranty
    "availability",         # InStock / OutOfStock
    "sku",
    "currency",
    "source_url",
    "scraped_at",
]

def export_sell_report(
    records: List[Any],
    file_path: Union[str, Path],
    format: str = "csv"
) -> Path:
    """
    Exports independent Cashify Refurbished Sell Mobile Prices Report.
    Ensures every record carries the prominent 'REFURBISHED' mark and condition grade.
    """
    path = Path(file_path)
    data = [_to_dict(r) for r in records]

    for row in data:
        # Guarantee Refurbished marks
        row["is_refurbished"] = True
        if not row.get("refurbished_mark"):
            row["refurbished_mark"] = "REFURBISHED"
        if not row.get("warranty"):
            row["warranty"] = "6 Months Warranty, 15 Days Refund"
        if "scraped_at" not in row and "timestamp" in row:
            row["scraped_at"] = row["timestamp"]

    df = pd.DataFrame(data)
    for col in SELL_REPORT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    cols = [c for c in SELL_REPORT_COLUMNS if c in df.columns] + [c for c in df.columns if c not in SELL_REPORT_COLUMNS]
    df = _prepare_df(df[cols])

    fmt = format.lower()
    if fmt in ("xlsx", "excel"):
        if not path.suffix.endswith(".xlsx"):
            path = path.with_suffix(".xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Refurbished_Sell_Prices")
    elif fmt == "json":
        if not path.suffix.endswith(".json"):
            path = path.with_suffix(".json")
        df.to_json(path, orient="records", indent=2)
    else:  # default csv
        if not path.suffix.endswith(".csv"):
            path = path.with_suffix(".csv")
        df.to_csv(path, index=False, encoding="utf-8")

    logger.info("Exported Refurbished Sell Mobile Report (%d records) to %s", len(records), path)
    return path


# =============================================================================
# 3. Price Intelligence & Margin Analysis Report
# =============================================================================

MARGIN_REPORT_COLUMNS = [
    "brand",
    "model",
    "storage",
    "refurbished_mark",
    "refurbished_grade",
    "cashify_buy_price",
    "cashify_sell_price",
    "original_mrp",
    "gross_margin",
    "margin_percentage",
    "warranty",
    "buy_url",
    "sell_url",
]

def export_margin_report(
    records: List[Any],
    file_path: Union[str, Path],
    format: str = "csv"
) -> Path:
    """Exports Buy vs Sell Margin Comparison Report to CSV, Excel, or JSON."""
    path = Path(file_path)
    data = [_to_dict(r) for r in records]

    df = pd.DataFrame(data)
    for col in MARGIN_REPORT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    cols = [c for c in MARGIN_REPORT_COLUMNS if c in df.columns] + [c for c in df.columns if c not in MARGIN_REPORT_COLUMNS]
    df = _prepare_df(df[cols])

    fmt = format.lower()
    if fmt in ("xlsx", "excel"):
        if not path.suffix.endswith(".xlsx"):
            path = path.with_suffix(".xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Margin_Intelligence")
    elif fmt == "json":
        if not path.suffix.endswith(".json"):
            path = path.with_suffix(".json")
        df.to_json(path, orient="records", indent=2)
    else:
        if not path.suffix.endswith(".csv"):
            path = path.with_suffix(".csv")
        df.to_csv(path, index=False, encoding="utf-8")

    logger.info("Exported Margin Intelligence Report (%d records) to %s", len(records), path)
    return path


# =============================================================================
# Backward Compatibility Helpers
# =============================================================================

def save_to_json(records: List[Any], file_path: Path) -> None:
    """Save records to JSON file."""
    export_buy_report(records, file_path, format="json")


def save_to_csv(records: List[Any], file_path: Path) -> None:
    """Save records to CSV file."""
    export_buy_report(records, file_path, format="csv")
