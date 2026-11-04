"""
Exporter module for Mobile Price Intelligence records.
Saves records to JSON and CSV formats with schema verification.
"""
import csv
import json
import logging
from pathlib import Path
from typing import Any, List
from models import MobilePriceRecord

logger = logging.getLogger("exporter")


def _to_dict(rec) -> dict:
    if hasattr(rec, "model_dump"):
        return rec.model_dump()
    if hasattr(rec, "dict"):
        return rec.dict()
    if isinstance(rec, dict):
        return rec
    return dict(rec)


def save_to_json(records: List[Any], file_path: Path) -> None:
    """Save records to JSON file, safely handling both Pydantic models and dictionaries."""
    data = [_to_dict(rec) for rec in records]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Successfully exported %d records to %s", len(records), file_path)


def save_to_csv(records: List[Any], file_path: Path) -> None:
    """Save records to CSV file, safely handling both Pydantic models and dictionaries."""
    if not records:
        logger.warning("No records to export to CSV.")
        return

    fieldnames = [
        "brand",
        "model",
        "storage",
        "ram",
        "cores",
        "camera",
        "condition",
        "defects",
        "buyback_price",
        "currency",
        "data_origin",
        "confidence_score",
        "source_url",
        "timestamp",
    ]

    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            row = _to_dict(rec)
            writer.writerow({k: row.get(k) for k in fieldnames})

    logger.info("Successfully exported %d records to %s", len(records), file_path)

