# `10_reset_demo` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-18. No bugs found in the notebook's own
logic; one pre-existing environment-state fact discovered during evidence collection (see
"Finding" below), not caused by this notebook or this run.

## Purpose being validated

Resets every G19 demo request back to its pre-decision status (SQL Cells 2–6, Lakehouse Cell 7,
semantic model Cell 8), verifies the reset landed (Cell 9), so the whole G19 approval narrative
can be re-demoed live without re-running any SQL setup script. Never touches the P1–P4
Purview-native scenarios built in `08`/`09`.

## Pre-run hardening (same session, before this run)

Reviewed against the pattern established for `02`/`06`/`07`/`08`/`09` before ever running this
notebook live:

- Added the `SempyLabsV2` environment metadata dependency block — Cell 8 uses `sempy_labs.tom`
  the same way `04`/`09` do, and this notebook was previously missing that attachment (masked by
  a runtime pip-install fallback that would likely have worked but is slower/non-deterministic).
- Added `_log_nb10_diagnostic()` and wrapped every substantive cell (2–8) in try/except with this
  logging call before re-raising — this notebook previously had zero diagnostic logging.
- Added a new Cell 9 (Final verification) that re-reads every reset request, the legacy AI
  requests, and the `ai_metadata` row count fresh from SQL/Lakehouse before trusting the reset
  succeeded, matching `07`/`08`/`09`'s own Verify-cell discipline.
- Fixed the stale header (`nb_18_demo_reset` → `10_reset_demo`) and stale legacy notebook-name
  references in the final summary print (`nb_11_gated_governance_sync`/`nb_17_g18_semantic_
  promotion` → `07_apply_approved_changes`/`09_reconcile_semantic_model`).

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status |
|---|---|---|---|---|
| 1 | `0ad5be77-f64b-48e0-9be7-c463e3e386cf` | 2026-08-18T06:05:42 | 2026-08-18T06:11:45 | ✅ `Completed` |

First live run, no failure, no diagnostic-log entries (the absence of `nb10_diagnostics_log`
after the run — the table is only created lazily on a first failure — is itself confirming
evidence of a clean run, same interpretation rule established for `nb09_diagnostics_log`).

## Data write-out confirmation

