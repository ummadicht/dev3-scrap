-- Daily aggregated prices
CREATE OR REPLACE VIEW price_daily AS
SELECT
    model_id,
    brand,
    model,
    source,
    condition,
    (captured_at AT TIME ZONE 'UTC')::date AS bucket_date,
    ROUND(AVG(price)::numeric, 2)::double precision AS avg_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    ROUND(
        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::numeric, 2
    )::double precision AS median_price,
    COUNT(*)::int AS sample_count
FROM price_snapshots
GROUP BY model_id, brand, model, source, condition, (captured_at AT TIME ZONE 'UTC')::date;

-- ISO Weekly aggregated prices
CREATE OR REPLACE VIEW price_weekly AS
SELECT
    model_id,
    brand,
    model,
    source,
    condition,
    DATE_TRUNC('week', captured_at AT TIME ZONE 'UTC')::date AS week_start,
    TO_CHAR(captured_at AT TIME ZONE 'UTC', 'IYYY-"W"IW') AS iso_week,
    ROUND(AVG(price)::numeric, 2)::double precision AS avg_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    ROUND(
        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::numeric, 2
    )::double precision AS median_price,
    COUNT(*)::int AS sample_count
FROM price_snapshots
GROUP BY
    model_id,
    brand,
    model,
    source,
    condition,
    DATE_TRUNC('week', captured_at AT TIME ZONE 'UTC')::date,
    TO_CHAR(captured_at AT TIME ZONE 'UTC', 'IYYY-"W"IW');

-- Monthly aggregated prices
CREATE OR REPLACE VIEW price_monthly AS
SELECT
    model_id,
    brand,
    model,
    source,
    condition,
    DATE_TRUNC('month', captured_at AT TIME ZONE 'UTC')::date AS month_start,
    TO_CHAR(captured_at AT TIME ZONE 'UTC', 'YYYY-MM') AS year_month,
    ROUND(AVG(price)::numeric, 2)::double precision AS avg_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    ROUND(
        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::numeric, 2
    )::double precision AS median_price,
    COUNT(*)::int AS sample_count
FROM price_snapshots
GROUP BY
    model_id,
    brand,
    model,
    source,
    condition,
    DATE_TRUNC('month', captured_at AT TIME ZONE 'UTC')::date,
    TO_CHAR(captured_at AT TIME ZONE 'UTC', 'YYYY-MM');

-- Trends view: DoD, WoW, MoM deltas and 7d/30d moving averages
CREATE OR REPLACE VIEW price_trends AS
WITH daily_ma AS (
    SELECT
        model_id,
        brand,
        model,
        source,
        condition,
        bucket_date,
        avg_price,
        LAG(avg_price) OVER (
            PARTITION BY model_id, source, condition
            ORDER BY bucket_date
        ) AS prev_day_price,
        ROUND(
            AVG(avg_price) OVER (
                PARTITION BY model_id, source, condition
                ORDER BY bucket_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            )::numeric, 2
        )::double precision AS ma_7d,
        ROUND(
            AVG(avg_price) OVER (
                PARTITION BY model_id, source, condition
                ORDER BY bucket_date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            )::numeric, 2
        )::double precision AS ma_30d
    FROM price_daily
),
weekly_delta AS (
    SELECT
        model_id,
        source,
        condition,
        week_start,
        avg_price AS week_avg_price,
        LAG(avg_price) OVER (
            PARTITION BY model_id, source, condition
            ORDER BY week_start
        ) AS prev_week_price
    FROM price_weekly
),
monthly_delta AS (
    SELECT
        model_id,
        source,
        condition,
        month_start,
        avg_price AS month_avg_price,
        LAG(avg_price) OVER (
            PARTITION BY model_id, source, condition
            ORDER BY month_start
        ) AS prev_month_price
    FROM price_monthly
)
SELECT
    d.model_id,
    d.brand,
    d.model,
    d.source,
    d.condition,
    d.bucket_date,
    d.avg_price AS current_price,
    d.prev_day_price,
    ROUND((d.avg_price - d.prev_day_price)::numeric, 2)::double precision AS dod_abs,
    CASE
        WHEN d.prev_day_price > 0
        THEN ROUND((((d.avg_price - d.prev_day_price) / d.prev_day_price) * 100.0)::numeric, 2)::double precision
        ELSE NULL
    END AS dod_pct,
    ROUND((w.week_avg_price - w.prev_week_price)::numeric, 2)::double precision AS wow_abs,
    CASE
        WHEN w.prev_week_price > 0
        THEN ROUND((((w.week_avg_price - w.prev_week_price) / w.prev_week_price) * 100.0)::numeric, 2)::double precision
        ELSE NULL
    END AS wow_pct,
    ROUND((m.month_avg_price - m.prev_month_price)::numeric, 2)::double precision AS mom_abs,
    CASE
        WHEN m.prev_month_price > 0
        THEN ROUND((((m.month_avg_price - m.prev_month_price) / m.prev_month_price) * 100.0)::numeric, 2)::double precision
        ELSE NULL
    END AS mom_pct,
    d.ma_7d,
    d.ma_30d
FROM daily_ma d
LEFT JOIN weekly_delta w
    ON w.model_id = d.model_id
    AND w.source = d.source
    AND w.condition = d.condition
    AND w.week_start = DATE_TRUNC('week', d.bucket_date::timestamp)::date
LEFT JOIN monthly_delta m
    ON m.model_id = d.model_id
    AND m.source = d.source
    AND m.condition = d.condition
    AND m.month_start = DATE_TRUNC('month', d.bucket_date::timestamp)::date;
