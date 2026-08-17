# Notebook Validation Capture — Index

**Purpose:** Live, execution-grounded validation record for each of the 10 current Fabric
notebooks, built by actually running each notebook end-to-end (not by reading the code).
Distinct from the two documents it complements:

- [`docs/01_Notebook_Description.md`](../../01_Notebook_Description.md) — static, code-grounded
  reference of what each notebook does. Not updated by a live run.
- [`docs/runbooks/ten-notebook-consolidated-validation.md`](../ten-notebook-consolidated-validation.md) —
  the execution *procedure* (REST harness, ordered sequence, validation checklist per stage).

This folder is the *evidence*: one file per notebook, filled in immediately after that notebook
is actually run in Fabric, capturing the job/Livy correlation IDs, the data written out, and
whether the result matches the Call Center / Maria Castellanos north-star governance use case
(`docs/purview-maria-north-star-scenario.md`).

**Known platform limit (do not re-investigate):** the Fabric Job Instance API only ever returns
a generic terminal failure message (`System cancelled the Spark session due to statement
execution failures`) — there is no per-cell REST endpoint. Confirmed empirically 2026-08-16
against real historical failures. `tools/run_fabric_notebook_job.py` correlates the job to its
Livy session (`sparkApplicationId`, `cancellationReason`) for the best available machine
evidence; the actual failing cell and its traceback are only visible in Monitor Hub in the
Fabric portal, using the IDs this tool prints.

## Run command

```powershell
& 'C:\Program Files\Python37\python.exe' tools\run_fabric_notebook_job.py `
  --workspace-id b976cac2-7754-4061-88c2-61c0ac016a99 `
  --notebook <notebook-display-name> `
  --startup-timeout 10 --execution-timeout 30 --poll-seconds 15 `
  --json-log docs\runbooks\notebook-validation\_job-log.jsonl
```

If the local session drops mid-run, resume monitoring the same Fabric job (never resubmit)
with `--job-id <jobId>` printed at submission time.

## Status

| # | Notebook | Status | Doc |
|---|---|---|---|
| 1 | `01_setup_source_data` | ✅ Completed | [01_setup_source_data.md](./01_setup_source_data.md) |
| 2 | `02_build_metadata_foundation` | ✅ Completed (real bug found + fixed) | [02_build_metadata_foundation.md](./02_build_metadata_foundation.md) |
| 3 | `03_build_semantic_model` | ⬜ Not started | — |
| 4 | `04_writeback_governed_metadata` | ⬜ Not started | — |
| 5 | `05_publish_governance_domains` | ⬜ Not started | — |
| 6 | `06_publish_glossary_and_lineage` | ⬜ Not started | — |
| 7 | `07_apply_approved_changes` | ⬜ Not started | — |
| 8 | `08_validate_governance_evidence` | ⬜ Not started | — |
| 9 | `09_reconcile_semantic_model` | ⬜ Not started | — |
| 10 | `10_reset_demo` | ⬜ Not started | — |

After all 10: semantic-model attribute/gating confirmation (certified vs. pending-approval
state) via the Power BI Modeling MCP, recorded in `docs/semantic-model-annotations.md`.
