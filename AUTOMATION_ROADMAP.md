# USGA/GC Dashboard Automation Roadmap

## Purpose

This roadmap describes how the current dashboard can evolve from a manually maintained, self-contained HTML file into a repeatable monthly reporting system. The recommended approach preserves the dashboard as a static, easy-to-distribute artifact while moving data preparation, validation, and business calculations into an automated pipeline.

The migration should be incremental. The existing dashboard can remain available throughout the work while each embedded dataset is replaced with a validated generated artifact.

## Current state

The application is a single `index.html` file containing:

- Six embedded CSS blocks, including accumulated override styles
- Static HTML for the page shell and portions of Retention Analysis
- Three large primary datasets embedded as JavaScript constants
- Additional draft attribution, GHIN trial, marketing, and affiliate datasets
- Business calculations and formatting logic written in browser JavaScript
- Handwritten SVG chart renderers
- Tab, filter, sorting, tooltip, and projection interactions
- Browser `localStorage` persistence for presentation preferences

There is currently no:

- Data-ingestion process
- Data contract or schema enforcement
- Database
- Build step
- Automated calculation test suite
- Data-quality test suite
- Release manifest
- API or external data loading
- Automated deployment process

The dashboard header displays July 1, 2026. Core membership data is populated through May 2026, segmentation status data through June 1, 2026, and segmentation demographic data through May 1, 2026. This illustrates an important current risk: one manually edited report date can imply a uniform cutoff even when sections have different source coverage.

### Current embedded sources

| Embedded source | Current coverage | Primary consumers |
|---|---:|---|
| `DATA` | 60 monthly rows, 2022–2026; populated through May 2026 | Summary, Acquisition Totals, Retention Totals, Recovery, projections |
| `SEGMENTATION_STATUS_DATA` | 348 records; 58 aggregate/club selections; Jan–Jun 2026 | Segmentation status totals and trends |
| `SEGMENTATION_BREAKDOWN_DATA` | 7,656 records; 58 aggregate/club selections; Feb–May 2026 | Segmentation age and gender analysis |
| Retention cohort HTML | Creation years 2022–2026 with milestone and club values | Retention Analysis |
| Attribution draft constants | Jan–May and YTD examples | Attribution Summary, GHIN Trials, Marketing, Affiliate Marketing |

Known placeholder and mock data is documented in `DASHBOARD_AUDIT.md`. In particular, Attribution is explicitly labeled as a mock module, future core membership rows contain null values, and three cohort milestones remain `TBD`.

## Target state

The target is an automated monthly workflow with clear separation between source data, business logic, presentation data, and the dashboard UI.

```text
Monthly controlled CSV exports
          ↓
File discovery and archival
          ↓
Schema and data-quality validation
          ↓
DuckDB staging and transformations
          ↓
Curated reporting tables
          ↓
Versioned JSON/Parquet dashboard artifacts
          ↓
Static dashboard build and automated tests
          ↓
Reviewable monthly release
```

In the target state:

- Source exports are immutable and traceable by reporting month.
- Each source has an owner, expected filename, schema, grain, and delivery schedule.
- A single command processes a new monthly delivery.
- The pipeline is idempotent: rerunning the same inputs produces the same results.
- Business metrics are calculated once in a tested SQL/data layer.
- The dashboard consumes small, versioned JSON files rather than containing megabytes of raw records.
- Section-specific `data_as_of` dates are visible and derived from source data.
- Mock and production data cannot be combined silently.
- Validation failures stop publication and produce an actionable report.
- Every release records input filenames, checksums, row counts, report dates, pipeline version, and output checksums.
- The final dashboard remains deployable to any static file host.

## Recommended folder structure

