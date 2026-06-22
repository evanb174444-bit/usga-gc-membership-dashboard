# USGA/GC Membership Dashboard — Project Overview

## 1. Current dashboard structure

The dashboard is currently a self-contained static web application implemented in a single `index.html` file. It does not require a web server, build step, package manager, JavaScript framework, or external charting library. Opening the file in a modern browser is enough to run it.

`index.html` combines four concerns:

1. **Presentation styles** — Embedded `<style>` blocks define the page layout, cards, tabs, tables, charts, responsive behavior, and visual states. The file contains one main stylesheet plus several later override blocks.
2. **Static document structure** — The HTML establishes the header, primary tabs, secondary tabs, static retention-cohort content, and empty containers used by JavaScript renderers.
3. **Embedded data** — Membership, segmentation, attribution, marketing, affiliate, and retention figures are stored directly in JavaScript arrays and objects.
4. **Application logic** — Vanilla JavaScript calculates metrics, generates SVG charts, renders HTML into dashboard containers, handles interactions, and persists user preferences.

The main startup flow is:

```text
Load embedded CSS, HTML, and data
        ↓
Initialize helper functions and UI state
        ↓
render()
  ├─ renderMembership()
  ├─ renderAcquisitionSection()
  ├─ renderRetentionSection()
  ├─ renderRecoverySection()
  └─ renderSegmentationSection()
        ↓
Restore the saved tab and other browser preferences
```

Most charts are generated as inline SVG. There are no calls to `fetch()`, no API integration, and no external runtime assets. UI settings are saved in browser `localStorage`, including the active tab, chart types, visible years, projection scenario, attribution view, table sort order, and selected segmentation club.

The dashboard header currently displays a report date of July 1, 2026. The latest populated core membership record is May 2026, while segmentation status data extends through June 1, 2026.

## 2. Major sections and tabs

### Summary

The Summary tab provides the executive view of the dashboard:

- Active GC golfers
- YTD membership growth and net growth
- Monthly and YTD new golfers
- On-time renewal and rolling 12-month retention
- Monthly and YTD reactivations
- Total membership growth by year
- Same-month year-over-year membership comparison
- Year-end membership projection

The projection can use the current year-over-year growth rate or fixed 20%, 25%, and 30% growth scenarios. Future values are derived by applying the selected factor to the prior year's remaining monthly membership totals.

### Acquisition

Acquisition contains two secondary tabs:

#### Totals

- Acquisition KPI highlights
- Monthly new-golfer year-over-year comparison
- YTD new-golfer year-over-year comparison
- Monthly new-golfer trend
- Cumulative YTD pacing
- Line/bar chart controls and year visibility controls

#### Attribution

Attribution contains four views:

- **Summary** — Acquisition totals and source mix for GHIN Trials, Marketing, Affiliate, and Organic/Unknown.
- **GHIN Trials** — Trial creation, conversion, conversion timing, active/inactive trial golfers, and conversions by golf association.
- **Marketing** — Spend, impressions, clicks, conversions, funnel performance, monthly trends, channel performance, and influencer performance.
- **Affiliate Marketing** — Affiliate traffic, conversions, conversion rate, monthly trends, partner share, and partner performance.

The Attribution module is explicitly identified in the source as a draft/mock module. Its data should not be treated uniformly as production data.

### Retention

Retention contains two secondary tabs:

#### Totals

- On-time renewal rate
- Golfers up for renewal
- Golfers renewed on time
- Golfers not renewed on time
- Rolling 12-month retention
- Prior-year active base
- Retained golfers
- Monthly and annual trend charts

#### Retention Analysis

- Active versus inactive golfers by creation year
- Cohort-level membership survival milestones
- Membership survival curve
- Club retention rankings for the 2022, 2023, and 2024 creation cohorts
- Sortable club ranking columns and expandable club list

Much of this cohort-analysis section is hard-coded directly in the HTML rather than generated from a dedicated data source.

### Recovery

The Recovery tab presents:

- Monthly reactivations
- YTD reactivations
- Reactivations as a share of the active golfer base
- Monthly reactivation trends
- Cumulative YTD pacing for 2025 and 2026

### Segmentation

The Segmentation tab supports an aggregate view and selection among 58 clubs/associations. It contains:

- Active, inactive, and archived golfer totals
- Active and inactive status trends
- Inactive share of the total golfer population
- Gender breakdowns by status
- Age breakdowns by status
- Over-indexing insights and association rankings
- Average-age highlights and age extremes

## 3. Data sources currently embedded in the file

### Core membership data

The `DATA` array contains 60 monthly rows spanning January 2022 through December 2026. It includes:

- Active golfers
- Monthly net change and percent change
- New golfers
- Reactivations
- On-time renewal rates
- Renewed and up-for-renewal counts
- Rolling retention rates

Actual populated coverage varies by metric. May 2026 is the latest row with populated core membership values. June through December 2026 are present as empty future rows.

### Segmentation status data

`SEGMENTATION_STATUS_DATA` contains 348 records for 58 aggregate/club selections across six report dates from January 5 through June 1, 2026. Fields include:

- Active golfers
- Inactive golfers
- Archived golfers
- Total golfers
- Status shares

### Segmentation demographic breakdown data

`SEGMENTATION_BREAKDOWN_DATA` contains 7,656 records covering 58 aggregate/club selections from February through May 2026. It breaks Active, Inactive, and Archived golfers down by:

- Age range
- Gender
- Golfer count
- Share within status

### Retention cohort and club data

Creation-year cohort summaries, survival milestones, the survival curve, and club rankings are embedded directly in the HTML. These values are not currently stored in a reusable JavaScript dataset.

### Acquisition attribution data

The file embeds separate arrays and objects for:

