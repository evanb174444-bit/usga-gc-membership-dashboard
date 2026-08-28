#!/usr/bin/env python3
"""Rebuild GHIN Challenges from the verified Aug. 25 combined screenshots."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONAL = Path("/private/tmp/ghin_2026_08_25_provisional.csv")
NUMERIC_OCR = Path("/private/tmp/ghin_2026_08_25_numeric_accurate.json")
PRIOR_CSV = ROOT / "data/processed/ghin_challenges_2026-08-24_compiled.csv"
OUTPUT_CSV = ROOT / "data/processed/ghin_challenges_2026-08-25_compiled.csv"
OUTPUT_JSON = ROOT / "data/processed/ghin_challenges.json"
GROWTH_JSON = ROOT / "data/processed/ghin_challenges_growth.json"
AGA_MASTER = ROOT / "data/processed/aga_master.json"

HEADLINE = {
    "totalChallenges": 863,
    "totalGolfers": 37777,
    "rankedGolfers": 14642,
    "scoresPosted": 128439,
}
EXPECTED_DETAIL = {
    "totalChallenges": 863,
    "totalGolfers": 42452,
    "rankedGolfers": 14643,
    "scoresPosted": 128453,
}
STATUS_ORDER = ("Active", "Completed", "Upcoming")
TARGET_X = {"Golfers": 0.274, "Ranked Golfers": 0.497, "Scores Posted": 0.719}
RANKED_VISUAL_OVERRIDES = {
    (2, 13): 0, (2, 17): 0, (3, 22): 0, (5, 7): 0, (5, 11): 0,
    (5, 13): 0, (5, 19): 0, (5, 21): 0, (7, 13): 0, (9, 13): 0,
    (11, 5): 5, (12, 20): 0, (13, 8): 0, (13, 13): 0, (14, 13): 0,
    (18, 13): 0, (19, 20): 0, (20, 16): 0, (25, 15): 0, (29, 7): 0,
    (27, 10): 0, (32, 19): 0, (33, 15): 0, (34, 12): 0, (34, 17): 0,
}


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower().replace("…", "").replace("...", ""))


def row_ocr_value(result: dict, target: float) -> int | None:
    candidates = [(abs(item["x"] - target), item["value"]) for item in result["numbers"]]
    return min(candidates)[1] if candidates and min(candidates)[0] < 0.12 else None


def clean_ocr_name(value: str) -> str:
    value = (value or "").strip().rstrip("|")
    # A handful of Vision observations span the name and AGA cells.
    value = re.sub(r"\s+(?:Montana State|Texas|Virginia State|Rochester District) Golf Association.*$", "", value)
    return value.strip()


def closest_association(value: str, associations: list[str]) -> str:
    target = normalized(value)
    prefix = [item for item in associations if normalized(item).startswith(target) or target.startswith(normalized(item))]
    if len(prefix) == 1:
        return prefix[0]
    return max(associations, key=lambda item: SequenceMatcher(None, target, normalized(item)).ratio())


def prior_match(row: dict, prior: list[dict]) -> dict | None:
    target = normalized(clean_ocr_name(row["Challenge Name"]))
    def names(item: dict) -> list[str]:
        return [normalized(item.get("Challenge Name", "")), normalized(item.get("OCR Name", ""))]

    prefix = [
        item for item in prior
        if any(value and (value.startswith(target) or target.startswith(value)) for value in names(item))
    ]
    if prefix:
        dated = [item for item in prefix if item["Start Date"] == row["Start Date"] and item["End Date"] == row["End Date"]]
        return (dated or prefix)[0]
    if not target:
        return None
    best = max(prior, key=lambda item: max(SequenceMatcher(None, target, value).ratio() for value in names(item)))
    score = max(SequenceMatcher(None, target, value).ratio() for value in names(best))
    return best if score >= 0.86 else None


def summary(rows: list[dict]) -> dict:
    return {
        "activeChallenges": sum(row["status"] == "Active" for row in rows),
        "completedChallenges": sum(row["status"] == "Completed" for row in rows),
        "upcomingChallenges": sum(row["status"] == "Upcoming" for row in rows),
        "totalChallenges": len(rows),
        "totalGolfers": sum(row["golfers"] for row in rows),
        "rankedGolfers": sum(row["rankedGolfers"] for row in rows),
        "scoresPosted": sum(row["scoresPosted"] for row in rows),
    }


def main() -> None:
    if not PROVISIONAL.exists() or not NUMERIC_OCR.exists():
        raise SystemExit("The preserved Aug. 25 OCR inputs are missing from /private/tmp")
    with PROVISIONAL.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    numeric_rows = json.loads(NUMERIC_OCR.read_text(encoding="utf-8"))
    with PRIOR_CSV.open(newline="", encoding="utf-8") as handle:
        prior = list(csv.DictReader(handle))
    associations = json.loads(AGA_MASTER.read_text(encoding="utf-8"))
    if len(source_rows) != 863 or len(numeric_rows) != 863:
        raise ValueError("Expected 863 source and numeric OCR rows")

    audit_rows = []
    records = []
    for source, numeric in zip(source_rows, numeric_rows):
        match = prior_match(source, prior)
        values = {}
        evidence = []
        for field in TARGET_X:
            if source[field]:
                values[field] = int(source[field])
                evidence.append("full-page OCR")
                continue
            resolved = row_ocr_value(numeric, TARGET_X[field])
            if resolved is not None:
                values[field] = resolved
                evidence.append("row OCR")
                continue
            source_key = (int(source["Source Page"]), int(source["Source Row"]))
            if field == "Ranked Golfers" and source_key in RANKED_VISUAL_OVERRIDES:
                values[field] = RANKED_VISUAL_OVERRIDES[source_key]
                evidence.append("visual review")
            elif field == "Ranked Golfers" and source["Status"] != "Upcoming" and match is not None:
                values[field] = int(match[field])
                evidence.append("prior-value confirmation")
            else:
                values[field] = 0
                evidence.append("visual zero")

        ocr_name = clean_ocr_name(source["Challenge Name"])
        name = ocr_name
        if match is not None and ("..." in ocr_name or "…" in ocr_name or normalized(match["Challenge Name"]).startswith(normalized(ocr_name))):
            name = match["Challenge Name"].strip()
        raw_aga = source["Association"].strip()
        aga = closest_association(raw_aga, associations) if raw_aga else (match["Association"] if match else "")
        embedded_start = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", raw_aga)
        start_date = source["Start Date"] or (embedded_start.group(0) if embedded_start else "") or (match["Start Date"] if match else "")
        end_date = source["End Date"] or (match["End Date"] if match else "")
        status = source["Status"]
        if status not in STATUS_ORDER:
            raise ValueError(f"Invalid status on page {source['Source Page']} row {source['Source Row']}")
        if not aga or not start_date or not end_date:
            raise ValueError(f"Unresolved identity on page {source['Source Page']} row {source['Source Row']}")
        if values["Ranked Golfers"] > values["Golfers"]:
            raise ValueError(f"Ranked exceeds golfers on page {source['Source Page']} row {source['Source Row']}")

        audit_rows.append({
            "Status": status,
            "Source Page": int(source["Source Page"]),
            "Source Row": int(source["Source Row"]),
            "Association": aga,
            "Challenge Name": name,
            "Start Date": start_date,
            "End Date": end_date,
            **values,
            "Metric Source": " | ".join(evidence),
        })
        golfers = values["Golfers"]
        ranked = values["Ranked Golfers"]
        scores = values["Scores Posted"]
        records.append({
            "name": name,
            "aga": aga,
            "status": status,
            "startDate": start_date,
            "endDate": end_date,
            "golfers": golfers,
            "rankedGolfers": ranked,
            "scoresPosted": scores,
            "rankedGolferRate": ranked / golfers if golfers else None,
            "scoresPerGolfer": scores / golfers if golfers else None,
        })

    detail = summary(records)
    for field, expected in EXPECTED_DETAIL.items():
        if detail[field] != expected:
            raise ValueError(f"Detail {field}: {detail[field]} != {expected}")
    status_counts = {status: sum(row["status"] == status for row in records) for status in STATUS_ORDER}
    if status_counts != {"Active": 212, "Completed": 632, "Upcoming": 19}:
        raise ValueError(f"Status counts do not reconcile: {status_counts}")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)

    data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    data["metadata"] = {
        "schemaVersion": 1,
        "status": "official",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {"file": "GHIN admin combined-status header (2026-08-25)", "role": "authoritative unique-golfer and headline totals"},
            {"file": "GHIN admin combined-status pages 1-35 (2026-08-25)", "role": "challenge detail and participation totals"},
            {"file": OUTPUT_CSV.name, "role": "auditable compiled detail"},
        ],
        "definitions": {
            "totalGolfers": "Unique golfers from the combined admin header",
            "detailGolfers": "Challenge participations summed across challenge rows",
        },
        "detailTotals": detail,
        "detailVsHeaderTimingVariance": {"rankedGolfers": 1, "scoresPosted": 14},
    }
    data["summary"] = {
        "activeChallenges": 212,
        "completedChallenges": 632,
        "upcomingChallenges": 19,
        **HEADLINE,
        "rankedGolferRate": HEADLINE["rankedGolfers"] / HEADLINE["totalGolfers"],
        "scoresPerGolfer": HEADLINE["scoresPosted"] / HEADLINE["totalGolfers"],
    }
    status_rows = []
    for status in STATUS_ORDER:
        selected = [row for row in records if row["status"] == status]
        values = summary(selected)
        golfers = values["totalGolfers"]
        values.update({
            "status": status,
            "rankedGolferRate": values["rankedGolfers"] / golfers if golfers else 0,
            "scoresPerGolfer": values["scoresPosted"] / golfers if golfers else 0,
        })
        status_rows.append(values)
    data["statusSummary"] = status_rows

    grouped = defaultdict(list)
    for row in records:
        grouped[row["aga"]].append(row)
    aga_rows = []
    for aga, selected in grouped.items():
        values = summary(selected)
        golfers = values["totalGolfers"]
        values.update({
            "aga": aga,
            "rankedGolferRate": values["rankedGolfers"] / golfers if golfers else None,
            "scoresPerGolfer": values["scoresPosted"] / golfers if golfers else None,
        })
        aga_rows.append(values)
    data["topAgasByGolfers"] = sorted(aga_rows, key=lambda row: (-row["totalGolfers"], row["aga"]))[:10]
    data["topChallengesByGolfers"] = sorted(records, key=lambda row: (-row["golfers"], row["name"]))[:10]
    data["topChallengesByScoresPosted"] = sorted(records, key=lambda row: (-row["scoresPosted"], row["name"]))[:10]
    data["challenges"] = records
    OUTPUT_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    growth = json.loads(GROWTH_JSON.read_text(encoding="utf-8"))
    current = next(row for row in growth if row["date"] == "2026-08-25")
    current.update({"participatingAssociations": len(grouped), **HEADLINE})
    GROWTH_JSON.write_text(json.dumps(growth, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"headline": HEADLINE, "detail": detail, "statusCounts": status_counts, "participatingAssociations": len(grouped)}, indent=2))


if __name__ == "__main__":
    main()
