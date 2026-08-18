# Notebook 10: `10_reset_demo` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/10_Notebook_Description.md` (validation history),
this document catalogs the **artifacts this notebook produces**, evaluates them against build
requirements, and explains its (non-audience-facing) role in the demo operation. Source document
for demo slide development — though this specific notebook has no slide content of its own.

---

## Notebook purpose & role

**What it is:** The "reset the stage" operator utility — not part of the demo narrative itself,
but the reason every other approval scenario in this repo can be re-demoed indefinitely without
rebuilding anything.

**How it's applied:** Run tenth, and again between rehearsals or live audiences — never during
an actual presentation. Resets every G19 demo request (Objective/Data Product/CDE/ontology/
semantic-promotion) back to its pre-decision status, reverts the specific field changes each
decision caused, and re-verifies the reset landed before declaring success.

**Use-case delivery objective:** Protects the integrity of every other notebook's demo narrative
by cleanly separating "real, one-time-proven Purview approvals" (never touched) from
"repeatable G19 demo content" (reset every time) — a presenter never has to worry about whether
today's demo run will still work tomorrow.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| Reset unified-ledger requests | 11 rows in `sqldemo.dbo.governance_requests` → `Submitted` | Every G19 Objective/Data Product/CDE/ontology-mapping request | Lets a presenter re-run the entire "submit → approve → apply" cycle from scratch |
| `SEMPROMO-TECHUTIL-001` reset to `Approved` | 1 row | The G18 semantic-promotion gate | Skips the "submit" step since this is a system-to-system gate, not a steward-click moment |
| Reverted production-object fields | `OKR-SVCDEL-SLA`, `DP-SVCPERF` | Real fields these G19 decisions changed | Presenter can redemo "certify it, recertify it" on the SAME real objects used elsewhere in the demo |
| `ai_metadata` demo-row cleanup | Lakehouse table | Removes G19-4's AI Instruction demo content | The Data Agent's grounding content returns to its true pre-G19 baseline |
| Removed `Technician Utilization Rate` measure | Semantic model | The G18 measure `09_reconcile_semantic_model` created | Lets `09`'s G18 phase recreate it fresh on the next redemo pass, proving the promotion step for real again |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Never delete a governed object row" | Confirmed by code review and live run — every reset is an `UPDATE`/status change, never a `DELETE` on a governed object table |
| "Never touch the real Purview-native scenarios" | Confirmed: `GT-SLA`/`DP-CUST360`/`DP-SVCPERF` requests, receipts, and semantic-model annotations from `08`/`09` were untouched by this notebook's live run (independently re-confirmed via SQL after) |
| Idempotent/repeatable | Every `UPDATE`/`DELETE` this notebook runs is naturally idempotent — rerunning it against an already-reset state is a safe no-op |
| Verify before declaring success | Cell 9 re-reads every reset target fresh from SQL/Lakehouse rather than trusting that no exception means success |

## Demo narrative support

- **Not shown to an audience.** This is purely an operator/presenter tool run between sessions.
- **Talking point (internal only):** "Run this after a live pass to put every gated request back
  to 'awaiting approval' so tomorrow's demo starts fresh, without touching a single real Purview
  approval or re-running any SQL setup script."
- **A real finding worth knowing before the next redemo:** the two disposable demo objects used
  earlier in the project to prove the retirement/decertification workflows without touching real
  production objects (`OKR-CUSTOPS-LEGACY-NPS`, `DP-LEGACY-CALLCENTER-IVR`) no longer exist in
  the live database — most likely cleared by an environment reseed at some point. Their reset
  *requests* still exist and were correctly reset to `Submitted`, but redemoing those specific
  two workflows would need the objects recreated first (see the runbook's Finding for detail).
  This doesn't affect any of the 3 Purview-native scenarios or the 2 real production objects,
  which all confirmed correctly reverted.

## High-level outcome

By the end of this notebook, the entire G19 demo narrative is back at its pre-decision starting
point — 11 requests `Submitted`, 1 gate back to `Approved`-not-yet-applied, 2 real production
objects reverted to their true baseline, AI Instruction grounding content back to its original
row, and the G18 measure removed — while every Purview-native scenario and real production
object from `08`/`09` remains completely untouched, confirmed via direct SQL query and a fresh
semantic-model reconnect, not just notebook print output.

---

See also: [`docs/10_Notebook_Description.md`](../10_Notebook_Description.md) (validation history) ·
[`docs/runbooks/notebook-validation/10_reset_demo.md`](../runbooks/notebook-validation/10_reset_demo.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
