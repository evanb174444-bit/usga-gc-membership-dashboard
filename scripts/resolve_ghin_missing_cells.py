#!/usr/bin/env python3
"""Resolve GHIN screenshot cells using full-page and row-context OCR evidence."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compile_ghin_screenshots import parse_record, read_jsonl  # noqa: E402


FIELDS = ("Golfers", "Ranked Golfers", "Scores Posted")


def contact_values(contact_ocr: Path, missing_rows: list[dict]) -> dict[tuple, dict[str, int]]:
    records = read_jsonl(contact_ocr)
    values = {}
    for batch, record in enumerate(records):
        subset = missing_rows[batch * 40:(batch + 1) * 40]
        height = record["height"]
        for index, row in enumerate(subset):
            expected_y = 1 - (10 + index * 55 + 25) / height
            found = {}
            for observation in record["observations"]:
                text = observation["text"].strip()
                if not re.fullmatch(r"\d+", text):
                    continue
                x = observation["x"] + observation["width"] / 2
                y = observation["y"] + observation["height"] / 2
                if abs(y - expected_y) > 0.014:
                    continue
                if 0.62 <= x < 0.72:
                    found["Golfers"] = int(text)
                elif 0.72 <= x < 0.82:
                    found["Ranked Golfers"] = int(text)
                elif 0.82 <= x < 0.91:
                    found["Scores Posted"] = int(text)
            values[(row["Status"], row["Source Page"], row["Source Row"])] = found
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--completed-ocr", type=Path, required=True)
    parser.add_argument("--active-upcoming-ocr", type=Path, required=True)
    parser.add_argument("--contact-ocr", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    for record in read_jsonl(args.completed_ocr):
        rows += parse_record(record, "Completed")[1]
    for record in read_jsonl(args.active_upcoming_ocr):
        status = "Upcoming" if Path(record["path"]).name == "Upcoming.png" else "Active"
        rows += parse_record(record, status)[1]
    # Preserve the source JSONL order while mapping the contact sheets: those
    # sheets were generated in that same order. Sort only after resolution.
    missing_rows = [row for row in rows if any(row[field] is None for field in FIELDS)]
    if len(missing_rows) != 198:
        raise ValueError(f"Expected 198 rows needing review; found {len(missing_rows)}")
    contact = contact_values(args.contact_ocr, missing_rows)

    with args.detail.open(newline="", encoding="utf-8-sig") as source:
        detail = {
            (row["Status"], int(row["Source Page"]), int(row["Source Row"])): row
            for row in csv.DictReader(source)
        }

    # Direct visual checks for cells where the enlarged contact-sheet OCR still
    # omitted a nonzero one-digit value or a cropped edge value.
    reviewed = {
        ("Active", 3, 10, "Scores Posted"): 3,
        ("Active", 3, 16, "Ranked Golfers"): 0,
        ("Active", 3, 23, "Ranked Golfers"): 1,
        ("Active", 3, 25, "Ranked Golfers"): 1,
        ("Active", 4, 8, "Golfers"): 5,
        ("Active", 5, 2, "Golfers"): 3,
        ("Active", 8, 21, "Ranked Golfers"): 9,
        ("Active", 9, 3, "Golfers"): 4,
        ("Active", 9, 3, "Ranked Golfers"): 2,
        ("Active", 9, 3, "Scores Posted"): 8,
        ("Completed", 16, 13, "Ranked Golfers"): 7,
        ("Completed", 16, 25, "Scores Posted"): 6,
        ("Completed", 17, 15, "Scores Posted"): 7,
        ("Completed", 18, 11, "Ranked Golfers"): 3,
        ("Completed", 18, 22, "Scores Posted"): 8,
        ("Completed", 19, 5, "Scores Posted"): 3,
        ("Completed", 19, 21, "Ranked Golfers"): 3,
        ("Completed", 22, 21, "Scores Posted"): 122,
        ("Completed", 6, 11, "Scores Posted"): 5,
        ("Completed", 5, 7, "Golfers"): 6,
        ("Completed", 6, 4, "Ranked Golfers"): 0,
        ("Completed", 10, 22, "Ranked Golfers"): 0,
        ("Completed", 12, 1, "Golfers"): 1,
        ("Completed", 12, 13, "Golfers"): 6,
        ("Completed", 12, 22, "Ranked Golfers"): 9,
        ("Completed", 13, 10, "Scores Posted"): 7,
        ("Completed", 14, 3, "Ranked Golfers"): 0,
        ("Completed", 14, 16, "Ranked Golfers"): 9,
        ("Upcoming", 1, 1, "Golfers"): 8,
    }

    output = []
    sources = Counter()
    for row in rows:
        key = (row["Status"], row["Source Page"], row["Source Row"])
        source = detail[key]
        known_agrees = all(
            row[field] is None or int(source[field]) == row[field]
            for field in FIELDS
        )
        metric_sources = []
        for field in FIELDS:
            review_key = (*key, field)
            if row[field] is not None:
                metric_sources.append("full-page OCR")
            elif review_key in reviewed:
                row[field] = reviewed[review_key]
                metric_sources.append("visual review")
            elif field in contact.get(key, {}):
                row[field] = contact[key][field]
                metric_sources.append("row-context OCR")
            elif known_agrees:
                row[field] = int(source[field])
                metric_sources.append("corrected detail")
            else:
                row[field] = 0
                metric_sources.append("visual zero")
            sources[metric_sources[-1]] += 1
        output.append({
            **row,
            "Association": source["Association"].strip(),
            "Challenge Name": source["Challenge Name"].strip(),
            "Metric Source": " | ".join(metric_sources),
        })

    output.sort(key=lambda row: (
        ("Active", "Completed", "Upcoming").index(row["Status"]),
        row["Source Page"], row["Source Row"],
    ))

    bad = [row for row in output if row["Ranked Golfers"] > row["Golfers"]]
    if bad:
        raise ValueError(f"{len(bad)} rows have ranked golfers greater than golfers: {bad}")

    fields = [
        "Status", "Source Page", "Source Row", "Association", "Challenge Name",
        "OCR Name", "OCR Association", "Start Date", "End Date", "Golfers",
        "Ranked Golfers", "Scores Posted", "Metric Source",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    print(f"Wrote {len(output)} rows; reviewed {len(missing_rows)} OCR-incomplete rows")
    print("Metric evidence:", dict(sources))


if __name__ == "__main__":
    main()