```text
USGA-GC-Dashboard/
├── README.md
├── DASHBOARD_AUDIT.md
├── PROJECT_OVERVIEW.md
├── AUTOMATION_ROADMAP.md
├── package.json                         # UI build and browser tests
├── pyproject.toml                       # Optional pipeline packaging
├── duckdb/
│   ├── dashboard.duckdb                 # Local generated database; normally ignored
│   └── README.md
├── data/
│   ├── raw/
│   │   └── 2026-07/
│   │       ├── membership.csv
│   │       ├── segmentation_status.csv
│   │       ├── segmentation_breakdown.csv
│   │       ├── retention_cohorts.csv
│   │       ├── retention_clubs.csv
│   │       ├── ghin_trials.csv
│   │       ├── marketing.csv
│   │       └── affiliates.csv
│   ├── reference/
│   │   ├── clubs.csv                    # Canonical club identifiers and names
│   │   ├── channels.csv                 # Canonical attribution channels
│   │   └── metric_definitions.csv
│   ├── processed/
│   │   └── 2026-07/                     # Validated Parquet or CSV snapshots
│   ├── manifests/
│   │   └── 2026-07.json                 # Inputs, checksums, dates, row counts
│   └── schemas/
│       ├── membership.schema.json
│       ├── segmentation-status.schema.json
│       ├── segmentation-breakdown.schema.json
│       ├── retention.schema.json
│       └── attribution.schema.json
├── sql/
│   ├── 00_sources.sql                   # Raw file views
│   ├── 10_staging.sql                   # Types, naming, deduplication
│   ├── 20_quality_checks.sql
│   ├── 30_membership_metrics.sql
│   ├── 31_acquisition_metrics.sql
│   ├── 32_retention_metrics.sql
│   ├── 33_recovery_metrics.sql
│   ├── 34_segmentation_metrics.sql
│   ├── 35_attribution_metrics.sql
│   └── 90_exports.sql                   # Dashboard-facing outputs
├── pipeline/
│   ├── run.py                           # Pipeline entry point
│   ├── discover.py                      # Finds and registers deliveries
│   ├── validate.py                      # File/schema validation
│   ├── manifest.py                      # Release metadata and checksums
│   └── publish.py                       # Builds versioned output
├── src/
│   ├── index.html                       # Semantic page shell
│   ├── styles/
│   │   ├── tokens.css
│   │   ├── base.css
│   │   ├── layout.css
│   │   ├── charts.css
│   │   └── sections/
│   ├── scripts/
│   │   ├── app.js
│   │   ├── state.js
│   │   ├── formatters.js
│   │   ├── charts/
│   │   └── sections/
│   └── data/                             # Generated JSON copied at build time
├── tests/
│   ├── data_quality/
│   ├── calculations/
│   ├── fixtures/
│   ├── browser/
│   └── visual/
├── reports/
│   └── validation/                       # Human-readable validation results
└── dist/                                 # Deployable generated dashboard
```

The language used to orchestrate the pipeline is less important than keeping transformations testable and explicit. Python is a practical choice for file handling and manifests, while DuckDB SQL can perform most transformations. A JavaScript/TypeScript pipeline could also drive DuckDB if that better matches team ownership.

Large generated databases, processed files, and `dist/` outputs should be excluded from version control unless organizational requirements call for versioned snapshots. Raw source retention should follow the applicable data-governance policy.

## Monthly CSV processing workflow

### 1. Receive and archive the delivery

Each reporting cycle receives a defined set of CSV exports. Files are copied without alteration into a month-specific directory such as `data/raw/2026-07/`.

The pipeline records for every file:

- Expected source type
- Original filename
- File checksum
- File size
- Extract/report date supplied by the source
- Receipt timestamp
- Row count
- Pipeline version

The raw files should be treated as immutable evidence. Corrections should arrive as a new delivery or receive a revision identifier rather than overwriting the prior file silently.

### 2. Validate file-level requirements

Before reading business data, verify:

- Every required export is present
- No unexpected duplicate export is present
- The file is valid CSV and uses the expected encoding and delimiter
- Required headers exist exactly once
- The reporting month matches the run request
- Empty or suspiciously small files are rejected

