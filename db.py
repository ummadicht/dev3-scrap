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

    def start_tunnel(self) -> int:
        """Starts the SSH tunnel and returns the local assigned port."""
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
        local_port = self._tunnel.local_bind_port
        logger.info("SSH tunnel established. Local forwarded port: %d", local_port)
        return local_port

    def stop_tunnel(self) -> None:
        """Closes the active SSH tunnel."""
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
                if self.database_url and not use_tunnel:
                    conn = psycopg2.connect(self.database_url)
                else:
                    conn = psycopg2.connect(
                        host=target_host,
                        port=target_port,
                        dbname=self.db_name,
                        user=self.db_user,
                        password=self.db_password,
                    )
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
                cur.execute(f"SET search_path TO {schema}, public;")
                # Fast existence check: If scraping_sources already exists, skip DDL to avoid ownership issues
                try:
                    cur.execute("""
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'scraping_sources' 
                        AND (table_schema = %s OR table_schema = 'public')
                        LIMIT 1;
                    """, (schema,))
                    if cur.fetchone() is not None:
                        return
                except Exception:
                    pass

                if schema and schema != "public":
                    try:
                        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
                        cur.execute(f"GRANT ALL ON SCHEMA {schema} TO PUBLIC;")
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
        """Populates scraping_sources from TARGET_DEVICES and DEFAULT_API_SOURCES if not already present."""
        from config import TARGET_DEVICES, DEFAULT_API_SOURCES

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
            return inserted_or_updated


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
