#!/usr/bin/env python3
"""Build normalized crop specifications for GHIN screenshot numeric cells."""

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

    records = []
    records.extend((record, "Completed") for record in read_jsonl(args.completed_ocr))
    records.extend(
        (record, "Upcoming" if Path(record["path"]).name == "Upcoming.png" else "Active")
        for record in read_jsonl(args.active_upcoming_ocr)
    )

    specs = []
    for record, status in records:
        observations = record["observations"]
        headers = header_centers(observations)
        end_header_y = center(max(
            [observation for observation in observations if observation["text"] == "End Date"],
            key=lambda observation: observation["y"],
        ))[1]
        row_positions = sorted((
            center(observation)[1]
            for observation in observations
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", observation["text"].strip())
            and center(observation)[1] < end_header_y
            and abs(center(observation)[0] - headers["End Date"]) < 0.05
        ), reverse=True)
        page = page_number(record, status)
        for row, y in enumerate(row_positions, 1):
            for field, header in (
                ("Golfers", "Golfers"),
                ("Ranked Golfers", "Ranked"),
                ("Scores Posted", "Scores"),
            ):
                specs.append({
                    "path": record["path"],
                    "status": status,
                    "page": page,
                    "row": row,
                    "field": field,
                    "centerX": headers[header],
                    "centerY": y,
                    # Keep the crop inside one table cell. Wider/taller crops can
                    # include a gridline or a digit from the adjacent row, which
                    # Vision may merge into values such as 31 -> 301.
                    "width": 0.040,
                    "height": 0.016,
                })
    args.output.write_text(json.dumps(specs, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(specs)} crop specifications")


if __name__ == "__main__":
    main()
