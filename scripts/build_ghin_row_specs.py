#!/usr/bin/env python3
"""Build row-context crop specifications from full-page Vision OCR output."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from compile_ghin_screenshots import center, header_centers, page_number, read_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--completed-ocr", type=Path, required=True)
    parser.add_argument("--active-upcoming-ocr", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [(record, "Completed") for record in read_jsonl(args.completed_ocr)]
    records += [
        (record, "Upcoming" if Path(record["path"]).name == "Upcoming.png" else "Active")
        for record in read_jsonl(args.active_upcoming_ocr)
    ]
    specs = []
    for record, status in records:
        observations = record["observations"]
        headers = header_centers(observations)
        end_header_y = center(max(
            [observation for observation in observations if observation["text"] == "End Date"],
            key=lambda observation: observation["y"],
        ))[1]
        positions = sorted((
            center(observation)[1]
            for observation in observations
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", observation["text"].strip())
            and center(observation)[1] < end_header_y
            and abs(center(observation)[0] - headers["End Date"]) < 0.05
        ), reverse=True)
        page = page_number(record, status)
        specs += [
            {"path": record["path"], "status": status, "page": page, "row": row, "centerY": y}
            for row, y in enumerate(positions, 1)
        ]
    args.output.write_text(json.dumps(specs, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(specs)} row specifications")


if __name__ == "__main__":
    main()
