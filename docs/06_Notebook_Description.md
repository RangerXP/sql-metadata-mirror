# `06_publish_glossary_and_lineage` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `06_publish_glossary_and_lineage.Notebook` — what it
does, what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/06_publish_glossary_and_lineage.md`.

**Status:** ✅ Validated.

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
bearer token (`Files/purview_publish/.purview_token_cache.json`), with a non-interactive
fallback cascade (cache -> manual `PURVIEW_ACCESS_TOKEN` -> Azure CLI -> TokenLibrary) that
never blocks an unattended run on an interactive sign-in prompt.

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
