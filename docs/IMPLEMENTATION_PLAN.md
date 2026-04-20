# Foam Booth Dashboard Implementation Plan

## Guiding Approach

Build the dashboard in two layers:

1. Static dashboard app hosted by GitHub Pages.
2. Offline data preparation pipeline that creates small, safe JSON artifacts for the app.

Do not make the dashboard depend on the old batch LLM/Supabase workflow. Treat LLM extraction as a later offline enrichment job with durable outputs, validation, and review files.

## Proposed Stack

- App: Vite, React, TypeScript.
- Charts: a lightweight React charting library such as Recharts or Apache ECharts.
- Tables: simple React tables first; add TanStack Table only if filtering/sorting grows.
- Data build: Python scripts using pandas for CSV normalization and aggregate generation.
- Deployment: GitHub Actions to build and deploy to GitHub Pages.

This repo is currently mostly empty, so there is no existing frontend stack to preserve.

## Phase 0: Decisions Before Implementation

Resolved planning decisions:

1. Public data policy.
   - Public GitHub Pages dashboard deployed by GitHub Actions.
   - The repo is public, so no PII can be committed.
   - The built static site must not contain customer names or raw descriptions.

2. Data source ownership.
   - Keep a data source register in this repo.
   - Do not commit the raw source or current stage-1 file because they contain customer names and free-text descriptions.
   - If a source file is committed later, it must be sanitized first: drop customer columns, remove/rewrite raw descriptions, and pass privacy checks.
   - If customer cohort IDs are required later, generate them with keyed HMAC using a GitHub Actions secret, not a committed salt.

3. Revenue rules.
   - Headline sales should default to product/service revenue.
   - Discounts, delivery, banking/non-product, refunds/negative lines, and zero-dollar lines should be separated in reconciliation/data quality views.
   - Overview can still show gross total as a secondary reconciliation metric.

4. V1 tab priority.
   - Overview, Sales Trends, Product Mix, Foam Analytics, Fabric Analytics, Data Quality.
   - Foam priority: popularity by foam type, thickness, month/season/year, and indoor/outdoor.
   - Fabric priority: rankings and indoor/outdoor-suitable inference with confidence labels.

## Phase 1: Repository Scaffold

Tasks:

1. Create Vite React TypeScript app structure.
2. Add package scripts:
   - `npm run dev`
   - `npm run build`
   - `npm run preview`
   - `npm run lint`
3. Configure the app for GitHub Pages base path.
4. Add GitHub Pages deployment workflow.
5. Add basic app shell with top tabs and shared date filter state.
6. Add `docs/DATA_SOURCES.md` as the source/privacy register.

Acceptance criteria:

- App runs locally.
- Production build succeeds.
- GitHub Pages workflow is present.
- Tabs render without data.

## Phase 2: Data Preparation Pipeline

Tasks:

1. Add `scripts/build_data.py`.
2. Read source data from a configured local/private path.
3. Normalize fields:
   - `row_id`
   - `date`
   - `invoice_id`
   - `item_number`
   - `quantity`
   - `price`
   - `total`
   - private-only description/customer fields in memory if needed for classification
4. Parse dates, money, missing quantities, and invoice IDs defensively.
5. Generate data quality metrics.
6. Write public aggregate artifacts into `public/data/`.
7. Write a generated source/privacy manifest into `public/data/source_manifest.json`.
8. Fail the build if public artifacts contain blocked fields such as customer names or raw descriptions.

Acceptance criteria:

- Data script runs from a clean checkout.
- Output JSON is deterministic.
- Public artifacts exclude customer names and raw descriptions.
- `data_quality.json` reports row counts, date range, missing values, and source file metadata.
- The source/privacy manifest documents input file, generated time, row counts, and PII exclusion status.

## Phase 3: Deterministic Classification

Tasks:

1. Add a rule-based classifier module.
2. Classify rows into:
   - `foam`
   - `fabric`
   - `dacron`
   - `covers_upholstery`
   - `delivery`
   - `discount`
   - `banking_non_product`
   - `other_product`
   - `unknown`
3. Extract high-confidence foam codes from item numbers and descriptions.
4. Extract high-confidence foam thickness from item numbers and descriptions.
5. Infer foam environment as indoor/outdoor/unknown from foam codes and outdoor terms.
6. Extract high-confidence fabric names, brands, and lengths where explicit.
7. Infer fabric environment as outdoor-suitable/indoor/unknown with confidence:
   - high confidence from known outdoor-suitable brands/terms, such as Sunbrella and Dickson.
   - medium confidence from explicit outdoor wording in fabric description.
   - low confidence from same-invoice association with outdoor foam.
8. Mark classification confidence and reason.
9. Aggregate categories over time.

