# `02_build_metadata_foundation` — Notebook Description & Artifact Catalog

**Purpose:** Full descriptive reference for `02_build_metadata_foundation.Notebook` — what it
does, what it consumes/produces, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and its live-validation history.

**Status:** ✅ Live-validated end-to-end 2026-08-17, after finding and fixing a real bug (see
`docs/runbooks/notebook-validation/02_build_metadata_foundation.md` for the full run evidence,
including 4 failed attempts and the investigation trail).

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

A leftover `mssparkutils.notebook.exit()` from before Cells 10–16 were merged in made them
unreachable dead code until fixed 2026-08-16 — this was **the first-ever live run where Cells
10–16 could possibly execute**, which is why the subsequent bug-hunt (below) was so involved:
this reconciliation logic had never actually run as part of the consolidated notebook before.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `purview/domain-charter.csv`, `data-product-catalog.csv`, `glossary-master.csv`, `cde-catalog.csv`, `role-directory.csv`, `label-policy.csv` | Cells 3–8 (via `load_metadata_dataset()`, SQL-mirror-only — CSV direct-read is intentionally disabled) |
| Mirrored `dbo.governance_domains`/`governance_data_products`/`governance_glossary_terms`/`governance_cdes`/`governance_role_assignments`/`governance_label_assignments`/`governance_change_requests`/`governance_okrs`/`governance_okr_key_results`/`governance_okr_data_products` in Azure SQL (`sqldemo`), populated by `sql/02_metadata_foundation/06_purview_metadata_schema.sql` + `07_seed_purview_metadata.sql` + `11_ontology_okr_schema.sql` + `12_seed_ontology_okrs.sql` | The actual SQL-mirror source `try_load_sql_dataset()` reads for Cells 3–8c |
| The live `BrookfieldEnercare` semantic model's table/column inventory (via `sm_annotations`' own history, since live SemPy inventory is disabled — `USE_SEMPY_INVENTORY = False`) | Cell 12's binding-resolution targets |

### Outputs produced

| Target | Rows (live-verified 2026-08-17, post-fix) |
|---|---|
| `lh_metadata.dbo.domains` | 3 |
| `lh_metadata.dbo.data_products` | 3 |
| `lh_metadata.dbo.glossary_terms` | 35 |
| `lh_metadata.dbo.cdes` | 12 |
| `lh_metadata.dbo.role_assignments` | 48 |
| `lh_metadata.dbo.label_assignments` | 9 |
| `lh_metadata.dbo.governance_change_requests` | 8 |
| `lh_metadata.dbo.okrs` / `okr_key_results` / `okr_data_products` | 3 / 5 / 3 |
| `lh_metadata.dbo.sm_annotations` (rebuilt fresh, `mode("overwrite")`) | 77 (`Glossary_Term_References`=62, `Sensitivity_Label`=7, `Data_Product_Owner`=6, `CDE_Member_Of`=2) |
| `lh_metadata.dbo.nb02_diagnostics_log` (new, added during this session's debugging) | Diagnostic-only — captures the real Python/JVM exception per named stage on any future failure, since Fabric's REST API never exposes cell-level detail |

## Demo fit

Invisible plumbing — keeps the governance content Purview publishes, and the annotations the
semantic model receives, in sync with the SQL source of truth.

## Talking points

"Every governance object — domain, product, term, CDE — has one SQL source row; this notebook
is the sync-and-reconcile step into the Fabric/semantic-model layer."

## Live-validation findings

This notebook required 5 live run attempts to reach `Completed`, because Cells 10–16 had never
executed successfully before (see "What it does" above). Fabric's Job Instance API reports only
a generic `System_Cancelled_Session_Statements_Failed` message for every failure, with no
per-cell detail — the real cause had to be found by adding custom diagnostic instrumentation
(a `_log_nb02_diagnostic(stage, error)` helper, matching the pattern already used in
`06_publish_glossary_and_lineage`/`07_apply_approved_changes`, writing the real exception +
traceback to `dbo.nb02_diagnostics_log` before re-raising).

| Finding | Detail | Status |
|---|---|---|
| **Dead-code bug: Cells 10–16 unreachable** | An unconditional `mssparkutils.notebook.exit()` at the end of Cell 9 — correct for the original standalone notebook, which ended at that line, but never removed once the reconciliation cells were appended during consolidation. | ✅ **Fixed 2026-08-16.** `exit()` call removed. |
| **Root cause of the 4 subsequent failures: stale Spark catalog schema** | `Cell 14`'s `glossary_df.collect()` failed with `Py4JJavaError: IllegalStateException: Couldn't find parent_term_code#42033 in [...]` — Spark's cached logical plan expected a `parent_term_code` column that no longer exists in the physical Delta table (replaced by `approved_at` from a later schema migration). Cell 10's `_read_table()` never got the `refreshTable()` fix that `05`/`06` already had. | ✅ **Fixed 2026-08-17.** Added `spark.catalog.refreshTable()` before every `spark.table()` read in Cell 10's `_read_table()`, and pruned `glossary_df`/`cde_df`/`data_products_df`/`labels_df` to only the columns Cell 14 actually reads (same proven pattern as `06_publish_glossary_and_lineage`). Confirmed live: successful run added zero new rows to `nb02_diagnostics_log`. |
| **Red herring investigated first: expensive Delta-path probing** | `try_load_sql_dataset()` (Cells 1–9) tries a large combinatorial set of physical `abfss://` Delta paths before falling back to catalog-based lookup — worth avoiding on its own merits, but proven **not** the actual cause (still failed after reordering catalog-lookup first, until the real Cell 14 fix landed). | ✅ **Reordered anyway** (catalog lookup now tried first) — cheaper in the common case, and defensible independent of the real bug. |
| **Glossary term placeholder names (source-data quality gap, not a notebook bug)** | Of the 35 glossary terms, only `GT-001`–`GT-010` have real curated `term_name` values; `GT-011`–`GT-035` (25 terms) carry a generic placeholder — literally `"Governance Term 16"`, etc. — in the underlying `dbo.glossary_terms` source data. | ⚠️ **Not fixed here** — this notebook correctly reads and reconciles whatever the SQL source contains; the placeholder names are upstream seed-content that needs real curated definitions (likely in `sql/02_metadata_foundation/07_seed_purview_metadata.sql`). Flagged for the broader artifact-cataloging pass. |
| **Proactive fix applied elsewhere the same day** | Given this bug class, audited all 10 notebooks for the same missing-`refreshTable()` pattern. | ✅ `04_writeback_governed_metadata` and `08_validate_governance_evidence` were also vulnerable and fixed proactively (not yet exercised by a live failure in those notebooks — see their own docs). |

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
