"""
Grading and Pricing Intelligence Engine.
Simulates and models condition tiers and defect-based price deductions against
ground-truth verified baseline quotes.
All generated condition-graded records are explicitly labeled with
data_origin='sample_condition_graded' to ensure complete transparency.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from config import CONDITION_TIERS
from models import MobilePriceRecord

logger = logging.getLogger("grading_engine")


def compute_repair_benchmarks(base_price: int) -> Dict[str, int]:
    """Calculate component repair benchmarks and exchange benchmarks from Grade A price."""
    wholesale_inr = int(round((base_price / 0.80) / 500.0) * 500)
    polish_cost   = int(max(600, round((base_price * 0.04) / 100.0) * 100))
    battery_cost  = int(max(1800, round((base_price * 0.07) / 100.0) * 100))
    housing_cost  = int(max(2200, round((base_price * 0.09) / 100.0) * 100))
    screen_repair = int(max(4500, round((base_price * 0.24) / 100.0) * 100))
    board_cost    = int(max(6500, round((base_price * 0.36) / 100.0) * 100))

    return {
        "wholesale_inr": wholesale_inr,
        "minor_polish_qc_cost": polish_cost,
        "battery_repair_cost": battery_cost,
        "housing_backglass_cost": housing_cost,
        "screen_repair_cost": screen_repair,
        "board_ic_repair_cost": board_cost,
    }


class GradingEngine:
    """Applies standard refurbished device grading factors to baseline prices."""

    def __init__(self, tiers: Optional[Dict] = None):
        self.tiers = tiers or CONDITION_TIERS

    def generate_graded_records(
        self, baseline_record: MobilePriceRecord
    ) -> List[MobilePriceRecord]:
        """
        Takes a verified baseline (Grade A) record and generates the full condition
        matrix records (Grade B, Grade C, Grade D, Grade E) with calibrated defect deductions.
        """
        graded_records: List[MobilePriceRecord] = []
        base_price = int(baseline_record.buyback_price)
        benchmarks = compute_repair_benchmarks(base_price)

        for grade_name, grade_info in self.tiers.items():
            factor = grade_info["factor"]
            adjusted_price = int(round(base_price * factor / 100.0) * 100) if factor < 1.0 else base_price

            # Skip Grade A if generating simulated secondary grades
            if factor >= 1.00:
                continue

            grade_code = grade_info.get("grade_code", grade_name.split()[0])
            
            # Calibrate defect text and repair deduction
            if grade_code == "Grade B":
                deduction = float(benchmarks["minor_polish_qc_cost"])
                defects_text = f"Minor signs of use · Est. QC/Polish cost: ₹{int(deduction)}"
            elif grade_code == "Grade C":
                deduction = float(benchmarks["battery_repair_cost"] + benchmarks["housing_backglass_cost"])
                defects_text = f"Aged battery / housing wear · Est. Battery+Housing repair: ₹{int(deduction)}"
            elif grade_code == "Grade D":
                deduction = float(benchmarks["screen_repair_cost"])
                defects_text = f"Cracked screen / display lines · Est. Screen replacement cost: ₹{int(deduction)}"
            elif grade_code == "Grade E":
                deduction = float(benchmarks["board_ic_repair_cost"])
                defects_text = f"Dead display + board issue · Est. Board+Screen repair cost: ₹{int(deduction)}"
            else:
                deduction = float(round(base_price * (1.0 - factor)))
                defects_text = grade_info.get("defects", "Condition wear")

            record = MobilePriceRecord(
                brand=baseline_record.brand,
                model=baseline_record.model,
                model_series=baseline_record.model_series,
                variant=baseline_record.variant or baseline_record.storage,
                storage=baseline_record.storage,
                storage_gb=baseline_record.storage_gb,
                ram=baseline_record.ram,
                ram_gb=baseline_record.ram_gb,
                cores=baseline_record.cores,
                camera=baseline_record.camera,
                condition=grade_code,
                condition_grade=grade_code,
                defects=defects_text,
                max_advertised_price=float(base_price),
                condition_deductions=deduction,
                buyback_price=adjusted_price,
                price=float(adjusted_price),
                source_url=baseline_record.source_url,
                timestamp=datetime.now(timezone.utc).isoformat(),
                data_origin="sample_condition_graded",
                currency=baseline_record.currency or "INR",
                confidence_score=0.85,
                device_id=baseline_record.device_id,
                report_id=baseline_record.report_id,
                report_day=baseline_record.report_day,
                report_time=baseline_record.report_time,
                report_bucket=baseline_record.report_bucket,
            )
            graded_records.append(record)

        return graded_records

    def build_full_dataset(
        self,
        verified_records: List[MobilePriceRecord],
        include_grading_matrix: bool = True,
        include_matrix: Optional[bool] = None,
        **kwargs
    ) -> List[MobilePriceRecord]:
        """
        Builds complete dataset containing verified scraped records (normalized as Grade A)
        and optionally appends condition-graded benchmark records (Grade B, C, D, E).
        """
        use_matrix = include_matrix if include_matrix is not None else include_grading_matrix
        all_records: List[MobilePriceRecord] = []

        for rec in verified_records:
            # Normalize baseline record to Grade A
            base_price = float(rec.buyback_price)
            normalized_rec = MobilePriceRecord(
                brand=rec.brand,
                model=rec.model,
                model_series=rec.model_series,
                variant=rec.variant or rec.storage,
                storage=rec.storage,
                storage_gb=rec.storage_gb,
                ram=rec.ram,
                ram_gb=rec.ram_gb,
                cores=rec.cores,
                camera=rec.camera,
                condition="Grade A",
                condition_grade="Grade A",
                defects="Flawless condition, zero scratches (Repair cost: ₹0)",
                max_advertised_price=base_price,
                condition_deductions=0.0,
                buyback_price=int(base_price),
                price=base_price,
                source_url=rec.source_url,
                timestamp=rec.timestamp or datetime.now(timezone.utc).isoformat(),
                data_origin=rec.data_origin or "verified_scraped",
                currency=rec.currency or "INR",
                confidence_score=rec.confidence_score or 1.0,
                device_id=rec.device_id,
                report_id=rec.report_id,
                report_day=rec.report_day,
                report_time=rec.report_time,
                report_bucket=rec.report_bucket,
            )
            all_records.append(normalized_rec)

            if use_matrix:
                simulated = self.generate_graded_records(normalized_rec)
                all_records.extend(simulated)

        return all_records
