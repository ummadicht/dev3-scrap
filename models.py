"""
Data models and schema validation for mobile price intelligence records.
Supports independent models for:
1. Cashify Buy Prices (Cashify pays customer for used device)
2. Cashify Sell Prices (Cashify sells refurbished device to customer)
3. Schema Interval Entities: Interval Reports, Devices, Repair & Exchange Costs, Observations, Runs
"""
from datetime import datetime, timezone, date, time
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MobilePriceRecord(BaseModel):
    """Represents a validated mobile buyback pricing record (Cashify Buy Price)."""
    model_config = ConfigDict(frozen=False)

    brand: str = Field(..., description="Device manufacturer, e.g., Apple, Samsung")
    model: str = Field(..., description="Device model with specifications, e.g., Samsung Galaxy S21 5G (8 GB/256 GB)")
    storage: str = Field(..., description="Storage variant, e.g., 64 GB, 128 GB, 256 GB")
    ram: Optional[str] = Field(default=None, description="Device RAM, e.g., 4 GB, 8 GB RAM")
    cores: Optional[str] = Field(default=None, description="Processor core count, e.g., 8, 6")
    camera: Optional[str] = Field(default=None, description="Camera setup, e.g., 12 MP, 64 MP")
    color: Optional[str] = Field(default=None, description="Color variant")
    network_type: Optional[str] = Field(default=None, description="Network type, e.g., 5G, 4G")
    condition: str = Field(..., description="Device condition description or grade")
    defects: str = Field(..., description="Defects or hardware faults present on device")
    buyback_price: int = Field(..., ge=0, description="Actual buyback price in local currency integer value")
    source_url: str = Field(..., description="Source URL where the price quote originated")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of record creation or collection"
    )
    data_origin: Literal["verified_scraped", "sample_condition_graded"] = Field(
        ...,
        description="Origin flag: 'verified_scraped' for live extracted quotes, 'sample_condition_graded' for calibrated matrix"
    )
    currency: str = Field(default="INR", description="Currency ISO code")
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence: 1.0 for verified DOM/RSC scrape, 0.85 for simulated condition"
    )

    # Extended fields matching scraper.cashify_buy_prices schema
    device_id: Optional[str] = Field(default=None, description="Canonical device identifier, e.g. apple-iphone-16-pro-128")
    model_series: Optional[str] = Field(default=None, description="Model series, e.g. iPhone 16 Series")
    variant: Optional[str] = Field(default=None, description="Variant string, e.g. 128 GB or 8 GB / 128 GB")
    storage_gb: Optional[int] = Field(default=None, description="Storage parsed as integer in GB")
    ram_gb: Optional[int] = Field(default=None, description="RAM parsed as integer in GB")
    condition_grade: Optional[str] = Field(default="Grade A", description="Condition grade: Grade A, Grade B, Grade C, Grade D, Grade E")
    max_advertised_price: Optional[float] = Field(default=None, description="Maximum advertised baseline price")
    condition_deductions: Optional[float] = Field(default=0.0, description="Deductions based on condition and repair costs")
    price: Optional[float] = Field(default=None, description="Final buyback price in currency unit")
    report_id: Optional[str] = Field(default=None, description="Interval report identifier, e.g. RPT-YYYYMMDD-HHMMSS-B2")
    report_day: Optional[str] = Field(default=None, description="Day of report YYYY-MM-DD")
    report_time: Optional[str] = Field(default=None, description="Time of report HH:MM:SS")
    report_bucket: Optional[str] = Field(default=None, description="Time slot bucket, e.g. B2_MORNING_06_12 [10:30]")

    @field_validator("buyback_price")
    @classmethod
    def validate_positive_price(cls, v: int) -> int:
        if v < 0:
            raise ValueError("buyback_price must be non-negative")
        return v

    @field_validator("brand")
    @classmethod
    def clean_brand(cls, v: str) -> str:
        return v.strip().title()


# Alias for clarity
CashifyBuyPriceRecord = MobilePriceRecord


