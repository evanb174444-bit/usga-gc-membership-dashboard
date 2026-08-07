# Executive Report HTML Prototype

This is a print-first HTML/CSS prototype for the GC Membership executive report.

## Local Preview

Serve the repo root, then open:

```sh
PORT=8000 ./scripts/serve_dashboard.sh
```

```text
http://127.0.0.1:8000/reports/html-report/executive-report.html
```

## Narrative Editor

Open:

```text
http://127.0.0.1:8000/reports/html-report/editor.html
```

This first test editor stores narrative changes in the browser's local storage.
It lets you edit commentary without touching HTML, CSS, JavaScript, JSON, or the PDF directly.

## Month-to-Month Workflow

The intended production workflow is:

1. Update the dashboard data for the month.
2. Open the editor.
3. Set the report key, for example `2026-08`.
4. Edit the report language and leadership commentary.
5. Preview the report in the right-hand pane.
6. Export the PDF.
7. Save both the approved PDF and a frozen HTML/copy snapshot into an archive folder.

Suggested archive structure:

```text
reports/archive/
  2026-08/
    executive-report.html
    report-copy.json
    gc-membership-executive-report-august-2026.pdf
  2026-09/
    executive-report.html
    report-copy.json
    gc-membership-executive-report-september-2026.pdf
```

The current editor is a browser-storage prototype. The next step is to add an export/save script that writes the approved monthly copy to `report-copy.json`, exports the PDF, and updates an online report archive index for GitHub Pages.

## Create a New Report Month

Create the next month by seeding it from the prior month:

```sh
python3 scripts/create_report_month.py 2026-09 --current
```

This creates:

```text
reports/archive/2026-09/report-copy.json
reports/archive/2026-09/executive-report.html
```

It also updates `reports/report-months.json`.

## Export / Archive PDF

Export a report month to its archive folder:

```sh
python3 scripts/export_executive_report.py --report 2026-08
```

Mark it final when approved:

```sh
python3 scripts/export_executive_report.py --report 2026-08 --final
```

The export script updates `reports/index.html` so GitHub Pages can show the report archive.

## Import Edited Copy from the Browser Editor

The editor has a **Download Copy JSON** button. After downloading the edited copy, import it into the archive folder:

```sh
python3 scripts/import_report_copy.py --report 2026-08 --file ~/Downloads/2026-08-report-copy.json
```

Then export the PDF again:

```sh
python3 scripts/export_executive_report.py --report 2026-08
```

## QA Before Publishing

Run:

```sh
python3 scripts/qa_report_archive.py
```

This checks:

- the report month manifest
- archive copy JSON files
- archive HTML/PDF paths
- PDF page count
- archive index presence

## Export Concept

Use Chrome/Chromium print-to-PDF once the layout is approved:

```sh
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless=new \
  --disable-gpu \
  --print-to-pdf=reports/html-report/output/gc-membership-executive-report.pdf \
  http://127.0.0.1:8000/reports/html-report/executive-report.html
```

The point of this route is to keep the final artifact as a polished PDF while using HTML/CSS as the fixed-page layout engine.
