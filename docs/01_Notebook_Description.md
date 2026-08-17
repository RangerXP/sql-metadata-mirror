# `01_setup_source_data` — Notebook Description & Artifact Catalog

**Purpose:** Full descriptive reference for `01_setup_source_data.Notebook` — what it does, what
it consumes/produces, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and its live-validation history.

**Status:** ✅ Live-validated end-to-end 2026-08-17 (see `docs/runbooks/notebook-validation/01_setup_source_data.md`
for the full run evidence). One real bug found and fixed during validation (see below).

**DEMO_MODE:** `False` for the Azure SQL publish section (its normal mode actually publishes).
The lakehouse source-table section and the Phase B Purview-extensions section have no
independent gate — they always run.

**Legacy name(s):** predecessor of `nb_01_setup_demo_environment`, `nb_05a_publish_synthetic_data_to_sql`,
`nb_06a_create_sin_backstop` (pre-consolidation 18-notebook structure).

---

## What it does

Three sections in one notebook:

1. **Lakehouse source tables** — creates the 7 core transactional tables (products, customers,
   service accounts, equipment, contracts, service requests, billing) plus a **call-center
   extension** (`cc_agents`, `fct_cc_interactions`, `fct_cc_transcript_turns`, and the
   intentionally-unmapped `ref_cc_billing_adj_category`) directly in `lh_enercare_demo` via
   PySpark. 50 synthetic Ontario customers.
2. **Publish to Azure SQL** (`DEMO_MODE = False`) — publishes the 7 source tables from
   `lh_enercare_demo` into Azure SQL (`sqldemo`), making SQL the authoritative mirrored source.
3. **Phase B — Purview demo extensions (CELL B0–B7)** — applies PII/classifier extensions (DOB,
   partial SIN, GPS, payment partials) and 6 new tables (`employees`, `service_zones`,
   `customer_consents`, `customer_complaints`, `data_owners_directory`, `audit_data_access`),
   seeds Maria-specific consent/complaint/audit rows, backfills and spot-checks Luhn-valid SINs,
   and grants the Purview managed identity read access. **As of 2026-08-16, this notebook no
   longer creates or seeds governance metadata** (domains, data products, glossary, CDEs, roles,
   labels, OKRs) — that duplicated, drifted-behind copy was removed. CELL B4A now only
   *verifies* the SQL-first governance metadata scripts (below) have already been applied to
   `sqldemo`, raising a clear `RuntimeError` naming them if `dbo.governance_domains` is empty.

## Artifact catalog

### SQL inputs consumed / verified as prerequisite

| Script | What it provides to this notebook |
|---|---|
| `sql/01_source_data/02_sub2_sql_source_schema.sql` | The 7-table transactional core schema this notebook's Cell "Publish to Azure SQL" section writes into. |
| `sql/02_metadata_foundation/06_purview_metadata_schema.sql`, `07_seed_purview_metadata.sql`, `11_ontology_okr_schema.sql`, `12_seed_ontology_okrs.sql` | **Prerequisite only** (CELL B4A) — this notebook no longer creates this content itself; it verifies these 4 scripts were already applied. |

### Tables/artifacts this notebook produces

| Target | Where | Rows (live-verified 2026-08-17) |
|---|---|---|
| `customers`, `service_accounts`, `equipment_registry`, `contracts`, `service_requests`, `billing_transactions`, `products` | `lh_enercare_demo` (lakehouse) | 50 / 56 / 39 / 57 / 31 / 587 / — |
| `cc_agents`, `fct_cc_interactions`, `fct_cc_transcript_turns`, `ref_cc_billing_adj_category` | `lh_enercare_demo` (lakehouse) | 15 / 300 / 3,479 / 12 |
| Same 7 core tables (mirrored copy) + `employees`, `service_zones`, `customer_consents`, `customer_complaints`, `data_owners_directory`, `audit_data_access` | Azure SQL `sqldemo` | 51 (50 + Maria) / 57 / 39 / 57 / 31 / 587 / 19 / 8 / 124 / 19 / 13 / 204 |

`ref_cc_billing_adj_category` is deliberately unmapped to the semantic model/curated metadata —
an intentional "orphaned demo asset" for governance-completeness talking points, not a gap.

## Demo fit

Foundational — nothing else runs without this. Not shown live; it's the "before the curtain"
step, except for the call-center correlation, which is exactly what Tom's Data Agent grounding
surfaces in Act 1.

## Talking points

"This is the synthetic Enercare universe — real Ontario geography, real FSAs, a realistic
customer/contract/service/call-center mix, entirely synthetic data — and one correlation baked
in on purpose: customers who call about billing are meaningfully less likely to renew their
protection plan."

## Live-validation findings

| Finding | Detail | Status |
|---|---|---|
| **Cohort-variance issue in the PP-renewal correlation** | The original random generation only produced a robust "billing callers renew less" gap for the 14 hand-designed `CORR_CUSTOMERS` (target ~57%). Any broader query (any customer who ever called billing, vs. never) showed only a weak, sometimes-inverted gap (~54.5% vs ~60%), because the other 272 randomly-generated interaction rows didn't condition `pp_renewal_outcome` on billing-caller status at all. | ✅ **Fixed 2026-08-17.** The remaining population now computes the full set of billing-callers first, then applies distinctly different acceptance-weight distributions (`PP_RENEWAL_WEIGHTS_BILLING_CALLER` vs `PP_RENEWAL_WEIGHTS_BASELINE`) based on that status. Re-verified live: billing-caller rate **50.8%** (n=65) vs non-billing-caller rate **85.7%** (n=7) — a robust ~35-point gap that holds for any reasonable cohort query, not just the designed 14. The notebook's own "Validate demo correlation" cell now asserts this gap holds on every run (`RuntimeError` if it regresses). |
| **Maria's customer count (51 vs expected 50)** | Investigated as a possible duplication bug. | Not a bug — confirmed no duplicate `customer_id`s; Maria Castellanos (`customer_id=18374622`) is a deliberate 51st row added by the Phase B seed on top of the 50 generic synthetic customers. |
| **Governance-metadata duplication (session-wide finding)** | This notebook previously embedded its own stale copy of the governance metadata schema/seed SQL. | ✅ **Fixed 2026-08-16** — see `docs/sql-prep-catalog.md` addendum. |

## Dependencies / downstream consumers

- Azure SQL `sqldemo` (published here) is mirrored into Fabric and consumed by
  `02_build_metadata_foundation` and `03_build_semantic_model`.
- The Phase B PII/consent/complaint tables feed Purview scans and `05_publish_governance_domains`
  / `06_publish_glossary_and_lineage`'s CDE/classification bindings.
- The call-center `fct_cc_interactions`/`fct_cc_transcript_turns` correlation is the raw signal
  that `04_writeback_governed_metadata`'s AI-grounding annotations need to surface correctly to
  the Data Agent (Act 1) — verify this dependency when validating notebook 4.

---

See also: [`02_Notebook_Description.md`](./02_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/01_setup_source_data.md`](./runbooks/notebook-validation/01_setup_source_data.md) ·
[`docs/sql-prep-catalog.md`](./sql-prep-catalog.md)

