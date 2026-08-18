# `04_writeback_governed_metadata` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `04_writeback_governed_metadata.Notebook` — what it
does, what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/04_writeback_governed_metadata.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** `False` (its normal mode actually writes to the live semantic model).

**Legacy name(s):** predecessor of `nb_04_sempy_writeback`, `nb_04a_extend_metadata_schema`,
`nb_05_push_qa_verified_answers` (pre-consolidation 18-notebook structure).

---

## What it does

Two originally-separate notebooks merged into one file:

- **Cells 1–10 — table/column/measure writeback** (formerly `nb_04_sempy_writeback`): reads
  curated metadata from `lh_metadata`, cross-checks the live model inventory (Power BI MCP),
  builds a write plan, and applies table/column/measure descriptions plus governance/ontology
  annotations into the `BrookfieldEnercare` semantic model via SemPy Labs TOM. Verified against
  a hard TOM read-back after every write. Cell 8 hard-depends on `sm_annotations` (raises
  `RuntimeError("sm_annotations is empty")` if missing) — populated by
  `02_build_metadata_foundation`.
- **Cells 11–15 — AI grounding writeback** (formerly `nb_05_push_qa_verified_answers`): reads
  `ai_metadata`, filters `WHERE IsDraft = 0 AND IsCertified = 1` (matching the KPI path's
  certification gate), builds the annotation payload, and writes
  `PBI_AI_Instructions`/`PBI_AI_VerifiedAnswers` annotations the Fabric Data Agent reads for
  grounding. `MAX_ANNOTATION_CHARS = 32000` (large enough for a full certified payload).

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `lh_metadata.dbo.sm_annotations` (written by `02_build_metadata_foundation`) | Cell 8 — the resolved table/column/measure annotation intents |
| `lh_metadata.dbo.glossary_terms` (column-pruned read: `term_code`, `term_name`, `definition`) | Cell 8's glossary-definition lookup |
| `lh_metadata.dbo.ai_metadata` | Cells 11–13 — `PBI_AI_Instructions`/`PBI_AI_VerifiedAnswers` source content, filtered to certified rows |
| `lh_metadata.dbo.okrs`/`okr_key_results`/`okr_data_products` | Ontology annotations enriching certified KPI measures |
| `lh_metadata.{semantic_measure_kpi_map, measure_kpi_map, kpi_measure_map}` (first existing candidate) | Optional measure-name alias resolution |
| Live `BrookfieldEnercare` semantic model inventory (via Power BI MCP) | Cross-check before building the write plan |

### Outputs produced (via direct semantic-model read-back)

| Target | Result |
|---|---|
| Table descriptions (13 tables) | All carry real, substantive descriptions (e.g. `dim_customer`, `fct_service_request`) |
| Measure descriptions (18 measures) | All carry real descriptions (`Technician Utilization Rate`, `Total MRR`/`New MRR`/`Churned MRR`, `SLA Breach Count`/`SLA Compliance Rate`, `Warranty Coverage Rate`, etc.) |
| Model-level `PBI_AI_Instructions` annotation | Present, contains real Enercare business-context grounding (billing systems, call-center queue taxonomy, FCR terminology) |
| Model-level `PBI_AI_VerifiedAnswers` annotation | Present, includes the quantified billing-caller/PP-renewal correlation from `01_setup_source_data` |

## Demo fit

This is the mechanism behind Ci Zhu's Act 3 promise — "there's only one `_Measures/Net
Revenue`... it's owned by me" — and also what lets Tom ask the Data Agent "show me Maria's
furnace status" and get a grounded answer (Act 1 / Acceptance Criterion 7).

## Talking points

"Notice the certification filter on both halves of this notebook — an uncertified KPI or AI
instruction change never reaches the semantic model or the Data Agent through this path.
That's what makes drift structurally impossible, not just a policy."

## Dependencies / downstream consumers

- Hard-depends on `02_build_metadata_foundation`'s `sm_annotations` output (Cell 8).
- Hard-depends on `01_setup_source_data`'s call-center correlation data reaching the semantic
  model correctly (via `03_build_semantic_model`) for the AI grounding to be meaningful.
- Feeds the Fabric Data Agent (`ee82668f-...DataAgent`) directly via the model annotations —
  no further notebook processes these before the Data Agent reads them at query time.

---

See also: [`03_Notebook_Description.md`](./03_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/04_writeback_governed_metadata.md`](./runbooks/notebook-validation/04_writeback_governed_metadata.md)
