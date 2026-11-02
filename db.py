"""
Database Connection & SSH Tunnel Manager
========================================
Manages secure SSH tunneling to host 40.192.21.98 (user: tunneluser)
and syncs mobile pricing intelligence records directly into the central SQL database.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv

# Load .env variables if present
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("DBManager")


class DatabaseManager:
    """Manages SSH tunnel and database operations for Mobile Scraping intelligence."""

    def __init__(
        self,
        ssh_host: str = "40.192.21.98",
        ssh_port: int = 22,
        ssh_username: str = "tunneluser",
        ssh_pkey_path: Optional[str] = None,
        db_dialect: str = "postgresql",  # "postgresql" or "mysql"
        db_name: str = "mobile_pricing",
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
        db_host: str = "127.0.0.1",
        db_remote_port: Optional[int] = None,
    ):
        self.ssh_host = os.getenv("SSH_HOST", ssh_host)
        self.ssh_port = int(os.getenv("SSH_PORT", ssh_port))
        self.ssh_username = os.getenv("SSH_USERNAME", ssh_username)
        self.ssh_pkey_path = os.getenv("SSH_PRIVATE_KEY_PATH", ssh_pkey_path or "./tunnel_key.pem")

        self.db_dialect = os.getenv("DB_DIALECT", db_dialect).lower()
        self.db_name = os.getenv("DB_NAME", db_name)
        self.db_user = os.getenv("DB_USERNAME", db_user or "")
        self.db_password = os.getenv("DB_PASSWORD", db_password or "")
        self.db_host = os.getenv("DB_HOST", db_host)

        default_port = 5432 if self.db_dialect == "postgresql" else 3306
        self.db_remote_port = int(os.getenv("DB_PORT", db_remote_port or default_port))

        self._tunnel = None

    def start_tunnel(self) -> int:
        """Starts the SSH tunnel and returns the local assigned port."""
        from sshtunnel import SSHTunnelForwarder

        pkey_path = Path(self.ssh_pkey_path).resolve()
        if not pkey_path.exists():
            raise FileNotFoundError(
                f"SSH private key file not found at: {pkey_path}. "
                f"Please place the private key file and update SSH_PRIVATE_KEY_PATH in .env"
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
        """Context manager providing an active database connection over the tunnel."""
        local_port = self.start_tunnel()
        conn = None
        try:
            if self.db_dialect == "postgresql":
                import psycopg2
                conn = psycopg2.connect(
                    host="127.0.0.1",
                    port=local_port,
                    dbname=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                )
            elif self.db_dialect == "mysql":
                import pymysql
                conn = pymysql.connect(
                    host="127.0.0.1",
                    port=local_port,
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
            self.stop_tunnel()

    def create_table_if_not_exists(self, conn: Any) -> None:
        """Ensures the mobile_buyback_pricing table exists."""
        if self.db_dialect == "postgresql":
            ddl = """
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
            """
        else:  # MySQL
            ddl = """
            CREATE TABLE IF NOT EXISTS mobile_buyback_pricing (
                id INT AUTO_INCREMENT PRIMARY KEY,
                brand VARCHAR(50) NOT NULL,
                model VARCHAR(200) NOT NULL,
                storage VARCHAR(50),
                ram VARCHAR(50),
                cores VARCHAR(50),
                camera VARCHAR(100),
                condition_grade VARCHAR(255) NOT NULL,
                defects TEXT,
                buyback_price DECIMAL(10, 2) NOT NULL,
                currency VARCHAR(10) DEFAULT 'INR',
                data_origin VARCHAR(50),
                confidence_score DECIMAL(3, 2),
                source_url VARCHAR(500) NOT NULL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_device (source_url(255), storage, condition_grade(100)),
                INDEX idx_brand_model (brand, model(100))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """

        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        logger.info("Table schema verified in database.")

    def upsert_records(self, records: List[Dict[str, Any]]) -> int:
        """Upsert scraped and condition-graded records into the database."""
        if not records:
            logger.warning("No records supplied for DB upsert.")
            return 0

        with self.get_connection() as conn:
            self.create_table_if_not_exists(conn)
            inserted_or_updated = 0

            with conn.cursor() as cur:
                if self.db_dialect == "postgresql":
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
                else:  # MySQL
                    query = """
                    INSERT INTO mobile_buyback_pricing (
                        brand, model, storage, ram, cores, camera,
                        condition_grade, defects, buyback_price, currency,
                        data_origin, confidence_score, source_url, scraped_at
                    ) VALUES (
                        %(brand)s, %(model)s, %(storage)s, %(ram)s, %(cores)s, %(camera)s,
                        %(condition)s, %(defects)s, %(buyback_price)s, %(currency)s,
                        %(data_origin)s, %(confidence_score)s, %(source_url)s, %(timestamp)s
                    )
                    ON DUPLICATE KEY UPDATE
                        buyback_price = VALUES(buyback_price),
                        ram = VALUES(ram),
                        cores = VALUES(cores),
                        camera = VALUES(camera),
                        defects = VALUES(defects),
                        data_origin = VALUES(data_origin),
                        confidence_score = VALUES(confidence_score),
                        scraped_at = VALUES(scraped_at);
                    """

                for rec in records:
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

            conn.commit()
            logger.info("Successfully upserted %d records to central DB.", inserted_or_updated)
            return inserted_or_updated


if __name__ == "__main__":
    db = DatabaseManager()
    print("DatabaseManager configured successfully.")
    print(f"Target SSH: {db.ssh_username}@{db.ssh_host}:{db.ssh_port}")
    print(f"Key Path: {db.ssh_pkey_path}")
    print(f"Dialect: {db.db_dialect}, Remote Port: {db.db_remote_port}")
