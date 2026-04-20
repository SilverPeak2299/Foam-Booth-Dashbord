# Gemini Task: Structure Foam Booth Sales Data

You are in the Foam Booth dashboard `data-processing` worktree.

The source data is here:

```text
data/gemini_source/stage_1_output_no_customer.csv
```

This CSV has already had the customer column removed. Use it as the source of truth. Do not modify it.

## Goal

Convert the sales line items into structured JSONL suitable for a static dashboard. The dashboard needs analytics for:

- foam popularity by year, month, and Australian season
- foam type rankings
- foam thickness rankings
- indoor vs outdoor foam trends
- fabric rankings
- inferred indoor/outdoor-suitable fabric classification
- data quality and low-confidence review counts

## Source Columns

The CSV columns are:

```text
"", Date, Invoice #, Item Number, Quantity, Description, Price, Total
```

Use the blank first column as `source_row_id`.

## Output Files

Create these files:

```text
data/gemini_output/semantic_line_items.jsonl
data/gemini_output/semantic_summary.json
data/gemini_output/review_needed.csv
```

If the full CSV is too large for one pass, process it in batches and checkpoint progress:

```text
data/gemini_output/batches/batch_0001.jsonl
data/gemini_output/batches/batch_0002.jsonl
data/gemini_output/progress.json
```

Then merge completed batches into `semantic_line_items.jsonl`.

## Output Schema

Every line in `semantic_line_items.jsonl` must be one JSON object matching:

```json
{
  "source_row_id": 0,
  "date": "2025-04-05",
  "invoice_id": "6814",
  "item_number": "Miscellaneous",
  "quantity": 1.0,
  "price": 527.27,
  "total": 527.27,
  "category": "foam",
  "product_type": "foam",
  "foam_code": "31/200R",
  "foam_density": 31,
  "foam_firmness": 200,
  "foam_thickness_mm": 50,
  "foam_environment": "outdoor",
  "dimensions_mm": {
    "length": 1730,
    "width": 1000,
    "height": 50
  },
  "piece_count": 2,
  "fabric_name": null,
  "fabric_brand": null,
  "fabric_length_m": null,
  "fabric_environment": null,
  "fabric_environment_confidence": null,
  "fabric_environment_reason": null,
  "is_non_product": false,
  "skip_reason": null,
  "confidence": 0.86,
  "review_needed": false,
  "evidence": ["Outdoor", "1000*1730", "2 inch thickness"]
}
```

Use `null` when a field is unknown or not applicable.

## Category Values

Use exactly one of:

```text
foam
fabric
dacron
covers_upholstery
delivery
discount
banking_non_product
other_product
unknown
```

## Foam Rules

Extract foam details from `Item Number` and `Description`.

Common mappings:

- `HD`, `High Density`, `High Dense`, seating foam: usually `29/200` unless another code is explicit.
- `MD`, `Medium Density`, `Medium Dense`: usually `23/130` unless another code is explicit.
- `Premium Medium Density`, mattress foam: often `30/130` unless another code is explicit.
- `Outdoor`, `Dryflow`, `Dricell`: outdoor foam.
- Foam codes ending in `R`, such as `31/200R` or `27/120R`, are outdoor foam.

Thickness:

- Inch values like `2"` or `4"` are thickness. Convert to mm with `inch * 25.4`, rounded to nearest whole mm.
- Explicit values like `75mm`, `100 mm`, `150mm thick` are thickness when context supports it.
- If dimensions are present but orientation is ambiguous, fill what is clear and set lower confidence.

Seasonality:

- Australian summer: December, January, February.
- Autumn: March, April, May.
- Winter: June, July, August.
- Spring: September, October, November.

## Fabric Rules

Extract fabric brand/name and length where possible.

Fabric environment is an inference, not a fact:

- `Sunbrella`, `Dickson`, `Sauleda`, marine, awning, and clearly outdoor terms are high-confidence `outdoor_suitable`.
- Explicit outdoor wording in the fabric description is medium-to-high confidence.
- If a fabric appears on the same invoice as outdoor foam, that is only low-confidence evidence.
- Do not classify a fabric as indoor just because no outdoor signal exists. Use `unknown` unless indoor-only evidence is explicit.

## Non-Product Rules

- Discounts, `Less`, refunds, credits, and negative adjustments: `discount`.
- Banking details, BSB, account details: `banking_non_product`.
- Delivery/freight/courier/shipping: `delivery`.
- Dacron, Dacon, wadding, wrap: `dacron`.
- Covers, sewing, zips, upholstery labor, velcro: `covers_upholstery`.

## Review Rules

Set `review_needed: true` when:

- category is `unknown`
- confidence is below `0.70`
- dimensions are ambiguous but important
- fabric name looks like it may be a customer/person rather than a product
- one line appears to contain multiple bundled products that cannot be separated cleanly

Write review rows to `data/gemini_output/review_needed.csv` with:

```text
source_row_id,date,invoice_id,item_number,description,reason
```

## Summary File

Create `data/gemini_output/semantic_summary.json` with:

- source file path
- generated timestamp
- source row count
- processed row count
- category counts
- review-needed count
- confidence distribution
- foam code counts
- foam thickness counts
- fabric brand/name counts
- fabric environment counts
- notes about assumptions or unresolved patterns

## Important

- Do not remove or edit `data/gemini_source/stage_1_output_no_customer.csv`.
- Prefer completing the work in batches rather than trying to hold the whole file in context.
- Preserve every source row in the final JSONL, even if category is `unknown`.
- Keep output machine-readable. JSONL must contain valid JSON only, one object per line.