class IntervalReportRecord(BaseModel):
    """Identifies and tracks an interval execution report in scraper.interval_reports."""
    report_id: str
    report_day: date
    report_time: time
    report_bucket: str
    interval_minutes: int = 30
    source_feed: str = "cashify-in"
    devices_processed: int = 0
    cashify_rows_added: int = 0
    observations_added: int = 0
    market_rows_added: int = 0
    status: str = "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CanonicalDeviceRecord(BaseModel):
    """Canonical device entry for scraper.devices."""
    id: str
    brand: str
    model: str
    storage_gb: int
    ram_gb: Optional[int] = None
    release_year: Optional[int] = None
    aliases: Optional[str] = None
    report_id: str
    report_day: date
    report_time: time
    report_bucket: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceRepairExchangeCostRecord(BaseModel):
    """Repair and exchange cost benchmarks for scraper.device_repair_exchange_costs."""
    device_id: str
    brand: str
    model: str
    storage_gb: int
    currency: str = "INR"
    oem_exchange_flawless: int
    retail_exchange_good: int
    exchange_cracked_grade: int
    screen_repair_cost: int
    battery_repair_cost: int
    housing_backglass_cost: int
    board_ic_repair_cost: int
    minor_polish_qc_cost: int
    report_id: str
    report_day: date
    report_time: time
    report_bucket: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ObservationRecord(BaseModel):
    """Normalized observation for scraper.observations."""
    program_id: str = "cashify-in"
    device_id: str
    condition_label: str
    amount_minor: int
    currency: str = "INR"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    source_url: Optional[str] = None
    report_id: str
    report_day: date
    report_time: time
    report_bucket: str


class ScraperRunRecord(BaseModel):
    """Scraper run tracker for scraper.runs."""
    id: str
    program_id: str = "cashify-in"
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str = "succeeded"
    captured: int = 0
    errors: int = 0
    quarantined: int = 0
    note: Optional[str] = None
    report_id: str
    report_day: date
    report_time: time
    report_bucket: str


class CashifySellPriceRecord(BaseModel):
    """
    Represents a validated Refurbished Mobile Selling Price record (Cashify Sell Price).
    Refurbished device sold by Cashify to customers.
    """
    model_config = ConfigDict(frozen=True)

    brand: str = Field(..., description="Device manufacturer, e.g. Apple, Samsung")
    model: str = Field(..., description="Device model name, e.g. Apple iPhone 13")
    model_series: Optional[str] = Field(default=None, description="Model series, e.g. iPhone 13 Series, Galaxy S Series")
    variant: Optional[str] = Field(default=None, description="Variant string, e.g. 4 GB / 128 GB")
    storage: Optional[str] = Field(default=None, description="Storage capacity, e.g. 128 GB")
    ram: Optional[str] = Field(default=None, description="Device RAM, e.g. 4 GB")
    color: Optional[str] = Field(default=None, description="Color variant, e.g. Green, Midnight, Blue")
    network_type: Optional[str] = Field(default=None, description="Network type, e.g. 5G, 4G")
    
    # Manager Requirement: Prominently mark refurbished devices
    is_refurbished: bool = Field(default=True, description="Always True for refurbished mobiles")
    refurbished_mark: str = Field(default="REFURBISHED", description="Visual badge/mark for refurbished products")
    refurbished_grade: str = Field(..., description="Refurbished condition grade: Superb, Good, Fair, Best Value")
    device_condition: str = Field(..., description="Full descriptive condition, e.g. 'Refurbished - Superb (Like New)'")
    
    # Commercial Pricing
    selling_price: int = Field(..., ge=0, description="Selling price charged by Cashify to customer in INR")
    original_mrp: Optional[int] = Field(default=None, ge=0, description="Original manufacturer list price (MRP) in INR")
    discount_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Percentage savings vs MRP")
    
    warranty: Optional[str] = Field(default="6 Months Warranty, 15 Days Refund", description="Warranty policy")
    availability: str = Field(default="InStock", description="Availability status: InStock or OutOfStock")
    sku: Optional[str] = Field(default=None, description="Unique SKU code")
    currency: str = Field(default="INR", description="Currency ISO code")
    source_url: str = Field(..., description="Source product URL")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of scrape"
    )
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")

    @field_validator("selling_price")
    @classmethod
    def validate_selling_price(cls, v: int) -> int:
        if v < 0:
            raise ValueError("selling_price must be non-negative")
        return v

    @field_validator("brand")
    @classmethod
    def clean_brand(cls, v: str) -> str:
        return v.strip().title()
