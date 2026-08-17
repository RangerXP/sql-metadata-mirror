# Notebook 04: `04_writeback_governed_metadata` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/04_Notebook_Description.md` (validation history),
this document catalogs the **live semantic-model artifacts** this notebook writes, evaluates
them against build requirements, and explains how they support the demo narrative. Source
document for demo slide development.

---

## Notebook purpose & role

**What it is:** The semantic-model writeback notebook. It's where governed metadata staged by
notebook 2 (`sm_annotations`) and certified AI content (`ai_metadata`) actually land in the live
`BrookfieldEnercare` semantic model via SemPy Labs TOM — the mechanism that turns "governance
intent" into "what Tom's CRM and Victoria's Power BI report actually show."

**How it's applied:** Runs fourth, always live (`DEMO_MODE = False` in normal operation). Two
merged sections: Cells 1–10 write table/column/measure descriptions and governance/ontology
annotations, verified against a hard TOM read-back after every write; Cells 11–15 write the two
AI grounding annotations (`PBI_AI_Instructions`, `PBI_AI_VerifiedAnswers`) the Fabric Data Agent
reads at query time. Both sections gate on certification (`IsDraft=0 AND IsCertified=1`) so only
approved content ever reaches the live model.

**Use-case delivery objective:** This is the mechanism behind Ci Zhu's Act 3 promise — "there's
only one `_Measures/Net Revenue`... it's owned by me" — and also what lets Tom ask the Data
Agent "show me Maria's furnace status" and get a grounded, correct answer (Act 1).

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| Table descriptions (13 tables) | Semantic-model TOM annotations | Real, substantive descriptions on every dimension/fact table (e.g. `dim_customer`: "Unified customer profile combining account details, active contracts, equipment count, and lifetime billing value") | What a Power BI user or Copilot sees when they hover/query a table — first-line self-service governance |
| Measure descriptions (18 measures) | Semantic-model TOM annotations | Descriptions on every business measure — `Total MRR`, `New/Churned MRR`, `Active Customer Count`, `SLA Breach Count`/`SLA Compliance Rate`, `Warranty Coverage Rate`, `Avg Lifetime Value`, `FCR Rate`, `PP Renewal Rate`, `Avg Handle Time`, `Escalation Rate`, etc. | The single, governed definition of every KPI cited throughout the demo — this is what makes "one measure, one meaning" a technical fact, not a promise |
| Column-level governance annotations | TOM annotations: `Glossary_Term_References`, `Sensitivity_Label`, `Data_Product_Owner`, `CDE_Member_Of` | Applies `sm_annotations`' 77-row reconciliation payload directly onto model columns | Lets a user right-click a column in Power BI and see exactly which glossary term, data product, and sensitivity label govern it |
| `PBI_AI_Instructions` (model annotation) | Semantic-model annotation, Data Agent grounding | Enercare business context: HVAC/water-heater/Protection-Plan/Ecobee services, billing system names (ZUORA/NetSuite/CLARIFY), call-center queue taxonomy, FCR/CSAT/AHT terminology | The "system prompt" equivalent for the Fabric Data Agent — grounds every natural-language answer in real business vocabulary |
| `PBI_AI_VerifiedAnswers` (model annotation) | Semantic-model annotation, Data Agent grounding | Certified Q&A pairs, including the quantified billing-caller/PP-renewal churn correlation (~51% vs. ~86%, a ~35-point gap) | Gives the Data Agent specific, governed, pre-approved answers instead of improvising — this is the artifact that turns a data insight into a repeatable, auditable answer |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Keep semantic model descriptions — Copilot and Fabric Data Agents still need metadata propagated via SemPy Labs" | This notebook is the entire mechanism for that propagation |
| Only certified content reaches the live model | Both sections filter on `IsCertified=1`, matching the KPI writeback path's gate exactly |
| Verified, not assumed, write success | Every write is checked against a hard TOM read-back in the same run — not just a "no exception thrown" assumption |
| AI grounding must be specific and quantified, not generic | Confirmed live 2026-08-17: the PP-renewal verified answer was strengthened from a qualitative hint ("often signals billing confusion") to the actual quantified gap, then re-verified present in the live annotation |

## Demo narrative support

- **Act 1 (Tom's Data Agent query):** `PBI_AI_Instructions` is literally what lets the Data
  Agent understand "PP" means Protection Plan and "AHT" means Average Handle Time when Tom asks
  a natural-language question mid-call.
- **Act 2/3 (the churn insight, governed):** the `PBI_AI_VerifiedAnswers` entry for "renewal
  rate" is a strong slide artifact — it shows the exact same insight Victoria's dashboard
  surfaces is *also* available as a governed, certified, quotable AI answer, not two disconnected
  systems telling two different stories.
- **Talking point:** "Every description, every annotation here passed through a certification
  gate before it ever touched the live model — and we don't just trust the write succeeded, we
  read it back and verify it in the same run."

## High-level outcome

By the end of this notebook, the live `BrookfieldEnercare` semantic model carries real,
governed, certified descriptions on every table, column, and measure, plus the two AI grounding
annotations the Fabric Data Agent depends on — including a specific, quantified business
insight (the billing-caller churn correlation) available both as a verified AI answer and as
the dashboard metric Victoria reviews.

---

See also: [`docs/04_Notebook_Description.md`](../04_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
