from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path


class ExportGranularity(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def bucket_date_token(dt: date | datetime, granularity: ExportGranularity) -> tuple[str, str, str, str]:
    """
    Returns (yyyy, yyyy_mm, bucket_folder, date_token) for a given date & granularity.
    Examples:
      daily   -> ('2026', '2026-11', '2026-11-17', '2026-11-17')
      weekly  -> ('2026', '2026-11', '2026-W47',   '2026-W47')
      monthly -> ('2026', '2026-11', '2026-11',    '2026-11')
    """
    d = dt.date() if isinstance(dt, datetime) else dt
    yyyy = f"{d.year:04d}"
    yyyy_mm = f"{d.year:04d}-{d.month:02d}"

    if granularity == ExportGranularity.DAILY:
        token = d.isoformat()
        return yyyy, yyyy_mm, token, token
    if granularity == ExportGranularity.WEEKLY:
        iso_year, iso_week, _ = d.isocalendar()
        token = f"{iso_year:04d}-W{iso_week:02d}"
        return f"{iso_year:04d}", yyyy_mm, token, token
    if granularity == ExportGranularity.MONTHLY:
        return yyyy, yyyy_mm, yyyy_mm, yyyy_mm
    raise ValueError(f"Unsupported granularity: {granularity}")


def build_bucket_dir(
    base_dir: Path,
    granularity: ExportGranularity,
    bucket_dt: date | datetime,
) -> Path:
    yyyy, yyyy_mm, bucket_folder, _ = bucket_date_token(bucket_dt, granularity)
    return base_dir / granularity.value / yyyy / yyyy_mm / bucket_folder


def build_export_csv_path(
    base_dir: Path,
    source: str,
    granularity: ExportGranularity,
    bucket_dt: date | datetime,
) -> Path:
    _, _, _, date_token = bucket_date_token(bucket_dt, granularity)
    bucket_dir = build_bucket_dir(base_dir, granularity, bucket_dt)
    return bucket_dir / f"{source}_{granularity.value}_{date_token}.csv"


def build_trends_csv_path(
    base_dir: Path,
    granularity: ExportGranularity,
    bucket_dt: date | datetime,
) -> Path:
    _, _, _, date_token = bucket_date_token(bucket_dt, granularity)
    bucket_dir = build_bucket_dir(base_dir, granularity, bucket_dt)
    return bucket_dir / f"trends_{granularity.value}_{date_token}.csv"
