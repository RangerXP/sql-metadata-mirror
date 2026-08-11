# Enercare Build Scorecard

**Last updated:** 2026-08-11
**Purpose:** Single quick-glance scorecard for all build units/phases. Update this file (not just `design-gap-analysis.md`) after every unit of work completes or changes status.

---

## Phase 1–3 (Foundational build) — ✅ All Done

| Unit | Status |
|---|---|
| G1 Cross-subscription architecture (sub1/sub2/sub3) | 🟢 Done |
| G2 Azure SQL source (sub2) | 🟢 Done |
| G3 Synthetic data publish + mirror validation | 🟢 Done |
| G4 Fabric Mirroring (sub2 → sub1) | 🟢 Done |
| G5 Metadata extraction / `lh_metadata` store | 🟢 Done |
| G6 SemPy/SemPy Labs semantic-model writeback | 🟢 Done |
| G7 Purview deployment (sub3) | 🟢 Done |
| G8 Purview scans, catalog, glossary/CDE publish | 🟢 Done |
| G9 Lineage registration (8/8 edges live) | 🟢 Done |
| G10 Steward workflow / AI drafting | 🟢 Done (2026-08-08 regression fixed; `nb_10` scorecard 0 `ACTION_REQUIRED`) |
| G11 Ontology/B2C extensions | 🟡 In Progress — see Phase 5 below |
| G12 Governance design/brief/CSV alignment | 🟢 Done |

---

## Phase 4 — Self-Healing Sync & Gated Governance

| Unit | Status |
|---|---|
| G13-1..3 Mirror CDC + gating schema + certification columns | 🟢 Done |
| **G13-4 `nb_11_gated_governance_sync`** | 🟢 Built, pushed live, dry-run validated, live-proven against all 4 real Approved requests, and git-sync identity conflict fixed (2026-08-10, `commitToGit` re-established a proper Fabric-issued `logicalId`) |
| G14-1..3 Scenario design/seed/runbook | 🟢 Done |
| **G14-4 Live run: KPI Approval** (`SLA_BRCH_RATE` v1→v2) | ✅ Proven — `Version=2`, certified, applied 2026-08-09 02:05:14 |
| **G14-5 Live run: Verified Answer Certification** | ✅ Proven — new `ai_metadata` row, applied 02:10:15 |
| **G14-6 Live run: CDE Classification** (`CDE-COMPLAINTREF`) | ✅ Proven — new `governance_cdes` row, applied 02:14:06 |
| **G14-7 Live run: Glossary Term** (`GT-SLA`) | ✅ Proven — new `governance_glossary_terms` row, applied 02:17:24 |
| G14-8 Phase 4 closeout (full propagation + `nb_10` reconfirm) | 🟢 Done — full chain proven end-to-end, `nb_10` scorecard 0 `ACTION_REQUIRED` across all phases |
| **G15-1 Native Purview publication evidence** (`GT-SLA`) | ✅ Proven — native approval published, immutable Draft/Published versions recorded, `PublicationReadback=Passed` |
| **G15-2 Semantic reconciliation closeout** (`nb_13`) | ✅ Proven — 3 SLA objects updated and read back, `SemanticModelReadback=Passed`, request `Completed` at 2026-08-11 23:10:02 UTC |
| **G15-3 Mirrored closed-loop evidence** | ✅ Proven — `sqldemo` SQL analytics endpoint showed `Completed` plus both passing receipts with matching hashes |

---

## Downstream Propagation Chain (proving G14-8)

| Step | Notebook | Status |
|---|---|---|
| 1 | `nb_07a_ingest_customer_files` | ✅ Completed |
| 2 | `nb_04_sempy_writeback` | ✅ Completed |
| 3 | `nb_05_push_qa_verified_answers` | ✅ Completed |
| 4a | `nb_08_purview_glossary_cde` | ✅ Completed — fixed via `spark.catalog.refreshTable()` before `spark.table()` (stale cached schema bug); job `93b0028c` |
| 4b | `nb_09_purview_labels_lineage` | ✅ Completed — same stale-schema bug, `refreshTable()` + column pruning (`_prune_columns()`) added; job `520730d6` |
| 5 | `nb_10_purview_stewardship_ai` (final scorecard check) | ✅ Completed — 0 `ACTION_REQUIRED` across `phase_08_stewardship` (19), `phase_09_controls` (4), `phase_10_ai_readiness` (4); job `162040be` |

---

## Phase 5 — Formal Ontology / OKR Business-Objective Layer (G11-1, §5E)

