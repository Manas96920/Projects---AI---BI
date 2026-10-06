# Validation notes

Verified on 6 October 2026 using global Python 3.12.10 and the public Olist dataset.

## Notebook and source checks

- All 19 main-notebook code cells executed successfully; the notebook has 33 cells.
- Read-only repeatable-read PostgreSQL extraction and required-column checks passed.
- No source tables were created, replaced, or reloaded by the reporting pipeline.
- Published notebooks have outputs, execution counts, and nonessential metadata cleared.
- Configuration examples use placeholders. Local credentials and connection outputs are excluded.

## Results and data quality

The sample compares July 2018 with June 2018. Extraction returned 12,459 order-grain
rows and 13,973 delivered items across both periods. Key/financial gates and
independent GMV reconciliation passed with BRL 0.01 absolute tolerance.

| Metric | July 2018 | June 2018 |
|---|---:|---:|
| Purchased orders | 6,292 | 6,167 |
| Delivered orders | 6,159 | 6,099 |
| Delivered merchandise GMV | BRL 867,953.46 | BRL 856,077.86 |
| Delivered order AOV | BRL 140.92 | BRL 140.36 |
| Delivered payment total | BRL 1,027,903.86 | BRL 1,012,090.68 |
| On-time delivery rate | 96.6% | 98.8% |

Six delivered orders have missing/invalid customer-delivery dates across both
cohorts: three in July and three in June. They are excluded from delivery KPIs.
July has 6,156 eligible delivery/on-time observations and 6,121 reviewed delivered
orders. Historical outcomes use the final dataset snapshot; hindsight is disclosed.

## AI, fallback, and report packaging

- A required live-AI CLI run and the executed notebook succeeded with
  `gemini-3.5-flash-lite`.
- The verified sample records `summary_source: gemini`. Numerical summary bullets
  were compared with the KPI evidence; explanation hypotheses are not causal proof.
- Disabled AI and transient provider failures produced explicitly labelled
  rule-based summaries. API/model availability remains account-dependent.
- Monthly and weekly historical reports and an empty calendar report were generated.
- File checksums matched success manifests. The sample PDF reopened successfully,
  and all four pages were rendered and visually reviewed.
- The published PDF is the reviewed aggregate public-data sample; its bytes match
  the original generated report. Its metadata and visible text were checked for
  credentials and local filesystem details.

## Automated checks

```powershell
python -m unittest discover -s tests -v
```

**14 tests passed.** Coverage includes calendar boundaries, delivered-only GMV/AOV,
unique-customer counting, cancellation scope, same-day on-time delivery, missing
reviews, zero baselines, invalid delivery exclusion, empty SQL charts, duplicate
keys, financial corruption, independent reconciliation, and summary validation/fallback.

## Scheduler scope

Weekly and monthly task definitions were prepared and parsed in memory by Windows
Task Scheduler. Their actions pin global Python 3.12 and the project working directory.
No task was registered or started during validation. Registration and testing a
scheduled run remain setup steps described in the guide.

Fresh recurring reports require ongoing ingestion. Static Olist historical mode
intentionally replays the same latest completed cohort. Published preview images
and the sample PDF show the verified result; generated runtime folders are ignored.

[Open the reviewed sample PDF](sample_reports/olist_monthly_2018-07-01_2018-07-31_generated_2026-10-06.pdf).
