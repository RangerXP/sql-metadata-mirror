# Notebook 10 — Pending Individual-File Split

**Status:** Temporary holding document. `docs/01_Notebook_Description.md` through
`docs/09_Notebook_Description.md` have been split into individual per-notebook files (one
file per notebook, matching the naming convention `NN_Notebook_Description.md`), each enriched
with artifact cataloging and live-validation findings as that notebook is worked through the
validation sequence (`docs/runbooks/notebook-validation/`).

The content below for notebook 10 has not yet been split out or enriched with live-run
evidence — it's preserved verbatim from the prior consolidated `01_Notebook_Description.md` so
nothing is lost. Once it's reached in the validation sequence, its section here will be
extracted into its own `10_Notebook_Description.md` (matching the pattern of 01–09) and removed
from this file.

---

## Legacy `nb_XX` → current notebook name mapping

For cross-referencing older dated docs that still cite the pre-consolidation names:

| Current notebook | Predecessor(s) (`nb_XX`) |
|---|---|
| `01_setup_source_data` | `nb_01_setup_demo_environment`, `nb_05a_publish_synthetic_data_to_sql`, `nb_06a_create_sin_backstop` |
| `02_build_metadata_foundation` | `nb_02_metadata_pipeline_demo` (thin `@tag` reader), `nb_07a_ingest_customer_files`, `nb_07b_merge_customer_metadata` |
| `03_build_semantic_model` | `nb_03_pbi_star_schema` |
| `04_writeback_governed_metadata` | `nb_04_sempy_writeback`, `nb_04a_extend_metadata_schema`, `nb_05_push_qa_verified_answers` |
| `05_publish_governance_domains` | `nb_07_publish_to_purview` (domains/data products portion) |
| `06_publish_glossary_and_lineage` | `nb_08_purview_glossary_cde`, `nb_09_purview_labels_lineage` |
| `07_apply_approved_changes` | `nb_11_gated_governance_sync` |
| `08_validate_governance_evidence` | `nb_10_purview_stewardship_ai`, `nb_12_purview_workflow_sync` (P1) |
| `09_reconcile_semantic_model` | `nb_13_semantic_reconcile` (P2), `nb_14_purview_access_sync` (P3), `nb_15_purview_dataproduct_sync` (P4 publish), `nb_16_dataproduct_semantic_reconcile` (P4 reconcile), `nb_17_g18_semantic_promotion` (G19 semantic promotion) |
| `10_reset_demo` | `nb_18_demo_reset` |

---


## Phase 4 — Governance Evidence & Purview-Native Workflow Proofs

See [`08_Notebook_Description.md`](./08_Notebook_Description.md) for `08_validate_governance_evidence` — split out and live-validated 2026-08-18.

See [`09_Notebook_Description.md`](./09_Notebook_Description.md) for `09_reconcile_semantic_model` — split out and live-validated 2026-08-18.

---

## Phase 5 — Demo Operations

### `10_reset_demo.Notebook` — `DEMO_MODE = False` (its normal mode is to actually reset state)
**What it does:** Resets every demo request (Objective edits/certification/recertification, AI
Instruction effective-date/rollback, Data Product certification/expiration/decertification,
CDE/ontology mapping, semantic-model promotion) back to its pre-decision status across both SQL
(Cells 3–6) and the Lakehouse/semantic model (Cells 7–8), so the whole approval narrative can
be re-demoed live, indefinitely. Never deletes a governed object row.
**Demo fit:** Not part of the demo narrative itself — the "reset the stage" utility run between
rehearsals or between live audiences.
**Talking points:** (internal use only — not shown to an audience) "Run this after a live pass
to put every gated request back to 'awaiting approval' so tomorrow's demo starts fresh."
**Note:** re-approving after a reset needs a small manual status flip (`Submitted`→`Approved`)
plus re-running the matching apply notebook (`07_apply_approved_changes` or the relevant phase
of `09_reconcile_semantic_model`) — the original build scripts won't reapply a reset request
since they're guarded by existence, not status.

---

## Governance Review Findings (orphan check, carried forward)

Every notebook was reviewed for content that reaches a production/demo-facing surface WITHOUT
flowing through the closed-loop governance gate — i.e., anything that isn't pure seed data or
architectural schema-building. Findings for notebooks 01/02 have moved into their own docs
(`01_Notebook_Description.md`, `02_Notebook_Description.md`); findings not yet tied to a
specific split-out notebook remain here.

| Finding | Detail | Status |
|---|---|---|
| **Stale pre-consolidation paths in `tools/`** | `tools/validate_build_workflow.ps1` and `tools/normalize_fabric_canonical_state.ps1` referenced a `fabric/` prefix folder that doesn't exist in this repo layout, plus the old `nb_04_sempy_writeback`/`nb_05_push_qa_verified_answers` notebook names — both scripts would fail their Gate D checks with false-positive "file missing" issues. `tools/test_nb09_live_publish_defaults.py` pointed at a notebook path that no longer exists. | ✅ **Fixed 2026-08-16.** Both scripts updated to the current repo-root paths and the single merged `04_writeback_governed_metadata.Notebook`; re-run and confirmed passing. The test file was fixed and renamed to `tools/test_publish_glossary_and_lineage_live_defaults.py` and confirmed passing. |
| **Stale-Spark-catalog-schema risk audit (session-wide, 2026-08-17)** | Root-caused live in `02_build_metadata_foundation` (a `collectToPython`/`IllegalStateException` on a schema-drifted `parent_term_code` column); audited all 10 notebooks for the same `_read_table`/`spark.table()` pattern. | ✅ `05`/`06` already had the fix; `02`/`04`/`08` were vulnerable and fixed; `01`/`03`/`07` only do low-risk same-session-write or `.columns`-only reads; `09`/`10` don't use Spark table reads at all. |
| Everything else reviewed | Domain/data-product/glossary/CDE publication notebooks (`05`, `06`) republish already-governed SQL/CSV source content — no bypass found. `07_apply_approved_changes` and `09_reconcile_semantic_model` all correctly fail closed on a required prior receipt before applying. `08_validate_governance_evidence`'s scorecard cells are read-only. `10_reset_demo` never deletes a governed row. | 🟢 No other orphans found |
