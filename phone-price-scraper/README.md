# Phone Price Scraper & Trend Analytics

Production-grade Python 3.12 data collection, PostgreSQL 16 time-series storage, date-bucketed CSV export, and trend analytics pipeline for mobile phone buyback and resale prices.

## Architecture

- **Scrapers (`src/phone_scraper/scrapers/`)**
  - `cashify_sell`: Collects Cashify "Sell old phone" buyback quotes per storage variant and condition grade, preserving raw `__NEXT_DATA__`/DOM payloads.
  - `cashify_buy`: Collects Cashify refurbished listings (selling price, MRP, discount %, storage, RAM, color, condition grade, warranty, stock status).
  - `amazon_sell`: Collects Amazon trade-in offer prices per device, storage, and condition.
  - `generic_api`: Config-driven JSON API connector configured via YAML under `config/sources/`, supporting `none`, `api_key`, `bearer`, `basic`, `oauth2_client_credentials`, and `cookie` auth, 401 token refresh + single retry, pagination (`none`, `page_number`, `offset_limit`, `cursor`, `link_header`), dotted JSON paths, and field transforms.
- **Scraping Guardrails (`src/phone_scraper/core/`)**
  - `robots.txt` respected by default (`RESPECT_ROBOTS_TXT=true`).
  - Per-domain rate limiting with 1–3s jitter and max concurrency of 2 per domain.
  - Exponential backoff retries (up to 3 attempts) on HTTP 429, 5xx, and timeouts.
  - Rotating user agents and optional proxy pool.
  - Raw payload disk cache under `raw/{source}/{YYYY-MM-DD}/`.
  - CAPTCHA and login-wall detection marks the `scrape_runs` row `blocked` and stops cleanly without attempting to bypass.
  - Secret redaction filter strips `Bearer`/`Basic` tokens and sensitive fields from logs.
- **PostgreSQL 16 Schema & Views (`alembic/` & `src/phone_scraper/db/`)**
  - `scrape_runs`, `phone_models`, and append-only `price_snapshots` with a daily UTC functional unique index `(source, source_product_id, condition, COALESCE(storage_gb, -1), (captured_at AT TIME ZONE 'UTC')::date)` so same-day reruns are idempotent.
  - Views: `price_daily`, `price_weekly`, `price_monthly`, and `price_trends` (DoD, WoW, MoM absolute + percentage deltas, 7-day & 30-day moving averages).

## Setup

### Local with `uv`

```bash
cd phone-price-scraper
cp .env.example .env
uv sync --extra dev
uv run playwright install chromium
```

Start PostgreSQL 16 (via Docker Compose or local Postgres) and run migrations:

```bash
docker compose up -d postgres
uv run phone-scraper db migrate
```

Optionally seed 15 days of sample snapshots to try exports and trend reports immediately:

```bash
uv run phone-scraper db seed
```

### Full Stack with Docker Compose

```bash
cd phone-price-scraper
cp .env.example .env
docker compose up --build
```

`docker compose` starts PostgreSQL 16 (`postgres`) and the scheduler container (`app`), which automatically runs `db migrate` and starts `scrape schedule`.

## Commands

Both the unified CLI (`phone-scraper ...`) and short script aliases (`scrape`, `export`, `trends`, `db`) are registered in `pyproject.toml`:

```bash
# Run a specific source or all enabled sources
uv run scrape run --source cashify_sell
uv run scrape run --source cashify_buy
uv run scrape run --source amazon_sell
uv run scrape run --source api:example_api
uv run scrape run --source all

# Start the daily APScheduler daemon (uses SCHEDULE_CRON_TIME & SCHEDULE_TIMEZONE)
uv run scrape schedule --source all

# Export date-bucketed CSVs, trends CSV, and manifest.json (with optional S3 upload)
uv run export --granularity daily --from 2026-11-01 --to 2026-11-17 --source all --format csv
uv run export --granularity weekly --from 2026-11-01 --to 2026-11-17 --source cashify_sell --format csv
uv run export --granularity monthly --from 2026-10-01 --to 2026-11-17 --source all --format csv

# Print DoD / WoW / MoM trend table in the terminal
uv run trends --granularity daily --model "iPhone 15"
uv run trends --granularity weekly
```

## Export Layout

Exports are written to date-bucketed directories (and mirrored to S3/MinIO/R2 if `S3_ENABLED=true`):

```text
exports/
  daily/2026/2026-11/2026-11-17/
    cashify_sell_daily_2026-11-17.csv
    trends_daily_2026-11-17.csv
    manifest.json
  weekly/2026/2026-11/2026-W47/
    cashify_buy_weekly_2026-W47.csv
    trends_weekly_2026-W47.csv
    manifest.json
  monthly/2026/2026-11/2026-11/
    amazon_sell_monthly_2026-11.csv
    trends_monthly_2026-11.csv
    manifest.json
```

## Example Output

```text
$ uv run trends --granularity daily --model "iPhone 15"
                         Mobile Price Trends (DAILY)
┏━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Brand ┃ Model     ┃ Source       ┃ Condition ┃ Bucket     ┃ Avg Price ┃ DoD %  ┃ WoW %  ┃ MoM % ┃ 7d MA    ┃ 30d MA   ┃
┡━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ Apple │ iPhone 15 │ cashify_sell │ excellent │ 2026-11-15 │ 41160.0   │ -0.29% │ -1.89% │ -     │ 41520.0  │ 41880.0  │
│ Apple │ iPhone 15 │ cashify_sell │ excellent │ 2026-11-16 │ 41040.0   │ -0.29% │ -1.68% │ -     │ 41400.0  │ 41820.0  │
│ Apple │ iPhone 15 │ cashify_sell │ excellent │ 2026-11-17 │ 40920.0   │ -0.29% │ -1.25% │ -     │ 41280.0  │ 41760.0  │
└───────┴───────────┴──────────────┴───────────┴────────────┴───────────┴────────┴────────┴───────┴──────────┴──────────┘
```

## Testing & Quality Checks

All parser, normalization, generic API, export, and trend tests run completely offline against saved HTML/JSON fixtures in `tests/fixtures/`:

```bash
uv run pytest
uv run ruff check .
uv run mypy
```
