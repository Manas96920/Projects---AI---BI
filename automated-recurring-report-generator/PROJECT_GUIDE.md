# Project guide: Automated Recurring Report Generator

## 1. The business problem and finished deliverable

An ecommerce analyst normally repeats a sequence of tasks: query the previous
period, calculate comparisons, draw charts, explain the results and format a
report. This project automates that sequence from an existing PostgreSQL source
to a dated PDF in a local folder. Windows Task Scheduler provides recurrence.

The finished report includes ten KPIs, three charts, a structured executive
summary and methodology/quality notes. Its run folder also contains aggregate
CSV files, the exact AI evidence payload, summary provenance and file checksums.
There is no Power BI/Tableau dependency, browser service or Node.js scheduler.

The main deliverable is `automated_recurring_report_generator.ipynb`: full code,
phase headings, numbered code cells, purpose/definition explanations and visible
intermediate results. `report_pipeline.py` mirrors its function definitions;
`run_report.py` runs them unattended. `data_loader.ipynb` is the prerequisite,
not something to rerun every week.

## 2. Scope and architectural decisions

| Layer | Implementation | Why |
|---|---|---|
| Source | Existing `olist` database, `public` schema | Reuse the loaded dataset |
| Extraction | SQLAlchemy + psycopg, parameterized SQL | Match the loader connection and safely bind dates |
| Consistency | Read-only repeatable-read transaction | Use one snapshot for all query totals |
| Grain | Order facts + separate delivered items | Avoid multiplying one-to-many joins |
| Analysis | pandas/NumPy | Explicit KPI definitions and edge-case handling |
| Visuals | Matplotlib, three PNG charts | Exportable visuals without a dashboard |
| Interpretation | Gemini with a JSON schema and image parts | Structured narrative based on calculated evidence |
| Availability | Labelled rule-based fallback | Reports continue without pretending fallback is AI |
| Packaging | ReportLab PDF | Shareable, date-named output |
| Audit | Aggregate CSV/JSON and SHA-256 manifest | Inspect and reproduce numeric evidence |
| Scheduling | Windows Task Scheduler | Use the user's existing Windows environment |

PDF is the baseline output format. Excel export, synthetic ongoing ingestion,
email delivery and a web UI are optional future extensions, not dependencies of
the working pipeline.

## 3. Prerequisites: global Python 3.12 and the existing loader

1. Open PowerShell in this project folder.
2. Confirm the interpreter:

   ```powershell
   python --version
   python -c "import sys; print(sys.executable)"
   ```

The `python` commands below assume that your global Python 3.12 executable is on PATH. If `python --version` is not 3.12, select the correct interpreter or invoke its full path with PowerShell's `&` operator. Confirm the executable with `python -c "import sys; print(sys.executable)"` before installing packages.

3. Install the project dependencies into that global interpreter:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. In VS Code/Jupyter, select the global Python 3.12 kernel. The pipeline checks
   the major/minor version and stops if the kernel is 3.10 or another version.
   If needed, register the global kernel once:

   ```powershell
   python -m ipykernel install --user --name global-python312 --display-name "Python 3.12 (global)"
   ```

5. PostgreSQL must be running and the Olist tables must already be populated.
   The reporting notebook never creates/replaces tables or reloads CSVs.

Required source tables are `orders`, `customers`, `order_items`, `order_payments`,
`order_reviews`, `products` and `product_category_name_translation`. `sellers`
from the loader is not needed for this report. Extra tables are ignored.

## 4. Private configuration

Use the existing `.env` in this folder, following dotenv syntax:

```dotenv
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=YOUR_ACTUAL_POSTGRES_PASSWORD
PGDATABASE=olist
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
```

The supplied `.env.example` is a template. Do not overwrite a working `.env`
with placeholders. `OLIST_DB_NAME` is accepted if `PGDATABASE` is absent. Model
selection is optional and depends on what your API account can access.
Environment variables already set in the process override the file. Restart
the notebook kernel/terminal after changing stale values.

