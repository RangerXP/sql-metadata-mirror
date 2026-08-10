# Enercare Build Scorecard

**Last updated:** 2026-08-10
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
| G11 Ontology/B2C extensions | ⏸ Deferred (Phase D) |
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
| G14-8 Phase 4 closeout (full propagation + `nb_10` reconfirm) | � Done — full chain proven end-to-end, `nb_10` scorecard 0 `ACTION_REQUIRED` across all phases |

> Note: `docs/design-gap-analysis.md` Quick Status rows for G14-4..G14-7 still show 🔴 as of this scorecard's last update — pending sync now that G14-8 has closed out.

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

## Update Log

- 2026-08-09: Scorecard created. Captures state after all 4 gated-governance scenarios proven live and propagation chain steps 1-3 completed; `nb_08` failing, diagnostics pushed, re-run pending.
- 2026-08-10: Fixed `nb_08`/`nb_09` stale Spark catalog schema bug (`refreshTable()` + column pruning), reran and confirmed both `Completed`. Reran `nb_10`, confirmed 0 `ACTION_REQUIRED` across all phases — full propagation chain (steps 1-5) now proven end-to-end, G14-8 closed. Separately fixed a Fabric git-sync identity conflict on `nb_11_gated_governance_sync` (duplicate/orphaned `logicalId` from a locally-invented `.platform` file never issued via Fabric's git connector) using `commitToGit`/`updateFromGit`; `nb_04a`/`nb_07a` incoming-change conflicts cleared in the same pass.
