# Build plan and step-by-step execution

## Milestones and dependencies

| Milestone | Inputs | Work | Reviewable result |
|---|---|---|---|
| 1. Environment | Global Python 3.12, existing loader/.env | Verify interpreter, imports and credentials | Kernel path and successful read-only connection |
| 2. Reporting contract | Olist schema and historical dates | Define grain, periods, currency and metric denominators | Documented KPI dictionary and printed windows |
| 3. Extraction | Milestones 1-2 | Query coverage, order facts and delivered items in one snapshot | Safe sample and current/prior row counts |
| 4. Validation | Extracted frames and independent SQL sums | Gate duplicates, linkage, invalid money and GMV fanout | Passing reconciliation and explicit quality warnings |
| 5. Analysis | Validated cohorts | Calculate ten KPIs and period changes | Numeric comparison table and sample sizes |
| 6. Visuals | Analysis frames | Draw trend/category/state charts | Three labelled PNGs |
| 7. Interpretation | Aggregate evidence and charts | Generate/validate Gemini JSON or labelled fallback | Structured summary and source provenance |
| 8. Packaging | KPIs, visuals, summary, limitations | Assemble PDF and export CSV/JSON/checksums | Complete dated run folder |
| 9. Recurrence | Successful standalone runner | Preview/register/test Windows task | Repeated execution with manifest and exit status |
| 10. Portfolio | Reviewed output and actual validation | Capture short demo and publish safe files | Evidence of the end-to-end automation |

The first eight milestones are implemented in the main notebook. The standalone
runner is also implemented. Schedule registration is an explicit final local
setup action: a prepared script is different from an installed/tested task.

## Execution sequence

### Step 1 - Open the workspace and confirm Python

```powershell
python --version
python -m pip install -r requirements.txt
```

Select global Python 3.12 in the notebook kernel picker. No virtual environment.
Do not reload the database: `data_loader.ipynb` has already completed that stage.

### Step 2 - Check `.env` and choose settings

Keep the existing PostgreSQL settings. Add/change `GEMINI_MODEL` only if needed.
Open the main notebook's configuration cell and initially use `monthly`,
`historical`, `AS_OF=None`, `AI_MODE='off'`. This first run checks the data/report
pipeline without an API dependency. The provided final notebook may already
have outputs; Run All performs a fresh run.

### Step 3 - Run through extraction and quality

Run cells through Phase 3. Check the selected dates, source coverage and row
counts. Confirm the key/financial/GMV checks pass and read delivery/coverage
warnings. Resolve a failing financial gate before proceeding.

### Step 4 - Review KPIs and charts

Run Phases 4-5. Confirm BRL currency, delivered-cohort AOV, customer_unique_id
counting and percentage-point changes for rates. Inspect all three charts.
Compare a GMV figure with `sql_totals` when learning how reconciliation works.

### Step 5 - Test the summary modes

Run Phase 6 with AI off; verify the source says `rule_based`. Then use `auto`
with the configured Gemini key and rerun the summary/PDF/export phases. For an
explicit live-provider check, use `required` in the CLI. Read the actual source
and fallback reason; a successful PDF is not by itself proof of a successful API call.

### Step 6 - Finish and visually inspect the output

Run Phases 7-8. Open the PDF and inspect every page. Verify the manifest status
and checksums; review `kpis.csv`, `summary.json` and `evidence.json` as supporting
evidence. The PDF documents historical hindsight and data-quality exclusions.

### Step 7 - Prove unattended execution

```powershell
python run_report.py --frequency monthly --mode historical --ai off
python run_report.py --frequency weekly --mode historical --ai auto
python -m unittest discover -s tests -v
```

The CLI should finish without Jupyter running. Confirm the report folder and
manifest, and verify errors return a nonzero process exit status.

### Step 8 - Preview, register and test recurrence

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_report.ps1 -Frequency monthly -Mode historical -Ai auto
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_report.ps1 -Frequency monthly -Mode historical -Ai auto -Register
Start-ScheduledTask -TaskName 'Olist-Recurring-Report-monthly'
Get-ScheduledTaskInfo -TaskName 'Olist-Recurring-Report-monthly'
```

Check the interpreter and project paths before registration. Default triggers
use local Windows time, day 1 or Monday at 09:00. Confirm that the scheduled
run adds a new success manifest and LastTaskResult is 0. See the guide for
logged-off operation and handling an existing task name.

### Step 9 - Build the portfolio demonstration

Show the command, the arriving PDF, the metric comparison, summary source,
three chart page and scheduler settings. Explicitly say historical Olist replay.
Use a separate ingestion project/source to demonstrate fresh weekly data later.

## Acceptance criteria

- Global Python 3.12 is used by the notebook and command-line runner.
- The loading notebook is preserved and PostgreSQL access is read-only.
- Current and prior periods have explicit, documented boundaries.
- Order/item/payment/review joins cannot silently multiply reported GMV.
- Key/financial gates and independent GMV reconciliation pass.
- Ten metrics, sample sizes and three charts appear in the report.
- Narrative provenance distinguishes Gemini from deterministic fallback.
- The PDF and aggregate evidence are date-named, inspectable and accompanied by checksums.
- The CLI executes successfully without an open notebook.
- Recurrence is ready to register; completion of installed scheduling requires a tested task run.

See `VALIDATION.md` for the subset verified live on this machine and any remaining
provider/scheduler limitations. Do not claim unperformed acceptance checks.
