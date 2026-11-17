from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Literal, cast

import typer
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from phone_scraper.analytics.trends import query_trends_from_db, render_trends_table
from phone_scraper.config import (
    get_settings,
    load_generic_api_configs,
    load_yaml_settings,
)
from phone_scraper.core.auth import configure_logging
from phone_scraper.core.http import BlockedByAntiBotError, HttpFetcher, PlaywrightFetcher
from phone_scraper.core.rate_limit import DomainRateLimiter
from phone_scraper.core.storage import PriceRepository, seed_sample_records
from phone_scraper.db.session import session_scope
from phone_scraper.exports.bucket_paths import ExportGranularity
from phone_scraper.exports.csv_export import export_from_db
from phone_scraper.scrapers.amazon_sell.scraper import AmazonSellScraper
from phone_scraper.scrapers.base import BaseScraper
from phone_scraper.scrapers.cashify_buy.scraper import CashifyBuyScraper
from phone_scraper.scrapers.cashify_sell.scraper import CashifySellScraper
from phone_scraper.scrapers.generic_api.scraper import GenericApiScraper

logger = logging.getLogger(__name__)

app = typer.Typer(help="Mobile phone buyback & resale price intelligence CLI.")
scrape_cli = typer.Typer(help="Run scrapers or start the daily scheduler.")
db_cli = typer.Typer(help="Database migration and seeding helpers.")

app.add_typer(scrape_cli, name="scrape")
app.add_typer(db_cli, name="db")


def _build_scrapers(source: str) -> list[BaseScraper]:
    settings = get_settings()
    yaml_cfg = load_yaml_settings(settings.config_dir / "settings.yaml")
    api_configs = load_generic_api_configs(settings.config_dir / "sources")

    rate_limiter = DomainRateLimiter(
        min_delay_sec=settings.rate_limit_min_sec,
        max_delay_sec=settings.rate_limit_max_sec,
        max_concurrency=settings.max_concurrency_per_domain,
    )
    http_fetcher = HttpFetcher(
        respect_robots_txt=settings.respect_robots_txt,
        rate_limiter=rate_limiter,
        timeout_sec=settings.http_timeout_sec,
        max_retries=settings.max_retries,
        user_agents=yaml_cfg.app.user_agents,
        proxies=settings.proxies or yaml_cfg.app.proxies,
        raw_cache_dir=settings.raw_cache_dir,
        use_raw_cache=settings.use_raw_cache,
    )
    pw_fetcher = PlaywrightFetcher(
        respect_robots_txt=settings.respect_robots_txt,
        rate_limiter=rate_limiter,
        user_agents=yaml_cfg.app.user_agents,
        proxies=settings.proxies or yaml_cfg.app.proxies,
        raw_cache_dir=settings.raw_cache_dir,
        use_raw_cache=settings.use_raw_cache,
    )

    available: dict[str, BaseScraper] = {}
    if "cashify_sell" in yaml_cfg.sources and yaml_cfg.sources["cashify_sell"].enabled:
        cfg = yaml_cfg.sources["cashify_sell"]
        available["cashify_sell"] = CashifySellScraper(
            cfg.urls,
            use_playwright=cfg.use_playwright,
            http_fetcher=http_fetcher,
            playwright_fetcher=pw_fetcher,
        )
    if "cashify_buy" in yaml_cfg.sources and yaml_cfg.sources["cashify_buy"].enabled:
        cfg = yaml_cfg.sources["cashify_buy"]
        available["cashify_buy"] = CashifyBuyScraper(
            cfg.urls,
            use_playwright=cfg.use_playwright,
            http_fetcher=http_fetcher,
            playwright_fetcher=pw_fetcher,
        )
    if "amazon_sell" in yaml_cfg.sources and yaml_cfg.sources["amazon_sell"].enabled:
        cfg = yaml_cfg.sources["amazon_sell"]
        available["amazon_sell"] = AmazonSellScraper(
            cfg.urls,
            use_playwright=cfg.use_playwright,
            http_fetcher=http_fetcher,
            playwright_fetcher=pw_fetcher,
        )

    for api_name, api_cfg in api_configs.items():
        available[f"api:{api_name}"] = GenericApiScraper(api_cfg, fetcher=http_fetcher)

    if source == "all":
        return list(available.values())
    if source not in available:
        raise typer.BadParameter(
            f"Unknown or disabled source '{source}'. Available: {', '.join(sorted(available))}"
        )
    return [available[source]]