The password/API key is never printed. Driver URLs and raw provider errors are
not written into logs because they can reveal credentials. `.env`, output
folders and logs are excluded by `.gitignore`. Before publishing an executed
notebook, also review its outputs and source labels for client-specific data.

Gemini API calls can incur charges under the account's API plan. `--ai off`
does not call the provider. The consumer chat subscription is separate from API
access; no plan-specific price/free-tier claims are required by this project.

## 5. Choose dates correctly for Olist

### Historical replay: the default

Olist contains 2016-2018 data. A current calendar report would contain no recent
orders. Historical mode anchors to the latest purchase timestamp of a delivered
order and reports the last completed calendar period before that date. This
avoids choosing the sparse late order tail as a supposedly representative month.

For the verified database, the default monthly comparison is **July 2018 versus
June 2018**. A late-August anchor selects July because August is not yet complete.
This is a replay heuristic, not a completeness guarantee; ingestion-watermark
tracking is an extension for a real continuously updated source.

An explicit anchor overrides automatic selection:

```powershell
python run_report.py --frequency monthly --as-of 2018-08-01 --ai off
```

This reports July, not August. Weeks are Monday through Sunday, and the same
anchor reports the last completed Monday-Sunday week. SQL uses `[start, end)`.
Adjacent monthly comparisons may have different numbers of days; growth is
reported on period totals, not normalized daily totals.

Historical KPIs use **final dataset status, payment and review observations**.
Olist does not provide a full event history that reconstructs everything known
at each reporting cutoff. The notebook and PDF explicitly disclose that
hindsight. A production implementation should use historical snapshots or a
fulfillment-date design depending on the client's reporting question.

### Calendar mode: ongoing ingestion

```powershell
python run_report.py --frequency weekly --mode calendar --ai off
```

The anchor uses today's date in Asia/Kolkata unless `--as-of` is supplied. Empty
periods retain order counts of zero but have unavailable GMV/AOV rather than
misleading zero revenue; comparisons and source freshness are flagged. Gemini
is not called for an empty current cohort. Olist remains static unless a separate
ingestion pipeline adds genuine or clearly labelled synthetic observations.

Olist purchase/delivery timestamps remain source-local naive values. Generation
timestamps use IST. Windows scheduled trigger times use the machine timezone.

## 6. Execute the notebook step by step

1. **Setup/configuration:** run imports; confirm Python 3.12 and the project path.
   Edit the configuration cell: frequency, mode, anchor, AI mode and model.
2. **Period logic:** inspect the explicit calendar example and half-open boundaries.
3. **Extraction:** read source coverage and both cohorts. Inspect the safe sample
   without displaying customer/order identifiers.
4. **Quality:** execute key/linkage/financial gates and three-way GMV reconciliation.
   Read warning messages; do not ignore incomplete coverage or denominator changes.
5. **KPIs:** inspect current/previous/change columns and delivery/review sample sizes.
6. **Charts:** create the unique run folder and display all three PNG images.
7. **Summary:** inspect the source, facts, explanation hypothesis, action and caveat.
8. **PDF:** generate and open the report using the notebook's file link.
9. **Exports:** verify the success manifest and every accompanying file checksum.
10. **Automation:** run the CLI, then preview and register your chosen schedule.

Run All performs steps 1-9; it shows the scheduling commands without registering
a task. Rerunning chart/report phases uses a new folder so earlier runs survive.
If a notebook cell fails before final export, fix the issue and rerun the affected
phase and dependent phases; the absence of `manifest.json` means that run is
not a completed pipeline run.

## 7. Metric dictionary and interpretation

