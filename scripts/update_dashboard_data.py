#!/usr/bin/env python3
"""Dry-run preview for the monthly dashboard data updater.

This phase validates the monthly four-file input package, loads the existing
cumulative JSON state, calculates dashboard outputs, plans a backup location,
and prints a QA summary. JSON writes are intentionally disabled during dry runs.

Reporting convention
--------------------
``--month YYYY-MM`` is the report month, normally run on the first day of that
month. Source files belong in ``data/raw/YYYY-MM/`` under the report month.
Those report-date snapshots produce dashboard metrics and a dashboard label for
the immediately preceding calendar month.

Example: ``--month 2026-07`` reads ``data/raw/2026-07/`` as the July 1, 2026
snapshot and calculates the June 2026 dashboard record.

Monthly source responsibilities
-------------------------------
* ``Current Month_Golfer Detail.csv`` is the master current-month export for
  membership, segmentation, retention, and recovery JSON generation.
* ``same_month_prior_year_report.csv`` supplies the prior-year active cohort
  for the 12-month retention comparison.
* ``Three-Months-Prior_GC Golfer Clubs.csv`` supplies up-for-renewal
  eligibility only.
* ``marketing_workbook.xlsx`` supplies marketing outputs when implemented.
* GHIN Trials can be generated from five aggregate Tableau CSV exports when
  present: ``Yearly Statistics.csv``, ``Trials Created by Day.csv``,
  ``Trial Conversions by Day.csv``, ``Conversions by Days in Trial.csv``,
  and ``AGA Conversions.csv``.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import math
import re
import shutil
import statistics
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree


REQUIRED_INPUT_FILENAMES = {
    "current golfer detail": "Current Month_Golfer Detail.csv",
    "same-month prior-year report": "same_month_prior_year_report.csv",
    "three-months-prior GC golfer clubs": "Three-Months-Prior_GC Golfer Clubs.csv",
    "marketing workbook": "marketing_workbook.xlsx",
}

EXISTING_JSON_FILENAMES = (
    "membership_monthly.json",
    "ghin_trials.json",
    "segmentation_status.json",
    "segmentation_breakdown.json",
    "retention_club_rankings.json",
    "retention_cohorts.json",
)

GHIN_TABLEAU_FILENAMES = {
    "yearly statistics": "Yearly Statistics.csv",
    "trials created by day": "Trials Created by Day.csv",
    "trial conversions by day": "Trial Conversions by Day.csv",
    "conversions by days in trial": "Conversions by Days in Trial.csv",
    "aga conversions": "AGA Conversions.csv",
}

RAW_SOURCE_SUFFIXES = {".csv", ".xlsx", ".xls"}

FIELD_ALIASES = {
    "golfer_id": ("golfer_id", "member_id", "membership_id", "ghin_number", "ghin", "id"),
    "status": ("status", "membership_status", "golfer_status"),
    "golf_association": ("golf_association", "golf_association_id"),
    "created_date": ("membership_creation_date", "membership_created_date", "created_date", "join_date", "created_at"),
    "is_new_golfer": ("is_new_golfer", "new_golfer", "new_golfer_flag"),
    "reactivation_date": ("golfer_status_date", "reactivation_date", "reactivated_date", "last_reactivation_date"),
    "is_reactivation": ("is_reactivation", "reactivation", "reactivation_flag"),
}

TRUE_VALUES = {"1", "true", "t", "yes", "y"}
FALSE_VALUES = {"0", "false", "f", "no", "n", ""}
ACTIVE_STATUS_VALUES = {"active", "current"}

GOLFER_DETAIL_REQUIRED_HEADERS = {
    "ghin_number",
    "local_number",
    "full_name",
    "club_number",
    "club_name",
    "golfer_status",
    "membership_creation_date",
    "golfer_status_date",
    "usga_membership_type",
    "handicap_index",
    "gender",
    "date_of_birth",
}

RENEWAL_ELIGIBILITY_REQUIRED_HEADERS = {
    "golfer_id",
    "status",
    "inactive_date",
}

SEGMENTATION_BREAKDOWN_REQUIRED_HEADERS = {
    "club_name",
    "golfer_status",
    "gender",
    "date_of_birth",
}

SEGMENTATION_STATUSES = ("Active", "Archived", "Inactive")
AGE_SEGMENTS = (
    "18–24",
    "25–34",
    "35–44",
    "45–54",
    "55–64",
    "65+",
    "Under 18",
    "Unknown",
)
GENDER_SEGMENTS = ("Female", "Male", "Unknown")
MAX_PLAUSIBLE_AGE = 120

RETENTION_COHORT_YEARS = (2022, 2023, 2024)
RETENTION_MILESTONE_MONTHS = (13, 25, 37)
RETENTION_COHORT_COLORS = {
    2022: "#14395f",
    2023: "#d85a32",
    2024: "#188552",
}

RECOVERY_AGE_BUCKETS = (
    ("Under 13 months", 0, 12),
    ("13–24 months", 13, 24),
    ("25–36 months", 25, 36),
    ("37–60 months", 37, 60),
)

MEMBERSHIP_PARITY_METRICS = (
    "activeGolfers",
    "newGolfers",
    "reactivations",
    "renewed",
    "upForRenewal",
    "onTimeRenewalRate",
    "retentionRate",
    "netChange",
    "percentChange",
)

MEMBERSHIP_RATE_METRICS = {
    "onTimeRenewalRate",
    "retentionRate",
    "percentChange",
}

METHODOLOGY_CHANGE_METRICS = {
    "renewed",
    "onTimeRenewalRate",
    "retentionRate",
}

PARITY_ABSOLUTE_TOLERANCE = 1e-9


class ValidationError(RuntimeError):
    """Raised when the monthly input package or cumulative state is invalid."""


@dataclass(frozen=True)
class InputFileSummary:
    label: str
    path: Path
    size_bytes: int
    data_rows: int | None = None
    sheet_count: int | None = None


@dataclass(frozen=True)
class JsonStateSummary:
    path: Path
    top_level_type: str
    row_count: int


@dataclass(frozen=True)
class CsvSnapshot:
    label: str
    path: Path
    headers: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class ParityResult:
    metric: str
    calculated_value: Any
    dashboard_value: Any
    difference: int | float | None
    passed: bool
    result_label: str


@dataclass(frozen=True)
class MetricGrainCount:
    membership_rows: int
    distinct_golfers: int


@dataclass(frozen=True)
class SegmentationDiagnostics:
    output_filename: str
    source_label: str
    source_rows: int
    target_records: int
    existing_target_records: int
    merged_records: int
    preserved_historical_records: int
    clubs: int
    status_counts: dict[str, int]
    missing_gender_rows: int = 0
    unknown_gender_rows: int = 0
    missing_birth_date_rows: int = 0
    implausible_birth_date_rows: int = 0


@dataclass(frozen=True)
class RetentionDiagnostics:
    source_rows: int
    status_counts: dict[str, int]
    missing_creation_dates: int
    missing_inactive_status_dates: int
    invalid_status_dates_by_status: dict[str, int]
    cohort_created: dict[int, int]
    cohort_active_today: dict[int, int]
    cohort_milestones: dict[tuple[int, int], int | None]
    baseline_created: dict[int, int]
    baseline_active_today: dict[int, int]
    baseline_milestones: dict[tuple[int, int], int | None]
    club_count: int
    club_created_total: int
    baseline_club_created_total: int
    exact_club_total_matches: int
    maximum_club_total_difference: int
    identical_rank_positions: int
    maximum_rank_shift: int


@dataclass(frozen=True)
class RecoveryDiagnostics:
    source_rows: int
    active_rows: int
    qualifying_recovery_rows: int
    distinct_recovery_ghins: int
    latest_month_recoveries: int
    clubs_with_recoveries: int
    missing_creation_dates: int
    missing_status_dates: int
    creation_not_before_status_rows: int
    club_breakdown_reconciles: bool
    creation_year_breakdown_reconciles: bool
    membership_age_breakdown_reconciles: bool


@dataclass(frozen=True)
class GhinTrialsDiagnostics:
    source_files: dict[str, Path]
    source_row_counts: dict[str, int]
    date_coverage: dict[str, tuple[str | None, str | None]]
    generated_summary: dict[str, Any]
    monthly_records: int
    monthly_trials_total: int
    monthly_conversions_total: int
    conversion_bucket_records: int
    conversion_bucket_total: int
    aga_records: int
    aga_total: int
    overview_campaigns_preserved: int
    overview_funnel_preserved: int
    parity_differences: list[str]


@dataclass
class QAReport:
    report_month: str
    activity_month: str
    dry_run: bool
    raw_directory: Path
    backup_directory: Path
    inputs: list[InputFileSummary] = field(default_factory=list)
    json_state: list[JsonStateSummary] = field(default_factory=list)
    checks: list[tuple[str, str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    membership_record: dict[str, Any] | None = None
    membership_parity: list[ParityResult] = field(default_factory=list)
    membership_grain_counts: dict[str, MetricGrainCount] = field(default_factory=dict)
    parity_baseline_label: str | None = None
    parity_baseline_is_fallback: bool = False
    calculation_notes: list[str] = field(default_factory=list)
    segmentation_diagnostics: list[SegmentationDiagnostics] = field(
        default_factory=list
    )
    retention_diagnostics: RetentionDiagnostics | None = None
    recovery_diagnostics: RecoveryDiagnostics | None = None
    recovery_output: dict[str, Any] | None = None
    ghin_trials_diagnostics: GhinTrialsDiagnostics | None = None
    ghin_trials_output: dict[str, Any] | None = None
    written_outputs: list[Path] = field(default_factory=list)

    def add_check(self, name: str, status: str, detail: str) -> None:
        self.checks.append((name, status, detail))


def parse_month(value: str) -> str:
    """Validate and normalize a YYYY-MM reporting month."""
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid month {value!r}; expected YYYY-MM"
        ) from exc
    normalized = parsed.strftime("%Y-%m")
    if normalized != value:
        raise argparse.ArgumentTypeError(
            f"invalid month {value!r}; expected zero-padded YYYY-MM"
        )
    return normalized


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the monthly four-file dashboard input package and plan a cumulative "
            "JSON update. --month is the report month; the dashboard output month "
            "is the prior calendar month. This preview does not write JSON."
        ),
        epilog=(
            "Example: --month 2026-07 reads data/raw/2026-07/ as the July 1, 2026 "
            "report snapshot and calculates the June 2026 dashboard record. Required "
            "monthly files are Current Month_Golfer Detail.csv, "
            "same_month_prior_year_report.csv, Three-Months-Prior_GC Golfer Clubs.csv, "
            "and marketing_workbook.xlsx."
        ),
    )
    parser.add_argument(
        "--month",
        required=True,
        type=parse_month,
        metavar="YYYY-MM",
        help=(
            "report month and data/raw/YYYY-MM directory, normally run on its first day; "
            "dashboard output is labeled for the prior calendar month"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="disable all output writes and print the planned update",
    )
    parser.add_argument(
        "--skip-marketing",
        action="store_true",
        help=(
            "development-only escape hatch: validate/generate non-marketing outputs "
            "without marketing_workbook.xlsx"
        ),
    )
    parser.add_argument(
        "--ghin-only",
        action="store_true",
        help=(
            "validate and generate GHIN Trials JSON from Tableau aggregate CSVs only; "
            "useful before the full monthly input package is available"
        ),
    )
    return parser.parse_args(argv)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def planned_backup_directory(data_dir: Path, month: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return data_dir / "backups" / month / timestamp


def detect_csv_format(path: Path) -> tuple[str, str]:
    """Detect the two supported export formats by byte-order mark."""
    try:
        with path.open("rb") as handle:
            prefix = handle.read(4)
    except OSError as exc:
        raise ValidationError(f"CSV could not be opened: {path}: {exc}") from exc
    if prefix.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16", "\t"
    return "utf-8-sig", ","


def trim_trailing_empty_cells(row: list[str]) -> list[str]:
    """Ignore empty trailing fields emitted by the UTF-16 tab export."""
    while row and not row[-1].strip():
        row.pop()
    return row


def count_csv_rows(path: Path) -> int:
    """Perform a lightweight CSV structural check and count data rows."""
    encoding, delimiter = detect_csv_format(path)
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            raw_header = next(reader, None)
            header = trim_trailing_empty_cells(raw_header) if raw_header else None
            if not header or not any(cell.strip() for cell in header):
                raise ValidationError(f"CSV has no header row: {path}")
            if len(set(header)) != len(header):
                raise ValidationError(f"CSV contains duplicate headers: {path}")
            return sum(
                1
                for row in reader
                if any(cell.strip() for cell in trim_trailing_empty_cells(row))
            )
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"CSV is not a supported UTF-8 comma or UTF-16 tab export: {path}"
        ) from exc
    except csv.Error as exc:
        raise ValidationError(f"CSV could not be parsed: {path}: {exc}") from exc


def normalize_header(value: str) -> str:
    """Normalize common CSV header styles to lowercase snake_case."""
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value.strip())
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_").lower()


def read_csv_snapshot(path: Path, label: str) -> CsvSnapshot:
    """Read a golfer-level snapshot and normalize its column names."""
    encoding, delimiter = detect_csv_format(path)
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            raw_headers = next(reader, None)
            if not raw_headers:
                raise ValidationError(f"CSV has no header row: {path}")
            raw_headers = trim_trailing_empty_cells(raw_headers)
            headers = tuple(normalize_header(name) for name in raw_headers)
            if any(not name for name in headers):
                raise ValidationError(f"CSV contains a blank header: {path}")
            if len(set(headers)) != len(headers):
                raise ValidationError(
                    f"CSV headers collide after normalization: {path}"
                )
            parsed_rows: list[dict[str, str]] = []
            for row_number, raw_row in enumerate(reader, start=2):
                raw_row = trim_trailing_empty_cells(raw_row)
                if not any(value.strip() for value in raw_row):
                    continue
                if len(raw_row) > len(headers):
                    raise ValidationError(
                        f"{label} has more values than headers at CSV row {row_number}"
                    )
                padded_row = raw_row + [""] * (len(headers) - len(raw_row))
                parsed_rows.append(
                    {
                        header: padded_row[index].strip()
                        for index, header in enumerate(headers)
                    }
                )
            rows = tuple(parsed_rows)
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"CSV is not a supported UTF-8 comma or UTF-16 tab export: {path}"
        ) from exc
    except csv.Error as exc:
        raise ValidationError(f"CSV could not be parsed: {path}: {exc}") from exc
    if not rows:
        raise ValidationError(f"CSV contains no data rows: {path}")
    return CsvSnapshot(label=label, path=path, headers=headers, rows=rows)


def read_tableau_rows(path: Path) -> list[list[str]]:
    """Read a Tableau CSV export, including UTF-16 tab-delimited crosstabs."""
    encoding, delimiter = detect_csv_format(path)
    rows: list[list[str]] = []
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            for raw_row in reader:
                row = trim_trailing_empty_cells([cell.strip() for cell in raw_row])
                if any(cell for cell in row):
                    rows.append(row)
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"Tableau CSV is not a supported UTF-8 comma or UTF-16 tab export: {path}"
        ) from exc
    except csv.Error as exc:
        raise ValidationError(
            f"Tableau CSV could not be parsed: {path}: {exc}"
        ) from exc
    if not rows:
        raise ValidationError(f"Tableau CSV contains no rows: {path}")
    return rows


def resolve_field(
    snapshot: CsvSnapshot,
    logical_name: str,
    *,
    required: bool = True,
) -> str | None:
    """Resolve one logical field through the documented header aliases."""
    aliases = FIELD_ALIASES[logical_name]
    matches = [alias for alias in aliases if alias in snapshot.headers]
    if len(matches) > 1:
        raise ValidationError(
            f"{snapshot.label} contains multiple aliases for {logical_name}: "
            + ", ".join(matches)
        )
    if matches:
        return matches[0]
    if required:
        raise ValidationError(
            f"{snapshot.label} is missing {logical_name}; accepted headers: "
            + ", ".join(aliases)
        )
    return None


def require_headers(
    snapshot: CsvSnapshot,
    required_headers: set[str],
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> None:
    """Require the corrected current-month export contract exactly by meaning."""
    aliases = aliases or {}
    available = set(snapshot.headers)
    missing = sorted(
        header
        for header in required_headers
        if header not in available
        and not any(alias in available for alias in aliases.get(header, ()))
    )
    if missing:
        raise ValidationError(
            f"{snapshot.label} is missing required headers: " + ", ".join(missing)
        )


def validate_current_source_contract(
    golfer_detail: CsvSnapshot,
    prior_golfer_clubs: CsvSnapshot,
) -> tuple[int, int]:
    """Validate the core detail and renewal-eligibility source contracts."""
    require_headers(golfer_detail, GOLFER_DETAIL_REQUIRED_HEADERS)
    require_headers(prior_golfer_clubs, RENEWAL_ELIGIBILITY_REQUIRED_HEADERS)

    detail_rows_by_id, _ = snapshot_rows_grouped_by_id(golfer_detail)
    prior_ids = gc_golfer_ids(prior_golfer_clubs)
    return len(detail_rows_by_id), len(prior_ids)


def gc_golfer_ids(snapshot: CsvSnapshot) -> set[str]:
    """Return unique golfer IDs from a one-to-many GC Golfer Clubs export."""
    golfer_ids: set[str] = set()
    for row_number, row in enumerate(snapshot.rows, start=2):
        golfer_id = row["golfer_id"].strip()
        if not golfer_id:
            raise ValidationError(
                f"{snapshot.label} has a blank golfer_id at CSV row {row_number}"
            )
        golfer_ids.add(golfer_id)
    return golfer_ids


def parse_boolean(value: str, context: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValidationError(f"invalid boolean value {value!r} in {context}")


def parse_source_date(value: str, context: str) -> date | None:
    """Parse supported CSV date formats; blank values remain null."""
    value = value.strip()
    if not value:
        return None
    for pattern in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValidationError(f"unsupported date value {value!r} in {context}")


def target_year_month(month: str) -> tuple[int, int]:
    parsed = datetime.strptime(month, "%Y-%m")
    return parsed.year, parsed.month


def is_target_month(value: date | None, year: int, month: int) -> bool:
    return value is not None and value.year == year and value.month == month


def snapshot_rows_grouped_by_id(
    snapshot: CsvSnapshot,
) -> tuple[dict[str, list[dict[str, str]]], str]:
    """Group one or more membership rows under each distinct golfer ID."""
    id_field = resolve_field(snapshot, "golfer_id")
    rows_by_id: dict[str, list[dict[str, str]]] = {}
    for row_number, row in enumerate(snapshot.rows, start=2):
        golfer_id = row[id_field].strip()
        if not golfer_id:
            raise ValidationError(
                f"{snapshot.label} has a blank golfer ID at CSV row {row_number}"
            )
        rows_by_id.setdefault(golfer_id, []).append(row)
    return rows_by_id, id_field


def active_ids(
    snapshot: CsvSnapshot,
) -> tuple[set[str], dict[str, list[dict[str, str]]]]:
    """Return distinct golfers having at least one active membership row."""
    rows_by_id, _ = snapshot_rows_grouped_by_id(snapshot)
    status_field = resolve_field(snapshot, "status")
    statuses = {row[status_field].strip().lower() for row in snapshot.rows}
    if not statuses & ACTIVE_STATUS_VALUES:
        raise ValidationError(
            f"{snapshot.label} has no recognized active status; expected Active or Current"
        )
    active = {
        golfer_id
        for golfer_id, golfer_rows in rows_by_id.items()
        if any(
            row[status_field].strip().lower() in ACTIVE_STATUS_VALUES
            for row in golfer_rows
        )
    }
    return active, rows_by_id


def count_active_membership_rows(snapshot: CsvSnapshot) -> int:
    """Count Active membership rows without deduplicating golfer IDs."""
    status_field = resolve_field(snapshot, "status")
    return sum(
        row[status_field].strip().lower() in ACTIVE_STATUS_VALUES
        for row in snapshot.rows
    )


def count_monthly_event(
    snapshot: CsvSnapshot,
    year: int,
    month: int,
    *,
    date_field_name: str,
    flag_field_name: str,
    metric_label: str,
) -> tuple[MetricGrainCount, str]:
    """Count monthly events at membership-row and distinct-golfer grain."""
    rows_by_id, _ = snapshot_rows_grouped_by_id(snapshot)
    date_field = resolve_field(snapshot, date_field_name, required=False)
    if date_field:
        matching_ids = {
            golfer_id
            for golfer_id, golfer_rows in rows_by_id.items()
            if any(
                is_target_month(
                    parse_source_date(
                        row[date_field],
                        f"{snapshot.label} {date_field} for golfer {golfer_id}",
                    ),
                    year,
                    month,
                )
                for row in golfer_rows
            )
        }
        matching_rows = sum(
            is_target_month(
                parse_source_date(
                    row[date_field],
                    f"{snapshot.label} {date_field}",
                ),
                year,
                month,
            )
            for row in snapshot.rows
        )
        return (
            MetricGrainCount(matching_rows, len(matching_ids)),
            f"{metric_label} membership rows and distinct GHIN Numbers counted from {date_field}",
        )

    flag_field = resolve_field(snapshot, flag_field_name, required=False)
    if flag_field:
        matching_ids = {
            golfer_id
            for golfer_id, golfer_rows in rows_by_id.items()
            if any(
                parse_boolean(
                    row[flag_field],
                    f"{snapshot.label} {flag_field} for golfer {golfer_id}",
                )
                for row in golfer_rows
            )
        }
        matching_rows = sum(
            parse_boolean(
                row[flag_field],
                f"{snapshot.label} {flag_field}",
            )
            for row in snapshot.rows
        )
        return (
            MetricGrainCount(matching_rows, len(matching_ids)),
            f"{metric_label} membership rows and distinct GHIN Numbers counted from {flag_field}",
        )

    raise ValidationError(
        f"{snapshot.label} cannot calculate {metric_label}; provide one of "
        f"{FIELD_ALIASES[date_field_name] + FIELD_ALIASES[flag_field_name]}"
    )


def count_current_reactivations(
    snapshot: CsvSnapshot,
    year: int,
    month: int,
) -> tuple[MetricGrainCount, str]:
    """Count active status changes in the target month that are not new joins."""
    rows_by_id, _ = snapshot_rows_grouped_by_id(snapshot)
    status_field = resolve_field(snapshot, "status")
    status_date_field = resolve_field(snapshot, "reactivation_date")
    created_date_field = resolve_field(snapshot, "created_date")
    matching_ids: set[str] = set()
    matching_rows = 0
    for golfer_id, golfer_rows in rows_by_id.items():
        golfer_matches = 0
        for row in golfer_rows:
            status_date = parse_source_date(
                row[status_date_field],
                f"{snapshot.label} {status_date_field} for golfer {golfer_id}",
            )
            created_date = parse_source_date(
                row[created_date_field],
                f"{snapshot.label} {created_date_field} for golfer {golfer_id}",
            )
            if (
                row[status_field].strip().lower() in ACTIVE_STATUS_VALUES
                and is_target_month(status_date, year, month)
                and not is_target_month(created_date, year, month)
                and (created_date is None or created_date <= status_date)
            ):
                golfer_matches += 1
        if golfer_matches:
            matching_ids.add(golfer_id)
            matching_rows += golfer_matches
    return (
        MetricGrainCount(matching_rows, len(matching_ids)),
        "reactivation membership rows and distinct GHIN Numbers counted as current Active "
        "rows with golfer_status_date in the target month and "
        "membership_creation_date outside the target month but not after golfer_status_date",
    )


def count_xlsx_sheets(path: Path) -> int:
    """Validate the XLSX container and return its declared worksheet count."""
    workbook_xml = "xl/workbook.xml"
    try:
        with zipfile.ZipFile(path) as archive:
            if workbook_xml not in archive.namelist():
                raise ValidationError(
                    f"workbook is missing {workbook_xml}: {path}"
                )
            root = ElementTree.fromstring(archive.read(workbook_xml))
    except (zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValidationError(f"workbook is not a valid XLSX file: {path}") from exc

    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    sheets = root.findall("main:sheets/main:sheet", namespace)
    return len(sheets)


def discover_inputs(
    raw_directory: Path,
    *,
    skip_marketing: bool = False,
) -> list[InputFileSummary]:
    """Locate and minimally validate the required monthly source files."""
    if not raw_directory.is_dir():
        raise ValidationError(f"raw input directory does not exist: {raw_directory}")

    required_paths = {
        label: raw_directory / filename
        for label, filename in REQUIRED_INPUT_FILENAMES.items()
        if not (skip_marketing and label == "marketing workbook")
    }
    missing = [path.name for path in required_paths.values() if not path.is_file()]
    if missing:
        raise ValidationError(
            "missing required input files: " + ", ".join(sorted(missing))
        )

    summaries: list[InputFileSummary] = []
    for label, path in required_paths.items():
        size_bytes = path.stat().st_size
        if size_bytes <= 0:
            raise ValidationError(f"input file is empty: {path}")
        if path.suffix.lower() == ".csv":
            summaries.append(
                InputFileSummary(
                    label=label,
                    path=path,
                    size_bytes=size_bytes,
                    data_rows=count_csv_rows(path),
                )
            )
        else:
            sheet_count = count_xlsx_sheets(path)
            if sheet_count != 3:
                raise ValidationError(
                    f"marketing workbook must contain exactly 3 sheets; "
                    f"found {sheet_count}: {path}"
                )
            summaries.append(
                InputFileSummary(
                    label=label,
                    path=path,
                    size_bytes=size_bytes,
                    sheet_count=sheet_count,
                )
            )
    return summaries


def load_existing_json_state(data_directory: Path) -> tuple[dict[str, Any], list[JsonStateSummary]]:
    """Load the existing cumulative JSON outputs without modifying them."""
    state: dict[str, Any] = {}
    summaries: list[JsonStateSummary] = []
    missing: list[str] = []

    for filename in EXISTING_JSON_FILENAMES:
        path = data_directory / filename
        if not path.is_file():
            missing.append(filename)
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"existing JSON could not be loaded: {path}: {exc}") from exc
        if not isinstance(value, (list, dict)):
            raise ValidationError(
                f"existing JSON must contain a top-level array or object: {path}"
            )
        row_count = len(value) if isinstance(value, list) else sum(
            len(item) for item in value.values() if isinstance(item, list)
        )
        state[filename] = value
        summaries.append(
            JsonStateSummary(
                path=path,
                top_level_type="array" if isinstance(value, list) else "object",
                row_count=row_count,
            )
        )

    if missing:
        raise ValidationError(
            "missing existing JSON state files: " + ", ".join(sorted(missing))
        )
    return state, summaries


def previous_month_active(membership_state: Any, target_month: str) -> int:
    """Read the immediately preceding active count from cumulative JSON state."""
    if not isinstance(membership_state, list):
        raise ValidationError("membership_monthly.json must contain a top-level array")
    year, month = target_year_month(target_month)
    previous_year, previous_month = (year - 1, 12) if month == 1 else (year, month - 1)
    matches = [
        row
        for row in membership_state
        if isinstance(row, dict)
        and row.get("year") == previous_year
        and row.get("monthNum") == previous_month
    ]
    if len(matches) != 1:
        raise ValidationError(
            f"membership_monthly.json must contain exactly one previous-month record "
            f"for {previous_year}-{previous_month:02d}"
        )
    value = matches[0].get("activeGolfers")
    if not isinstance(value, int) or value < 0:
        raise ValidationError(
            f"previous-month activeGolfers is not a nonnegative integer for "
            f"{previous_year}-{previous_month:02d}"
        )
    return value


def target_membership_record(
    membership_state: Any,
    target_month: str,
) -> dict[str, Any]:
    """Load exactly one existing dashboard record for the reporting month."""
    if not isinstance(membership_state, list):
        raise ValidationError("membership_monthly.json must contain a top-level array")
    year, month = target_year_month(target_month)
    matches = [
        row
        for row in membership_state
        if isinstance(row, dict)
        and row.get("year") == year
        and row.get("monthNum") == month
    ]
    if len(matches) != 1:
        raise ValidationError(
            "membership_monthly.json must contain exactly one target-month "
            f"record for {target_month}"
        )
    return matches[0]


def previous_calendar_month(target_month: str) -> tuple[int, int]:
    year, month = target_year_month(target_month)
    return (year - 1, 12) if month == 1 else (year, month - 1)


def activity_month_for_report(report_month: str) -> str:
    """Map a report-month snapshot to its prior-calendar-month dashboard label."""
    year, month = previous_calendar_month(report_month)
    return f"{year}-{month:02d}"


def display_month(month: str) -> str:
    year, month_number = target_year_month(month)
    return datetime(year, month_number, 1).strftime("%B %Y")


def display_report_date(report_month: str) -> str:
    year, month_number = target_year_month(report_month)
    return datetime(year, month_number, 1).strftime("%B 1, %Y")


def normalize_segmentation_status(value: str, context: str) -> str:
    """Map source status text to the three dashboard status labels."""
    normalized = value.strip().lower()
    mapping = {status.lower(): status for status in SEGMENTATION_STATUSES}
    if normalized not in mapping:
        raise ValidationError(
            f"unsupported golfer status {value!r} in {context}; expected "
            + ", ".join(SEGMENTATION_STATUSES)
        )
    return mapping[normalized]


def normalize_gender_segment(value: str) -> tuple[str, bool, bool]:
    """Return dashboard gender label plus missing/unrecognized diagnostics."""
    normalized = value.strip().lower()
    if normalized in {"f", "female"}:
        return "Female", False, False
    if normalized in {"m", "male"}:
        return "Male", False, False
    if not normalized:
        return "Unknown", True, False
    return "Unknown", False, True


def age_segment(
    birth_date_value: str,
    report_date: date,
    context: str,
) -> tuple[str, bool, bool]:
    """Bucket age as of the report date and flag missing/implausible dates."""
    birth_date = parse_source_date(birth_date_value, context)
    if birth_date is None:
        return "Unknown", True, False
    age = report_date.year - birth_date.year - (
        (report_date.month, report_date.day)
        < (birth_date.month, birth_date.day)
    )
    if age < 0 or age > MAX_PLAUSIBLE_AGE:
        return "Unknown", False, True
    if age < 18:
        return "Under 18", False, False
    if age <= 24:
        return "18–24", False, False
    if age <= 34:
        return "25–34", False, False
    if age <= 44:
        return "35–44", False, False
    if age <= 54:
        return "45–54", False, False
    if age <= 64:
        return "55–64", False, False
    return "65+", False, False


def segmentation_club_names(snapshot: CsvSnapshot) -> list[str]:
    """Return sorted source club names after rejecting blank club values."""
    club_names: set[str] = set()
    for row_number, row in enumerate(snapshot.rows, start=2):
        club_name = row["club_name"].strip()
        if not club_name:
            raise ValidationError(
                f"{snapshot.label} has a blank club_name at CSV row {row_number}"
            )
        club_names.add(club_name)
    return sorted(club_names)


def generate_segmentation_status_records(
    report_month: str,
    activity_month: str,
    current_detail: CsvSnapshot,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Generate All and club status records directly from Golfer Detail rows."""
    require_headers(current_detail, {"club_name", "golfer_status"})
    year, month_number = target_year_month(activity_month)
    month_name = datetime(year, month_number, 1).strftime("%B")
    report_date_label = display_report_date(report_month)
    club_names = segmentation_club_names(current_detail)
    counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row_number, row in enumerate(current_detail.rows, start=2):
        club_name = row["club_name"].strip()
        status = normalize_segmentation_status(
            row["golfer_status"],
            f"{current_detail.label} golfer_status at CSV row {row_number}",
        )
        counts["All"][status] += 1
        counts[club_name][status] += 1

    records: list[dict[str, Any]] = []
    for club_name in ["All", *club_names]:
        active = counts[club_name]["Active"]
        inactive = counts[club_name]["Inactive"]
        archived = counts[club_name]["Archived"]
        total = active + inactive + archived
        records.append(
            {
                "year": year,
                "month": month_name,
                "monthNum": month_number,
                "label": report_date_label,
                "reportDate": report_date_label,
                "clubName": club_name,
                "inactiveGolfers": inactive,
                "activeGolfers": active,
                "archivedGolfers": archived,
                "totalGolfers": total,
                "inactiveShare": inactive / total if total else 0.0,
                "activeShare": active / total if total else 0.0,
                "archivedShare": archived / total if total else 0.0,
            }
        )

    validate_segmentation_status_records(records, len(club_names) + 1)
    return records, {
        status: counts["All"][status] for status in SEGMENTATION_STATUSES
    }


