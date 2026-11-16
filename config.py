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
    # --- OnePlus Series ---
    {
        "brand": "OnePlus",
        "series": "OnePlus Series",
        "model_family": "OnePlus 12",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-oneplus-12",
    },
    {
        "brand": "OnePlus",
        "series": "OnePlus Series",
        "model_family": "OnePlus 9 Pro 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-oneplus-9-pro-5g",
    },
    {
        "brand": "OnePlus",
        "series": "OnePlus Series",
        "model_family": "OnePlus Nord CE 3 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-oneplus-nord-ce-3-5g",
    },

    # --- Google Pixel Series ---
    {
        "brand": "Google",
        "series": "Pixel Series",
        "model_family": "Pixel 8 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-google-pixel-8-pro",
    },
    {
        "brand": "Google",
        "series": "Pixel Series",
        "model_family": "Pixel 8",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-google-pixel-8",
    },
    {
        "brand": "Google",
        "series": "Pixel Series",
        "model_family": "Pixel 7a",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-google-pixel-7a",
    },

    # --- Xiaomi & Redmi Series ---
    {
        "brand": "Xiaomi",
        "series": "Xiaomi Series",
        "model_family": "Xiaomi Mi 11X",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-xiaomi-mi-11x",
    },
    {
        "brand": "Redmi",
        "series": "Redmi Note Series",
        "model_family": "Redmi Note 11 Pro Plus 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-redmi-note-11-pro-plus-5g",
    },

    # --- Vivo & iQOO Series ---
    {
        "brand": "Vivo",
        "series": "Vivo Series",
        "model_family": "Vivo V30 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-vivo-v30-pro",
    },
    {
        "brand": "Vivo",
        "series": "Vivo Series",
        "model_family": "Vivo V29 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-vivo-v29-pro",
    },
    {
        "brand": "iQOO",
        "series": "iQOO Series",
        "model_family": "iQOO 12 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-iqoo-12-5g",
    },

    # --- Motorola Series ---
    {
        "brand": "Motorola",
        "series": "Motorola Series",
        "model_family": "Moto Edge 30",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-motorola-moto-edge-30",
    },

    # --- Realme Series ---
    {
        "brand": "Realme",
        "series": "Realme Series",
        "model_family": "Realme 7",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-realme-7",
    },

    # --- Nothing Series ---
    {
        "brand": "Nothing",
        "series": "Nothing Series",
        "model_family": "Nothing Phone 2",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-nothing-phone-2",
    },
    {
        "brand": "Nothing",
        "series": "Nothing Series",
        "model_family": "Nothing Phone 1",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-nothing-phone-1",
    },
]

