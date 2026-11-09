"""
PostgreSQL Schema Setup: Dedicated 'price_iq' Schema
====================================================
Creates and provisions the isolated 'price_iq' schema in PostgreSQL (scrapingdb)
for the PriceIQ engine, completely decoupled from the 'scraper' schema.
"""

import logging
import time
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PriceIQSchemaSetup")

def setup_price_iq_schema() -> dict:
    logger.info("Connecting to PostgreSQL to provision 'price_iq' schema...")
    db_mgr = db.DatabaseManager()
    
    with db_mgr.get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Create dedicated schema
            cur.execute("CREATE SCHEMA IF NOT EXISTS price_iq;")
            cur.execute("GRANT ALL ON SCHEMA price_iq TO PUBLIC;")
            cur.execute("SET search_path TO price_iq, public;")

            # 2. Table: price_iq.pricing_records
            # Holds normalized wholesale mobile buyback quotes directly for PriceIQ
            cur.execute("""
            CREATE TABLE IF NOT EXISTS price_iq.pricing_records (
                id SERIAL PRIMARY KEY,
                brand VARCHAR(100) NOT NULL,
                device_model VARCHAR(255) NOT NULL,
                storage VARCHAR(50),
                ram VARCHAR(50),
                condition_grade VARCHAR(100) NOT NULL,
                wholesale_price NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(10) DEFAULT 'INR',
                market VARCHAR(20) DEFAULT 'IN',
                channel VARCHAR(50) DEFAULT 'wholesale',
                source_provider VARCHAR(100) DEFAULT 'WholeCellMarket',
                source_url TEXT,
                confidence_score NUMERIC(3, 2) DEFAULT 0.95,
                comparables INT DEFAULT 1,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_priceiq_device_grade_storage UNIQUE (device_model, storage, condition_grade, channel)
            );
            CREATE INDEX IF NOT EXISTS idx_priceiq_device ON price_iq.pricing_records (device_model);
            CREATE INDEX IF NOT EXISTS idx_priceiq_brand ON price_iq.pricing_records (brand);
            """)

            # 3. Table: price_iq.rate_card_matrix
            # Holds standardized 4-tier condition grading matrix for Rate Card uploads
            cur.execute("""
            CREATE TABLE IF NOT EXISTS price_iq.rate_card_matrix (
                id SERIAL PRIMARY KEY,
                device_model VARCHAR(255) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                storage VARCHAR(50),
                grade_a_price NUMERIC(10, 2) NOT NULL,
                grade_b_price NUMERIC(10, 2) NOT NULL,
                grade_c_price NUMERIC(10, 2) NOT NULL,
                grade_d_price NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(10) DEFAULT 'INR',
                market VARCHAR(20) DEFAULT 'IN',
                channel VARCHAR(50) DEFAULT 'wholesale',
                uploaded_to_portal BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_priceiq_ratecard_device UNIQUE (device_model, storage, channel)
            );
            """)

            # 4. Table: price_iq.migration_audit_log
            # Tracks every migration run, timestamp, row counts, and status
            cur.execute("""
            CREATE TABLE IF NOT EXISTS price_iq.migration_audit_log (
                id SERIAL PRIMARY KEY,
                migration_type VARCHAR(100) NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                records_migrated INT DEFAULT 0,
                status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
                duration_seconds NUMERIC(6, 2) DEFAULT 0.0,
                log_details JSONB DEFAULT '{}'::jsonb,
                executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)

            conn.commit()

            # Verify schema and tables
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'price_iq'
                ORDER BY table_name;
            """)
            created_tables = [r[0] for r in cur.fetchall()]

    logger.info("Successfully provisioned 'price_iq' schema in PostgreSQL.")
    logger.info("Tables created in 'price_iq': %s", ", ".join(created_tables))
    return {
        "status": "success",
        "schema": "price_iq",
        "tables": created_tables,
    }

if __name__ == "__main__":
    setup_price_iq_schema()

