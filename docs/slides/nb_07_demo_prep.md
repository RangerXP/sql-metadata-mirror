# Notebook 07: `07_apply_approved_changes` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/07_Notebook_Description.md` (validation history),
this document catalogs the **governance artifacts this notebook mutates**, evaluates them
against build requirements, and explains how they support the demo narrative. Source document
for demo slide development.

---

## Notebook purpose & role

**What it is:** The apply-on-approve dispatcher — the notebook that turns an *Approved*
governance decision into an actual, live change in `lh_metadata`. It's the mechanism behind
every "someone approved this, now watch the data change" moment in the demo.

**How it's applied:** Runs seventh, always live (`DEMO_MODE = False`). Reads directly from the
`sub2` SQL source (never the lakehouse mirror, to avoid acting on stale status), validates each
pending request carries proper governance tagging, dispatches by request type, and stamps each
processed row `Applied`.

**Use-case delivery objective:** This is the technical proof behind Ci Zhu's Act 3 claim that
every governed change goes through the same approval contract — not a one-off manual edit, but
a repeatable, auditable, SQL-driven workflow that a real governance team would actually use.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| KPI re-certifications | `lh_metadata.kpi_metadata` mutation | Version bump, formula/threshold/description updates for an approved KPI change (e.g. SLA Breach Rate's auto-suppression fix closing the Maria repeat-complaint pattern from Act 2) | Demonstrates a KPI definition correction traced directly to a real operational finding |
| Verified-answer certifications | `lh_metadata.ai_metadata` insert (`RecordType='verified_answer'`) | New certified Q&A content (e.g. the no-heat SLA credit-policy answer drafted from Tom's actual call script) | Shows a real agent interaction becoming governed, reusable AI-answer content |
| CDE classifications | New CDE registration (e.g. `CDE-COMPLAINTREF`) | Registers a new Critical Data Element with its sensitivity classification | Demonstrates the approval gate for a brand-new governance object, not just an edit |
| Glossary term publications | New glossary term registration (e.g. `GT-SLA`) | Formally publishes a term that had been used narratively but never registered | Closes the gap between "the term everyone says" and "the term that's actually governed" |
| AI instruction certifications/rollbacks | `lh_metadata.ai_metadata` insert/version management | Certifies a new AI instruction (with optional future-effective date) or rolls back a flawed edit to a prior certified version | The escalation-guidance rollback scenario is a genuine "governance catches a mistake" story — a real safety clause that was accidentally dropped, caught, and reverted |
| `sqldemo.dbo.governance_change_requests` (audit trail) | Durable status/timestamp record | `status`/`applied_at` stamped on every processed request | The complete, queryable proof of who requested what, who approved it, and when it took effect — this table alone can answer an auditor's "show me every governance change and who approved it" question |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Closed-loop governance: every approval produces durable evidence" | `governance_change_requests`' `status`/`applied_at` columns are exactly that evidence, independently queryable without trusting notebook print output |
| SQL-controlled approval, not UI-only | Approval happens by updating a SQL row's status — matching the design decision that SQL, not a bespoke UI, drives the demo's approval mechanics |
| Governance tagging must be present on every request (found during validation) | Confirmed via live testing 2026-08-17 that `domain`/`owner`/`sensitivity`/`semantic_role`/`business_use` are mandatory on every request regardless of type; fixed all 8 seed scenarios to include them so future reseeds remain dispatchable |
| Rollback must be a first-class, auditable operation, not a manual fix | `AI_INSTRUCTION_ROLLBACK` dynamically resolves the prior certified version with no hardcoded IDs — proven live via the GCR-AII-003/004 pair and the author's own GCR-VALTEST-001/-REVERT test cycle |

## Demo narrative support

- **Act 2/3 crossover:** the SLA Breach Rate KPI re-certification is a strong slide artifact —
  it's the technical closure of the exact operational bug (auto-suppressed dispatch) Ranbir
  found in Act 2, now formally certified as a KPI definition change with Ci Zhu's approval.
- **The rollback story:** GCR-AII-003 (a well-intentioned but flawed edit that drops a safety
  clause) → GCR-AII-004 (the catch and revert) is a compelling, self-contained narrative beat for
  a slide about governance *catching mistakes*, not just approving good changes.
- **Talking point:** "One dispatcher, several request types, all sharing the same
  Draft→Approved→Applied contract — this is what makes the closed loop closed."

## High-level outcome

By the end of this notebook, every currently-approved governance change request has been
applied to `lh_metadata` and stamped with a durable, auditable record of when and by whom. Live
validation on 2026-08-17 went further than a routine run: a real apply-then-revert test cycle
confirmed the mechanism works today (not just historically), and surfaced a genuine build gap
— undocumented mandatory governance tags — that's now fixed across all seed scenarios.

---

See also: [`docs/07_Notebook_Description.md`](../07_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
