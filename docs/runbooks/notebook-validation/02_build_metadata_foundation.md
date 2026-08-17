# `02_build_metadata_foundation` — Validation Capture

**Status:** 🔄 Retry in progress after an initial failure — see findings below.

## Purpose being validated

Two merged sections: Cells 1–9 (governance CSV/SQL-mirror ingestion into `lh_metadata.dbo.*`)
and Cells 10–16 (semantic reconciliation — cross-references glossary/CDE/data-product/label
bindings against the semantic model and writes `sm_annotations`). Cells 10–16 were unreachable
dead code (behind a stray `mssparkutils.notebook.exit()`) until the fix earlier in this session
— **this is the first live run where they can possibly execute.**

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status |
|---|---|---|---|---|
| 1 | `a015cfc0-f560-49fe-aa39-a21e4d6c1f82` | 2026-08-17T05:08:22 | 2026-08-17T05:15:11 | ❌ `Failed` |
| 2 | *(in progress)* | | | |

**Attempt 1 failure detail (full generic message — Fabric exposes no more than this over REST):**

```json
{
  "errorCode": "System_Cancelled_Session_Statements_Failed",
  "message": "System cancelled the Spark session due to statement execution failures",
  "isRetriable": false
}
```

Livy session: `sparkApplicationId=application_1786943372244_0001`,
`livyId=865aebd1-24a4-4dda-8a11-8ece523ee61c` — same generic `cancellationReason`, no
additional detail even from the singular Livy session endpoint.

## Diagnostic findings (attempt 1, by inference — no cell-level API exists)

Since Fabric's REST API cannot identify the failing cell, diagnosis was done by querying
`lh_metadata` directly and reading the source code:

- All Cells 1–9 target tables (`dbo.domains`, `dbo.data_products`, `dbo.glossary_terms`,
  `dbo.cdes`, `dbo.role_assignments`, `dbo.label_assignments`,
  `dbo.governance_change_requests`, `dbo.okrs`, `dbo.okr_key_results`,
  `dbo.okr_data_products`) all hold exactly their expected row counts (3/3/35/12/48/9/8/3/5/3).
  This is consistent with Cells 1–9 succeeding, but is **not conclusive** — none of these are
  freshly created by this notebook alone in a way that rules out stale prior-run data.
- `dbo.sm_annotations` (the table Cells 10–16 build) already existed with 77 rows and a schema
  exactly matching what Cell 15 writes (`model`, `table`, `object_type`, `object_name`,
  `annotation_key`, `annotation_value`) — no schema drift. This table's data could be stale from
  before the dead-code fix (its write is `mode("overwrite")`, so whatever is there reflects the
  last time Cell 15 *did* run, which historically could only have been the old, pre-consolidation
  standalone `nb_07b` notebook).
- Code review of Cells 10–16 found no obvious hard defect (schema matches, null-guards are
  present in `_append_annotation`), but this logic has never run successfully as part of the
  consolidated notebook before today, so a reproducible bug is still plausible.
- Other notebooks in this workspace (`04_writeback_governed_metadata`) also show several
  `Failed` runs with the identical generic error in the same 2026-08-16/17 window, which is
  consistent with either a shared environment/capacity issue or genuine per-notebook bugs —
  ambiguous from the API evidence alone.

**Decision:** retry once before deeper code-level instrumentation, to distinguish a transient
Spark session/capacity issue from a reproducible bug in the newly-unblocked cells.

## Data write-out confirmation

*(pending final attempt)*

## Maria Castellanos north-star use-case match

*(pending — will confirm glossary/CDE/data-product bindings that touch Maria's specific
governed objects, e.g. GT-CONSENT, CDE-CONSENTSTATE, resolve correctly in `sm_annotations`.)*

## Issues encountered

- Attempt 1: `Failed`, generic Spark session cancellation, cause not yet isolated.
