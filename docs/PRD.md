# Foam Booth Sales Analytics Dashboard PRD

## 1. Purpose

Build a static GitHub Pages dashboard that turns Foam Booth sales history into clear, browsable analytics for sales trends, ordering patterns, product mix, foam/fabric rankings, and data quality.

The dashboard should be useful before the free-text semantic extraction is perfect. Version 1 should rely on deterministic, precomputed analytics from the semi-prepared CSV, then add an auditable LLM enrichment pipeline as a later layer.

## 2. Background

The prior analysis work lives in `../Foam-Booth-Data-Analysis`.

Key inputs found there:

- Raw sales export: `../Foam-Booth-Data-Analysis/data/data.txt`
- Semi-prepared CSV: `../Foam-Booth-Data-Analysis/data/stage_1_output.txt`
- Prior LLM prompt/schema: `../Foam-Booth-Data-Analysis/scripts/gemini_request.py`
- Prior LLM batch runner: `../Foam-Booth-Data-Analysis/scripts/llm_processing.py`
- Prior notebooks: `../Foam-Booth-Data-Analysis/notebooks/`

Current usable data facts from `stage_1_output.txt`:

- 83,107 prepared line items.
- 39,231 unique invoices.
- Date range: 2006-11-09 to 2025-05-02.
- Top-level fields: `Co./Last Name`, `Date`, `Invoice #`, `Item Number`, `Quantity`, `Description`, `Price`, `Total`.
- About 48.5% of prepared rows still have `Item Number = Miscellaneous`.
- Free-text descriptions contain major business signal, including foam type, dimensions, fabric names, banking notes, Dacron, covers, sewing, and bundled line items.

The prior LLM pipeline should not be reused as-is for production dashboard data. It processed only 10 rows per run, wrote directly to Supabase instead of durable output files, had schema/prompt/validation mismatches, and did not produce a complete enriched dataset.

## 3. Product Goals

1. Provide a static dashboard that can be deployed through GitHub Pages.
2. Show reliable sales and ordering trends from the available historical data.
3. Rank fabrics, foam types, foam thicknesses, product categories, and item codes where confidence is sufficient.
4. Make uncertain or unparsed data visible rather than hiding it.
5. Keep semantic enrichment offline and reproducible so the static site only consumes prepared JSON/CSV artifacts.
6. Publish through GitHub Pages/GitHub Actions with no PII committed to this public repo and no PII emitted in the static site.

## 4. Non-Goals

1. No live database dependency for the dashboard.
2. No client-side LLM calls.
3. No Supabase dependency for version 1.
4. No private/authenticated dashboard through GitHub Pages alone.
5. No claim that semantic extraction is complete until the enrichment pipeline includes validation and review outputs.

## 5. Users

Primary user: Foam Booth operator/analyst who wants to understand historical sales, popular products, ordering cycles, and fabric/foam demand.

Secondary user: developer/maintainer updating the dataset, improving extraction, and publishing dashboard updates.

## 6. Privacy And Publishing Policy

The dashboard will be public because it is deployed from a public repo to GitHub Pages through GitHub Actions. All committed files and all deployed static files must be treated as public.

Required publishing rules:

- Publish aggregate metrics only.
- Do not commit raw customer names.
- Do not commit raw free-text descriptions.
- Do not deploy raw customer names.
- Do not deploy raw free-text descriptions.
- Do not commit the original raw or stage-1 source file unless it has first been sanitized.
- Sanitized source files must drop `Co./Last Name` and any other direct customer-name fields.
- Sanitized source files must not include raw descriptions unless a separate redaction pass proves they contain no PII or banking details.
- Customer repeat-order analytics should be omitted from public v1. If needed later, use a keyed HMAC generated with a GitHub Actions secret; do not commit the key or a reversible mapping table.

The repo should include a data source register documenting where source data came from, what transformations were applied, and which artifacts are safe to publish.

## 7. User Experience

The app should open directly to the analytics experience, with top-level tabs for focused pages. The interface should support date filtering and clear drilldowns without requiring the user to understand the raw CSV.

Planned tabs:

1. Overview
   - Total sales, invoice count, line count, average invoice value.
   - Current selected date range.
   - Year-over-year and month-over-month summaries.
   - Data coverage and confidence indicators.

2. Sales Trends
   - Monthly revenue trend.
   - Invoice count trend.
   - Average order value trend.
   - Seasonality by month and day of week.
   - Rolling averages for long-range smoothing.

3. Product Mix
   - Revenue and line-count split by deterministic category.
   - Top item numbers by revenue and count.
   - Discounts, delivery, non-product, and unknown/misc totals separated clearly.
   - Category trend over time.

4. Foam Analytics
   - Foam type rankings, such as `29/200`, `23/130`, `30/130`, `31/200R`, `27/120R`.
   - Indoor vs outdoor foam split where classification confidence allows.
   - Foam thickness popularity by month/season/year where thickness can be parsed from item number or description.
   - Foam type popularity by month/season/year.
   - Dimension summaries after enrichment is available.
   - Unclassified foam-like descriptions list as review counts, not raw text in public mode.

5. Fabric Analytics
   - Fabric name rankings by revenue and estimated meters.
   - Fabric trend over time.
   - Indoor/outdoor-suitable fabric classification with confidence labels.
   - Brand-based outdoor-suitable signals such as Sunbrella and Dickson.
   - Lower-confidence invoice-association signals when fabric appears with outdoor foam.
   - Unknown fabric-like descriptions count for review.
   - Supplier/brand rollups if reliable names can be extracted.

