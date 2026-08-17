# `03_build_semantic_model` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-17.

## Purpose being validated

Builds the Power BI-ready dimensional star schema (`dim_date`, core dimensions,
`dim_equipment`, `fct_billing`, `fct_service_request`, `fct_contract_month`, and the
call-center fact/dimension tables) on top of the Fabric-mirrored SQL source, in one
straight-through run with no dry-run/live split (it only rebuilds derived lakehouse tables,
never SQL or the semantic model itself).

## Run record

| Field | Value |
|---|---|
| Notebook item ID | `442a35eb-772a-42e3-9cb8-1586e3d58312` |
| Job ID | `cb92a1b1-3036-4426-afb5-b8243b999257` |
| Start (UTC) | 2026-08-17T06:27:36.52 |
| End (UTC) | 2026-08-17T06:34:47.88 (≈7.2 min) |
| Status | `Completed` |
| Failure reason | `null` |

No perceptible cold-start reduction from enabling `highConcurrency.notebookPipelineRunEnabled`
on this first run after the toggle — plausible causes: first run after enabling still needed a
fresh session, or the prior job's session had already expired (`sessionTimeoutInMinutes: 20`,
and this run started well outside that window from the last one). Will observe across the
remaining notebooks in this sequence to see if session reuse kicks in for back-to-back runs.

## Data write-out confirmation

| Table | Rows | Source cross-check |
|---|---|---|
| `dim_date` | 4,748 | Reasonable daily-grain date dimension |
| `dim_customer` | 51 | Matches `sqldemo.customers` (50 + Maria) ✅ |
| `dim_product` | 10 | — |
| `dim_service_account` | 57 | Matches `sqldemo.service_accounts` ✅ |
| `dim_equipment` | 39 | Matches `sqldemo.equipment_registry` ✅ |
| `fct_billing` | 587 | Matches `sqldemo.billing_transactions` ✅ |
| `fct_service_request` | 31 | Matches `sqldemo.service_requests` ✅ |
| `fct_contract_month` | 1,250 | Monthly-grain expansion of contracts — plausible |
| `dim_cc_agent` | 15 | Matches `cc_agents` ✅ |
| `dim_cc_billing_adj` | 12 | Matches `ref_cc_billing_adj_category` ✅ |
| `fct_cc_interactions` | 300 | Exact match to source, unmodified ✅ |
| `fct_cc_transcript_turns` | 3,479 | Exact match to source, unmodified ✅ |

## Maria Castellanos north-star use-case match

- ✅ `dim_customer` carries Maria's 51st row through correctly.
- ✅ **Critical check**: the notebook-1 cohort-normalization fix (billing-caller vs
  non-billing-caller PP-renewal gap) propagated through the star schema **unchanged**:
  billing-caller rate **50.8%** vs non-billing-caller rate **85.7%**, identical to the source
  lakehouse. Confirms notebook 3 is a pure pass-through/reshape for this data, not an
  independent copy that could silently drift from the source.

## Issues encountered

None. Job completed on the first attempt.
