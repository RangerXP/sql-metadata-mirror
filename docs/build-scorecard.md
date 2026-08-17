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

## Phase 5 — G17: Unified Governance Ledger Reconciliation (closed 2026-08-13)

| Unit | Status |
|---|---|
| R1 Migrate legacy `governance_change_requests` into unified ledger | ✅ Done — `sql/14_migrate_legacy_governance_to_unified_ledger.sql`, 4/4 rows migrated |
| R2 Reconcile duplicate `GT-SLA` governance record | ✅ Done — `sql/15_reconcile_gt_sla_duplicate_governance.sql`, legacy row `Superseded`, mapped to native |
| R3 Gate AI Instructions (structural fix, not a patch) | ✅ Done — `sql/16_add_ai_instruction_gate.sql`; `nb_04a`'s reseed now structurally excludes `IsCertified=1` rows |
| R4 Gate OKR Key Result creation | ✅ Done — `sql/18_add_okr_approval_gate.sql`, real `KR-TECH-UTIL` under `OKR-SVCDEL-SLA` |
| R5 Role-assignment ledger entries | ✅ Done — `sql/17_backfill_role_assignment_ledger.sql`, 8 entries covering every real P3/P4 role grant |
| **R6 Prove drift-and-restore self-correction for real** | ✅ Done — live-tested on the Purview-native track (`DP-SVCPERF`/`nb_16`): deliberately drifted a semantic annotation, confirmed wrong, re-ran `nb_16`, confirmed restored, same request/receipt (no new approval fabricated). SQL-controlled track (`nb_04_sempy_writeback`) confirmed structurally identical (unconditional reapply from `kpi_metadata` every run) |

Every one of the 8 `governance_requests.request_type` values now has at least one real, `Completed`, queryable demo object. **G17 fully closed.**

## Phase 6 — G18-A: @tag Native Extraction (closed 2026-08-13)

