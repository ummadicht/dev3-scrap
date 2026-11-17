from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from phone_scraper.analytics.trends import compute_trends_from_dataframe


def _make_history_df() -> pd.DataFrame:
    rows = [
        # Previous month: October 2026
        ("Apple", "iPhone 15", "cashify_sell", "excellent", 45000.0, datetime(2026, 10, 20, 6, 0, tzinfo=UTC)),
        # Previous ISO week (W46): Nov 9 & Nov 10, 2026
        ("Apple", "iPhone 15", "cashify_sell", "excellent", 43000.0, datetime(2026, 11, 9, 6, 0, tzinfo=UTC)),
        ("Apple", "iPhone 15", "cashify_sell", "excellent", 42000.0, datetime(2026, 11, 10, 6, 0, tzinfo=UTC)),
        # Current ISO week (W47): Nov 16 & Nov 17, 2026
        ("Apple", "iPhone 15", "cashify_sell", "excellent", 41000.0, datetime(2026, 11, 16, 6, 0, tzinfo=UTC)),
        ("Apple", "iPhone 15", "cashify_sell", "excellent", 40000.0, datetime(2026, 11, 17, 6, 0, tzinfo=UTC)),
        # Another model to verify filtering
        ("Samsung", "Galaxy S24", "amazon_sell", "good", 39000.0, datetime(2026, 11, 17, 6, 0, tzinfo=UTC)),
    ]
    return pd.DataFrame(
        [
            {
                "brand": b,
                "model": m,
                "source": s,
                "condition": c,
                "price": p,
                "captured_at": dt,
            }
            for b, m, s, c, p, dt in rows
        ]
    )


def test_compute_daily_trends_dod_wow_mom_and_moving_averages() -> None:
    df = _make_history_df()
    trends = compute_trends_from_dataframe(df, granularity="daily", model_filter="iPhone 15")
    assert len(trends) == 5

    latest = trends.iloc[-1]
    assert latest["bucket_date"] == "2026-11-17"
    assert float(latest["avg_price"]) == 40000.0
    # DoD vs 2026-11-16 (41000)
    assert float(latest["dod_abs"]) == -1000.0
    assert float(latest["dod_pct"]) == -2.44
    # WoW: W47 avg = 40500 vs W46 avg = 42500 -> -2000 (-4.71%)
    assert float(latest["wow_abs"]) == -2000.0
    assert float(latest["wow_pct"]) == -4.71
    # MoM: Nov avg = (43000+42000+41000+40000)/4 = 41500 vs Oct avg = 45000 -> -3500 (-7.78%)
    assert float(latest["mom_abs"]) == -3500.0
    assert float(latest["mom_pct"]) == -7.78
    # 7d/30d MAs across 5 observations
    expected_ma = round((45000 + 43000 + 42000 + 41000 + 40000) / 5.0, 2)
    assert float(latest["ma_7d"]) == expected_ma
    assert float(latest["ma_30d"]) == expected_ma


def test_compute_weekly_and_monthly_buckets() -> None:
    df = _make_history_df()
    weekly = compute_trends_from_dataframe(df, granularity="weekly", model_filter="iPhone 15")
    assert list(weekly["bucket_date"]) == ["2026-W43", "2026-W46", "2026-W47"]
    assert float(weekly.iloc[-1]["avg_price"]) == 40500.0

    monthly = compute_trends_from_dataframe(df, granularity="monthly", model_filter="iPhone 15")
    assert list(monthly["bucket_date"]) == ["2026-10", "2026-11"]
    assert float(monthly.iloc[-1]["avg_price"]) == 41500.0
