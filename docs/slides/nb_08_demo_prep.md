# Notebook 08: `08_validate_governance_evidence` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/08_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The governance health-check notebook — a read-only scorecard proving the stewardship, control,
and AI-readiness state of everything built by notebooks 02–07, plus the first Purview-native
approval workflow observed live through its own API (`GT-SLA`) rather than a SQL-side
simulation. Runs eighth. Cells 1–6 (with 5a) are pure validation, no writes to source data; Cells
7–13 observe and record one real Purview workflow event.

**Why it matters for the demo:** this is the proof point for "we don't just claim governance
maturity, we can show it" — every domain, data product, and CDE has a resolvable steward and
owner, every control check passes, and `GT-SLA` shows a genuine Draft→Published correlation
observed through the Unified Catalog API.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Reads Tier 3 (`lh_metadata`)** for the scorecard; **observes Tier 3 Purview** directly for the `GT-SLA` check. Writes only its own validation-output tables — never a contract tier itself |
| Ontology footprint | Validates the ontology graph's integrity (every OKR→Data Product link resolves, every Key Result resolves to its parent OKR) rather than creating entities |
| Governance workflow | First exercise of a **Purview-native** workflow (Term publish) — approver signs off inside the Purview portal; this notebook only *observes* the resulting `status` field, matching the "governed object's own state is the evidence" principle |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| Stewardship scorecard (18 rows) | Every domain/data-product/CDE with resolved owner, steward, certification status | The single table an auditor asks for first — "prove every governed object has an accountable human" |
| Controls / AI-readiness / ontology validation (4 checks each) | Sensitivity-label coverage, certified-content availability, OKR graph integrity | The "is it safe to let Copilot/Data Agents answer from this" gate |
| Closeout rollup (4-row summary) | Rows checked / action-required / PASS-FAIL per phase | The one table to screenshot for a "governance health: all green" slide |
| `GT-SLA` P1 evidence | Real Draft→Published transition, durably recorded | The demo's one moment of "this actually happened inside Purview, we're reading it back, not asserting it" |

## High-level takeaways (what to say)

- "This is our own governance health check, and this is what a real approval inside the
  Purview portal looks like once read back through the API — not a SQL-side approximation."
- "Every scorecard row traces to a real UPN — Rupal Solanki, Shruthi Srinivas, Ci Zhu — not a
  placeholder. Nothing here is hand-waved."
- "This notebook is the one place we prove the governance contract actually holds, not just
  that it was designed to."

## Demo requirements this notebook satisfies

- Act 3: Ci Zhu's audit answer — "who approved the SLA definition, and how do you know?" —
  answered by a live API read-back, not a screenshot or a claim.
- The stewardship/controls/AI-readiness/ontology "all green" scorecard, usable as an
  opening-frame or closing-payoff slide.
- Proves the Purview-native workflow pattern this demo relies on for `08`/`09` actually works
  end-to-end against a real, named approver.

---

See also: [`docs/08_Notebook_Description.md`](../08_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