All confirmed via direct SQL query and a fresh Power BI Modeling MCP reconnect (never trusting
the notebook's own print output alone):

**Unified-ledger requests reset to `Submitted`** (`sqldemo.dbo.governance_requests`):

| request_id | current_status |
|---|---|
| `CDEMAP-CONTRACT-RENEWAL-001` | Submitted |
| `DPCERT-LEGACY-IVR-001` | Submitted |
| `DPCERT-SVCPERF-002` | Submitted |
| `DPCERTREVIEW-SVCPERF-001` | Submitted |
| `DPDECERT-LEGACY-IVR-001` | Submitted |
| `OBJCERT-SVCDEL-SLA-001` | Submitted |
| `OBJEDIT-SVCDEL-SLA-001` | Submitted |
| `OBJRECERT-SVCDEL-SLA-001` | Submitted |
| `OBJRETIRE-CUSTOPS-LEGACY-NPS-001` | Submitted |
| `ONTOMAP-TECHUTIL-001` | Submitted |
| `TAG-D0BF6E496681E6B0` | Submitted |
| `SEMPROMO-TECHUTIL-001` | **Approved** (correctly not reset all the way to Submitted — a system-to-system gate, not a steward-click moment) |

**Legacy AI Instruction requests reset to `PendingApproval`** (`sqldemo.dbo.governance_change_requests`):
`GCR-AII-002`, `GCR-AII-003`, `GCR-AII-004` all confirmed `PendingApproval`.

**Real production object field reverts** (`sqldemo.dbo.governance_okrs` / `governance_data_products`):

| Object | Confirmed reverted state |
|---|---|
| `OKR-SVCDEL-SLA` | `target_date=2026-12-31`, `is_certified=0`, `certified_by=NULL`, `status=Published` |
| `DP-SVCPERF` | `is_certified=0`, `certified_by=NULL`, `expiration_date=NULL`, `status=Published` |

**`ai_metadata` cleanup** (`lh_metadata.ai_metadata`): only `RecordID 40` (`escalation`,
`IsCertified=1`, `IsRolledBack=NULL`) remains for the reset `TriggerText` values — the
`weather_delay` demo row (which had no pre-G19 baseline to preserve) is fully gone, 0 rows.

**Semantic model** (Power BI Modeling MCP, reconnected fresh via `ConnectFabric` before reading):
`fct_service_request[Technician Utilization Rate]` — `Get` returns `"Measure [Technician
Utilization Rate] not found in the model"`, confirming the measure was actually removed, not
just reported as removed by the notebook's own print output.

## Finding: the 2 disposable demo objects no longer exist in the live database

While verifying Cell 4's field reverts, direct SQL query of `dbo.governance_okrs` and
`dbo.governance_data_products` showed only the **3 real production rows each** (`OKR-CUSTOPS-CX`,
`OKR-REVCON-RETAIN`, `OKR-SVCDEL-SLA`; `DP-BILLHEALTH`, `DP-CUST360`, `DP-SVCPERF`) — matching
the seed `.sql` files' own declared counts (also confirmed by `tools/audit_seed_vs_source.py`).
The two disposable demo objects this notebook's design assumes still exist —
`OKR-CUSTOPS-LEGACY-NPS` and `DP-LEGACY-CALLCENTER-IVR` (created earlier in the project to prove
the retirement/decertification workflows without touching real production objects) — are **not
present in the current live database at all**.

This is **not a bug in `10_reset_demo`** — Cell 4's `UPDATE ... WHERE okr_id = 'OKR-CUSTOPS-
LEGACY-NPS'` / `WHERE data_product_id = 'DP-LEGACY-CALLCENTER-IVR'` statements simply affected 0
rows (a SQL `UPDATE` against a non-matching `WHERE` clause is a normal no-op, not an error), so
the notebook completed cleanly with no false success. It's a **pre-existing environment-state
fact**, most likely explained by the demo environment having been reseeded from scratch (via
`01_setup_source_data`, which reseeds `sqldemo`/`lh_metadata` to the seed `.sql` files' exact
declared row counts) at some point after those two disposable objects were originally created in
an earlier project phase — a reseed would not know about or preserve ad-hoc objects that were
never part of the seed script's own declared content.

**Practical consequence:** the 3 governance requests referencing these objects
(`OBJRETIRE-CUSTOPS-LEGACY-NPS-001`, `DPCERT-LEGACY-IVR-001`, `DPDECERT-LEGACY-IVR-001`) are now
correctly reset to `Submitted`, but re-approving them in a future redemo would have no real
underlying object to apply a field change to. This does not block or affect any of the 3
Purview-native scenarios (`GT-SLA`, `DP-CUST360`, `DP-SVCPERF`) or the real production objects
(`OKR-SVCDEL-SLA`, `DP-SVCPERF`), which all confirmed correctly reverted. If the disposable-object
retirement/decertification demo scenarios are needed again, the objects would need to be
recreated first (the original `sql/24`/`sql/26` creation logic, re-run once).

## Post-hoc validation

Ran both governance-contract tools after this notebook's success — both clean:

- `tools/audit_seed_vs_source.py --target both`: **0 failing checks** across row-count,
  value-level parity, enum compliance, and referential-integrity categories, at both the sub2
  SQL source and the `lh_metadata` destination.
- `tools/validate_required_columns_not_null.py --target both`: **0 violations** across 74
  required-column x table checks at both targets.

## Maria Castellanos north-star use-case match

Not directly part of the demo narrative — this is the operator utility that makes every other
scenario's demo repeatable indefinitely. Its correct behavior (real production objects and
Purview-native scenarios untouched, demo-only state cleanly reset) directly protects the
integrity of every other notebook's proven demo narrative.

## Issues encountered

- No bugs in this notebook's own logic on its first live run.
- 1 pre-existing environment-state fact discovered during evidence collection (see Finding
  above) — not a defect in `10_reset_demo`, and does not affect the demo's core Purview-native
  or real-production-object narrative.
