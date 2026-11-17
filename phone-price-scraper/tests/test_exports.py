from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from phone_scraper.config import Settings
from phone_scraper.exports.bucket_paths import (
    ExportGranularity,
    build_export_csv_path,
    build_trends_csv_path,
)
from phone_scraper.exports.csv_export import export_bucketed_dataframe
from phone_scraper.exports.manifest import file_sha256
from phone_scraper.exports.s3_upload import S3Exporter


def test_bucket_paths_for_all_granularities(tmp_path: Path) -> None:
    dt = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)

    daily = build_export_csv_path(tmp_path, "cashify_sell", ExportGranularity.DAILY, dt)
    assert daily == tmp_path / "daily/2026/2026-11/2026-11-17/cashify_sell_daily_2026-11-17.csv"

    weekly = build_export_csv_path(tmp_path, "cashify_buy", ExportGranularity.WEEKLY, dt)
    assert weekly == tmp_path / "weekly/2026/2026-11/2026-W47/cashify_buy_weekly_2026-W47.csv"

    monthly = build_export_csv_path(tmp_path, "amazon_sell", ExportGranularity.MONTHLY, dt)
    assert monthly == tmp_path / "monthly/2026/2026-11/2026-11/amazon_sell_monthly_2026-11.csv"

    trends_daily = build_trends_csv_path(tmp_path, ExportGranularity.DAILY, dt)
    assert trends_daily == tmp_path / "daily/2026/2026-11/2026-11-17/trends_daily_2026-11-17.csv"


def test_export_bucketed_dataframe_writes_csv_trends_and_manifest(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "run_id": 10,
                "source": "cashify_sell",
                "source_product_id": "ip15-128",
                "brand": "Apple",
                "model": "iPhone 15",
                "storage_gb": 128,
                "condition": "excellent",
                "price": 42000.0,
                "currency": "INR",
                "captured_at": datetime(2026, 11, 16, 6, 0, tzinfo=UTC),
            },
            {
                "run_id": 11,
                "source": "cashify_sell",
                "source_product_id": "ip15-128",
                "brand": "Apple",
                "model": "iPhone 15",
                "storage_gb": 128,
                "condition": "excellent",
                "price": 41000.0,
                "currency": "INR",
                "captured_at": datetime(2026, 11, 17, 6, 0, tzinfo=UTC),
            },
        ]
    )

    written = export_bucketed_dataframe(
        df,
        exports_dir=tmp_path,
        granularity=ExportGranularity.DAILY,
        source="all",
    )
    assert len(written) == 6

    day2_csv = tmp_path / "daily/2026/2026-11/2026-11-17/cashify_sell_daily_2026-11-17.csv"
    day2_manifest = tmp_path / "daily/2026/2026-11/2026-11-17/manifest.json"
    day2_trends = tmp_path / "daily/2026/2026-11/2026-11-17/trends_daily_2026-11-17.csv"

    assert day2_csv.exists()
    assert day2_manifest.exists()
    assert day2_trends.exists()

    manifest = json.loads(day2_manifest.read_text(encoding="utf-8"))
    assert manifest["row_count"] == 1
    assert manifest["sha256"] == file_sha256(day2_csv)
    assert manifest["run_ids"] == ["11"]

    trends_df = pd.read_csv(day2_trends)
    assert len(trends_df) == 1
    assert float(trends_df.iloc[0]["dod_abs"]) == -1000.0


def test_s3_exporter_key_matches_local_bucket_structure(tmp_path: Path) -> None:
    settings = Settings(
        s3_enabled=True,
        s3_bucket="phone-prices",
        s3_prefix="exports",
        s3_region="ap-south-1",
        exports_dir=tmp_path,
    )
    exporter = S3Exporter(settings)
    local_file = tmp_path / "daily/2026/2026-11/2026-11-17/cashify_sell_daily_2026-11-17.csv"
    key = exporter.build_key(local_file, tmp_path)
    assert key == "exports/daily/2026/2026-11/2026-11-17/cashify_sell_daily_2026-11-17.csv"
