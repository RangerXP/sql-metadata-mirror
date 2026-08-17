# `07_apply_approved_changes` — Notebook Description & Artifact Catalog

**Purpose:** Full descriptive reference for `07_apply_approved_changes.Notebook` — what it
does, what it consumes/produces, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and its live-validation history.

**Status:** ✅ Live-validated end-to-end 2026-08-17, including a real apply-then-revert test
cycle that found and fixed a genuine build gap (see
`docs/runbooks/notebook-validation/07_apply_approved_changes.md` for full evidence).

**DEMO_MODE:** `False` (intentional — its job is to apply real state changes).

**Legacy name(s):** predecessor of `nb_11_gated_governance_sync`.

---

## What it does

The apply-on-approve dispatcher for the closed-loop gated-governance workflow. Reads
`Approved`/unapplied rows directly from the `sub2` SQL source (`sqlserver-sk2wus3`/`sqldemo`,
never the lakehouse mirror, to avoid acting on stale status), validates each row carries the
required governance tags, dispatches by `request_type` (`KPI_APPROVAL`,
`VERIFIED_ANSWER_CERTIFICATION`, `CDE_CLASSIFICATION`, `GLOSSARY_TERM_DEFINITION`,
`AI_INSTRUCTION_CERTIFICATION`, `AI_INSTRUCTION_ROLLBACK`), applies the corresponding change to
`lh_metadata`, and stamps the request `Applied`.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `sqldemo.dbo.governance_change_requests` (status='Approved', applied_at IS NULL) | The pending-apply queue this notebook drains every run |

### Outputs produced

| Output | Detail |
|---|---|
| `lh_metadata.kpi_metadata` updates | KPI certification, version bump, formula/threshold changes for `KPI_APPROVAL` requests |
| `lh_metadata.ai_metadata` inserts | New certified verified-answer / AI-instruction rows for `VERIFIED_ANSWER_CERTIFICATION`/`AI_INSTRUCTION_CERTIFICATION` requests |
| `AI_INSTRUCTION_ROLLBACK` handling | Restores a prior certified AI instruction version, resolving the currently-active row and the one immediately before it dynamically (no hardcoded RecordID) |
| `sqldemo.dbo.governance_change_requests.status/applied_at` stamped `Applied` | The durable audit trail proving each approved change was actually applied, and when |
| `lh_metadata.nb11_diagnostics_log` | Real exception + traceback capture, since Fabric's job API exposes no cell-level detail |

## Demo fit

This is the live "click Approve → watch the data change" moment for every SQL-controlled
scenario — a KPI reformulation, a new verified answer, an AI instruction fix, or a rollback when
a bad edit is caught (the GCR-AII-003/004 escalation-guidance scenario is a real example: a
flawed edit that drops a safety clause, caught and reverted through the same governed path).

## Talking points

"One dispatcher, several request types, all sharing the same Draft→Approved→Applied contract —
this is what makes the closed loop closed."

## Live-validation findings

| Finding | Detail | Status |
|---|---|---|
| **Initial run had nothing new to process** | All 8 seeded governance change requests were already `Applied` from prior sessions (2026-08-09/2026-08-13) — a clean run with 0 errors, but it didn't exercise the actual dispatch/apply code path for anything new. | ℹ️ Not a bug — prompted a deliberate live test (below) to genuinely exercise the mechanism. |
| **Real bug/gap found via live test: undocumented mandatory governance tags** | Inserted a real `KPI_APPROVAL` test request (`GCR-VALTEST-001`, bumping AHT's description/version) with a minimal payload matching the historical seed-data shape. It was silently skipped — `_validate_approved_request()` unconditionally requires every request's `proposed_payload` to carry 5 tag keys (`domain`, `owner`, `sensitivity`, `semantic_role`, `business_use`), a check that **none of the 8 original seed scenarios' payloads satisfy** (confirmed by inspecting `sql/07_governance_gates/10_seed_gated_governance_scenarios.sql` and the AI-instruction gate files) — they were applied before this validation gate existed. | ✅ **Fixed 2026-08-17.** Added the 5 required tags to all 8 seed scenarios across `10_seed_gated_governance_scenarios.sql`, `16_add_ai_instruction_gate.sql`, and `25_g19_ai_instruction_lifecycle_gate.sql` (so any future reseed/demo-reset produces genuinely dispatchable requests), and synced the equivalent tags onto the 8 already-`Applied` live rows in `sqldemo` via `JSON_MODIFY` for consistency. |
| **Confirmed live: the dispatcher genuinely works today** | After adding the required tags to the test payload, re-running the notebook correctly dispatched `GCR-VALTEST-001` — `kpi_metadata.AHT` updated to Version 2 with the test marker text, `CertifiedBy` stamped, and the request status flipped to `Applied`. | ✅ Confirmed via direct SQL read-back, not just job status. |
| **Test change cleanly reverted through the same governed mechanism** | Rather than a raw side-channel fix, inserted a second properly-tagged request (`GCR-VALTEST-001-REVERT`) restoring AHT's original Version/Description, and re-ran the notebook to apply it — proving the dispatcher also handles a genuine "undo" scenario correctly. | ✅ Confirmed: AHT restored to Version 1, original description, both test requests show `Applied` in the audit trail. |

## Dependencies / downstream consumers

- Depends on `sqldemo.dbo.governance_change_requests` being seeded (via
  `sql/07_governance_gates/*.sql`) with properly-tagged, `Approved` rows.
- Applied changes feed directly into `lh_metadata.kpi_metadata`/`ai_metadata`, which
  `04_writeback_governed_metadata` and `09_reconcile_semantic_model` read from for their own
  writebacks.
- `08_validate_governance_evidence`'s stewardship/control checks and `09_reconcile_semantic_model`
  both depend on this notebook's `Applied` stamping being accurate and current.

---

See also: [`06_Notebook_Description.md`](./06_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/07_apply_approved_changes.md`](./runbooks/notebook-validation/07_apply_approved_changes.md)