Acceptance criteria:

- Product Mix tab can show revenue/count by category.
- Foam tab can rank common foam codes and thicknesses.
- Foam tab can show month/season/year popularity and indoor/outdoor split.
- Fabric tab can rank explicitly detected fabric names.
- Fabric tab can show indoor/outdoor-suitable inference with confidence labels.
- Unknown/miscellaneous share is visible.

## Phase 4: Dashboard Pages

Tasks:

1. Overview tab:
   - total revenue
   - product-only revenue
   - invoice count
   - line count
   - average invoice value
   - date range
   - data freshness

2. Sales Trends tab:
   - monthly revenue
   - monthly invoice count
   - average order value
   - year-over-year comparison

3. Product Mix tab:
   - category revenue/count chart
   - top item numbers
   - category trend over time

4. Foam Analytics tab:
   - foam code ranking
   - foam thickness ranking
   - foam popularity by month/season/year
   - outdoor vs indoor split where known
   - foam revenue trend
   - unknown foam-like count

5. Fabric Analytics tab:
   - fabric ranking by revenue
   - estimated meters where reliable
   - outdoor-suitable vs indoor/unknown split with confidence
   - brand rankings where reliable
   - fabric revenue trend
   - unknown fabric-like count

6. Data Quality tab:
   - missing values
   - dropped raw rows warning
   - unknown/misc share
   - non-product row counts
   - public data exclusion status

Acceptance criteria:

- Each tab renders from generated JSON.
- Date filtering updates visible metrics consistently.
- Empty states are clear.
- Mobile layout does not overflow.

## Phase 5: LLM Enrichment Pipeline

This phase should happen after deterministic v1 is working.

Tasks:

1. Create `scripts/enrich_semantics.py`.
2. Process only rows that deterministic rules mark as unknown, low-confidence, or semantically valuable.
3. Use durable JSONL output:
   - one input row per output record
   - no direct database writes
   - resumable by row ID
   - prompt/model version recorded
4. Use strict schema with stable field names:
   - `row_id`
   - `invoice_id`
   - `category`
   - `product_type`
   - `foam_code`
   - `is_outdoor`
   - `dimensions_mm`
   - `piece_count`
   - `fabric_name`
   - `fabric_length_m`
   - `skip_reason`
   - `confidence`
5. Validate every response.
6. Write failures and low-confidence rows to review files.
7. Add a manual review loop before incorporating LLM fields into public aggregates.

Acceptance criteria:

- The enrichment job can stop and resume without duplicate records.
- Invalid model output is captured, not silently skipped.
- The data build can include or exclude LLM enrichment by version.
- The dashboard data quality tab shows enrichment coverage and failure rates.

## Phase 6: QA And Deployment

Tasks:

1. Add automated checks:
   - data build smoke test
   - TypeScript build
   - dashboard render smoke test
2. Verify public artifacts for privacy leaks:
   - no raw customer names
   - no raw descriptions
   - no customer mapping table
   - no source CSV copied into build output
3. Test GitHub Pages deployment.
4. Document the update workflow in `README.md`.

Acceptance criteria:

- A fresh clone can build the data and app with documented commands.
- GitHub Pages deployment works.
- Public build contains only approved data.

## Suggested Milestones

1. Milestone 1: Static app shell and GitHub Pages deployment.
2. Milestone 2: Data build from `stage_1_output.txt` to public aggregate JSON.
3. Milestone 3: Overview, Sales Trends, Product Mix, and Data Quality tabs.
4. Milestone 4: Deterministic Foam and Fabric analytics.
5. Milestone 5: Foam seasonality and fabric indoor/outdoor-suitable inference.
6. Milestone 6: Auditable LLM enrichment pipeline for hard rows.
7. Milestone 7: Review workflow and refined rankings.

## Known Risks

1. GitHub Pages and this repo are public, so privacy leaks are permanent once committed or deployed.
2. The stage-1 CSV is not the complete raw ledger because the prior notebook skipped malformed raw rows.
3. Nearly half of line items are `Miscellaneous`, so deterministic v1 will have meaningful unknown coverage.
4. Free-text descriptions can include customer-specific or banking-related data.
5. Historical item codes and descriptions are inconsistent across years.
6. LLM extraction can introduce silent errors unless output is versioned, validated, and reviewable.

## Recommended Next Implementation Step

Start by scaffolding the app, the data source register, and the privacy-checked data build together. The first working slice should produce `summary.json`, `monthly_sales.json`, `top_items.json`, `foam_seasonality.json`, `fabric_rankings.json`, and `data_quality.json`, then render them in Overview, Sales Trends, Product Mix, Foam Analytics, Fabric Analytics, and Data Quality tabs.
