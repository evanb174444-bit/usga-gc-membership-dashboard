#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "report-months.json"


def main():
    parser = argparse.ArgumentParser(description="Import downloaded editor copy JSON into a report month archive.")
    parser.add_argument("--report", required=True, help="Report key, e.g. 2026-08")
    parser.add_argument("--file", required=True, help="Downloaded copy JSON from the editor")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    month = manifest.get("months", {}).get(args.report)
    if not month:
        raise SystemExit(f"Unknown report key: {args.report}")

    src = Path(args.file).expanduser()
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.exists():
        raise SystemExit(f"Copy file not found: {src}")

    data = json.loads(src.read_text())
    dest = ROOT / month["copyPath"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Imported {src} -> {dest}")


if __name__ == "__main__":
    main()
