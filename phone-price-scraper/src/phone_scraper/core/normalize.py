from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class NormalizedCondition(StrEnum):
    NEW = "new"
    LIKE_NEW = "like_new"
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


CONDITION_PATTERNS: list[tuple[re.Pattern[str], NormalizedCondition]] = [
    (re.compile(r"\b(brand\s*new|new|sealed)\b", re.I), NormalizedCondition.NEW),
    (re.compile(r"\b(like\s*new|mint|superb|flawless|grade\s*a\+?)\b", re.I), NormalizedCondition.LIKE_NEW),
    (re.compile(r"\b(excellent|very\s*good)\b", re.I), NormalizedCondition.EXCELLENT),
    (re.compile(r"\b(good|grade\s*b)\b", re.I), NormalizedCondition.GOOD),
    (re.compile(r"\b(fair|average|acceptable|grade\s*c)\b", re.I), NormalizedCondition.FAIR),
    (
        re.compile(r"\b(poor|broken|cracked|defective|damaged|dead|faulty|grade\s*[de])\b", re.I),
        NormalizedCondition.POOR,
    ),
]


def normalize_condition(raw: str | None) -> NormalizedCondition:
    """Normalize arbitrary site/API condition strings to canonical enum."""
    if not raw:
        return NormalizedCondition.UNKNOWN
    text = raw.strip().lower().replace("_", " ").replace("-", " ")
    for member in NormalizedCondition:
        if text == member.value.replace("_", " "):
            return member
    for pattern, condition in CONDITION_PATTERNS:
        if pattern.search(text):
            return condition
    return NormalizedCondition.UNKNOWN


def parse_storage_gb(raw: str | int | float | None) -> int | None:
    """Parse storage capacity such as '128 GB' or '1 TB' into integer GB."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        val = int(raw)
        return val if val > 0 else None
    text = str(raw).strip()
    m_tb = re.search(r"(\d+)\s*tb\b", text, re.I)
    if m_tb:
        return int(m_tb.group(1)) * 1024
    m_gb = re.search(r"(\d+)\s*gb\b", text, re.I)
    if m_gb:
        return int(m_gb.group(1))
    m_plain = re.fullmatch(r"\d{2,4}", text)
    if m_plain:
        return int(text)
    return None


def parse_ram_gb(raw: str | int | float | None) -> int | None:
    """Parse RAM capacity such as '8 GB' into integer GB."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        val = int(raw)
        return val if 1 <= val <= 64 else None
    text = str(raw).strip()
    m_gb = re.search(r"(\d+)\s*gb\b", text, re.I)
    if m_gb:
        val = int(m_gb.group(1))
        return val if 1 <= val <= 64 else None
    m_plain = re.fullmatch(r"\d{1,2}", text)
    if m_plain:
        val = int(text)
        return val if 1 <= val <= 64 else None
    return None


def compute_discount_pct(price: float, mrp: float | None) -> float | None:
    if mrp is None or mrp <= 0 or price < 0 or mrp < price:
        return None
    return round(((mrp - price) / mrp) * 100.0, 2)


def stable_product_id(*parts: str | int | None) -> str:
    joined = "|".join(str(p).strip().lower() for p in parts if p is not None and str(p).strip())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


class NormalizedPriceRecord(BaseModel):
    """Canonical schema shared by all scrapers and API connectors."""

    source: str
    source_product_id: str
    brand: str
    model: str
    storage_gb: int | None = None
    ram_gb: int | None = None
    color: str | None = None
    condition: NormalizedCondition = NormalizedCondition.UNKNOWN
    price: float
    currency: str = "INR"
    mrp: float | None = None
    discount_pct: float | None = None
    in_stock: bool | None = None
    source_url: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str | int = 0
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("captured_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value: Any) -> datetime:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.now(UTC)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> str:
        text = str(value or "INR").strip().upper()
        return text[:10] or "INR"

    @field_validator("price")
    @classmethod
    def _validate_positive_price(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("price must be > 0")
        return round(float(value), 2)