Optional sources may be allowed, but their absence should be clearly represented in the release manifest and dashboard rather than filled with invented values.

### 3. Load raw staging tables

DuckDB can read each CSV directly into a raw view or staging table. Initial loads should preserve source values as closely as possible and add lineage fields such as:

- `_source_file`
- `_source_checksum`
- `_report_month`
- `_loaded_at`
- `_row_number`

Schema inference is convenient during exploration, but production processing should declare column types explicitly to prevent a changed value from silently changing a field's type.

### 4. Normalize and conform the data

Staging transformations should:

- Parse and standardize dates
- Trim text and normalize missing values
- Convert counts, currency, and rates to declared numeric types
- Map club names to stable club IDs
- Map marketing and affiliate labels to canonical channels/partners
- Standardize month labels, age bands, gender values, and statuses
- Deduplicate at the expected grain
- Preserve unknown categories when they are legitimate source values
- Distinguish unavailable values from real zero values

Expected grains should be documented. Examples include one row per month for membership, one row per report date and club for segmentation status, and one row per report date, club, status, segment type, and segment for demographic breakdowns.

### 5. Run quality and reconciliation checks

Checks should fail the build or raise a reviewed warning depending on severity:

- Duplicate primary keys
- Missing required months
- Future dates or stale report dates
- Negative golfer counts
- Rates outside 0–100%
- `renewed > up_for_renewal`
- `active + inactive + archived != total`
- Status shares that do not sum to approximately 100%
- Age/gender segment counts that do not reconcile to status totals
- YTD totals that do not equal the sum of monthly records
- Attribution components that do not reconcile to attributed acquisition totals
- Unexpected club additions, removals, or naming changes
- Material month-over-month changes above an agreed review threshold
- Production outputs containing `TBD`, mock labels, or unapproved null metrics

The pipeline should write both a machine-readable result and a concise Markdown/HTML validation report.

### 6. Build curated reporting tables

Validated staging data is transformed into stable reporting tables with names and fields designed for dashboard consumption. Suggested tables include:

- `fct_membership_monthly`
- `fct_acquisition_monthly`
- `fct_retention_monthly`
- `fct_reactivation_monthly`
- `fct_segmentation_status`
- `fct_segmentation_breakdown`
- `fct_retention_cohort_milestones`
- `fct_retention_club_cohorts`
- `fct_attribution_monthly`
- `fct_marketing_channel_monthly`
- `fct_affiliate_partner_monthly`
- `dim_club`
- `dim_month`

Dashboard-ready views can then expose exactly the metrics and ordering the UI needs.

### 7. Export dashboard artifacts

DuckDB can export curated views to JSON, CSV, or Parquet. JSON is the simplest browser input; Parquet is useful for retained analytical outputs and larger downstream analysis.

Recommended dashboard files include:

```text
membership.json
acquisition.json
retention.json
recovery.json
segmentation-status.json
segmentation-breakdown.json
attribution.json
report-metadata.json
```

`report-metadata.json` should contain the overall release month, each section's `data_as_of` date, validation status, source manifest reference, and whether each source is production, provisional, or mock.

### 8. Build, test, and publish

The dashboard build copies validated JSON and static application files into `dist/`. Automated browser tests load the built dashboard, verify key KPIs against known pipeline outputs, exercise filters and tabs, and capture visual regression screenshots.

Publication should require:

- All blocking data tests passing
- No unapproved mock or TBD values
- Expected report dates displayed
- KPI reconciliation checks passing
- A reviewed validation report
- A complete release manifest

## Where DuckDB fits

DuckDB is well suited to this project because the expected workflow is analytical, file-oriented, and monthly rather than transaction-heavy.

### Recommended role

DuckDB can act as the local analytical engine between raw CSV exports and dashboard JSON:

- Query CSV and Parquet files directly
- Apply explicit types and transformations with SQL
- Join multiple monthly exports
- Use window functions for prior-period and rolling calculations
- Aggregate detailed club and demographic records efficiently
- Run reconciliation and quality queries
- Persist a local database for investigation
- Export curated results to JSON, CSV, or Parquet

