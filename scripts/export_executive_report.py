#!/usr/bin/env python3
import argparse
import contextlib
import http.server
import json
import os
import re
import socketserver
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "report-months.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def slug_month(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def load_manifest():
    with MANIFEST.open() as f:
        return json.load(f)


def save_manifest(data):
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")


def update_index():
    script = ROOT / "scripts" / "update_report_archive_index.py"
    if script.exists():
        subprocess.run(["python3", str(script)], check=True)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@contextlib.contextmanager
def local_server():
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield port
        finally:
            server.shutdown()
            thread.join(timeout=2)


def ensure_month(manifest, report_key):
    months = manifest.setdefault("months", {})
    if report_key in months:
        return months[report_key]
    raise SystemExit(f"Unknown report key: {report_key}. Add it to reports/report-months.json first.")


def export_pdf(report_key, output_path):
    with local_server() as port:
        url = f"http://127.0.0.1:{port}/reports/html-report/executive-report.html?report={report_key}"
        if output_path.exists():
            output_path.unlink()
        cmd = [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir=/private/tmp/gc-report-export-{report_key}",
            "--virtual-time-budget=5000",
            f"--print-to-pdf={output_path}",
            url,
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            proc.communicate(timeout=18)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise SystemExit("Chrome did not create the PDF export.")
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="Export a GC Membership executive report month to PDF.")
    parser.add_argument("--report", help="Report key, e.g. 2026-08. Defaults to manifest current.")
    parser.add_argument("--final", action="store_true", help="Mark the report month as final in the manifest.")
    args = parser.parse_args()

    manifest = load_manifest()
    report_key = args.report or manifest.get("current")
    if not report_key:
        raise SystemExit("No report key supplied and manifest has no current value.")

    month = ensure_month(manifest, report_key)
    report_month = month["reportMonth"]
    pdf_path = ROOT / month.get("pdfPath", f"reports/archive/{report_key}/gc-membership-executive-report-{slug_month(report_month)}.pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    copy_path = ROOT / month["copyPath"]
    if not copy_path.exists():
        raise SystemExit(f"Missing report copy file: {copy_path}")

    export_pdf(report_key, pdf_path)
    month["pdfPath"] = str(pdf_path.relative_to(ROOT))
    if args.final:
        month["status"] = "final"
    else:
        month.setdefault("status", "draft")
    save_manifest(manifest)
    update_index()
    print(f"Exported {report_key} to {pdf_path}")
    print(f"Status: {month['status']}")


if __name__ == "__main__":
    main()
