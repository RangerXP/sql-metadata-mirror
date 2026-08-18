# Notebook 09: `09_reconcile_semantic_model` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/09_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The closed-loop payoff notebook — where three separately-approved Purview governance decisions
(a glossary term, a data product access request, a data product publish) actually land as real
metadata inside the live semantic model, plus one brand-new KPI measure born from a governed
source object. Runs ninth. Five phases, each independently gated on its own upstream
approval/receipt, each re-verifying a fresh read-back before marking its request `Completed`.

**Why it matters for the demo:** this is the "does the approval actually change anything a
report consumer sees" proof point — a glossary term's governed definition shows up as a real
measure description, a data product's approved publish shows up as real column annotations, and
a new Key Result gets a real KPI measure, not a slide claiming one exists.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 3 (consumption)** — reads Purview-observed decisions and the SQL ledger, writes only to the live semantic model |
| Ontology footprint | Reconciles decisions already made about the **Glossary Term**, **Data Product**, and (via G18) **Key Result** ontology entities into the semantic model that report consumers actually see |
| Governance workflow | Runs **4 workflows side by side**, deliberately mixing the two patterns this demo uses — see the table below |

**How these decisions originate — Purview-native vs. SQL-controlled:**

| Scenario | Origin | Verification |
|---|---|---|
| GT-SLA (P2) | Real Purview **Term publish** workflow, approved by Ci Zhu | Tier 1 — API-observed `status` field |
| DP-CUST360 access (P3) | Real Purview **Data product access** policy, approved by Victoria Tan | No API exists for this decision — honestly recorded as operator-attested |
| DP-SVCPERF publish (P4) | Real Purview **Data product publish** workflow, approved by Ranbir Singh | Tier 1 — same API-observed pattern as GT-SLA |
| Technician Utilization Rate (G18) | **Not Purview at all** — a pure SQL-controlled pipeline (`@tag` → CDE classify → ontology map → SQL-approved promotion) | Only this repo's own SQL ledger is checked |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| GT-SLA semantic annotations | Governed definition text on `SLA Breach Count`/`SLA Compliance Rate`/`IsSlaBreachFlag` | The measure a report author sees now carries Ci Zhu's approved SLA definition |
| DP-CUST360 access evidence | Victoria Tan's attested approval of Rupal Solanki's access request | The demo's honest answer to "can you always machine-verify an approval" |
| DP-SVCPERF semantic annotations | Governed definition text on `TechnicianId`/`EquipmentType` | Same "approval actually changes the model" proof as GT-SLA, on a different object type |
| `Technician Utilization Rate` measure (new) | A brand-new KPI, tied to `KR-TECH-UTIL` | The full-circle "governed source table becomes a real report KPI" moment |

## High-level takeaways (what to say)

- "Open the `SLA Breach Count` measure in the model and read its description — that's the
  literal, physical result of an approval that happened in Purview, not a screenshot."
- "Purview doesn't expose an API for data-product access decisions, so instead of pretending we
  machine-verified it, we record it as attested, clearly labeled, right next to the parts we
  genuinely did verify. That's a stronger trust story than quietly papering over the gap."
- "`Technician Utilization Rate` started as a plain SQL view someone tagged — by the end of this
  notebook it's a real, governed measure a report author can drag onto a canvas. That's the
  entire discovery-to-KPI pipeline made visible in one demo."
- "Rerun any of these phases against the same request and you get the same receipt,
  re-validated, not a new one fabricated — that's idempotent self-correction, not just a
  one-time write."

## Demo requirements this notebook satisfies

- Act 3: proves each of Ci Zhu's/Victoria's/Ranbir's approvals actually changed the semantic
  model, not just a SQL status flag.
- Demonstrates the honest handling of a real platform limitation (no API for access decisions)
  rather than fabricating false verification.
- The G18 "new SQL source becomes a real semantic-model KPI" full-circle onboarding story.

---

See also: [`docs/09_Notebook_Description.md`](../09_Notebook_Description.md) (artifact catalog + validation pointer, incl. full governance-origin table) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
