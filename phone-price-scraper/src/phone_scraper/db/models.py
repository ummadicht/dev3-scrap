from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _json_type() -> Any:
    """Use JSONB on PostgreSQL while keeping generic JSON fallback for test engines."""
    return JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshots: Mapped[list[PriceSnapshot]] = relationship(back_populates="run")


class PhoneModel(Base):
    __tablename__ = "phone_models"
    __table_args__ = (UniqueConstraint("brand", "model", name="uq_phone_models_brand_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    snapshots: Mapped[list[PriceSnapshot]] = relationship(back_populates="phone_model")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index("ix_price_snapshots_model_captured", "model_id", "captured_at"),
        Index("ix_price_snapshots_source_captured", "source", "captured_at"),
        Index("ix_price_snapshots_side_captured", "side", "captured_at"),
        Index(
            "uq_price_snapshots_daily_dedup",
            "source",
            "source_product_id",
            "condition",
            text("COALESCE(storage_gb, -1)"),
            text("COALESCE(part_category, '')"),
            text("((captured_at AT TIME ZONE 'UTC')::date)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scrape_runs.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[int] = mapped_column(ForeignKey("phone_models.id", ondelete="RESTRICT"), nullable=False)

    side: Mapped[str] = mapped_column(String(16), nullable=False, default="sell")
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    storage_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    condition: Mapped[str] = mapped_column(String(32), nullable=False)
    part_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    part_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    mrp: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(_json_type(), nullable=False, default=dict)

    run: Mapped[ScrapeRun] = relationship(back_populates="snapshots")
    phone_model: Mapped[PhoneModel] = relationship(back_populates="snapshots")
