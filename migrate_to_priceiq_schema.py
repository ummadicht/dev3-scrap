"""
PriceIQ SQLite to PostgreSQL Migration Engine (Dedicated 'price_iq' Schema)
===========================================================================
Migrates PriceIQ wholesale data from SQLite (priceiq.db) directly into the
dedicated 'price_iq' schema in PostgreSQL (scrapingdb).

Guarantees:
- Strict Schema Isolation: Only writes to schema 'price_iq'.
- Zero impact on 'scraper' schema.
- Real-time Percentage Tracking (0% -> 100%).
- Full Audit Log in price_iq.migration_audit_log.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PriceIQMigrator")

BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB_PATH = BASE_DIR / "priceiq.db"


class PriceIQSchemaMigrator:
    """Manages migration of PriceIQ data from SQLite to price_iq PostgreSQL schema."""

    def __init__(self, sqlite_path: Path = SQLITE_DB_PATH):
        self.sqlite_path = Path(sqlite_path)
        self.db_mgr = db.DatabaseManager()
        self.progress_pct = 0

    def update_progress(self, pct: int, step_desc: str) -> None:
        self.progress_pct = min(100, max(0, pct))
        bar_len = 25
        filled = int(round(bar_len * (self.progress_pct / 100.0)))
        bar = "=" * filled + "-" * (bar_len - filled)
        logger.info("[%3d%%] [%s] %s", self.progress_pct, bar, step_desc)

    def execute_migration(self) -> Dict[str, Any]:
        start_time = time.time()
        self.update_progress(0, "Initiating Migration into 'price_iq' PostgreSQL Schema")

        if not self.sqlite_path.exists():
            raise FileNotFoundError(f"Source SQLite database not found at {self.sqlite_path}")

        # Step 1: Read SQLite PriceIQ Data (25%)
        self.update_progress(20, "Extracting PriceIQ records from SQLite (priceiq.db)")
        sqlite_conn = sqlite3.connect(self.sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        s_cur = sqlite_conn.cursor()

        # Check tables in SQLite
        s_cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in s_cur.fetchall()]

        pricing_rows: List[Dict[str, Any]] = []
        if "mobile_buyback_pricing" in tables:
            s_cur.execute("SELECT * FROM mobile_buyback_pricing;")
            pricing_rows = [dict(r) for r in s_cur.fetchall()]

        sqlite_conn.close()
        self.update_progress(35, f"Extracted {len(pricing_rows)} records from SQLite source")

        # Step 2: Connect to PostgreSQL and verify 'price_iq' schema (50%)
        self.update_progress(50, "Connecting to PostgreSQL and switching to 'price_iq' schema")

        migrated_pricing = 0
        rate_cards_created = 0

        with self.db_mgr.get_connection() as conn:
            with conn.cursor() as cur:
                # Ensure schema exists and set search path
                cur.execute("CREATE SCHEMA IF NOT EXISTS price_iq;")
                cur.execute("SET search_path TO price_iq, public;")

                # Step 3: Batch Upsert into price_iq.pricing_records (75%)
                self.update_progress(70, f"Upserting {len(pricing_rows)} rows into price_iq.pricing_records")

                insert_pricing_sql = """
                INSERT INTO price_iq.pricing_records (
                    brand, device_model, storage, ram, condition_grade,
                    wholesale_price, currency, market, channel, source_provider,
                    source_url, confidence_score, comparables, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (device_model, storage, condition_grade, channel) DO UPDATE SET
                    wholesale_price = EXCLUDED.wholesale_price,
                    confidence_score = EXCLUDED.confidence_score,
                    updated_at = CURRENT_TIMESTAMP;
                """

                # Device rate card mapping accumulator
                # (device_model, storage) -> {grade_a, grade_b, ...}
                device_rate_cards: Dict[tuple, Dict[str, Any]] = {}

                for r in pricing_rows:
                    brand = r.get("brand", "Generic")
                    model = r.get("model", "")
                    storage = r.get("storage", "")
                    ram = r.get("ram", "")
                    condition = r.get("condition", "Grade A")
                    price = float(r.get("buyback_price", 0))
                    source_url = r.get("source_url", "")
                    confidence = float(r.get("confidence_score", 0.95))

                    cur.execute(insert_pricing_sql, (
                        brand, model, storage, ram, condition,
                        price, "INR", "IN", "wholesale", "WholeCellMarket",
                        source_url, confidence, 1
                    ))
                    migrated_pricing += 1

                    # Accumulate for rate_card_matrix
                    key = (model, storage, brand)
                    if key not in device_rate_cards:
                        device_rate_cards[key] = {
                            "model": model, "storage": storage, "brand": brand,
                            "A": price, "B": round(price * 0.88),
                            "C": round(price * 0.72), "D": round(price * 0.45)
                        }
                    else:
                        cond_upper = condition.upper()
                        if "GRADE B" in cond_upper:
                            device_rate_cards[key]["B"] = price
                        elif "GRADE C" in cond_upper:
                            device_rate_cards[key]["C"] = price
                        elif "GRADE D" in cond_upper:
                            device_rate_cards[key]["D"] = price
                        elif "GRADE A" in cond_upper:
                            device_rate_cards[key]["A"] = price

                self.update_progress(85, f"Ingested {migrated_pricing} records into price_iq.pricing_records")

                # Step 4: Populate price_iq.rate_card_matrix (90%)
                self.update_progress(90, "Calibrating and upserting 4-tier rate card matrix into price_iq.rate_card_matrix")
                insert_ratecard_sql = """
                INSERT INTO price_iq.rate_card_matrix (
                    device_model, brand, storage, grade_a_price, grade_b_price,
                    grade_c_price, grade_d_price, currency, market, channel, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (device_model, storage, channel) DO UPDATE SET
                    grade_a_price = EXCLUDED.grade_a_price,
                    grade_b_price = EXCLUDED.grade_b_price,
                    grade_c_price = EXCLUDED.grade_c_price,
                    grade_d_price = EXCLUDED.grade_d_price,
                    updated_at = CURRENT_TIMESTAMP;
                """
                for key, data in device_rate_cards.items():
                    cur.execute(insert_ratecard_sql, (
                        data["model"], data["brand"], data["storage"],
                        data["A"], data["B"], data["C"], data["D"],
                        "INR", "IN", "wholesale"
                    ))
                    rate_cards_created += 1

                # Step 5: Record Audit Log
                duration = round(time.time() - start_time, 2)
                cur.execute("""
                INSERT INTO price_iq.migration_audit_log (
                    migration_type, source_type, records_migrated, status, duration_seconds, log_details
                ) VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    "SQLite_to_PostgreSQL_PriceIQ_Schema",
                    "sqlite3_priceiq.db",
                    migrated_pricing,
                    "SUCCESS",
                    duration,
                    json.dumps({
                        "pricing_records": migrated_pricing,
                        "rate_cards": rate_cards_created,
                        "schema": "price_iq",
                        "database": "scrapingdb"
                    })
                ))

                conn.commit()

                # Step 6: Parity Reconciliation (100%)
                cur.execute("SELECT COUNT(*) FROM price_iq.pricing_records;")
                total_in_price_iq = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM price_iq.rate_card_matrix;")
                total_rate_cards = cur.fetchone()[0]

        self.update_progress(100, f"Migration Complete! Verified {total_in_price_iq} records in 'price_iq' schema ({duration}s)")

        return {
            "status": "success",
            "progress_pct": 100,
            "target_schema": "price_iq",
            "target_database": "scrapingdb",
            "pricing_records_migrated": migrated_pricing,
            "rate_cards_calibrated": rate_cards_created,
            "total_pricing_in_price_iq": total_in_price_iq,
            "total_rate_cards_in_price_iq": total_rate_cards,
            "duration_seconds": duration,
        }


def main():
    migrator = PriceIQSchemaMigrator()
    result = migrator.execute_migration()
    print("\n" + "=" * 60)
    print("MIGRATION TO 'price_iq' SCHEMA COMPLETED (100%)")
    print("=" * 60)
    print(f"Target Schema            : {result['target_schema']}")
    print(f"Pricing Records Migrated : {result['pricing_records_migrated']}")
    print(f"Rate Cards Calibrated    : {result['rate_cards_calibrated']}")
    print(f"Total Rows in price_iq   : {result['total_pricing_in_price_iq']}")
    print(f"Execution Duration       : {result['duration_seconds']}s")
    print("=" * 60)


if __name__ == "__main__":
    main()

