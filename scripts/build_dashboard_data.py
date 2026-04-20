#!/usr/bin/env python3
"""Build aggregate JSON artifacts for the static dashboard."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


SOURCE = Path("data/gemini_output/semantic_line_items.jsonl")
VALIDATION = Path("data/gemini_output/validation_report.json")
SUMMARY = Path("data/gemini_output/semantic_summary.json")
OUT_DIR = Path("public/data")

NON_PRODUCT_CATEGORIES = {"discount", "delivery", "banking_non_product"}
PRODUCT_CATEGORIES = {"foam", "fabric", "dacron", "covers_upholstery", "other_product", "unknown"}
MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def parse_date(value: str) -> tuple[int | None, int | None, str | None]:
    if not value:
        return None, None, None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None, None, None
    return parsed.year, parsed.month, f"{parsed.year:04d}-{parsed.month:02d}"


def season_au(month: int | None) -> str | None:
    if month is None:
        return None
    if month in {12, 1, 2}:
        return "summer"
    if month in {3, 4, 5}:
        return "autumn"
    if month in {6, 7, 8}:
        return "winter"
    return "spring"


def add_metric(bucket: dict, total: float, invoice_id: str | None, confidence: float | None) -> None:
    bucket["revenue"] += total
    bucket["line_count"] += 1
    if invoice_id:
        bucket["invoice_ids"].add(invoice_id)
    if isinstance(confidence, (int, float)):
        bucket["confidence_sum"] += confidence
        bucket["confidence_count"] += 1


def metric_bucket() -> dict:
    return {"revenue": 0.0, "line_count": 0, "invoice_ids": set(), "confidence_sum": 0.0, "confidence_count": 0}


def finalize_metric(key: str, bucket: dict) -> dict:
    confidence_count = bucket["confidence_count"]
    return {
        "key": key,
        "revenue": round(bucket["revenue"], 2),
        "line_count": bucket["line_count"],
        "invoice_count": len(bucket["invoice_ids"]),
        "avg_confidence": round(bucket["confidence_sum"] / confidence_count, 3) if confidence_count else None,
    }


def top_counter(counter: Counter, limit: int = 20) -> list[dict]:
    return [{"key": key, "count": count} for key, count in counter.most_common(limit)]


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    total_revenue = 0.0
    product_revenue = 0.0
    gross_positive_revenue = 0.0
    invoice_ids: set[str] = set()
    date_values: list[str] = []
    confidence_values: list[float] = []
    review_needed = 0

    category = defaultdict(metric_bucket)
    monthly = defaultdict(metric_bucket)
    yearly = defaultdict(metric_bucket)
    category_monthly = defaultdict(metric_bucket)
    foam_code = defaultdict(metric_bucket)
    foam_thickness = defaultdict(metric_bucket)
    foam_environment = defaultdict(metric_bucket)
    foam_month = defaultdict(metric_bucket)
    foam_code_month = defaultdict(metric_bucket)
    foam_thickness_month = defaultdict(metric_bucket)
    foam_env_month = defaultdict(metric_bucket)
    foam_code_season = defaultdict(metric_bucket)
    foam_thickness_season = defaultdict(metric_bucket)
    fabric_name = defaultdict(metric_bucket)
    fabric_brand = defaultdict(metric_bucket)
    fabric_environment = defaultdict(metric_bucket)
    fabric_month = defaultdict(metric_bucket)
    fabric_env_month = defaultdict(metric_bucket)
    confidence_bucket = Counter()
    category_counts = Counter()
    review_by_category = Counter()
    unknown_by_month = Counter()

    for record in read_jsonl(args.source):
        total_rows += 1
        cat = record.get("category") or "unknown"
        category_counts[cat] += 1
        invoice_id = str(record.get("invoice_id") or "")
        if invoice_id:
            invoice_ids.add(invoice_id)
        total = record.get("total")
        total = float(total) if isinstance(total, (int, float)) else 0.0
        confidence = record.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence_values.append(float(confidence))
            confidence_bucket[f"{int(confidence * 10) / 10:.1f}"] += 1
        year, month, month_key = parse_date(record.get("date") or "")
        season = season_au(month)
        if record.get("date"):
            date_values.append(record["date"])

        total_revenue += total
        if total > 0:
            gross_positive_revenue += total
        if cat in PRODUCT_CATEGORIES and total > 0 and not record.get("is_non_product"):
            product_revenue += total

        if record.get("review_needed"):
            review_needed += 1
            review_by_category[cat] += 1

        add_metric(category[cat], total, invoice_id, confidence)
        if month_key:
            add_metric(monthly[month_key], total, invoice_id, confidence)
            add_metric(category_monthly[f"{month_key}|{cat}"], total, invoice_id, confidence)
            if cat == "unknown":
                unknown_by_month[month_key] += 1
        if year:
            add_metric(yearly[str(year)], total, invoice_id, confidence)

        if cat == "foam":
            code = record.get("foam_code") or "unknown"
            thickness = record.get("foam_thickness_mm")
            thickness_key = str(int(round(thickness))) if isinstance(thickness, (int, float)) and thickness > 0 else "unknown"
            env = record.get("foam_environment") or "unknown"
            add_metric(foam_code[code], total, invoice_id, confidence)
            add_metric(foam_thickness[thickness_key], total, invoice_id, confidence)
            add_metric(foam_environment[env], total, invoice_id, confidence)
            if month_key:
                add_metric(foam_month[month_key], total, invoice_id, confidence)
                add_metric(foam_code_month[f"{month_key}|{code}"], total, invoice_id, confidence)
                add_metric(foam_thickness_month[f"{month_key}|{thickness_key}"], total, invoice_id, confidence)
                add_metric(foam_env_month[f"{month_key}|{env}"], total, invoice_id, confidence)
            if season and year:
                add_metric(foam_code_season[f"{year}|{season}|{code}"], total, invoice_id, confidence)
                add_metric(foam_thickness_season[f"{year}|{season}|{thickness_key}"], total, invoice_id, confidence)

        if cat == "fabric":
            name = record.get("fabric_name") or "unknown"
            brand = record.get("fabric_brand") or "unknown"
            env = record.get("fabric_environment") or "unknown"
            add_metric(fabric_name[name], total, invoice_id, confidence)
            add_metric(fabric_brand[brand], total, invoice_id, confidence)
            add_metric(fabric_environment[env], total, invoice_id, confidence)
            if month_key:
                add_metric(fabric_month[month_key], total, invoice_id, confidence)
                add_metric(fabric_env_month[f"{month_key}|{env}"], total, invoice_id, confidence)

    def finalized_series(mapping: dict, split_keys: tuple[str, ...] = ()) -> list[dict]:
        rows = []
        for key, bucket in mapping.items():
            row = finalize_metric(str(key), bucket)
            if split_keys:
                parts = str(key).split("|")
                for name, value in zip(split_keys, parts):
                    row[name] = value
            rows.append(row)
        return sorted(rows, key=lambda row: row.get("key", ""))

    def finalized_top(mapping: dict, limit: int = 30) -> list[dict]:
        rows = [finalize_metric(str(key), bucket) for key, bucket in mapping.items()]
        return sorted(rows, key=lambda row: row["revenue"], reverse=True)[:limit]

    validation = json.loads(VALIDATION.read_text(encoding="utf-8")) if VALIDATION.exists() else {}
    semantic_summary = json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {}

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source),
        "row_count": total_rows,
        "invoice_count": len(invoice_ids),
        "date_min": min(date_values) if date_values else None,
        "date_max": max(date_values) if date_values else None,
        "gross_total": round(total_revenue, 2),
        "gross_positive_revenue": round(gross_positive_revenue, 2),
        "product_revenue": round(product_revenue, 2),
        "review_needed_count": review_needed,
        "review_needed_rate": round(review_needed / total_rows, 4) if total_rows else 0,
        "average_confidence": round(mean(confidence_values), 3) if confidence_values else None,
        "category_counts": dict(category_counts),
        "validation_integrity_passed": validation.get("passed_integrity"),
        "semantic_summary_notes": semantic_summary.get("notes", []),
    }

    outputs = {
        "summary.json": summary,
        "monthly_sales.json": {
            "monthly": finalized_series(monthly),
            "yearly": finalized_series(yearly),
            "category_monthly": finalized_series(category_monthly, ("month", "category")),
        },
        "product_mix.json": {
            "category": sorted([finalize_metric(k, v) for k, v in category.items()], key=lambda row: row["revenue"], reverse=True),
            "category_counts": dict(category_counts),
            "review_by_category": dict(review_by_category),
            "unknown_by_month": dict(sorted(unknown_by_month.items())),
        },
        "foam_analytics.json": {
            "top_codes": finalized_top(foam_code),
            "top_thicknesses": finalized_top(foam_thickness),
            "environment": sorted([finalize_metric(k, v) for k, v in foam_environment.items()], key=lambda row: row["revenue"], reverse=True),
            "monthly": finalized_series(foam_month),
            "code_monthly": finalized_series(foam_code_month, ("month", "foam_code")),
            "thickness_monthly": finalized_series(foam_thickness_month, ("month", "thickness_mm")),
            "environment_monthly": finalized_series(foam_env_month, ("month", "environment")),
            "code_season": finalized_series(foam_code_season, ("year", "season", "foam_code")),
            "thickness_season": finalized_series(foam_thickness_season, ("year", "season", "thickness_mm")),
        },
        "fabric_analytics.json": {
            "top_names": finalized_top(fabric_name),
            "top_brands": finalized_top(fabric_brand),
            "environment": sorted([finalize_metric(k, v) for k, v in fabric_environment.items()], key=lambda row: row["revenue"], reverse=True),
            "monthly": finalized_series(fabric_month),
            "environment_monthly": finalized_series(fabric_env_month, ("month", "environment")),
        },
        "data_quality.json": {
            "validation": validation,
            "confidence_distribution": dict(sorted(confidence_bucket.items())),
            "review_by_category": dict(review_by_category),
            "low_confidence_not_reviewed": validation.get("low_confidence_not_reviewed", {}),
            "dimension_quality_examples": validation.get("dimension_quality_examples", []),
        },
    }

    for filename, payload in outputs.items():
        (args.out_dir / filename).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {len(outputs)} dashboard data files to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

