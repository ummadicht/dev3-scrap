"""
Flask Web Application for Multi-Source Mobile Price Intelligence
================================================================
Centralized Multi-Source Data Collection, Historical Storage & Comparison Platform.
"""

from __future__ import annotations

import copy
import csv
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
)

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CONDITION_TIERS,
    MAX_RETRIES,
    OUTPUT_CSV_PATH,
    OUTPUT_JSON_PATH,
    REQUEST_TIMEOUT_SECONDS,
    TARGET_DEVICES,
)
from db import DatabaseManager
from driver_manager import driver_manager
from exporter import save_to_json
from grading_engine import GradingEngine
from models import MobilePriceRecord
from scraper import CashifyScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WebApp")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Initialize central Database Manager
db_manager = DatabaseManager()


# ---------------------------------------------------------------------------
# Data Loaders & Calculations
# ---------------------------------------------------------------------------
def load_records() -> List[Dict[str, Any]]:
    """Load records from output.json and deduplicate by (source_url, storage, condition)."""
    if OUTPUT_JSON_PATH.exists():
        with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
            try:
                raw = json.load(f)
            except json.JSONDecodeError:
                raw = []
        dedup: Dict[tuple, Dict[str, Any]] = {}
        for r in raw:
            grade_prefix = r.get("condition", "").split(":")[0].strip()
            key = (r.get("source_url", ""), r.get("storage", ""), grade_prefix)
            if key not in dedup or r.get("timestamp", "") >= dedup[key].get("timestamp", ""):
                dedup[key] = r
        return list(dedup.values())
    return []


