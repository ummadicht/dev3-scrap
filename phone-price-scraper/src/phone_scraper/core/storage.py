from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from phone_scraper.core.normalize import NormalizedCondition, NormalizedPriceRecord
from phone_scraper.db.models import PhoneModel, PriceSnapshot, ScrapeRun


class PriceRepository:
    """Repository managing scrape_runs, phone_models, and idempotent price_snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def start_run(self, source: str) -> ScrapeRun:
        run = ScrapeRun(source=source, status="running", started_at=datetime.now(UTC))
        self.session.add(run)
        self.session.flush()
        return run

    def finish_run(
        self,
        run: ScrapeRun,
        *,
        status: str,
        records_count: int,
        error_message: str | None = None,
    ) -> None:
        run.status = status
        run.records_count = records_count
        run.error_message = error_message
        run.finished_at = datetime.now(UTC)
        self.session.flush()

    def get_or_create_model(self, brand: str, model: str) -> PhoneModel:
        stmt = select(PhoneModel).where(PhoneModel.brand == brand, PhoneModel.model == model)
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing
        phone_model = PhoneModel(brand=brand, model=model)
        self.session.add(phone_model)
        self.session.flush()
        return phone_model

    def upsert_snapshots(self, records: Iterable[NormalizedPriceRecord], run_id: int) -> int:
        """
        Idempotently store snapshots: reruns on the same UTC date update existing
        (source, source_product_id, condition, storage_gb, date) rows without duplicating.
        """
        dialect_name = self.session.bind.dialect.name if self.session.bind else ""
        if dialect_name == "postgresql":
            return self.save_snapshots_pg_idempotent(records, run_id)

        rows_written = 0
        for rec in records:
            phone_model = self.get_or_create_model(rec.brand, rec.model)
            self.session.add(
                PriceSnapshot(
                    run_id=run_id,
                    model_id=phone_model.id,
                    source=rec.source,
                    source_product_id=rec.source_product_id,
                    brand=rec.brand,
                    model=rec.model,
                    storage_gb=rec.storage_gb,
                    ram_gb=rec.ram_gb,
                    color=rec.color,
                    condition=rec.condition.value,
                    price=rec.price,
                    currency=rec.currency,
                    mrp=rec.mrp,
                    discount_pct=rec.discount_pct,
                    in_stock=rec.in_stock,
                    source_url=rec.source_url,
                    captured_at=rec.captured_at,
                    raw_payload=rec.raw_payload,
                )
            )
            rows_written += 1

        self.session.flush()
        return rows_written

    def save_snapshots_pg_idempotent(
        self, records: Iterable[NormalizedPriceRecord], run_id: int
    ) -> int:
        """Execute PostgreSQL ON CONFLICT upsert against the daily functional unique index."""
        from sqlalchemy import text

        count = 0
        for rec in records:
            phone_model = self.get_or_create_model(rec.brand, rec.model)
            self.session.execute(
                text(
                    """
                    INSERT INTO price_snapshots (
                        run_id, model_id, source, source_product_id,
                        brand, model, storage_gb, ram_gb, color, condition,
                        price, currency, mrp, discount_pct, in_stock,
                        source_url, captured_at, raw_payload
                    ) VALUES (
                        :run_id, :model_id, :source, :source_product_id,
                        :brand, :model, :storage_gb, :ram_gb, :color, :condition,
                        :price, :currency, :mrp, :discount_pct, :in_stock,
                        :source_url, :captured_at, CAST(:raw_payload AS jsonb)
                    )
                    ON CONFLICT (
                        source,
                        source_product_id,
                        condition,
                        COALESCE(storage_gb, -1),
                        ((captured_at AT TIME ZONE 'UTC')::date)
                    )
                    DO UPDATE SET
                        run_id = EXCLUDED.run_id,
                        price = EXCLUDED.price,
                        mrp = EXCLUDED.mrp,
                        discount_pct = EXCLUDED.discount_pct,
                        in_stock = EXCLUDED.in_stock,
                        raw_payload = EXCLUDED.raw_payload
                    """
                ),
                {
                    "run_id": run_id,
                    "model_id": phone_model.id,
                    "source": rec.source,
                    "source_product_id": rec.source_product_id,
                    "brand": rec.brand,
                    "model": rec.model,
                    "storage_gb": rec.storage_gb,
                    "ram_gb": rec.ram_gb,
                    "color": rec.color,
                    "condition": rec.condition.value,
                    "price": rec.price,
                    "currency": rec.currency,
                    "mrp": rec.mrp,
                    "discount_pct": rec.discount_pct,
                    "in_stock": rec.in_stock,
                    "source_url": rec.source_url,
                    "captured_at": rec.captured_at,
                    "raw_payload": _dumps_json(rec.raw_payload),
                },
            )
            count += 1
        self.session.flush()
        return count


def _dumps_json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, default=str)


def seed_sample_records(session: Session) -> int:
    """Seed realistic multi-day historical records for local verification."""
    from datetime import timedelta

    repo = PriceRepository(session)
    run = repo.start_run("seed")
    now = datetime.now(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    samples: list[NormalizedPriceRecord] = []

    base_devices = [
        ("cashify_sell", "Apple", "iPhone 15", 128, 6, NormalizedCondition.EXCELLENT, 42600.0, None),
        ("cashify_sell", "Apple", "iPhone 15", 128, 6, NormalizedCondition.GOOD, 37500.0, None),
        ("cashify_buy", "Apple", "iPhone 13", 128, 4, NormalizedCondition.GOOD, 34999.0, 59900.0),
        ("amazon_sell", "Samsung", "Galaxy S24 Ultra", 256, 12, NormalizedCondition.EXCELLENT, 58000.0, None),
    ]

    for day_offset in range(14, -1, -1):
        dt = now - timedelta(days=day_offset)
        for src, brand, model, storage, ram, cond, base_price, mrp in base_devices:
            drift = (14 - day_offset) * -120.0
            price = max(1000.0, base_price + drift)
            samples.append(
                NormalizedPriceRecord(
                    source=src,
                    source_product_id=f"{src}-{brand}-{model}-{storage}".lower().replace(" ", "-"),
                    brand=brand,
                    model=model,
                    storage_gb=storage,
                    ram_gb=ram,
                    condition=cond,
                    price=price,
                    currency="INR",
                    mrp=mrp,
                    discount_pct=round(((mrp - price) / mrp) * 100.0, 2) if mrp else None,
                    in_stock=True if src == "cashify_buy" else None,
                    source_url=f"https://example.invalid/{src}/{model.lower().replace(' ', '-')}",
                    captured_at=dt,
                    run_id=run.id,
                    raw_payload={"seeded": True, "day_offset": day_offset},
                )
            )

    written = repo.save_snapshots_pg_idempotent(samples, run.id)
    repo.finish_run(run, status="success", records_count=written)
    return written
