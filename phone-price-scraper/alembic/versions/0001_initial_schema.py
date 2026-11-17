"""Initial PostgreSQL schema and analytical views.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-17
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scrape_runs_source", "scrape_runs", ["source"], unique=False)

    op.create_table(
        "phone_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand", "model", name="uq_phone_models_brand_model"),
    )

    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("source_product_id", sa.String(length=128), nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("storage_gb", sa.Integer(), nullable=True),
        sa.Column("ram_gb", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(length=80), nullable=True),
        sa.Column("condition", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("mrp", sa.Float(), nullable=True),
        sa.Column("discount_pct", sa.Float(), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_id"], ["phone_models.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["scrape_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_snapshots_model_captured",
        "price_snapshots",
        ["model_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_price_snapshots_source_captured",
        "price_snapshots",
        ["source", "captured_at"],
        unique=False,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_price_snapshots_daily_dedup
        ON price_snapshots (
            source,
            source_product_id,
            condition,
            COALESCE(storage_gb, -1),
            ((captured_at AT TIME ZONE 'UTC')::date)
        );
        """
    )

    views_path = Path(__file__).resolve().parents[2] / "src" / "phone_scraper" / "db" / "views.sql"
    op.execute(views_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS price_trends;")
    op.execute("DROP VIEW IF EXISTS price_monthly;")
    op.execute("DROP VIEW IF EXISTS price_weekly;")
    op.execute("DROP VIEW IF EXISTS price_daily;")
    op.execute("DROP INDEX IF EXISTS uq_price_snapshots_daily_dedup;")
    op.drop_index("ix_price_snapshots_source_captured", table_name="price_snapshots")
    op.drop_index("ix_price_snapshots_model_captured", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_table("phone_models")
    op.drop_index("ix_scrape_runs_source", table_name="scrape_runs")
    op.drop_table("scrape_runs")