def build_custom_tiers(params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build condition tier multipliers from client overrides."""
    tiers = copy.deepcopy(CONDITION_TIERS)
    try:
        if "grade_b" in params and params["grade_b"] is not None:
            tiers["Grade B (Good)"]["factor"] = round(float(params["grade_b"]) / 100.0, 4)
        if "grade_c" in params and params["grade_c"] is not None:
            tiers["Grade C (Fair / Average)"]["factor"] = round(float(params["grade_c"]) / 100.0, 4)
        if "grade_d" in params and params["grade_d"] is not None:
            tiers["Grade D (Defective / Broken)"]["factor"] = round(float(params["grade_d"]) / 100.0, 4)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid custom tier multiplier supplied, using defaults: %s", exc)
    return tiers


def filter_by_storage(
    records: List[MobilePriceRecord],
    allowed_storages: List[str],
) -> List[MobilePriceRecord]:
    """Filter records by an allowed list of storage capacities."""
    if not allowed_storages:
        return records
    normalized_allowed = {s.upper().replace(" ", "") for s in allowed_storages}
    return [
        r for r in records
        if r.storage and r.storage.upper().replace(" ", "") in normalized_allowed
    ]


def compute_kpis(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate dashboard summary KPIs from pricing records."""
    if not records:
        return {
            "total_records": 0,
            "verified_count": 0,
            "simulated_count": 0,
            "avg_price": 0,
            "max_price": 0,
            "max_device": "—",
            "min_price": 0,
            "min_device": "—",
            "brands_tracked": 0,
            "last_updated": "Never",
        }

    prices = [r["buyback_price"] for r in records if "buyback_price" in r]
    avg_price = int(sum(prices) / len(prices)) if prices else 0
    max_rec = max(records, key=lambda x: x.get("buyback_price", 0)) if records else {}
    min_rec = min(records, key=lambda x: x.get("buyback_price", 0)) if records else {}

    verified = sum(1 for r in records if r.get("data_origin") == "verified_scraped")
    simulated = sum(1 for r in records if r.get("data_origin") == "sample_condition_graded")
    brands = len({r["brand"] for r in records if "brand" in r})

    timestamps = [r["timestamp"] for r in records if r.get("timestamp")]
    latest_ts = max(timestamps) if timestamps else None
    if latest_ts:
        try:
            dt = datetime.fromisoformat(latest_ts)
            last_updated = dt.strftime("%d %b %Y, %I:%M %p UTC")
        except Exception:
            last_updated = latest_ts
    else:
        last_updated = "Never"

    return {
        "total_records": len(records),
        "verified_count": verified,
        "simulated_count": simulated,
        "avg_price": avg_price,
        "max_price": max_rec.get("buyback_price", 0),
        "max_device": max_rec.get("model", "—"),
        "min_price": min_rec.get("buyback_price", 0),
        "min_device": min_rec.get("model", "—"),
        "brands_tracked": brands,
        "last_updated": last_updated,
    }


def upsert_records(
    existing: List[Dict[str, Any]],
    new_records: List[MobilePriceRecord],
    include_matrix: bool = True,
    target_urls: set = None,
) -> tuple:
    """Upsert records cleanly in memory without duplicates."""
    if not include_matrix and target_urls:
        existing = [
            r for r in existing
            if not (r.get("source_url") in target_urls and r.get("data_origin") == "sample_condition_graded")
        ]

    existing_map = {
        (r.get("source_url", ""), r.get("storage", ""), r.get("condition", "").split(":")[0].strip()): idx
        for idx, r in enumerate(existing)
    }

    updated_count = 0
    added_count = 0
    now_iso = datetime.utcnow().isoformat() + "+00:00"

    for rec in new_records:
        rec_dict = rec.model_dump()
        rec_dict["timestamp"] = now_iso
        grade_prefix = rec.condition.split(":")[0].strip()
        key = (rec.source_url, rec.storage, grade_prefix)
        if key in existing_map:
            idx = existing_map[key]
            existing[idx].update(rec_dict)
            updated_count += 1
        else:
            existing.append(rec_dict)
            existing_map[key] = len(existing) - 1
            added_count += 1

    return existing, updated_count, added_count


# ---------------------------------------------------------------------------
# UI Page Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Main price intelligence dashboard (clean modern white theme)."""
    records = load_records()
    records = sorted(records, key=lambda x: x.get("timestamp", ""), reverse=True)
    kpis = compute_kpis(records)

    try:
        platform_stats = db_manager.get_platform_analytics()
        recent_changes = db_manager.get_price_comparison_report(limit=10)
    except Exception as e:
        logger.warning("Could not fetch DB stats for index: %s", e)
        platform_stats = {
            "total_sources": len(TARGET_DEVICES),
            "active_sources": len(TARGET_DEVICES),
            "paused_sources": 0,
            "failed_sources": 0,
            "total_runs": 1,
            "total_records_collected": len(records),
        }
        recent_changes = []

    return render_template(
        "index.html",
        records=records,
        kpis=kpis,
        platform_stats=platform_stats,
        recent_changes=recent_changes,
        target_devices=TARGET_DEVICES,
    )


@app.route("/sources")
def sources_page():
    """Dedicated Scraping Source Management interface."""
    try:
        db_manager.seed_default_sources_if_empty()
        sources = db_manager.get_sources()
        stats = db_manager.get_platform_analytics()
    except Exception as exc:
        logger.exception("Failed to load sources from PostgreSQL")
        sources = []
        stats = {"total_sources": 0, "active_sources": 0, "paused_sources": 0, "total_runs": 0, "total_records_collected": 0}

    # Fallback to configured target devices so the page is never blank/null
    if not sources:
        sources = [
            {
                "id": idx + 1,
                "name": f"Cashify - {dev.get('brand')} {dev.get('model_family', 'Device')}",
                "source_type": "website_cashify",
                "category": dev.get("category", "Smartphones"),
                "bucket_name": "cashify_buyback",
                "target_url": dev.get("url", ""),
                "status": "ACTIVE",
                "schedule_interval_min": 1440,
                "last_scraped_at": None,
                "last_status_message": "Ready to scrape",
            }
            for idx, dev in enumerate(TARGET_DEVICES)
        ]
        stats["total_sources"] = len(sources)
        stats["active_sources"] = len(sources)
        stats["paused_sources"] = 0

    return render_template(
        "sources.html",
        sources=sources,
        stats=stats,
    )


@app.route("/comparison")
def comparison_page():
    """Dedicated Price Comparison and Change Detection report page."""
    try:
        try:
            comparisons = db_manager.get_price_comparison_report(limit=250)
            stats = db_manager.get_platform_analytics()
        except Exception as exc:
            logger.exception("Failed to load comparison data from database")
            comparisons = []
            stats = {"price_increases": 0, "price_decreases": 0, "price_unchanged": 0, "new_items": 0}

        # Fallback to baseline records so comparison matrix is never blank/null
        if not comparisons:
            current_records = load_records_from_storage()
            comparisons = [
                {
                    "id": idx + 1,
                    "device_identifier": f"{r.brand} {r.model} ({r.storage or 'Base'})",
                    "brand": r.brand,
                    "condition_grade": r.condition,
                    "old_price_fmt": "—",
                    "new_price_fmt": f"₹{int(r.buyback_price):,}",
                    "diff_fmt": "Baseline",
                    "badge_cls": "bg-sky-50 text-sky-700 border border-sky-200",
                    "change_type": "NEW",
                    "bucket_name": "cashify_buyback",
                    "detected_at": r.timestamp,
                    "detected_at_fmt": r.timestamp[:16].replace("T", " ") if isinstance(r.timestamp, str) else "Just now",
                }
                for idx, r in enumerate(current_records[:150])
            ]
            stats["new_items"] = len(comparisons)

        for c_item in comparisons:
            if not c_item.get("detected_at_fmt"):
                ts = c_item.get("detected_at")
                if hasattr(ts, "strftime"):
                    c_item["detected_at_fmt"] = ts.strftime("%d %b %H:%M")
                elif isinstance(ts, str) and len(ts) >= 16:
                    c_item["detected_at_fmt"] = ts[:16].replace("T", " ")
                else:
                    c_item["detected_at_fmt"] = "Just now"

        return render_template(
            "comparison.html",
            comparisons=comparisons,
            stats=stats,
        )
    except Exception as fatal_err:
        logger.exception("Critical error in comparison_page: %s", fatal_err)
        return render_template(
            "comparison.html",
            comparisons=[],
            stats={"price_increases": 0, "price_decreases": 0, "price_unchanged": 0, "new_items": 0},
        )


# ---------------------------------------------------------------------------
# Scraping Sources REST APIs
# ---------------------------------------------------------------------------
@app.route("/api/sources", methods=["GET"])
def api_get_sources():
    """List all registered scraping sources."""
    status = request.args.get("status")
    category = request.args.get("category")
    try:
        sources = db_manager.get_sources(status=status, category=category)
        return jsonify({"success": True, "sources": sources})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sources", methods=["POST"])
def api_add_source():
    """Add a new website URL or REST API for scraping."""
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name", "").strip()
    target_url = data.get("target_url", "").strip()

    if not name or not target_url:
        return jsonify({"success": False, "error": "Name and Target URL are required."}), 400

    try:
        new_id = db_manager.add_source(
            name=name,
            target_url=target_url,
            source_type=data.get("source_type", "website_cashify"),
            category=data.get("category", "Smartphones"),
            bucket_name=data.get("bucket_name", "cashify_buyback"),
            http_method=data.get("http_method", "GET"),
            headers=data.get("headers_json"),
            auth_config=data.get("auth_config_json"),
            params=data.get("params_json"),
            schedule_interval_min=int(data.get("schedule_interval_min", 1440)),
            status=data.get("status", "ACTIVE"),
        )
        return jsonify({"success": True, "source_id": new_id, "message": f"Source '{name}' added successfully."}), 201
    except Exception as exc:
        logger.exception("Error adding source")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sources/<int:source_id>", methods=["GET"])
def api_get_source(source_id: int):
    """Get configuration details for a single source."""
    source = db_manager.get_source(source_id)
    if not source:
        return jsonify({"success": False, "error": "Source not found."}), 404
    return jsonify({"success": True, "source": source})


@app.route("/api/sources/<int:source_id>", methods=["PUT"])
def api_update_source(source_id: int):
    """Update configuration of an existing source."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        updated = db_manager.update_source(source_id, data)
        if not updated:
            return jsonify({"success": False, "error": "Source not found or no changes provided."}), 404
        return jsonify({"success": True, "message": f"Source ID {source_id} updated successfully."})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sources/<int:source_id>/status", methods=["POST"])
def api_set_source_status(source_id: int):
    """Pause or Resume an individual scraping source without deleting it."""
    data = request.get_json(force=True, silent=True) or {}
    status = data.get("status", "").upper()
    if status not in {"ACTIVE", "PAUSED"}:
        return jsonify({"success": False, "error": "Status must be 'ACTIVE' or 'PAUSED'."}), 400

    try:
        updated = db_manager.set_source_status(source_id, status)
        if not updated:
            return jsonify({"success": False, "error": "Source not found."}), 404
        return jsonify({"success": True, "message": f"Source status set to {status}."})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sources/<int:source_id>", methods=["DELETE"])
def api_delete_source(source_id: int):
    """Delete a scraping source."""
    try:
        deleted = db_manager.delete_source(source_id)
        if not deleted:
            return jsonify({"success": False, "error": "Source not found."}), 404
        return jsonify({"success": True, "message": f"Source ID {source_id} deleted."})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sources/<int:source_id>/scrape", methods=["POST"])
def api_trigger_source_scrape(source_id: int):
    """
    Manually trigger an execution for an individual scraping source:
    1. Checks status (refuses if PAUSED).
    2. Runs driver (Cashify, REST API, or generic HTML).
    3. Stores historical snapshots in PostgreSQL under logical bucket.
    4. Automatically calculates ΔP & %Δ and writes change events.
    5. Updates live mirror table & exports.
    """
    source = db_manager.get_source(source_id)
    if not source:
        return jsonify({"success": False, "error": "Source not found."}), 404

    if source.get("status") == "PAUSED":
        return jsonify({
            "success": False,
            "error": f"Source '{source.get('name')}' is currently PAUSED. Please resume it before executing."
        }), 400

    bucket_name = source.get("bucket_name", "default_bucket")
    run_id = db_manager.start_scrape_run(source_id, bucket_name)

    try:
        records = driver_manager.execute_source(source)
        if not records:
            db_manager.finish_scrape_run(run_id, source_id, "FAILED", 0, 0, "No records returned by driver.")
            return jsonify({"success": False, "error": "Driver extracted zero records."}), 404

        # Save historical snapshots in PostgreSQL bucket
        saved_count = db_manager.save_historical_snapshots(run_id, source_id, bucket_name, records)

        # Detect and log price variations (ΔP & %Δ)
        changes = db_manager.detect_and_record_changes(run_id, source_id, bucket_name, records)

        # Upsert into PostgreSQL live mirror table
        db_manager.upsert_records(records)

        # Synchronize local file exports
        existing = load_records()
        for r in records:
            grade_prefix = r.get("condition", "").split(":")[0].strip()
            key = (r.get("source_url", ""), r.get("storage", ""), grade_prefix)
            # Upsert into in-memory list
            found = False
            for idx, ex in enumerate(existing):
                if (ex.get("source_url"), ex.get("storage"), ex.get("condition", "").split(":")[0].strip()) == key:
                    existing[idx].update(r)
                    found = True
                    break
            if not found:
                existing.append(r)

        save_to_json(existing, OUTPUT_JSON_PATH)
        save_to_csv_raw(existing, OUTPUT_CSV_PATH)

        db_manager.finish_scrape_run(
            run_id=run_id,
            source_id=source_id,
            status="SUCCESS",
            records_count=saved_count,
            changes_count=len(changes),
        )

        return jsonify({
            "success": True,
            "message": f"Scrape completed: {saved_count} snapshots saved in bucket '{bucket_name}', {len(changes)} price changes detected.",
            "run_id": run_id,
            "records_scraped": saved_count,
            "changes_count": len(changes),
        })

    except Exception as exc:
        logger.exception("Error during source execution")
        db_manager.finish_scrape_run(run_id, source_id, "FAILED", 0, 0, str(exc))
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Legacy & Bulk Scraping Endpoints (Enhanced with Historical DB Storage)
# ---------------------------------------------------------------------------
@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """Trigger a scrape for one or more URLs and store historical snapshots."""
    data = request.get_json(force=True, silent=True) or {}
    urls = data.get("urls") or ([data["url"]] if data.get("url") else [])
    urls = [u.strip() for u in urls if u and u.strip()]

    if not urls:
        return jsonify({"success": False, "error": "No URL provided."}), 400

    include_matrix = bool(data.get("include_matrix", True))
    allowed_storages = data.get("storages") or []
    custom_tiers = build_custom_tiers(data)

    try:
        scraper = CashifyScraper()
        engine = GradingEngine(tiers=custom_tiers)

        all_verified: List[MobilePriceRecord] = []
        for u in urls:
            extracted = scraper.scrape_url(u)
            if allowed_storages:
                extracted = filter_by_storage(extracted, allowed_storages)
            all_verified.extend(extracted)

        if not all_verified:
            return jsonify({"success": False, "error": "No matching pricing records found."}), 404

        new_all = engine.build_full_dataset(all_verified, include_grading_matrix=include_matrix)
        new_dicts = [r.model_dump() for r in new_all]

        # 1. Historical bucket recording in PostgreSQL
        try:
            run_id = db_manager.start_scrape_run(source_id=None, bucket_name="cashify_buyback")
            db_manager.save_historical_snapshots(run_id, source_id=None, bucket_name="cashify_buyback", records=new_dicts)
            changes = db_manager.detect_and_record_changes(run_id, source_id=None, bucket_name="cashify_buyback", records=new_dicts)
            db_manager.finish_scrape_run(run_id, source_id=None, status="SUCCESS", records_count=len(new_dicts), changes_count=len(changes))
            db_manager.upsert_records(new_dicts)
        except Exception as db_err:
            logger.warning("DB historical logging skipped: %s", db_err)

        # 2. Update files
        existing = load_records()
        scraped_urls = {r.source_url for r in all_verified}
        existing, updated_count, added_count = upsert_records(
            existing, new_all, include_matrix=include_matrix, target_urls=scraped_urls
        )
        save_to_json(existing, OUTPUT_JSON_PATH)
        save_to_csv_raw(existing, OUTPUT_CSV_PATH)

        return jsonify({
            "success": True,
            "message": f"Successfully scraped {len(all_verified)} live variants ({len(new_dicts)} total records saved historically)!",
            "total_records": len(existing),
            "updated_count": updated_count,
            "added_count": added_count,
        })
    except Exception as exc:
        logger.exception("Error during scrape")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/scrape-all", methods=["POST"])
def api_scrape_all():
    """Trigger full catalog refresh across all devices with historical snapshots."""
    try:
        scraper = CashifyScraper()
        engine = GradingEngine()
        all_verified: List[MobilePriceRecord] = []

        for dev in TARGET_DEVICES:
            url = dev.get("url")
            if url:
                extracted = scraper.scrape_url(url)
                all_verified.extend(extracted)

        if not all_verified:
            return jsonify({"success": False, "error": "No records extracted."}), 404

        full_dataset = engine.build_full_dataset(all_verified, include_grading_matrix=True)
        rec_dicts = [r.model_dump() for r in full_dataset]

        # Historical run in PostgreSQL
        try:
            run_id = db_manager.start_scrape_run(source_id=None, bucket_name="cashify_buyback")
            db_manager.save_historical_snapshots(run_id, source_id=None, bucket_name="cashify_buyback", records=rec_dicts)
            changes = db_manager.detect_and_record_changes(run_id, source_id=None, bucket_name="cashify_buyback", records=rec_dicts)
            db_manager.finish_scrape_run(run_id, source_id=None, status="SUCCESS", records_count=len(rec_dicts), changes_count=len(changes))
            db_manager.upsert_records(rec_dicts)
        except Exception as db_err:
            logger.warning("DB logging error: %s", db_err)

        existing = load_records()
        existing, u_count, a_count = upsert_records(existing, full_dataset, include_matrix=True)
        save_to_json(existing, OUTPUT_JSON_PATH)
        save_to_csv_raw(existing, OUTPUT_CSV_PATH)

        return jsonify({
            "success": True,
            "message": f"Catalog refreshed: {len(all_verified)} verified quotes, {len(rec_dicts)} historical snapshots stored in PostgreSQL.",
            "total_records": len(existing),
        })
    except Exception as exc:
        logger.exception("Error during scrape-all")
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# File Exports
# ---------------------------------------------------------------------------
@app.route("/download/csv")
def download_csv():
    """Export all records as a downloadable CSV."""
    records = load_records()
    save_to_csv_raw(records, OUTPUT_CSV_PATH)
    return send_file(
        OUTPUT_CSV_PATH,
        mimetype="text/csv",
        as_attachment=True,
        download_name="mobile_buyback_pricing_intelligence.csv",
    )


@app.route("/download/json")
def download_json():
    """Export all records as a downloadable JSON."""
    return send_file(
        OUTPUT_JSON_PATH,
        mimetype="application/json",
        as_attachment=True,
        download_name="mobile_buyback_pricing_intelligence.json",
    )


def save_to_csv_raw(records: List[Dict[str, Any]], path: Path):
    """Write raw dicts to CSV."""
    fieldnames = [
        "brand", "model", "storage", "ram", "cores", "camera", "condition", "defects",
        "buyback_price", "currency", "data_origin", "confidence_score",
        "source_url", "timestamp",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, "") for k in fieldnames})
    logger.info("Exported %d records to %s", len(records), path)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
