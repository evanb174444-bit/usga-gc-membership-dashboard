#!/usr/bin/env python3
"""Inventory major JavaScript datasets embedded in the dashboard HTML."""

from __future__ import annotations

import re
import sys
from pathlib import Path


DATASET_DECLARATION = re.compile(
    r"^[ \t]*const[ \t]+([A-Z][A-Z0-9_]*)[ \t]*=[ \t]*([\[{])",
    re.MULTILINE,
)


def is_dataset_name(name: str) -> bool:
    """Select dashboard data constants while excluding UI/config constants."""
    return name == "DATA" or "DATA" in name or "DRAFT" in name


def find_literal_end(source: str, start: int) -> int:
    """Return the position after a balanced array or object literal."""
    pairs = {"[": "]", "{": "}"}
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = start

    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue

        if block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue

        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if char in "'\"`":
            quote = char
            index += 1
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif char in "]}":
            if not stack or char != stack[-1]:
                raise ValueError(f"Unbalanced dataset literal near character {index}")
            stack.pop()
            if not stack:
                return index + 1
        index += 1

    raise ValueError("Dataset literal did not terminate before the end of the file")


def count_array_records(literal: str) -> int:
    """Count comma-separated elements at the top level of an array literal."""
    content = literal[1:-1]
    if not content.strip():
        return 0

    depth = 0
    records = 1
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = 0

    while index < len(content):
        char = content[index]
        following = content[index + 1] if index + 1 < len(content) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if char in "'\"`":
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth -= 1
        elif char == "," and depth == 0:
            records += 1
        index += 1

    return records


def inventory(html_path: Path) -> list[dict[str, object]]:
    source = html_path.read_text(encoding="utf-8")
    datasets: list[dict[str, object]] = []

    for match in DATASET_DECLARATION.finditer(source):
        name = match.group(1)
        if not is_dataset_name(name):
            continue

        literal_start = match.start(2)
        literal_end = find_literal_end(source, literal_start)
        literal = source[literal_start:literal_end]
        literal_type = "array" if literal[0] == "[" else "object"
        record_count = count_array_records(literal) if literal_type == "array" else 1
        starting_line = source.count("\n", 0, match.start()) + 1

        datasets.append(
            {
                "name": name,
                "line": starting_line,
                "records": record_count,
                "type": literal_type,
            }
        )

    return datasets


def print_summary(html_path: Path, datasets: list[dict[str, object]]) -> None:
    name_width = max([len("Dataset"), *(len(str(row["name"])) for row in datasets)])
    line_width = max([len("Start line"), *(len(str(row["line"])) for row in datasets)])
    count_width = max([len("Records"), *(len(f'{int(row["records"]):,}') for row in datasets)])

    print(f"Dashboard dataset inventory: {html_path}")
    print()
    print(
        f"{'Dataset':<{name_width}}  "
        f"{'Type':<6}  "
        f"{'Start line':>{line_width}}  "
        f"{'Records':>{count_width}}"
    )
    print(
        f"{'-' * name_width}  "
        f"{'-' * 6}  "
        f"{'-' * line_width}  "
        f"{'-' * count_width}"
    )
    for row in datasets:
        print(
            f"{str(row['name']):<{name_width}}  "
            f"{str(row['type']):<6}  "
            f"{int(row['line']):>{line_width}}  "
            f"{int(row['records']):>{count_width},}"
        )

    array_records = sum(
        int(row["records"]) for row in datasets if row["type"] == "array"
    )
    print()
    print(
        f"Found {len(datasets)} major embedded datasets "
        f"containing {array_records:,} top-level array records."
    )
    object_count = sum(1 for row in datasets if row["type"] == "object")
    if object_count:
        print(
            f"Object datasets are reported as one top-level record each "
            f"({object_count} object dataset{'s' if object_count != 1 else ''})."
        )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    html_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else project_root / "index.html"

    if not html_path.is_file():
        print(f"Error: dashboard file not found: {html_path}", file=sys.stderr)
        return 1

    try:
        datasets = inventory(html_path)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Error reading dashboard inventory: {error}", file=sys.stderr)
        return 1

    if not datasets:
        print(f"No major embedded datasets found in {html_path}")
        return 0

    print_summary(html_path, datasets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
