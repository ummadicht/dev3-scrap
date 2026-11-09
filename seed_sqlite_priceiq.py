"""
Seed PriceIQ Wholesale Data into local SQLite Database (priceiq.db)
===================================================================
Creates and populates priceiq.db with PriceIQ wholesale mobile buyback
intelligence and sources for local testing, staging, and migration.
"""

import json
import logging
import re
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SeedSQLitePriceIQ")

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "priceiq.db"
OUTPUT_JSON = BASE_DIR / "output.json"


def seed_sqlite_db(db_path: Path = DB_PATH) -> int:
    logger.info("Initializing SQLite database at: %s", db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Create tables
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
    CREATE TABLE IF NOT EXISTS priceiq_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device TEXT NOT NULL,
        brand TEXT NOT NULL,
        storage TEXT,
        condition_grade TEXT,
        price REAL NOT NULL,
        market TEXT DEFAULT 'IN',
        channel TEXT DEFAULT 'wholesale',
        source TEXT DEFAULT 'WholeCellMarket',
        comparables INT DEFAULT 1,
        source_url TEXT,
        synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (device, condition_grade, channel)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scraping_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Smartphones',
        bucket_name TEXT NOT NULL,
        target_url TEXT NOT NULL,
        http_method TEXT NOT NULL DEFAULT 'GET',
        headers_json TEXT DEFAULT '{}',
        auth_config_json TEXT DEFAULT '{}',
        params_json TEXT DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        UNIQUE (target_url)
    );
    """)

    # 2. Populate from output.json
    records = []
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            records = json.load(f)

    # Filter/Prioritize PriceIQ & Wholesale records
    inserted_pricing = 0
    inserted_priceiq = 0

    for r in records:
        brand = r.get("brand", "Generic")
        model = r.get("model", "")
        storage = r.get("storage", "")
        condition = r.get("condition", "Grade A")
        price = float(r.get("buyback_price", 0))
        source_url = r.get("source_url", "")
        origin = r.get("data_origin", "wholesale_api_feed")
        confidence = float(r.get("confidence_score", 0.95))

        cur.execute("""
        INSERT INTO mobile_buyback_pricing (
            brand, model, storage, ram, cores, camera, condition, defects,
            buyback_price, currency, data_origin, confidence_score, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source_url, storage, condition) DO UPDATE SET
            buyback_price = excluded.buyback_price,
            data_origin = excluded.data_origin,
            confidence_score = excluded.confidence_score;
        """, (
            brand, model, storage, r.get("ram", ""), r.get("cores", ""),
            r.get("camera", ""), condition, r.get("defects", "None"),
            price, r.get("currency", "INR"), origin, confidence, source_url
        ))
        inserted_pricing += 1

        # Also populate priceiq_prices table
        grade = "Grade A" if "A" in condition.upper() else ("Grade B" if "B" in condition.upper() else condition)
        cur.execute("""
        INSERT INTO priceiq_prices (
            device, brand, storage, condition_grade, price, market, channel, source, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (device, condition_grade, channel) DO UPDATE SET
            price = excluded.price,
            synced_at = CURRENT_TIMESTAMP;
        """, (
            model, brand, storage, grade, price, "IN", "wholesale", "WholeCellMarket", source_url
        ))
        inserted_priceiq += 1

    # 3. Add default Scraping Sources
    cur.execute("""
    INSERT INTO scraping_sources (name, source_type, category, bucket_name, target_url, http_method)
    VALUES 
        ('WholeCellMarket - Wholesale PriceIQ B2B API', 'rest_api', 'Smartphones', 'wholecell_wholesale', '/source/wholecellmarket/apple-iphone-13-4-gb-128-gb', 'POST'),
        ('Cashify Buyback Scraper', 'website_cashify', 'Smartphones', 'cashify_buyback', 'https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-13-4-gb-128-gb', 'GET'),
        ('BackMarket Buyback API', 'rest_api', 'Refurbished Trade-In', 'backmarket_buyback', 'https://www.backmarket.com', 'GET'),
        ('SellCell Global Comparison API', 'rest_api', 'Smartphones', 'sellcell_prices', 'https://www.sellcell.com', 'GET')
    ON CONFLICT (target_url) DO NOTHING;
    """)

    conn.commit()
    conn.close()

    logger.info("Successfully seeded SQLite database priceiq.db (%d pricing records, %d PriceIQ records).",
                inserted_pricing, inserted_priceiq)
    return inserted_pricing


if __name__ == "__main__":
    seed_sqlite_db()

