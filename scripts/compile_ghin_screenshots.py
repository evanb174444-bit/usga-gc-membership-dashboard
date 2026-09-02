#!/usr/bin/env python3
"""Compile screenshot-recognized GHIN Challenge cells into an auditable CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


STATUS_PAGES = {"Active": 9, "Completed": 26, "Upcoming": 1}


def center(observation: dict) -> tuple[float, float]:
    return (
        observation["x"] + observation["width"] / 2,
        observation["y"] + observation["height"] / 2,
    )


def page_number(record: dict, status: str) -> int:
    expected_pages = STATUS_PAGES[status]
    for observation in record["observations"]:
        match = re.search(rf"(\d+)\s+of\s+{expected_pages}\s+pages", observation["text"])
        if match:
            return int(match.group(1))
    if status == "Upcoming":
        return 1
    raise ValueError(f"Page number not recognized in {record['path']}")


def header_centers(observations: list[dict]) -> dict[str, float]:
    headers = {}
    for label in ("Start Date", "End Date", "Status", "Golfers", "Ranked", "Scores"):
        candidates = [o for o in observations if o["text"] == label]
        if candidates:
            headers[label] = center(max(candidates, key=lambda o: o["y"]))[0]
    required = {"Start Date", "End Date", "Status", "Golfers", "Ranked", "Scores"}
    if set(headers) != required:
        raise ValueError(f"Missing headers: {sorted(required - set(headers))}")
    return headers


def closest_text(observations: list[dict], target_x: float, target_y: float, pattern: str) -> str:
    candidates = []
    for observation in observations:
        text = observation["text"].strip()
        x, y = center(observation)
        if abs(y - target_y) <= 0.012 and re.fullmatch(pattern, text):
            candidates.append((abs(x - target_x), text))
    if not candidates or min(candidates)[0] > 0.04:
        raise ValueError(f"Cell not recognized near x={target_x:.3f}, y={target_y:.3f}")
    return min(candidates)[1]


def closest_number(observations: list[dict], target_x: float, target_y: float) -> int | None:
    try:
        return int(closest_text(observations, target_x, target_y, r"\d+"))
    except ValueError:
        return None


def closest_date(observations: list[dict], target_x: float, target_y: float) -> str | None:
    try:
        return closest_text(observations, target_x, target_y, r"\d{4}-\d{2}-\d{2}")
    except ValueError:
        return None


def row_text(observations: list[dict], target_y: float, minimum_x: float, maximum_x: float) -> str | None:
    candidates = []
    for observation in observations:
        text = observation["text"].strip()
        x, y = center(observation)
        if abs(y - target_y) <= 0.014 and minimum_x <= observation["x"] < maximum_x:
            if text not in {"Active", "Completed", "Upcoming"} \
                    and not re.fullmatch(r"\d+|\d{4}-\d{2}-\d{2}", text):
                candidates.append((observation["x"], text))
    return min(candidates)[1] if candidates else None


def parse_record(record: dict, status: str) -> tuple[int, list[dict]]:
    observations = record["observations"]
    headers = header_centers(observations)
    row_positions = []
    for observation in observations:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observation["text"].strip()):
            continue
        x, y = center(observation)
        if y < center(max([o for o in observations if o["text"] == "End Date"], key=lambda o: o["y"]))[1] \
                and abs(x - headers["End Date"]) < 0.05:
            row_positions.append(y)
    row_positions.sort(reverse=True)

    page = page_number(record, status)
    expected_rows = 25
    if status == "Completed" and page == 26:
        expected_rows = 6
    elif status == "Active" and page == 9:
        expected_rows = 13
    elif status == "Upcoming":
        expected_rows = 15
    if len(row_positions) != expected_rows:
        raise ValueError(
            f"{record['path']} page {page}: recognized {len(row_positions)} row positions; expected {expected_rows}"
        )

    rows = []
    for row_index, y in enumerate(row_positions, 1):
        try:
            rows.append({
                "Status": status,
                "Source Page": page_number(record, status),
                "Source Row": row_index,
                "OCR Name": row_text(observations, y, 0.12, 0.39),
                "OCR Association": row_text(observations, y, 0.34, 0.56),
                "Start Date": closest_date(observations, headers["Start Date"], y),
                "End Date": closest_date(observations, headers["End Date"], y),
                "Golfers": closest_number(observations, headers["Golfers"], y),
                "Ranked Golfers": closest_number(observations, headers["Ranked"], y),
                "Scores Posted": closest_number(observations, headers["Scores"], y),
            })
        except ValueError as error:
            raise ValueError(
                f"{record['path']} page {page_number(record, status)} row {row_index}: {error}"
            ) from error
    return page_number(record, status), rows


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--completed-ocr", type=Path, required=True)
    parser.add_argument("--active-upcoming-ocr", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    parsed_rows = []
    seen_pages = {status: set() for status in STATUS_PAGES}
    for record in read_jsonl(args.completed_ocr):
        page, rows = parse_record(record, "Completed")
        seen_pages["Completed"].add(page)
        parsed_rows.extend(rows)
    for record in read_jsonl(args.active_upcoming_ocr):
        status = "Upcoming" if Path(record["path"]).name == "Upcoming.png" else "Active"
        page, rows = parse_record(record, status)
        seen_pages[status].add(page)
        parsed_rows.extend(rows)

    for status, page_count in STATUS_PAGES.items():
        expected = set(range(1, page_count + 1))
        if seen_pages[status] != expected:
            raise ValueError(f"{status} page coverage mismatch: {sorted(seen_pages[status])}")

    with args.detail.open(newline="", encoding="utf-8-sig") as source:
        detail_rows = list(csv.DictReader(source))
    detail_by_key = {
        (row["Status"], int(row["Source Page"]), int(row["Source Row"])): row
        for row in detail_rows
    }

    output_rows = []
    for parsed in parsed_rows:
        key = (parsed["Status"], parsed["Source Page"], parsed["Source Row"])
        if key not in detail_by_key:
            raise ValueError(f"No detail row for {key}")
        source = detail_by_key[key]
        for field in ("Golfers", "Ranked Golfers", "Scores Posted"):
            if parsed[field] is None:
                parsed[field] = int(source[field])
                parsed.setdefault("Fallback Fields", []).append(field)
        fallback_fields = parsed.pop("Fallback Fields", [])
        output_rows.append({
            **parsed,
            "Association": source["Association"].strip(),
            "Challenge Name": source["Challenge Name"].strip(),
            "Metric Source": "admin screenshot" if not fallback_fields else (
                "admin screenshot; source fallback: " + ", ".join(fallback_fields)
            ),
        })

    output_rows.sort(key=lambda row: (
        ("Active", "Completed", "Upcoming").index(row["Status"]),
        row["Source Page"],
        row["Source Row"],
    ))
    fields = [
        "Status", "Source Page", "Source Row", "Association", "Challenge Name",
        "OCR Name", "OCR Association", "Start Date", "End Date", "Golfers", "Ranked Golfers", "Scores Posted", "Metric Source",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
