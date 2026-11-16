"""
Configuration module for Refurbished Mobile Price Intelligence System.
Centralizes scraping targets, HTTP parameters, grading multipliers, and file paths.
"""
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON_PATH = BASE_DIR / "output.json"
OUTPUT_CSV_PATH = BASE_DIR / "output.csv"

# Target Mobile Buyback URLs (Cashify authorized public pricing pages)
TARGET_DEVICES = [
    # --- Samsung Galaxy Z Series (Fold & Flip) ---
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Fold 6",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-fold-6-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Fold 5",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-fold-5",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Fold 4",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-fold-4-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Fold 3 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-fold3-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Fold 2",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-fold2-5g-12-gb-256-gb",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Flip 6",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-flip-6-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Flip 5",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-flip-5",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Flip 4",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-flip-4-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Flip 3 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-flip3-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Z Series",
        "model_family": "Galaxy Z Flip",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-z-flip-8-gb-128-gb",
    },

    # --- Samsung Galaxy S Series ---
    {
        "brand": "Samsung",
        "series": "Galaxy S Series",
        "model_family": "Galaxy S24 Ultra 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-s24-ultra-5g-12-gb-256-gb",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy S Series",
        "model_family": "Galaxy S23 Ultra 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-s23-ultra-5g-12-gb-256-gb",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy S Series",
        "model_family": "Galaxy S23 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-s23-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy S Series",
        "model_family": "Galaxy S21 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-s21-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy S Series",
        "model_family": "Galaxy S21 FE 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-s21-fe-5g-8-gb-128-gb",
    },

    # --- Samsung Galaxy Note Series ---
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 20 Ultra 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-note-20-ultra-5g-12-gb-256-gb",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 20",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-note-20-8-gb-256-gb",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 10 Plus",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-note-10-plus",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 10 Lite",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-note-10-lite",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 10",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-note-10-8-gb-256-gb",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 9",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-p-samsung-galaxy-note-9",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy Note Series",
        "model_family": "Galaxy Note 8",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-p-samsung-galaxy-note-8",
    },

    # --- Samsung Galaxy A Series ---
    {
        "brand": "Samsung",
        "series": "Galaxy A Series",
        "model_family": "Galaxy A54 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-a54-5g",
    },
    {
        "brand": "Samsung",
        "series": "Galaxy A Series",
        "model_family": "Galaxy A34 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-samsung-galaxy-a34-5g",
    },

    # --- Apple iPhone Series ---
    {
        "brand": "Apple",
        "series": "iPhone 16 Series",
        "model_family": "iPhone 16",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-16-8-gb-128-gb",
    },
    {
        "brand": "Apple",
        "series": "iPhone 15 Series",
        "model_family": "iPhone 15",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-15-6-gb-128-gb",
    },
    {
        "brand": "Apple",
        "series": "iPhone 14 Series",
        "model_family": "iPhone 14 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-14-pro-6-gb-128-gb",
    },
    {
        "brand": "Apple",
        "series": "iPhone 14 Series",
        "model_family": "iPhone 14",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-14",
    },
    {
        "brand": "Apple",
        "series": "iPhone 13 Series",
        "model_family": "iPhone 13 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-13-pro-6-gb-128-gb",
    },
    {
        "brand": "Apple",
        "series": "iPhone 13 Series",
        "model_family": "iPhone 13",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-13",
    },
    {
        "brand": "Apple",
        "series": "iPhone 12 Series",
        "model_family": "iPhone 12",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-12",
    },
    {
        "brand": "Apple",
        "series": "iPhone 11 Series",
        "model_family": "iPhone 11",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-apple-iphone-11",
    },
]

# Additional API Sources (WholeCellMarket, Wholesale & Buyback Feeds)
DEFAULT_API_SOURCES = [
    {
        "name": "WholeCellMarket - PriceIQ Bulk Pricing API",
        "source_type": "mobile_api",
        "category": "Smartphones & Wholesale",
        "bucket_name": "wholecell_wholesale",
        "target_url": "https://thesuperiq.com/apps/priceiq/programs?market=IN",
        "http_method": "GET",
        "headers_json": {"Accept": "application/json"},
        "auth_config_json": {
            "type": "bearer",
            "token_url": "https://thesuperiq.com/apps/priceiq/api/oauth/token",
            "client_id_env": "WHOLECELL_CLIENT_ID",
            "client_secret_env": "WHOLECELL_CLIENT_SECRET",
        },
        "params_json": {"market": "IN", "channel": "wholesale"},
        "status": "ACTIVE",
    },
    {
        "name": "BackMarket - Buyback Pricing Partner API",
        "source_type": "rest_api",
        "category": "Refurbished Trade-In",
        "bucket_name": "backmarket_buyback",
        "target_url": "https://www.backmarket.com",
        "http_method": "GET",
        "headers_json": {"Accept": "application/json"},
        "auth_config_json": {"type": "none"},
        "params_json": {"country": "in", "category": "smartphones"},
        "status": "ACTIVE",
    },
    {
        "name": "SellCell - Global Mobile Price Intelligence API",
        "source_type": "rest_api",
        "category": "Smartphones",
        "bucket_name": "sellcell_prices",
        "target_url": "https://www.sellcell.com",
        "http_method": "GET",
        "headers_json": {"Accept": "application/json"},
        "auth_config_json": {"type": "none"},
        "params_json": {"limit": 50},
        "status": "ACTIVE",
    },
]

# HTTP Request Headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
}

# Network settings
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 1.5

# Condition and Defect Grading Multipliers (Industry standard buyback benchmarks)
# Used to simulate condition tiers against verified live maximum buyback baseline
CONDITION_TIERS = {
    "Grade A (Flawless)": {
        "grade_code": "Grade A",
        "condition_desc": "Like New / Flawless - 100% functional, zero scratches, battery health > 85%",
        "defects": "Flawless condition, zero scratches (Repair cost: ₹0)",
        "factor": 1.00,
    },
    "Grade B (Good)": {
        "grade_code": "Grade B",
        "condition_desc": "Good - Fully functional, minor hairline scratches on body/frame, no dents",
        "defects": "Minor signs of use · Est. QC/Polish cost",
        "factor": 0.88,
    },
    "Grade C (Fair / Average)": {
        "grade_code": "Grade C",
        "condition_desc": "Average - Fully functional, moderate scratches and minor body dent, battery < 80%",
        "defects": "Aged battery / housing wear · Est. Battery+Housing repair",
        "factor": 0.72,
    },
    "Grade D (Cracked Screen)": {
        "grade_code": "Grade D",
        "condition_desc": "Cracked - Display cracks or lines, functional touch",
        "defects": "Cracked screen / display lines · Est. Screen replacement cost",
        "factor": 0.54,
    },
    "Grade E (Defective / Board)": {
        "grade_code": "Grade E",
        "condition_desc": "Defective - Dead display or logic board / IC faults",
        "defects": "Dead display + board issue · Est. Board+Screen repair cost",
        "factor": 0.35,
    },
}
