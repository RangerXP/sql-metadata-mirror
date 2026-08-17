# `06_publish_glossary_and_lineage` — Notebook Description & Artifact Catalog

**Purpose:** Full descriptive reference for `06_publish_glossary_and_lineage.Notebook` — what
it does, what it consumes/produces, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and its live-validation history.

**Status:** ✅ Live-validated end-to-end 2026-08-17, after finding and fixing four real bugs
(see `docs/runbooks/notebook-validation/06_publish_glossary_and_lineage.md` for the full run
evidence).

**DEMO_MODE:** No top-level gate — both phases always write dry-run artifacts; live Purview
publish is controlled by `SQL_MIRROR_ONLY_DEPLOYMENT` / `PURVIEW_PUBLISH_OVERRIDE` /
`APPLY_CHANGES` / `DISABLE_LIVE_PURVIEW_PUBLISH`.

**Legacy name(s):** predecessor of `nb_08_purview_glossary_cde` (Cells 1–5) and
`nb_09_purview_labels_lineage` (Cells 6–11), merged into one file sharing a single Purview
token cache.

---

## What it does

Two originally-separate notebooks merged into one file:

- **Cells 1–5 — glossary/CDE publish** (formerly `nb_08_purview_glossary_cde`): reads
  `glossary_terms`/`cdes` from `lh_metadata`, builds Atlas typedef + entity payloads, publishes
  35 glossary terms and 12 CDEs to Purview, associates each CDE to its parent glossary term,
  and self-heals stale term `shortDescription` values on every run so terms created under an
  older code-naming convention stay in sync with the current source.
- **Cells 6–11 — labels & lineage** (formerly `nb_09_purview_labels_lineage`): publishes
  sensitivity labels, CDE classifications, and custom Atlas lineage edges (SQL → Fabric →
  semantic model), since native Purview scans only establish asset identity, not cross-system
  process lineage.

Purview authentication is shared across both phases and with `05_publish_governance_domains`/
`08_validate_governance_evidence`/`09_reconcile_semantic_model` via a common OneLake-cached
bearer token (`Files/purview_publish/.purview_token_cache.json`), with a robust fallback
cascade (cache → manual `PURVIEW_ACCESS_TOKEN` → Azure CLI → TokenLibrary → interactive
device-code as last resort).

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `lh_metadata.glossary_terms` | 35 glossary term Atlas entities + self-heal shortDescription checks |
| `lh_metadata.cdes` | 12 `EnercareCriticalDataElement` Atlas entities + classifications |
| `lh_metadata.label_assignments` | Sensitivity label assignments (Cells 6–11) |
| `lh_metadata.data_products` | Semantic-model anchor resolution for glossary-to-asset fallback association |
| `context/lineage-edges.csv`-derived manifest | Custom Atlas lineage process edges (SQL → Fabric → semantic model) |

### Outputs produced

| Output | Detail |
|---|---|
| Purview Atlas glossary terms (live) | 35 terms created/existing, self-healed shortDescription where stale |
| Purview Atlas CDE entities (live) | 12 `EnercareCriticalDataElement` entities |
| CDE-to-glossary-term associations | 12/12 assigned |
| Glossary-to-asset associations | Term ↔ bound SQL/Fabric/semantic-model asset links |
| Sensitivity label assignments (live) | Published per `label_assignments` |
| Custom Atlas lineage processes (live) | SQL → Fabric → semantic model edges, batched entity/bulk publish |
| `Files/purview_publish/.purview_token_cache.json` | Shared bearer-token cache (read/written by 05/06/08/09) |
| `dbo.nb08_diagnostics_log` / `dbo.nb09_diagnostics_log` | Real exception + traceback capture for each phase, since Fabric's job API exposes no cell-level detail |

## Demo fit

This is every `GT-*`/`CDE-*` reference throughout Maria's scenario (GT-SLA, GT-CONSENT,
CDE-CONTRACTAMT, CDE-CONSENTSTATE, etc.) plus the "click View lineage" moment in Act 3 — the
chain from a Power BI visual back to source SQL that Ci Zhu shows the auditor.

## Talking points

"GT-SLA is the term that ties Tom's credit calculation, Victoria's MTTR dashboard, and Ci Zhu's
audit answer to one published definition — and native scans tell Purview an asset exists, while
this notebook tells Purview how assets connect across systems."

## Live-validation findings

This notebook required 6 live run attempts across two separate root causes before reaching a
clean `Completed`, plus one Purview account/endpoint config bug found via a manual portal run.