def validate_segmentation_status_records(
    records: Sequence[dict[str, Any]],
    expected_clubs: int,
) -> None:
    if len(records) != expected_clubs:
        raise ValidationError(
            f"segmentation_status.json generated {len(records)} records; "
            f"expected {expected_clubs}"
        )
    keys: set[tuple[int, int, str]] = set()
    for record in records:
        key = (record["year"], record["monthNum"], record["clubName"])
        if key in keys:
            raise ValidationError(
                f"segmentation_status.json generated duplicate key {key}"
            )
        keys.add(key)
        component_total = sum(
            record[field]
            for field in (
                "activeGolfers",
                "inactiveGolfers",
                "archivedGolfers",
            )
        )
        if component_total != record["totalGolfers"]:
            raise ValidationError(
                f"segmentation status counts do not total for {record['clubName']}"
            )
        share_total = sum(
            record[field]
            for field in ("activeShare", "inactiveShare", "archivedShare")
        )
        expected_share = 1.0 if component_total else 0.0
        if not math.isclose(share_total, expected_share, abs_tol=1e-12):
            raise ValidationError(
                f"segmentation status shares do not total for {record['clubName']}"
            )


def generate_segmentation_breakdown_records(
    report_month: str,
    activity_month: str,
    current_detail: CsvSnapshot,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Generate age/gender breakdowns directly from Golfer Detail rows."""
    require_headers(
        current_detail,
        SEGMENTATION_BREAKDOWN_REQUIRED_HEADERS,
    )
    year, month_number = target_year_month(activity_month)
    month_name = datetime(year, month_number, 1).strftime("%B")
    report_date_value = date(*target_year_month(report_month), 1)
    report_date_label = display_report_date(report_month)
    club_names = segmentation_club_names(current_detail)
    counts: Counter[tuple[str, str, str, str]] = Counter()
    status_totals: Counter[tuple[str, str]] = Counter()
    source_status_counts: Counter[str] = Counter()
    missing_gender_rows = 0
    unknown_gender_rows = 0
    missing_birth_date_rows = 0
    implausible_birth_date_rows = 0

    for row_number, row in enumerate(current_detail.rows, start=2):
        club_name = row["club_name"].strip()
        status = normalize_segmentation_status(
            row["golfer_status"],
            f"{current_detail.label} golfer_status at CSV row {row_number}",
        )
        gender, gender_missing, gender_unknown = normalize_gender_segment(
            row["gender"]
        )
        age, birth_date_missing, birth_date_implausible = age_segment(
            row["date_of_birth"],
            report_date_value,
            (
                f"{current_detail.label} date_of_birth "
                f"at CSV row {row_number}"
            ),
        )
        missing_gender_rows += int(gender_missing)
        unknown_gender_rows += int(gender_unknown)
        missing_birth_date_rows += int(birth_date_missing)
        implausible_birth_date_rows += int(birth_date_implausible)
        source_status_counts[status] += 1

        for output_club in ("All", club_name):
            status_totals[(output_club, status)] += 1
            counts[(output_club, status, "Age", age)] += 1
            counts[(output_club, status, "Gender", gender)] += 1

    records: list[dict[str, Any]] = []
    segment_groups = (("Age", AGE_SEGMENTS), ("Gender", GENDER_SEGMENTS))
    for club_name in ["All", *club_names]:
        for status in SEGMENTATION_STATUSES:
            status_total = status_totals[(club_name, status)]
            for segment_type, segments in segment_groups:
                for segment in segments:
                    golfer_count = counts[
                        (club_name, status, segment_type, segment)
                    ]
                    records.append(
                        {
                            "year": year,
                            "month": month_name,
                            "monthNum": month_number,
                            "reportDate": report_date_label,
                            "clubName": club_name,
                            "status": status,
                            "segmentType": segment_type,
                            "segment": segment,
                            "golferCount": golfer_count,
                            "shareWithinStatus": (
                                golfer_count / status_total
                                if status_total
                                else 0.0
                            ),
                        }
                    )

    validate_segmentation_breakdown_records(records, len(club_names) + 1)
    return records, {
        **{status: source_status_counts[status] for status in SEGMENTATION_STATUSES},
        "missingGender": missing_gender_rows,
        "unknownGender": unknown_gender_rows,
        "missingBirthDate": missing_birth_date_rows,
        "implausibleBirthDate": implausible_birth_date_rows,
    }


def validate_segmentation_breakdown_records(
    records: Sequence[dict[str, Any]],
    expected_clubs: int,
) -> None:
    expected_records = expected_clubs * len(SEGMENTATION_STATUSES) * (
        len(AGE_SEGMENTS) + len(GENDER_SEGMENTS)
    )
    if len(records) != expected_records:
        raise ValidationError(
            f"segmentation_breakdown.json generated {len(records)} records; "
            f"expected {expected_records}"
        )
    keys: set[tuple[Any, ...]] = set()
    grouped_counts: Counter[tuple[str, str, str]] = Counter()
    grouped_shares: defaultdict[tuple[str, str, str], float] = defaultdict(float)
    for record in records:
        key = (
            record["year"],
            record["monthNum"],
            record["clubName"],
            record["status"],
            record["segmentType"],
            record["segment"],
        )
        if key in keys:
            raise ValidationError(
                f"segmentation_breakdown.json generated duplicate key {key}"
            )
        keys.add(key)
        group = (
            record["clubName"],
            record["status"],
            record["segmentType"],
        )
        grouped_counts[group] += record["golferCount"]
        grouped_shares[group] += record["shareWithinStatus"]

    all_totals = {
        status: grouped_counts[("All", status, "Age")]
        for status in SEGMENTATION_STATUSES
    }
    for group, share_total in grouped_shares.items():
        expected_share = 1.0 if grouped_counts[group] else 0.0
        if not math.isclose(share_total, expected_share, abs_tol=1e-12):
            raise ValidationError(
                "segmentation breakdown shares do not total for "
                + "/".join(group)
            )
        club_name, status, segment_type = group
        if segment_type == "Gender":
            age_total = grouped_counts[(club_name, status, "Age")]
            if grouped_counts[group] != age_total:
                raise ValidationError(
                    f"Age/Gender totals differ for {club_name}/{status}"
                )
    if sum(all_totals.values()) <= 0:
        raise ValidationError("segmentation breakdown contains no source rows")


def merge_target_month_records(
    existing_records: Any,
    generated_records: Sequence[dict[str, Any]],
    activity_month: str,
    output_filename: str,
) -> tuple[list[dict[str, Any]], int, int]:
    """Replace one target month in memory while preserving all other records."""
    if not isinstance(existing_records, list) or not all(
        isinstance(record, dict) for record in existing_records
    ):
        raise ValidationError(f"{output_filename} must contain a top-level array")
    year, month_number = target_year_month(activity_month)
    historical_records: list[dict[str, Any]] = []
    existing_target_records = 0
    insertion_index: int | None = None
    for record in existing_records:
        is_target = (
            record.get("year") == year
            and record.get("monthNum") == month_number
        )
        if is_target:
            existing_target_records += 1
            if insertion_index is None:
                insertion_index = len(historical_records)
        else:
            historical_records.append(record)
    if insertion_index is None:
        insertion_index = len(historical_records)
    merged = historical_records.copy()
    merged[insertion_index:insertion_index] = list(generated_records)
    if len(merged) != (
        len(existing_records) - existing_target_records + len(generated_records)
    ):
        raise ValidationError(f"{output_filename} cumulative row-count check failed")
    return merged, existing_target_records, len(historical_records)


def add_calendar_months(value: date, months: int) -> date:
    """Add whole calendar months while keeping month-end dates valid."""
    absolute_month = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(absolute_month, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def retention_cohort_fully_eligible(
    cohort_year: int,
    milestone_months: int,
    report_date: date,
) -> bool:
    """A cohort is publishable only after its final creation date matures."""
    return report_date > add_calendar_months(
        date(cohort_year, 12, 31), milestone_months
    )


def display_integer(value: int) -> str:
    return f"{value:,}"


def display_percent(value: float) -> str:
    return f"{value:.1%}"


def display_compact_thousands(value: int) -> str:
    return f"{math.floor(value / 1000 + 0.5):,}K"


def retention_delta_display(
    current_rate: float | None,
    prior_rate: float | None,
) -> tuple[str, str]:
    if current_rate is None or prior_rate is None:
        return "TBD", "neutral"
    points = (current_rate - prior_rate) * 100
    if math.isclose(points, 0.0, abs_tol=0.05):
        return "0.0 pts", "neutral"
    return (
        f"{points:+.1f} pts",
        "positive" if points > 0 else "negative",
    )


def coordinate_display(value: float) -> str:
    rounded = round(value, 1)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:.1f}"


def retention_survival_curve(
    milestone_rates: Sequence[float | None],
) -> dict[str, Any]:
    """Create the existing dashboard's SVG coordinates from survival rates."""
    x_positions = (70.0, 366.7, 663.3, 960.0)
    available_rates: list[tuple[int, float]] = [(0, 1.0)]
    for index, rate in enumerate(milestone_rates, start=1):
        if rate is None:
            break
        available_rates.append((index, rate))
    y_scale = (260.0 - 30.0) / (1.0 - 0.25)
    dots: list[dict[str, str]] = []
    value_labels: list[dict[str, Any]] = []
    point_values: list[str] = []
    for milestone_index, rate in available_rates:
        x = x_positions[milestone_index]
        y = 30.0 + (1.0 - rate) * y_scale
        x_display = coordinate_display(x)
        y_display = coordinate_display(y)
        point_values.append(f"{x_display},{y_display}")
        dots.append({"cx": x_display, "cy": y_display})
        if milestone_index:
            value_labels.append(
                {
                    "x": x_display,
                    "y": coordinate_display(y - 14.0),
                    "milestoneIndex": milestone_index,
                }
            )
    return {
        "points": " ".join(point_values),
        "dots": dots,
        "valueLabels": value_labels,
    }


def eligible_cohort_display(years: Sequence[int]) -> str:
    if not years:
        return "No eligible cohorts"
    if len(years) == 1:
        return f"{years[0]} eligible cohort"
    return f"{min(years)}–{max(years)} eligible cohorts"


def generate_retention_outputs(
    report_month: str,
    current_detail: CsvSnapshot,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    """Generate retention cohort and club-ranking JSON-compatible values."""
    require_headers(
        current_detail,
        {
            "club_name",
            "golfer_status",
            "membership_creation_date",
            "golfer_status_date",
        },
    )
    report_year, report_month_number = target_year_month(report_month)
    report_date = date(report_year, report_month_number, 1)
    report_date_label = display_report_date(report_month)
    display_years = tuple(range(report_year, report_year - 5, -1))

    status_counts: Counter[str] = Counter()
    created_by_year: Counter[int] = Counter()
    active_by_year: Counter[int] = Counter()
    milestone_survivors: Counter[tuple[int, int]] = Counter()
    club_created: Counter[tuple[str, int]] = Counter()
    club_active: Counter[tuple[str, int]] = Counter()
    missing_creation_dates = 0
    missing_inactive_status_dates = 0
    invalid_status_dates: Counter[str] = Counter()

    for row_number, row in enumerate(current_detail.rows, start=2):
        status = normalize_segmentation_status(
            row["golfer_status"],
            f"{current_detail.label} golfer_status at CSV row {row_number}",
        )
        status_counts[status] += 1
        creation_date = parse_source_date(
            row["membership_creation_date"],
            f"{current_detail.label} membership_creation_date at CSV row {row_number}",
        )
        status_date = parse_source_date(
            row["golfer_status_date"],
            f"{current_detail.label} golfer_status_date at CSV row {row_number}",
        )
        if creation_date is None:
            missing_creation_dates += 1
            continue
        if status != "Active" and status_date is None:
            missing_inactive_status_dates += 1
        invalid_timeline = (
            status_date is not None and status_date < creation_date
        )
        if invalid_timeline:
            invalid_status_dates[status] += 1

        cohort_year = creation_date.year
        created_by_year[cohort_year] += 1
        if status == "Active":
            active_by_year[cohort_year] += 1

        if cohort_year not in RETENTION_COHORT_YEARS:
            continue
        club_name = row["club_name"].strip()
        if not club_name:
            raise ValidationError(
                f"{current_detail.label} has a blank club_name at CSV row {row_number}"
            )
        club_created[(club_name, cohort_year)] += 1
        if status == "Active":
            club_active[(club_name, cohort_year)] += 1

        if invalid_timeline:
            continue
        for milestone_months in RETENTION_MILESTONE_MONTHS:
            milestone_date = add_calendar_months(
                creation_date, milestone_months
            )
            if report_date <= milestone_date:
                continue
            survived = status == "Active" or (
                status != "Active"
                and status_date is not None
                and status_date > milestone_date
            )
            if survived:
                milestone_survivors[(cohort_year, milestone_months)] += 1

    milestone_counts: dict[tuple[int, int], int | None] = {}
    milestone_rates: dict[tuple[int, int], float | None] = {}
    for cohort_year in RETENTION_COHORT_YEARS:
        created = created_by_year[cohort_year]
        for milestone_months in RETENTION_MILESTONE_MONTHS:
            eligible = retention_cohort_fully_eligible(
                cohort_year, milestone_months, report_date
            )
            count = (
                milestone_survivors[(cohort_year, milestone_months)]
                if eligible
                else None
            )
            milestone_counts[(cohort_year, milestone_months)] = count
            milestone_rates[(cohort_year, milestone_months)] = (
                count / created
                if count is not None and created
                else None
            )

    analyzed = sum(created_by_year[year] for year in display_years)
    active_today = sum(active_by_year[year] for year in display_years)
    inactive_today = analyzed - active_today
    summary: list[dict[str, str]] = [
        {
            "label": "Golfers Analyzed",
            "valueDisplay": display_integer(analyzed),
            "subDisplay": report_date_label,
        },
        {
            "label": "Active Today",
            "valueDisplay": display_integer(active_today),
            "subDisplay": report_date_label,
        },
        {
            "label": "Inactive Today",
            "valueDisplay": display_integer(inactive_today),
            "subDisplay": report_date_label,
        },
    ]
    for milestone_months in RETENTION_MILESTONE_MONTHS:
        eligible_years = [
            year
            for year in RETENTION_COHORT_YEARS
            if milestone_counts[(year, milestone_months)] is not None
        ]
        numerator = sum(
            int(milestone_counts[(year, milestone_months)] or 0)
            for year in eligible_years
        )
        denominator = sum(created_by_year[year] for year in eligible_years)
        rate = numerator / denominator if denominator else None
        summary.append(
            {
                "label": f"Active Beyond {milestone_months} Months",
                "valueDisplay": display_percent(rate) if rate is not None else "TBD",
                "subDisplay": eligible_cohort_display(eligible_years),
            }
        )

    creation_year_status: list[dict[str, str]] = []
    for cohort_year in display_years:
        created = created_by_year[cohort_year]
        active = active_by_year[cohort_year]
        active_rate = active / created if created else 0.0
        creation_year_status.append(
            {
                "yearDisplay": str(cohort_year),
                "activeDisplay": display_percent(active_rate),
                "inactiveDisplay": display_percent(1.0 - active_rate),
                "totalDisplay": display_compact_thousands(created),
            }
        )

    cohorts: list[dict[str, Any]] = []
    for cohort_year in RETENTION_COHORT_YEARS:
        created = created_by_year[cohort_year]
        active = active_by_year[cohort_year]
        milestones: list[dict[str, str]] = [
            {
                "label": "Created",
                "golfersDisplay": display_integer(created),
                "percentDisplay": "100.0%",
                "deltaDisplay": "—",
                "deltaClass": "neutral",
            }
        ]
        curve_rates: list[float | None] = []
        for milestone_months in RETENTION_MILESTONE_MONTHS:
            count = milestone_counts[(cohort_year, milestone_months)]
            rate = milestone_rates[(cohort_year, milestone_months)]
            curve_rates.append(rate)
            if count is None or rate is None:
                delta_display, delta_class = "TBD", "neutral"
                golfers_display = percent_display = "TBD"
            else:
                golfers_display = display_integer(count)
                percent_display = display_percent(rate)
                if cohort_year == RETENTION_COHORT_YEARS[0]:
                    delta_display, delta_class = "—", "neutral"
                else:
                    delta_display, delta_class = retention_delta_display(
                        rate,
                        milestone_rates[
                            (cohort_year - 1, milestone_months)
                        ],
                    )
            milestones.append(
                {
                    "label": f"Active Beyond {milestone_months} Months",
                    "golfersDisplay": golfers_display,
                    "percentDisplay": percent_display,
                    "deltaDisplay": delta_display,
                    "deltaClass": delta_class,
                }
            )
        cohorts.append(
            {
                "yearDisplay": str(cohort_year),
                "createdDisplay": display_integer(created),
                "activeTodayDisplay": display_integer(active),
                "activeRateDisplay": display_percent(
                    active / created if created else 0.0
                ),
                "comparisonHeader": (
                    "vs Prior"
                    if cohort_year == RETENTION_COHORT_YEARS[0]
                    else f"vs {cohort_year - 1}"
                ),
                "color": RETENTION_COHORT_COLORS[cohort_year],
                "milestones": milestones,
                "survivalCurve": retention_survival_curve(curve_rates),
            }
        )

    club_names = sorted(
        {
            club_name
            for club_name, cohort_year in club_created
            if cohort_year in RETENTION_COHORT_YEARS
        }
    )
    ranking_values: list[dict[str, Any]] = []
    for club_name in club_names:
        rates = {
            year: (
                club_active[(club_name, year)]
                / club_created[(club_name, year)]
                if club_created[(club_name, year)]
                else 0.0
            )
            for year in RETENTION_COHORT_YEARS
        }
        total = sum(
            club_created[(club_name, year)]
            for year in RETENTION_COHORT_YEARS
        )
        ranking_values.append(
            {"club": club_name, "total": total, "rates": rates}
        )
    ranking_values.sort(
        key=lambda item: (-item["rates"][2022], item["club"])
    )
    rankings: list[dict[str, str]] = []
    for rank, item in enumerate(ranking_values, start=1):
        rankings.append(
            {
                "club": item["club"],
                "total": str(item["total"]),
                "ret2022": str(item["rates"][2022]),
                "ret2023": str(item["rates"][2023]),
                "ret2024": str(item["rates"][2024]),
                "rankDisplay": str(rank),
                "clubDisplay": item["club"],
                "totalDisplay": display_integer(item["total"]),
                "ret2022Display": display_percent(item["rates"][2022]),
                "ret2023Display": display_percent(item["rates"][2023]),
                "ret2024Display": display_percent(item["rates"][2024]),
            }
        )

    retention_cohorts = {
        "summary": summary,
        "creationYearStatus": creation_year_status,
        "cohorts": cohorts,
    }
    validate_retention_outputs(
        retention_cohorts,
        rankings,
        created_by_year,
        active_by_year,
        milestone_counts,
    )
    stats: dict[str, Any] = {
        "statusCounts": dict(status_counts),
        "missingCreationDates": missing_creation_dates,
        "missingInactiveStatusDates": missing_inactive_status_dates,
        "invalidStatusDates": dict(invalid_status_dates),
        "cohortCreated": {
            year: created_by_year[year] for year in RETENTION_COHORT_YEARS
        },
        "cohortActiveToday": {
            year: active_by_year[year] for year in RETENTION_COHORT_YEARS
        },
        "cohortMilestones": milestone_counts,
    }
    return retention_cohorts, rankings, stats


def validate_retention_outputs(
    retention_cohorts: dict[str, Any],
    rankings: Sequence[dict[str, str]],
    created_by_year: Counter[int],
    active_by_year: Counter[int],
    milestone_counts: dict[tuple[int, int], int | None],
) -> None:
    if len(retention_cohorts.get("summary", [])) != 6:
        raise ValidationError("retention_cohorts.json must contain 6 summary records")
    if len(retention_cohorts.get("creationYearStatus", [])) != 5:
        raise ValidationError(
            "retention_cohorts.json must contain 5 creation-year status records"
        )
    cohorts = retention_cohorts.get("cohorts", [])
    if len(cohorts) != len(RETENTION_COHORT_YEARS):
        raise ValidationError("retention_cohorts.json must contain 3 cohorts")
    for cohort_year in RETENTION_COHORT_YEARS:
        created = created_by_year[cohort_year]
        if created <= 0:
            raise ValidationError(f"retention cohort {cohort_year} is empty")
        if active_by_year[cohort_year] > created:
            raise ValidationError(
                f"retention cohort {cohort_year} Active Today exceeds Created"
            )
        available_counts = [
            milestone_counts[(cohort_year, months)]
            for months in RETENTION_MILESTONE_MONTHS
            if milestone_counts[(cohort_year, months)] is not None
        ]
        if any(count > created for count in available_counts):
            raise ValidationError(
                f"retention cohort {cohort_year} milestone exceeds Created"
            )
        if any(
            later > earlier
            for earlier, later in zip(available_counts, available_counts[1:])
        ):
            raise ValidationError(
                f"retention cohort {cohort_year} survival is not nonincreasing"
            )
    if len(rankings) != 57:
        raise ValidationError(
            f"retention_club_rankings.json generated {len(rankings)} clubs; expected 57"
        )
    if len({record["club"] for record in rankings}) != len(rankings):
        raise ValidationError("retention club rankings contain duplicate clubs")
    ranking_total = sum(int(record["total"]) for record in rankings)
    cohort_total = sum(created_by_year[year] for year in RETENTION_COHORT_YEARS)
    if ranking_total != cohort_total:
        raise ValidationError(
            "retention club ranking totals do not equal cohort Created totals"
        )


def parse_display_integer(value: Any) -> int | None:
    if not isinstance(value, str) or value == "TBD":
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def retention_baseline_values(
    retention_cohorts: Any,
) -> tuple[
    dict[int, int],
    dict[int, int],
    dict[tuple[int, int], int | None],
]:
    if not isinstance(retention_cohorts, dict):
        raise ValidationError("retention_cohorts.json must contain an object")
    created: dict[int, int] = {}
    active: dict[int, int] = {}
    milestones: dict[tuple[int, int], int | None] = {}
    for cohort in retention_cohorts.get("cohorts", []):
        year = int(cohort["yearDisplay"])
        created_value = parse_display_integer(cohort.get("createdDisplay"))
        active_value = parse_display_integer(cohort.get("activeTodayDisplay"))
        if created_value is None or active_value is None:
            raise ValidationError(
                f"retention_cohorts.json has invalid cohort counts for {year}"
            )
        created[year] = created_value
        active[year] = active_value
        for milestone in cohort.get("milestones", []):
            match = re.fullmatch(
                r"Active Beyond (13|25|37) Months",
                str(milestone.get("label", "")),
            )
            if match:
                milestones[(year, int(match.group(1)))] = parse_display_integer(
                    milestone.get("golfersDisplay")
                )
    return created, active, milestones


def build_retention_diagnostics(
    source_rows: int,
    stats: dict[str, Any],
    generated_rankings: Sequence[dict[str, str]],
    existing_cohorts: Any,
    existing_rankings: Any,
) -> RetentionDiagnostics:
    baseline_created, baseline_active, baseline_milestones = (
        retention_baseline_values(existing_cohorts)
    )
    if not isinstance(existing_rankings, list):
        raise ValidationError("retention_club_rankings.json must contain an array")
    baseline_by_club = {
        str(record.get("club")): record
        for record in existing_rankings
        if isinstance(record, dict)
    }
    generated_by_club = {record["club"]: record for record in generated_rankings}
    if set(baseline_by_club) != set(generated_by_club):
        raise ValidationError(
            "generated retention club set differs from retention_club_rankings.json"
        )
    total_differences = [
        abs(
            int(generated_by_club[club]["total"])
            - int(baseline_by_club[club]["total"])
        )
        for club in generated_by_club
    ]
    rank_shifts = [
        abs(
            int(generated_by_club[club]["rankDisplay"])
            - int(baseline_by_club[club]["rankDisplay"])
        )
        for club in generated_by_club
    ]
    return RetentionDiagnostics(
        source_rows=source_rows,
        status_counts=dict(stats["statusCounts"]),
        missing_creation_dates=int(stats["missingCreationDates"]),
        missing_inactive_status_dates=int(
            stats["missingInactiveStatusDates"]
        ),
        invalid_status_dates_by_status=dict(stats["invalidStatusDates"]),
        cohort_created=dict(stats["cohortCreated"]),
        cohort_active_today=dict(stats["cohortActiveToday"]),
        cohort_milestones=dict(stats["cohortMilestones"]),
        baseline_created=baseline_created,
        baseline_active_today=baseline_active,
        baseline_milestones=baseline_milestones,
        club_count=len(generated_rankings),
        club_created_total=sum(
            int(record["total"]) for record in generated_rankings
        ),
        baseline_club_created_total=sum(
            int(record["total"]) for record in existing_rankings
        ),
        exact_club_total_matches=sum(diff == 0 for diff in total_differences),
        maximum_club_total_difference=max(total_differences, default=0),
        identical_rank_positions=sum(shift == 0 for shift in rank_shifts),
        maximum_rank_shift=max(rank_shifts, default=0),
    )


def whole_calendar_months(start: date, end: date) -> int:
    """Return elapsed whole calendar months between two ordered dates."""
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(0, months)


def recovery_age_bucket(age_months: int) -> str:
    for label, minimum, maximum in RECOVERY_AGE_BUCKETS:
        if age_months >= minimum and (
            maximum is None or age_months <= maximum
        ):
            return label
    raise ValidationError(f"unable to bucket recovery age {age_months}")


def generate_recovery_analysis(
    report_month: str,
    current_detail: CsvSnapshot,
) -> tuple[dict[str, Any], RecoveryDiagnostics]:
    """Generate membership-level YTD Recovery Analysis from Golfer Detail."""
    require_headers(
        current_detail,
        {
            "ghin_number",
            "club_number",
            "club_name",
            "golfer_status",
            "membership_creation_date",
            "golfer_status_date",
        },
    )
    report_year, report_month_number = target_year_month(report_month)
    report_date = date(report_year, report_month_number, 1)
    period_end = report_date - timedelta(days=1)
    period_start = date(period_end.year, 1, 1)
    latest_month = period_end.month

    active_rows = 0
    active_by_club: Counter[tuple[str, str]] = Counter()
    recoveries_by_month: Counter[int] = Counter()
    recovery_ghins_by_month: defaultdict[int, set[str]] = defaultdict(set)
    recoveries_by_club: Counter[tuple[str, str]] = Counter()
    latest_recoveries_by_club: Counter[tuple[str, str]] = Counter()
    recovery_ages_by_club: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    recoveries_by_creation_year: Counter[int] = Counter()
    active_by_creation_year: Counter[int] = Counter()
    recovery_ages_by_creation_year: defaultdict[int, list[int]] = defaultdict(list)
    recoveries_by_age: Counter[str] = Counter()
    all_recovery_ages: list[int] = []
    distinct_recovery_ghins: set[str] = set()
    missing_creation_dates = 0
    missing_status_dates = 0
    creation_not_before_status_rows = 0

    for row_number, row in enumerate(current_detail.rows, start=2):
        status = normalize_segmentation_status(
            row["golfer_status"],
            f"{current_detail.label} golfer_status at CSV row {row_number}",
        )
        if status != "Active":
            continue
        active_rows += 1
        club_number = row["club_number"].strip()
        club_name = row["club_name"].strip()
        if not club_number or not club_name:
            raise ValidationError(
                f"{current_detail.label} has a blank club identifier at CSV row {row_number}"
            )
        active_by_club[(club_number, club_name)] += 1

        creation_date = parse_source_date(
            row["membership_creation_date"],
            f"{current_detail.label} membership_creation_date at CSV row {row_number}",
        )
        status_date = parse_source_date(
            row["golfer_status_date"],
            f"{current_detail.label} golfer_status_date at CSV row {row_number}",
        )
        if creation_date is None:
            missing_creation_dates += 1
            continue
        active_by_creation_year[creation_date.year] += 1
        if status_date is None:
            missing_status_dates += 1
            continue
        if creation_date >= status_date:
            creation_not_before_status_rows += 1
            continue
        if not period_start <= status_date <= period_end:
            continue

        golfer_id = row["ghin_number"].strip()
        if not golfer_id:
            raise ValidationError(
                f"{current_detail.label} has a blank GHIN Number at CSV row {row_number}"
            )
        age_months = whole_calendar_months(creation_date, status_date)
        age_bucket = recovery_age_bucket(age_months)
        club_key = (club_number, club_name)
        recoveries_by_month[status_date.month] += 1
        recovery_ghins_by_month[status_date.month].add(golfer_id)
        recoveries_by_club[club_key] += 1
        if status_date.month == latest_month:
            latest_recoveries_by_club[club_key] += 1
        recovery_ages_by_club[club_key].append(age_months)
        recoveries_by_creation_year[creation_date.year] += 1
        recovery_ages_by_creation_year[creation_date.year].append(age_months)
        recoveries_by_age[age_bucket] += 1
        all_recovery_ages.append(age_months)
        distinct_recovery_ghins.add(golfer_id)

    recoveries_ytd = sum(recoveries_by_month.values())
    latest_month_recoveries = recoveries_by_month[latest_month]
    recovery_rate = recoveries_ytd / active_rows if active_rows else None
    clubs_with_recoveries = sum(
        count > 0 for count in recoveries_by_club.values()
    )
    median_age = (
        statistics.median(all_recovery_ages) if all_recovery_ages else None
    )

    monthly_trend: list[dict[str, Any]] = []
    cumulative = 0
    for month_number in range(1, latest_month + 1):
        recoveries = recoveries_by_month[month_number]
        cumulative += recoveries
        monthly_trend.append(
            {
                "year": period_end.year,
                "month": datetime(period_end.year, month_number, 1).strftime("%B"),
                "monthNum": month_number,
                "label": datetime(period_end.year, month_number, 1).strftime("%B %Y"),
                "recoveries": recoveries,
                "cumulativeRecoveries": cumulative,
                "distinctGHINs": len(recovery_ghins_by_month[month_number]),
                "recoveriesAsPctOfActiveBase": (
                    recoveries / active_rows if active_rows else None
                ),
            }
        )

    by_club: list[dict[str, Any]] = []
    for club_key in sorted(active_by_club, key=lambda value: value[1]):
        club_number, club_name = club_key
        recoveries = recoveries_by_club[club_key]
        active_base = active_by_club[club_key]
        ages = recovery_ages_by_club[club_key]
        by_club.append(
            {
                "clubNumber": club_number,
                "clubName": club_name,
                "recoveriesYTD": recoveries,
                "latestMonthRecoveries": latest_recoveries_by_club[club_key],
                "activeMemberships": active_base,
                "shareOfYTDRecoveries": (
                    recoveries / recoveries_ytd if recoveries_ytd else 0.0
                ),
                "recoveriesAsPctOfActiveBase": (
                    recoveries / active_base if active_base else None
                ),
                "medianMembershipAgeMonths": (
                    statistics.median(ages) if ages else None
                ),
            }
        )

    by_creation_year: list[dict[str, Any]] = []
    for creation_year in sorted(recoveries_by_creation_year):
        recoveries = recoveries_by_creation_year[creation_year]
        active_base = active_by_creation_year[creation_year]
        ages = recovery_ages_by_creation_year[creation_year]
        by_creation_year.append(
            {
                "creationYear": creation_year,
                "recoveriesYTD": recoveries,
                "shareOfYTDRecoveries": (
                    recoveries / recoveries_ytd if recoveries_ytd else 0.0
                ),
                "activeMemberships": active_base,
                "recoveriesAsPctOfActiveBase": (
                    recoveries / active_base if active_base else None
                ),
                "medianMembershipAgeMonths": statistics.median(ages),
            }
        )

    by_membership_age: list[dict[str, Any]] = []
    for label, minimum, maximum in RECOVERY_AGE_BUCKETS:
        recoveries = recoveries_by_age[label]
        by_membership_age.append(
            {
                "segment": label,
                "minimumMonths": minimum,
                "maximumMonths": maximum,
                "recoveriesYTD": recoveries,
                "shareOfYTDRecoveries": (
                    recoveries / recoveries_ytd if recoveries_ytd else 0.0
                ),
            }
        )

    ranking_source = sorted(
        by_club,
        key=lambda record: (
            -record["recoveriesYTD"],
            -float(record["recoveriesAsPctOfActiveBase"] or 0.0),
            record["clubName"],
        ),
    )
    rankings = [
        {
            "rank": index,
            **record,
            "priorYearRecoveriesYTD": None,
            "yoyChange": None,
        }
        for index, record in enumerate(ranking_source, start=1)
    ]

    club_reconciles = sum(
        record["recoveriesYTD"] for record in by_club
    ) == recoveries_ytd
    creation_year_reconciles = sum(
        record["recoveriesYTD"] for record in by_creation_year
    ) == recoveries_ytd
    age_reconciles = sum(
        record["recoveriesYTD"] for record in by_membership_age
    ) == recoveries_ytd
    qa = {
        "sourceRows": len(current_detail.rows),
        "activeRows": active_rows,
        "qualifyingRecoveryRows": recoveries_ytd,
        "distinctRecoveryGHINs": len(distinct_recovery_ghins),
        "missingCreationDateRows": missing_creation_dates,
        "missingStatusDateRows": missing_status_dates,
        "creationNotBeforeStatusDateRows": creation_not_before_status_rows,
        "clubBreakdownReconciles": club_reconciles,
        "creationYearBreakdownReconciles": creation_year_reconciles,
        "membershipAgeBreakdownReconciles": age_reconciles,
    }
    output = {
        "metadata": {
            "schemaVersion": 1,
            "definitionVersion": "active-status-date-v1",
            "reportMonth": report_month,
            "reportDate": report_date.isoformat(),
            "activityThrough": period_end.isoformat(),
            "periodStart": period_start.isoformat(),
            "periodEnd": period_end.isoformat(),
            "grain": "membership",
            "source": "Current Month_Golfer Detail.csv",
        },
        "summary": {
            "recoveriesYTD": recoveries_ytd,
            "latestMonthRecoveries": latest_month_recoveries,
            "activeMemberships": active_rows,
            "recoveriesAsPctOfActiveBase": recovery_rate,
            "clubsWithRecoveries": clubs_with_recoveries,
            "medianMembershipAgeMonths": median_age,
            "priorYearRecoveriesYTD": None,
            "yoyChange": None,
        },
        "monthlyTrend": monthly_trend,
        "byClub": by_club,
        "byCreationYear": by_creation_year,
        "byMembershipAge": by_membership_age,
        "rankings": rankings,
        "qa": qa,
    }
    validate_recovery_analysis(output)
    diagnostics = RecoveryDiagnostics(
        source_rows=len(current_detail.rows),
        active_rows=active_rows,
        qualifying_recovery_rows=recoveries_ytd,
        distinct_recovery_ghins=len(distinct_recovery_ghins),
        latest_month_recoveries=latest_month_recoveries,
        clubs_with_recoveries=clubs_with_recoveries,
        missing_creation_dates=missing_creation_dates,
        missing_status_dates=missing_status_dates,
        creation_not_before_status_rows=creation_not_before_status_rows,
        club_breakdown_reconciles=club_reconciles,
        creation_year_breakdown_reconciles=creation_year_reconciles,
        membership_age_breakdown_reconciles=age_reconciles,
    )
    return output, diagnostics


def validate_recovery_analysis(output: dict[str, Any]) -> None:
    required = {
        "metadata",
        "summary",
        "monthlyTrend",
        "byClub",
        "byCreationYear",
        "byMembershipAge",
        "rankings",
        "qa",
    }
    if set(output) != required:
        raise ValidationError("recovery_analysis.json has an invalid top-level schema")
    if len(output["byClub"]) != 57 or len(output["rankings"]) != 57:
        raise ValidationError(
            "recovery_analysis.json must contain 57 club and ranking records"
        )
    if len(output["byMembershipAge"]) != len(RECOVERY_AGE_BUCKETS):
        raise ValidationError("recovery membership-age buckets are incomplete")
    if not all(
        output["qa"][field]
        for field in (
            "clubBreakdownReconciles",
            "creationYearBreakdownReconciles",
            "membershipAgeBreakdownReconciles",
        )
    ):
        raise ValidationError("recovery breakdowns do not reconcile to YTD total")


def write_recovery_analysis(
    data_directory: Path,
    backup_directory: Path,
    output: dict[str, Any],
) -> Path:
    """Write the validated Recovery Analysis output with backup-on-replace."""
    output_path = data_directory / "recovery_analysis.json"
    if output_path.exists():
        backup_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, backup_directory / output_path.name)
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def parse_tableau_int(value: str, context: str) -> int:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        raise ValidationError(f"{context} is blank")
    try:
        return int(float(cleaned))
    except ValueError as exc:
        raise ValidationError(f"{context} is not a valid integer: {value!r}") from exc


def parse_tableau_percent(value: str, context: str) -> float:
    cleaned = value.strip().replace("%", "")
    if not cleaned:
        raise ValidationError(f"{context} is blank")
    try:
        return float(cleaned) / 100
    except ValueError as exc:
        raise ValidationError(f"{context} is not a valid percent: {value!r}") from exc


def parse_tableau_date(value: str, context: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%B %d, %Y").date()
    except ValueError as exc:
        raise ValidationError(f"{context} is not a valid Tableau date: {value!r}") from exc


def discover_ghin_tableau_inputs(raw_directory: Path) -> dict[str, Path]:
    """Locate the five Tableau aggregate exports for GHIN Trials."""
    paths = {
        label: raw_directory / filename
        for label, filename in GHIN_TABLEAU_FILENAMES.items()
    }
    missing = [path.name for path in paths.values() if not path.is_file()]
    if missing:
        raise ValidationError(
            "missing GHIN Trials Tableau exports: " + ", ".join(sorted(missing))
        )
    return paths


def parse_ghin_yearly_statistics(path: Path, report_year: int) -> tuple[dict[str, Any], dict[str, int]]:
    rows = read_tableau_rows(path)
    if len(rows) < 6:
        raise ValidationError("Yearly Statistics.csv must contain a header and 5 metric rows")
    header = rows[0]
    try:
        year_index = header.index(str(report_year))
    except ValueError as exc:
        raise ValidationError(
            f"Yearly Statistics.csv is missing report-year column {report_year}"
        ) from exc

    required_metrics = {
        "(1) Total Trials Created": "totalTrialsCreated",
        "(2) Trial Conversions": "trialConversions",
        "(3) Conversion Rate": "conversionRate",
        "(4) Active Trial Golfers": "activeTrialGolfers",
        "(5) Inactive Trial Golfers": "inactiveTrialGolfers",
    }
    found: dict[str, Any] = {}
    for row in rows[1:]:
        if not row:
            continue
        label = row[0].strip()
        key = required_metrics.get(label)
        if not key:
            continue
        if len(row) <= year_index:
            raise ValidationError(f"Yearly Statistics.csv row {label!r} is missing {report_year} value")
        context = f"Yearly Statistics.csv {label} {report_year}"
        found[key] = (
            parse_tableau_percent(row[year_index], context)
            if key == "conversionRate"
            else parse_tableau_int(row[year_index], context)
        )
    missing = sorted(set(required_metrics.values()) - set(found))
    if missing:
        raise ValidationError("Yearly Statistics.csv missing metrics: " + ", ".join(missing))
    expected_rate = (
        found["trialConversions"] / found["totalTrialsCreated"]
        if found["totalTrialsCreated"]
        else None
    )
    if expected_rate is not None and not math.isclose(
        found["conversionRate"], expected_rate, rel_tol=0.0, abs_tol=0.0001
    ):
        raise ValidationError(
            "Yearly Statistics.csv conversion rate does not match conversions / trials"
        )
    return found, {"rows": len(rows) - 1}


def parse_ghin_daily_crosstab(path: Path, label: str) -> tuple[dict[date, int], tuple[str | None, str | None], int]:
    rows = read_tableau_rows(path)
    if len(rows) < 3:
        raise ValidationError(f"{path.name} must contain Tableau date headers and count rows")
    date_row = rows[1]
    value_rows = [row for row in rows[2:] if row and row[0].strip().lower() == "trial golfer count"]
    if not value_rows:
        value_rows = [row for row in rows[2:] if row and row[0].strip().lower() == "count of trial_golfers"]
    if not value_rows:
        raise ValidationError(f"{path.name} is missing Trial Golfer Count row")
    value_row = value_rows[0]
    values: dict[date, int] = {}
    for index in range(1, min(len(date_row), len(value_row))):
        date_label = date_row[index].strip()
        count_label = value_row[index].strip()
        if not date_label:
            continue
        parsed_date = parse_tableau_date(
            date_label, f"{path.name} date header column {index + 1}"
        )
        values[parsed_date] = parse_tableau_int(
            count_label or "0", f"{path.name} {label} for {date_label}"
        )
    if not values:
        raise ValidationError(f"{path.name} contains no dated daily values")
    dates = sorted(values)
    return (
        values,
        (dates[0].isoformat(), dates[-1].isoformat()),
        len(dates),
    )


def month_abbreviation(month_number: int) -> str:
    return calendar.month_abbr[month_number]


def monthly_ghin_records(
    report_month: str,
    created_by_day: dict[date, int],
    conversions_by_day: dict[date, int],
) -> list[dict[str, Any]]:
    activity_month = activity_month_for_report(report_month)
    year, through_month = target_year_month(activity_month)
    records: list[dict[str, Any]] = []
    for month_number in range(1, through_month + 1):
        trials = sum(
            value
            for day, value in created_by_day.items()
            if day.year == year and day.month == month_number
        )
        conversions = sum(
            value
            for day, value in conversions_by_day.items()
            if day.year == year and day.month == month_number
        )
        records.append(
            {
                "label": month_abbreviation(month_number),
                "trials": trials,
                "conversions": conversions,
            }
        )
    return records


GHIN_CONVERSION_BUCKET_LABELS = {
    "0 (first day)": "First day",
    "1 (next day)": "Next day",
    "2-7 (first week)": "First week",
    "7-30 (first month)": "First month",
    "30+ (beyond 1 month)": "Beyond 1 month",
}


def parse_ghin_conversion_buckets(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows = read_tableau_rows(path)
    if not rows or len(rows[0]) < 2 or rows[0][0] != "Group" or rows[0][1] != "Count":
        raise ValidationError("Conversions by Days in Trial.csv must have Group and Count columns")
    records: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) < 2 or not row[0].strip():
            continue
        label = GHIN_CONVERSION_BUCKET_LABELS.get(row[0].strip())
        if not label:
            raise ValidationError(
                f"Conversions by Days in Trial.csv row {row_number} has unknown bucket {row[0]!r}"
            )
        count = parse_tableau_int(row[1], f"Conversions by Days in Trial.csv row {row_number} count")
        pct_value = (
            parse_tableau_percent(row[2], f"Conversions by Days in Trial.csv row {row_number} percent")
            if len(row) > 2 and row[2].strip()
            else None
        )
        records.append({"label": label, "count": count, "pct": pct_value})
    if len(records) != len(GHIN_CONVERSION_BUCKET_LABELS):
        raise ValidationError(
            f"Conversions by Days in Trial.csv generated {len(records)} buckets; expected {len(GHIN_CONVERSION_BUCKET_LABELS)}"
        )
    total = sum(record["count"] for record in records)
    for record in records:
        calculated = record["count"] / total if total else None
        if record["pct"] is None:
            record["pct"] = calculated
        elif calculated is not None and not math.isclose(
            record["pct"], calculated, rel_tol=0.0, abs_tol=0.0001
        ):
            raise ValidationError(
                f"Conversions by Days in Trial.csv percent mismatch for {record['label']}"
            )
    return records, len(rows) - 1


def parse_ghin_aga_conversions(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows = read_tableau_rows(path)
    if not rows or len(rows[0]) < 2 or rows[0][1] != "Count":
        raise ValidationError("AGA Conversions.csv must have association and Count columns")
    records: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) < 2 or not row[0].strip():
            continue
        records.append(
            {
                "name": row[0].strip(),
                "count": parse_tableau_int(
                    row[1], f"AGA Conversions.csv row {row_number} count"
                ),
            }
        )
    if not records:
        raise ValidationError("AGA Conversions.csv contains no association rows")
    records.sort(key=lambda record: (-record["count"], record["name"]))
    return records, len(rows) - 1


def ghin_parity_differences(generated: dict[str, Any], existing: Any) -> list[str]:
    if not isinstance(existing, dict):
        return ["existing ghin_trials.json is not an object; parity skipped"]
    differences: list[str] = []
    comparisons = [
        ("summary.totalTrialsCreated", generated["summary"].get("totalTrialsCreated"), existing.get("summary", {}).get("totalTrialsCreated")),
        ("summary.trialConversions", generated["summary"].get("trialConversions"), existing.get("summary", {}).get("trialConversions")),
        ("summary.conversionRate", generated["summary"].get("conversionRate"), existing.get("summary", {}).get("conversionRate")),
        ("summary.activeTrialGolfers", generated["summary"].get("activeTrialGolfers"), existing.get("summary", {}).get("activeTrialGolfers")),
        ("summary.inactiveTrialGolfers", generated["summary"].get("inactiveTrialGolfers"), existing.get("summary", {}).get("inactiveTrialGolfers")),
        ("monthly record count", len(generated.get("monthly", [])), len(existing.get("monthly", []))),
        ("monthly trials total", sum(r.get("trials", 0) for r in generated.get("monthly", [])), sum(r.get("trials", 0) for r in existing.get("monthly", []))),
        ("monthly conversions total", sum(r.get("conversions", 0) for r in generated.get("monthly", [])), sum(r.get("conversions", 0) for r in existing.get("monthly", []))),
        ("conversionBuckets total", sum(r.get("count", 0) for r in generated.get("conversionBuckets", [])), sum(r.get("count", 0) for r in existing.get("conversionBuckets", []))),
        ("agaConversions record count", len(generated.get("agaConversions", [])), len(existing.get("agaConversions", []))),
        ("agaConversions total", sum(r.get("count", 0) for r in generated.get("agaConversions", [])), sum(r.get("count", 0) for r in existing.get("agaConversions", []))),
    ]
    for label, calculated, current in comparisons:
        if isinstance(calculated, float) or isinstance(current, float):
            same = (
                isinstance(calculated, (int, float))
                and isinstance(current, (int, float))
                and math.isclose(float(calculated), float(current), rel_tol=0.0, abs_tol=1e-12)
            )
        else:
            same = calculated == current
        if not same:
            differences.append(f"{label}: generated={calculated!r}, existing={current!r}")
    return differences


def generate_ghin_trials_output(
    report_month: str,
    raw_directory: Path,
    existing_ghin: Any,
) -> tuple[dict[str, Any], GhinTrialsDiagnostics]:
    """Generate ghin_trials.json from five aggregate Tableau CSV exports."""
    report_year, _ = target_year_month(report_month)
    paths = discover_ghin_tableau_inputs(raw_directory)
    source_row_counts: dict[str, int] = {}
    date_coverage: dict[str, tuple[str | None, str | None]] = {}

    summary, yearly_counts = parse_ghin_yearly_statistics(
        paths["yearly statistics"], report_year
    )
    source_row_counts["Yearly Statistics.csv"] = yearly_counts["rows"]
    date_coverage["Yearly Statistics.csv"] = (str(report_year), str(report_year))

    created_by_day, created_coverage, created_rows = parse_ghin_daily_crosstab(
        paths["trials created by day"], "trials"
    )
    source_row_counts["Trials Created by Day.csv"] = created_rows
    date_coverage["Trials Created by Day.csv"] = created_coverage

    conversions_by_day, conversion_coverage, conversion_rows = parse_ghin_daily_crosstab(
        paths["trial conversions by day"], "conversions"
    )
    source_row_counts["Trial Conversions by Day.csv"] = conversion_rows
    date_coverage["Trial Conversions by Day.csv"] = conversion_coverage

    conversion_buckets, bucket_rows = parse_ghin_conversion_buckets(
        paths["conversions by days in trial"]
    )
    source_row_counts["Conversions by Days in Trial.csv"] = bucket_rows
    date_coverage["Conversions by Days in Trial.csv"] = (None, None)

    aga_conversions, aga_rows = parse_ghin_aga_conversions(paths["aga conversions"])
    source_row_counts["AGA Conversions.csv"] = aga_rows
    date_coverage["AGA Conversions.csv"] = (None, None)

    monthly = monthly_ghin_records(report_month, created_by_day, conversions_by_day)
    existing_overview = (
        existing_ghin.get("overview", {}) if isinstance(existing_ghin, dict) else {}
    )
    overview = {
        "signups": summary["totalTrialsCreated"],
        "activeTrials": summary["activeTrialGolfers"],
        "conversions": summary["trialConversions"],
        "conversionRate": summary["conversionRate"],
        "campaigns": existing_overview.get("campaigns", []),
        "funnel": existing_overview.get("funnel", []),
    }
    output = {
        "metadata": {
            "schemaVersion": 1,
            "status": "draft",
            "source": "Tableau aggregate CSV exports",
        },
        "overview": overview,
        "summary": summary,
        "monthly": monthly,
        "conversionBuckets": conversion_buckets,
        "agaConversions": aga_conversions,
    }
    validate_ghin_trials_output(output)
    parity = ghin_parity_differences(output, existing_ghin)
    diagnostics = GhinTrialsDiagnostics(
        source_files={filename: path for filename, path in paths.items()},
        source_row_counts=source_row_counts,
        date_coverage=date_coverage,
        generated_summary=summary,
        monthly_records=len(monthly),
        monthly_trials_total=sum(row["trials"] for row in monthly),
        monthly_conversions_total=sum(row["conversions"] for row in monthly),
        conversion_bucket_records=len(conversion_buckets),
        conversion_bucket_total=sum(row["count"] for row in conversion_buckets),
        aga_records=len(aga_conversions),
        aga_total=sum(row["count"] for row in aga_conversions),
        overview_campaigns_preserved=len(overview["campaigns"]),
        overview_funnel_preserved=len(overview["funnel"]),
        parity_differences=parity,
    )
    return output, diagnostics


def validate_ghin_trials_output(output: dict[str, Any]) -> None:
    required = {"metadata", "overview", "summary", "monthly", "conversionBuckets", "agaConversions"}
    if set(output) != required:
        raise ValidationError("ghin_trials.json has an invalid top-level schema")
    if output["metadata"].get("schemaVersion") != 1:
        raise ValidationError("ghin_trials.json metadata.schemaVersion must be 1")
    summary = output["summary"]
    for key in ("totalTrialsCreated", "trialConversions", "activeTrialGolfers", "inactiveTrialGolfers"):
        if not isinstance(summary.get(key), int):
            raise ValidationError(f"ghin_trials.json summary.{key} must be an integer")
    expected_rate = (
        summary["trialConversions"] / summary["totalTrialsCreated"]
        if summary["totalTrialsCreated"]
        else None
    )
    if expected_rate is None:
        if summary.get("conversionRate") is not None:
            raise ValidationError("ghin_trials.json summary.conversionRate must be null when denominator is zero")
    elif not math.isclose(summary.get("conversionRate"), expected_rate, rel_tol=0.0, abs_tol=0.0001):
        raise ValidationError("ghin_trials.json summary.conversionRate does not match conversions / trials")
    if not isinstance(output["monthly"], list) or not output["monthly"]:
        raise ValidationError("ghin_trials.json monthly must be a non-empty array")
    if len(output["conversionBuckets"]) != len(GHIN_CONVERSION_BUCKET_LABELS):
        raise ValidationError("ghin_trials.json conversionBuckets has an unexpected record count")
    if not output["agaConversions"]:
        raise ValidationError("ghin_trials.json agaConversions must be non-empty")


def write_ghin_trials_json(
    data_directory: Path,
    backup_directory: Path,
    output: dict[str, Any],
) -> Path:
    """Write the validated GHIN Trials output with backup-on-replace."""
    output_path = data_directory / "ghin_trials.json"
    if output_path.exists():
        backup_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, backup_directory / output_path.name)
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def membership_parity_baseline(
    membership_state: Any,
    target_month: str,
) -> tuple[dict[str, Any] | None, str, bool]:
    """Use the target month when populated, otherwise its prior month."""
    target_record = target_membership_record(membership_state, target_month)
    if any(target_record.get(metric) is not None for metric in MEMBERSHIP_PARITY_METRICS):
        return target_record, target_month, False

    previous_year, previous_month = previous_calendar_month(target_month)
    previous_label = f"{previous_year}-{previous_month:02d}"
    previous_matches = [
        row
        for row in membership_state
        if isinstance(row, dict)
        and row.get("year") == previous_year
        and row.get("monthNum") == previous_month
    ]
    if len(previous_matches) == 1 and any(
        previous_matches[0].get(metric) is not None
        for metric in MEMBERSHIP_PARITY_METRICS
    ):
        return previous_matches[0], previous_label, True
    return None, target_month, False


def compare_membership_parity(
    calculated_record: dict[str, Any],
    dashboard_record: dict[str, Any],
) -> list[ParityResult]:
    """Compare generated metrics with the selected dashboard baseline values."""
    results: list[ParityResult] = []
    for metric in MEMBERSHIP_PARITY_METRICS:
        calculated = calculated_record.get(metric)
        dashboard = dashboard_record.get(metric)
        calculated_is_number = isinstance(calculated, (int, float)) and not isinstance(
            calculated, bool
        )
        dashboard_is_number = isinstance(dashboard, (int, float)) and not isinstance(
            dashboard, bool
        )

        if calculated is None and dashboard is None:
            difference: int | float | None = 0
            passed = True
        elif calculated_is_number and dashboard_is_number:
            difference = calculated - dashboard
            if metric in MEMBERSHIP_RATE_METRICS:
                passed = math.isclose(
                    calculated,
                    dashboard,
                    rel_tol=0.0,
                    abs_tol=PARITY_ABSOLUTE_TOLERANCE,
                )
            else:
                passed = calculated == dashboard
        else:
            difference = None
            passed = False

        if metric in METHODOLOGY_CHANGE_METRICS:
            result_label = "METHODOLOGY CHANGE"
        else:
            result_label = "PASS" if passed else "FAIL"

        results.append(
            ParityResult(
                metric=metric,
                calculated_value=calculated,
                dashboard_value=dashboard,
                difference=difference,
                passed=passed,
                result_label=result_label,
            )
        )
    return results


def calculate_renewal_metrics(
    current_detail: CsvSnapshot,
    three_months_prior_golfer_clubs: CsvSnapshot,
    year: int,
    month: int,
) -> tuple[int, int, float | None, str]:
    """Calculate renewal eligibility and continued active status by golfer ID."""
    current_detail_active, _ = active_ids(current_detail)

    eligible_ids: set[str] = set()
    for row_number, row in enumerate(
        three_months_prior_golfer_clubs.rows, start=2
    ):
        golfer_id = row["golfer_id"].strip()
        if not golfer_id:
            raise ValidationError(
                f"{three_months_prior_golfer_clubs.label} has a blank "
                f"golfer_id at CSV row {row_number}"
            )
        inactive_date = parse_source_date(
            row["inactive_date"],
            f"{three_months_prior_golfer_clubs.label} inactive_date "
            f"for golfer {golfer_id}",
        )
        if (
            row["status"].strip().lower() == "active"
            and is_target_month(inactive_date, year, month)
        ):
            eligible_ids.add(golfer_id)

    renewed_ids = eligible_ids & current_detail_active
    up_for_renewal = len(eligible_ids)
    renewed = len(renewed_ids)
    rate = renewed / up_for_renewal if up_for_renewal else None
    method = (
        "upForRenewal: three-months-prior GC Golfer Clubs rows with "
        "status Active and inactive_date in target month; renewed: eligible "
        "golfer_id is Active anywhere in Current Month_Golfer Detail"
    )
    return renewed, up_for_renewal, rate, method
def calculate_membership_record(
    activity_month: str,
    current_detail: CsvSnapshot,
    prior_year: CsvSnapshot,
    three_months_prior_golfer_clubs: CsvSnapshot,
    existing_state: dict[str, Any],
) -> tuple[dict[str, Any], list[str], dict[str, MetricGrainCount]]:
    """Calculate one dashboard-compatible activity-month record."""
    year, month = target_year_month(activity_month)
    current_active, _ = active_ids(current_detail)
    prior_active, _ = active_ids(prior_year)

    new_golfer_counts, new_method = count_monthly_event(
        current_detail,
        year,
        month,
        date_field_name="created_date",
        flag_field_name="is_new_golfer",
        metric_label="new golfers",
    )
    reactivation_counts, reactivation_method = count_current_reactivations(
        current_detail, year, month
    )
    renewed, up_for_renewal, on_time_rate, renewal_method = calculate_renewal_metrics(
        current_detail,
        three_months_prior_golfer_clubs,
        year,
        month,
    )

    active_golfers = count_active_membership_rows(current_detail)
    prior_month_active = previous_month_active(
        existing_state["membership_monthly.json"], activity_month
    )
    net_change = active_golfers - prior_month_active
    percent_change = (
        net_change / prior_month_active if prior_month_active else None
    )
    retention_rate = (
        len(current_active & prior_active) / len(prior_active)
        if prior_active
        else None
    )
    month_name = datetime(year, month, 1).strftime("%B")

    record = {
        "year": year,
        "month": month_name,
        "activeGolfers": active_golfers,
        "monthNum": month,
        "label": f"{month_name} {year}",
        "priorMonthActive": prior_month_active,
        "netChange": net_change,
        "percentChange": percent_change,
        "newGolfers": new_golfer_counts.membership_rows,
        "reactivations": reactivation_counts.membership_rows,
        "onTimeRenewalRate": on_time_rate,
        "renewed": renewed,
        "upForRenewal": up_for_renewal,
        "retentionRate": retention_rate,
    }
    validate_membership_record(record)
    notes = [
        "activeGolfers counted Active Current Month_Golfer Detail membership rows without GHIN deduplication",
        new_method,
        reactivation_method,
        renewal_method,
        "retentionRate matched distinct prior-year active golfer_ids to distinct Active GHIN Numbers in Current Month_Golfer Detail",
        "netChange and percentChange used prior-month cumulative JSON state",
    ]
    grain_counts = {
        "newGolfers": new_golfer_counts,
        "reactivations": reactivation_counts,
    }
    return record, notes, grain_counts


def validate_membership_record(record: dict[str, Any]) -> None:
    """Validate the generated target record before it reaches any write phase."""
    count_fields = (
        "activeGolfers",
        "priorMonthActive",
        "newGolfers",
        "reactivations",
        "renewed",
        "upForRenewal",
    )
    for field_name in count_fields:
        value = record.get(field_name)
        if not isinstance(value, int) or value < 0:
            raise ValidationError(
                f"calculated {field_name} must be a nonnegative integer"
            )
    if record["renewed"] > record["upForRenewal"]:
        raise ValidationError("calculated renewed exceeds upForRenewal")
    for field_name in ("onTimeRenewalRate", "retentionRate"):
        value = record.get(field_name)
        if value is not None and not 0 <= value <= 1:
            raise ValidationError(f"calculated {field_name} is outside 0–1")


def membership_input_paths(inputs: Sequence[InputFileSummary]) -> dict[str, Path]:
    return {item.label: item.path for item in inputs}


def load_membership_snapshots(
    inputs: Sequence[InputFileSummary],
) -> tuple[
    CsvSnapshot,
    CsvSnapshot,
    CsvSnapshot,
    tuple[int, int],
]:
    paths = membership_input_paths(inputs)
    current_detail = read_csv_snapshot(
        paths["current golfer detail"], "current golfer detail"
    )
    prior_year = read_csv_snapshot(
        paths["same-month prior-year report"],
        "same-month prior-year report",
    )
    prior_clubs = read_csv_snapshot(
        paths["three-months-prior GC golfer clubs"],
        "three-months-prior GC golfer clubs",
    )
    source_stats = validate_current_source_contract(
        current_detail, prior_clubs
    )
    return (
        current_detail,
        prior_year,
        prior_clubs,
        source_stats,
    )


def validate_output_row_counts_stub(existing_state: dict[str, Any]) -> list[str]:
    """Future hook for cumulative merge row-count and reconciliation checks."""
    del existing_state
    return ["Cumulative merge row-count validation deferred until JSON writes are enabled."]


def format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.1f} MiB"


