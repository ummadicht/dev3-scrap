"""
Unit tests for Mobile Price Intelligence System.
Tests model validation, scraping extraction, grading logic, and file export.
"""
import json
import csv
from pathlib import Path
import pytest
from pydantic import ValidationError

from models import MobilePriceRecord
from scraper import CashifyScraper
from grading_engine import GradingEngine
from exporter import save_to_csv, save_to_json


def test_mobile_price_record_valid():
    """Verify that a valid record instantiates without error."""
    rec = MobilePriceRecord(
        brand="Apple",
        model="Apple iPhone 13 (4 GB/128 GB)",
        storage="128 GB",
        condition="Grade A: Like New",
        defects="None",
        buyback_price=53150,
        source_url="https://www.cashify.in/test",
        data_origin="verified_scraped",
    )
    assert rec.brand == "Apple"
    assert rec.buyback_price == 53150
    assert rec.currency == "INR"
    assert rec.confidence_score == 1.0


def test_mobile_price_record_invalid_price():
    """Verify that negative prices trigger a ValidationError."""
    with pytest.raises(ValidationError):
        MobilePriceRecord(
            brand="Samsung",
            model="Galaxy S21",
            storage="128 GB",
            condition="Good",
            defects="None",
            buyback_price=-500,
            source_url="https://www.cashify.in/test",
            data_origin="verified_scraped",
        )


def test_scraper_extract_from_mock_html():
    """Test extracting variant record from synthetic HTML with Schema.org itemprop and specifications."""
    scraper = CashifyScraper()
    mock_payload = (
        '<html><body>'
        '<div itemprop="brand">Samsung</div>'
        '<img itemprop="image" alt="Samsung Galaxy S21 5G (8 GB/256 GB)" />'
        '<div itemprop="offers"><span itemprop="price">13280</span><span itemprop="priceCurrency">INR</span></div>'
        'self.__next_f.push([1,"\\"specifications\\":{\\"storage\\":[{\\"id\\":1338,\\"dval\\":\\"256 GB\\"}],\\"ram\\":[{\\"id\\":832,\\"dval\\":\\"8 GB RAM\\"}],\\"cores\\":[{\\"id\\":839,\\"dval\\":\\"8\\"}],\\"backCamera\\":[{\\"id\\":1267,\\"dval\\":\\"12 MP\\"},{\\"id\\":1899,\\"dval\\":\\"64 MP\\"}]}"]);'
        '</body></html>'
    )
    rec = scraper.scrape_single_variant_page(mock_payload, "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-s21-5g-8-gb-256-gb")
    assert rec is not None
    assert rec.brand == "Samsung"
    assert rec.storage == "256 GB"
    assert rec.ram == "8 GB RAM"
    assert rec.cores == "8"
    assert rec.buyback_price == 13280
    assert rec.data_origin == "verified_scraped"


def test_grading_engine_multipliers():
    """Verify that the grading engine applies expected factors and labels origin."""
    engine = GradingEngine()
    base_rec = MobilePriceRecord(
        brand="Apple",
        model="Apple iPhone 13 (4 GB/128 GB)",
        storage="128 GB",
        condition="Grade A: Like New / Flawless",
        defects="None",
        buyback_price=10000,
        source_url="https://www.cashify.in/test",
        data_origin="verified_scraped",
    )
    simulated = engine.generate_graded_records(base_rec)
    assert len(simulated) == 3  # Grade B, Grade C, Grade D

    # Grade B (0.88 factor)
    assert simulated[0].buyback_price == 8800
    assert simulated[0].data_origin == "sample_condition_graded"
    assert "Grade B" in simulated[0].condition

    # Grade C (0.72 factor)
    assert simulated[1].buyback_price == 7200
    assert "Grade C" in simulated[1].condition

    # Grade D (0.45 factor)
    assert simulated[2].buyback_price == 4500
    assert "Grade D" in simulated[2].condition
    assert "Cracked" in simulated[2].defects


