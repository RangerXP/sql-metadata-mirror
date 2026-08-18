# `08_validate_governance_evidence` — Notebook Description & Artifact Catalog

**Purpose:** Full descriptive reference for `08_validate_governance_evidence.Notebook` — what
it does, what it consumes/produces, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and its live-validation history.

**Status:** ✅ Live-validated end-to-end 2026-08-18, after finding and fixing a real upstream
data regression (see `docs/runbooks/notebook-validation/08_validate_governance_evidence.md` for
full evidence, and `docs/02_Notebook_Description.md`'s Follow-up section for the upstream fix).

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

## Live-validation findings

| Finding | Detail | Status |
|---|---|---|
| **Upstream data regression blocked all early attempts** | Stewardship scorecard failed with `Couldn't find governance_domain_stewards#74 in [...]` — traced to a full regression of the 2026-08-08 steward-data fix at the sub2 SQL source (all steward columns NULL), plus stale legacy glossary-term content, plus Fabric mirroring found `Paused`. Full root-cause chain in `docs/02_Notebook_Description.md`'s Follow-up section. | ✅ **Fixed 2026-08-18** at the source (backfill + reseed + mirroring restart), not by patching around the gap in this notebook. |
| **2 automated resubmissions misdiagnosed as a repeat of the same bug** | After the upstream fix, 2 unattended `RunNotebook` batch jobs still failed identically. Corrected finding: these actually hung on Cell 9's Purview token acquisition, which only had a manual→cache→device-code cascade at the time — an unattended job can't complete an interactive sign-in. | ✅ **Fixed 2026-08-18** by adding an `AzureCliCredential` fallback tier to `get_purview_token()`, reusing the already-authenticated `az` CLI session instead of blocking on device-code. |
| **Confirmed live: all four validation phases genuinely PASS** | Manual run (portal, interactive session) completed cleanly: 18/18 stewardship rows PASS, 4/4 controls (1 intentional WARN), 4/4 AI readiness, 4/4 ontology — 0 `ACTION_REQUIRED` anywhere. | ✅ Independently re-verified via direct SQL query against all 4 live tables (not just notebook print output) — see `docs/runbooks/notebook-validation/08_validate_governance_evidence.md`. |
| **P1 Purview-native workflow proof confirmed live** | `GT-SLA` observed `status=Published`, correlated Draft→Published evidence chain intact, applied and verified with a `Passed` receipt. | ✅ Confirmed via Cells 9/11/12 output. |
| **Governance-contract compliance** | Ran the full `tools/audit_seed_vs_source.py --target both` (value parity, row counts, enum compliance, referential integrity) and `tools/validate_required_columns_not_null.py --target both` against the tables this notebook reads. | ✅ 0 failing checks across both tools, at both the sub2 source and the `lh_metadata` destination. |

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
[`docs/runbooks/notebook-validation/08_validate_governance_evidence.md`](./runbooks/notebook-validation/08_validate_governance_evidence.md) ·
[`docs/02_Notebook_Description.md`](./02_Notebook_Description.md) (upstream regression details)
