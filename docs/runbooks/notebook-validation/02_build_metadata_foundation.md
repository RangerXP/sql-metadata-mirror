# `02_build_metadata_foundation` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-17, after finding and fixing a real bug.

## Purpose being validated

Two merged sections: Cells 1–9 (governance CSV/SQL-mirror ingestion into `lh_metadata.dbo.*`)
and Cells 10–16 (semantic reconciliation — cross-references glossary/CDE/data-product/label
bindings against the semantic model and writes `sm_annotations`). Cells 10–16 were unreachable
dead code (behind a stray `mssparkutils.notebook.exit()`) until the fix earlier in this session
— **this was the first live run where they could possibly execute.**

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status |
|---|---|---|---|---|
| 1 | `a015cfc0-f560-49fe-aa39-a21e4d6c1f82` | 2026-08-17T05:08:22 | 2026-08-17T05:15:11 | ❌ `Failed` |
| 2 (retry, no code change) | `929054d2-82f3-4c84-b470-23bc9f794e61` | 2026-08-17T05:17:58 | 2026-08-17T05:25:32 | ❌ `Failed` (reproducible, not transient) |
| 3 (ingestion reorder + Cells 3-9 diagnostics) | `a6c41b4d-1001-4b7b-8f85-e0e62e6e956f` | 2026-08-17T05:30:28 | 2026-08-17T05:37:22 | ❌ `Failed` (reorder wasn't the cause; diagnostics finally captured the real exception) |
| 4 (real fix: refreshTable + column pruning) | `5bc51918-6849-486f-8ff0-8669c91c1a73` | 2026-08-17T05:42:05 | 2026-08-17T05:48:45 | ❌ `Failed` (fix not yet pushed/synced when this ran) |
| 5 (fix live) | `92e98718-6a78-42c2-8a1d-b54157e27a68` | 2026-08-17T05:52:12 | 2026-08-17T05:58:52 | ✅ `Completed` |

**Generic Fabric failure detail (identical across all 4 failed attempts — confirms the platform
exposes no more than this over REST):**

```json
{
  "errorCode": "System_Cancelled_Session_Statements_Failed",
  "message": "System cancelled the Spark session due to statement execution failures",
  "isRetriable": false
}
```

## Root cause (found via custom diagnostic instrumentation, not the Fabric API)

Added a `_log_nb02_diagnostic(stage, error)` helper (matching the existing pattern already used
in `06_publish_glossary_and_lineage`/`07_apply_approved_changes`) that writes the real Python
exception + traceback to `dbo.nb02_diagnostics_log` before re-raising, since Fabric's REST API
cannot identify the failing cell. This surfaced the actual error on attempt 3:

```
stage: cell14_build_annotation_rows
error_type: Py4JJavaError
error_message: An error occurred while calling o10276.collectToPython.
: java.lang.IllegalStateException: Couldn't find parent_term_code#42033 in
  [term_code#42030,term_name#42031,acronyms#42032,domain_code#42034,owner_upn#42035,
   additional_owners_upn#42036,definition#42037,status#42038,is_cde#42039,
   industry_origin#42040,resources#42041,bound_assets#42042,approved_at#42044]
```

**This is the exact same stale-Spark-catalog-schema bug already documented and fixed elsewhere
in this repo** (`06_publish_glossary_and_lineage`'s `_read_table()`, and the historical
2026-08-10 "G14-8" fix for `nb_08`/`nb_09`): Spark's cached logical plan expected a
`parent_term_code` column that no longer exists in the physical Delta table (replaced by
`approved_at` from a later schema migration), and `glossary_df.collect()` in Cell 14 forces
Spark to materialize the *entire* cached schema, not just the columns the Python code actually
touches. Cell 10's `_read_table()` (used for the reconciliation section) never got the
`refreshTable()` + column-pruning fix that notebook 06 already has.

**Fix applied:** added `spark.catalog.refreshTable(candidate)` before `spark.table(candidate)`
in Cell 10's `_read_table()`, and pruned `glossary_df`/`cde_df`/`data_products_df`/`labels_df`
to only the columns Cell 14 actually reads (`GLOSSARY_COLUMNS_NEEDED`, `CDE_COLUMNS_NEEDED`,
etc.) — same pattern as notebook 06. Also instrumented Cells 3–9 with the same diagnostic
logger for defense-in-depth (none of them actually failed, but if a similar bug ever recurs
there, it will now be immediately queryable instead of hidden).

**A red herring investigated first:** `try_load_sql_dataset()`'s ingestion helper (Cells 1–9)
tries a large combinatorial set of physical `abfss://` Delta paths before falling back to
catalog-based lookup — worth avoiding on its own merits (reordered to try the known-good
catalog lookup first), but this was **not** the actual cause of this failure; attempt 3 proved
that empirically (still failed after reordering, until the real Cell 14 fix was applied).

## Data write-out confirmation

`dbo.sm_annotations` (rebuilt fresh by the successful run, `mode("overwrite")`): **77 rows**,
breakdown by `annotation_key`:

| Annotation key | Count |
|---|---|
| `Glossary_Term_References` | 62 |
| `Sensitivity_Label` | 7 |
| `Data_Product_Owner` | 6 |
| `CDE_Member_Of` | 2 |

`dbo.nb02_diagnostics_log`: 2 rows total, both from the pre-fix failed attempts — **zero new
rows added during the successful run**, confirming the fix, not luck, resolved it.

Cells 1–9 target tables all still hold their expected counts (3/3/35/12/48/9/8/3/5/3 for
domains/data_products/glossary_terms/cdes/role_assignments/label_assignments/
governance_change_requests/okrs/okr_key_results/okr_data_products).

## Maria Castellanos north-star use-case match

- ✅ `dim_customer` correctly carries the `GT-003 | Customer Consent` glossary binding,
  resolved from `dbo.glossary_terms` (`bound_assets = dbo.customer_consents`) — this is the
  term Ci Zhu cites when explaining Maria's consent governance in Act 3.
- ⚠️ **Finding (source-data quality gap, not a notebook 02 bug):** of the 35 glossary terms,
  only `GT-001` through `GT-010` have real curated `term_name` values (Customer, Customer
  Consent, Social Insurance Number, PCI Scope Data, Service Request, First Contact Resolution,
  Contract, Billing Transaction, Data Owner, Data Access Audit). `GT-011` through `GT-035` (25
  terms) carry a generic placeholder name — literally `"Governance Term 16"`, `"Governance Term
  17"`, etc. — in the underlying `dbo.glossary_terms` source data. Notebook 02 correctly reads
  and reconciles whatever the SQL source contains; this is upstream seed-content that needs
  real curated definitions written for GT-011–035 (likely in
  `sql/02_metadata_foundation/07_seed_purview_metadata.sql` or wherever these specific rows
  originate) — flagged for the broader artifact-cataloging pass, not fixed here.

## Issues encountered

- 4 of 5 attempts failed before the real fix was found and applied; resolved via custom
  diagnostic instrumentation since Fabric's REST API provides no cell-level detail. See
  "Root cause" above for the full investigation trail.

## Follow-up (2026-08-17, later same day): quantified PP renewal / billing-caller correlation

The `04_writeback_governed_metadata` validation doc flagged an open item: the semantic model's
AI grounding referenced the billing-caller/PP-renewal correlation (the notebook-1 cohort-variance
fix) only qualitatively ("often signals billing confusion"), not with the actual fixed numbers
(~51% renewal for billing-queue callers vs. ~86% for everyone else, a ~35-point gap). Strengthened
the `PP_RNW_RATE` / "renewal rate" `verified_answer` row in this notebook's seed data
(`ai_metadata`) with the quantified gap so the Data Agent can surface it as a specific,
governed, Tom-facing fact instead of a vague qualitative hint.

| Attempt | Job ID | Start (UTC) | End (UTC) | Status | Note |
|---|---|---|---|---|---|
| 6 | `d817ce60-3405-4e6f-b07b-da8daacda8db` | 2026-08-17T07:22:19 | 2026-08-17T07:29:14 | ✅ `Completed` (misleading) | Ran against **stale Fabric code** — see pitfall below. `ai_metadata` content unchanged after this run. |
| 7 (after git sync fix) | `8800f6f6-9986-47ab-8d7e-c42008f0be05` | 2026-08-17T07:35:28 | 2026-08-17T07:42:42 | ✅ `Completed` (verified) | `ai_metadata.RecordID=18` confirmed updated with the quantified-gap text. |

**Pitfall discovered — local edits do not auto-propagate to Fabric:** editing
`notebook-content.py` locally and even committing+pushing to git is **not enough** to change
what Fabric actually executes. Fabric only picks up git history after its own workspace Git
connection is explicitly synced (`POST /v1/workspaces/{id}/git/updateFromGit`). Attempt 6 above
ran, reported `Completed`, and printed no error at all — but silently executed the **old**
pre-edit code, because the Fabric workspace head (`5ada16a...`) was 4 commits behind the pushed
remote head. There is no warning surfaced anywhere in the job API for this condition; the only
way to catch it is to actually verify the data output changed as expected. Added
`tools/sync_fabric_git.py` to make this an explicit, scripted step — **run it after every push
of a `notebook-content.py` change and before re-running that notebook's job.**

## Corrected data write-out confirmation (attempt 7)

`dbo.ai_metadata` `RecordID=18` (`TriggerText='renewal rate'`, `LinkedKPICode='PP_RNW_RATE'`,
`IsCertified=1`, `CertifiedBy='Victoria Tan'`):

> PP Renewal Rate target is 82%. Customers who contacted the billing queue before their renewal
> date renew at roughly 51%, versus about 86% for customers who did not contact the billing
> queue — a ~35-point gap signaling billing confusion as a churn driver. Cross-reference with
> AHT on billing queue.


