# `09_reconcile_semantic_model` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-18, after finding and fixing two real
bugs: a missing environment attachment (blocked `sempy_labs` entirely) and a Draft-before-
Published guard that didn't tolerate an idempotent rerun of an already-`Completed` request.

## Purpose being validated

Five phases in one notebook:

- **Cells 1–7 (P2):** reconcile the approved `GT-SLA` glossary term into the semantic model.
- **Cells 8–14 (P3):** record the `DP-CUST360` data product access decision (operator-attested).
- **Cells 15–21 (P4a):** observe the `DP-SVCPERF` Draft→Published publish transition.
- **Cells 22–28 (P4b):** reconcile the approved `DP-SVCPERF` publish into semantic-model
  annotations.
- **Cell 29 (G18/G19):** promote `KR-TECH-UTIL`'s source object into a new semantic measure.

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status | Note |
|---|---|---|---|---|---|
| 1 | `a686063e-ae8f-4615-86a2-954cebb62842` | 2026-08-18T04:24:28 | 2026-08-18T04:27:49 | ❌ `Failed` | No diagnostic logging present yet; `nb09_diagnostics_log` didn't exist afterward, meaning the failure occurred before any wrapped cell (3+) ran |
| 2 | `47d112fe-4998-4044-a982-88d580a241af` | 2026-08-18T04:31:24 | 2026-08-18T04:34:56 | ❌ `Failed` | Diagnostic logging added to Cell 2's import; captured the real error: `ModuleNotFoundError: No module named 'sempy_labs'` |
| 3 | `a4496a5e-b704-41f2-96f1-296bb114bf9e` | 2026-08-18T04:37:55 | 2026-08-18T04:57:26 | ❌ `Failed` | Environment fix applied before this run — P2 completed for real (fresh `SemanticModelReadback` receipt written at 04:41:42), but the run failed later with no new diagnostic-log entry; root cause found via direct SQL evidence + the user's own manual run, not this run's own diagnostics |
| 4 (manual, interactive) | *(portal session, no REST job ID)* | ~2026-08-18T05:2x | ~2026-08-18T05:29:31 | ✅ Completed (verified by output + SQL) | User-triggered manual run after the Cell 19 guard fix; all 29 cells produced correct output through Cell 29's completion message |

## Root cause — two distinct real bugs, found in sequence

**Bug 1 (attempts 1–2): missing environment attachment.** Attempt 1 failed before Cell 3 ever
logged anything, which was itself the diagnostic signal — an empty/non-existent
`nb09_diagnostics_log` table after a failure means the failure happened earlier than any
wrapped cell, not that "nothing went wrong." Added diagnostic logging to Cell 2's
`sempy_labs.tom` import; attempt 2 captured the real error:

```
ModuleNotFoundError: No module named 'sempy_labs'
```

This notebook's item-level `# META` metadata `dependencies` block only declared `lakehouse` —
unlike `04_writeback_governed_metadata` (which also uses `sempy_labs.tom` successfully) and
correctly declares an `environment` block pointing at `environmentId
7380ddbb-a87b-8113-489c-049cb1998b35` (SempyLabsV2). Fixed by adding the identical `environment`
block to `09_reconcile_semantic_model`'s metadata header.

**Bug 2 (attempt 3): idempotent-rerun guard gap.** With the environment fix in place, attempt 3
ran ~20 minutes (vs. ~3.3 minutes for attempts 1–2) — direct SQL confirmed P2 (`GT-SLA`)
completed for real this run, writing a fresh `SemanticModelReadback` receipt at
`2026-08-18 04:41:42`. The run still failed later with **no new** `nb09_diagnostics_log` entry,
meaning the failure occurred somewhere the diagnostic wrapping didn't catch it — a different
failure signature than bugs 1–2. The user's subsequent manual/interactive run in the Fabric
portal surfaced the actual traceback (invisible to the REST job API):

```
RuntimeError: Refusing to record Published as approval evidence because this correlation has no
prior Draft observation. Unpublish/edit DP-SVCPERF, run this notebook once while Draft, submit
it to the native workflow, then rerun after approval.
```

Cell 19's P4a guard only tolerated `existing_status in ("Draft", "Approved")` before accepting a
`Published` observation as approval evidence. `PV-DP-SVCPERF-9EAF4919D7DFD8F8B5C6` was already
`Completed` from an earlier session (2026-08-13), so this idempotent rerun was incorrectly
rejected as if it had never seen a Draft baseline. Fixed by adding `"Completed"` to the tolerated
set — reaching `Completed` already proves Draft was observed at some point in this correlation's
history; the guard's real intent (block a Published-only observation with **no** prior Draft
ever) is unaffected.

## Data write-out confirmation (final successful run)

All 4 governance requests confirmed `Completed` via direct SQL query
(`sqldemo.dbo.governance_requests`):

