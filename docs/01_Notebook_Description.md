# `01_setup_source_data` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `01_setup_source_data.Notebook` — what it does, what it
consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/01_setup_source_data.md`.

**Status:** ✅ Validated.

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

| Target | Where | Rows |
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
[`03_Notebook_Description.md`](./03_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/01_setup_source_data.md`](./runbooks/notebook-validation/01_setup_source_data.md) ·
[`docs/sql-prep-catalog.md`](./sql-prep-catalog.md)