| Unit | Status |
|---|---|
| Schema: `sql/11_ontology_okr_schema.sql` (governance_okrs/okr_key_results/okr_data_products) | 🟢 Built |
| Seed: `sql/12_seed_ontology_okrs.sql` (3 OKRs, 5 key results, 3 links) | 🟢 Built |
| `purview/okr-catalog.csv` reference artifact | 🟢 Built |
| `nb_07a` ingestion (Cell 8c: okrs/okr_key_results/okr_data_products) | 🟢 Built |
| `nb_07` publish `EnercareOKR`/`EnercareOKRKeyResult` Atlas entities + Data Product links | 🟢 Built |
| `nb_08` fix: assign each CDE's own entity to its parent Glossary Term | 🟢 Built |
| `nb_10` Cell 5a `purview_phase_11_ontology_validation` scorecard | 🟢 Built |
| Live apply: `sql/11`/`sql/12` against `sqldemo` + Fabric mirror pickup | 🔴 Not started |
| Live run: `nb_07a` → `nb_07` → `nb_08` → `nb_10`, confirm 0 `ACTION_REQUIRED` | 🔴 Not started |
| Docs: `docs/design-gap-analysis.md` G11 section, `docs/Enercare-Demo-SemPy-Design-Guide.md` §5E | 🟢 Done |

---

## Update Log

- 2026-08-09: Scorecard created. Captures state after all 4 gated-governance scenarios proven live and propagation chain steps 1-3 completed; `nb_08` failing, diagnostics pushed, re-run pending.
- 2026-08-10: Fixed `nb_08`/`nb_09` stale Spark catalog schema bug (`refreshTable()` + column pruning), reran and confirmed both `Completed`. Reran `nb_10`, confirmed 0 `ACTION_REQUIRED` across all phases — full propagation chain (steps 1-5) now proven end-to-end, G14-8 closed. Separately fixed a Fabric git-sync identity conflict on `nb_11_gated_governance_sync` (duplicate/orphaned `logicalId` from a locally-invented `.platform` file never issued via Fabric's git connector) using `commitToGit`/`updateFromGit`; `nb_04a`/`nb_07a` incoming-change conflicts cleared in the same pass.
- 2026-08-10 (later same day): Found and fixed a real data-corruption bug in `nb_04a_extend_metadata_schema`'s Set B seed — a PySpark `Row()` kwarg order mismatch against `KPI_SCHEMA`'s declared field order caused `Domain`/`Owner`/`Description` values to silently rotate for all 5 certified call-center KPIs (`FCR`, `CSAT`, `AHT`, `PP_RNW_RATE`, `SLA_BRCH_RATE`) in the live `kpi_metadata` table and downstream in the `BrookfieldEnercare` semantic model's `_Measures.tmdl` (`FCR Rate`/`Avg CSAT`/`Avg Handle Time (sec)` descriptions had been overwritten with an owner email string instead of the real KPI description). Code fix applied to `nb_04a` (kwarg order corrected to match schema); live data fix applied via a throwaway temp Fabric notebook (`zz_temp_kpi_fix`, since the Lakehouse SQL analytics endpoint is read-only and rejects DML) executing targeted `UPDATE` statements via Spark — confirmed correct via sqlcmd re-query, then the temp item was deleted. Re-ran `nb_04_sempy_writeback` (`DEMO_MODE=False`) to push the corrected descriptions into the live semantic model; confirmed via `getDefinition` that `_Measures.tmdl` now has the correct descriptions. Committed and pushed both the `nb_04a` code fix and the Fabric-authored semantic-model `commitToGit` result to git; live `nb_04a` Fabric item also re-pushed via `updateDefinition` to match the fixed local code. Fabric workspace git status confirmed fully clean (`TOTAL_CHANGES=0`) at the end of this pass.
- 2026-08-11: Built the formal ontology / OKR business-objective layer (G11-1, design guide §5E) end-to-end in code: `sql/11_ontology_okr_schema.sql` + `sql/12_seed_ontology_okrs.sql`, `purview/okr-catalog.csv`, `nb_07a` ingestion, `nb_07` publish of `EnercareOKR`/`EnercareOKRKeyResult` Atlas entities with Data Product links, and a `nb_08` fix so each CDE's own Atlas entity is assigned to its parent Glossary Term (previously only the term's `bound_assets` were linked, not the CDE entity itself — found by code inspection). Added `nb_10` Cell 5a ontology scorecard. Corrected `docs/design-gap-analysis.md`'s stale "Purview typed-relationships not yet GA" claim. Live-apply (SQL + notebook reruns) intentionally left for a follow-up pass; see Phase 5 above.