| Finding | Detail | Status |
|---|---|---|
| **Root cause 1: stale Delta column-mapping ID on `glossary_terms`** | Cell 3's `glossary_df.collect()` failed with `IllegalStateException: Couldn't find previous_definition#63 in [...]` — a phantom column neither declared in the current schema nor referenced anywhere in the notebook's own code, yet still resolved by Spark's cached plan. Traced to the same class of bug as the historical 2026-08-10 OKR `progress_amount` fix: Delta's column-mapping ID history can leave stale physical-schema references from an earlier column add/rename that persist across plain overwrite+refreshTable. | ✅ **Fixed.** Generalized `02_build_metadata_foundation`'s `write_table_from_pandas()` to `DROP TABLE IF EXISTS` before every table overwrite (previously scoped to only `okr_key_results`), purging stale column-mapping IDs for `glossary_terms` and all other written tables. |
| **Root cause 2: phantom columns in `CDE_COLUMNS_NEEDED`** | After fix 1, a second failure surfaced: `IllegalStateException: Couldn't find steward_upn#172 in [...]`. Both of this notebook's `CDE_COLUMNS_NEEDED` lists (Cells 2 and 7) referenced columns (`steward_upn`, `cde_code`, `domain_code`, `sensitivity_label`, `owner_upn`, `validation_rule`, `description`) that never existed in the actual `cdes` source data at all — confirmed by cross-checking `sql/02_metadata_foundation` ingestion's `cde_required` column list, which never included them. | ✅ **Fixed.** Trimmed both `CDE_COLUMNS_NEEDED` lists (and one stray `GLOSSARY_COLUMNS_NEEDED` entry) to only the columns that genuinely exist, matching the ingestion source contract. |
| **Missing diagnostic instrumentation on both live-publish blocks** | Neither Cell 5 (glossary/CDE Atlas publish) nor Cell 11 (labels/lineage Atlas publish) had any exception logging — both were large, uninstrumented `else:` blocks, unlike every other cell in this notebook. This meant real failures during the ~18-minute self-heal/publish loop were invisible beyond Fabric's generic `System_Cancelled_Session_Statements_Failed`. | ✅ **Fixed.** Wrapped both blocks in `try/except` with `_log_nb08_diagnostic("cell5_live_publish", ex)` / `_log_nb09_diagnostic("cell11_live_publish", ex)`, applied via a mechanical line-range re-indentation script (not manual retyping, given the ~280–700 line block sizes) to avoid introducing indentation bugs. |
| **Purview endpoint/account config bug in Cell 6** | A manual portal run of the labels/lineage phase (Cell 6) raised `RuntimeError: PURVIEW_API_BASE_URL/... is not set` — Cell 6 hard-failed instead of falling back to the public Purview hostname like Cell 1 does, and defaulted to the wrong account name (`Purview-West3` instead of `Purview-West2`, the account that actually has the live glossary/Unified Catalog). | ✅ **Fixed.** Aligned Cell 6's `_resolve_purview_base_url()` and `PURVIEW_ACCOUNT_NAME` default to match Cell 1's already-proven-working resolver. |
| **Platform gotcha: Fabric git-sync conflict from concurrent portal edits** | While debugging, a manual interactive portal session was open on this same notebook at the same time as scripted git-sync + REST job runs, causing `POST git/updateFromGit` to fail with `MissingWorkspaceConflictResolution`. | ✅ Worked around by adding explicit `conflictResolution: {conflictResolutionType: "Workspace", conflictResolutionPolicy: "PreferRemote"}` to `tools/sync_fabric_git.py`'s request body — git-side fixes now always win over an unsaved live workspace edit. |

### Run record

| Attempt | Job ID | Duration | Status | Note |
|---|---|---|---|---|
| 1 | `223c2941-8136-4c20-8e0d-59b14271879a` | ~4.5 min | ❌ `Failed` | Root cause 1 (`previous_definition` phantom column) |
| 2 (after DROP TABLE fix) | `0ddd45b8-09a0-40fa-85fd-bc4f9e4e3ae5` | ~19.6 min | ❌ `Failed` | Root cause 2 (`steward_upn` phantom column) — long duration masked by an also-expired Purview token cache mid-run |
| 3 (after CDE_COLUMNS_NEEDED fix) | `77264e48-b255-4025-9f85-623dd3ffe18d` | ~20.2 min | ❌ `Failed` | Uninstrumented Cell 11 live-publish block — real cause invisible until diagnostic wrap added |
| 4 (after diagnostic wrap + Cell 6 endpoint fix) | `c8a91f6f-8e2d-4e82-813b-2c992669568e` | ~12.6 min | ✅ `Completed` | Clean run — 35/35 glossary terms, 12/12 CDEs, 12/12 CDE-term associations, lineage published |

## Data write-out confirmation

- **Glossary terms:** 35/35 created or already-existing, self-heal applied where `shortDescription` had drifted from the current `term_code`.
- **CDEs:** 12/12 `EnercareCriticalDataElement` entities published.
- **CDE-to-GlossaryTerm associations:** 12/12 assigned, 0 unresolved.
- **Glossary-to-asset associations:** semantic-model anchor resolved (`BrookfieldEnercare`) for fallback association where a direct bound-asset match wasn't found.
- **Diagnostics:** `nb08_diagnostics_log` holds 3 rows, all from the pre-fix failed attempts — zero new rows added on the successful run.

## Maria Castellanos north-star use-case match

- ✅ `GT-SLA`, `GT-CONSENT`, and the other glossary terms referenced throughout Tom's call and
  Ci Zhu's audit walkthrough are live, published Atlas entities with correct definitions.
- ✅ CDE-to-term associations (e.g. `CDE-CONTRACTAMT` bound to its governing glossary term) are
  live — this is the exact linkage Ci Zhu cites when proving single-source-of-truth to the
  auditor.
- ✅ Custom Atlas lineage edges give Ci Zhu the "click View lineage" moment: Power BI visual →
  semantic-model measure → lakehouse table → mirrored SQL → source SQL, the same chain Tom's
  and Victoria's views trace back through.

## Dependencies / downstream consumers

- Depends on `02_build_metadata_foundation` having populated `glossary_terms`/`cdes`/
  `label_assignments`/`data_products`.
- Shares the Purview token cache with `05_publish_governance_domains`,
  `08_validate_governance_evidence`, and `09_reconcile_semantic_model`.
- `08_validate_governance_evidence`'s stewardship scorecard and `09_reconcile_semantic_model`'s
  Unified Catalog reconciliation both depend on the glossary terms/CDEs published here already
  existing in Purview.

---

See also: [`05_Notebook_Description.md`](./05_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/06_publish_glossary_and_lineage.md`](./runbooks/notebook-validation/06_publish_glossary_and_lineage.md)