This avoids introducing a hosted database before one is needed. A monthly run can operate entirely on local or controlled-storage files and produce a static dashboard.

### Suggested DuckDB layers

| Layer | Purpose |
|---|---|
| Raw views | Direct representation of delivered CSV files plus lineage metadata |
| Staging tables/views | Typed, normalized, deduplicated records |
| Curated facts/dimensions | Stable business grains and conformed identifiers |
| Metric views | YTD, YoY, retention, attribution, and cohort calculations |
| Export views | Small, UI-specific tables ordered for JSON generation |

### What DuckDB should not do

DuckDB does not need to serve live browser requests. The browser should not connect directly to the database, and the database file should not be published with the dashboard. DuckDB prepares the release artifacts; the dashboard remains a static consumer.

If the process eventually needs concurrent users, real-time updates, row-level security, or operational writeback, a hosted warehouse or transactional database may become appropriate. DuckDB can still remain useful for local development and test fixtures.

## Calculations currently embedded in `index.html`

The current browser code performs both business calculations and presentation calculations.

### Date selection and data fallback

- Builds a year/month lookup for core records
- Finds the latest populated active-golfer row
- Falls back to the latest non-null row when a selected/reporting row is empty
- Limits chart rows to the selected reporting period
- Validates whether a same-month prior-year comparison is available

### Shared membership calculations

- YTD sum of new golfers
- Prior-year YTD sum of new golfers
- YTD sum of reactivations
- Prior-year YTD sum of reactivations
- Same-month prior-year active golfers
- Absolute active-golfer YoY change
- Percentage active-golfer YoY change
- Absolute and percentage YTD acquisition change
- Absolute and percentage YTD reactivation change
- Estimated retained golfers: retention rate × prior-year active golfers
- Not renewed: up for renewal − renewed
- New golfers as a share of active golfers
- Reactivations as a share of active golfers
- Generic relative changes and safe shares

### Summary calculations

- Current-year growth from prior December
- Prior-year growth over the comparable year-to-date interval
- Difference between current and prior comparable growth rates
- Current and prior YTD net membership growth
- Same-month acquisition and recovery comparisons
- Month-over-month rolling retention comparison
- Same-month renewal comparison

### Membership chart and projection calculations

- Annual membership values and growth between years
- Same-month membership values and growth across years
- Current-year actual series
- Historical yearly series
- Default projection factor based on current active golfers versus the same prior-year month
- Alternative 20%, 25%, and 30% scenarios
- Remaining-month projection using prior-year monthly totals × selected factor

### Acquisition calculations

- Monthly new-golfer YoY values and changes
- YTD new-golfer totals and YoY values
- Cumulative acquisition pacing by year
- Monthly and YTD acquisition share of the active base
- Year visibility and chart-series filtering

### Retention calculations

- Renewed and not-renewed comparisons
- Retained-golfer estimates from rolling retention rates
- Prior-year active base comparisons
- Rolling retention month-over-month change
- Club ranking order and rank numbers

Retention cohort milestones, survival-curve values, and club cohort rates are largely embedded as finished values in HTML rather than calculated by a reusable pipeline.

### Recovery calculations

- Monthly reactivation YoY change
- YTD reactivation totals and YoY change
- Monthly and YTD reactivation share of active golfers
- Cumulative reactivation pacing by year

### Segmentation calculations

- Active and inactive trend series
- Latest breakdown by club, status, age, and gender
- Comparison of club segment share with the all-club share
- Over-indexing values and rankings
- Female-share over-indexing
- Weighted average age estimates using age-band midpoint assumptions
- Youngest/oldest association rankings
- Largest or notable age-segment insights

### Attribution, marketing, and affiliate calculations

