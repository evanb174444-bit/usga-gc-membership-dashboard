# Monthly GC dashboard runbook

## Trigger

When the user says “run the latest GC numbers” or equivalent, execute this workflow without requiring them to create folders, rename files, or move downloads manually.

## Reporting-period convention

- The report snapshot is normally captured on the first or second day of a month.
- Create `data/raw/YYYY-MM/` using the snapshot month.
- `scripts/update_dashboard_data.py --month YYYY-MM` stores completed-month activity under the immediately preceding calendar month.
- Example: the September 2, 2026 delivery is the September snapshot, and its completed activity month is August 2026.
- Active membership and rolling-retention values are snapshot metrics. August acquisition, renewal, and recovery totals are activity metrics.

## Source intake

1. Find the newest intended `Golfer Detail Report*.csv` in the user’s Downloads folder.
2. Confirm its timestamp and expected Golfer Detail headers.
3. Copy it to `data/raw/YYYY-MM/Current Month_Golfer Detail.csv`.
4. Find the same-date snapshot from the prior year, typically named like `GC Golfer Clubs  MMDDYYYY...csv`.
5. Copy it to `data/raw/YYYY-MM/same_month_prior_year_report.csv`.
6. Obtain the three-months-prior source from the existing raw folder three calendar months earlier. Copy that folder’s `Current Month_GC Golfer Clubs.csv` to `data/raw/YYYY-MM/Three-Months-Prior_GC Golfer Clubs.csv`.
7. Verify copied files byte-for-byte when copying from an existing raw folder. Never move or delete the source download.

Optional section inputs in the same monthly folder:

- `Yearly Statistics.csv`
- `Trials Created by Day.csv`
- `Trial Conversions by Day.csv`
- `Conversions by Days in Trial.csv`
- `AGA Conversions.csv`
- `marketing_workbook.xlsx`

Do not reuse prior-month GHIN Trial or marketing files as if they were current. Run and publish those sections only when their current inputs arrive.

## Core calculation command

Run core membership while marketing is pending:

```sh
python3 scripts/update_dashboard_data.py --month YYYY-MM --skip-marketing
```

The full core run updates:

- `data/membership_monthly.json`
- `data/segmentation_status.json`
- `data/segmentation_breakdown.json`
- `data/retention_cohorts.json`
- `data/retention_club_rankings.json`
- `data/recovery_analysis.json`

GHIN Trials may be added later with `--ghin-only`. Marketing may be added later with `--marketing-only`.

When running `--ghin-only`, the five Tableau exports refresh only the “All Conversion Data (GC + AGAs)” section. Preserve `gcSummary` and `gcMonthly` unchanged unless current GC-only source data is also supplied and explicitly supported by the updater. Confirm the GC-only headline and monthly chart remain populated after every GHIN-only run.

## Established metric rules

- Active golfers: count Active membership rows in Current Month Golfer Detail without GHIN deduplication.
- New golfers: membership creation date falls in the completed activity month.
- Reactivations and Recovery latest-month recoveries must use exactly the same filter: current Active row, status date in the activity month, creation date outside that month, and creation date not after status date.
- The membership and Recovery modules must reconcile to the same latest-month reactivation count before publication.
- On-time renewal uses the three-months-prior eligibility file and the established renewal calculation in the updater.
- Rolling 12-month retention uses the established active-anywhere methodology: distinct active GHINs in the same-date prior-year snapshot form the denominator, and those GHINs Active anywhere in the current Golfer Detail snapshot form the numerator.
- Retention is not a same-club metric.

## QA interpretation

- A first run for a new snapshot has no existing same-period dashboard baseline.
- The prior live month may be shown only as month-over-month context. Expected differences must be labeled `CHANGE`, never `FAIL`.
- Pass/fail parity is valid only when rerunning against an existing populated record for the same activity period.
- Review source-schema checks, internal reconciliations, duplicate membership rows, invalid dates, and section-specific warnings before publication.
- Do not describe a successful new-month calculation as failed merely because it differs from the prior live snapshot.

## Dashboard dates and comparisons

- Header report date: the actual delivery date, such as September 2, 2026.
- Active membership wording: “as of September 1, 2026,” compared with “September 1, 2025.”
- Monthly activity wording: “August 2026,” compared with “August 2025.”
- Primary KPI badges compare the equivalent prior-year period, not the immediately preceding month.
- Snapshot KPIs compare matching report-date snapshots.
- Activity KPIs compare matching calendar activity periods.
- Changes between rates are percentage-point differences (`pts`), not relative percentages.
- Month-over-month movement belongs in trend charts or secondary context.
- Rolling 12-month retention’s primary comparison is the matching prior-year snapshot. Example: September 1, 2026 versus September 1, 2025.
- Period dropdowns must default on every page load to the latest populated month and year. A user may change them during the session, but a reload returns to the latest data.

## Visual QA

- Serve the dashboard locally with `PORT=8000 ./scripts/serve_dashboard.sh`.
- Verify Summary, Acquisition, Retention, Recovery, and Segmentation in a browser.
- Check every KPI value, basis label, date, percent-versus-point format, and chart endpoint.
- Ensure chart scales accommodate the latest value; labels and growth badges must not overlap.
- When GitHub Pages appears unchanged after a push, verify the deployed HTML first, then use a hard refresh or commit-specific cache-busting query string.

## Publishing

- Raw source files and backups are ignored by Git and must remain local.
- Keep unrelated user changes out of a scoped commit unless the user explicitly asks to push everything.
- Push to GitHub only when explicitly requested.
- After pushing, report the commit hash and verify the deployed page contains the updated source.
