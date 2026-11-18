-- =============================================================================
-- Swapup Scrapper — PostgreSQL 16 Schema (No Authentication Required)
-- Supports:
--   1. Buy · Refurbished (side = 'buy'   : cashify_buy, Amazon India)
--   2. Sell · Buyback    (side = 'sell'  : cashify_sell, amazon_sell, partner APIs)
--   3. New Devices       (side = 'new'   : amazon.in, flipkart)
--   4. Parts Pricing     (side = 'parts' : samsung_parts, apple_parts)
-- =============================================================================

-- 1. Scrape Runs (Execution & Audit Log)
CREATE TABLE IF NOT EXISTS scrape_runs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(120) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    records_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_scrape_runs_source ON scrape_runs (source);

-- 2. Phone Models (Dimension Table, Unique on Brand + Model)
CREATE TABLE IF NOT EXISTS phone_models (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(80) NOT NULL,
    model VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_phone_models_brand_model UNIQUE (brand, model)
);

-- 3. Price Snapshots (Append-Only Time-Series Fact Table)
CREATE TABLE IF NOT EXISTS price_snapshots (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    model_id INTEGER NOT NULL REFERENCES phone_models(id) ON DELETE RESTRICT,

    side VARCHAR(16) NOT NULL DEFAULT 'sell',
    source VARCHAR(120) NOT NULL,
    source_product_id VARCHAR(128) NOT NULL,
    brand VARCHAR(80) NOT NULL,
    model VARCHAR(160) NOT NULL,

    storage_gb INTEGER,
    ram_gb INTEGER,
    color VARCHAR(80),
    condition VARCHAR(32) NOT NULL,

    part_category VARCHAR(80),
    part_name VARCHAR(200),

    price DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    mrp DOUBLE PRECISION,
    discount_pct DOUBLE PRECISION,
    in_stock BOOLEAN,

    source_url TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_price_snapshots_model_captured
    ON price_snapshots (model_id, captured_at);

CREATE INDEX IF NOT EXISTS ix_price_snapshots_source_captured
    ON price_snapshots (source, captured_at);

CREATE INDEX IF NOT EXISTS ix_price_snapshots_side_captured
    ON price_snapshots (side, captured_at);

-- Same-day idempotent deduplication constraint
CREATE UNIQUE INDEX IF NOT EXISTS uq_price_snapshots_daily_dedup
    ON price_snapshots (
        source,
        source_product_id,
        condition,
        COALESCE(storage_gb, -1),
        COALESCE(part_category, ''),
        ((captured_at AT TIME ZONE 'UTC')::date)
    );

-- 4. Analytical Views (Daily, ISO Weekly, Monthly, DoD/WoW/MoM Trends)
CREATE OR REPLACE VIEW price_daily AS
SELECT
    model_id,
    brand,
    model,
    side,
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
GROUP BY model_id, brand, model, side, source, condition, (captured_at AT TIME ZONE 'UTC')::date;

CREATE OR REPLACE VIEW price_weekly AS
SELECT
    model_id,
    brand,
    model,
    side,
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
    side,
    source,
    condition,
    DATE_TRUNC('week', captured_at AT TIME ZONE 'UTC')::date,
    TO_CHAR(captured_at AT TIME ZONE 'UTC', 'IYYY-"W"IW');

CREATE OR REPLACE VIEW price_monthly AS
SELECT
    model_id,
    brand,
    model,
    side,
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
    side,
    source,
    condition,
    DATE_TRUNC('month', captured_at AT TIME ZONE 'UTC')::date,
    TO_CHAR(captured_at AT TIME ZONE 'UTC', 'YYYY-MM');

CREATE OR REPLACE VIEW price_trends AS
WITH daily_ma AS (
    SELECT
        model_id,
        brand,
        model,
        side,
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
    d.side,
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
