#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "report-months.json"


def pdf_pages(path):
    candidates = [
        Path("/Users/EvanBelfi/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdfinfo"),
        Path("/opt/homebrew/bin/pdfinfo"),
        Path("/usr/local/bin/pdfinfo"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                out = subprocess.check_output([str(candidate), str(path)], text=True)
                for line in out.splitlines():
                    if line.startswith("Pages:"):
                        return int(line.split(":", 1)[1].strip())
            except Exception:
                pass
    return None


def main():
    errors = []
    manifest = json.loads(MANIFEST.read_text())
    months = manifest.get("months", {})
    if not manifest.get("current"):
        errors.append("Manifest is missing current report key.")
    if manifest.get("current") not in months:
        errors.append("Manifest current report key is not listed in months.")

    for key, month in sorted(months.items()):
        for field in ["copyPath", "htmlPath", "pdfPath"]:
            path = ROOT / month[field]
            if not path.exists():
                errors.append(f"{key}: missing {field}: {path}")
        copy_path = ROOT / month["copyPath"]
        if copy_path.exists():
            try:
                json.loads(copy_path.read_text())
            except Exception as exc:
                errors.append(f"{key}: copy JSON is invalid: {exc}")
        pdf_path = ROOT / month["pdfPath"]
        if pdf_path.exists():
            pages = pdf_pages(pdf_path)
            if pages != 5:
                errors.append(f"{key}: expected 5 PDF pages, found {pages}")
            if pdf_path.stat().st_size < 100_000:
                errors.append(f"{key}: PDF looks too small: {pdf_path.stat().st_size} bytes")

    index = ROOT / "reports" / "index.html"
    if not index.exists():
        errors.append("Missing reports/index.html")
    else:
        html = index.read_text()
        for key, month in months.items():
            if Path(month["htmlPath"]).name not in html and key not in html:
                errors.append(f"{key}: archive index may not include report link.")

    if errors:
        print("Report archive QA failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("Report archive QA passed.")
    print(f"Current report: {manifest['current']}")
    print(f"Months checked: {', '.join(sorted(months))}")


if __name__ == "__main__":
    main()
