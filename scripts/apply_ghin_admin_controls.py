#!/usr/bin/env python3
"""Apply verified admin control totals to processed GHIN dashboard data."""

from __future__ import annotations

import json
import csv
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "ghin_challenges.json"
GROWTH = ROOT / "data" / "processed" / "ghin_challenges_growth.json"
COMPILED = ROOT / "data" / "processed" / "ghin_challenges_2026-08-24_compiled.csv"
AGA_MASTER = ROOT / "data" / "processed" / "aga_master.json"

CONTROLS = {
    "Active": {"challenges": 213, "golfers": 10266, "ranked": 3689, "scores": 35873},
    "Completed": {"challenges": 631, "golfers": 29667, "ranked": 10885, "scores": 91840},
    "Upcoming": {"challenges": 15, "golfers": 585, "ranked": 0, "scores": 0},
}


def metrics(status: str, values: dict[str, int]) -> dict:
    golfers = values["golfers"]
    return {
        "status": status,
        "activeChallenges": values["challenges"] if status == "Active" else 0,
        "completedChallenges": values["challenges"] if status == "Completed" else 0,
        "upcomingChallenges": values["challenges"] if status == "Upcoming" else 0,
        "totalChallenges": values["challenges"],
        "totalGolfers": golfers,
        "rankedGolfers": values["ranked"],
        "scoresPosted": values["scores"],
        "rankedGolferRate": values["ranked"] / golfers if golfers else 0,
        "scoresPerGolfer": values["scores"] / golfers if golfers else 0,
    }


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower().replace("…", " ")).strip()


def closest(value: str, choices: list[str]) -> str:
    target = normalized(value)
    if not target:
        return ""
    prefix = [choice for choice in choices if normalized(choice).startswith(target)]
    if prefix:
        return max(prefix, key=lambda choice: SequenceMatcher(None, target, normalized(choice)).ratio())
    return max(choices, key=lambda choice: SequenceMatcher(None, target, normalized(choice)).ratio())


def compiled_records() -> list[dict]:
    with COMPILED.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    names_by_status: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["Challenge Name"] not in names_by_status[row["Status"]]:
            names_by_status[row["Status"]].append(row["Challenge Name"])
    associations = json.loads(AGA_MASTER.read_text(encoding="utf-8"))
    records = []
    for row in rows:
        golfers = int(row["Golfers"])
        ranked = int(row["Ranked Golfers"])
        scores = int(row["Scores Posted"])
        name = closest(row["OCR Name"] or row["Challenge Name"], names_by_status[row["Status"]])
        aga = closest(row["OCR Association"] or row["Association"], associations)
        records.append({
            "name": name,
            "aga": aga,
            "status": row["Status"],
            "startDate": row["Start Date"] or None,
            "endDate": row["End Date"] or None,
            "golfers": golfers,
            "rankedGolfers": ranked,
            "scoresPosted": scores,
            "rankedGolferRate": ranked / golfers if golfers else None,
            "scoresPerGolfer": scores / golfers if golfers else None,
        })
    return records


def row_summary(records: list[dict]) -> dict:
    return {
        "activeChallenges": sum(row["status"] == "Active" for row in records),
        "completedChallenges": sum(row["status"] == "Completed" for row in records),
        "upcomingChallenges": sum(row["status"] == "Upcoming" for row in records),
        "totalChallenges": len(records),
        "totalGolfers": sum(row["golfers"] for row in records),
        "rankedGolfers": sum(row["rankedGolfers"] for row in records),
        "scoresPosted": sum(row["scoresPosted"] for row in records),
    }


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    records = compiled_records()
    totals = {key: sum(row[key] for row in CONTROLS.values()) for key in ("challenges", "golfers", "ranked", "scores")}
    data["metadata"]["generatedAt"] = datetime.now(timezone.utc).isoformat()
    data["metadata"]["sources"] = [
        {"file": "ghin_challenges_2026-08-24_detail_names_corrected.csv", "role": "complete challenge names"},
        {"file": "admin screenshots (35 pages)", "role": "verified status totals and row metrics"},
        {"file": "ghin_challenges_2026-08-24_compiled.csv", "role": "auditable compiled detail"},
    ]
    data["summary"] = {
        "activeChallenges": CONTROLS["Active"]["challenges"],
        "completedChallenges": CONTROLS["Completed"]["challenges"],
        "upcomingChallenges": CONTROLS["Upcoming"]["challenges"],
        "totalChallenges": totals["challenges"],
        "totalGolfers": totals["golfers"],
        "rankedGolfers": totals["ranked"],
        "scoresPosted": totals["scores"],
        "rankedGolferRate": totals["ranked"] / totals["golfers"],
        "scoresPerGolfer": totals["scores"] / totals["golfers"],
    }
    data["statusSummary"] = [metrics(status, CONTROLS[status]) for status in ("Active", "Completed", "Upcoming")]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        grouped[row["aga"]].append(row)
    aga_rows = []
    for aga, aga_records in grouped.items():
        summary = row_summary(aga_records)
        golfers = summary["totalGolfers"]
        summary.update({
            "aga": aga,
            "rankedGolferRate": summary["rankedGolfers"] / golfers if golfers else None,
            "scoresPerGolfer": summary["scoresPosted"] / golfers if golfers else None,
        })
        aga_rows.append(summary)
    data["topAgasByGolfers"] = sorted(aga_rows, key=lambda row: (-row["totalGolfers"], row["aga"]))[:10]
    data["topChallengesByGolfers"] = sorted(records, key=lambda row: (-row["golfers"], row["name"]))[:10]
    data["topChallengesByScoresPosted"] = sorted(records, key=lambda row: (-row["scoresPosted"], row["name"]))[:10]
    data["challenges"] = records
    DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    growth = json.loads(GROWTH.read_text(encoding="utf-8"))
    current = next(row for row in growth if row["date"] == "2026-08-24")
    current.update({
        "totalChallenges": totals["challenges"],
        "totalGolfers": totals["golfers"],
        "rankedGolfers": totals["ranked"],
        "scoresPosted": totals["scores"],
    })
    GROWTH.write_text(json.dumps(growth, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["summary"], indent=2))


if __name__ == "__main__":
    main()
