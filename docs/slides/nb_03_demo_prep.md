# Notebook 03: `03_build_semantic_model` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/03_Notebook_Description.md` (validation history),
this document catalogs the **analytics-ready artifacts** this notebook produces, evaluates them
against build requirements, and explains how they support the demo narrative. Source document
for demo slide development.

---

## Notebook purpose & role

**What it is:** The dimensional modeling notebook. It transforms the Fabric-mirrored SQL source
tables into a Power BI-ready star schema — the shape the `BrookfieldEnercare` semantic model
consumes for every KPI calculation in the demo.

**How it's applied:** Runs third, always live, no dry-run/live split — it only rebuilds derived
lakehouse tables, never touches SQL or the semantic model directly. Pure reshape/pass-through:
reads mirrored tables, applies surrogate keys and dimensional modeling, writes the star schema
back to `lh_enercare_demo`.

**Use-case delivery objective:** This is where raw operational data becomes *analytics-ready*.
Without this step, Tom's CRM, Victoria's dashboard, and Ci Zhu's KPI citations would have
nothing consistent to query — this notebook is the single reshape point that guarantees every
downstream KPI (FCR, AHT, Net Revenue, Churn, PP Renewal Rate) is calculated from the same
dimensional model, not divergent ad-hoc queries.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| `dim_date` | Star-schema dimension (4,748 rows) | Daily-grain calendar dimension | Time-intelligence backbone for every trend/YoY measure |
| `dim_customer` | Star-schema dimension (51 rows) | Customer master, reshaped for BI consumption | Matches `sqldemo.customers` exactly — Maria's row (51) flows through unchanged |
| `dim_product` | Star-schema dimension (10 rows) | Product/plan dimension | Product-line slicing for contract and revenue analysis |
| `dim_service_account` | Star-schema dimension (57 rows) | Service address/premise dimension | Matches `sqldemo.service_accounts` exactly |
| `dim_equipment` | Star-schema dimension (39 rows) | Equipment registry dimension | Matches `sqldemo.equipment_registry` exactly — Maria's furnace record |
| `fct_billing` | Star-schema fact (587 rows) | Billing transaction fact | Matches `sqldemo.billing_transactions` exactly — powers DP-BILLHEALTH KPIs |
| `fct_service_request` | Star-schema fact (31 rows) | Open/in-progress service request fact | Matches `sqldemo.service_requests` exactly — Maria's SR-2026-051142 |
| `fct_contract_month` | Star-schema fact (1,250 rows) | Monthly MRR contribution per contract | Powers Net MRR / New MRR / Churned MRR measures |
| `dim_cc_agent` | Star-schema dimension (15 rows) | Call-center agent roster | Matches `cc_agents` exactly |
| `dim_cc_billing_adj` | Star-schema dimension (12 rows) | Billing-adjustment category dimension | Matches `ref_cc_billing_adj_category` exactly |
| `fct_cc_interactions` | Star-schema fact (300 rows) | Call-center interaction fact | Exact, unmodified pass-through from source — preserves the billing-caller/PP-renewal correlation bit-for-bit |
| `fct_cc_transcript_turns` | Star-schema fact (3,479 rows) | Transcript-turn fact | Exact, unmodified pass-through from source |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Purview is the governed catalog endpoint; `lh_metadata` is a working store; the semantic model needs propagated metadata" | This notebook builds the *data* layer the semantic model sits on — a prerequisite for `04_writeback_governed_metadata`'s descriptions/annotations to attach to real tables/columns |
| Demo correlation must survive every reshape, not just the original seed | Verified live: billing-caller PP-renewal rate (50.8%) vs. non-billing-caller (85.7%) is bit-for-bit identical to the notebook-1 source, confirming this notebook is a pure reshape with no independent copy that could silently drift |
| Star schema must match source counts exactly (no silent data loss/duplication) | Every table's row count was cross-checked against its `sqldemo` source table during validation — all matched exactly |

## Demo narrative support

- **Foundational, not narrative-visible:** this notebook has no single "moment" in the script
  the way notebook 1's data or notebook 6's lineage does — its value is structural. The slide
  angle is architectural: "one reshape step, one star schema, every KPI in the demo traces back
  to it — this is what makes Tom's CRM number and Victoria's dashboard number the same number."
- **Talking point:** "Notice this notebook does one thing: mirrored SQL in, star schema out. No
  business logic, no governance annotations — just the dimensional shape Power BI needs. That
  separation of concerns is what keeps the pipeline debuggable."

## High-level outcome

By the end of this notebook, a complete, validated Power BI-ready star schema exists in
`lh_enercare_demo`, with every fact/dimension table matching its SQL source exactly and the
notebook-1 churn-correlation insight intact. This is the analytics foundation every KPI in the
Maria Castellanos demo is calculated from.

---

See also: [`docs/03_Notebook_Description.md`](../03_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
