# Notebook 07: `07_apply_approved_changes` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/07_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The apply-on-approve dispatcher — turns an *Approved* governance decision into an actual, live
change in `lh_metadata`. Runs seventh, always live. Reads directly from the `sub2` SQL source
(never the lakehouse mirror, to avoid acting on stale status), validates each pending request
carries proper governance tagging, dispatches by request type, and stamps each processed row
`Applied`.

**Why it matters for the demo:** this is the technical proof behind Ci Zhu's Act 3 claim that
every governed change goes through the same approval contract — not a one-off manual edit, but
a repeatable, auditable, SQL-driven workflow a real governance team would actually use.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 1 → Tier 3 bridge** — reads the Approved decision directly from the Tier 1 SQL contract (`sub2`) and applies it into `lh_metadata` (Tier 3) |
| Ontology footprint | Does not create new ontology entities — it applies **content changes** governed objects already reference (KPI definitions, verified answers, CDE/glossary registrations, AI instructions) |
| Governance workflow | The **SQL-controlled workflow**, exactly: `Draft → PendingApproval → Approved → Applied`, dispatched by `request_type`. This is the non-Purview-native half of this repo's two governance-workflow patterns (contrast with `08`/`09`'s Purview-native Term/Data-Product workflows) |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| KPI re-certifications | Version bump / formula / threshold updates in `kpi_metadata` | e.g. the SLA Breach Rate auto-suppression fix — a KPI correction traced directly to a real operational finding from Act 2 |
| Verified-answer / AI-instruction certifications, rollbacks | New certified `ai_metadata` content or a reverted flawed edit | The escalation-guidance rollback is a genuine "governance catches a mistake" story — a real safety clause dropped, caught, and reverted |
| New CDE / glossary term registrations | New governed objects, not just edits | Demonstrates the approval gate for brand-new governance objects |
| `governance_change_requests` audit trail | `status`/`applied_at` stamped on every processed request | Answers "show me every governance change and who approved it" directly, without trusting notebook print output |

## High-level takeaways (what to say)

- "One dispatcher, several request types, all sharing the same Draft→Approved→Applied contract
  — this is what makes the closed loop closed."
- "Approval happens by updating one SQL row's status — this is SQL-controlled governance, the
  other half of this demo's two workflow patterns alongside the Purview-native ones."
- "The rollback path resolves the prior certified version dynamically, with no hardcoded ID —
  proven live with a real flawed-edit-then-catch-then-revert cycle."

## Demo requirements this notebook satisfies

- Act 2/3: the SLA Breach Rate KPI re-certification closes the exact operational bug found in
  Act 2, now formally approved and applied.
- Act 3: the durable, queryable audit trail Ci Zhu points to for "who approved what, and when."
- Demonstrates governance catching and reverting its own mistake (the escalation-guidance
  rollback), not just approving good changes.

---

See also: [`docs/07_Notebook_Description.md`](../07_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