6. Customers
   - Excluded from public v1 because the repo and GitHub Pages deployment are public.
   - Future public-safe option: aggregate repeat-order cohorts using non-reversible keyed HMAC IDs generated outside the repo.

7. Data Quality
   - Missing value counts.
   - Rows dropped between raw and stage-1 data.
   - Unclassified/miscellaneous share over time.
   - Non-product rows detected, such as banking details and discounts.
   - Semantic extraction coverage and validation failure counts once LLM enrichment exists.

## 8. Data Pipeline Requirements

The static site should consume generated artifacts committed to the repo or produced during the GitHub Actions build.

Recommended artifact shape:

- `public/data/summary.json`
- `public/data/monthly_sales.json`
- `public/data/yearly_sales.json`
- `public/data/category_trends.json`
- `public/data/top_items.json`
- `public/data/top_foam_types.json`
- `public/data/foam_seasonality.json`
- `public/data/top_fabrics.json`
- `public/data/fabric_rankings.json`
- `public/data/fabric_environment.json`
- `public/data/data_quality.json`

Internal/generated-but-not-public artifacts may include:

- `data/processed/transactions.parquet` or `transactions.csv`
- `data/processed/classified_lines.jsonl`
- `data/processed/semantic_enrichment.jsonl`
- `data/review/semantic_failures.jsonl`
- `data/review/low_confidence_rows.csv`

The app should not parse the full raw CSV in the browser. Large parsing and aggregation should happen in a build step. Internal artifacts that contain customer names or raw descriptions must remain outside the public repo unless redacted.

## 9. Classification Strategy

Version 1 should implement deterministic classification first:

- `foam`: item numbers/descriptions matching foam types, density/firmness codes, HD/MD aliases, dryflow/dricell/outdoor terms.
- `fabric`: explicit fabric/fabric-brand/length terms.
- `dacron`: Dacron, Dacon, wadding, wrap.
- `covers_upholstery`: covers, sewing, zips, upholstery work.
- `delivery`: delivery or freight lines.
- `discount`: discounts, less, negative adjustment lines.
- `banking_non_product`: BSB, banking, account details.
- `other_product`: recognizable non-foam product lines.
- `unknown`: unclassified rows.

The deterministic classifier should assign:

- `category`
- `subcategory`
- `confidence`
- `classification_reason`
- `is_public_safe`

Foam-specific derived fields:

- `foam_code`, such as `29/200` or `31/200R`.
- `foam_density`.
- `foam_firmness`.
- `foam_thickness_mm`.
- `foam_environment`: `indoor`, `outdoor`, or `unknown`.
- `foam_environment_confidence`.

Fabric-specific derived fields:

- `fabric_name`.
- `fabric_brand`.
- `fabric_length_m`.
- `fabric_environment`: `outdoor_suitable`, `indoor`, or `unknown`.
- `fabric_environment_confidence`.
- `fabric_environment_reason`.

Fabric indoor/outdoor classification should be treated as an inference, not a fact. Brand terms like Sunbrella and Dickson can indicate outdoor-suitable fabric with higher confidence. Association with outdoor foam on the same invoice can be used only as a lower-confidence signal because customers may use outdoor fabrics indoors and vice versa.

LLM enrichment should come after this as an offline, resumable, audited pipeline, focused on rows that deterministic logic cannot confidently parse.

## 10. LLM Enrichment Requirements

The future LLM/subagent process should produce durable JSONL output and never write directly to the dashboard or database without validation.

Each enriched row should include:

- Original row ID.
- Invoice ID.
- Original item number.
- Private source row reference for offline validation only; do not publish raw descriptions or description hashes.
- Extracted product type.
- Foam density/firmness code when present.
- Outdoor/indoor flag when present.
- Dimensions in millimeters when parseable.
- Quantity/pieces/meters when parseable.
- Fabric name when parseable.
- Fabric indoor/outdoor-suitable inference when parseable, including reason and confidence.
- Skip/non-product reason when applicable.
- Confidence score.
- Validation status.
- Error message if rejected.
- Model/prompt version.

The LLM schema must use consistent names. Use `dimensions`, not `Dimentions`; use `invoice_id`, not `invoice number`.

## 11. Functional Requirements

1. The dashboard must load from GitHub Pages without a server.
2. The dashboard must support date range filtering across all analytics tabs.
3. All chart values must come from precomputed artifacts, not live database calls.
4. The dashboard must display when data was generated and from which source file.
5. The dashboard must expose data quality warnings when categories or periods have low confidence.
6. The dashboard must be usable on desktop and mobile.
7. The dashboard must handle empty filters and missing metrics gracefully.
8. Public builds must exclude raw customer names and raw descriptions.
9. Public builds must include a generated data source/privacy manifest.

## 12. Success Metrics

1. Dashboard deploys through GitHub Pages from a repeatable GitHub Actions workflow.
2. Initial page load stays reasonable for static hosting by loading aggregate JSON instead of the full transaction file.
3. At least these views are functional in v1: Overview, Sales Trends, Product Mix, Data Quality.
4. Foam pages show deterministic rankings by type, thickness, month/season/year, and indoor/outdoor split where confidence is high.
5. Fabric pages show rankings and indoor/outdoor-suitable inference with confidence labels.
6. The generated data quality report states classification coverage, missing values, unknown/misc share, and public privacy checks.
7. The semantic enrichment pipeline can be rerun without losing progress and without duplicating rows.

## 13. Open Questions

1. Should a sanitized source file be committed to this repo, or should GitHub Actions receive source data through a private artifact/secret process?
2. For fabric rankings, is quantity usually meters, or are there important exceptions that need special handling?
3. Should the old Supabase database be ignored, replaced, or kept as a private downstream target later?