| Request | Type | Status | `completed_at` |
|---|---|---|---|
| `PV-GT-SLA-0359C207890E4EB1B8AB` | `GLOSSARY_TERM_PUBLICATION` | Completed | 2026-08-11 (unchanged — `COALESCE`-protected, correct) |
| `PV-CUST360-ACCESS-BD3BEBA460C530FA5076` | `DataProductAccess` | Completed | 2026-08-18 05:29:14 |
| `PV-DP-SVCPERF-9EAF4919D7DFD8F8B5C6` | `DataProductPublish` | Completed | 2026-08-18 05:29:26 |
| `SEMPROMO-TECHUTIL-001` | `SemanticModelPromotion` | Completed | 2026-08-18 05:29:31 |

All 6 receipts confirmed `Passed` (`sqldemo.dbo.governance_target_receipts`), 5 with today's
fresh `observed_at` timestamp (GT-SLA's P1 `PublicationReadback` correctly untouched — that's
P1's own receipt, not something this notebook rewrites):

| Request | Target system | Receipt type | Status | `observed_at` |
|---|---|---|---|---|
| GT-SLA | Fabric | `SemanticModelReadback` | Passed | 2026-08-18 05:29:12 |
| GT-SLA | Purview | `PublicationReadback` | Passed | 2026-08-18 02:45:01 (P1's own receipt) |
| DP-CUST360-ACCESS | Purview | `AccessDecisionReadback` | Passed | 2026-08-18 05:29:14 |
| DP-SVCPERF | Purview | `PublicationReadback` | Passed | 2026-08-18 05:29:17 |
| DP-SVCPERF | Fabric | `SemanticModelReadback` | Passed | 2026-08-18 05:29:26 |
| SEMPROMO-TECHUTIL-001 | Fabric | `SemanticModelReadback` | Passed | 2026-08-18 05:29:31 |

**Live semantic-model confirmation** (Power BI Modeling MCP, reconnected fresh via
`ConnectFabric` immediately before each read to avoid the documented stale-cache gotcha):

| Object | Description confirms | Annotations confirm |
|---|---|---|
| `_Measures[SLA Breach Count]` | Governed GT-SLA definition text present | `Glossary_Term_References=GT-SLA`, correct term ID + content hash + request ID |
| `_Measures[SLA Compliance Rate]` | Governed GT-SLA definition text present | Same 4 annotations as above |
| `fct_service_request.IsSlaBreachFlag` | Governed GT-SLA definition text present | Same 4 annotations as above |
| `fct_service_request.TechnicianId` | Governed DP-SVCPERF definition text present | `DataProduct_References=DP-SVCPERF`, correct data-product ID + content hash + request ID |
| `dim_equipment.EquipmentType` | Governed DP-SVCPERF definition text present | Same 4 annotations as above |
| `fct_service_request[Technician Utilization Rate]` (new measure) | `DIVIDE(DISTINCTCOUNT(...TechnicianId), COUNTROWS(...))`, format `0.0%` | `SourceObject_References=dbo.vw_technician_utilization_summary`, `KeyResult_Id=KR-TECH-UTIL`, `Governance_Request_Id=SEMPROMO-TECHUTIL-001` |

## Post-hoc validation

Ran both governance-contract tools after this notebook's success — both clean:

- `tools/audit_seed_vs_source.py --target both`: **0 failing checks** across row-count,
  value-level parity, enum compliance, and referential-integrity categories, at both the sub2
  SQL source and the `lh_metadata` destination.
- `tools/validate_required_columns_not_null.py --target both`: **0 violations** across 74
  required-column x table checks at both targets.

## Maria Castellanos north-star use-case match

- ✅ Completes the GT-SLA (Ci Zhu), DP-CUST360 (Victoria Tan/Rupal Solanki), and DP-SVCPERF
  (Ranbir Singh/Shruthi Srinivas) governance chains — each scenario's real Purview action is now
  reflected in the live semantic model with a durable, re-verifiable receipt.
- ✅ The G18/G19 `Technician Utilization Rate` measure is the "new SQL source becomes a real
  semantic-model KPI" full-circle moment for the onboarding narrative.

## Issues encountered

- 1 real bug: missing `environment` metadata dependency block (attempts 1–2), fixed by copying
  the identical block from `04_writeback_governed_metadata`.
- 1 real bug: Cell 19's Draft-before-Published guard didn't tolerate an already-`Completed`
  correlation on an idempotent rerun (attempt 3), fixed by adding `"Completed"` to the tolerated
  `existing_status` set.
- Also removed the interactive `DeviceCodeCredential` fallback from Cells 9 and 16 (and, while
  auditing the same pattern repo-wide, from `05_publish_governance_domains` and
  `06_publish_glossary_and_lineage`) — an unattended `RunNotebook` job can never complete a
  device-code sign-in, and none of the removed fallbacks were ever actually needed since a
  non-interactive Azure CLI credential path already existed alongside each one.
- No data-quality bugs found — every table this notebook reads/writes passed the full
  governance-contract audit both before and after this notebook's live run.
