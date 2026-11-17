from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, cast

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from phone_scraper.analytics.trends import compute_trends_from_dataframe
from phone_scraper.config import Settings
from phone_scraper.exports.bucket_paths import (
    ExportGranularity,
    bucket_date_token,
    build_export_csv_path,
    build_trends_csv_path,
)
from phone_scraper.exports.manifest import write_manifest
from phone_scraper.exports.s3_upload import S3Exporter


def export_bucketed_dataframe(
    df: pd.DataFrame,
    *,
    exports_dir: Path,
    granularity: ExportGranularity,
    source: str = "all",
    settings: Settings | None = None,
) -> list[Path]:
    """
    Partition a snapshot DataFrame into date-bucketed CSV files, write trends CSV
    and manifest.json per bucket, and optionally upload to S3.
    """
    if df.empty:
        return []

    work = df.copy()
    work["captured_at"] = pd.to_datetime(work["captured_at"], utc=True)
    work["_bucket_key"] = work["captured_at"].apply(
        lambda dt: bucket_date_token(dt.to_pydatetime(), granularity)[3]
    )

    granularity_lit = cast(Literal["daily", "weekly", "monthly"], granularity.value)
    trends_full = compute_trends_from_dataframe(work, granularity=granularity_lit)
    written_files: list[Path] = []
    s3_exporter = S3Exporter(settings) if (settings and settings.s3_enabled) else None

    for bucket_token, bucket_df in work.groupby("_bucket_key"):
        sample_dt = bucket_df["captured_at"].iloc[0].to_pydatetime()
        sources_in_bucket = (
            [source] if source != "all" else sorted(bucket_df["source"].astype(str).unique())
        )

        for src_name in sources_in_bucket:
            src_df = bucket_df[bucket_df["source"] == src_name].drop(columns=["_bucket_key"])
            if src_df.empty:
                continue
            csv_path = build_export_csv_path(exports_dir, src_name, granularity, sample_dt)
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            src_df.to_csv(csv_path, index=False)
            run_ids = src_df["run_id"].tolist() if "run_id" in src_df.columns else []
            manifest_path = write_manifest(
                csv_path,
                row_count=len(src_df),
                run_ids=run_ids,
                source=src_name,
                granularity=granularity.value,
                extra={"bucket": str(bucket_token)},
            )
            written_files.extend([csv_path, manifest_path])
            if s3_exporter:
                s3_exporter.upload_file(csv_path, exports_dir)
                s3_exporter.upload_file(manifest_path, exports_dir)

        # Write trends_{granularity}_{date}.csv in the same bucket directory
        trends_path = build_trends_csv_path(exports_dir, granularity, sample_dt)
        trends_path.parent.mkdir(parents=True, exist_ok=True)
        bucket_trends = (
            trends_full[trends_full["bucket_date"] == str(bucket_token)]
            if not trends_full.empty
            else pd.DataFrame()
        )
        bucket_trends.to_csv(trends_path, index=False)
        written_files.append(trends_path)
        if s3_exporter:
            s3_exporter.upload_file(trends_path, exports_dir)

    return written_files


def export_from_db(
    session: Session,
    *,
    granularity: ExportGranularity,
    from_date: date,
    to_date: date,
    source: str = "all",
    settings: Settings,
) -> list[Path]:
    """Query PostgreSQL snapshots within [from_date, to_date] and export CSV buckets."""
    start_ts = datetime(from_date.year, from_date.month, from_date.day, tzinfo=UTC)
    end_ts = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=UTC)

    sql = """
        SELECT
            id, run_id, model_id, source, source_product_id,
            brand, model, storage_gb, ram_gb, color, condition,
            price, currency, mrp, discount_pct, in_stock,
            source_url, captured_at
        FROM price_snapshots
        WHERE captured_at >= :start_ts AND captured_at <= :end_ts
    """
    params: dict[str, object] = {"start_ts": start_ts, "end_ts": end_ts}
    if source != "all":
        sql += " AND source = :source"
        params["source"] = source
    sql += " ORDER BY captured_at ASC"

    rows = session.execute(text(sql), params).mappings().all()
    df = pd.DataFrame([dict(r) for r in rows])
    return export_bucketed_dataframe(
        df,
        exports_dir=settings.exports_dir,
        granularity=granularity,
        source=source,
        settings=settings,
    )