- Attribution totals by source
- Monthly and YTD attribution source shares
- Acquisition-mix donut shares
- Attribution source rankings
- GHIN conversion rate: conversions ÷ trials
- Marketing totals for spend, conversions, impressions, and clicks
- CPA: spend ÷ conversions
- CTR: clicks ÷ impressions
- CPC: spend ÷ clicks
- CPM: spend ÷ impressions × 1,000
- Marketing conversion rate: conversions ÷ clicks
- Marketing spend shares and funnel shares
- Affiliate totals and conversion rates
- Affiliate partner conversion shares and rankings

Some attribution YoY values are hard-coded display strings instead of calculations.

### Presentation-only calculations

- Axis ranges and tick intervals
- SVG coordinates, bar widths, donut angles, and line paths
- Compact number and percentage formatting
- Tooltip content
- Sorting and visible-row selection

## Calculations that should move into the data pipeline

The guiding rule should be: if a value defines business meaning, reconciliation, or reported performance, calculate it in the pipeline. If it only controls how a validated value is displayed, keep it in the browser.

### Move first

These calculations should move early because they are widely reused and straightforward to test:

- Report and section `data_as_of` dates
- YTD new golfers and reactivations
- Prior-year YTD totals
- Same-month YoY absolute and percentage changes
- Net membership growth since prior December
- New-golfer and reactivation shares of active golfers
- Renewed and not-renewed counts
- Retained-golfer counts and prior-year active bases
- Monthly and YTD acquisition pacing values
- Monthly and cumulative reactivation pacing values

### Move with retention source automation

- Creation-year cohort counts
- Active/inactive cohort counts and rates
- 13-, 25-, and 37-month survival milestones
- Survival change from the prior milestone
- Club cohort retention rates
- Club rankings and comparison deltas

Moving these values will eliminate hard-coded cohort HTML and allow `TBD` milestones to resolve automatically when cohorts become eligible.

### Move with segmentation automation

- Status totals and shares
- Demographic reconciliation totals
- Club versus all-club index values
- Association rankings
- Weighted average age estimates
- Female-share and age-segment over-indexing
- Youngest/oldest association lists

Age-band midpoint assumptions should be documented in metric definitions and implemented centrally rather than hidden in UI code.

### Move with attribution productionization

- Source totals and shares
- Source YoY changes
- Trial conversion rates and conversion timing shares
- Marketing spend, CPA, CTR, CPC, CPM, and conversion rates
- Marketing funnel and channel totals
- Affiliate conversion rates and partner shares
- Reconciliation between acquisition totals and attribution sources

Mock sources should be replaced with documented production exports before these views are eligible for publication.

### Projection split

The pipeline should provide historical actuals, approved baseline forecast inputs, and a documented default projection. Interactive what-if scenarios can remain in the browser because they are user-selected presentation scenarios. The dashboard should clearly distinguish an approved forecast from an exploratory scenario.

### Keep in the browser

- Number and label formatting
- SVG geometry and chart scaling
- Tab/filter state
- Chart-type selection
- Visible-year selection
- Sorting for interactive tables
- Tooltips
- Exploratory projection scenario selection

## Estimated implementation phases

Estimates assume one engineer working with regular input from metric owners and data providers. Calendar time will depend more on source access and business-definition decisions than on dashboard code.

### Phase 0 — Ownership and definitions

**Estimated effort:** 3–5 working days

- Inventory every required monthly export and owner
- Define source delivery dates and expected filenames
- Document grains, keys, and metric definitions
- Decide whether the dashboard reports one common cutoff or section-specific dates
- Classify every existing dataset as production, provisional, mock, or obsolete
- Define approval criteria for monthly publication

**Exit criterion:** A signed-off source and metric register exists.

### Phase 1 — Repository and baseline safeguards

**Estimated effort:** 3–5 working days

- Create the target directory skeleton
- Add version control ignore rules for generated/private artifacts
- Extract representative CSV fixtures from the embedded datasets
- Record baseline KPI values and dashboard screenshots
- Add a simple build command that reproduces the current static dashboard
- Add checks that the current UI still renders correctly