| Metric | Calculation | Important scope |
|---|---|---|
| Purchased orders | Number of order rows | All final statuses, assigned by purchase date |
| Delivered orders | Count with `order_status='delivered'` | Final snapshot cohort outcomes |
| Delivered merchandise GMV | Sum of delivered-order item prices | BRL, freight excluded; not net revenue/profit |
| Delivered order AOV | GMV / delivered orders | Same numerator/denominator cohort |
| Delivered payment total | Sum of delivered-order payment values | Separate from item GMV; includes freight/adjustments |
| Purchasing customers | Distinct `customer_unique_id` | All statuses; not distinct `customer_id` |
| Cancellation rate | Canceled orders / purchased orders × 100 | `unavailable` is not counted as `canceled` |
| On-time rate | Valid delivered date ≤ estimated date / eligible delivered orders × 100 | Calendar-day comparison; excludes invalid/missing dates |
| Average delivery days | Mean `(delivered - purchased)` elapsed days | Valid delivered timestamps only |
| Mean order review score | Mean per-order average valid score | Delivered orders; valid scores 1-5 only |

Reviews are averaged within each order before averaging across delivered orders.
This avoids overweighting orders with multiple review records. Missing reviews
are excluded rather than assigned zero. Delivery/estimated timestamps are
compared by calendar date so evening delivery on the promised day is on time.

Relative change is `(current - previous) / previous × 100`, with N/A for a zero
baseline. Rates use percentage-point changes; a move from 90% to 95% is +5 pp.
Sample sizes identify how many delivered orders contribute to payment, delivery,
on-time and review metrics.

## 8. Data-quality policy

The pipeline fails on duplicate order/item keys, missing customer links/statuses,
delivered orders without items, negative/missing financial records or monetary
reconciliation failure. It validates columns against the loader schema first.
All SQL dates are bound parameters and all queries run in a read-only transaction.

Warnings cover incomplete source-date coverage, undated orders, invalid review
scores, absent delivered payments, invalid customer-delivery timestamps, missing
estimates and empty/stale calendar windows. Invalid delivery observations are
excluded from delivery denominators and explicitly counted in the warning.

Reconciliation independently sums delivered GMV at order grain, item grain and
in a third SQL query. The allowed absolute difference is BRL 0.01. This checks
the reported scope rather than assuming a successful query proves correct totals.

## 9. AI implementation and limitations

The model receives the aggregate KPI table, category movement, sample sizes,
quality caveats and three PNGs. No review messages/customer identifiers are sent.
The prompt prohibits causal certainty and unsupported concepts such as profit,
conversion rate and refunds. Source labels are explicitly treated as data.