- Monthly attribution source mix
- GHIN trial overview and funnel
- GHIN trial yearly totals
- Monthly trials and conversions
- Conversion timing buckets
- AGA trial conversions
- Marketing source mix
- Marketing funnel and channel performance
- Influencer performance
- Affiliate monthly and partner performance

A source comment states that the YTD marketing aggregate came from `Marketing_Metrics_Update (1).xlsx`, specifically its Marketing Metrics sheet. That workbook is not present in the current project directory, and the dashboard does not load it dynamically.

## 4. Known placeholder and mock data

The full detailed audit is maintained in `DASHBOARD_AUDIT.md`. The major issues are:

- The page title labels Attribution as `DRAFT`.
- The source explicitly calls Acquisition Attribution a mock module with placeholder data that is not production source data.
- Most attribution, GHIN trial, affiliate, and marketing datasets use `DRAFT` in their constant names.
- Attribution source YoY changes are hard-coded strings rather than calculated from source records.
- The YTD marketing mix is draft-labeled but has a comment identifying it as real spreadsheet-sourced aggregate data.
- June through December 2026 core membership rows are empty placeholders containing `null` metrics.
- The 2023 cohort's 37-month retention milestone is `TBD`.
- The 2024 cohort's 25-month and 37-month milestones are `TBD`.
- The marketing “monthly” performance and funnel-spend arrays currently contain only a single YTD record.
- No `TODO`, `FIXME`, or `XXX` comments are currently present.

## 5. Opportunities for future automation

### Automated data ingestion

Replace manually embedded arrays with a repeatable import process that reads controlled CSV or Excel exports. The process should validate required columns, normalize dates and club names, reject duplicate records, and produce browser-ready JSON.

### Report-date management

Derive the displayed report date from validated source data instead of editing header text manually. Because the sources currently have different latest dates, the UI should either show a date per section or clearly define the dashboard-wide reporting cutoff.

### Data-quality checks

Add automated validation for:

- Missing months
- Unexpected nulls
- Duplicate club/month records
- Status totals that do not reconcile
- Demographic shares that do not sum correctly
- Renewal counts that exceed golfers up for renewal
- Retention or conversion rates outside valid ranges
- Attribution totals that do not reconcile with acquisition totals
- Placeholder or `TBD` values included in a production release

### Metric calculation pipeline

Move YTD totals, year-over-year changes, retained-golfer counts, projection inputs, attribution shares, and cohort milestones into a tested data-preparation layer. This would reduce the amount of calculation logic performed independently by browser renderers.

### Automated dashboard builds

A lightweight build script could:

1. Read current source files.
2. Validate and transform the data.
3. Generate versioned JSON artifacts.
4. Build the dashboard.
5. Run automated tests.
6. Produce a deployable `dist/` directory.

### Testing and visual regression

Useful automated coverage would include:

- Unit tests for calculations and formatting
- Data-schema and reconciliation tests
- DOM tests for tab and filter behavior
- Browser tests for localStorage state
- Screenshot comparisons at desktop, tablet, and mobile widths
- Accessibility checks for tab semantics, keyboard navigation, contrast, and SVG descriptions

### Release and deployment automation

A continuous-integration workflow could validate every proposed change, build a preview, prevent releases containing known mock data, and publish approved versions to static hosting. Source file dates and checksums could be recorded in a release manifest for traceability.

## 6. Recommended folder structure as the dashboard grows

The dashboard can remain a static application while separating data, logic, and presentation. A practical target structure is:

```text
USGA-GC-Dashboard/
├── README.md
├── DASHBOARD_AUDIT.md
├── PROJECT_OVERVIEW.md
├── package.json                    # Optional build/test tooling
├── src/
│   ├── index.html                  # Semantic page shell
│   ├── styles/
│   │   ├── tokens.css              # Colors, spacing, typography
│   │   ├── base.css                # Reset and shared elements
│   │   ├── layout.css              # Header, tabs, grids, cards
│   │   ├── charts.css              # SVG/chart presentation
│   │   └── sections/
│   │       ├── summary.css
│   │       ├── acquisition.css
│   │       ├── retention.css
│   │       ├── recovery.css
│   │       └── segmentation.css
│   ├── scripts/
│   │   ├── app.js                  # Startup and orchestration
│   │   ├── state.js                # UI state and localStorage
│   │   ├── calculations.js         # Shared metric calculations
│   │   ├── formatters.js           # Counts, percentages, labels
│   │   ├── charts/                 # Reusable SVG renderers
│   │   └── sections/
│   │       ├── summary.js
│   │       ├── acquisition.js
│   │       ├── retention.js
│   │       ├── recovery.js
│   │       └── segmentation.js
│   └── data/
│       ├── membership.json
│       ├── segmentation-status.json
│       ├── segmentation-breakdown.json
│       ├── retention-cohorts.json
│       └── attribution.json
├── data/
│   ├── raw/                        # Original controlled exports
│   ├── processed/                  # Validated normalized data
│   ├── schemas/                    # Machine-readable data contracts
│   └── README.md                   # Source ownership and refresh rules
├── scripts/
│   ├── import-data.js
│   ├── validate-data.js
│   └── build-dashboard.js
├── tests/
│   ├── calculations/
│   ├── data-quality/
│   ├── browser/
│   └── visual/
├── docs/
│   ├── metric-definitions.md
│   ├── data-sources.md
│   └── release-process.md
└── dist/                            # Generated deployable output
```

This structure does not require adopting a large frontend framework. Standard JavaScript modules, CSS files, JSON data, and a small build/test toolchain would be sufficient. The most valuable first extraction would be moving the three very large embedded datasets out of `index.html`; the next would be splitting section renderers and consolidating the accumulated CSS override blocks.