**Exit criterion:** The current dashboard can be reproduced and compared safely during migration.

### Phase 2 — DuckDB ingestion and validation foundation

**Estimated effort:** 1–2 weeks

- Implement raw CSV discovery and checksums
- Add explicit schemas for membership and segmentation exports
- Load raw and staging layers in DuckDB
- Normalize dates, clubs, statuses, age bands, and gender values
- Implement core reconciliation and duplicate checks
- Generate a validation report and release manifest

**Exit criterion:** Membership and segmentation CSVs load repeatably, with failures blocking invalid releases.

### Phase 3 — Core metric pipeline

**Estimated effort:** 1–2 weeks

- Implement membership, acquisition, retention-total, and recovery SQL views
- Move YTD, YoY, share, renewal, and retained-golfer calculations into tested SQL
- Export dashboard-ready JSON
- Reconcile every output against the current dashboard
- Add section-level `data_as_of` metadata

**Exit criterion:** Summary, Acquisition Totals, Retention Totals, and Recovery can be driven by generated artifacts.

### Phase 4 — UI extraction and generated-data integration

**Estimated effort:** 1–2 weeks

- Split HTML, CSS, and JavaScript into source modules
- Remove the three large primary datasets from application source
- Load generated JSON during the build or at runtime
- Preserve current tabs, charts, tooltips, filters, and localStorage behavior
- Consolidate CSS override blocks
- Add browser, accessibility, and responsive visual tests

**Exit criterion:** The static dashboard matches the current experience while consuming generated data.

### Phase 5 — Retention cohort automation

**Estimated effort:** 1–2 weeks, subject to golfer-level or prepared cohort-source availability

- Ingest cohort and club retention exports
- Calculate eligibility and survival milestones
- Generate survival-curve and club-ranking data
- Replace hard-coded retention-analysis HTML
- Remove `TBD` values when source eligibility permits

**Exit criterion:** Retention Analysis is generated from documented source data.

### Phase 6 — Attribution productionization

**Estimated effort:** 2–4 weeks, highly dependent on source availability and attribution definitions

- Confirm production GHIN trial, marketing, affiliate, and organic sources
- Define attribution rules and reconciliation tolerances
- Replace every mock/draft dataset
- Calculate all source performance metrics in DuckDB
- Add production/mock state validation
- Remove draft labeling only after stakeholder approval

**Exit criterion:** Attribution is traceable, reconciled, and approved for production reporting.

### Phase 7 — Monthly release automation

**Estimated effort:** 1 week

- Add one-command monthly processing
- Run validation, transformation, export, build, and browser tests automatically
- Produce a dated preview and validation report
- Add approval and publication steps
- Archive release manifests and output checksums
- Document rerun, correction, and rollback procedures

**Exit criterion:** A new approved monthly dashboard can be produced without editing application code or embedded data manually.

### Phase 8 — Operational hardening

**Estimated effort:** Ongoing; initial 1–2 weeks

- Add scheduled or event-triggered execution where appropriate
- Add notifications for missing files and failed validations
- Track pipeline duration, row counts, and freshness over time
- Establish retention and access policies for source data
- Review accessibility and security
- Define support ownership and service expectations

**Exit criterion:** The monthly process is monitored, documented, and supportable beyond its original author.

## Suggested first milestone

The lowest-risk, highest-value first release is to automate only the core membership and segmentation data while leaving the UI visually unchanged. That milestone would:

1. Establish monthly folder and manifest conventions.
2. Load membership and segmentation CSVs into DuckDB.
3. Validate and calculate core KPIs.
4. Export the three datasets currently responsible for most of the size of `index.html`.
5. Build a static dashboard against those generated artifacts.
6. Preserve Attribution as visibly mock until its production sources are ready.

This delivers a repeatable reporting foundation without making the success of the first automation release depend on resolving every attribution and retention-cohort question at once.
