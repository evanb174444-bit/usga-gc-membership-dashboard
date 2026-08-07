#!/usr/bin/env python3
import argparse
import calendar
import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "report-months.json"


def load_manifest():
    with MANIFEST.open() as f:
        return json.load(f)


def save_manifest(data):
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")


def parse_key(key):
    year, month = key.split("-")
    return int(year), int(month)


def previous_key(key):
    year, month = parse_key(key)
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def month_label(key):
    year, month = parse_key(key)
    return f"{calendar.month_name[month]} {year}"


def slug_month(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def default_data_through(key):
    year, month = parse_key(key)
    first = date(year, month, 1)
    through = first - timedelta(days=1)
    return through.strftime("%B %-d, %Y")


def default_report_date(key):
    year, month = parse_key(key)
    return date(year, month, 2).strftime("%B %-d, %Y")


def main():
    parser = argparse.ArgumentParser(description="Create a new monthly executive report archive entry.")
    parser.add_argument("report", help="New report key, e.g. 2026-09")
    parser.add_argument("--seed", help="Existing report key to seed copy from. Defaults to previous month or current manifest.")
    parser.add_argument("--current", action="store_true", help="Set the new report as the current report month.")
    args = parser.parse_args()

    manifest = load_manifest()
    months = manifest.setdefault("months", {})
    if args.report in months:
        raise SystemExit(f"{args.report} already exists in reports/report-months.json")

    seed_key = args.seed or previous_key(args.report)
    if seed_key not in months:
        seed_key = manifest.get("current")
    if not seed_key or seed_key not in months:
        raise SystemExit("No valid seed month found.")

    report_month = month_label(args.report)
    archive_dir = ROOT / "reports" / "archive" / args.report
    archive_dir.mkdir(parents=True, exist_ok=True)

    seed_copy = ROOT / months[seed_key]["copyPath"]
    copy_path = archive_dir / "report-copy.json"
    shutil.copyfile(seed_copy, copy_path)

    copy = json.loads(copy_path.read_text())
    copy["reportMonth"] = report_month
    copy["reportDate"] = f"Report Date: {default_report_date(args.report)}"
    copy_path.write_text(json.dumps(copy, indent=2) + "\n")

    wrapper_path = archive_dir / "executive-report.html"
    wrapper_path.write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url=../../html-report/executive-report.html?report={args.report}">
  <title>{report_month} Executive Report</title>
</head>
<body>
  <p><a href="../../html-report/executive-report.html?report={args.report}">Open {report_month} Executive Report</a></p>
</body>
</html>
""")

    months[args.report] = {
        "reportMonth": report_month,
        "reportDate": default_report_date(args.report),
        "dataThrough": default_data_through(args.report),
        "status": "draft",
        "copyPath": str(copy_path.relative_to(ROOT)),
        "htmlPath": str(wrapper_path.relative_to(ROOT)),
        "pdfPath": str((archive_dir / f"gc-membership-executive-report-{slug_month(report_month)}.pdf").relative_to(ROOT)),
    }
    if args.current:
        manifest["current"] = args.report
    save_manifest(manifest)
    print(f"Created report month {args.report} from {seed_key}")
    print(f"Copy: {copy_path}")


if __name__ == "__main__":
    main()
