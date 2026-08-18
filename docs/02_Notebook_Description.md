# `02_build_metadata_foundation` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `02_build_metadata_foundation.Notebook` — what it does,
what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/02_build_metadata_foundation.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** No single top-level flag — two merged sections, each unconditional (always run).

**Legacy name(s):** predecessor of `nb_02_metadata_pipeline_demo` (thin `@tag` reader, now
retired), `nb_07a_ingest_customer_files`, `nb_07b_merge_customer_metadata`
(pre-consolidation 18-notebook structure).

---

## What it does

Two originally-separate notebooks merged into one file:

- **Cells 1–9 — governance ingestion** (formerly `nb_07a_ingest_customer_files`): reads
  `domain-charter.csv`, `data-product-catalog.csv`, `glossary-master.csv`, `cde-catalog.csv`,
  `role-directory.csv`, `label-policy.csv`, mirrored `governance_change_requests`, and the
  ontology/OKR tables into `lh_metadata.dbo.*` for the Purview-publish notebooks to read.
- **Cells 10–16 — semantic reconciliation** (formerly `nb_07b_merge_customer_metadata`):
  cross-references glossary/CDE/data-product/label associations against the semantic model's
  real table/column names, resolves aliases, and writes the reconciled `sm_annotations` working
  table that `04_writeback_governed_metadata` depends on.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `purview/domain-charter.csv`, `data-product-catalog.csv`, `glossary-master.csv`, `cde-catalog.csv`, `role-directory.csv`, `label-policy.csv` | Cells 3–8 (via `load_metadata_dataset()`, SQL-mirror-only — CSV direct-read is intentionally disabled) |
| Mirrored `dbo.governance_domains`/`governance_data_products`/`governance_glossary_terms`/`governance_cdes`/`governance_role_assignments`/`governance_label_assignments`/`governance_change_requests`/`governance_okrs`/`governance_okr_key_results`/`governance_okr_data_products` in Azure SQL (`sqldemo`), populated by `sql/02_metadata_foundation/06_purview_metadata_schema.sql` + `07_seed_purview_metadata.sql` + `11_ontology_okr_schema.sql` + `12_seed_ontology_okrs.sql` | The actual SQL-mirror source `try_load_sql_dataset()` reads for Cells 3–8c |
| The live `BrookfieldEnercare` semantic model's table/column inventory (via `sm_annotations`' own history, since live SemPy inventory is disabled — `USE_SEMPY_INVENTORY = False`) | Cell 12's binding-resolution targets |

### Outputs produced

| Target | Rows |
|---|---|
| `lh_metadata.dbo.domains` | 3 |
| `lh_metadata.dbo.data_products` | 3 |
| `lh_metadata.dbo.glossary_terms` | 35 |
| `lh_metadata.dbo.cdes` | 12 |
| `lh_metadata.dbo.role_assignments` | 48 |
| `lh_metadata.dbo.label_assignments` | 9 |
| `lh_metadata.dbo.governance_change_requests` | 10 |
| `lh_metadata.dbo.okrs` / `okr_key_results` / `okr_data_products` | 3 / 5 / 3 |
| `lh_metadata.dbo.sm_annotations` (rebuilt fresh, `mode("overwrite")`) | 77 (`Glossary_Term_References`=62, `Sensitivity_Label`=7, `Data_Product_Owner`=6, `CDE_Member_Of`=2) |
| `lh_metadata.dbo.nb02_diagnostics_log` | Real exception + traceback capture per named stage, since Fabric's job API exposes no cell-level detail |

## Demo fit

Invisible plumbing — keeps the governance content Purview publishes, and the annotations the
semantic model receives, in sync with the SQL source of truth.

## Talking points

"Every governance object — domain, product, term, CDE — has one SQL source row; this notebook
is the sync-and-reconcile step into the Fabric/semantic-model layer."

## Dependencies / downstream consumers

- Depends on `01_setup_source_data` having run first (SQL-mirror-only ingestion; the CSV direct
  fallback is intentionally disabled).
- `04_writeback_governed_metadata` Cell 8 hard-depends on `sm_annotations` (raises
  `RuntimeError("sm_annotations is empty")` if it's missing) — this dependency is now satisfied
  by a normal end-to-end run of this notebook again.
- `05_publish_governance_domains` and `06_publish_glossary_and_lineage` read the
  `domains`/`data_products`/`glossary_terms`/`cdes`/`label_assignments` tables this notebook
  populates.
- The GT-011–035 placeholder-name gap should be checked again when validating `06`, since that
  notebook publishes these same term names to Purview.

---

See also: [`01_Notebook_Description.md`](./01_Notebook_Description.md) ·
[`03_Notebook_Description.md`](./03_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/02_build_metadata_foundation.md`](./runbooks/notebook-validation/02_build_metadata_foundation.md) ·
[`docs/sql-prep-catalog.md`](./sql-prep-catalog.md)