def _run_scrapers(source: str) -> None:
    configure_logging()
    scrapers = _build_scrapers(source)
    for scraper in scrapers:
        with session_scope() as session:
            repo = PriceRepository(session)
            run = repo.start_run(scraper.source_name)
            try:
                records = scraper.collect(run.id)
                count = repo.save_snapshots_pg_idempotent(records, run.id)
                repo.finish_run(run, status="success", records_count=count)
                typer.echo(f"[{scraper.source_name}] stored {count} snapshots (run_id={run.id})")
            except BlockedByAntiBotError as exc:
                logger.error("Source %s blocked: %s", scraper.source_name, exc)
                repo.finish_run(run, status="blocked", records_count=0, error_message=str(exc))
            except Exception as exc:
                logger.exception("Source %s failed: %s", scraper.source_name, exc)
                repo.finish_run(run, status="failed", records_count=0, error_message=str(exc))
                raise


@scrape_cli.command("run")
def scrape_run(
    source: str = typer.Option(
        "all",
        "--source",
        help="Target source: cashify_sell | cashify_buy | amazon_sell | api:<name> | all",
    ),
) -> None:
    """Execute one-off scraping run for a source or all configured sources."""
    _run_scrapers(source)


@scrape_cli.command("schedule")
def scrape_schedule(
    source: str = typer.Option("all", "--source", help="Source to schedule daily."),
) -> None:
    """Start APScheduler to run scraping daily at SCHEDULE_CRON_TIME."""
    configure_logging()
    settings = get_settings()
    hour_str, minute_str = settings.schedule_cron_time.split(":")
    scheduler = BlockingScheduler(timezone=settings.schedule_timezone)
    trigger = CronTrigger(hour=int(hour_str), minute=int(minute_str))
    scheduler.add_job(_run_scrapers, trigger=trigger, args=[source], id="daily_phone_scrape")
    typer.echo(
        f"Scheduler started for '{source}' daily at {settings.schedule_cron_time} "
        f"({settings.schedule_timezone})."
    )
    scheduler.start()


@app.command("export")
def export_cmd(
    granularity: ExportGranularity = typer.Option(..., "--granularity"),
    from_date: str = typer.Option(..., "--from", help="Start date YYYY-MM-DD"),
    to_date: str = typer.Option(..., "--to", help="End date YYYY-MM-DD"),
    source: str = typer.Option("all", "--source", help="Source name or 'all'"),
    fmt: str = typer.Option("csv", "--format", help="Export format (csv)"),
) -> None:
    """Export date-bucketed CSVs, trends CSV, and manifest.json."""
    configure_logging()
    if fmt.lower() != "csv":
        raise typer.BadParameter("Only --format csv is supported.")
    settings = get_settings()
    d_from = date.fromisoformat(from_date)
    d_to = date.fromisoformat(to_date)
    with session_scope() as session:
        files = export_from_db(
            session,
            granularity=granularity,
            from_date=d_from,
            to_date=d_to,
            source=source,
            settings=settings,
        )
    typer.echo(f"Generated {len(files)} export artifact(s) under {settings.exports_dir}/")


@app.command("trends")
def trends_cmd(
    granularity: ExportGranularity = typer.Option(ExportGranularity.DAILY, "--granularity"),
    model: str | None = typer.Option(None, "--model", help="Optional model name substring filter"),
) -> None:
    """Compute and print DoD/WoW/MoM + moving average trends in the terminal."""
    configure_logging()
    gran_lit = cast(Literal["daily", "weekly", "monthly"], granularity.value)
    with session_scope() as session:
        df = query_trends_from_db(session, granularity=gran_lit, model=model)
    render_trends_table(df, granularity.value)


@db_cli.command("migrate")
def db_migrate() -> None:
    """Run Alembic migrations up to head."""
    from alembic import command
    from alembic.config import Config

    configure_logging()
    cfg = Config(str(Path("alembic.ini")))
    command.upgrade(cfg, "head")
    typer.echo("Database migrated to head.")


@db_cli.command("seed")
def db_seed() -> None:
    """Seed multi-day sample records into PostgreSQL for local trend testing."""
    configure_logging()
    with session_scope() as session:
        count = seed_sample_records(session)
    typer.echo(f"Seeded {count} price_snapshots records.")


def export_cli() -> None:
    typer.run(export_cmd)


def trends_cli() -> None:
    typer.run(trends_cmd)


if __name__ == "__main__":
    app()
