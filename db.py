"""
Database Connection & SSH Tunnel Manager (Multi-Source Platform)
================================================================
Manages secure SSH tunneling to PostgreSQL (scrapingdb) and handles:
1. Centralized Scraping Sources Management (Websites & REST APIs)
2. Bucket-based Historical Snapshot Storage (immutable per scrape run)
3. Automated Price & Attribute Change Detection (historical delta tracking)
4. Backward-compatible live mirror upserts for existing endpoints
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from dotenv import load_dotenv

# Load .env variables if present
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("DBManager")


def resolve_report_bucket(dt: Optional[datetime] = None, interval_mins: int = 30) -> Dict[str, Any]:
    """
    Computes standard interval bucket parameters matching PostgreSQL resolve_report_bucket:
    report_id, report_day, report_time, report_bucket.
    """
    if dt is None:
        dt = datetime.now()
    hour = dt.hour
    minute = dt.minute

    if hour < 6:
        bucket_prefix = "B1_OVERNIGHT_00_06"
    elif hour < 12:
        bucket_prefix = "B2_MORNING_06_12"
    elif hour < 18:
        bucket_prefix = "B3_AFTERNOON_12_18"
    else:
        bucket_prefix = "B4_EVENING_18_24"

    slot_start = (minute // interval_mins) * interval_mins
    slot_str = f"{hour:02d}:{slot_start:02d}"

    report_day = dt.date().isoformat()
    report_time = dt.time().strftime("%H:%M:%S")
    report_bucket = f"{bucket_prefix} [{slot_str}]"
    prefix_short = bucket_prefix.split("_")[0]
    report_id = f"RPT-{dt.strftime('%Y%m%d-%H%M%S')}-{prefix_short}"

    return {
        "report_id": report_id,
        "report_day": report_day,
        "report_time": report_time,
        "report_bucket": report_bucket,
    }


def _parse_storage_gb(storage_str: Any, model_str: str = "", url_str: str = "") -> int:
    """Extract integer storage capacity in GB."""
    combined = f"{storage_str or ''} {model_str or ''} {url_str or ''}"
    m_tb = re.search(r"(\d+)\s*TB", combined, re.I)
    if m_tb:
        return int(m_tb.group(1)) * 1024
    m_gb = re.search(r"(\d+)\s*(?:GB|gb)", combined, re.I)
    if m_gb:
        return int(m_gb.group(1))
    m_num = re.search(r"\b(\d{2,4})\b", str(storage_str or ""))
    if m_num:
        val = int(m_num.group(1))
        if val in (16, 32, 64, 128, 256, 512, 1024):
            return val
    return 128


def _parse_ram_gb(ram_str: Any, model_str: str = "", url_str: str = "") -> Optional[int]:
    """Extract integer RAM capacity in GB if applicable."""
    if ram_str:
        m = re.search(r"(\d+)\s*(?:GB|gb)", str(ram_str), re.I)
        if m:
            return int(m.group(1))
    m_slash = re.search(r"(\d+)\s*(?:GB|gb)\s*/\s*\d+\s*(?:GB|gb)", model_str or "", re.I)
    if m_slash:
        return int(m_slash.group(1))
    m_url = re.search(r"-(\d+)-gb-(\d+)-gb", url_str or "", re.I)
    if m_url:
        return int(m_url.group(1))
    return None


def _clean_device_model(raw_model: str, brand: str) -> str:
    """Normalize model string to match canonical scraper.devices hierarchy."""
    cleaned = (raw_model or "").strip()
    cleaned = re.sub(r"^Sell\s+Old\s+", "", cleaned, flags=re.I)
    if brand and cleaned.lower().startswith(brand.lower()):
        cleaned = cleaned[len(brand):].strip()
    cleaned = re.sub(r"\s*\(\s*\d+\s*(?:GB|TB).*?\)\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*Online\s*&.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:5G|4G|AI Smartphone|Smartphone|Mobile Phone)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80].strip()


def _build_canonical_device_id(brand: str, model: str, storage_gb: int) -> str:
    """Build canonical device primary key slug."""
    clean_m = _clean_device_model(model, brand)
    base = f"{brand}-{clean_m}-{storage_gb}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return slug[:140].rstrip("-")


def _derive_model_series(brand: str, model_name: str) -> str:
    """Derive model series hierarchy across all major mobile manufacturers."""
    m = model_name.lower()
    b = brand.lower()

    # Apple iPhone
    if "iphone 16" in m:
        return "iPhone 16 Series"
    if "iphone 15" in m:
        return "iPhone 15 Series"
    if "iphone 14" in m:
        return "iPhone 14 Series"
    if "iphone 13" in m:
        return "iPhone 13 Series"
    if "iphone 12" in m:
        return "iPhone 12 Series"
    if "iphone 11" in m:
        return "iPhone 11 Series"
    if "iphone" in m:
        return "iPhone Series"

    # Samsung Galaxy
    if "z fold" in m:
        return "Galaxy Z Fold Series"
    if "z flip" in m:
        return "Galaxy Z Flip Series"
    if "s24" in m:
        return "Galaxy S24 Series"
    if "s23" in m:
        return "Galaxy S23 Series"
    if "s22" in m:
        return "Galaxy S22 Series"
    if "s21" in m:
        return "Galaxy S21 Series"
    if "note 20" in m:
        return "Galaxy Note 20 Series"
    if "note 10" in m:
        return "Galaxy Note 10 Series"
    if "note 9" in m:
        return "Galaxy Note 9 Series"
    if "note 8" in m:
        return "Galaxy Note 8 Series"
    if "note" in m:
        return "Galaxy Note Series"
    if "galaxy a" in m:
        return "Galaxy A Series"
    if "galaxy f" in m or "galaxy m" in m:
        return "Galaxy M & F Series"

    # OnePlus
    if "oneplus" in b or "oneplus" in m:
        for num in ("13", "12", "11", "10", "9", "8", "7"):
            if num in m:
                return f"OnePlus {num} Series"
        if "nord" in m:
            return "OnePlus Nord Series"
        if "open" in m:
            return "OnePlus Open Series"
        return "OnePlus Series"

    # Google Pixel
    if "google" in b or "pixel" in m:
        for num in ("9", "8", "7", "6"):
            if num in m:
                return f"Pixel {num} Series"
        return "Pixel Series"

    # Xiaomi / Redmi
    if "redmi" in b or "redmi" in m:
        if "note" in m:
            return "Redmi Note Series"
        return "Redmi Series"
    if "xiaomi" in b or "xiaomi" in m:
        return "Xiaomi Flagship Series"

    # Vivo / iQOO
    if "iqoo" in b or "iqoo" in m:
        return "iQOO Series"
    if "vivo" in b or "vivo" in m:
        if "x" in m:
            return "Vivo X Series"
        if "v" in m:
            return "Vivo V Series"
        if "t" in m:
            return "Vivo T Series"
        return "Vivo Series"

    # Oppo
    if "oppo" in b or "oppo" in m:
        if "find" in m:
            return "Oppo Find Series"
        if "reno" in m:
            return "Oppo Reno Series"
        return "Oppo Series"

    # Realme
    if "realme" in b or "realme" in m:
        if "gt" in m:
            return "Realme GT Series"
        return "Realme Series"

    # Motorola
    if "motorola" in b or "moto" in m:
        if "edge" in m:
            return "Moto Edge Series"
        if "razr" in m:
            return "Moto Razr Series"
        if "g" in m:
            return "Moto G Series"
        return "Motorola Series"

    # Nothing
    if "nothing" in b or "nothing" in m:
        return "Nothing Phone Series"

    return f"{brand} {model_name}"


def _compute_repair_benchmarks(base_price: int) -> Dict[str, int]:
    """Calculate component repair benchmarks and exchange benchmarks from Grade A price."""
    wholesale_inr = int(round((base_price / 0.80) / 500.0) * 500)
    polish_cost   = int(max(600, round((base_price * 0.04) / 100.0) * 100))
    battery_cost  = int(max(1800, round((base_price * 0.07) / 100.0) * 100))
    housing_cost  = int(max(2200, round((base_price * 0.09) / 100.0) * 100))
    screen_repair = int(max(4500, round((base_price * 0.24) / 100.0) * 100))
    board_cost    = int(max(6500, round((base_price * 0.36) / 100.0) * 100))

    return {
        "wholesale_inr": wholesale_inr,
        "minor_polish_qc_cost": polish_cost,
        "battery_repair_cost": battery_cost,
        "housing_backglass_cost": housing_cost,
        "screen_repair_cost": screen_repair,
        "board_ic_repair_cost": board_cost,
        "oem_exchange_flawless": int(round((wholesale_inr * 0.82) / 500.0) * 500),
        "retail_exchange_good": int(round((wholesale_inr * 0.78) / 500.0) * 500),
        "exchange_cracked_grade": int(round((wholesale_inr * 0.46) / 500.0) * 500),
    }


class DatabaseManager:
    """Manages SSH tunnel and database operations for Multi-Source Scraping & Comparison Platform."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        ssh_host: Optional[str] = None,
        ssh_port: int = 22,
        ssh_username: Optional[str] = None,
        ssh_pkey_path: Optional[str] = None,
        db_dialect: str = "postgresql",
        db_name: str = "scrapingdb",
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
        db_host: str = "127.0.0.1",
        db_remote_port: Optional[int] = None,
        db_schema: Optional[str] = None,
    ):
        # 1. Check for DATABASE_URL (takes precedence for direct connections)
        db_url = database_url or os.getenv("DATABASE_URL")
        self.database_url = db_url
        if db_url:
            import urllib.parse
            # Safe parsing regex for passwords containing unencoded '@' characters
            url_match = re.match(r'^(?P<scheme>[^:]+)://(?:(?P<user>[^:]+)(?::(?P<password>.+))?@)?(?P<host>[^:/@]+)(?::(?P<port>\d+))?(?:/(?P<dbname>[^?]+))?', db_url)
            if url_match:
                db_dialect = (url_match.group("scheme") or "postgresql").lower().split("+")[0]
                db_user = urllib.parse.unquote(url_match.group("user") or "")
                db_password = urllib.parse.unquote(url_match.group("password") or "")
                db_host = url_match.group("host") or "127.0.0.1"
                default_p = 5432 if "postgres" in db_dialect else 3306
                db_remote_port = int(url_match.group("port") or default_p)
                db_name = (url_match.group("dbname") or "scrapingdb").strip("/")
            else:
                parsed = urllib.parse.urlparse(db_url)
                db_dialect = (parsed.scheme.split("+")[0] or "postgresql").lower()
                db_user = urllib.parse.unquote(parsed.username or "")
                db_password = urllib.parse.unquote(parsed.password or "")
                db_host = parsed.hostname or "127.0.0.1"
                default_p = 5432 if "postgres" in db_dialect else 3306
                db_remote_port = parsed.port or default_p
                parsed_path = parsed.path.lstrip("/")
                if parsed_path:
                    db_name = parsed_path

        self.ssh_host = ssh_host if ssh_host is not None else os.getenv("SSH_HOST", "")
        self.ssh_port = int(ssh_port if ssh_port is not None else os.getenv("SSH_PORT", "22"))
        self.ssh_username = ssh_username if ssh_username is not None else os.getenv("SSH_USERNAME", "")
        self.ssh_pkey_path = ssh_pkey_path if ssh_pkey_path is not None else os.getenv("SSH_PRIVATE_KEY_PATH", "./proxy.pem")

        self.db_dialect = (db_dialect if db_dialect is not None else os.getenv("DB_DIALECT", "postgresql")).lower()
        self.db_name = db_name if db_name is not None else os.getenv("DB_NAME", "scrapingdb")
        self.db_user = db_user if db_user is not None else os.getenv("DB_USERNAME", "")
        self.db_password = db_password if db_password is not None else os.getenv("DB_PASSWORD", "")
        self.db_host = db_host if db_host is not None else os.getenv("DB_HOST", "127.0.0.1")

        default_port = 5432 if self.db_dialect == "postgresql" else 3306
        self.db_remote_port = int(db_remote_port if db_remote_port is not None else os.getenv("DB_PORT", str(default_port)))

        # Default schema is 'scraper' or 'public'
        default_schema = "scraper" if self.db_name == "scrapingdb" else "public"
        self.db_schema = db_schema or os.getenv("DB_SCHEMA", default_schema)

        self._tunnel = None
        self._tunnel_ref_count = 0

    def start_tunnel(self) -> int:
        """Starts the SSH tunnel and returns the local assigned port."""
        if self._tunnel and self._tunnel.is_active:
            self._tunnel_ref_count += 1
            return self._tunnel.local_bind_port

        from sshtunnel import SSHTunnelForwarder

        pkey_path = Path(self.ssh_pkey_path).resolve()
        if not pkey_path.exists():
            raise FileNotFoundError(
                f"SSH private key file not found at: {pkey_path}. "
                f"Please ensure proxy.pem is present."
            )

        logger.info(
            "Establishing SSH tunnel to %s@%s:%d -> remote DB port %d...",
            self.ssh_username,
            self.ssh_host,
            self.ssh_port,
            self.db_remote_port,
        )

        self._tunnel = SSHTunnelForwarder(
            (self.ssh_host, self.ssh_port),
            ssh_username=self.ssh_username,
            ssh_pkey=str(pkey_path),
            remote_bind_address=("127.0.0.1", self.db_remote_port),
        )
        self._tunnel.start()
        self._tunnel_ref_count = 1
        local_port = self._tunnel.local_bind_port
        logger.info("SSH tunnel established. Local forwarded port: %d", local_port)
        return local_port

    def stop_tunnel(self) -> None:
        """Closes the active SSH tunnel if no active callers remain."""
        if self._tunnel_ref_count > 1:
            self._tunnel_ref_count -= 1
            return

        self._tunnel_ref_count = 0
        if self._tunnel and self._tunnel.is_active:
            self._tunnel.stop()
            logger.info("SSH tunnel closed.")
            self._tunnel = None

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Context manager providing an active database connection (direct or over SSH tunnel)."""
        use_tunnel = bool(
            self.ssh_host
            and os.path.exists(self.ssh_pkey_path or "")
            and os.getenv("USE_SSH_TUNNEL", "true").lower() in ("true", "1", "yes")
        )

        target_host = self.db_host
        target_port = self.db_remote_port

        if use_tunnel:
            target_port = self.start_tunnel()
            target_host = "127.0.0.1" 
        conn = None
        try:
            if self.db_dialect == "postgresql":
                import psycopg2
                try:
                    conn = psycopg2.connect(
                        host=target_host,
                        port=target_port,
                        dbname=self.db_name,
                        user=self.db_user,
                        password=self.db_password,
                        connect_timeout=10,
                    )
                except Exception as direct_err:
                    if self.database_url and not use_tunnel:
                        try:
                            conn = psycopg2.connect(self.database_url, connect_timeout=10)
                        except Exception:
                            raise direct_err
                    else:
                        raise direct_err
            elif self.db_dialect in ("sqlite", "sqlite3"):
                import sqlite3
                sqlite_path = self.database_url.replace("sqlite:///", "").replace("sqlite://", "") if self.database_url else self.db_name
                conn = sqlite3.connect(sqlite_path)
                conn.row_factory = sqlite3.Row
            elif self.db_dialect == "mysql":
                import pymysql
                conn = pymysql.connect(
                    host=target_host,
                    port=target_port,
                    database=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                    autocommit=False,
                )
            else:
                raise ValueError(f"Unsupported DB dialect: {self.db_dialect}")

            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            if use_tunnel:
                self.stop_tunnel()

    def create_table_if_not_exists(self, conn: Any) -> None:
        """Initializes all platform tables in PostgreSQL (schema: scraper / public)."""
        schema = self.db_schema

        if self.db_dialect == "postgresql":
            with conn.cursor() as cur:
                if schema and schema != "public":
                    try:
                        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
                    except Exception:
                        pass
                cur.execute(f"SET search_path TO {schema}, public;")

                # 1. Existing live mirror table (Backward-compatible)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS mobile_buyback_pricing (
                    id SERIAL PRIMARY KEY,
                    brand VARCHAR(50) NOT NULL,
                    model VARCHAR(200) NOT NULL,
                    storage VARCHAR(50),
                    ram VARCHAR(50),
                    cores VARCHAR(50),
                    camera VARCHAR(100),
                    condition VARCHAR(255) NOT NULL,
                    defects TEXT,
                    buyback_price NUMERIC(10, 2) NOT NULL,
                    currency VARCHAR(10) DEFAULT 'INR',
                    data_origin VARCHAR(50),
                    confidence_score NUMERIC(3, 2),
                    source_url TEXT NOT NULL,
                    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_device_variant_condition UNIQUE (source_url, storage, condition)
                );
                CREATE INDEX IF NOT EXISTS idx_brand_model ON mobile_buyback_pricing (brand, model);
                """)

                # 1b. Separate Cashify Buy Prices Table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS cashify_buy_prices (
                    id SERIAL PRIMARY KEY,
                    brand VARCHAR(50) NOT NULL,
                    model VARCHAR(200) NOT NULL,
                    model_series VARCHAR(100),
                    variant VARCHAR(100),
                    storage VARCHAR(50),
                    ram VARCHAR(50),
                    cores VARCHAR(50),
                    camera VARCHAR(100),
                    color VARCHAR(50),
                    network_type VARCHAR(20),
                    condition VARCHAR(255) NOT NULL,
                    defects TEXT,
                    buyback_price NUMERIC(10, 2) NOT NULL,
                    max_advertised_price NUMERIC(10, 2),
                    condition_deductions NUMERIC(10, 2),
                    currency VARCHAR(10) DEFAULT 'INR',
                    data_origin VARCHAR(50) DEFAULT 'verified_scraped',
                    confidence_score NUMERIC(3, 2) DEFAULT 1.0,
                    source_url TEXT NOT NULL,
                    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_buy_device_variant_condition UNIQUE (source_url, storage, condition)
                );
                CREATE INDEX IF NOT EXISTS idx_buy_brand_model ON cashify_buy_prices (brand, model);
                """)

                # 1c. Separate Cashify Sell Prices Table (Refurbished Mobiles)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS cashify_sell_prices (
                    id SERIAL PRIMARY KEY,
                    brand VARCHAR(50) NOT NULL,
                    model VARCHAR(200) NOT NULL,
                    model_series VARCHAR(100),
                    variant VARCHAR(100),
                    storage VARCHAR(50),
                    ram VARCHAR(50),
                    color VARCHAR(50),
                    network_type VARCHAR(20),
                    is_refurbished BOOLEAN DEFAULT TRUE NOT NULL,
                    refurbished_mark VARCHAR(50) DEFAULT 'REFURBISHED' NOT NULL,
                    refurbished_grade VARCHAR(50) NOT NULL,
                    device_condition VARCHAR(150) NOT NULL,
                    selling_price NUMERIC(10, 2) NOT NULL,
                    original_mrp NUMERIC(10, 2),
                    discount_percent NUMERIC(5, 2),
                    warranty VARCHAR(200) DEFAULT '6 Months Warranty, 15 Days Refund',
                    availability VARCHAR(50) DEFAULT 'InStock',
                    sku VARCHAR(100),
                    currency VARCHAR(10) DEFAULT 'INR',
                    source_url TEXT NOT NULL,
                    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_sell_sku_grade UNIQUE (source_url, sku, refurbished_grade)
                );
                CREATE INDEX IF NOT EXISTS idx_sell_brand_model ON cashify_sell_prices (brand, model);
                CREATE INDEX IF NOT EXISTS idx_sell_is_refurbished ON cashify_sell_prices (is_refurbished);
                CREATE INDEX IF NOT EXISTS idx_sell_grade ON cashify_sell_prices (refurbished_grade);
                """)

                # 2. Centralized Scraping Sources Management Table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS scraping_sources (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    source_type VARCHAR(50) NOT NULL DEFAULT 'website_cashify',
                    category VARCHAR(100) NOT NULL DEFAULT 'Smartphones',
                    bucket_name VARCHAR(100) NOT NULL DEFAULT 'cashify_buyback',
                    target_url TEXT NOT NULL,
                    http_method VARCHAR(10) NOT NULL DEFAULT 'GET',
                    headers_json JSONB DEFAULT '{}'::jsonb,
                    auth_config_json JSONB DEFAULT '{}'::jsonb,
                    params_json JSONB DEFAULT '{}'::jsonb,
                    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                    schedule_interval_min INT DEFAULT 1440,
                    last_scraped_at TIMESTAMP WITH TIME ZONE,
                    last_status_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sources_status ON scraping_sources (status);
                CREATE INDEX IF NOT EXISTS idx_sources_bucket ON scraping_sources (bucket_name);
                """)

                # 3. Scraping Runs Execution Table (Snapshots Tracker)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS scraping_runs (
                    id SERIAL PRIMARY KEY,
                    source_id INT REFERENCES scraping_sources(id) ON DELETE SET NULL,
                    bucket_name VARCHAR(100) NOT NULL,
                    run_status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
                    records_count INT DEFAULT 0,
                    changes_count INT DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP WITH TIME ZONE
                );
                CREATE INDEX IF NOT EXISTS idx_runs_bucket ON scraping_runs (bucket_name, started_at);
                """)

                # 4. Bucket-Based Historical Snapshots (Immutable per run)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS historical_price_snapshots (
                    id SERIAL PRIMARY KEY,
                    run_id INT REFERENCES scraping_runs(id) ON DELETE CASCADE,
                    source_id INT REFERENCES scraping_sources(id) ON DELETE SET NULL,
                    bucket_name VARCHAR(100) NOT NULL,
                    device_identifier VARCHAR(255) NOT NULL,
                    brand VARCHAR(100),
                    model VARCHAR(255) NOT NULL,
                    storage VARCHAR(50),
                    ram VARCHAR(50),
                    cores VARCHAR(50),
                    camera VARCHAR(100),
                    condition_grade VARCHAR(100),
                    defects TEXT,
                    buyback_price NUMERIC(12, 2) NOT NULL,
                    currency VARCHAR(10) DEFAULT 'INR',
                    raw_attributes JSONB DEFAULT '{}'::jsonb,
                    source_url TEXT,
                    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON historical_price_snapshots (bucket_name, device_identifier, condition_grade, captured_at DESC);
                """)

                # 5. Price & Attribute Change Events Table
                cur.execute("""
                CREATE TABLE IF NOT EXISTS price_change_events (
                    id SERIAL PRIMARY KEY,
                    run_id INT REFERENCES scraping_runs(id) ON DELETE CASCADE,
                    source_id INT REFERENCES scraping_sources(id) ON DELETE SET NULL,
                    bucket_name VARCHAR(100) NOT NULL,
                    device_identifier VARCHAR(255) NOT NULL,
                    brand VARCHAR(100),
                    model VARCHAR(255) NOT NULL,
                    storage VARCHAR(50),
                    condition_grade VARCHAR(100),
                    old_price NUMERIC(12, 2),
                    new_price NUMERIC(12, 2) NOT NULL,
                    price_diff NUMERIC(12, 2) NOT NULL,
                    pct_change NUMERIC(7, 2),
                    change_type VARCHAR(20) NOT NULL,
                    attribute_changes JSONB DEFAULT '{}'::jsonb,
                    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_change_events_lookup ON price_change_events (bucket_name, change_type, detected_at DESC);
                """)

            conn.commit()
            logger.info("Enterprise multi-source tables and indexes verified in schema %s.", schema)
        elif self.db_dialect in ("sqlite", "sqlite3"):
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS mobile_buyback_pricing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                storage TEXT,
                ram TEXT,
                cores TEXT,
                camera TEXT,
                condition TEXT NOT NULL,
                defects TEXT,
                buyback_price REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                data_origin TEXT,
                confidence_score REAL,
                source_url TEXT NOT NULL,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_url, storage, condition)
            );
            CREATE TABLE IF NOT EXISTS cashify_buy_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                model_series TEXT,
                variant TEXT,
                storage TEXT,
                ram TEXT,
                cores TEXT,
                camera TEXT,
                color TEXT,
                network_type TEXT,
                condition TEXT NOT NULL,
                defects TEXT,
                buyback_price REAL NOT NULL,
                max_advertised_price REAL,
                condition_deductions REAL,
                currency TEXT DEFAULT 'INR',
                data_origin TEXT DEFAULT 'verified_scraped',
                confidence_score REAL DEFAULT 1.0,
                source_url TEXT NOT NULL,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_url, storage, condition)
            );
            CREATE TABLE IF NOT EXISTS cashify_sell_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                model_series TEXT,
                variant TEXT,
                storage TEXT,
                ram TEXT,
                color TEXT,
                network_type TEXT,
                is_refurbished INTEGER DEFAULT 1 NOT NULL,
                refurbished_mark TEXT DEFAULT 'REFURBISHED' NOT NULL,
                refurbished_grade TEXT NOT NULL,
                device_condition TEXT NOT NULL,
                selling_price REAL NOT NULL,
                original_mrp REAL,
                discount_percent REAL,
                warranty TEXT DEFAULT '6 Months Warranty, 15 Days Refund',
                availability TEXT DEFAULT 'InStock',
                sku TEXT,
                currency TEXT DEFAULT 'INR',
                source_url TEXT NOT NULL,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_url, sku, refurbished_grade)
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS scraping_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'website_cashify',
                category TEXT NOT NULL DEFAULT 'Smartphones',
                bucket_name TEXT NOT NULL DEFAULT 'cashify_buyback',
                target_url TEXT NOT NULL,
                http_method TEXT NOT NULL DEFAULT 'GET',
                headers_json TEXT DEFAULT '{}',
                auth_config_json TEXT DEFAULT '{}',
                params_json TEXT DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                schedule_interval_min INT DEFAULT 1440,
                last_scraped_at TEXT,
                last_status_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS priceiq_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device TEXT NOT NULL,
                storage TEXT,
                condition_grade TEXT,
                price REAL NOT NULL,
                market TEXT DEFAULT 'IN',
                channel TEXT DEFAULT 'wholesale',
                source TEXT DEFAULT 'PriceIQ Wholesale Engine',
                comparables INT DEFAULT 1,
                synced_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
            logger.info("SQLite multi-source and PriceIQ tables verified.")

    # =========================================================================
    # Source Management (CRUD & State)
    # =========================================================================

    def seed_default_sources_if_empty(self) -> int:
        """Populates scraping_sources from TARGET_DEVICES, DEFAULT_API_SOURCES, and DEFAULT_AMAZON_SOURCES if not already present."""
        from config import TARGET_DEVICES, DEFAULT_API_SOURCES, DEFAULT_AMAZON_SOURCES

        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("SELECT target_url FROM scraping_sources;")
                existing_urls = {row[0] for row in cur.fetchall()}

                inserted = 0

                # 1. Seed Cashify targets if not present
                for dev in TARGET_DEVICES:
                    url = dev.get("url", "").strip()
                    if url and url not in existing_urls:
                        brand = dev.get("brand", "Unknown")
                        family = dev.get("model_family", "Device")
                        name = f"Cashify - {brand} {family}"
                        cur.execute("""
                            INSERT INTO scraping_sources (
                                name, source_type, category, bucket_name,
                                target_url, http_method, status
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """, (name, "website_cashify", "Smartphones", "cashify_buyback", url, "GET", "ACTIVE"))
                        existing_urls.add(url)
                        inserted += 1

                # 2. Seed WholeCellMarket & Other API Sources if not present
                for api_src in DEFAULT_API_SOURCES:
                    url = api_src.get("target_url", "").strip()
                    if url and url not in existing_urls:
                        cur.execute("""
                            INSERT INTO scraping_sources (
                                name, source_type, category, bucket_name,
                                target_url, http_method, headers_json,
                                auth_config_json, params_json, status
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s);
                        """, (
                            api_src.get("name"),
                            api_src.get("source_type", "rest_api"),
                            api_src.get("category", "Smartphones"),
                            api_src.get("bucket_name", "api_pricing"),
                            url,
                            api_src.get("http_method", "GET"),
                            json.dumps(api_src.get("headers_json", {})),
                            json.dumps(api_src.get("auth_config_json", {})),
                            json.dumps(api_src.get("params_json", {})),
                            api_src.get("status", "ACTIVE"),
                        ))
                        existing_urls.add(url)
                        inserted += 1

                # 3. Seed Amazon India Sources if not present
                for amz_src in DEFAULT_AMAZON_SOURCES:
                    url = amz_src.get("target_url", "").strip()
                    if url and url not in existing_urls:
                        cur.execute("""
                            INSERT INTO scraping_sources (
                                name, source_type, category, bucket_name,
                                target_url, http_method, status
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """, (
                            amz_src.get("name"),
                            amz_src.get("source_type", "website_amazon"),
                            amz_src.get("category", "eCommerce / Retail & Renewed"),
                            amz_src.get("bucket_name", "amazon_pricing"),
                            url,
                            amz_src.get("http_method", "GET"),
                            amz_src.get("status", "ACTIVE"),
                        ))
                        existing_urls.add(url)
                        inserted += 1

                if inserted > 0:
                    conn.commit()
                    logger.info("Seeded %d new default sources into PostgreSQL.", inserted)

                cur.execute("SELECT COUNT(*) FROM scraping_sources;")
                return cur.fetchone()[0]

    def get_sources(self, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all registered scraping sources with optional filters."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")

                query = "SELECT * FROM scraping_sources WHERE 1=1"
                params = []
                if status:
                    query += " AND status = %s"
                    params.append(status)
                if category:
                    query += " AND category = %s"
                    params.append(category)
                query += " ORDER BY id ASC;"

                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                results = []
                for r in rows:
                    row_dict = dict(zip(columns, r))
                    if row_dict.get("last_scraped_at"):
                        row_dict["last_scraped_at_fmt"] = row_dict["last_scraped_at"].strftime("%d %b %Y, %I:%M %p")
                    else:
                        row_dict["last_scraped_at_fmt"] = "Never"
                    results.append(row_dict)
                return results

    def get_source(self, source_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single source by ID."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("SELECT * FROM scraping_sources WHERE id = %s;", (source_id,))
                row = cur.fetchone()
                if not row:
                    return None
                columns = [desc[0] for desc in cur.description]
                return dict(zip(columns, row))

    def add_source(
        self,
        name: str,
        target_url: str,
        source_type: str = "website_cashify",
        category: str = "Smartphones",
        bucket_name: str = "cashify_buyback",
        http_method: str = "GET",
        headers: Optional[Dict[str, Any]] = None,
        auth_config: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        schedule_interval_min: int = 1440,
        status: str = "ACTIVE",
    ) -> int:
        """Register a new scraping source (website or REST API)."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("""
                    INSERT INTO scraping_sources (
                        name, source_type, category, bucket_name,
                        target_url, http_method, headers_json, auth_config_json,
                        params_json, schedule_interval_min, status, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    RETURNING id;
                """, (
                    name, source_type, category, bucket_name,
                    target_url, http_method.upper(),
                    json.dumps(headers or {}),
                    json.dumps(auth_config or {}),
                    json.dumps(params or {}),
                    schedule_interval_min, status.upper()
                ))
                new_id = cur.fetchone()[0]
                conn.commit()
                logger.info("Created new scraping source ID %d: %s", new_id, name)
                return new_id

    def update_source(self, source_id: int, updates: Dict[str, Any]) -> bool:
        """Update configuration of an existing scraping source."""
        allowed_fields = {
            "name", "source_type", "category", "bucket_name", "target_url",
            "http_method", "headers_json", "auth_config_json", "params_json",
            "schedule_interval_min", "status", "last_status_message", "last_scraped_at"
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}
        if not filtered:
            return False

        set_clauses = []
        params = []
        for k, v in filtered.items():
            set_clauses.append(f"{k} = %s")
            if isinstance(v, (dict, list)):
                params.append(json.dumps(v))
            else:
                params.append(v)
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(source_id)

        query = f"UPDATE scraping_sources SET {', '.join(set_clauses)} WHERE id = %s;"
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute(query, params)
                conn.commit()
                return cur.rowcount > 0

    def set_source_status(self, source_id: int, status: str, message: Optional[str] = None) -> bool:
        """Pause, Resume, or set Status for a scraping source."""
        status = status.upper()
        if status not in {"ACTIVE", "PAUSED", "RUNNING", "FAILED"}:
            raise ValueError(f"Invalid source status: {status}")
        updates = {"status": status}
        if message is not None:
            updates["last_status_message"] = message
        return self.update_source(source_id, updates)

    def delete_source(self, source_id: int) -> bool:
        """Delete a scraping source."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("DELETE FROM scraping_sources WHERE id = %s;", (source_id,))
                conn.commit()
                return cur.rowcount > 0

    # =========================================================================
    # Bucket-Based Historical Snapshots & Runs Execution
    # =========================================================================

    def start_scrape_run(self, source_id: Optional[int], bucket_name: str) -> int:
        """Record the beginning of a scrape execution run."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("""
                    INSERT INTO scraping_runs (source_id, bucket_name, run_status)
                    VALUES (%s, %s, 'RUNNING')
                    RETURNING id;
                """, (source_id, bucket_name))
                run_id = cur.fetchone()[0]
                if source_id:
                    cur.execute("""
                        UPDATE scraping_sources
                        SET status = 'RUNNING', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (source_id,))
                conn.commit()
                return run_id

    def finish_scrape_run(
        self,
        run_id: int,
        source_id: Optional[int],
        status: str,
        records_count: int,
        changes_count: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Finalize a scrape execution run with completed metrics."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("""
                    UPDATE scraping_runs
                    SET run_status = %s,
                        records_count = %s,
                        changes_count = %s,
                        error_message = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (status, records_count, changes_count, error_message, run_id))

                if source_id:
                    next_status = "ACTIVE" if status == "SUCCESS" else ("FAILED" if status == "FAILED" else "ACTIVE")
                    cur.execute("""
                        UPDATE scraping_sources
                        SET status = %s,
                            last_scraped_at = CURRENT_TIMESTAMP,
                            last_status_message = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (next_status, error_message or f"Completed {records_count} records ({changes_count} changes)", source_id))
                conn.commit()

    def get_recent_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent scraping run logs joined with source details."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                cur.execute("""
                    SELECT r.id, r.source_id, r.bucket_name, r.run_status,
                           r.records_count, r.changes_count, r.error_message,
                           r.started_at, r.completed_at,
                           s.name as source_name, s.source_type
                    FROM scraping_runs r
                    LEFT JOIN scraping_sources s ON r.source_id = s.id
                    ORDER BY r.started_at DESC
                    LIMIT %s;
                """, (limit,))
                rows = cur.fetchall()
                results = []
                for row in rows:
                    started = row[7]
                    completed = row[8]
                    duration_sec = None
                    if started and completed:
                        try:
                            duration_sec = round((completed - started).total_seconds(), 1)
                        except Exception:
                            pass
                    results.append({
                        "id": row[0],
                        "source_id": row[1],
                        "bucket_name": row[2],
                        "run_status": row[3],
                        "records_count": row[4] or 0,
                        "changes_count": row[5] or 0,
                        "error_message": row[6],
                        "started_at": started.strftime("%d %b %Y, %I:%M %p") if hasattr(started, "strftime") else str(started or "—"),
                        "completed_at": completed.strftime("%d %b %Y, %I:%M %p") if hasattr(completed, "strftime") else str(completed or "—"),
                        "duration_sec": duration_sec,
                        "source_name": row[9] or "Bulk Catalog Scrape",
                        "source_type": row[10] or "website_cashify",
                    })
                return results

    def save_historical_snapshots(
        self,
        run_id: int,
        source_id: Optional[int],
        bucket_name: str,
        records: List[Dict[str, Any]],
    ) -> int:
        """Store immutable historical price snapshots for this execution run."""
        if not records:
            return 0

        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")

                insert_sql = """
                INSERT INTO historical_price_snapshots (
                    run_id, source_id, bucket_name, device_identifier,
                    brand, model, storage, ram, cores, camera,
                    condition_grade, defects, buyback_price, currency,
                    raw_attributes, source_url, captured_at
                ) VALUES (
                    %(run_id)s, %(source_id)s, %(bucket_name)s, %(device_identifier)s,
                    %(brand)s, %(model)s, %(storage)s, %(ram)s, %(cores)s, %(camera)s,
                    %(condition_grade)s, %(defects)s, %(buyback_price)s, %(currency)s,
                    %(raw_attributes)s, %(source_url)s, CURRENT_TIMESTAMP
                );
                """

                count = 0
                for r in records:
                    brand = r.get("brand", "Unknown")
                    model = r.get("model", "Unknown")
                    storage = r.get("storage", "")
                    condition = r.get("condition", "Grade A")
                    price = float(r.get("buyback_price", 0))

                    identifier = f"{brand} {model}".strip()
                    if storage and storage not in identifier:
                        identifier = f"{identifier} ({storage})"

                    extra = {
                        "data_origin": r.get("data_origin"),
                        "confidence_score": r.get("confidence_score"),
                    }

                    cur.execute(insert_sql, {
                        "run_id": run_id,
                        "source_id": source_id,
                        "bucket_name": bucket_name,
                        "device_identifier": identifier,
                        "brand": brand,
                        "model": model,
                        "storage": storage,
                        "ram": r.get("ram", ""),
                        "cores": r.get("cores", ""),
                        "camera": r.get("camera", ""),
                        "condition_grade": condition.split(":")[0].strip(),
                        "defects": r.get("defects", "None"),
                        "buyback_price": price,
                        "currency": r.get("currency", "INR"),
                        "raw_attributes": json.dumps(extra),
                        "source_url": r.get("source_url", ""),
                    })
                    count += 1
                conn.commit()
                logger.info("Saved %d historical snapshots for run_id %s in bucket %s.", count, run_id, bucket_name)
                return count

    # =========================================================================
    # Comparison & Delta Detection Engine
    # =========================================================================

    def detect_and_record_changes(
        self,
        run_id: int,
        source_id: Optional[int],
        bucket_name: str,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Compares newly scraped records against the MOST RECENT snapshot in the same bucket.
        Calculates ΔP and %Δ, categorizes as INCREASED, DECREASED, UNCHANGED, or NEW,
        and saves events into price_change_events.
        """
        if not records:
            return []

        changes: List[Dict[str, Any]] = []

        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")

                # Retrieve the latest snapshot prices BEFORE this run in the same bucket
                cur.execute("""
                    SELECT DISTINCT ON (device_identifier, condition_grade)
                        device_identifier, condition_grade, buyback_price, captured_at
                    FROM historical_price_snapshots
                    WHERE bucket_name = %s AND run_id != %s
                    ORDER BY device_identifier, condition_grade, captured_at DESC;
                """, (bucket_name, run_id))

                prev_map = {
                    (row[0], row[1]): float(row[2])
                    for row in cur.fetchall()
                }

                change_sql = """
                INSERT INTO price_change_events (
                    run_id, source_id, bucket_name, device_identifier,
                    brand, model, storage, condition_grade,
                    old_price, new_price, price_diff, pct_change,
                    change_type, attribute_changes, detected_at
                ) VALUES (
                    %(run_id)s, %(source_id)s, %(bucket_name)s, %(device_identifier)s,
                    %(brand)s, %(model)s, %(storage)s, %(condition_grade)s,
                    %(old_price)s, %(new_price)s, %(price_diff)s, %(pct_change)s,
                    %(change_type)s, %(attribute_changes)s, CURRENT_TIMESTAMP
                );
                """

                for r in records:
                    brand = r.get("brand", "Unknown")
                    model = r.get("model", "Unknown")
                    storage = r.get("storage", "")
                    condition = r.get("condition", "Grade A").split(":")[0].strip()
                    new_price = float(r.get("buyback_price", 0))

                    identifier = f"{brand} {model}".strip()
                    if storage and storage not in identifier:
                        identifier = f"{identifier} ({storage})"

                    key = (identifier, condition)
                    old_price = prev_map.get(key)

                    if old_price is None:
                        change_type = "NEW"
                        diff = 0.0
                        pct = 0.0
                    elif new_price > old_price:
                        change_type = "INCREASED"
                        diff = round(new_price - old_price, 2)
                        pct = round((diff / old_price) * 100, 2)
                    elif new_price < old_price:
                        change_type = "DECREASED"
                        diff = round(new_price - old_price, 2)
                        pct = round((diff / old_price) * 100, 2)
                    else:
                        change_type = "UNCHANGED"
                        diff = 0.0
                        pct = 0.0

                    change_entry = {
                        "run_id": run_id,
                        "source_id": source_id,
                        "bucket_name": bucket_name,
                        "device_identifier": identifier,
                        "brand": brand,
                        "model": model,
                        "storage": storage,
                        "condition_grade": condition,
                        "old_price": old_price,
                        "new_price": new_price,
                        "price_diff": diff,
                        "pct_change": pct,
                        "change_type": change_type,
                        "attribute_changes": json.dumps({"defects": r.get("defects", "")}),
                    }

                    cur.execute(change_sql, change_entry)
                    changes.append(change_entry)

                conn.commit()
                logger.info("Recorded %d price comparisons for run %s.", len(changes), run_id)
                return changes

    # =========================================================================
    # Analytics & Comparison Reporting Queries
    # =========================================================================

    def get_price_comparison_report(
        self,
        bucket_name: Optional[str] = None,
        change_type: Optional[str] = None,
        limit: int = 150,
    ) -> List[Dict[str, Any]]:
        """Fetch comparative price changes for dashboard tables."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")

                query = """
                SELECT DISTINCT ON (device_identifier, condition_grade)
                    id, bucket_name, device_identifier, brand, model,
                    storage, condition_grade, old_price, new_price,
                    price_diff, pct_change, change_type, detected_at
                FROM price_change_events
                WHERE 1=1
                """
                params = []
                if bucket_name:
                    query += " AND bucket_name = %s"
                    params.append(bucket_name)
                if change_type:
                    query += " AND change_type = %s"
                    params.append(change_type)

                query += " ORDER BY device_identifier, condition_grade, detected_at DESC LIMIT %s;"
                params.append(limit)

                cur.execute(query, params)
                cols = [desc[0] for desc in cur.description]
                results = []
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    d["old_price_fmt"] = f"₹{int(d['old_price']):,}" if d.get("old_price") is not None else "—"
                    d["new_price_fmt"] = f"₹{int(d['new_price']):,}"
                    diff_val = d.get("price_diff", 0)
                    pct_val = d.get("pct_change", 0)
                    if diff_val > 0:
                        d["diff_fmt"] = f"+₹{int(diff_val):,} (+{pct_val:.2f}%)"
                        d["badge_cls"] = "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    elif diff_val < 0:
                        d["diff_fmt"] = f"-₹{abs(int(diff_val)):,} ({pct_val:.2f}%)"
                        d["badge_cls"] = "bg-rose-50 text-rose-700 border border-rose-200"
                    else:
                        d["diff_fmt"] = "No Change"
                        d["badge_cls"] = "bg-slate-50 text-slate-600 border border-slate-200"
                    results.append(d)
                return results

    def get_platform_analytics(self) -> Dict[str, Any]:
        """Aggregate high-level overview metrics across all sources, buckets, and changes."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")

                # Sources metrics
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_sources,
                        COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_sources,
                        COUNT(*) FILTER (WHERE status = 'PAUSED') AS paused_sources,
                        COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_sources
                    FROM scraping_sources;
                """)
                src = cur.fetchone()

                # Runs metrics
                cur.execute("""
                    SELECT
                        COUNT(*) AS total_runs,
                        COUNT(*) FILTER (WHERE run_status = 'SUCCESS') AS success_runs,
                        COUNT(*) FILTER (WHERE run_status = 'FAILED') AS failed_runs,
                        COALESCE(SUM(records_count), 0) AS total_records_collected
                    FROM scraping_runs;
                """)
                runs = cur.fetchone()

                # Change metrics
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE change_type = 'INCREASED') AS price_increases,
                        COUNT(*) FILTER (WHERE change_type = 'DECREASED') AS price_decreases,
                        COUNT(*) FILTER (WHERE change_type = 'UNCHANGED') AS price_unchanged,
                        COUNT(*) FILTER (WHERE change_type = 'NEW') AS new_items
                    FROM price_change_events;
                """)
                changes = cur.fetchone()

                # Total live records in mirror table
                cur.execute("SELECT COUNT(*) FROM mobile_buyback_pricing;")
                live_records = cur.fetchone()[0]

                return {
                    "total_sources": src[0] or 0,
                    "active_sources": src[1] or 0,
                    "paused_sources": src[2] or 0,
                    "failed_sources": src[3] or 0,
                    "total_runs": runs[0] or 0,
                    "success_runs": runs[1] or 0,
                    "failed_runs": runs[2] or 0,
                    "total_records_collected": runs[3] or live_records,
                    "live_records": live_records,
                    "price_increases": changes[0] or 0,
                    "price_decreases": changes[1] or 0,
                    "price_unchanged": changes[2] or 0,
                    "new_items": changes[3] or 0,
                }

    # =========================================================================
    # Live Mirror Table Upsert (Backward-Compatible)
    # =========================================================================

    def upsert_records(self, records: List[Dict[str, Any]]) -> int:
        """Upsert records into the live mirror table (mobile_buyback_pricing)."""
        if not records:
            logger.warning("No records supplied for DB upsert.")
            return 0

        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            inserted_or_updated = 0

            with conn.cursor() as cur:
                schema = self.db_schema
                cur.execute(f"SET search_path TO {schema}, public;")
                try:
                    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_device_variant_condition ON mobile_buyback_pricing (source_url, storage, condition);")
                    conn.commit()
                except Exception:
                    conn.rollback()

                query = """
                INSERT INTO mobile_buyback_pricing (
                    brand, model, storage, ram, cores, camera,
                    condition, defects, buyback_price, currency,
                    data_origin, confidence_score, source_url, scraped_at
                ) VALUES (
                    %(brand)s, %(model)s, %(storage)s, %(ram)s, %(cores)s, %(camera)s,
                    %(condition)s, %(defects)s, %(buyback_price)s, %(currency)s,
                    %(data_origin)s, %(confidence_score)s, %(source_url)s, %(timestamp)s
                )
                ON CONFLICT (source_url, storage, condition) DO UPDATE SET
                    buyback_price = EXCLUDED.buyback_price,
                    ram = EXCLUDED.ram,
                    cores = EXCLUDED.cores,
                    camera = EXCLUDED.camera,
                    defects = EXCLUDED.defects,
                    data_origin = EXCLUDED.data_origin,
                    confidence_score = EXCLUDED.confidence_score,
                    scraped_at = EXCLUDED.scraped_at;
                """

                for rec in records:
                    try:
                        cur.execute(query, {
                            "brand": rec.get("brand", "Unknown"),
                            "model": rec.get("model", "Unknown"),
                            "storage": rec.get("storage", ""),
                            "ram": rec.get("ram", ""),
                            "cores": rec.get("cores", ""),
                            "camera": rec.get("camera", ""),
                            "condition": rec.get("condition", "Grade A"),
                            "defects": rec.get("defects", "None"),
                            "buyback_price": rec.get("buyback_price", 0),
                            "currency": rec.get("currency", "INR"),
                            "data_origin": rec.get("data_origin", "verified_scraped"),
                            "confidence_score": rec.get("confidence_score", 1.0),
                            "source_url": rec.get("source_url", ""),
                            "timestamp": rec.get("timestamp"),
                        })
                        inserted_or_updated += 1
                    except Exception:
                        conn.rollback()
                        # Fallback simple update/insert
                        cur.execute("""
                            UPDATE mobile_buyback_pricing
                            SET buyback_price = %(buyback_price)s, scraped_at = %(timestamp)s
                            WHERE source_url = %(source_url)s AND storage = %(storage)s AND condition = %(condition)s;
                        """, {
                            "buyback_price": rec.get("buyback_price", 0),
                            "timestamp": rec.get("timestamp"),
                            "source_url": rec.get("source_url", ""),
                            "storage": rec.get("storage", ""),
                            "condition": rec.get("condition", "Grade A"),
                        })
                        if cur.rowcount == 0:
                            cur.execute("""
                                INSERT INTO mobile_buyback_pricing (
                                    brand, model, storage, ram, cores, camera,
                                    condition, defects, buyback_price, currency,
                                    data_origin, confidence_score, source_url, scraped_at
                                ) VALUES (
                                    %(brand)s, %(model)s, %(storage)s, %(ram)s, %(cores)s, %(camera)s,
                                    %(condition)s, %(defects)s, %(buyback_price)s, %(currency)s,
                                    %(data_origin)s, %(confidence_score)s, %(source_url)s, %(timestamp)s
                                );
                            """, {
                                "brand": rec.get("brand", "Unknown"),
                                "model": rec.get("model", "Unknown"),
                                "storage": rec.get("storage", ""),
                                "ram": rec.get("ram", ""),
                                "cores": rec.get("cores", ""),
                                "camera": rec.get("camera", ""),
                                "condition": rec.get("condition", "Grade A"),
                                "defects": rec.get("defects", "None"),
                                "buyback_price": rec.get("buyback_price", 0),
                                "currency": rec.get("currency", "INR"),
                                "data_origin": rec.get("data_origin", "verified_scraped"),
                                "confidence_score": rec.get("confidence_score", 1.0),
                                "source_url": rec.get("source_url", ""),
                                "timestamp": rec.get("timestamp"),
                            })
                        inserted_or_updated += 1
                        conn.commit()

            conn.commit()
            logger.info("Successfully upserted %d records to central DB mirror table.", inserted_or_updated)

            # Automatically ingest and sync all updated schema tables:
            # 1. scraper.interval_reports
            # 2. scraper.devices
            # 3. scraper.device_repair_exchange_costs
            # 4. scraper.cashify_buy_prices (Grades A through E)
            # 5. scraper.observations (paise minor amounts)
            # 6. scraper.market_prices (sell-side retail & renewed eCommerce)
            # 7. scraper.runs
            try:
                is_amazon = any(
                    "amazon" in str(r.get("source_url", "")).lower()
                    or "amazon" in str(r.get("data_origin", "")).lower()
                    or r.get("asin")
                    for r in records
                )
                if is_amazon:
                    self.ingest_amazon_data(records, conn=conn)
                else:
                    self.ingest_cashify_interval_data(records, conn=conn)
            except Exception as e:
                logger.warning("Could not ingest into updated schema tables via interval pipeline: %s", e)

            return inserted_or_updated

    def ingest_cashify_interval_data(
        self,
        records: List[Dict[str, Any]],
        executed_at: Optional[datetime] = None,
        interval_mins: int = 30,
        conn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Filters and formats Cashify scraping data according to the updated schema hierarchy:
        1. scraper.interval_reports (Execution tracking and bucket stats)
        2. scraper.devices (Canonical device specifications & variants)
        3. scraper.device_repair_exchange_costs (Component repair & retail exchange benchmarks)
        4. scraper.cashify_buy_prices (5 condition tiers: Grade A to Grade E with deductions)
        5. scraper.observations (Paise minor units observations for market analytics)
        6. scraper.runs (Execution run tracking)
        """
        if not records:
            return {"status": "empty", "devices_count": 0, "rows_added": 0}

        now_dt = executed_at or datetime.now()
        bucket_info = resolve_report_bucket(now_dt, interval_mins)
        report_id = bucket_info["report_id"]
        report_day = bucket_info["report_day"]
        report_time = bucket_info["report_time"]
        report_bucket = bucket_info["report_bucket"]

        # 1. Filter, deduplicate, and normalize unique canonical devices
        device_map: Dict[str, Dict[str, Any]] = {}
        for rec in records:
            brand = (rec.get("brand") or "Apple").strip().title()
            raw_model = rec.get("model") or "iPhone"
            clean_m = _clean_device_model(raw_model, brand)
            storage_str = rec.get("storage") or ""
            storage_gb = rec.get("storage_gb") or _parse_storage_gb(storage_str, raw_model, rec.get("source_url", ""))
            ram_str = rec.get("ram") or ""
            ram_gb = rec.get("ram_gb") or _parse_ram_gb(ram_str, raw_model, rec.get("source_url", ""))
            dev_id = rec.get("device_id") or _build_canonical_device_id(brand, clean_m, storage_gb)

            raw_price = rec.get("max_advertised_price") or rec.get("buyback_price") or rec.get("price") or 0
            price_val = int(float(raw_price))
            if price_val <= 0:
                continue

            if dev_id not in device_map or price_val > device_map[dev_id]["buyback_price"]:
                device_map[dev_id] = {
                    "brand": brand,
                    "model": clean_m,
                    "storage_gb": int(storage_gb),
                    "ram_gb": int(ram_gb) if ram_gb is not None else None,
                    "device_id": dev_id,
                    "max_advertised_price": price_val,
                    "buyback_price": price_val,
                    "source_url": rec.get("source_url", "https://www.cashify.in/sell-old-mobile-phone")
                }

        device_payload = list(device_map.values())
        if not device_payload:
            return {"status": "no_valid_devices", "devices_count": 0, "rows_added": 0}

        def _do_ingest(active_conn: Any) -> str:
            nonlocal report_id
            self.create_table_if_not_exists(active_conn)
            with active_conn.cursor() as cur:
                schema = self.db_schema
                if self.db_dialect == "postgresql":
                    cur.execute(f"SET search_path TO {schema}, public;")

                # Strategy A: Use PostgreSQL Stored Procedure scraper.ingest_cashify_interval_payload
                sp_succeeded = False
                if self.db_dialect == "postgresql":
                    try:
                        cur.execute(
                            "SELECT scraper.ingest_cashify_interval_payload(%s::jsonb, %s::timestamptz, %s);",
                            (json.dumps(device_payload), now_dt, interval_mins)
                        )
                        res = cur.fetchone()
                        if res and res[0]:
                            report_id = res[0]
                            active_conn.commit()
                            sp_succeeded = True
                            logger.info(
                                "Successfully ingested Cashify interval payload via DB procedure (Report ID: %s, Devices: %d)",
                                report_id, len(device_payload)
                            )
                    except Exception as sp_err:
                        active_conn.rollback()
                        logger.warning("Stored procedure ingestion fallback to direct parameterized SQL: %s", sp_err)

                # Strategy B: Direct Parameterized SQL Multi-Table Ingestion (Reliable Fallback)
                if not sp_succeeded:
                    run_id = f"cashify-interval-{report_id}"
                    devices_count = 0

                    for dev in device_payload:
                        b_brand = dev["brand"]
                        b_model = dev["model"]
                        b_storage = dev["storage_gb"]
                        b_ram = dev["ram_gb"]
                        b_id = dev["device_id"]
                        b_price = dev["buyback_price"]
                        b_url = dev["source_url"]
                        b_year = now_dt.year
                        b_series = _derive_model_series(b_brand, b_model)
                        b_variant = f"{b_ram} GB / {b_storage} GB" if b_ram else f"{b_storage} GB"

                        bench = _compute_repair_benchmarks(b_price)

                        if self.db_dialect == "postgresql":
                            # 1. Upsert scraper.devices
                            cur.execute("""
                                INSERT INTO devices (id, brand, model, storage_gb, ram_gb, release_year, report_id, report_day, report_time, report_bucket, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                  brand = EXCLUDED.brand,
                                  model = EXCLUDED.model,
                                  storage_gb = EXCLUDED.storage_gb,
                                  ram_gb = COALESCE(EXCLUDED.ram_gb, devices.ram_gb),
                                  report_id = EXCLUDED.report_id,
                                  report_day = EXCLUDED.report_day,
                                  report_time = EXCLUDED.report_time,
                                  report_bucket = EXCLUDED.report_bucket,
                                  updated_at = EXCLUDED.updated_at;
                            """, (b_id, b_brand, b_model, b_storage, b_ram, b_year, report_id, report_day, report_time, report_bucket, now_dt))

                            # 2. Upsert scraper.device_repair_exchange_costs
                            cur.execute("""
                                INSERT INTO device_repair_exchange_costs (
                                  device_id, brand, model, storage_gb, currency,
                                  oem_exchange_flawless, retail_exchange_good, exchange_cracked_grade,
                                  screen_repair_cost, battery_repair_cost, housing_backglass_cost,
                                  board_ic_repair_cost, minor_polish_qc_cost,
                                  report_id, report_day, report_time, report_bucket, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (device_id) DO UPDATE SET
                                  oem_exchange_flawless = EXCLUDED.oem_exchange_flawless,
                                  retail_exchange_good = EXCLUDED.retail_exchange_good,
                                  exchange_cracked_grade = EXCLUDED.exchange_cracked_grade,
                                  screen_repair_cost = EXCLUDED.screen_repair_cost,
                                  battery_repair_cost = EXCLUDED.battery_repair_cost,
                                  housing_backglass_cost = EXCLUDED.housing_backglass_cost,
                                  board_ic_repair_cost = EXCLUDED.board_ic_repair_cost,
                                  minor_polish_qc_cost = EXCLUDED.minor_polish_qc_cost,
                                  report_id = EXCLUDED.report_id,
                                  report_day = EXCLUDED.report_day,
                                  report_time = EXCLUDED.report_time,
                                  report_bucket = EXCLUDED.report_bucket,
                                  updated_at = EXCLUDED.updated_at;
                            """, (
                                b_id, b_brand, b_model, b_storage, "INR",
                                bench["oem_exchange_flawless"], bench["retail_exchange_good"], bench["exchange_cracked_grade"],
                                bench["screen_repair_cost"], bench["battery_repair_cost"], bench["housing_backglass_cost"],
                                bench["board_ic_repair_cost"], bench["minor_polish_qc_cost"],
                                report_id, report_day, report_time, report_bucket, now_dt
                            ))

                            # 3. Insert 5 condition grades into scraper.cashify_buy_prices
                            grades_data = [
                                ("Grade A", "Grade A", "Flawless condition, zero scratches (Repair cost: ₹0)", 0.0, float(b_price)),
                                ("Grade B", "Grade B", f"Minor signs of use · Est. QC/Polish cost: ₹{bench['minor_polish_qc_cost']}", float(bench["minor_polish_qc_cost"]), float(round(b_price * 0.88 / 100.0) * 100)),
                                ("Grade C", "Grade C", f"Aged battery / housing wear · Est. Battery+Housing repair: ₹{bench['battery_repair_cost'] + bench['housing_backglass_cost']}", float(bench["battery_repair_cost"] + bench["housing_backglass_cost"]), float(round(b_price * 0.72 / 100.0) * 100)),
                                ("Grade D", "Grade D", f"Cracked screen / display lines · Est. Screen replacement cost: ₹{bench['screen_repair_cost']}", float(bench["screen_repair_cost"]), float(round(b_price * 0.54 / 100.0) * 100)),
                                ("Grade E", "Grade E", f"Dead display + board issue · Est. Board+Screen repair cost: ₹{bench['board_ic_repair_cost']}", float(bench["board_ic_repair_cost"]), float(round(b_price * 0.35 / 100.0) * 100)),
                            ]

                            for cond_label, grade_code, defect_desc, deduction_val, grade_price in grades_data:
                                cur.execute("""
                                    INSERT INTO cashify_buy_prices (
                                      brand, model, model_series, variant, storage, ram,
                                      condition, condition_grade, defects,
                                      max_advertised_price, condition_deductions, buyback_price, price,
                                      currency, source_url, scraped_at,
                                      report_id, report_day, report_time, report_bucket
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                                """, (
                                    b_brand, b_model, b_series, b_variant, f"{b_storage} GB", f"{b_ram} GB" if b_ram else "",
                                    cond_label, grade_code, defect_desc,
                                    float(b_price), deduction_val, grade_price, grade_price,
                                    "INR", b_url, now_dt,
                                    report_id, report_day, report_time, report_bucket
                                ))

                                # 4. Insert into scraper.observations
                                cur.execute("""
                                    INSERT INTO observations (
                                      program_id, device_id, condition_label, amount_minor, currency,
                                      observed_at, run_id, source_url,
                                      report_id, report_day, report_time, report_bucket
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                                """, (
                                    "cashify-in", b_id, grade_code, int(grade_price * 100), "INR",
                                    now_dt, run_id, b_url,
                                    report_id, report_day, report_time, report_bucket
                                ))

                        devices_count += 1

                    if self.db_dialect == "postgresql":
                        # 5. Insert scraper.runs
                        cur.execute("""
                            INSERT INTO runs (
                              id, program_id, started_at, finished_at, status, captured, errors, quarantined, note,
                              report_id, report_day, report_time, report_bucket
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING;
                        """, (
                            run_id, "cashify-in", now_dt, now_dt, "succeeded", devices_count * 5, 0, 0,
                            f"Cashify Interval Scrape Ingestion · {report_bucket}",
                            report_id, report_day, report_time, report_bucket
                        ))

                        # 6. Insert scraper.interval_reports
                        cur.execute("""
                            INSERT INTO interval_reports (
                              report_id, report_day, report_time, report_bucket, interval_minutes,
                              source_feed, devices_processed, cashify_rows_added, observations_added, market_rows_added, status, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (report_id) DO NOTHING;
                        """, (
                            report_id, report_day, report_time, report_bucket, interval_mins,
                            "cashify-in", devices_count, devices_count * 5, devices_count * 5, 0, "completed", now_dt
                        ))

                    active_conn.commit()
                    logger.info("Direct SQL Ingestion completed: %d devices, %d quotes stored in schema tables.", devices_count, devices_count * 5)
            return report_id

        if conn is not None:
            _do_ingest(conn)
        else:
            with self.get_connection() as c:
                _do_ingest(c)

        return {
            "status": "success",
            "report_id": report_id,
            "report_bucket": report_bucket,
            "devices_processed": len(device_payload),
            "cashify_rows_added": len(device_payload) * 5,
            "observations_added": len(device_payload) * 5,
        }

    def ingest_amazon_data(
        self,
        records: List[Dict[str, Any]],
        executed_at: Optional[datetime] = None,
        interval_mins: int = 30,
        conn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Ingests scraped Amazon India retail and renewed mobile pricing data
        into the scraper schema hierarchy:
        1. scraper.devices (canonical device definitions)
        2. scraper.observations (normalized price observations, program_id = 'amazon-in')
        3. scraper.market_prices (sell-side retail/renewed market pricing)
        4. scraper.runs (execution tracking)
        5. scraper.interval_reports (aggregate report tracking, market_rows_added)
        """
        if not records:
            return {"status": "empty", "devices_count": 0, "rows_added": 0}

        now_dt = executed_at or datetime.now()
        bucket_info = resolve_report_bucket(now_dt, interval_mins)
        report_id = bucket_info["report_id"]
        report_day = bucket_info["report_day"]
        report_time = bucket_info["report_time"]
        report_bucket = bucket_info["report_bucket"]
        run_id = f"RUN-AMAZON-{now_dt.strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
        week_str = f"{now_dt.year}-W{now_dt.isocalendar()[1]:02d}"

        def _do_ingest_amazon(active_conn: Any):
            self.create_table_if_not_exists(active_conn)
            with active_conn.cursor() as cur:
                schema = self.db_schema
                if self.db_dialect == "postgresql":
                    cur.execute(f"SET search_path TO {schema}, public;")

                devices_seen = set()
                market_rows_added = 0
                obs_rows_added = 0

                for r in records:
                    brand = (r.get("brand") or "Unknown").strip().title()[:90]
                    raw_model = r.get("model") or "Device"
                    clean_m = _clean_device_model(raw_model, brand)[:80]
                    storage_str = r.get("storage") or ""
                    storage_gb = r.get("storage_gb") or _parse_storage_gb(storage_str, raw_model, r.get("source_url", ""))
                    ram_str = r.get("ram") or ""
                    ram_gb = r.get("ram_gb") or _parse_ram_gb(ram_str, raw_model, r.get("source_url", ""))
                    dev_id = (r.get("device_id") or _build_canonical_device_id(brand, clean_m, storage_gb))[:140].rstrip("-")

                    raw_price = r.get("price") or r.get("selling_price") or r.get("buyback_price") or 0
                    price_val = int(float(raw_price))
                    if price_val <= 0:
                        continue

                    is_renewed = bool(r.get("is_renewed"))
                    channel = "amazon-renewed" if is_renewed else "amazon"
                    cond_code = "Grade A" if is_renewed else "New"
                    amount_minor = price_val * 100
                    source_url = r.get("source_url", "https://www.amazon.in")

                    # 1. Upsert into scraper.devices
                    if dev_id not in devices_seen:
                        if self.db_dialect == "postgresql":
                            cur.execute("""
                                INSERT INTO devices (
                                    id, brand, model, storage_gb, ram_gb, release_year, aliases,
                                    report_id, report_day, report_time, report_bucket, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    model = EXCLUDED.model,
                                    ram_gb = COALESCE(EXCLUDED.ram_gb, devices.ram_gb),
                                    updated_at = EXCLUDED.updated_at,
                                    report_id = EXCLUDED.report_id,
                                    report_day = EXCLUDED.report_day,
                                    report_time = EXCLUDED.report_time,
                                    report_bucket = EXCLUDED.report_bucket;
                            """, (
                                dev_id, brand, clean_m, storage_gb, ram_gb, 2024,
                                f"{brand} {clean_m}", report_id, report_day, report_time, report_bucket, now_dt
                            ))
                        devices_seen.add(dev_id)

                    # 2. Insert into scraper.observations
                    cur.execute("""
                        INSERT INTO observations (
                            program_id, device_id, condition_label, amount_minor, currency,
                            observed_at, run_id, source_url,
                            report_id, report_day, report_time, report_bucket
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        "amazon-in", dev_id, cond_code, amount_minor, "INR",
                        now_dt, run_id, source_url,
                        report_id, report_day, report_time, report_bucket
                    ))
                    obs_rows_added += 1

                    # 3. Insert into scraper.market_prices
                    if self.db_dialect == "postgresql":
                        cur.execute("""
                            INSERT INTO market_prices (
                                device_id, market, channel, cond_lo, cond_hi, amount_minor, currency,
                                observed_at, sample_size, dispersion_pct, source, entered_by, week,
                                report_id, report_day, report_time, report_bucket
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """, (
                            dev_id, "IN", channel, cond_code, cond_code, amount_minor, "INR",
                            now_dt, 1, 0.0, "Amazon India", "amazon-scraper", week_str,
                            report_id, report_day, report_time, report_bucket
                        ))
                        market_rows_added += 1

                # 4. Insert into scraper.runs
                if self.db_dialect == "postgresql":
                    cur.execute("""
                        INSERT INTO runs (
                            id, program_id, started_at, finished_at, status, captured, errors, quarantined, note,
                            report_id, report_day, report_time, report_bucket
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING;
                    """, (
                        run_id, "amazon-in", now_dt, now_dt, "succeeded", market_rows_added, 0, 0,
                        f"Amazon India Ingestion · {report_bucket}",
                        report_id, report_day, report_time, report_bucket
                    ))

                    # 5. Insert or update interval_reports
                    cur.execute("""
                        INSERT INTO interval_reports (
                            report_id, report_day, report_time, report_bucket, interval_minutes,
                            source_feed, devices_processed, cashify_rows_added, observations_added, market_rows_added, status, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (report_id) DO UPDATE SET
                            devices_processed = interval_reports.devices_processed + EXCLUDED.devices_processed,
                            observations_added = interval_reports.observations_added + EXCLUDED.observations_added,
                            market_rows_added = interval_reports.market_rows_added + EXCLUDED.market_rows_added,
                            status = 'completed';
                    """, (
                        report_id, report_day, report_time, report_bucket, interval_mins,
                        "amazon-in", len(devices_seen), 0, obs_rows_added, market_rows_added, "completed", now_dt
                    ))

                active_conn.commit()
                logger.info(
                    "Amazon Ingestion completed: %d devices, %d market_prices, %d observations stored in scraper schema.",
                    len(devices_seen), market_rows_added, obs_rows_added
                )

        if conn is not None:
            _do_ingest_amazon(conn)
        else:
            with self.get_connection() as c:
                _do_ingest_amazon(c)

        return {
            "status": "success",
            "report_id": report_id,
            "report_bucket": report_bucket,
            "devices_processed": len(records),
        }

    # Aliases for convenience
    upsert_buy_records = upsert_records
    ingest_records = ingest_cashify_interval_data

    # =========================================================================
    # Refurbished Sell Prices Operations (Dedicated Sell Table)
    # =========================================================================

    def upsert_sell_records(self, records: List[Dict[str, Any]]) -> int:
        """Upsert refurbished records into the dedicated cashify_sell_prices table."""
        if not records:
            logger.warning("No refurbished sell records supplied for DB upsert.")
            return 0

        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            inserted_or_updated = 0

            with conn.cursor() as cur:
                schema = self.db_schema
                if self.db_dialect == "postgresql":
                    cur.execute(f"SET search_path TO {schema}, public;")

                is_pg = (self.db_dialect == "postgresql")

                for rec in records:
                    sku = rec.get("sku") or f"{rec.get('model')}-{rec.get('storage')}-{rec.get('color')}"
                    params = {
                        "brand": rec.get("brand", "Unknown"),
                        "model": rec.get("model", "Unknown"),
                        "model_series": rec.get("model_series", ""),
                        "variant": rec.get("variant", ""),
                        "storage": rec.get("storage", ""),
                        "ram": rec.get("ram", ""),
                        "color": rec.get("color", ""),
                        "network_type": rec.get("network_type", ""),
                        "is_refurbished": True,
                        "refurbished_mark": rec.get("refurbished_mark", "REFURBISHED"),
                        "refurbished_grade": rec.get("refurbished_grade", "Superb"),
                        "device_condition": rec.get("device_condition", "Refurbished - Superb"),
                        "selling_price": rec.get("selling_price", 0),
                        "original_mrp": rec.get("original_mrp"),
                        "discount_percent": rec.get("discount_percent"),
                        "warranty": rec.get("warranty", "6 Months Warranty, 15 Days Refund"),
                        "availability": rec.get("availability", "InStock"),
                        "sku": sku,
                        "currency": rec.get("currency", "INR"),
                        "source_url": rec.get("source_url", ""),
                        "timestamp": rec.get("timestamp") or datetime.utcnow().isoformat(),
                    }

                    try:
                        if is_pg:
                            cur.execute("""
                                INSERT INTO cashify_sell_prices (
                                    brand, model, model_series, variant, storage, ram, color, network_type,
                                    is_refurbished, refurbished_mark, refurbished_grade, device_condition,
                                    selling_price, original_mrp, discount_percent, warranty, availability,
                                    sku, currency, source_url, scraped_at
                                ) VALUES (
                                    %(brand)s, %(model)s, %(model_series)s, %(variant)s, %(storage)s, %(ram)s, %(color)s, %(network_type)s,
                                    %(is_refurbished)s, %(refurbished_mark)s, %(refurbished_grade)s, %(device_condition)s,
                                    %(selling_price)s, %(original_mrp)s, %(discount_percent)s, %(warranty)s, %(availability)s,
                                    %(sku)s, %(currency)s, %(source_url)s, %(timestamp)s
                                )
                                ON CONFLICT (source_url, sku, refurbished_grade) DO UPDATE SET
                                    selling_price = EXCLUDED.selling_price,
                                    original_mrp = EXCLUDED.original_mrp,
                                    discount_percent = EXCLUDED.discount_percent,
                                    warranty = EXCLUDED.warranty,
                                    availability = EXCLUDED.availability,
                                    is_refurbished = EXCLUDED.is_refurbished,
                                    refurbished_mark = EXCLUDED.refurbished_mark,
                                    device_condition = EXCLUDED.device_condition,
                                    scraped_at = EXCLUDED.scraped_at;
                            """, params)
                        else:
                            cur.execute("""
                                INSERT INTO cashify_sell_prices (
                                    brand, model, model_series, variant, storage, ram, color, network_type,
                                    is_refurbished, refurbished_mark, refurbished_grade, device_condition,
                                    selling_price, original_mrp, discount_percent, warranty, availability,
                                    sku, currency, source_url, scraped_at
                                ) VALUES (
                                    :brand, :model, :model_series, :variant, :storage, :ram, :color, :network_type,
                                    :is_refurbished, :refurbished_mark, :refurbished_grade, :device_condition,
                                    :selling_price, :original_mrp, :discount_percent, :warranty, :availability,
                                    :sku, :currency, :source_url, :timestamp
                                )
                                ON CONFLICT (source_url, sku, refurbished_grade) DO UPDATE SET
                                    selling_price = excluded.selling_price,
                                    original_mrp = excluded.original_mrp,
                                    discount_percent = excluded.discount_percent,
                                    warranty = excluded.warranty,
                                    availability = excluded.availability,
                                    scraped_at = excluded.scraped_at;
                            """, params)
                        inserted_or_updated += 1
                    except Exception as e:
                        logger.error("Error upserting sell record %s: %s", params.get("model"), e)
                        if is_pg:
                            conn.rollback()

                conn.commit()
            logger.info("Successfully upserted %d refurbished sell records into cashify_sell_prices.", inserted_or_updated)
            return inserted_or_updated

    def get_buy_prices(self, limit: int = 500, brand: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch records from cashify_buy_prices (or fallback to mobile_buyback_pricing)."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                if self.db_dialect == "postgresql":
                    cur.execute(f"SET search_path TO {schema}, public;")

                # Try cashify_buy_prices first, fallback to mobile_buyback_pricing if empty
                target_table = "cashify_buy_prices"
                cur.execute(f"SELECT COUNT(*) FROM {target_table};")
                count = cur.fetchone()[0]
                if count == 0:
                    target_table = "mobile_buyback_pricing"

                is_pg = (self.db_dialect == "postgresql")
                placeholder = "%s" if is_pg else "?"

                if brand:
                    query = f"SELECT * FROM {target_table} WHERE brand ILIKE {placeholder} ORDER BY brand, model, storage LIMIT {placeholder};" if is_pg else f"SELECT * FROM {target_table} WHERE LOWER(brand) = LOWER({placeholder}) ORDER BY brand, model, storage LIMIT {placeholder};"
                    cur.execute(query, (brand, limit))
                else:
                    query = f"SELECT * FROM {target_table} ORDER BY brand, model, storage LIMIT {placeholder};"
                    cur.execute(query, (limit,))

                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def get_sell_prices(self, limit: int = 500, brand: Optional[str] = None, grade: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch records from the dedicated refurbished cashify_sell_prices table."""
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                if self.db_dialect == "postgresql":
                    cur.execute(f"SET search_path TO {schema}, public;")

                is_pg = (self.db_dialect == "postgresql")
                placeholder = "%s" if is_pg else "?"

                conditions = ["1=1"]
                params = []

                if brand:
                    conditions.append(f"brand ILIKE {placeholder}" if is_pg else f"LOWER(brand) = LOWER({placeholder})")
                    params.append(brand)
                if grade:
                    conditions.append(f"refurbished_grade ILIKE {placeholder}" if is_pg else f"LOWER(refurbished_grade) = LOWER({placeholder})")
                    params.append(grade)

                params.append(limit)
                query = f"SELECT * FROM cashify_sell_prices WHERE {' AND '.join(conditions)} ORDER BY brand, model, selling_price ASC LIMIT {placeholder};"
                cur.execute(query, tuple(params))
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def get_price_intelligence_comparison(self, brand: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Compare Buy prices vs Refurbished Sell prices to determine Cashify's Gross Profit Margin.
        Margin = Refurbished Sell Price - Buyback Purchase Price
        """
        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            with conn.cursor() as cur:
                schema = self.db_schema
                if self.db_dialect == "postgresql":
                    cur.execute(f"SET search_path TO {schema}, public;")

                # Match by brand and model
                query = """
                SELECT 
                    s.brand,
                    s.model,
                    s.storage,
                    s.refurbished_grade,
                    s.is_refurbished,
                    s.refurbished_mark,
                    b.buyback_price AS cashify_buy_price,
                    s.selling_price AS cashify_sell_price,
                    s.original_mrp,
                    (s.selling_price - b.buyback_price) AS gross_margin,
                    ROUND(((s.selling_price - b.buyback_price) / NULLIF(b.buyback_price, 0)) * 100, 1) AS margin_percentage,
                    s.warranty,
                    s.source_url AS sell_url,
                    b.source_url AS buy_url
                FROM cashify_sell_prices s
                JOIN mobile_buyback_pricing b 
                  ON LOWER(s.brand) = LOWER(b.brand) 
                 AND LOWER(s.model) = LOWER(b.model)
                ORDER BY gross_margin DESC;
                """
                try:
                    cur.execute(query)
                    cols = [desc[0] for desc in cur.description]
                    return [dict(zip(cols, r)) for r in cur.fetchall()]
                except Exception as e:
                    logger.warning("Could not execute margin comparison query: %s", e)
                    return []


if __name__ == "__main__":
    db = DatabaseManager()
    print("Testing multi-source platform schema setup...")
    with db.get_connection() as conn:
        db.create_table_if_not_exists(conn)
    seeded = db.seed_default_sources_if_empty()
    sources = db.get_sources()
    stats = db.get_platform_analytics()
    print(f"Total Sources Registered: {len(sources)}")
    print(f"Platform Analytics: {stats}")
