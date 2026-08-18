# `08_validate_governance_evidence` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `08_validate_governance_evidence.Notebook` — what it
does, what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/08_validate_governance_evidence.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** Cells 1–6 (with 5a) have no gate (pure read-only validation). Cells 7+:
`DEMO_MODE = False` (intentional — Cell 9 observes and persists a real Purview workflow event).

**Legacy name(s):** predecessor of `nb_10_purview_stewardship_ai` (Cells 1–6/5a) and
`nb_12_purview_workflow_sync` (Cells 7–13, P1).

---

## What it does

Two originally-separate notebooks merged into one file:

- **Cells 1–6 (with 5a) — stewardship/certification scorecard:** read-only validation across
  four dimensions — steward/owner/certification coverage per governed object, DLP/label
  control readiness, AI-readiness (certified products, bound glossary terms/CDEs, semantic
  annotation availability), and OKR/ontology graph-integrity (every OKR linked to a data
  product, every key result resolving to its parent OKR). No writes to source data; writes only
  its own validation-stage output tables and a closeout manifest.
- **Cells 7–13 — P1 Purview-native workflow proof:** observes a real Purview-native Glossary
  Term publish workflow (`GT-SLA`) via the term's own `status` field in the Unified Catalog —
  the only real API-observable proxy for approval, since Purview exposes no workflow-request
  API. Enforces Draft-before-Published correlation guardrails, then persists an idempotent
  observation event and a durable P1 evidence receipt to the `sub2` SQL ledger
  (`governance_events` / `governed_object_versions` / `governance_target_receipts`).

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `lh_metadata.domains` / `data_products` / `cdes` | Stewardship/owner/certification scorecard (Cell 3) |
| `lh_metadata.role_assignments` / `label_assignments` | DLP/label control readiness checks (Cell 4) |
| `lh_metadata.glossary_terms` / `semantic_annotation_plan` (falls back to `sm_annotations`) | AI readiness checks (Cell 5) |
| `lh_metadata.okrs` / `okr_key_results` / `okr_data_products` | Ontology/OKR relationship-integrity checks (Cell 5a) |
| Purview Unified Catalog `GT-SLA` term (`b3b54277-3b36-47d8-831c-a2b9a5f02634`) | P1 live observation (Cell 9) |

### Outputs produced

| Output | Detail |
|---|---|
| `lh_metadata.purview_phase_08_stewardship_scorecard` | 18 rows (3 domains + 3 data products + 12 CDEs), each with `has_steward`/`has_owner`/`is_certified_or_published`/`stage_status` |
| `lh_metadata.purview_phase_09_controls_validation` | 4 checks — confidential label rules, DLP policy mode (manual gate), label policy coverage, sensitive CDE identification |
| `lh_metadata.purview_phase_10_ai_readiness_validation` | 4 checks — certified/published products, glossary terms bound to assets, CDEs bound to columns, semantic annotation plan availability |
| `lh_metadata.purview_phase_11_ontology_validation` | 4 checks — OKRs available, key results available, OKR→data-product linkage, key-result→OKR resolution |
| `lh_metadata.purview_phase_08_10_closeout` | Rollup summary (rows checked / action-required / status per phase) |
| `Files/purview_publish/phase_08_10_stewardship_ai/stewardship_ai_closeout_manifest.json` | Manual-gate notes + stage-table pointers |
| `sqldemo.dbo.governance_events` / `governed_object_versions` / `governance_target_receipts` | P1's durable Draft/Published observation event + evidence receipt for `GT-SLA` |
| `lh_metadata.nb08val_diagnostics_log` | Real exception + traceback capture, since Fabric's job API exposes no cell-level detail |

## Demo fit

The "proof it all worked" scorecard, plus Ci Zhu's audit answer for `GT-SLA` — a real Purview
workflow run observed through its own API, not a SQL-side simulation.

## Talking points

"This is our own governance health check, and this is what a real approval inside the Purview
portal looks like once read back through the API — not a SQL-side approximation."

## Dependencies / downstream consumers

- Depends on `02_build_metadata_foundation` having written `domains`/`data_products`/`cdes`/
  `role_assignments`/`label_assignments`/`okrs`/`okr_key_results`/`okr_data_products`/
  `sm_annotations` correctly and completely — this notebook is purely a read-only validator of
  that upstream contract, never a workaround for gaps in it.
- The P1 `GT-SLA` evidence receipt this notebook writes is a prerequisite for
  `09_reconcile_semantic_model`'s P2 phase, which fails closed unless this receipt already
  passed.

---

See also: [`07_Notebook_Description.md`](./07_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/08_validate_governance_evidence.md`](./runbooks/notebook-validation/08_validate_governance_evidence.md)
(build/debug history and live-run evidence) ·
[`docs/02_Notebook_Description.md`](./02_Notebook_Description.md)
