# Dashboard Placeholder, Draft, Mock, and TBD Audit

This report audits `index.html` for placeholder data, draft data, mock data, TODOs, and TBD values. CSS classes and function names containing terms such as `attribution-draft` are treated as identifiers rather than separate placeholder-data locations.

## Global

- `index.html:6` — The page title explicitly labels Attribution as `DRAFT`.
- `index.html:1440` — CSS comment: `DRAFT: Secondary Acquisition tabs`.
- `index.html:1560` — Explicit declaration that the Acquisition Attribution module is a mock and its placeholder data is not production source data.

## Summary and shared membership data

- `index.html:5563` — `DATA` contains future placeholder rows for June through December 2026. Their membership, acquisition, recovery, and retention fields are all `null`.

These placeholders affect Summary, Acquisition Totals, Retention Totals, and Recovery because all four use this shared dataset. The renderers currently fall back to May 2026, the latest populated record.

## Acquisition — Attribution Summary

- `index.html:5913` — `ATTRIBUTION_DRAFT_DATA`: January through May source totals for GHIN Trials, Marketing, Affiliate, and Organic/Unknown.
- `index.html:5934` — Hard-coded draft YoY claims for each attribution source: `+24.0%`, `+12.5%`, `+18.8%`, and `+3.1%`.

These values drive the attribution KPIs, acquisition-mix donut, and monthly source trend.

## Acquisition — GHIN Trials

- `index.html:6064` — `GHIN_TRIALS_DRAFT`: trial signup, activation, engagement, conversion, and campaign values.
- `index.html:6484` — `GHIN_TRIALS_YEARLY_DRAFT`: yearly totals and active/inactive trial golfers.
- `index.html:6492` — `GHIN_TRIALS_MONTHLY_DRAFT`: January through May trials and conversions.
- `index.html:6500` — `GHIN_TRIALS_CONVERSION_BUCKETS_DRAFT`: conversion timing buckets.
- `index.html:6508` — `GHIN_TRIALS_AGA_DRAFT`: conversion counts for 58 golf associations.

## Acquisition — Marketing

- `index.html:6083` — A source note says the YTD marketing aggregate came from `Marketing_Metrics_Update (1).xlsx`; that source file is not in this project.
- `index.html:6088` — `MARKETING_MIX_DRAFT`: draft-labeled channel conversion mix. Unlike most attribution data, the preceding comment identifies this as real YTD source data.
- `index.html:6702` — `MARKETING_MONTHLY_PERFORMANCE_DRAFT`: despite “monthly” in its name, it contains only one `YTD` row.
- `index.html:6706` — `MARKETING_MONTHLY_FUNNEL_SPEND_DRAFT`: one YTD funnel-spend row.
- `index.html:6710` — `MARKETING_FUNNEL_DRAFT`: awareness, consideration, and conversion funnel metrics.
- `index.html:6716` — `MARKETING_CHANNEL_PERFORMANCE_DRAFT`: channel-level spend and performance.
- `index.html:6735` — `MARKETING_INFLUENCER_PERFORMANCE_DRAFT`: one aggregate influencer/creator row.

## Acquisition — Affiliate Marketing

- `index.html:6100` — `AFFILIATE_MARKETING_DRAFT`: four affiliate source totals.
- `index.html:6108` — `AFFILIATE_MONTHLY_PERFORMANCE_DRAFT`: January through May traffic and conversions.
- `index.html:6116` — `AFFILIATE_PARTNER_PERFORMANCE_DRAFT`: traffic and conversions for six partners.

## Retention — Retention Analysis

Nine literal `TBD` values represent three unavailable cohort milestones:

- `index.html:4877` — 2023 cohort, “Active Beyond 37 Months”: golfers, percentage, and comparison are all `TBD`.
- `index.html:4926` — 2024 cohort, “Active Beyond 25 Months”: three `TBD` values.
- `index.html:4932` — 2024 cohort, “Active Beyond 37 Months”: three `TBD` values.

## Recovery

No independently labeled draft, mock, or TBD data was found. Recovery shares the empty June through December 2026 rows in `DATA`.

## Segmentation

No placeholder, draft, mock, TODO, or TBD values were found. `Unknown` age/gender entries are data categories, not placeholder markers.

## TODO audit

No `TODO`, `FIXME`, or `XXX` comments were found.
