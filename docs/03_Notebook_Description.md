# `03_build_semantic_model` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `03_build_semantic_model.Notebook` — what it does, what
it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/03_build_semantic_model.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** No gate — single straight-through run every time (it only rebuilds derived
lakehouse tables, never SQL or the semantic model itself, so there's no live/dry-run split).

**Legacy name(s):** predecessor of `nb_03_pbi_star_schema` (pre-consolidation 18-notebook
structure).

---

## What it does

Builds the Power BI-ready dimensional star schema (`dim_date`, core dimensions,
`dim_equipment`, `fct_billing`, `fct_service_request`, `fct_contract_month`, and the
call-center fact/dimension tables) on top of the Fabric-mirrored SQL source in one
straight-through run.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| Mirrored `dbo.customers`/`service_accounts`/`equipment_registry`/`contracts`/`service_requests`/`billing_transactions`/`products` (from Azure SQL `sqldemo`, published by `01_setup_source_data`) | Core dimension/fact builds |
| `lh_enercare_demo.cc_agents`/`fct_cc_interactions`/`fct_cc_transcript_turns`/`ref_cc_billing_adj_category` (written directly by `01_setup_source_data`, not mirrored through SQL) | Call-center dimension/fact builds |

### Outputs produced (all in `lh_enercare_demo`)

| Table | Rows |
|---|---|
| `dim_date` | 4,748 |
| `dim_customer` | 51 |
| `dim_product` | 10 |
| `dim_service_account` | 57 |
| `dim_equipment` | 39 |
| `fct_billing` | 587 |
| `fct_service_request` | 31 |
| `fct_contract_month` | 1,250 |
| `dim_cc_agent` | 15 |
| `dim_cc_billing_adj` | 12 |
| `fct_cc_interactions` | 300 (pass-through, unmodified) |
| `fct_cc_transcript_turns` | 3,479 (pass-through, unmodified) |

## Demo fit

This produces the actual tables the `BrookfieldEnercare` semantic model and every downstream
KPI/measure are built on — the physical backbone of Act 2 (Victoria's dashboard).

## Talking points

"Same dimensional model whether you're a data engineer looking at Delta tables or an executive
looking at a Power BI report."

## Dependencies / downstream consumers

- Depends on `01_setup_source_data` having published to `sqldemo` and the mirror having synced.
- The star schema tables here are what `04_writeback_governed_metadata` annotates and what the
  `BrookfieldEnercare` semantic model's Power BI report is built on.

---

See also: [`02_Notebook_Description.md`](./02_Notebook_Description.md) ·
[`04_Notebook_Description.md`](./04_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/03_build_semantic_model.md`](./runbooks/notebook-validation/03_build_semantic_model.md)
