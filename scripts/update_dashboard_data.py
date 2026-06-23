#!/usr/bin/env python3
"""Phase 2 preview for the monthly dashboard data updater.

This phase validates the monthly input package, loads the existing cumulative
JSON state, calculates one membership-month record, plans a backup location,
and prints a QA summary. JSON writes are intentionally disabled.

Reporting convention
--------------------
``--month YYYY-MM`` is the report month, normally run on the first day of that
month. Source files belong in ``data/raw/YYYY-MM/`` under the report month.
Those report-date snapshots produce dashboard metrics and a dashboard label for
the immediately preceding calendar month.

Example: ``--month 2026-07`` reads ``data/raw/2026-07/`` as the July 1, 2026
snapshot and calculates the June 2026 dashboard record.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree


REQUIRED_INPUT_FILENAMES = {
    "current golfer detail": "Current Month_Golfer Detail.csv",
    "current GC golfer clubs": "Current Month_GC Golfer Clubs.csv",
    "same-month prior-year report": "same_month_prior_year_report.csv",
    "three-months-prior GC golfer clubs": "Three-Months-Prior_GC Golfer Clubs.csv",
    "marketing workbook": "marketing_workbook.xlsx",
}

OPTIONAL_MEMBERSHIP_INPUT_LABEL = "current GC golfer clubs"

EXISTING_JSON_FILENAMES = (
    "membership_monthly.json",
    "segmentation_status.json",
    "segmentation_breakdown.json",
    "retention_club_rankings.json",
    "retention_cohorts.json",
)

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
}

GC_GOLFER_CLUBS_REQUIRED_HEADERS = {
    "golfer_id",
    "club_id",
    "golf_association",
    "status",
    "inactive_date",
    "inactive_flag",
    "email",
    "gender",
    "date_of_birth",
    "first_name",
    "last_name",
    "primary_club",
    "name",
    "club_name",
    "membership_code",
}

RENEWAL_ELIGIBILITY_REQUIRED_HEADERS = {
    "golfer_id",
    "status",
    "inactive_date",
}

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
            "Validate a monthly dashboard input package and plan a cumulative "
            "JSON update. --month is the report month; the dashboard output month "
            "is the prior calendar month. Phase 2 does not write JSON."
        ),
        epilog=(
            "Example: --month 2026-07 reads data/raw/2026-07/ as the July 1, 2026 "
            "report snapshot and calculates the June 2026 dashboard record."
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
        help="allow membership processing without marketing_workbook.xlsx",
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
    """Locate and minimally validate the required physical source files."""
    if not raw_directory.is_dir():
        raise ValidationError(f"raw input directory does not exist: {raw_directory}")

    required_paths = {
        label: raw_directory / filename
        for label, filename in REQUIRED_INPUT_FILENAMES.items()
        if not (skip_marketing and label == "marketing workbook")
        and label != OPTIONAL_MEMBERSHIP_INPUT_LABEL
    }
    missing = [path.name for path in required_paths.values() if not path.is_file()]
    if missing:
        raise ValidationError(
            "missing required input files: " + ", ".join(sorted(missing))
        )

    discovered_sources = {
        path.name
        for path in raw_directory.iterdir()
        if path.is_file() and path.suffix.lower() in RAW_SOURCE_SUFFIXES
    }
    expected_sources = set(REQUIRED_INPUT_FILENAMES.values())
    unexpected = sorted(discovered_sources - expected_sources)
    if unexpected:
        raise ValidationError(
            "unexpected source files found: "
            + ", ".join(unexpected)
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
    optional_current_gc = (
        raw_directory / REQUIRED_INPUT_FILENAMES[OPTIONAL_MEMBERSHIP_INPUT_LABEL]
    )
    if optional_current_gc.is_file():
        summaries.append(
            InputFileSummary(
                label=OPTIONAL_MEMBERSHIP_INPUT_LABEL,
                path=optional_current_gc,
                size_bytes=optional_current_gc.stat().st_size,
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
    print("  Backup directory not created in Phase 2 preview.")
    print()
    print("Writes")
    if report.dry_run:
        print("  Disabled by --dry-run; no JSON files were modified.")
    else:
        print("  Disabled for Phase 2 preview, even without --dry-run.")
        print("  No JSON files were modified; the calculated record is QA-only.")
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
        report.inputs = discover_inputs(
            raw_directory,
            skip_marketing=args.skip_marketing,
        )
        report.add_check(
            "Required source files",
            "PASS",
            (
                "three core membership CSVs are present; Current GC Golfer Clubs is optional and marketing was skipped"
                if args.skip_marketing
                else "three core membership CSVs and the marketing workbook are present; Current GC Golfer Clubs is optional"
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
            f"all 10 corrected source headers are present; {detail_golfers:,} distinct GHIN Numbers across membership rows",
        )
        report.add_check(
            "Current GC Golfer Clubs",
            "IGNORED",
            "not loaded or used for core membership metrics",
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
            "Current Month_GC Golfer Clubs is retained for future club-level analysis but is not used by core membership metrics."
        )
        report.warnings.append(
            "Future segmentation and cohort calculations should use Golfer Detail where its fields permit."
        )
        report.warnings.append(
            "Marketing workbook processing was skipped."
            if args.skip_marketing
            else "Marketing workbook column validation remains deferred."
        )
        report.add_check(
            "JSON overwrite",
            "SKIPPED",
            "Phase 2 is report-only; target record was not merged or written",
        )
    except ValidationError as exc:
        report.add_check("Phase 2 validation", "FAIL", str(exc))
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
            f"Activity month {activity_month} has no populated dashboard baseline. No JSON files were written."
            if not parity_evaluated
            else (
                f"Target membership record matches the {report.parity_baseline_label} dashboard baseline. No JSON files were written."
                if parity_passed
                else f"Target membership record differs from the {report.parity_baseline_label} dashboard baseline. No JSON files were written."
            )
        ),
    )
    return 0 if parity_passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
