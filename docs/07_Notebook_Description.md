# `07_apply_approved_changes` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `07_apply_approved_changes.Notebook` — what it
does, what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/07_apply_approved_changes.md`.

**Status:** ✅ Validated.

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