# Amazon India Scraping Targets (New & Amazon Renewed Refurbished Mobile Devices)
DEFAULT_AMAZON_SOURCES = [
    # --- Amazon Renewed / Refurbished Smartphone Category ---
    {
        "name": "Amazon India - Renewed Smartphones Store",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/s?k=renewed+mobile+phones",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhones Hub",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/s?k=renewed+iphone",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Samsung Galaxy Hub",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/s?k=renewed+samsung+galaxy",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 15",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-15-128GB/dp/B0DJLY8563",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 14",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-14-128GB/dp/B0BY2HBC2F",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 13",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-13-128GB/dp/B09V4BHM3X",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 12",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-12-64GB/dp/B08L5WHFT9",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Samsung Galaxy S23 Ultra",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Samsung-Galaxy-Ultra-Phantom/dp/B0C39M5SVR",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed OnePlus 11 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-OnePlus-Titan-Black-Storage/dp/B0C157GGFY",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Google Pixel 7",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Google-Pixel-Lemongrass-128GB/dp/B0BRXQ4998",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: Apple ---
    {
        "name": "Amazon India - Apple iPhone 16",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-16-128-GB/dp/B0DGJ9M6P4",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Apple iPhone 15",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Apple iPhone 14",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-14-128GB-Blue/dp/B0BDK62PDX",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Apple iPhone 13",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-13-128GB-Midnight/dp/B09G9BL5CP",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: Samsung ---
    {
        "name": "Amazon India - Samsung Galaxy S24 Ultra",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-Ultra-Titanium-Storage/dp/B0CS5X68S8",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Samsung Galaxy S24 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-S24-5G-128GB/dp/B0CS5Y234X",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Samsung Galaxy S23 FE 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-S23-Graphite-Storage/dp/B0CJCDV6MV",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Samsung Galaxy A55 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-Awesome-Iceblue-Storage/dp/B0CY28F1G7",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: OnePlus ---
    {
        "name": "Amazon India - OnePlus 12",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-Silky-Black-256GB-Storage/dp/B0CQPPV54C",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - OnePlus 12R",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-12R-Iron-Gray-Storage/dp/B0CQPLJ3BB",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - OnePlus Nord CE 4 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-Nord-Celadon-128GB-Storage/dp/B0CX21C2BC",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - OnePlus Open",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-Open-Emerald-512GB-Storage/dp/B0CKR4PBYC",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: Google Pixel ---
    {
        "name": "Amazon India - Google Pixel 8 Pro",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Google-Pixel-Pro-Bay-Storage/dp/B0CGVRK123",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Google Pixel 8",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Google-Pixel-Hazel-128-Storage/dp/B0CGVQH11K",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Google Pixel 7a",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Google-Pixel-Charcoal-128GB-Storage/dp/B0BZVG3Z8Y",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Mid-Range: Xiaomi / Redmi ---
    {
        "name": "Amazon India - Xiaomi 14 Ultra",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Xiaomi-Ultra-White-512GB-Storage/dp/B0D18987G4",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Redmi Note 13 Pro+ 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Redmi-Note-Fusion-Black-Storage/dp/B0CQ2WMS7D",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Mid-Range: Vivo & iQOO ---
    {
        "name": "Amazon India - Vivo V30 Pro 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Vivo-V30-Pro-5G-Storage/dp/B0CXT67890",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - iQOO 12 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/iQOO-Legend-Snapdragon-Flagship-Processor/dp/B07WHQRC7H",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail: Motorola, Realme, Nothing ---
    {
        "name": "Amazon India - Motorola Edge 50 Pro",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Motorola-Edge-Pro-Black-Storage/dp/B0D131W52R",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Realme 12 Pro+ 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/realme-Submarine-Blue-128-Storage/dp/B0CSD8B6J5",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Nothing Phone 2",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Nothing-Phone-Dark-Grey-Storage/dp/B0C9Q4WXYZ",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Nothing Phone 2a",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Nothing-Phone-White-128-Storage/dp/B0CV467R8T",
        "http_method": "GET",
        "status": "ACTIVE",
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
    # --- OnePlus Series ---
    {
        "brand": "OnePlus",
        "series": "OnePlus Series",
        "model_family": "OnePlus 12",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-oneplus-12",
    },
    {
        "brand": "OnePlus",
        "series": "OnePlus Series",
        "model_family": "OnePlus 9 Pro 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-oneplus-9-pro-5g",
    },
    {
        "brand": "OnePlus",
        "series": "OnePlus Series",
        "model_family": "OnePlus Nord CE 3 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-oneplus-nord-ce-3-5g",
    },

    # --- Google Pixel Series ---
    {
        "brand": "Google",
        "series": "Pixel Series",
        "model_family": "Pixel 8 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-google-pixel-8-pro",
    },
    {
        "brand": "Google",
        "series": "Pixel Series",
        "model_family": "Pixel 8",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-google-pixel-8",
    },
    {
        "brand": "Google",
        "series": "Pixel Series",
        "model_family": "Pixel 7a",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-google-pixel-7a",
    },

    # --- Xiaomi & Redmi Series ---
    {
        "brand": "Xiaomi",
        "series": "Xiaomi Series",
        "model_family": "Xiaomi Mi 11X",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-xiaomi-mi-11x",
    },
    {
        "brand": "Redmi",
        "series": "Redmi Note Series",
        "model_family": "Redmi Note 11 Pro Plus 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-redmi-note-11-pro-plus-5g",
    },

    # --- Vivo & iQOO Series ---
    {
        "brand": "Vivo",
        "series": "Vivo Series",
        "model_family": "Vivo V30 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-vivo-v30-pro",
    },
    {
        "brand": "Vivo",
        "series": "Vivo Series",
        "model_family": "Vivo V29 Pro",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-vivo-v29-pro",
    },
    {
        "brand": "iQOO",
        "series": "iQOO Series",
        "model_family": "iQOO 12 5G",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-iqoo-12-5g",
    },

    # --- Motorola Series ---
    {
        "brand": "Motorola",
        "series": "Motorola Series",
        "model_family": "Moto Edge 30",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-motorola-moto-edge-30",
    },

    # --- Realme Series ---
    {
        "brand": "Realme",
        "series": "Realme Series",
        "model_family": "Realme 7",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-realme-7",
    },

    # --- Nothing Series ---
    {
        "brand": "Nothing",
        "series": "Nothing Series",
        "model_family": "Nothing Phone 2",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-nothing-phone-2",
    },
    {
        "brand": "Nothing",
        "series": "Nothing Series",
        "model_family": "Nothing Phone 1",
        "url": "https://www.cashify.in/sell-old-mobile-phone/used-nothing-phone-1",
    },
]

# Amazon India Scraping Targets (New & Amazon Renewed Refurbished Mobile Devices)
DEFAULT_AMAZON_SOURCES = [
    # --- Amazon Renewed / Refurbished Smartphone Category ---
    {
        "name": "Amazon India - Renewed Smartphones Store",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/s?k=renewed+mobile+phones",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhones Hub",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/s?k=renewed+iphone",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Samsung Galaxy Hub",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/s?k=renewed+samsung+galaxy",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 15",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-15-128GB/dp/B0DJLY8563",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 14",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-14-128GB/dp/B0BY2HBC2F",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 13",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-13-128GB/dp/B09V4BHM3X",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Apple iPhone 12",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Apple-iPhone-12-64GB/dp/B08L5WHFT9",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Samsung Galaxy S23 Ultra",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Samsung-Galaxy-Ultra-Phantom/dp/B0C39M5SVR",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed OnePlus 11 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-OnePlus-Titan-Black-Storage/dp/B0C157GGFY",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Renewed Google Pixel 7",
        "source_type": "website_amazon",
        "category": "eCommerce / Amazon Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Renewed-Google-Pixel-Lemongrass-128GB/dp/B0BRXQ4998",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: Apple ---
    {
        "name": "Amazon India - Apple iPhone 16",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-16-128-GB/dp/B0DGJ9M6P4",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Apple iPhone 15",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Apple iPhone 14",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-14-128GB-Blue/dp/B0BDK62PDX",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Apple iPhone 13",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Apple-iPhone-13-128GB-Midnight/dp/B09G9BL5CP",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: Samsung ---
    {
        "name": "Amazon India - Samsung Galaxy S24 Ultra",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-Ultra-Titanium-Storage/dp/B0CS5X68S8",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Samsung Galaxy S24 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-S24-5G-128GB/dp/B0CS5Y234X",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Samsung Galaxy S23 FE 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-S23-Graphite-Storage/dp/B0CJCDV6MV",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Samsung Galaxy A55 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Samsung-Galaxy-Awesome-Iceblue-Storage/dp/B0CY28F1G7",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: OnePlus ---
    {
        "name": "Amazon India - OnePlus 12",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-Silky-Black-256GB-Storage/dp/B0CQPPV54C",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - OnePlus 12R",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-12R-Iron-Gray-Storage/dp/B0CQPLJ3BB",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - OnePlus Nord CE 4 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-Nord-Celadon-128GB-Storage/dp/B0CX21C2BC",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - OnePlus Open",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/OnePlus-Open-Emerald-512GB-Storage/dp/B0CKR4PBYC",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Flagship Devices: Google Pixel ---
    {
        "name": "Amazon India - Google Pixel 8 Pro",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Google-Pixel-Pro-Bay-Storage/dp/B0CGVRK123",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Google Pixel 8",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Google-Pixel-Hazel-128-Storage/dp/B0CGVQH11K",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Google Pixel 7a",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Google-Pixel-Charcoal-128GB-Storage/dp/B0BZVG3Z8Y",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Mid-Range: Xiaomi / Redmi ---
    {
        "name": "Amazon India - Xiaomi 14 Ultra",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Xiaomi-Ultra-White-512GB-Storage/dp/B0D18987G4",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Redmi Note 13 Pro+ 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Redmi-Note-Fusion-Black-Storage/dp/B0CQ2WMS7D",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail / Mid-Range: Vivo & iQOO ---
    {
        "name": "Amazon India - Vivo V30 Pro 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Vivo-V30-Pro-5G-Storage/dp/B0CXT67890",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - iQOO 12 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/iQOO-Legend-Snapdragon-Flagship-Processor/dp/B07WHQRC7H",
        "http_method": "GET",
        "status": "ACTIVE",
    },

    # --- Amazon Retail: Motorola, Realme, Nothing ---
    {
        "name": "Amazon India - Motorola Edge 50 Pro",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Motorola-Edge-Pro-Black-Storage/dp/B0D131W52R",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Realme 12 Pro+ 5G",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/realme-Submarine-Blue-128-Storage/dp/B0CSD8B6J5",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Nothing Phone 2",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Nothing-Phone-Dark-Grey-Storage/dp/B0C9Q4WXYZ",
        "http_method": "GET",
        "status": "ACTIVE",
    },
    {
        "name": "Amazon India - Nothing Phone 2a",
        "source_type": "website_amazon",
        "category": "eCommerce / Retail & Renewed",
        "bucket_name": "amazon_pricing",
        "target_url": "https://www.amazon.in/Nothing-Phone-White-128-Storage/dp/B0CV467R8T",
        "http_method": "GET",
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