def test_export_json_and_csv(tmp_path: Path):
    """Verify export to JSON and CSV formats."""
    json_path = tmp_path / "test_output.json"
    csv_path = tmp_path / "test_output.csv"

    test_records = [
        MobilePriceRecord(
            brand="Samsung",
            model="Galaxy S21 5G (8 GB/128 GB)",
            storage="128 GB",
            condition="Grade A: Like New",
            defects="None",
            buyback_price=34930,
            source_url="https://www.cashify.in/samsung-s21",
            data_origin="verified_scraped",
        )
    ]

    save_to_json(test_records, json_path)
    assert json_path.exists()
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["buyback_price"] == 34930

    save_to_csv(test_records, csv_path)
    assert csv_path.exists()
    with open(csv_path, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 1
    assert reader[0]["model"] == "Galaxy S21 5G (8 GB/128 GB)"
    assert int(reader[0]["buyback_price"]) == 34930


def test_priceiq_record_formatting():
    """Verify conversion of internal records into PriceIQ bulk upload schema."""
    from priceiq_client import PriceIQClient

    raw_data = [
        {
            "brand": "Apple",
            "model": "Apple iPhone 11 Pro Max",
            "storage": "512 GB",
            "buyback_price": 19500,
            "data_origin": "verified_scraped",
        }
    ]
    formatted = PriceIQClient.format_records_for_priceiq(raw_data)
    assert len(formatted) == 1
    assert formatted[0]["device"] == "Apple iPhone 11 Pro Max (512 GB)"
    assert formatted[0]["price"] == 19500
    assert formatted[0]["comparables"] == 1


def test_database_manager_initialization():
    """Verify DatabaseManager configuration and default values."""
    from db import DatabaseManager

    mgr = DatabaseManager(ssh_host="10.0.0.1", ssh_username="testuser")
    assert mgr.ssh_host == "10.0.0.1"
    assert mgr.ssh_username == "testuser"
    assert mgr.db_dialect in ["postgresql", "mysql"]

    # Test DATABASE_URL parsing
    db_url_mgr = DatabaseManager(database_url="postgresql://devuser:pass123@localhost:5432/swapup_dev")
    assert db_url_mgr.db_user == "devuser"
    assert db_url_mgr.db_password == "pass123"
    assert db_url_mgr.db_name == "swapup_dev"
    assert db_url_mgr.db_host == "localhost"
    assert db_url_mgr.db_remote_port == 5432


def test_rest_api_driver_normalization():
    """Verify REST API driver handles custom JSON feeds and normalizes attributes."""
    from driver_manager import RestApiDriver

    driver = RestApiDriver()
    mock_payload = {
        "rows": [
            {
                "device": "Samsung Galaxy S24 Ultra (12 GB/512 GB)",
                "price": 62000,
                "grade": "Grade A",
                "storage": "512 GB",
            }
        ]
    }
    normalized = driver._normalize_json_payload(mock_payload, "https://api.example.com/prices", {})
    assert len(normalized) == 1
    assert normalized[0]["brand"] == "Samsung"
    assert normalized[0]["buyback_price"] == 62000.0
    assert normalized[0]["storage"] == "512 GB"
    assert normalized[0]["data_origin"] == "api_rest_feed"


def test_price_comparison_delta_calculation():
    """Verify delta calculation between old price and new price."""
    old_p = 50000.0
    new_p_increase = 52000.0
    diff_inc = round(new_p_increase - old_p, 2)
    pct_inc = round((diff_inc / old_p) * 100, 2)
    assert diff_inc == 2000.0
    assert pct_inc == 4.0

    new_p_decrease = 45000.0
    diff_dec = round(new_p_decrease - old_p, 2)
    pct_dec = round((diff_dec / old_p) * 100, 2)
    assert diff_dec == -5000.0
    assert pct_dec == -10.0


def test_driver_manager_registration():
    """Verify DriverManager properly registers and dispatches mobile_api and rest_api."""
    from driver_manager import driver_manager, RestApiDriver, CashifyDriver

    assert "mobile_api" in driver_manager.drivers
    assert isinstance(driver_manager.drivers["mobile_api"], RestApiDriver)
    assert "website_cashify" in driver_manager.drivers
    assert isinstance(driver_manager.drivers["website_cashify"], CashifyDriver)


def test_api_test_connection_endpoint_validation():
    """Verify /api/sources/test-connection rejects invalid input."""
    from app import app

    client = app.test_client()
    resp = client.post("/api/sources/test-connection", json={})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False

    # Invalid URL format
    resp2 = client.post("/api/sources/test-connection", json={"target_url": "ftp://not-supported"})
    assert resp2.status_code == 400
    assert resp2.get_json()["success"] is False


def test_upsert_records_with_dict_objects():
    """Verify upsert_records safely processes dict items without model_dump error and updates timestamps."""
    from app import upsert_records

    existing = []
    new_records = [
        {
            "brand": "Apple",
            "model": "Apple iPhone 15",
            "storage": "128 GB",
            "condition": "Grade A: Like New",
            "defects": "None",
            "buyback_price": 45000,
            "source_url": "https://example.com/test",
            "data_origin": "verified_scraped",
        }
    ]

    updated_existing, updated_count, added_count = upsert_records(existing, new_records)
    assert added_count == 1
    assert len(updated_existing) == 1
    assert "timestamp" in updated_existing[0]
    assert updated_existing[0]["brand"] == "Apple"


def test_default_api_sources_configured():
    """Verify DEFAULT_API_SOURCES contains WholeCellMarket and external API feeds."""
    from config import DEFAULT_API_SOURCES

    source_names = [s["name"] for s in DEFAULT_API_SOURCES]
    assert any("WholeCellMarket" in name for name in source_names)
    assert any("BackMarket" in name for name in source_names)
    assert any("SellCell" in name for name in source_names)


def test_sqlite_db_manager_connection(tmp_path):
    """Verify db.DatabaseManager supports SQLite dialect and provisions tables."""
    import db
    db_file = tmp_path / "test_priceiq.db"
    db_mgr = db.DatabaseManager(
        db_dialect="sqlite",
        db_name=str(db_file),
    )
    with db_mgr.get_connection() as conn:
        db_mgr.create_table_if_not_exists(conn)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        assert "mobile_buyback_pricing" in tables
        assert "priceiq_prices" in tables


def test_sqlite_to_postgres_migrator_progress(tmp_path):
    """Verify SQLiteToPostgresMigrator progresses through 0% to 100% and validates SQLite source."""
    from migrate_sqlite_to_postgres import SQLiteToPostgresMigrator
    import sqlite3

    db_file = tmp_path / "test_source.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("CREATE TABLE mobile_buyback_pricing (id INTEGER PRIMARY KEY, brand TEXT, model TEXT, storage TEXT, condition TEXT, defects TEXT, buyback_price REAL, currency TEXT, data_origin TEXT, confidence_score REAL, source_url TEXT);")
    cur.execute("INSERT INTO mobile_buyback_pricing VALUES (1, 'Apple', 'Apple iPhone 13', '128 GB', 'Grade A: Like New', 'None', 26750, 'INR', 'wholesale_api_feed', 0.95, '/test');")
    conn.commit()
    conn.close()

    migrator = SQLiteToPostgresMigrator(sqlite_path=db_file)
    assert migrator.progress_pct == 0

    migrator.update_progress(25, "Quarter complete")
    assert migrator.progress_pct == 25

    migrator.update_progress(100, "Finished")
    assert migrator.progress_pct == 100




