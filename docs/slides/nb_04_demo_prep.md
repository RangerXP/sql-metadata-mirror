# Notebook 04: `04_writeback_governed_metadata` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/04_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The semantic-model writeback notebook — where governed metadata staged by notebook 02
(`sm_annotations`) and certified AI content (`ai_metadata`) actually land in the live
`BrookfieldEnercare` semantic model via SemPy Labs TOM. Runs fourth, always live. Two gated
sections: table/column/measure descriptions + governance annotations (verified against a hard
TOM read-back after every write), and the two AI grounding annotations
(`PBI_AI_Instructions`, `PBI_AI_VerifiedAnswers`) the Fabric Data Agent reads at query time.
Both sections gate on certification (`IsDraft=0 AND IsCertified=1`).

**Why it matters for the demo:** this is the mechanism behind Ci Zhu's Act 3 promise — "there's
only one `_Measures/Net Revenue`... it's owned by me" — and what lets Tom ask the Data Agent
"show me Maria's furnace status" and get a grounded, correct answer (Act 1).

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 3 (consumption)** — the final propagation step, applying Tier 1-sourced, Tier 3-staged (`sm_annotations`) content onto the live semantic model |
| Ontology footprint | Does not create ontology entities — it *propagates* them, attaching `Glossary_Term_References`/`Data_Product_Owner`/`CDE_Member_Of`/ontology annotations from `sm_annotations` onto real model objects |
| Governance workflow | SQL-controlled certification gate — the `IsDraft=0 AND IsCertified=1` filter is the same Draft→Approved certification contract used throughout this repo's SQL-controlled (non-Purview-native) workflows |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| Table & measure descriptions (13 tables, 18 measures) | Real, substantive TOM descriptions on every dimension/fact table and business measure | The single governed definition of every KPI cited throughout the demo —"one measure, one meaning" as a technical fact |
| Column-level governance annotations | `Glossary_Term_References`, `Sensitivity_Label`, `Data_Product_Owner`, `CDE_Member_Of` | Lets a user right-click a column in Power BI and see exactly which glossary term/product/label governs it |
| `PBI_AI_Instructions` | Model-level annotation: Enercare business vocabulary, billing systems, call-center queue taxonomy | The "system prompt" equivalent grounding every Data Agent answer in real business terms |
| `PBI_AI_VerifiedAnswers` | Model-level annotation: certified Q&A incl. the quantified billing-caller/PP-renewal correlation (~51% vs. ~86%) | Turns a data insight into a repeatable, governed, quotable AI answer instead of an improvised one |

## High-level takeaways (what to say)

- "Every description and annotation here passed through a certification gate before it touched
  the live model — and we don't just trust the write succeeded, we read it back and verify it
  in the same run."
- "The AI grounding content isn't generic boilerplate — it includes a specific, quantified
  business fact, certified the same way a KPI is certified."
- "Notice both halves of this notebook — measures and AI grounding — share the exact same
  certification gate. That's what makes drift structurally impossible, not just a policy."

## Demo requirements this notebook satisfies

- Act 1: grounds the Fabric Data Agent's natural-language answers in real business vocabulary
  and Maria-specific facts.
- Act 2/3: makes the churn insight available both as a governed AI answer and as the dashboard
  metric Victoria reviews — one fact, two surfaces, no drift.
- Act 3: the technical basis for Ci Zhu's "one measure, one meaning, one owner" claim.

---

See also: [`docs/04_Notebook_Description.md`](../04_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

