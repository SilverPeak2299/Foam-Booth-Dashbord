#!/usr/bin/env python3
"""Patch the first semantic extraction with deterministic cleanup rules.

This is intentionally conservative. It does not call an LLM and it does not
recreate the full semantic extraction. It only:
- recategorizes v1 rows that were left as category=unknown when source text has
  a deterministic product/non-product signal
- enforces the deterministic foam environment rule from foam_code
- fills foam code density/firmness and obvious thickness where recoverable
- fills basic fabric fields from metre/brand descriptions where recoverable
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SOURCE_CSV = Path("data/gemini_source/stage_1_output_no_customer.csv")
SEMANTIC_JSONL = Path("data/gemini_output/semantic_line_items.jsonl")
SUMMARY_JSON = Path("data/gemini_output/semantic_summary.json")
VALIDATION_JSON = Path("data/gemini_output/validation_report.json")
REPORT_JSON = Path("data/gemini_output/v1_unknown_patch_report.json")

FOAM_CODE_RE = re.compile(r"(?<!\d)(?:AA|MA|EN|D|N|F|VF)?(\d{2})[-/](\d{1,3})(R?)(?!\d)", re.I)
INCH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\"|inch(?:es)?)", re.I)
CM_HIGH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*cm\s*(?:h(?:ei)?ght|high|hight)", re.I)
MM_HIGH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mm\s*(?:thick|h(?:ei)?ght|high|hight)", re.I)
MM_THICK_ITEM_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*mm\b", re.I)
FABRIC_LENGTH_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:x\s*)?(?:metres?|meters?|mtrs?|mtr)\b", re.I)
FABRIC_SHORT_LENGTH_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*m\b", re.I)
DIMENSION_ONLY_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:x|\*)\s*\d+(?:\.\d+)?\s*(?:cm|mm)?\b", re.I)

FOAM_KEYWORDS_RE = re.compile(
    r"\b(foam|mattress|wedge|wedges|overlay|bolster|swag|bed in bag|bassinet|bassinett|"
    r"cushion|eva|dryflow|dricell|dri\s*cell|pillow|futon|sit\s*&?\s*sleep)\b",
    re.I,
)
FOAM_ITEM_RE = re.compile(
    r"^(?:F\d|S?\d+(?:\.\d+)?\"|\d+(?:\.\d+)?\"|[A-Z]*HD|[A-Z]*MD|HR|MS|MKS|"
    r"MSWAG|MSFOLD|MFOLD|WEDG|WEDGE|OQ|OKB|OS|OD|KS|QS|DB|SB)",
    re.I,
)
DACRON_RE = re.compile(r"\b(dacron|wadding|d\d{2}\b)", re.I)
COVER_RE = re.compile(r"\b(cover|covers|sewing|upholstery|zip|zipper|piping|calico|stitch|making)\b", re.I)
DELIVERY_RE = re.compile(r"\b(deliv\w*|delvery|delivey|delviery|freight|courier|shipping|pickup|pick up)\b", re.I)
DISCOUNT_RE = re.compile(r"\b(discount|refund|credit|return|equalization|equalisation)\b", re.I)
BANK_RE = re.compile(r"\b(bsb|bank\s*a/?c|banking details|account details|acct)\b", re.I)
OTHER_RE = re.compile(r"\b(glue|gluing|cutting fee|interlock|webbing|velcro|spray|hinge|button|thread|elastic|staple|castor)\b", re.I)
FABRIC_MATERIAL_RE = re.compile(r"\b(nu-?suede|suede|vinyl|canvas|anahide|fabric|material|commercial grade)\b", re.I)

FABRIC_BRANDS = {
    "sunbrella": "Sunbrella",
    "warwick": "Warwick",
    "dickson": "Dickson",
    "vistaweave": "Vistaweave",
    "keylargo": "Keylargo",
    "sauleda": "Sauleda",
    "gilda": "Gilda",
    "ashcroft": "Ashcroft",
    "oscar": "Oscar",
    "bingo": "Bingo",
    "tempotest": "Tempotest",
}
OUTDOOR_FABRIC_BRANDS = {"Sunbrella", "Dickson", "Vistaweave", "Keylargo", "Sauleda", "Tempotest"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, default=SOURCE_CSV)
    parser.add_argument("--semantic-jsonl", type=Path, default=SEMANTIC_JSONL)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--validation-json", type=Path, default=VALIDATION_JSON)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_source(path: Path) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {int(float(row[""])): row for row in rows}


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def source_text(row: dict[str, str]) -> str:
    return f"{row.get('Item Number') or ''} {row.get('Description') or ''}".strip()


def parse_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def parse_foam_code(text: str) -> str | None:
    for match in FOAM_CODE_RE.finditer(text):
        density = int(match.group(1))
        firmness = int(match.group(2))
        if 10 <= density <= 90 and 10 <= firmness <= 800:
            return f"{density:02d}/{firmness}{match.group(3).upper()}"
    return None


def split_foam_code(code: str | None) -> tuple[int | None, int | None]:
    if not code:
        return None, None
    match = re.match(r"^(\d{2})/(\d{1,3})R?$", code)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_thickness_mm(text: str, record: dict) -> int | None:
    for pattern, multiplier in [(INCH_RE, 25.4), (CM_HIGH_RE, 10), (MM_HIGH_RE, 1)]:
        match = pattern.search(text)
        if match:
            value = float(match.group(1)) * multiplier
            if 1 <= value <= 300:
                return int(round(value))
    item_number = text.split(" ", 1)[0]
    match = MM_THICK_ITEM_RE.search(item_number)
    if match:
        value = float(match.group(1))
        if 1 <= value <= 300:
            return int(round(value))
    dims = record.get("dimensions_mm")
    height = dims.get("height") if isinstance(dims, dict) else None
    if isinstance(height, (int, float)) and 1 <= height <= 300:
        return int(round(height))
    return None


def parse_piece_count(text: str) -> int | None:
    match = re.search(r"\b(\d+)\s*(?:pieces?|pcs)\b", text, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d+)\s*x\s*\d", text, re.I)
    if match:
        count = int(match.group(1))
        if 1 <= count <= 20:
            return count
    return None


def infer_fabric_brand(text: str) -> str | None:
    lowered = text.lower()
    for needle, brand in FABRIC_BRANDS.items():
        if needle in lowered:
            return brand
    return None


def parse_fabric_name(text: str, brand: str | None) -> str | None:
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\s*(?:x\s*)?(?:metres?|meters?|mtrs?|mtr|m)\b", "", text, flags=re.I)
    cleaned = re.sub(r"\bMiscellaneous\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:,")
    if brand:
        cleaned = re.sub(re.escape(brand), "", cleaned, flags=re.I).strip(" -:,")
    return cleaned or brand


def classify_unknown(row: dict[str, str]) -> str | None:
    text = source_text(row)
    lowered = text.lower()
    total = parse_float(row.get("Total")) or 0.0
    if BANK_RE.search(text):
        return "banking_non_product"
    if DELIVERY_RE.search(text):
        return "delivery"
    if DISCOUNT_RE.search(text) and total <= 0:
        return "discount"
    if DACRON_RE.search(text):
        return "dacron"
    if (row.get("Item Number") or "").upper().startswith("IT"):
        return "other_product"
    if parse_foam_code(text) or FOAM_KEYWORDS_RE.search(text) or FOAM_ITEM_RE.search(row.get("Item Number") or ""):
        return "foam"
    if infer_fabric_brand(text) or FABRIC_LENGTH_RE.search(text) or "outdoor vinyl" in lowered:
        return "fabric"
    if FABRIC_SHORT_LENGTH_RE.search(text) and FABRIC_MATERIAL_RE.search(text):
        return "fabric"
    if DIMENSION_ONLY_RE.search(text):
        return "foam"
    if COVER_RE.search(text):
        return "covers_upholstery"
    if OTHER_RE.search(text):
        return "other_product"
    return None


def patch_foam(record: dict, text: str, stats: Counter) -> None:
    before_env = record.get("foam_environment")
    before_code = record.get("foam_code")
    code = before_code or parse_foam_code(text)
    if code:
        code = code.upper()
        record["foam_code"] = code
        density, firmness = split_foam_code(code)
        if density is not None:
            record["foam_density"] = density
        if firmness is not None:
            record["foam_firmness"] = firmness
        record["foam_environment"] = "outdoor" if code.endswith("R") else "indoor"
    else:
        record["foam_environment"] = "unknown"
    if before_env != record.get("foam_environment"):
        stats["foam_environment_patched"] += 1
    if before_code != record.get("foam_code"):
        stats["foam_code_patched"] += 1

    thickness = record.get("foam_thickness_mm") or parse_thickness_mm(text, record)
    if thickness:
        if record.get("foam_thickness_mm") != thickness:
            stats["foam_thickness_patched"] += 1
        record["foam_thickness_mm"] = thickness

    piece_count = record.get("piece_count") or parse_piece_count(text)
    if piece_count:
        if record.get("piece_count") != piece_count:
            stats["piece_count_patched"] += 1
        record["piece_count"] = piece_count


def patch_fabric(record: dict, text: str, stats: Counter) -> None:
    brand = record.get("fabric_brand") or infer_fabric_brand(text)
    length_match = FABRIC_LENGTH_RE.search(text) or (
        FABRIC_SHORT_LENGTH_RE.search(text) if FABRIC_MATERIAL_RE.search(text) else None
    )
    fabric_length = record.get("fabric_length_m")
    if fabric_length in (None, "") and length_match:
        fabric_length = float(length_match.group(1))
        stats["fabric_length_patched"] += 1
    if brand and record.get("fabric_brand") != brand:
        record["fabric_brand"] = brand
        stats["fabric_brand_patched"] += 1
    name = record.get("fabric_name") or parse_fabric_name(text, brand)
    if name and record.get("fabric_name") != name:
        record["fabric_name"] = name
        stats["fabric_name_patched"] += 1
    if fabric_length not in (None, ""):
        record["fabric_length_m"] = fabric_length
    lowered = text.lower()
    if brand in OUTDOOR_FABRIC_BRANDS or any(word in lowered for word in ["outdoor", "marine", "vinyl"]):
        record["fabric_environment"] = "outdoor_suitable"
        record["fabric_environment_confidence"] = record.get("fabric_environment_confidence") or 0.85
        record["fabric_environment_reason"] = record.get("fabric_environment_reason") or "Deterministic brand or outdoor keyword"
    else:
        record["fabric_environment"] = record.get("fabric_environment") or "unknown"


def patch_records(records: list[dict], source_by_id: dict[int, dict[str, str]]) -> tuple[list[dict], dict]:
    stats: Counter = Counter()
    recategorized: Counter = Counter()
    still_unknown_examples = []

    for record in records:
        source_row = source_by_id.get(record["source_row_id"])
        text = source_text(source_row) if source_row else ""

        if record.get("category") == "unknown":
            category = classify_unknown(source_row or {})
            if category:
                record["category"] = category
                record["product_type"] = category if category not in {"delivery", "discount", "banking_non_product"} else None
                record["skip_reason"] = None
                record["review_needed"] = False
                record["confidence"] = max(float(record.get("confidence") or 0.0), 0.8)
                record["is_non_product"] = category in {"delivery", "discount", "banking_non_product"}
                recategorized[category] += 1
            else:
                record["review_needed"] = True
                if len(still_unknown_examples) < 25:
                    still_unknown_examples.append(
                        {
                            "source_row_id": record["source_row_id"],
                            "item_number": source_row.get("Item Number") if source_row else None,
                            "description": source_row.get("Description") if source_row else None,
                        }
                    )

        if record.get("category") == "foam":
            record["product_type"] = record.get("product_type") or "foam"
            record["is_non_product"] = False
            patch_foam(record, text, stats)
        elif record.get("category") == "fabric":
            record["product_type"] = record.get("product_type") or "fabric"
            record["is_non_product"] = False
            patch_fabric(record, text, stats)

    category_counts = Counter(record.get("category") for record in records)
    foam_env_counts = Counter(record.get("foam_environment") for record in records if record.get("category") == "foam")
    fabric_env_counts = Counter(record.get("fabric_environment") for record in records if record.get("category") == "fabric")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(records),
        "recategorized_unknown_rows": dict(recategorized),
        "remaining_unknown_rows": category_counts.get("unknown", 0),
        "patch_counts": dict(stats),
        "category_counts": dict(category_counts),
        "foam_environment_counts": {str(key): value for key, value in foam_env_counts.items()},
        "fabric_environment_counts": {str(key): value for key, value in fabric_env_counts.items()},
        "still_unknown_examples": still_unknown_examples,
        "notes": [
            "Patched from no-customer source CSV with deterministic regex rules only.",
            "Foam environment rule: foam_code ending R => outdoor; foam_code present without R => indoor; missing foam_code => unknown.",
        ],
    }
    return records, report


def write_jsonl(path: Path, records: list[dict]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    tmp_path.replace(path)


def update_summary(path: Path, report: dict) -> None:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    payload["patched_at"] = report["generated_at"]
    payload["processed_row_count"] = report["row_count"]
    payload["category_counts"] = report["category_counts"]
    payload["foam_environment_counts"] = report["foam_environment_counts"]
    payload["fabric_environment_counts"] = report["fabric_environment_counts"]
    payload["review_needed_count"] = report["remaining_unknown_rows"]
    notes = payload.setdefault("notes", [])
    note = "v1 unknown rows patched with deterministic no-PII source rules."
    if note not in notes:
        notes.append(note)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_validation(path: Path, report: dict) -> None:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    payload["patched_at"] = report["generated_at"]
    payload["category_counts"] = report["category_counts"]
    payload["review_needed_count"] = report["remaining_unknown_rows"]
    payload["foam_environment_counts"] = report["foam_environment_counts"]
    payload["fabric_environment_counts"] = report["fabric_environment_counts"]
    payload["v1_unknown_patch_report"] = str(REPORT_JSON)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_by_id = read_source(args.source_csv)
    records = read_jsonl(args.semantic_jsonl)
    records, report = patch_records(records, source_by_id)

    print(json.dumps(report, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    write_jsonl(args.semantic_jsonl, records)
    args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_summary(args.summary_json, report)
    update_validation(args.validation_json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
