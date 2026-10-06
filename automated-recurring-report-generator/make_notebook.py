"""Rebuild the tutorial notebook from the shared, commented pipeline source.

This keeps notebook definitions and the unattended runner in sync. Rebuilding
clears outputs; execute the notebook again after intentionally changing code.
"""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parent
source = (ROOT / "report_pipeline.py").read_text(encoding="utf-8")
blocks = {}
for block in source.split("# %% ")[1:]:
    title, code = block.split("\n", 1)
    blocks[title.strip()] = code.strip()

cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s, tags=None):
    cell = nbf.v4.new_code_cell(s.strip())
    if tags:
        cell.metadata["tags"] = tags
    cells.append(cell)


md("""
# Automated Recurring Report Generator
## Project 2 - Full pipeline with PostgreSQL, Python and Gemini

**Business goal:** produce a complete recurring commerce report without manually
querying data, calculating metrics, taking chart screenshots or writing a summary.

This notebook continues from `data_loader.ipynb`. Your existing Olist database is
the source. There is no data download, table creation or data reload in this project.
Use your **global Python 3.12** interpreter throughout.

**Pipeline:** PostgreSQL snapshot → quality checks → current/previous-period KPIs
→ three charts → structured executive summary → date-named PDF → aggregate
exports and manifest → Windows Task Scheduler.

The implementation is included in the code cells below. `report_pipeline.py`
contains the same definitions for unattended execution; `run_report.py` is its
command-line entry point. Run cells from top to bottom with **Run All**.
""")
md("""
## 0. Project guide and execution plan

| Phase | What we build | Completion check |
|---|---|---|
| 0 | Global Python setup and private configuration | Python is 3.12; imports work |
| 1 | Explicit reporting dates | Current and prior calendar windows are printed |
| 2 | Read-only PostgreSQL extraction | One row per order; separate item grain |
| 3 | Data-quality gates | Key, money and independent GMV checks pass |
| 4 | Ten KPIs and chart datasets | Current, previous and change columns are visible |
| 5 | Three charts | Trend, category and state PNGs are displayed |
| 6 | Executive summary | Gemini or rule-based source is explicitly identified |
| 7 | PDF assembly | Report opens with KPI, summary, chart and methodology pages |
| 8 | Audit outputs | CSV/JSON exports and checksums are present |
| 9 | Recurring execution | CLI succeeds; a scheduler command is ready to use |

**Design decisions**

- Default to the latest completed **historical month**. Olist is a static dataset
  from 2016-2018; a report for this week's actual dates would be empty.
- Anchor historical replay to the latest *delivered-order purchase*, which avoids
  selecting the dataset's sparse canceled-order tail. This is a demo heuristic,
  not evidence of complete ingestion. `AS_OF` lets you choose a specific anchor.
- Treat periods as purchase-date cohorts using final snapshot outcomes. We cannot
  reconstruct what status/review was known on a historical date from this dataset.
- Never join raw items, payments and reviews together. Aggregate each by order
  first to avoid double-counting.
- Use Gemini only for interpretation; Python/SQL calculate the figures. A labelled
  deterministic summary keeps the report available if the API is unavailable.

Read `PROJECT_GUIDE.md` for the complete build plan, step-by-step execution,
metric dictionary, troubleshooting and portfolio demo checklist.
""")
md("""
## 0.1 Workspace and global Python environment

```text
Automated Recurring Report Generator/
├── .env                           # your existing private credentials
├── .env.example                   # safe configuration template
├── data_loader.ipynb               # your original loading notebook
├── automated_recurring_report_generator.ipynb  # this main notebook
├── report_pipeline.py              # same pipeline definitions for automation
├── run_report.py                   # command-line runner
├── make_notebook.py                # regenerate notebook after source changes
├── requirements.txt
├── README.md
├── PROJECT_GUIDE.md
├── EXECUTION_PLAN.md
├── schedule_report.ps1             # prepares/registers a weekly/monthly task
├── tests/test_pipeline.py
├── logs/report_pipeline.log
└── output/reports/<period>/<run>/   # PDF, charts, aggregates, evidence, manifest
```

Install dependencies into **global Python 3.12**, from PowerShell:

```powershell
python -m pip install -r requirements.txt
```

Select the global 3.12 interpreter as this notebook's kernel in VS Code/Jupyter.
If it is not listed, register it once:

```powershell
python -m ipykernel install --user --name global-python312 --display-name "Python 3.12 (global)"
```

No virtual environment is needed. Package installation and kernel registration
are one-time setup commands; the notebook does not reinstall dependencies on each run.
""")
code("# Cell 1 - Imports and project paths\n\n" + blocks["Imports and paths"] + "\n\nprint('Python:', sys.version.split()[0])\nprint('Interpreter:', sys.executable)\nprint('Project:', PROJECT_DIR)")
md("""
## 0.2 Private configuration

Use the same dotenv format as your loader:

```dotenv
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=YOUR_ACTUAL_PASSWORD
PGDATABASE=olist
GEMINI_API_KEY=YOUR_API_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
```

The implementation accepts `PGDATABASE` or the loader's documented alias
`OLIST_DB_NAME`. The actual `.env` is ignored by Git; credentials are never
printed, written into notebook cells or copied into reports. An existing process
environment takes precedence over the file. Restart the kernel after changing it.

**Report options**

- `FREQUENCY`: `monthly` or `weekly`.
- `REPORT_MODE`: `historical` for Olist replay; `calendar` for ongoing source data.
- `AS_OF`: `None` for automatic dates, or `date(2018, 8, 1)` to report July 2018.
  It is an **anchor date**, not the last included report date.
- `AI_MODE`: `auto` for Gemini with fallback; `off` for no API requests;
  `required` to fail when a Gemini summary cannot be generated.
- `MODEL`: a Gemini model available to your API account; `.env` `GEMINI_MODEL`
  overrides this value. API access is separate from consumer chat subscriptions.

In `auto` mode, the aggregate metrics and three chart images are sent to Gemini
when a key is configured. No customer IDs or review text are sent.
""")
code("# Cell 2 - Reporting configuration and date helpers\n\n" + blocks["Configuration and reporting periods"])
code("""
# Cell 3 - Choose the run settings (edit this cell)
FREQUENCY = "monthly"
REPORT_MODE = "historical"
AS_OF = None                  # Example: date(2018, 8, 1) reports July 2018.
AI_MODE = "off"               # Change to 'auto' to send aggregates/charts to Gemini.
MODEL = "gemini-3.5-flash-lite"
ENV_FILE = PROJECT_DIR / ".env"

cfg = ReportConfig(project_dir=PROJECT_DIR, frequency=FREQUENCY,
                   mode=REPORT_MODE, as_of=AS_OF, ai_mode=AI_MODE,
                   model=MODEL, env_file=ENV_FILE)
print('Frequency:', cfg.frequency, '| Mode:', cfg.mode, '| AI:', cfg.ai_mode)
print('Environment file found:', ENV_FILE.is_file())
""", ["configuration"])
md("""
# Phase 1 - Define the reporting periods

We compare the last completed calendar period with the immediately preceding one.
SQL includes the start timestamp and excludes the end timestamp. An order exactly
at midnight on the next month's first day belongs to the next month.

**Monthly example:** anchor 1 August 2018 → current 1-31 July; previous 1-30 June.
Months may have different day counts; totals are period totals, not daily-normalized growth.

**Weekly example:** anchor Wednesday 29 August → current Monday 20 August through
Sunday 26 August; previous Monday 13 August through Sunday 19 August.

The actual anchor is selected after reading the database coverage in Phase 2.
Dates in Olist remain source-local naive timestamps; we do not relabel Brazilian
purchase times as Indian purchase times. Generation timestamps use IST.
""")
code("""
# Cell 4 - Verify period logic with an explicit example
example_period = select_period(date(2018, 8, 1), cfg.frequency)
print('Example current period:', example_period.label)
print('Example previous period:', example_period.prior_label)
print('Exclusive end boundary:', example_period.end)
""")
md("""
# Phase 2 - Extract from the existing PostgreSQL database

The connection uses `postgresql+psycopg`, matching your loader. Required columns
are checked before queries run. All queries use one repeatable-read, read-only
transaction, so the extracted frames and reconciliation totals share a snapshot.

**Outputs**

- `orders`: one row per order, with independently aggregated item, payment and
  review values. Customer identity is kept in memory only for distinct counts.
- `items`: delivered items at `(order_id, order_item_id)` grain, with translated
  category names. The fallback for untranslated categories is the original name.
- `coverage`: source date range, latest delivered purchase, total/undated orders.
- `sql_totals`: independent delivered-item GMV sums for reconciliation.

Only `public` tables are read. `sellers` exists in your loader but is unnecessary
for these KPIs. Nothing is written to PostgreSQL.
""")
code("# Cell 5 - SQL queries and read-only extraction\n\n" + blocks["SQL extraction at the correct grain"])
code("""
# Cell 6 - Pull the current and previous cohorts
data = extract_data(cfg)
period = data['period']
print('Current:', period.label)
print('Previous:', period.prior_label)
print('Source first purchase:', data['coverage']['first_purchase'].date())
print('Source latest purchase:', data['coverage']['last_purchase'].date())
print('Latest delivered purchase:', data['coverage']['last_delivered_purchase'].date())
print('Source orders:', f"{data['coverage']['total_orders']:,}")
print('Extracted orders:', f"{len(data['orders']):,}")
print('Extracted delivered items:', f"{len(data['items']):,}")

# Show only a safe inspection sample; customer/order identifiers stay out of output.
from IPython.display import display, Image as NotebookImage, FileLink
display(data['orders'][['order_status', 'order_purchase_timestamp',
                        'item_count', 'merchandise_value', 'period']].head())
""")
md("""
# Phase 3 - Validate the data before calculating results

**Stop the report** for duplicate order/item keys, missing customer links,
missing statuses, delivered orders without items, invalid financial values or
GMV discrepancies. A report with incorrect financial totals must not look successful.

**Keep explicit warnings** for missing payments/delivery estimates, invalid delivery
dates, invalid review scores, incomplete date coverage and empty cohorts. Missing
review/delivery observations are excluded from those averages rather than treated
as zero. Undelivered orders can legitimately have no customer-delivery timestamp.

Reconciliation compares three independent paths: order-level item totals,
item-level totals and a separate SQL sum. The currency tolerance is BRL 0.01.
""")
code("# Cell 7 - Quality gates and reconciliation\n\n" + blocks["Data quality gates"])
code("""
# Cell 8 - Execute the validation gates
warnings = validate_data(data, cfg)
print('Key, financial and GMV checks: PASSED')
for warning in warnings:
    print('NOTE:', warning)
""")
md("""
# Phase 4 - Calculate current-period and comparison KPIs

| Metric | Definition / denominator |
|---|---|
| Purchased orders | All orders purchased in the period, regardless of final status |
| Delivered orders | Orders in that purchase cohort with final status `delivered` |
| Delivered merchandise GMV | Sum of delivered item prices; freight excluded |
| Delivered order AOV | Delivered merchandise GMV / delivered orders |
| Delivered payment total | Sum of payment values for delivered orders; separately reported |
| Purchasing customers | Distinct `customer_unique_id` across all purchased orders |
| Cancellation rate | `canceled` orders / all purchased orders × 100 |
| On-time delivery rate | Delivered orders on/before estimated calendar day / eligible delivered orders × 100 |
| Average delivery days | Mean elapsed days from purchase to customer delivery with valid dates |
| Mean order review score | Mean per-order average valid review score, on delivered orders |

**Reading changes:** `(current - previous) / previous × 100` for relative changes;
rate changes use **percentage points**. A zero baseline produces N/A instead of
infinity. No delivered orders means GMV/AOV are N/A; a genuine zero-price cohort
can still have zero GMV. GMV is not net revenue, refunds, marketplace income or profit.

Delivery/review KPIs describe the final observed cohort outcomes. A production
pipeline needs snapshot history or a fulfillment-date design to avoid hindsight.
""")
code("# Cell 9 - KPI functions and chart datasets\n\n" + blocks["KPI calculations and chart datasets"])
code("""
# Cell 10 - Build the numeric evidence
analysis = build_analysis(data)
display(analysis['kpis'][['label', 'current_display', 'previous_display', 'change_display']])
print('Eligible delivery orders:', analysis['current']['delivery_sample'])
print('Eligible on-time orders:', analysis['current']['on_time_sample'])
print('Reviewed delivered orders:', analysis['current']['review_sample'])
print('Delivered orders with payment:', analysis['current']['payment_sample'])
display(analysis['category_all'].head(8))
""")
md("""
# Phase 5 - Generate three reusable report charts

1. **Daily delivered GMV:** trend by purchase date within the current cohort.
2. **Top categories:** the largest eight categories by delivered merchandise GMV.
3. **Top customer states:** delivered GMV by buyer state, limited to eight states.

All values use BRL. Days with no observed delivered items are zero-filled for the
trend chart. Category/state bars are the top eight, not the full population.
Each run gets a separate folder so rerunning the notebook does not overwrite an
earlier report. PNGs are also used as visual context for Gemini and in the PDF.
""")
code("# Cell 11 - Output paths and chart generation\n\n" + blocks["Chart generation and run paths"])
code("""
# Cell 12 - Create and inspect the charts
run_dir = prepare_run(cfg, period)
charts = create_charts(analysis, period, run_dir)
print('Run folder:', run_dir)
for chart in charts:
    display(NotebookImage(filename=str(chart), width=900))
""")
md("""
# Phase 6 - Write the executive summary from evidence

Gemini receives the metric table, category changes, sample sizes, limitations and
all three charts. The prompt asks for a JSON structure containing a headline,
2-4 factual changes, a **hypothesis** about possible drivers, one recommended
action and an interpretation caveat. Python validates the response structure.

This implementation uses the installed `google-genai` SDK's `generate_content`
method, image parts and a JSON response schema. The model is configurable.
Transient 429/5xx errors receive at most two retries; other failures go straight
to fallback in `auto` mode. Individual requests have a 45-second timeout.

**Truthful fallback:** no API key, provider failure or empty reporting cohort
produces a deterministic, explicitly labelled summary. This proves the report
pipeline, but is not labelled as AI output. `required` mode makes provider failure
an error. Numeric evidence remains authoritative; schema validation does not
prove that an AI explanation is correct.

Official references:
[Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[image input](https://ai.google.dev/gemini-api/docs/image-understanding),
[current models](https://ai.google.dev/gemini-api/docs/models).
""")
code("# Cell 13 - Evidence payload, prompt, Gemini call and fallback\n\n" + blocks["Evidence-grounded executive summary"])
code(r"""
# Cell 14 - Generate and inspect the summary
summary = generate_summary(cfg, analysis, data, charts, warnings)
print('Summary source:', summary['source'])
if summary.get('model'):
    print('Model:', summary['model'])
if summary.get('fallback_reason'):
    print('Fallback reason:', summary['fallback_reason'])
print('\n' + summary['headline'])
for bullet in summary['what_changed']:
    print('-', bullet)
print('\nPossible explanation:', summary['possible_explanation'])
print('\nRecommended action:', summary['recommended_action'])
print('\nCaveat:', summary['caveat'])
""")
md("""
# Phase 7 - Assemble the date-named PDF

The report contains a KPI comparison page, an executive summary, the three
charts, and methodology/quality notes with coverage and sample sizes. Money is
formatted in BRL; page footers identify the period and replay mode.

Text from the database/model is escaped before PDF rendering. ReportLab writes
to a temporary filename, then renames it only after the document builds. This
prevents an interrupted write from exposing an incomplete final PDF.

Filename example:
`olist_monthly_2018-07-01_2018-07-31_generated_2026-10-06.pdf`.
The generation date and the historical reporting dates are separate.
""")
code("# Cell 15 - PDF layout and rendering\n\n" + blocks["PDF rendering"])
code("""
# Cell 16 - Build the finished report
pdf_path = build_pdf(cfg, data, analysis, summary, warnings, charts, run_dir)
print('PDF created:', pdf_path)
print('Size:', f'{pdf_path.stat().st_size / 1024:,.1f} KB')
display(FileLink(str(pdf_path.relative_to(PROJECT_DIR))))
""")
md("""
# Phase 8 - Export aggregate evidence and the run manifest

Each run folder contains:

- The PDF and three PNG charts.
- `kpis.csv`, `daily.csv`, `category_all.csv`, `states.csv` for numeric inspection.
- `evidence.json` for the exact aggregate model context and `summary.json` with
  its source/model/fallback reason.
- `manifest.json` with status, generation timestamp, dates, Python version,
  warnings and SHA-256 checksums for report files.

No raw customer/order identifiers, connection URLs or API keys are exported.
The success manifest is written last. Failed CLI runs log an exception class,
return a nonzero exit code and have no success manifest.
""")
code("# Cell 17 - Export helpers, logging and reusable orchestration\n\n" + blocks["Artifact export, logging and end-to-end orchestration"])
code("""
# Cell 18 - Finish the run and verify its artifacts
configure_logging(PROJECT_DIR)
manifest = save_artifacts(cfg, data, analysis, summary, warnings, pdf_path, run_dir)
assert manifest['status'] == 'success'
for relative_name, checksum in manifest['files'].items():
    artifact = run_dir / relative_name
    assert artifact.is_file(), f'Missing artifact: {relative_name}'
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == checksum
print('Artifacts verified:', len(manifest['files']))
print('Manifest:', run_dir / 'manifest.json')
""")
md(r"""
# Phase 9 - Execute unattended and prepare the schedule

The scheduled task should run the lightweight Python entry point, using the same
functions as the notebook. It does not need VS Code, Jupyter or a dashboard app.

From this project's PowerShell folder:

```powershell
python run_report.py --frequency monthly --mode historical --ai off
python run_report.py --frequency weekly --mode historical --ai auto
python run_report.py --frequency monthly --mode historical --as-of 2018-08-01 --ai required
```

The first command has no API cost. The last command requires a working Gemini
key/model and selects July 2018. Use `--mode calendar` only with ongoing ingestion;
otherwise current Olist calendar reports are correctly empty and flagged stale.

## 9.1 Windows Task Scheduler

Preview the task settings without registering anything:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_report.ps1 -Frequency monthly -Mode historical -Ai auto
```

Then register your chosen schedule explicitly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_report.ps1 -Frequency monthly -Mode historical -Ai auto -Register
```

The default is 09:00 local Windows time on the first day of each month; weekly
runs use Monday 09:00. This machine should use the India timezone for 09:00 IST.
The task uses the absolute global Python 3.12 executable and a project working
directory. It is configured to run while you are logged on, start after missed
triggers, and ignore overlapping instances. Configure logged-off execution in
Task Scheduler if needed; the guide explains the additional account setup.

Test the registered task and inspect status:

```powershell
Start-ScheduledTask -TaskName 'Olist-Recurring-Report-monthly'
Get-ScheduledTaskInfo -TaskName 'Olist-Recurring-Report-monthly'
```

See [Microsoft's Task Scheduler documentation](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create)
for schedule types. This notebook prepares the automation files; it does not
register a recurring task simply because you press Run All.
""")
code(r"""
# Cell 19 - Show the exact global interpreter command for your next run
import subprocess
command = [sys.executable, str(PROJECT_DIR / 'run_report.py'),
           '--frequency', cfg.frequency, '--mode', cfg.mode, '--ai', cfg.ai_mode]
if cfg.as_of:
    command.extend(['--as-of', cfg.as_of.isoformat()])
print(subprocess.list2cmdline(command))
print('Schedule preview: .\\schedule_report.ps1 -Frequency', cfg.frequency,
      '-Mode', cfg.mode, '-Ai', cfg.ai_mode)
""")
md("""
# Phase 10 - Acceptance checks and portfolio presentation

**Before calling the project complete**

1. Run this notebook with the global Python 3.12 kernel.
2. Confirm the printed period, GMV reconciliation and eligible sample sizes.
3. Open the generated PDF and inspect tables, chart labels and quality notes.
4. Confirm `summary_source` in the manifest: `gemini` or `rule_based`.
5. Run the CLI once with `--ai off`, then with `--ai required` if testing live AI.
6. Preview/register the schedule and test one scheduled execution.

Run the edge-case checks with:

```powershell
python -m unittest discover -s tests -v
```

**Suggested 60-90 second demo:** show the private configuration without exposing
values, trigger the CLI, show the PDF appear, open its KPI/summary/chart pages,
then show the task settings and manifest. State that Olist is a historical replay
and that an ongoing client deployment requires a fresh source feed.

**Extensions after the baseline:** introduce snapshot history, ingestion-watermark
checks, client branding, report retention and an approved delivery channel.
These are separate from this project's working PostgreSQL-to-report pipeline.
""")

notebook = nbf.v4.new_notebook(cells=cells)
notebook.metadata = {
    "kernelspec": {"display_name": "Python 3.12 (global)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12.10", "file_extension": ".py",
                      "mimetype": "text/x-python", "nbconvert_exporter": "python",
                      "pygments_lexer": "ipython3", "codemirror_mode": {"name": "ipython", "version": 3}},
}
nbf.validate(notebook)
target = ROOT / "automated_recurring_report_generator.ipynb"
nbf.write(notebook, target)
print(f'Created {target.name}: {len(cells)} cells')
