#!/usr/bin/env python3
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "report-months.json"
INDEX = ROOT / "reports" / "index.html"


def main():
    manifest = json.loads(MANIFEST.read_text())
    cards = []
    for key, month in sorted(manifest.get("months", {}).items(), reverse=True):
      report_month = html.escape(month["reportMonth"])
      report_date = html.escape(month["reportDate"])
      data_through = html.escape(month["dataThrough"])
      status = html.escape(month.get("status", "draft").title())
      html_path = "./" + str(Path(month["htmlPath"]).relative_to("reports"))
      pdf_path = "./" + str(Path(month["pdfPath"]).relative_to("reports"))
      cards.append(f"""
    <article class="card">
      <div>
        <h2>{report_month}</h2>
        <p class="meta">Report date: {report_date} · Data through: {data_through} · Status: {status}</p>
      </div>
      <div class="actions">
        <a class="primary" href="{html.escape(html_path)}">View Report</a>
        <a href="{html.escape(pdf_path)}">PDF</a>
      </div>
    </article>""")

    INDEX.write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GC Membership Reports Archive</title>
  <style>
    body {{ margin: 0; background: #eef3f8; color: #172235; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding: 34px 42px; background: #123a60; color: white; }}
    h1 {{ margin: 0; font-size: 34px; }}
    header p {{ margin: 8px 0 0; color: rgba(255,255,255,.76); }}
    main {{ display: grid; gap: 16px; max-width: 980px; margin: 28px auto; padding: 0 22px; }}
    .card {{ display: grid; grid-template-columns: 1fr auto; gap: 18px; align-items: center; padding: 22px; background: white; border: 1px solid #dce5ef; border-radius: 12px; box-shadow: 0 10px 30px rgba(18,58,96,.08); }}
    h2 {{ margin: 0; font-size: 22px; }}
    .meta {{ margin: 7px 0 0; color: #62728a; font-size: 14px; }}
    .actions {{ display: flex; gap: 10px; }}
    a {{ border: 1px solid #cfdbea; border-radius: 999px; padding: 10px 15px; color: #123a60; font-weight: 800; text-decoration: none; }}
    a.primary {{ background: #123a60; color: white; border-color: #123a60; }}
  </style>
</head>
<body>
  <header>
    <h1>GC Membership Reports Archive</h1>
    <p>Monthly executive reports generated from the dashboard reporting system.</p>
  </header>
  <main>{''.join(cards)}
  </main>
</body>
</html>
""")
    print(f"Updated {INDEX}")


if __name__ == "__main__":
    main()
