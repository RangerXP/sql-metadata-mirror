# Notebook 10: `10_reset_demo` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain if asked
about it. Not the validation history (`docs/10_Notebook_Description.md`) and not the end-to-end
demo script (a separate demo-design-walkthrough document covers that). This notebook has no
audience-facing slide content of its own — it's the operator utility that keeps every other
notebook's demo repeatable.

---

## Role in the demo

The "reset the stage" operator utility — not part of the demo narrative itself, but the reason
every other approval scenario in this repo can be re-demoed indefinitely without rebuilding
anything. Run tenth, and again between rehearsals or live audiences, never during an actual
presentation. Resets every G19 demo request back to its pre-decision status, reverts the
specific field changes each decision caused, and re-verifies the reset landed.

**Why it matters for the demo:** it protects the integrity of every other notebook's demo
narrative by cleanly separating "real, one-time-proven Purview approvals" (never touched) from
"repeatable G19 demo content" (reset every time) — a presenter never has to worry about whether
today's demo run will still work tomorrow.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 1 → Tier 3 reset** — reverts Tier 1 SQL ledger status and Tier 3 (`lh_metadata`, semantic model) content back to pre-decision state |
| Ontology footprint | Touches no ontology entity's identity (never deletes a Domain/Data Product/Objective/CDE row) — only reverts the *decision fields* (certification, retirement, promotion state) layered on top |
| Governance workflow | Resets **SQL-controlled** workflow state only. Deliberately never touches the 3 Purview-native workflows (`GT-SLA` Term publish, `DP-CUST360` access, `DP-SVCPERF` publish) — those are real, one-time-proven approvals this notebook cannot and does not undo |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| 11 reset unified-ledger requests | Objective/Data Product/CDE/ontology-mapping requests → `Submitted` | Lets a presenter re-run the entire "submit → approve → apply" cycle from scratch |
| Reverted production-object fields | `OKR-SVCDEL-SLA`, `DP-SVCPERF` reverted to true baseline | Presenter can redemo "certify it, recertify it" on the same real objects used elsewhere in the demo |
| `ai_metadata` demo-row cleanup | AI Instruction demo content removed | The Data Agent's grounding content returns to its true pre-G19 baseline |
| `Technician Utilization Rate` measure removed | The G18 measure notebook 09 created | Lets notebook 09's G18 phase recreate it fresh on the next redemo pass |

## High-level takeaways (what to say, if asked)

- "This is an operator tool, not something shown to an audience — it's what lets us redemo the
  same approval story tomorrow without rebuilding anything."
- "It never touches the three real Purview-native approvals — GT-SLA, the Customer 360 access
  request, the Service Performance publish. Those stay proven; only the repeatable demo content
  resets."
- "Everything it does is a status/field revert, never a delete — no governed object row is ever
  removed."

## Demo requirements this notebook satisfies

- Makes the entire G19 approval narrative repeatable for future demo sessions without manual
  SQL cleanup.
- Preserves the 3 Purview-native scenario proofs (notebooks 08/09) across any number of resets.

---

See also: [`docs/10_Notebook_Description.md`](../10_Notebook_Description.md) (artifact catalog + validation pointer, incl. the disposable-demo-object finding) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
