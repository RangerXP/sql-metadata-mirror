# Notebook 03: `03_build_semantic_model` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/03_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The dimensional modeling notebook. Transforms the Fabric-mirrored SQL source tables into a
Power BI-ready star schema — the shape the `BrookfieldEnercare` semantic model consumes for
every KPI in the demo. Runs third, always live, pure reshape/pass-through (no business logic,
no governance annotations).

**Why it matters for the demo:** without this step, Tom's CRM, Victoria's dashboard, and Ci
Zhu's KPI citations would have nothing consistent to query. This is the single reshape point
that guarantees every downstream KPI (FCR, AHT, Net Revenue, Churn, PP Renewal Rate) is
calculated from the same dimensional model, not divergent ad-hoc queries.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 3 (consumption)** — reshapes Tier 1 data (via its Tier 2 mirrored copy) into an analytics-ready shape; writes no governance metadata itself |
| Ontology footprint | None — this notebook operates entirely on operational/transactional data, not the governance ontology |
| Governance workflow | None — a pure, unconditional reshape step with no approval gate |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| `dim_date`, `dim_customer`, `dim_product`, `dim_service_account`, `dim_equipment` | Core star-schema dimensions, each matching its `sqldemo` source table exactly | Maria's customer/equipment rows flow through unchanged — same identity, analytics-ready shape |
| `fct_billing`, `fct_service_request`, `fct_contract_month` | Core star-schema facts | Power DP-BILLHEALTH KPIs and Net/New/Churned MRR measures Victoria reviews |
| `dim_cc_agent`, `dim_cc_billing_adj`, `fct_cc_interactions`, `fct_cc_transcript_turns` | Call-center dimension/fact tables, `fct_cc_interactions`/`fct_cc_transcript_turns` passed through unmodified | Preserves the billing-caller/PP-renewal correlation bit-for-bit from notebook 01 |

## High-level takeaways (what to say)

- "This notebook does one thing: mirrored SQL in, star schema out. No business logic, no
  governance annotations — just the dimensional shape Power BI needs. That separation of
  concerns is what keeps the pipeline debuggable."
- "Every fact and dimension table here matches its SQL source row-for-row — there's no silent
  data loss or duplication possible in this reshape step."
- "One reshape step, one star schema — every KPI in the demo traces back to it. That's what
  makes Tom's CRM number and Victoria's dashboard number the same number."

## Demo requirements this notebook satisfies

- The single analytics-ready data foundation every KPI (FCR, AHT, Net Revenue, Churn, PP
  Renewal Rate) in Acts 1–3 is calculated from.
- Confirms the Act 1/2 churn correlation survives the reshape unchanged — no independent copy
  that could silently drift from the source.

---

See also: [`docs/03_Notebook_Description.md`](../03_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