def format_parity_value(metric: str, value: Any) -> str:
    if value is None:
        return "null"
    if metric in MEMBERSHIP_RATE_METRICS and isinstance(value, (int, float)):
        return f"{value:.6f} ({value:.1%})"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    return str(value)


def format_parity_difference(metric: str, difference: int | float | None) -> str:
    if difference is None:
        return "n/a"
    if metric in MEMBERSHIP_RATE_METRICS:
        return f"{difference:+.9f}"
    if isinstance(difference, int):
        return f"{difference:+,}"
    return f"{difference:+g}"


def print_membership_parity_table(results: Sequence[ParityResult]) -> None:
    headers = (
        "Metric",
        "Calculated Value",
        "Dashboard Baseline Value",
        "Difference",
        "RESULT",
    )
    rows = [
        (
            result.metric,
            format_parity_value(result.metric, result.calculated_value),
            format_parity_value(result.metric, result.dashboard_value),
            format_parity_difference(result.metric, result.difference),
            result.result_label,
        )
        for result in results
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  " + " | ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    print("  " + "-+-".join("-" * width for width in widths))
    for row in rows:
        print("  " + " | ".join(row[index].ljust(widths[index]) for index in range(len(row))))


def print_metric_grain_diagnostics(
    counts: dict[str, MetricGrainCount],
    parity_results: Sequence[ParityResult],
) -> None:
    dashboard_values = {
        result.metric: result.dashboard_value for result in parity_results
    }
    headers = (
        "Metric",
        "Membership Rows",
        "Row Difference",
        "Row PASS/FAIL",
        "Distinct GHIN",
        "GHIN Difference",
        "GHIN PASS/FAIL",
        "Dashboard Value",
    )
    rows: list[tuple[str, ...]] = []
    for metric in ("newGolfers", "reactivations"):
        grain = counts[metric]
        dashboard = dashboard_values.get(metric)
        if isinstance(dashboard, int) and not isinstance(dashboard, bool):
            row_difference = grain.membership_rows - dashboard
            ghin_difference = grain.distinct_golfers - dashboard
            row_status = "PASS" if row_difference == 0 else "FAIL"
            ghin_status = "PASS" if ghin_difference == 0 else "FAIL"
            dashboard_display = f"{dashboard:,}"
            row_difference_display = f"{row_difference:+,}"
            ghin_difference_display = f"{ghin_difference:+,}"
        else:
            row_status = ghin_status = "FAIL"
            dashboard_display = "null"
            row_difference_display = ghin_difference_display = "n/a"
        rows.append(
            (
                metric,
                f"{grain.membership_rows:,}",
                row_difference_display,
                row_status,
                f"{grain.distinct_golfers:,}",
                ghin_difference_display,
                ghin_status,
                dashboard_display,
            )
        )
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  " + " | ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    print("  " + "-+-".join("-" * width for width in widths))
    for row in rows:
        print("  " + " | ".join(row[index].ljust(widths[index]) for index in range(len(row))))


def print_qa_summary(report: QAReport, status: str, message: str) -> None:
    print(f"Dashboard data update scaffold: report month {report.report_month}")
    print(f"Report date: {display_report_date(report.report_month)}")
    print(f"Activity month: {report.activity_month} ({display_month(report.activity_month)})")
    print(f"Dashboard label: {display_month(report.activity_month)}")
    print(f"Status: {status}")
    print(f"Mode: {'DRY RUN' if report.dry_run else 'STANDARD'}")
    print(f"Raw directory: {report.raw_directory}")
    print()

    if report.inputs:
        print("Inputs")
        for item in report.inputs:
            detail = f"{format_bytes(item.size_bytes)}"
            if item.data_rows is not None:
                detail += f", {item.data_rows:,} data rows"
            if item.sheet_count is not None:
                detail += f", {item.sheet_count} sheets"
            print(f"  {item.label}: {item.path.name} ({detail})")
        print()

    if report.json_state:
        print("Existing JSON state")
        for item in report.json_state:
            print(
                f"  {item.path.name}: {item.top_level_type}, "
                f"{item.row_count:,} top-level/logical rows"
            )
        print()

    if report.membership_record:
        print("Calculated target membership record")
        for field_name, value in report.membership_record.items():
            if field_name in {"onTimeRenewalRate", "retentionRate"}:
                display = "null" if value is None else f"{value:.6f} ({value:.1%})"
            elif field_name == "percentChange":
                display = "null" if value is None else f"{value:.6f} ({value:.1%})"
            else:
                display = str(value)
            print(f"  {field_name}: {display}")
        print()

    if report.membership_parity:
        baseline_note = f"baseline: {report.parity_baseline_label}"
        if report.parity_baseline_is_fallback:
            baseline_note += f"; {report.activity_month} has no populated baseline"
        print(f"Membership monthly diagnostics ({baseline_note})")
        print_membership_parity_table(report.membership_parity)
        print()

    if report.membership_grain_counts and report.membership_parity:
        print("New golfer and reactivation grain diagnostics")
        print_metric_grain_diagnostics(
            report.membership_grain_counts,
            report.membership_parity,
        )
        print()

    if report.segmentation_diagnostics:
        print("Segmentation JSON dry-run diagnostics")
        for item in report.segmentation_diagnostics:
            print(f"  {item.output_filename}")
            print(
                f"    source: {item.source_label} "
                f"({item.source_rows:,} rows)"
            )
            print(
                f"    output clubs: {item.clubs:,}; "
                f"target records: {item.target_records:,}"
            )
            print(
                f"    target records replaced in memory: "
                f"{item.existing_target_records:,}"
            )
            print(
                f"    historical records preserved: "
                f"{item.preserved_historical_records:,}; "
                f"merged records: {item.merged_records:,}"
            )
            print(
                "    All status counts: "
                + ", ".join(
                    f"{status}={item.status_counts.get(status, 0):,}"
                    for status in SEGMENTATION_STATUSES
                )
            )
            if item.output_filename == "segmentation_breakdown.json":
                print(
                    f"    gender diagnostics: missing="
                    f"{item.missing_gender_rows:,}, unrecognized="
                    f"{item.unknown_gender_rows:,}"
                )
                print(
                    f"    birth-date diagnostics: missing="
                    f"{item.missing_birth_date_rows:,}, implausible="
                    f"{item.implausible_birth_date_rows:,}"
                )
        print()

    if report.retention_diagnostics:
        item = report.retention_diagnostics
        print("Retention Analysis dry-run diagnostics")
        print(
            f"  source: Current Month_Golfer Detail.csv "
            f"({item.source_rows:,} membership rows)"
        )
        print(
            "  status counts: "
            + ", ".join(
                f"{status}={item.status_counts.get(status, 0):,}"
                for status in SEGMENTATION_STATUSES
            )
        )
        print(
            f"  missing creation dates: {item.missing_creation_dates:,}; "
            f"missing inactive status dates: "
            f"{item.missing_inactive_status_dates:,}"
        )
        print(
            "  invalid status dates before creation excluded from milestones: "
            + ", ".join(
                f"{status}={item.invalid_status_dates_by_status.get(status, 0):,}"
                for status in SEGMENTATION_STATUSES
            )
        )
        print("  Cohort comparison")
        print(
            "    Year | Created | Baseline | Diff | Active Today | "
            "Baseline | Diff"
        )
        print(
            "    -----+---------+----------+------+--------------+"
            "----------+-----"
        )
        for year in RETENTION_COHORT_YEARS:
            created = item.cohort_created[year]
            created_baseline = item.baseline_created[year]
            active = item.cohort_active_today[year]
            active_baseline = item.baseline_active_today[year]
            print(
                f"    {year} | {created:>7,} | {created_baseline:>8,} | "
                f"{created-created_baseline:>+4,} | {active:>12,} | "
                f"{active_baseline:>8,} | {active-active_baseline:>+4,}"
            )
        print("  Milestone comparison")
        print("    Cohort | Months | Calculated | Baseline | Difference")
        print("    -------+--------+------------+----------+-----------")
        for year in RETENTION_COHORT_YEARS:
            for months in RETENTION_MILESTONE_MONTHS:
                calculated = item.cohort_milestones[(year, months)]
                baseline = item.baseline_milestones.get((year, months))
                calculated_display = (
                    "TBD" if calculated is None else f"{calculated:,}"
                )
                baseline_display = (
                    "TBD" if baseline is None else f"{baseline:,}"
                )
                difference_display = (
                    "n/a"
                    if calculated is None or baseline is None
                    else f"{calculated-baseline:+,}"
                )
                print(
                    f"    {year:>6} | {months:>6} | "
                    f"{calculated_display:>10} | {baseline_display:>8} | "
                    f"{difference_display:>10}"
                )
        print(
            f"  club rankings: {item.club_count} clubs; Created total "
            f"{item.club_created_total:,} vs baseline "
            f"{item.baseline_club_created_total:,}"
        )
        print(
            f"  club totals matching exactly: "
            f"{item.exact_club_total_matches}/{item.club_count}; "
            f"maximum total difference: "
            f"{item.maximum_club_total_difference:,}"
        )
        print(
            f"  identical default rank positions: "
            f"{item.identical_rank_positions}/{item.club_count}; "
            f"maximum rank shift: {item.maximum_rank_shift}"
        )
        print()

    if report.recovery_diagnostics:
        item = report.recovery_diagnostics
        print("Recovery Analysis dry-run diagnostics")
        print(
            f"  source rows: {item.source_rows:,}; "
            f"Active rows: {item.active_rows:,}"
        )
        print(
            f"  qualifying YTD recovery rows: "
            f"{item.qualifying_recovery_rows:,}; distinct GHINs: "
            f"{item.distinct_recovery_ghins:,}"
        )
        print(
            f"  latest completed month recoveries: "
            f"{item.latest_month_recoveries:,}; clubs with recoveries: "
            f"{item.clubs_with_recoveries:,}"
        )
        print(
            f"  missing creation dates: {item.missing_creation_dates:,}; "
            f"missing status dates: {item.missing_status_dates:,}; "
            f"creation date not before status date: "
            f"{item.creation_not_before_status_rows:,}"
        )
        print(
            "  reconciliations: "
            f"club={'PASS' if item.club_breakdown_reconciles else 'FAIL'}, "
            f"creation year={'PASS' if item.creation_year_breakdown_reconciles else 'FAIL'}, "
            f"membership age={'PASS' if item.membership_age_breakdown_reconciles else 'FAIL'}"
        )
        print()

    if report.ghin_trials_diagnostics:
        item = report.ghin_trials_diagnostics
        print("GHIN Trials dry-run diagnostics")
        print("  Source files")
        for source_label, path in item.source_files.items():
            filename = path.name
            coverage = item.date_coverage.get(filename, (None, None))
            coverage_label = (
                f"{coverage[0]} to {coverage[1]}"
                if coverage[0] and coverage[1]
                else "not date-grained"
            )
            print(
                f"    {filename}: {item.source_row_counts.get(filename, 0):,} rows; "
                f"coverage {coverage_label}"
            )
        print("  Generated summary")
        print(
            f"    totalTrialsCreated={item.generated_summary['totalTrialsCreated']:,}; "
            f"trialConversions={item.generated_summary['trialConversions']:,}; "
            f"conversionRate={item.generated_summary['conversionRate']:.2%}; "
            f"activeTrialGolfers={item.generated_summary['activeTrialGolfers']:,}; "
            f"inactiveTrialGolfers={item.generated_summary['inactiveTrialGolfers']:,}"
        )
        print(
            f"  Monthly: {item.monthly_records:,} records; "
            f"trials={item.monthly_trials_total:,}; "
            f"conversions={item.monthly_conversions_total:,}"
        )
        print(
            f"  Conversion buckets: {item.conversion_bucket_records:,} records; "
            f"total={item.conversion_bucket_total:,}"
        )
        print(
            f"  AGA conversions: {item.aga_records:,} records; total={item.aga_total:,}"
        )
        print(
            f"  Overview: preserved {item.overview_campaigns_preserved:,} campaign rows "
            f"and {item.overview_funnel_preserved:,} funnel rows from existing ghin_trials.json"
        )
        print("  Parity vs existing data/ghin_trials.json")
        if item.parity_differences:
            for diff in item.parity_differences:
                print(f"    DIFF {diff}")
        else:
            print("    PASS generated output matches existing comparable GHIN values")
        print()

    if report.calculation_notes:
        print("Calculation methods")
        for note in report.calculation_notes:
            print(f"  - {note}")
        print()

    if report.checks:
        print("Checks")
        for name, check_status, detail in report.checks:
            print(f"  {name}: {check_status} — {detail}")
        print()

    if report.warnings:
        print("Warnings")
        for warning in report.warnings:
            print(f"  - {warning}")
        print()

    print("Backup plan")
    print(f"  {report.backup_directory}")
    print("  Backup directory not created during dry-run preview.")
    print()
    print("Writes")
    if report.dry_run:
        print("  Disabled by --dry-run; no JSON files were modified.")
    elif report.written_outputs:
        for output_path in report.written_outputs:
            print(f"  Wrote {output_path}")
    else:
        print("  No JSON files were modified.")
    print()
    print(message)


def run(args: argparse.Namespace) -> int:
    root = project_root()
    data_directory = root / "data"
    report_month = args.month
    activity_month = activity_month_for_report(report_month)
    raw_directory = data_directory / "raw" / report_month
    report = QAReport(
        report_month=report_month,
        activity_month=activity_month,
        dry_run=args.dry_run,
        raw_directory=raw_directory,
        backup_directory=planned_backup_directory(data_directory, report_month),
    )

    try:
        report.add_check(
            "Reporting period",
            "PASS",
            (
                f"report month {report_month} ({display_report_date(report_month)} snapshot); "
                f"source directory data/raw/{report_month}/; "
                f"activity month and dashboard label {display_month(activity_month)}"
            ),
        )
        if args.ghin_only:
            existing_state, report.json_state = load_existing_json_state(data_directory)
            report.add_check(
                "Existing JSON loading",
                "PASS",
                f"loaded {len(existing_state)} cumulative output files",
            )
            report.ghin_trials_output, report.ghin_trials_diagnostics = generate_ghin_trials_output(
                report_month,
                raw_directory,
                existing_state["ghin_trials.json"],
            )
            report.add_check(
                "GHIN Trials Tableau exports",
                "PASS",
                "validated five aggregate Tableau CSV exports",
            )
            report.add_check(
                "GHIN Trials generation",
                "PASS",
                (
                    f"generated summary, {len(report.ghin_trials_output['monthly'])} monthly rows, "
                    f"{len(report.ghin_trials_output['conversionBuckets'])} conversion buckets, and "
                    f"{len(report.ghin_trials_output['agaConversions'])} AGA rows"
                ),
            )
            report.calculation_notes.extend(
                (
                    "ghin_trials.json summary is generated from Yearly Statistics.csv for the report year",
                    "ghin_trials.json monthly rows aggregate Trials Created by Day.csv and Trial Conversions by Day.csv by activity-month calendar month",
                    "ghin_trials.json conversionBuckets uses Conversions by Days in Trial.csv counts and validates Tableau percentages against count share",
                    "ghin_trials.json agaConversions uses AGA Conversions.csv grouped counts sorted by count descending and association name",
                    "overview numeric fields are generated from summary; overview campaign and funnel rows are preserved from existing ghin_trials.json because the five aggregate Tableau exports do not include campaign, activation, or engagement detail",
                )
            )
            if args.dry_run:
                report.add_check(
                    "GHIN Trials JSON write",
                    "SKIPPED",
                    "dry-run output was validated in memory; data/ghin_trials.json was not modified",
                )
            else:
                report.written_outputs.append(
                    write_ghin_trials_json(
                        data_directory,
                        report.backup_directory,
                        report.ghin_trials_output,
                    )
                )
                report.add_check(
                    "GHIN Trials JSON write",
                    "PASS",
                    "wrote data/ghin_trials.json",
                )
            print_qa_summary(
                report,
                status="PASS (GHIN TRIALS)",
                message=(
                    "GHIN Trials dry-run completed; no JSON files were written."
                    if args.dry_run
                    else "GHIN Trials JSON was written."
                ),
            )
            return 0

        report.inputs = discover_inputs(
            raw_directory,
            skip_marketing=args.skip_marketing,
        )
        report.add_check(
            "Required source files",
            "PASS",
            (
                "three CSV sources are present and marketing was skipped"
                if args.skip_marketing
                else "three CSV sources and the marketing workbook are present"
            ),
        )
        report.add_check(
            "Marketing workbook",
            "SKIPPED" if args.skip_marketing else "PASS",
            (
                "disabled by --skip-marketing"
                if args.skip_marketing
                else "workbook contains exactly 3 sheets"
            ),
        )

        existing_state, report.json_state = load_existing_json_state(data_directory)
        report.add_check(
            "Existing JSON loading",
            "PASS",
            f"loaded {len(existing_state)} cumulative output files",
        )

        (
            current_detail,
            prior_year,
            three_months_prior_clubs,
            source_stats,
        ) = load_membership_snapshots(report.inputs)
        detail_golfers, prior_gc_golfers = source_stats
        report.add_check(
            "Current Golfer Detail schema",
            "PASS",
            f"master current-month headers are present; {detail_golfers:,} distinct GHIN Numbers across membership rows",
        )
        report.add_check(
            "Three-Months-Prior GC Golfer Clubs schema",
            "PASS",
            f"golfer_id, status, and inactive_date are present; {prior_gc_golfers:,} unique golfers available for renewal eligibility",
        )
        (
            report.membership_record,
            report.calculation_notes,
            report.membership_grain_counts,
        ) = calculate_membership_record(
            activity_month,
            current_detail,
            prior_year,
            three_months_prior_clubs,
            existing_state,
        )
        report.calculation_notes.insert(
            0,
            (
                f"report month {display_month(report_month)} reads data/raw/{report_month}/ "
                f"and produces the {display_month(activity_month)} dashboard record"
            ),
        )

        status_records, status_counts = generate_segmentation_status_records(
            report_month,
            activity_month,
            current_detail,
        )
        (
            merged_status_records,
            existing_status_target_records,
            preserved_status_records,
        ) = merge_target_month_records(
            existing_state["segmentation_status.json"],
            status_records,
            activity_month,
            "segmentation_status.json",
        )
        status_clubs = len({record["clubName"] for record in status_records})
        report.segmentation_diagnostics.append(
            SegmentationDiagnostics(
                output_filename="segmentation_status.json",
                source_label="Current Month_Golfer Detail.csv",
                source_rows=len(current_detail.rows),
                target_records=len(status_records),
                existing_target_records=existing_status_target_records,
                merged_records=len(merged_status_records),
                preserved_historical_records=preserved_status_records,
                clubs=status_clubs,
                status_counts=status_counts,
            )
        )
        report.add_check(
            "Segmentation status generation",
            "PASS",
            (
                f"generated {len(status_records):,} {display_month(activity_month)} "
                "All/club records from Golfer Detail"
            ),
        )

        breakdown_records, breakdown_stats = (
            generate_segmentation_breakdown_records(
                report_month,
                activity_month,
                current_detail,
            )
        )
        (
            merged_breakdown_records,
            existing_breakdown_target_records,
            preserved_breakdown_records,
        ) = merge_target_month_records(
            existing_state["segmentation_breakdown.json"],
            breakdown_records,
            activity_month,
            "segmentation_breakdown.json",
        )
        breakdown_clubs = len(
            {record["clubName"] for record in breakdown_records}
        )
        report.segmentation_diagnostics.append(
            SegmentationDiagnostics(
                output_filename="segmentation_breakdown.json",
                source_label="Current Month_Golfer Detail.csv",
                source_rows=len(current_detail.rows),
                target_records=len(breakdown_records),
                existing_target_records=existing_breakdown_target_records,
                merged_records=len(merged_breakdown_records),
                preserved_historical_records=preserved_breakdown_records,
                clubs=breakdown_clubs,
                status_counts={
                    status: breakdown_stats[status]
                    for status in SEGMENTATION_STATUSES
                },
                missing_gender_rows=breakdown_stats["missingGender"],
                unknown_gender_rows=breakdown_stats["unknownGender"],
                missing_birth_date_rows=breakdown_stats["missingBirthDate"],
                implausible_birth_date_rows=breakdown_stats[
                    "implausibleBirthDate"
                ],
            )
        )
        report.add_check(
            "Segmentation breakdown generation",
            "PASS",
            (
                f"generated {len(breakdown_records):,} {display_month(activity_month)} "
                "All/club age and gender records from Golfer Detail"
            ),
        )
        report.add_check(
            "Segmentation historical preservation",
            "PASS",
            (
                f"preserved {preserved_status_records:,} status and "
                f"{preserved_breakdown_records:,} breakdown records outside "
                f"{activity_month}"
            ),
        )
        report.calculation_notes.extend(
            (
                "segmentation_status.json counted Golfer Detail membership rows by Club Name and Golfer Status; no join or GHIN deduplication",
                "segmentation_breakdown.json counted Golfer Detail membership rows directly by club/status, Gender, and age as of the report date; no join or golfer deduplication",
                "segmentation target-month records were replaced only in memory; records outside the activity month were preserved",
            )
        )

        (
            retention_cohorts_output,
            retention_rankings_output,
            retention_stats,
        ) = generate_retention_outputs(report_month, current_detail)
        report.retention_diagnostics = build_retention_diagnostics(
            len(current_detail.rows),
            retention_stats,
            retention_rankings_output,
            existing_state["retention_cohorts.json"],
            existing_state["retention_club_rankings.json"],
        )
        report.add_check(
            "Retention cohort generation",
            "PASS",
            (
                f"generated {len(retention_cohorts_output['cohorts'])} cohort cards, "
                "6 summary metrics, 5 creation-year status rows, and survival-curve geometry"
            ),
        )
        report.add_check(
            "Retention club ranking generation",
            "PASS",
            (
                f"generated {len(retention_rankings_output)} club rows from "
                "2022–2024 Created and Active Today membership rows"
            ),
        )
        invalid_retention_rows = sum(
            report.retention_diagnostics.invalid_status_dates_by_status.values()
        )
        report.add_check(
            "Retention milestone validation",
            "PASS",
            (
                "milestone survival is nonincreasing and does not exceed Created; "
                f"{invalid_retention_rows:,} rows with Golfer Status Date before "
                "Membership Creation Date were excluded from milestone numerators"
            ),
        )
        report.calculation_notes.extend(
            (
                "retention Created and Active Today counts use Current Month_Golfer Detail membership rows without GHIN deduplication",
                "retention milestones add 13, 25, or 37 calendar months to Membership Creation Date; Active rows survive through the report date and non-Active rows survive when Golfer Status Date is later than the milestone",
                "retention milestone rows with Golfer Status Date before Membership Creation Date are excluded from survival numerators and retained in Created denominators",
                "retention club rankings divide Active Today by Created within each Club Name and creation year; Total is 2022–2024 Created",
                "retention survival-curve SVG points are regenerated from milestone percentages",
            )
        )
        if invalid_retention_rows:
            report.warnings.append(
                f"Retention QA excluded {invalid_retention_rows:,} membership rows "
                "from milestone survival because Golfer Status Date precedes "
                "Membership Creation Date."
            )

        report.recovery_output, report.recovery_diagnostics = (
            generate_recovery_analysis(report_month, current_detail)
        )
        report.add_check(
            "Recovery Analysis generation",
            "PASS",
            (
                f"generated {len(report.recovery_output['monthlyTrend'])} monthly rows, "
                f"{len(report.recovery_output['byClub'])} club rows, "
                f"{len(report.recovery_output['byCreationYear'])} creation-year rows, "
                f"{len(report.recovery_output['byMembershipAge'])} age buckets, and "
                f"{len(report.recovery_output['rankings'])} ranking rows"
            ),
        )
        report.add_check(
            "Recovery Analysis reconciliation",
            "PASS",
            "club, creation-year, and membership-age totals reconcile to Recoveries YTD",
        )
        report.calculation_notes.extend(
            (
                "Recovery Analysis is membership-level and includes Active Golfer Detail rows where Membership Creation Date precedes Golfer Status Date and Golfer Status Date falls inside the YTD activity period",
                "Recovery Analysis uses Recoveries as % of Active Base for composition metrics; it is not an inactive-population conversion rate",
                "Recovery Analysis monthly, club, creation-year, membership-age, and ranking datasets reconcile to the same YTD recovery cohort",
            )
        )
        try:
            report.ghin_trials_output, report.ghin_trials_diagnostics = generate_ghin_trials_output(
                report_month,
                raw_directory,
                existing_state["ghin_trials.json"],
            )
            report.add_check(
                "GHIN Trials generation",
                "PASS",
                (
                    f"generated summary, {len(report.ghin_trials_output['monthly'])} monthly rows, "
                    f"{len(report.ghin_trials_output['conversionBuckets'])} conversion buckets, and "
                    f"{len(report.ghin_trials_output['agaConversions'])} AGA rows"
                ),
            )
            report.calculation_notes.extend(
                (
                    "ghin_trials.json summary is generated from Yearly Statistics.csv for the report year",
                    "ghin_trials.json monthly rows aggregate Trials Created by Day.csv and Trial Conversions by Day.csv by activity-month calendar month",
                    "ghin_trials.json conversionBuckets uses Conversions by Days in Trial.csv counts and validates Tableau percentages against count share",
                    "ghin_trials.json agaConversions uses AGA Conversions.csv grouped counts sorted by count descending and association name",
                    "overview numeric fields are generated from summary; overview campaign and funnel rows are preserved from existing ghin_trials.json because the five aggregate Tableau exports do not include campaign, activation, or engagement detail",
                )
            )
        except ValidationError as exc:
            report.warnings.append(f"GHIN Trials generation skipped: {exc}")
        dashboard_record, baseline_label, baseline_is_fallback = membership_parity_baseline(
            existing_state["membership_monthly.json"], activity_month
        )
        report.parity_baseline_label = baseline_label
        report.parity_baseline_is_fallback = baseline_is_fallback
        if dashboard_record is None:
            parity_evaluated = False
            parity_passed = True
            report.add_check(
                "Membership monthly parity",
                "SKIPPED",
                f"{activity_month} has no populated dashboard baseline and no populated prior-month fallback",
            )
        else:
            parity_evaluated = True
            report.membership_parity = compare_membership_parity(
                report.membership_record,
                dashboard_record,
            )
            comparable_results = [
                result
                for result in report.membership_parity
                if result.result_label != "METHODOLOGY CHANGE"
            ]
            methodology_change_count = (
                len(report.membership_parity) - len(comparable_results)
            )
            parity_pass_count = sum(result.passed for result in comparable_results)
            parity_passed = parity_pass_count == len(comparable_results)
            report.add_check(
                "Membership monthly diagnostics",
                "PASS" if parity_passed else "FAIL",
                (
                    f"{parity_pass_count}/{len(comparable_results)} comparable metrics match "
                    f"the {baseline_label} dashboard baseline; "
                    f"{methodology_change_count} metrics classified as methodology changes"
                ),
            )
            if baseline_is_fallback:
                report.warnings.append(
                    f"{activity_month} dashboard metrics are all null; parity uses {baseline_label} as a fallback baseline."
                )
            new_golfer_parity = next(
                result
                for result in report.membership_parity
                if result.metric == "newGolfers"
            )
            if not new_golfer_parity.passed:
                report.warnings.append(
                    "New Golfer logic remains membership_creation_date in the activity month; "
                    "the dashboard variance is treated as likely snapshot/backfill drift."
                )
            report.warnings.append(
                "The old dashboard used stricter same-club and expiration-extension renewal logic. "
                "The new active-anywhere method counts eligible golfers retained anywhere in the GC ecosystem; "
                "Renewed and On-Time Renewal Rate differences are methodology changes, not parity failures."
            )
            report.warnings.append(
                "The old dashboard's 70.76% retention rate cannot be reproduced from available fields "
                "without nonstandard exclusions or a different prior-year snapshot. The new retention method "
                "uses distinct active prior-year GHINs as the denominator and counts those GHINs Active anywhere "
                "in Current Month_Golfer Detail as the numerator; its variance is a methodology change."
            )
        report.add_check(
            "Membership target record",
            "PASS",
            f"calculated {report.membership_record['label']}",
        )
        for warning in validate_output_row_counts_stub(existing_state):
            report.warnings.append(warning)
        report.warnings.append(
            "Current Month_Golfer Detail is the master current-month source for membership, segmentation, retention, and recovery outputs; Current Month_GC Golfer Clubs is no longer required."
        )
        report.warnings.append(
            "Marketing workbook processing was skipped."
            if args.skip_marketing
            else "Marketing workbook column validation remains deferred."
        )
        if args.dry_run:
            report.add_check(
                "Recovery Analysis JSON write",
                "SKIPPED",
                "dry-run output was validated in memory; no JSON was written",
            )
        else:
            report.written_outputs.append(
                write_recovery_analysis(
                    data_directory,
                    report.backup_directory,
                    report.recovery_output,
                )
            )
            report.add_check(
                "Recovery Analysis JSON write",
                "PASS",
                "wrote data/recovery_analysis.json; no other JSON output was modified",
            )
            if report.ghin_trials_output:
                report.written_outputs.append(
                    write_ghin_trials_json(
                        data_directory,
                        report.backup_directory,
                        report.ghin_trials_output,
                    )
                )
                report.add_check(
                    "GHIN Trials JSON write",
                    "PASS",
                    "wrote data/ghin_trials.json",
                )
    except ValidationError as exc:
        report.add_check("Update validation", "FAIL", str(exc))
        print_qa_summary(
            report,
            status="FAIL",
            message="No files were written.",
        )
        return 1

    print_qa_summary(
        report,
        status=(
            "PASS (NO DASHBOARD BASELINE)"
            if not parity_evaluated
            else (
                "PASS (MEMBERSHIP DIAGNOSTICS)"
                if parity_passed
                else "FAIL (MEMBERSHIP DIAGNOSTICS)"
            )
        ),
        message=(
            f"Activity month {activity_month} has no populated dashboard baseline."
            if not parity_evaluated
            else (
                f"Target membership record matches the {report.parity_baseline_label} dashboard baseline."
                if parity_passed
                else f"Target membership record differs from the {report.parity_baseline_label} dashboard baseline."
            )
        ) + (
            " Recovery Analysis JSON was written."
            if report.written_outputs
            else " No JSON files were written."
        ),
    )
    return 0 if parity_passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
