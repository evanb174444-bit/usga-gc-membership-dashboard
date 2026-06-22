# Dashboard Data Migration Log

## Current migration status

Two production-facing datasets have been removed from `index.html` and converted to standalone JSON files. The dashboard now loads both datasets through HTTP before its first render.

The migration used a parity-first approach: records, field names, values, ordering, nulls, and existing browser-side calculations were preserved.

## 1. Datasets extracted

### `SEGMENTATION_BREAKDOWN_DATA`

- **Original location:** Embedded JavaScript array in `index.html`
- **Records:** 7,656
- **New location:** `data/segmentation_breakdown.json`
- **Consumers:** Segmentation gender breakdowns, age breakdowns, average-age estimates, female-share indexes, and youngest/oldest association rankings
- **Migration behavior:** The JSON loads before the dashboard renders and is assigned to the existing `SEGMENTATION_BREAKDOWN_DATA` variable.
- **Parity result:** All records were preserved with a matching semantic data fingerprint.

### `DATA`

- **Original location:** Embedded JavaScript array in `index.html`
- **Records:** 60
- **New location:** `data/membership_monthly.json`
- **Consumers:** Summary, Acquisition Totals, Retention Totals, Recovery, membership comparisons, and projections
- **Migration behavior:** The JSON loads before the dashboard renders. `DATA`, `BY_YEAR_MONTH`, `DEFAULT_REF_ROW`, `DEFAULT_REF`, widget references, and `YOY_REF` are initialized only after loading succeeds.
- **Parity result:** All 60 records were preserved exactly, with no renamed fields or recalculated values and a matching semantic data fingerprint.

## 2. Files created

### Extracted data files

- `data/segmentation_breakdown.json`
- `data/membership_monthly.json`

### Supporting migration and audit files

- `scripts/serve_dashboard.sh` — Runs a local-only HTTP server for dashboard preview and JSON loading.
- `scripts/dashboard_inventory.py` — Inventories major embedded datasets and reports their approximate location and record count.
- `DATASET_INVENTORY.md` — Documents the pre-migration embedded dataset inventory and dashboard consumers.
- `DASHBOARD_AUDIT.md` — Documents placeholder, draft, mock, and TBD data.
- `PROJECT_OVERVIEW.md` — Documents the current application architecture.
- `AUTOMATION_ROADMAP.md` — Describes the path toward automated monthly reporting.
- `MIGRATION_LOG.md` — This migration record.

`index.html` was modified only to replace the two embedded arrays with deferred variables, load their JSON files, and initialize dependent state after loading.

## 3. Dashboard sections verified

### Segmentation extraction verification

The dashboard was served through `http://127.0.0.1:8000/` and tested in a browser.

Verified behavior:

- Segmentation tab loads successfully.
- All 58 club/association selections render without failures.
- Status KPI summary renders.
- Active golfer trend chart renders.
- Inactive golfer trend chart renders.
- Gender active/inactive breakdowns render.
- Age active/inactive breakdowns render.
- Active and inactive average-age values render.
- Female-share over-index and under-index rankings render.
- Youngest and oldest association rankings render.
- No Segmentation empty states appeared for the tested selections.
- No browser console errors or warnings were reported.

### Membership extraction verification

Verified behavior:

- **Summary** — Headline membership KPIs, annual growth, same-month YoY comparison, and all summary values render.
- **Acquisition Totals** — KPI highlights, monthly YoY, YTD YoY, monthly trend, and cumulative pacing render.
- **Retention Totals** — On-time renewal and rolling 12-month retention cards and charts render.
- **Recovery** — Monthly and cumulative YTD reactivation cards and charts render.
- **Projections** — Current-growth and 20% scenarios recalculate and render; the current-growth scenario was restored after testing.
- The dashboard requested `data/membership_monthly.json` successfully with HTTP 200.
- No browser console errors or warnings were reported.

Attribution, GHIN Trials, Marketing, and Affiliate Marketing were not part of the membership extraction verification because their datasets and calculations were not changed.

## 4. Data still embedded in `index.html`

The current inventory finds 16 major embedded dataset constants containing 467 top-level array records.

### Segmentation

- `SEGMENTATION_STATUS_DATA` — 348 records

This continues to drive Segmentation status KPIs and active/inactive monthly trends.

### Acquisition Attribution Summary

- `ATTRIBUTION_DRAFT_DATA` — 5 records

### GHIN Trials

- `GHIN_TRIALS_DRAFT` — One top-level object containing trial overview and funnel values
- `GHIN_TRIALS_YEARLY_DRAFT` — One top-level object
- `GHIN_TRIALS_MONTHLY_DRAFT` — 5 records
- `GHIN_TRIALS_CONVERSION_BUCKETS_DRAFT` — 5 records
- `GHIN_TRIALS_AGA_DRAFT` — 58 records

### Marketing

- `MARKETING_MIX_DRAFT` — 9 records
- `MARKETING_MONTHLY_PERFORMANCE_DRAFT` — 1 record
- `MARKETING_MONTHLY_FUNNEL_SPEND_DRAFT` — 1 record
- `MARKETING_FUNNEL_DRAFT` — 3 records
- `MARKETING_CHANNEL_PERFORMANCE_DRAFT` — 16 records
- `MARKETING_INFLUENCER_PERFORMANCE_DRAFT` — 1 record

### Affiliate Marketing

- `AFFILIATE_MARKETING_DRAFT` — 4 records
- `AFFILIATE_MONTHLY_PERFORMANCE_DRAFT` — 5 records
- `AFFILIATE_PARTNER_PERFORMANCE_DRAFT` — 6 records

### Retention Analysis

Creation-year cohort values, membership survival milestones, the survival curve, and club retention rankings remain hard-coded directly in the HTML rather than represented as a reusable dataset constant.

### Other application content

CSS, HTML templates, SVG chart rendering, calculations, interaction state, and most section rendering logic remain embedded in `index.html`. Extracting data does not yet split application code into modules.

## 5. Next recommended migration step

Extract `SEGMENTATION_STATUS_DATA` next into:

```text
data/segmentation_status.json
```

Reasons:

1. It is now the largest remaining embedded dataset at 348 records.
2. It is isolated to the Segmentation section, limiting regression risk.
3. The existing asynchronous startup already loads external Segmentation data, so the integration pattern is established.
4. Extracting it would complete externalization of the current Segmentation data layer.
5. It can be verified against the same 58 club selections and active/inactive trend checks already used for the breakdown migration.

The safest implementation is another parity-first extraction: preserve the array exactly, load it alongside `segmentation_breakdown.json`, and leave all existing status calculations and rendering functions unchanged.

After Segmentation status is externalized, the next architectural milestone should be defining controlled monthly CSV schemas and introducing DuckDB to generate the three production JSON artifacts. Draft attribution datasets should remain visibly draft until approved production sources and reconciliation rules are available.
