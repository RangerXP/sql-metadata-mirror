# `10_reset_demo` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `10_reset_demo.Notebook` — what it does, what it
consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/10_reset_demo.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** `False` — this notebook's normal, intentional mode is to actually reset state (a
`True` run only previews the planned changes).

**Legacy name(s):** predecessor of `nb_18_demo_reset`.

---

## What it does

The "reset the stage" utility — not part of the demo narrative itself, but what makes every
other approval scenario in this repo re-demoable indefinitely without re-running any SQL setup
script. Moves every G19 demo request back to its pre-decision status and undoes the specific
field changes that decision caused:

- **Cells 2–6 (SQL, one shared transaction):** resets 11 unified-ledger requests (Objective
  edit/certify/recertify/retire, Data Product certify/expire-review/decertify, the G18-A tag
  request, CDE/ontology-mapping requests) back to `Submitted`; resets `SEMPROMO-TECHUTIL-001`
  back to `Approved` (a system-to-system gate, not a steward-click moment, so it doesn't go all
  the way back to `Submitted`); reverts the actual field values these decisions changed on the
  real production objects `OKR-SVCDEL-SLA` and `DP-SVCPERF`; resets 3 legacy AI Instruction
  requests to `PendingApproval`.
- **Cell 7 (Lakehouse):** removes the AI Instruction demo rows from `ai_metadata`, keeping only
  the original pre-G19 baseline row.
- **Cell 8 (semantic model):** removes the `Technician Utilization Rate` measure so
  `09_reconcile_semantic_model`'s G18 phase can recreate it fresh next time.
- **Cell 9 (Final verification):** re-reads every reset request, the legacy requests, and the
  `ai_metadata` row count fresh from SQL/Lakehouse before declaring success.

Never deletes a governed object row, and never touches the P1–P4 Purview-native scenarios
(`GT-SLA`, `DP-CUST360`, `DP-SVCPERF`) built in `08_validate_governance_evidence` /
`09_reconcile_semantic_model` — those are real, one-time-proven Purview approvals; undoing them
would require actually un-publishing/un-approving inside the live Purview portal itself, which
this notebook cannot do and doesn't attempt.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `sqldemo.dbo.governance_requests` / `governance_events` / `governed_object_versions` / `governance_target_receipts` | Every request this notebook resets (Cells 3, 5) |
| `sqldemo.dbo.governance_okrs` / `governance_data_products` | The specific fields Cell 4 reverts |
| `sqldemo.dbo.governance_change_requests` | The 3 legacy AI Instruction requests Cell 5 resets |
| `lh_metadata.ai_metadata` | Cell 7's demo-row cleanup target |
| `BrookfieldEnercare` semantic model (live, via SemPy Labs TOM) | Cell 8's measure-removal target |

### Outputs produced

| Output | Detail |
|---|---|
| 11 unified-ledger requests reset to `Submitted` | Objective edit/certify/recertify/retire, Data Product certify/expire-review/decertify, G18-A tag, CDE/ontology-mapping |
| `SEMPROMO-TECHUTIL-001` reset to `Approved` | System-to-system gate, not reset all the way to `Submitted` |
| `OKR-SVCDEL-SLA` / `DP-SVCPERF` field reverts | Real production objects reverted to their true pre-G19 baseline values |
| 3 legacy AI Instruction requests reset to `PendingApproval` | `GCR-AII-002/003/004` |
| `ai_metadata` demo rows removed | Only the original baseline row (`RecordID 40`) remains |
| `fct_service_request[Technician Utilization Rate]` measure removed | So `09_reconcile_semantic_model`'s Cell 29 can recreate it fresh |
| `lh_metadata.nb10_diagnostics_log` | Real exception + traceback capture, since Fabric's job API exposes no cell-level detail (created lazily on first failure — absence of this table is itself evidence of a clean run) |

## Demo fit

Not part of the demo narrative itself — the operator-facing utility that resets the stage
between rehearsals or between live audiences, so the whole G19 approval story can be re-told
from a clean starting point without rebuilding anything.

## Talking points

(Internal use only — not shown to an audience.) "Run this after a live pass to put every gated
request back to 'awaiting approval' so tomorrow's demo starts fresh, without re-running a single
SQL setup script."

## Dependencies / downstream consumers

- Re-approving a reset request needs a small manual status flip (`Submitted`→`Approved`) plus
  re-running the matching apply notebook — `07_apply_approved_changes` for the legacy AI
  Instruction requests, or the relevant phase of `09_reconcile_semantic_model` for
  `SEMPROMO-TECHUTIL-001`. The original build scripts (`sql/24`, `sql/26`, `sql/27`, `sql/28`)
  will **not** reapply a reset request — they're guarded by `request_id` existence, not status.
- Does not depend on or affect `08_validate_governance_evidence` / `09_reconcile_semantic_model`'s
  P1–P4 Purview-native scenario state (`GT-SLA`, `DP-CUST360`, `DP-SVCPERF`) at all.

---

See also: [`09_Notebook_Description.md`](./09_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/10_reset_demo.md`](./runbooks/notebook-validation/10_reset_demo.md)
(build/debug history and live-run evidence)