| Unit | Status |
|---|---|
| `sql/19_tag_annotation_extraction.sql` (proc + DDL trigger, native SQL, no CLR) | ✅ Done — real idempotency bug found+fixed (timestamp was polluting the content hash) |
| `nb_02` shrink (remove standalone Python `@tag` prototype, thin SQL reader) | ✅ Done — 828 → 172 lines; removed 2 previously-undiscovered live-write risks (`kpi_metadata` overwrite, real `ALTER TABLE COMMENT`), confirmed neither had ever run against production; original backed up |
| Final-form demo: Approved / Rejected / Pending | ✅ Done — `vw_technician_utilization_summary` (Completed), `vw_employee_pii_export` (Rejected, real PII rationale), `vw_contract_renewal_pipeline` (Submitted, confirmed picked up by `nb_02`'s thin reader) |

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

## Phase 6 — Native Purview Workflow Stakeholder Coverage (G16)

| Unit | Status |
|---|---|
| Wireframe: stakeholder-to-scenario mapping, ground-truth native workflow types, manual-role prerequisites | 🟢 Done — `docs/purview-native-workflow-wireframe.md` |
| P3 — Data product access (`DP-CUST360`): Victoria Tan approver, Rupal Solanki requester | ✅ Done — fully closed live end-to-end (2026-08-12): `request=PV-CUST360-ACCESS-BD3BEBA460C530FA5076 status=Completed`, `AccessDecisionReadback` receipt Passed (operator-attested decision, per confirmed platform limitation) |
| P4 — Data product publish (`DP-SVCPERF`/DOM-SVCDEL): Ranbir Singh approver, Shruthi Srinivas requester | ✅ Done — fully closed live end-to-end (2026-08-12): real Draft→Published cycle approved by Ranbir Singh, `nb_15`/`nb_16` evidence chain Completed with both receipts Passed |
| Phase closeout — all 5 stakeholders proven; move to non-native workflow phase | 🔴 Not started |

---

## Update Log

- 2026-08-09: Scorecard created. Captures state after all 4 gated-governance scenarios proven live and propagation chain steps 1-3 completed; `nb_08` failing, diagnostics pushed, re-run pending.
- 2026-08-10: Fixed `nb_08`/`nb_09` stale Spark catalog schema bug (`refreshTable()` + column pruning), reran and confirmed both `Completed`. Reran `nb_10`, confirmed 0 `ACTION_REQUIRED` across all phases — full propagation chain (steps 1-5) now proven end-to-end, G14-8 closed. Separately fixed a Fabric git-sync identity conflict on `nb_11_gated_governance_sync` (duplicate/orphaned `logicalId` from a locally-invented `.platform` file never issued via Fabric's git connector) using `commitToGit`/`updateFromGit`; `nb_04a`/`nb_07a` incoming-change conflicts cleared in the same pass.
- 2026-08-10 (later same day): Found and fixed a real data-corruption bug in `nb_04a_extend_metadata_schema`'s Set B seed — a PySpark `Row()` kwarg order mismatch against `KPI_SCHEMA`'s declared field order caused `Domain`/`Owner`/`Description` values to silently rotate for all 5 certified call-center KPIs (`FCR`, `CSAT`, `AHT`, `PP_RNW_RATE`, `SLA_BRCH_RATE`) in the live `kpi_metadata` table and downstream in the `BrookfieldEnercare` semantic model's `_Measures.tmdl` (`FCR Rate`/`Avg CSAT`/`Avg Handle Time (sec)` descriptions had been overwritten with an owner email string instead of the real KPI description). Code fix applied to `nb_04a` (kwarg order corrected to match schema); live data fix applied via a throwaway temp Fabric notebook (`zz_temp_kpi_fix`, since the Lakehouse SQL analytics endpoint is read-only and rejects DML) executing targeted `UPDATE` statements via Spark — confirmed correct via sqlcmd re-query, then the temp item was deleted. Re-ran `nb_04_sempy_writeback` (`DEMO_MODE=False`) to push the corrected descriptions into the live semantic model; confirmed via `getDefinition` that `_Measures.tmdl` now has the correct descriptions. Committed and pushed both the `nb_04a` code fix and the Fabric-authored semantic-model `commitToGit` result to git; live `nb_04a` Fabric item also re-pushed via `updateDefinition` to match the fixed local code. Fabric workspace git status confirmed fully clean (`TOTAL_CHANGES=0`) at the end of this pass.
- 2026-08-11: Built the formal ontology / OKR business-objective layer (G11-1, design guide §5E) end-to-end in code: `sql/11_ontology_okr_schema.sql` + `sql/12_seed_ontology_okrs.sql`, `purview/okr-catalog.csv`, `nb_07a` ingestion, `nb_07` publish of `EnercareOKR`/`EnercareOKRKeyResult` Atlas entities with Data Product links, and a `nb_08` fix so each CDE's own Atlas entity is assigned to its parent Glossary Term (previously only the term's `bound_assets` were linked, not the CDE entity itself — found by code inspection). Added `nb_10` Cell 5a ontology scorecard. Corrected `docs/design-gap-analysis.md`'s stale "Purview typed-relationships not yet GA" claim. Live-apply (SQL + notebook reruns) intentionally left for a follow-up pass; see Phase 5 above.
- 2026-08-11 (later same day): Closed G15 (native Purview publication closed loop for `GT-SLA`) and committed the Phase 6 wireframe (G16) mapping the remaining 4 stakeholders (Victoria Tan, Rupal Solanki, Ranbir Singh, Shruthi Srinivas) onto the only 2 remaining native Unified Catalog workflow types — Data product access (P3, `DP-CUST360`) and Data product publish (P4, `DP-SVCPERF`/DOM-SVCDEL) — confirmed against Microsoft Learn that no other native workflow type exists (no native path for CDE/KPI/verified-answer/OKR approval; those stay SQL-controlled per Phase 4). Also confirmed Unified Catalog RBAC role assignment (Governance Domain Creator, Data Product Owner, Data Steward, etc.) has no REST API — UI-only, via Settings > Unified Catalog > Roles and permissions or a domain's Roles tab — distinct from the `contacts.owner`/`contacts.steward` metadata fields already scriptable via the Data Governance API. See `docs/purview-native-workflow-wireframe.md` for the full build template, sequencing, and required manual role setup per stakeholder.
- 2026-08-16: Completed the notebook consolidation (18 `nb_XX_name.Notebook` items → 10 current notebooks, `01_setup_source_data` … `10_reset_demo`) with a full cell-numbering/stale-cross-reference cleanup across all 10 — see `docs/01_Notebook_Description.md` (full rewrite) for the current per-notebook reference and a `nb_XX` → current-name mapping table. Repacked `sql/` (27 files, same numbers) into 3 notebook-aligned folders — see `docs/sql-prep-catalog.md`. Found and fixed a real drift bug during the repack: `01_setup_source_data` had embedded its own stale copy of the governance-metadata schema/seed SQL, missing a `governance_domain_stewards` column the authoritative `sql/02_metadata_foundation/06_purview_metadata_schema.sql` already had; removed the duplicate and replaced it with a prerequisite check. Also confirmed (open, not yet fixed) that `02_build_metadata_foundation`'s merged reconciliation section (`sm_annotations` build, formerly `nb_07b`) is unreachable dead code behind an unconditional `mssparkutils.notebook.exit()` mid-file.
