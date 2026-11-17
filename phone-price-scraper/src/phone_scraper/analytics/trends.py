from __future__ import annotations

from typing import Literal

import pandas as pd
from rich.console import Console
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.orm import Session


def compute_trends_from_dataframe(
    df: pd.DataFrame,
    granularity: Literal["daily", "weekly", "monthly"] = "daily",
    model_filter: str | None = None,
) -> pd.DataFrame:
    """
    Compute DoD, WoW, MoM (absolute + % deltas) and 7-day / 30-day moving averages
    from snapshot rows with columns: brand, model, source, condition, price, captured_at.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "brand",
                "model",
                "source",
                "condition",
                "bucket_date",
                "avg_price",
                "min_price",
                "max_price",
                "median_price",
                "dod_abs",
                "dod_pct",
                "wow_abs",
                "wow_pct",
                "mom_abs",
                "mom_pct",
                "ma_7d",
                "ma_30d",
            ]
        )

    work = df.copy()
    work["captured_at"] = pd.to_datetime(work["captured_at"], utc=True)
    if model_filter:
        mask = work["model"].astype(str).str.contains(model_filter, case=False, na=False)
        work = work.loc[mask].copy()
        if work.empty:
            return pd.DataFrame()

    work["day"] = work["captured_at"].dt.tz_convert("UTC").dt.floor("D")
    group_cols = ["brand", "model", "source", "condition"]

    # Daily baseline aggregation for DoD + 7d/30d moving averages
    daily = (
        work.groupby([*group_cols, "day"], as_index=False)["price"]
        .agg(
            avg_price="mean",
            min_price="min",
            max_price="max",
            median_price="median",
        )
        .sort_values([*group_cols, "day"])
    )
    daily["avg_price"] = daily["avg_price"].round(2)
    daily["median_price"] = daily["median_price"].round(2)

    daily["prev_day_price"] = daily.groupby(group_cols)["avg_price"].shift(1)
    daily["dod_abs"] = (daily["avg_price"] - daily["prev_day_price"]).round(2)
    daily["dod_pct"] = (
        ((daily["avg_price"] - daily["prev_day_price"]) / daily["prev_day_price"]) * 100.0
    ).round(2)

    daily["ma_7d"] = (
        daily.groupby(group_cols)["avg_price"]
        .transform(lambda s: s.rolling(window=7, min_periods=1).mean())
        .round(2)
    )
    daily["ma_30d"] = (
        daily.groupby(group_cols)["avg_price"]
        .transform(lambda s: s.rolling(window=30, min_periods=1).mean())
        .round(2)
    )

    # ISO weekly delta
    work["week_start"] = (
        work["captured_at"].dt.tz_convert("UTC").dt.to_period("W-SUN").dt.start_time.dt.tz_localize("UTC")
    )
    weekly = (
        work.groupby([*group_cols, "week_start"], as_index=False)["price"]
        .agg(week_avg="mean", week_min="min", week_max="max", week_median="median")
        .sort_values([*group_cols, "week_start"])
    )
    weekly["prev_week_avg"] = weekly.groupby(group_cols)["week_avg"].shift(1)
    weekly["wow_abs"] = (weekly["week_avg"] - weekly["prev_week_avg"]).round(2)
    weekly["wow_pct"] = (
        ((weekly["week_avg"] - weekly["prev_week_avg"]) / weekly["prev_week_avg"]) * 100.0
    ).round(2)

    # Monthly delta
    work["month_start"] = (
        work["captured_at"].dt.tz_convert("UTC").dt.to_period("M").dt.start_time.dt.tz_localize("UTC")
    )
    monthly = (
        work.groupby([*group_cols, "month_start"], as_index=False)["price"]
        .agg(month_avg="mean", month_min="min", month_max="max", month_median="median")
        .sort_values([*group_cols, "month_start"])
    )
    monthly["prev_month_avg"] = monthly.groupby(group_cols)["month_avg"].shift(1)
    monthly["mom_abs"] = (monthly["month_avg"] - monthly["prev_month_avg"]).round(2)
    monthly["mom_pct"] = (
        ((monthly["month_avg"] - monthly["prev_month_avg"]) / monthly["prev_month_avg"]) * 100.0
    ).round(2)

    daily["week_start"] = (
        daily["day"].dt.tz_convert("UTC").dt.to_period("W-SUN").dt.start_time.dt.tz_localize("UTC")
    )
    daily["month_start"] = (
        daily["day"].dt.tz_convert("UTC").dt.to_period("M").dt.start_time.dt.tz_localize("UTC")
    )

    merged = daily.merge(
        weekly[[*group_cols, "week_start", "week_avg", "week_min", "week_max", "week_median", "wow_abs", "wow_pct"]],
        on=[*group_cols, "week_start"],
        how="left",
    ).merge(
        monthly[[*group_cols, "month_start", "month_avg", "month_min", "month_max", "month_median", "mom_abs", "mom_pct"]],
        on=[*group_cols, "month_start"],
        how="left",
    )

    if granularity == "weekly":
        out = (
            merged.sort_values([*group_cols, "day"])
            .groupby([*group_cols, "week_start"], as_index=False)
            .last()
        )
        out["bucket_date"] = out["week_start"].dt.strftime("%G-W%V")
        out["avg_price"] = out["week_avg"].round(2)
        out["min_price"] = out["week_min"].round(2)
        out["max_price"] = out["week_max"].round(2)
        out["median_price"] = out["week_median"].round(2)
    elif granularity == "monthly":
        out = (
            merged.sort_values([*group_cols, "day"])
            .groupby([*group_cols, "month_start"], as_index=False)
            .last()
        )
        out["bucket_date"] = out["month_start"].dt.strftime("%Y-%m")
        out["avg_price"] = out["month_avg"].round(2)
        out["min_price"] = out["month_min"].round(2)
        out["max_price"] = out["month_max"].round(2)
        out["median_price"] = out["month_median"].round(2)
    else:
        out = merged.copy()
        out["bucket_date"] = out["day"].dt.strftime("%Y-%m-%d")

    cols = [
        "brand",
        "model",
        "source",
        "condition",
        "bucket_date",
        "avg_price",
        "min_price",
        "max_price",
        "median_price",
        "dod_abs",
        "dod_pct",
        "wow_abs",
        "wow_pct",
        "mom_abs",
        "mom_pct",
        "ma_7d",
        "ma_30d",
    ]
    return out[cols].reset_index(drop=True)


def query_trends_from_db(
    session: Session,
    *,
    granularity: Literal["daily", "weekly", "monthly"] = "daily",
    model: str | None = None,
) -> pd.DataFrame:
    """Load snapshots from PostgreSQL and compute trend report."""
    sql = """
        SELECT brand, model, source, condition, price, captured_at
        FROM price_snapshots
    """
    params: dict[str, str] = {}
    if model:
        sql += " WHERE LOWER(model) LIKE :model_pattern"
        params["model_pattern"] = f"%{model.lower()}%"
    sql += " ORDER BY captured_at ASC"

    rows = session.execute(text(sql), params).mappings().all()
    df = pd.DataFrame([dict(r) for r in rows])
    return compute_trends_from_dataframe(df, granularity=granularity, model_filter=model)


def render_trends_table(df: pd.DataFrame, granularity: str) -> None:
    """Print formatted trend table to terminal via Rich."""
    console = Console()
    if df.empty:
        console.print("[yellow]No trend records found for the specified criteria.[/yellow]")
        return

    table = Table(title=f"Mobile Price Trends ({granularity.upper()})")
    for col in [
        "Brand",
        "Model",
        "Source",
        "Condition",
        "Bucket",
        "Avg Price",
        "DoD %",
        "WoW %",
        "MoM %",
        "7d MA",
        "30d MA",
    ]:
        table.add_column(col)

    def _fmt(val: object, suffix: str = "") -> str:
        if val is None or pd.isna(val):
            return "-"
        return f"{val}{suffix}"

    for _, row in df.tail(50).iterrows():
        table.add_row(
            str(row["brand"]),
            str(row["model"]),
            str(row["source"]),
            str(row["condition"]),
            str(row["bucket_date"]),
            _fmt(row["avg_price"]),
            _fmt(row["dod_pct"], "%"),
            _fmt(row["wow_pct"], "%"),
            _fmt(row["mom_pct"], "%"),
            _fmt(row["ma_7d"]),
            _fmt(row["ma_30d"]),
        )
    console.print(table)