The SDK's `generate_content` interface accepts image parts and a JSON schema;
local validation checks required strings and 2-4 change bullets. The model name
is configurable rather than embedded as an account requirement. The implementation
uses the installed SDK interface described in
[Google's structured-output documentation](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
and [image-input documentation](https://ai.google.dev/gemini-api/docs/image-understanding).
Choose an available model from [Google's model list](https://ai.google.dev/gemini-api/docs/models).

`auto` falls back on missing credentials, provider errors, malformed output or
empty data. `off` deliberately uses deterministic facts. `required` makes a
provider/configuration failure stop the run, while an empty period still produces
an explicitly labelled empty-data report. Provider 429/5xx errors get bounded
retries; individual request timeouts are 45 seconds.

The PDF and `summary.json` identify the actual source and model. JSON-schema
validation guarantees structure, not factual correctness. Numeric CSV/evidence
remains authoritative and generated explanatory hypotheses require human judgment.

## 10. Unattended runner and schedule

First prove the CLI works outside Jupyter:

```powershell
python run_report.py --frequency monthly --mode historical --ai off
python run_report.py --frequency weekly --mode historical --ai auto
```

Use `--env-file "C:\path\to\.env"` if the credentials live elsewhere.
Success prints the PDF and manifest paths. Failure returns exit code 1 and logs
the error class without emitting secret-bearing exception text. Individual SQL
statements have a 60-second timeout.

Preview the schedule:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_report.ps1 -Frequency monthly -Mode historical -Ai auto
```

Register explicitly when the preview is correct:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_report.ps1 -Frequency monthly -Mode historical -Ai auto -Register
```

Monthly triggers run on day 1 at 09:00; weekly triggers run Monday at 09:00. `-At`
changes the time. Registration does not replace an existing task of the same
name. Windows timezone controls the trigger; use India Standard Time for IST.
The action pins the absolute global Python 3.12 interpreter, runner path and
working directory. It runs with limited privileges while you are logged on,
starts when available after a missed trigger and ignores overlapping instances.

For logged-off execution, open Task Scheduler, select the task's General tab,
choose **Run whether user is logged on or not**, and supply the Windows account
credentials there. Verify that account can read `.env` and write the report
folder and that PostgreSQL is running. Files in a synced folder should be available locally.
Keep task credentials separate from project files.

Trigger a test and inspect its result:

```powershell
Start-ScheduledTask -TaskName 'Olist-Recurring-Report-monthly'
Get-ScheduledTaskInfo -TaskName 'Olist-Recurring-Report-monthly'
```

Confirm LastTaskResult is 0, a new run folder appeared and its manifest says
success. A task entry alone is not proof of successful scheduled reporting.
See [Microsoft's scheduling reference](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create)
for supported recurring calendar schedule types.

## 11. Output structure, review and failure handling

```text
output/reports/monthly_2018-07-01_2018-08-01/run_<IST timestamp>_<unique suffix>/
├── olist_monthly_2018-07-01_2018-07-31_generated_<today>.pdf
├── charts/daily_gmv.png
├── charts/category_gmv.png
├── charts/state_gmv.png
├── kpis.csv
├── daily.csv
├── category_all.csv
├── states.csv
├── evidence.json
├── summary.json
└── manifest.json
```

The end date in the parent folder is exclusive. The PDF uses the human-readable
inclusive date range. The run timestamp and PDF generation date are actual IST
generation time, separate from historical cohort dates. `manifest.json` is
written last and contains SHA-256 checksums for the ten other files. A partially
failed CLI run may contain `failure.json`; it has no success manifest.

Open every PDF page after a layout change. Inspect charts, table columns,
wrapped summary text, footer numbers and quality warnings. The build's current
checks and visual inspection are recorded in `VALIDATION.md`.

## 12. Troubleshooting

| Symptom | Action |
|---|---|
| Version check says wrong Python | Select global 3.12 kernel; use `python` for terminal commands |
| Module missing | Install `requirements.txt` using that exact interpreter |
| Connection fails | Verify PostgreSQL service and `.env` host/port/user/password/database |
| Correct `.env`, wrong connection | Restart kernel/terminal; process environment has precedence |
| Missing table/column | Compare the named source table with `data_loader.ipynb` schema |
| Empty current report | Use historical mode for Olist or choose a historical anchor |
| Gemini 404/permission failure | Choose a model enabled for your account; confirm key/API access |
| Gemini quota/transient failure | Inspect labelled fallback; use `required` to test live AI explicitly |
| No success manifest | Run did not finish; inspect quality checks/logs and rerun |
| Scheduled run cannot find `.env` | Check task action/working directory and user account access |
| PowerShell says scripts are disabled | Use the documented process-only `-ExecutionPolicy Bypass -File` invocation; no system policy change is needed |
| Task did not run while logged off | Configure account-based logged-off execution in Task Scheduler |
| A report folder grows every schedule | Historical Olist replay repeats the same cohort; freshness requires ingestion |

## 13. Portfolio evidence and next development milestones

Record a 60-90 second walkthrough: run the CLI, show the dated PDF arriving,
open the KPI/summary/charts, show source provenance in the manifest, then show
the recurring task configuration. Keep private credentials out of the recording.
Describe the dataset honestly as a historical replay.

Publish the source files and a reviewed sample PDF, not `.env` or unreviewed
outputs. State the actual validation performed, including AI/fallback source and
whether a scheduled execution was tested. Potential milestones are snapshot
history, ingestion watermark, report retention, client branding and explicitly
authorized delivery. Synthetic data should live in a separate labelled source,
never silently alter the original Olist records.
