"""
Main execution entrypoint for Refurbished Mobile Price Intelligence POC.
Coordinates scraping, condition grading simulation, validation, and export.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List

from config import BASE_DIR, OUTPUT_CSV_PATH, OUTPUT_JSON_PATH, TARGET_DEVICES
from exporter import save_to_csv, save_to_json
from grading_engine import GradingEngine
from models import MobilePriceRecord
from scraper import CashifyScraper

# Ensure utf-8 output in Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def print_summary_table(records: List[MobilePriceRecord]) -> None:
    """Print a clean CLI summary table of collected records."""
    print("\n" + "=" * 90)
    print(f"{'BRAND':<8} | {'MODEL':<34} | {'STORAGE':<8} | {'PRICE (INR)':<11} | {'ORIGIN':<16} | {'DEFECTS'}")
    print("=" * 90)

    for r in records:
        origin_badge = "[VERIFIED]" if r.data_origin == "verified_scraped" else "[GRADED-SIM]"
        defect_preview = (r.defects[:25] + "...") if len(r.defects) > 25 else r.defects
        print(
            f"{r.brand:<8} | {r.model[:34]:<34} | {r.storage:<8} | ₹{r.buyback_price:<10,d} | {origin_badge:<16} | {defect_preview}"
        )
    print("=" * 90)


def print_price_intelligence_insights(records: List[MobilePriceRecord]) -> None:
    """Analyze device model, storage, and condition impacts on buyback value."""
    verified = [r for r in records if r.data_origin == "verified_scraped"]
    print("\n" + "#" * 90)
    print("### MOBILE BUYBACK PRICE INTELLIGENCE INSIGHTS ###")
    print("#" * 90)

    print(f"\n1. TOTAL DATA POINTS: {len(records)} ({len(verified)} verified live, {len(records) - len(verified)} graded matrix)")

    # Group by model family
    models = {}
    for r in verified:
        # group by brand + short model
        key = f"{r.brand} - {r.model.split('(')[0].strip()}"
        models.setdefault(key, []).append(r)

    print("\n2. STORAGE CAPACITY IMPACT (Verified Baseline Quotes):")
    for model_name, variants in models.items():
        print(f"\n   * {model_name}:")
        sorted_variants = sorted(variants, key=lambda x: x.buyback_price)
        base = sorted_variants[0]
        for v in sorted_variants:
            premium = v.buyback_price - base.buyback_price
            pct = (premium / base.buyback_price) * 100 if base.buyback_price else 0
            print(f"     - {v.storage:>7}: ₹{v.buyback_price:>7,d} (Base +₹{premium:,d} / +{pct:.1f}%)")

    print("\n3. CONDITION & DEFECT IMPACT (Sample iPhone 13 128GB Case Study):")
    sample_iphone = [r for r in records if "iPhone 13" in r.model and "128 GB" in r.storage]
    if sample_iphone:
        for r in sample_iphone:
            tier_name = r.condition.split(":")[0]
            print(f"   * {tier_name:<30} -> ₹{r.buyback_price:>7,d} | Defects: {r.defects}")

    print("\n" + "#" * 90 + "\n")


def run_pipeline(include_matrix: bool = True) -> int:
    """Run the complete scrape, transform, and export pipeline."""
    logger.info("Initializing Mobile Price Intelligence Scraping Pipeline...")
    scraper = CashifyScraper()
    grading_engine = GradingEngine()

    verified_records: List[MobilePriceRecord] = []

    # Iterate configured targets
    for target in TARGET_DEVICES:
        url = target["url"]
        logger.info("Processing target: %s %s -> %s", target["brand"], target["model_family"], url)
        try:
            extracted = scraper.scrape_url(url)
            logger.info("Extracted %d verified variant records from %s", len(extracted), url)
            verified_records.extend(extracted)
        except Exception as e:
            logger.error("Error scraping target %s: %s", url, e, exc_info=True)

    if not verified_records:
        logger.error("No verified records were extracted! Exiting pipeline.")
        return 1

    logger.info("Total verified live records collected: %d", len(verified_records))

    # Apply condition grading simulation
    final_records = grading_engine.build_full_dataset(
        verified_records, include_grading_matrix=include_matrix
    )
    logger.info("Total final records (verified + graded): %d", len(final_records))

    # Export
    save_to_json(final_records, OUTPUT_JSON_PATH)
    save_to_csv(final_records, OUTPUT_CSV_PATH)

    # Sync to Database
    try:
        from datetime import datetime, timezone
        from db import DatabaseManager
        db = DatabaseManager()
        now_iso = datetime.now(timezone.utc).isoformat()
        records_dict = [
            r.model_dump() if hasattr(r, "model_dump") else (r.dict() if hasattr(r, "dict") else dict(r))
            for r in final_records
        ]
        for r in records_dict:
            r["timestamp"] = now_iso
            
        # Ingest into all schema tables (interval_reports, devices, repair costs, cashify_buy_prices, observations, runs)
        ingest_res = db.ingest_cashify_interval_data(records_dict)
        db.upsert_records(records_dict)
        logger.info(
            "Successfully synced to schema tables: Report ID %s, Bucket: %s, Devices: %d, Rows: %d",
            ingest_res.get("report_id"),
            ingest_res.get("report_bucket"),
            ingest_res.get("devices_processed", 0),
            ingest_res.get("cashify_rows_added", 0),
        )
    except Exception as db_err:
        logger.warning("Could not sync to database: %s", db_err)

    # CLI Output
    print_summary_table(final_records)
    print_price_intelligence_insights(final_records)

    logger.info("Pipeline execution completed successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Refurbished Mobile Price Intelligence POC")
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="Export only verified live scraped records without condition matrix simulation"
    )
    args = parser.parse_args()

    sys.exit(run_pipeline(include_matrix=not args.live_only))


if __name__ == "__main__":
    main()

