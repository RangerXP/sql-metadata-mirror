# SQL Prep — Artifact Catalog and Use-Case Narrative Map

**Purpose:** Canonical, current index of every SQL script in [`sql/`](../sql/), what it builds, which of
the 10 current notebooks consumes it, and how it earns its place in the demo's north-star
narrative — [Maria's Furnace](./purview-maria-north-star-scenario.md). This document is the
result of the SQL repack that aligned `sql/` with the 10-notebook structure (see
[`sql/README.md`](../sql/README.md) for the folder-level summary).

**Companion documents:** [`docs/01_Notebook_Description.md`](./01_Notebook_Description.md), [`docs/02_Notebook_Description.md`](./02_Notebook_Description.md), [`docs/03_Notebook_Description.md`](./03_Notebook_Description.md), [`docs/04_Notebook_Description.md`](./04_Notebook_Description.md), [`docs/05_Notebook_Description.md`](./05_Notebook_Description.md), [`docs/06_Notebook_Description.md`](./06_Notebook_Description.md), [`docs/07_Notebook_Description.md`](./07_Notebook_Description.md) — the equivalent per-notebook catalog, split one file per notebook as each is live-validated (see [`docs/08-10_Notebook_Description_pending.md`](./08-10_Notebook_Description_pending.md) for notebooks not yet split out).

---

## Repack summary

`sql/` was reorganized from a single flat folder (numbered by file-creation chronology) into
three folders that mirror the notebook that actually consumes each script. **File numbers
were preserved** — only the folder location changed — so every existing cross-reference
(a script's own `PRINT`/comment text citing another script by number, `tools/*.py` `Path()`
dependencies, notebook comments) continues to identify the same artifact. All of those
cross-references were updated in the same pass to include the new folder prefix.

| Old state | New state |
|---|---|
| 27 scripts flat in `sql/`, numbered by creation date | 27 scripts in 3 notebook-aligned folders, same numbers |
| Headers cited pre-consolidation notebook names (`nb_11`, `nb_07a`, `nb_04a`, `nb_05a`, `nb_14`/`15`/`16`/`17`, `nb_01`/`nb_02`/`nb_03`) | Headers cite the current 10-notebook names |
| `tools/*.py` referenced `sql/07_seed_purview_metadata.sql` / `sql/05_seed_purview_demo_data.sql` directly | Updated to `sql/02_metadata_foundation/...` / `sql/01_source_data/...` |
| `sql/README.md` described a "next-step modernization" that never happened | Describes the structure as-built |

No SQL logic changed. This was a structural/annotation repack only, matching the same
discipline already applied to the 10 notebooks (see prior session work: cell numbering,
merge-header cleanup, stale cross-reference correction).

---

## Cast reference (for the narrative column below)

| Persona | Role |
|---|---|
| **Maria Castellanos** | The customer whose furnace outage and billing case is the north star |
| **Tom Nguyen** | Call Center Specialist serving Maria in real time (Act 1) |
| **Victoria Tan** | CCO, Domain Owner DOM-CUSTOPS, sees the aggregate case in review (Act 2) |
| **Ci Zhu** | Data Governance Admin / Glossary Owner, proves single-source-of-truth to the auditor (Act 3) |
| **Rupal Solanki** | Data Steward, DOM-CUSTOPS (customer data quality, consent) |
| **Shruthi Srinivas** | Data Steward, DOM-SVCDEL (service/equipment data quality) |
| **Ranbir Singh** | Domain Owner, DOM-SVCDEL (field operations) |

---

## `01_source_data/` — feeds `01_setup_source_data.Notebook`

| # | Script | What it builds | Narrative tie-in |
|---|---|---|---|
| 02 | `02_sub2_sql_source_schema.sql` | The 7-table transactional core (products, customers, service_accounts, equipment_registry, contracts, service_requests, billing_transactions) | The literal tables that hold Maria's furnace rental, her service request, and her billing charge — the physical bedrock every act reads from. |
| 04 | `04_purview_demo_extensions.sql` | PII/classifier extensions (DOB, SIN partial, GPS, payment partials) + 6 new tables (employees, customer_consents, customer_complaints, service_zones, data_owners_directory, audit_data_access) | Adds `customer_consents` and `customer_complaints` — the tables that let Ci Zhu prove Maria's consent state and complaint history are governed, not just her furnace ticket. |
| 05 | `05_seed_purview_demo_data.sql` | Synthetic data sized to fire Purview classifiers; explicitly seeds Maria Castellanos's consent state, SLA complaint, and Tom Nguyen's access-audit trail | Directly seeds the Act 1/Act 2 evidence: Maria's consent record Rupal stewards, her complaint Victoria reviews, and the audit row proving Tom's access was purpose-bound. |
| 08 | `08_workspace_identity_login.sql` | Grants Fabric Mirroring access to `sqldemo` for the Enercare-West3 workspace identity | Invisible plumbing — no persona-facing role, but everything downstream (every other script, every notebook) depends on this mirror connection existing. |

## `02_metadata_foundation/` — feeds `02_build_metadata_foundation.Notebook`

| # | Script | What it builds | Narrative tie-in |
|---|---|---|---|
| 06 | `06_purview_metadata_schema.sql` | SQL-first governance metadata schema: domains, data products, glossary terms, CDEs, role assignments, labels | The schema that lets Ci Zhu say "one governed definition" — domains map to DOM-CUSTOPS/DOM-SVCDEL/DOM-REVCON, the exact domains Victoria and Ranbir own. |
| 07 | `07_seed_purview_metadata.sql` | Baseline seed: 3 domains, 3 data products, 35 glossary terms, 12 CDEs, 48 role assignments, 9 labels | Seeds `DP-CUST360` (Customer 360) — the data product Tom and Victoria both query for Maria — and the CDEs (Customer Identifier, SIN, Consent Status) Ci Zhu cites in Act 3. |
| 11 | `11_ontology_okr_schema.sql` | Business-objective layer: `governance_okrs` / `governance_okr_key_results` / `governance_okr_data_products` | Lets Victoria's "why does this keep happening" question connect to a real Objective (`OKR-SVCDEL-SLA` — Protect SLA Attainment), not just a KPI number. |
| 12 | `12_seed_ontology_okrs.sql` | Seeds the 3 Enercare OKRs, 5 key results, 3 data-product links | `OKR-SVCDEL-SLA`'s definition literally cites "closing the auto-suppression dispatch gap surfaced in Act 2 of the Maria northstar scenario" — this script is written directly from Maria's case. |
| 19 | `19_tag_annotation_extraction.sql` | Native T-SQL `@tag:` extraction from view/procedure definitions into `governance_requests`/`governance_events` | The mechanism behind Act 3's "nothing gets adopted without review" claim — any new SQL object touching Maria's data surfaces here first. |
| 20 | `20_g18a_demo_views.sql` | Two demo views: `vw_technician_utilization_summary` (Approved) and `vw_employee_pii_export` (Rejected for ungoverned PII) | Proves the gate has teeth: an attempt to expose raw SIN/DOB (the same PII class protecting Maria's own SIN) is demonstrably blocked, not just detected. |

## `07_governance_gates/` — feeds `07_apply_approved_changes.Notebook`, evidenced by `08_validate_governance_evidence.Notebook` and `09_reconcile_semantic_model.Notebook`

| # | Script | What it builds | Narrative tie-in |
|---|---|---|---|
| 09 | `09_gated_governance_requests_schema.sql` | Legacy `governance_change_requests` audit-trailed workflow table (4 original gate types) | The original mechanism proving Ci Zhu's Act 3 line: "it would mean someone edited the semantic model... requires my review." |
| 10 | `10_seed_gated_governance_scenarios.sql` | Seeds the 4 Phase 4 demo scenarios, one per stakeholder, Ci Zhu as constant approver | Literally casts Ranbir Singh, Victoria Tan, and the rest as requesters against Ci Zhu's approval — the Act 3 governance chain in seed-data form. |
| 13 | `13_closed_loop_governance_ledger.sql` | Durable unified ledger: `governance_requests` / `governance_events` / `governed_object_versions` / `governance_target_receipts` / `governance_object_mappings` | The evidence spine Ci Zhu points to when the auditor asks "prove it" — every decision on every object Maria's case touches is queryable from one place. |
| 14 | `14_migrate_legacy_governance_to_unified_ledger.sql` | Historical backfill of the 4 legacy gate rows into the unified ledger | Ensures Act 3's "one authoritative history" claim covers scenarios seeded before the ledger existed, not just new ones. |
| 15 | `15_reconcile_gt_sla_duplicate_governance.sql` | Marks the legacy SQL `GT-SLA` gate `Superseded` in favor of the native Purview workflow's more rigorous evidence | Resolves the exact SLA-breach term at the center of Maria's missed-technician case down to one authoritative record. |
| 16 | `16_add_ai_instruction_gate.sql` | Gates AI Instructions (Copilot/Data Agent grounding content) through Draft→Approved→Applied | Protects the exact grounding text the Data Agent uses when Tom asks "show me Maria's furnace status" (Act 1, Acceptance Criterion 7). |
| 17 | `17_backfill_role_assignment_ledger.sql` | Operator-attested backfill of Data Product / domain role-assignment evidence | Documents who is really Data Product Owner on Customer 360 and Service Performance — the roles Victoria and Ranbir hold over Maria's data. |
| 18 | `18_add_okr_approval_gate.sql` | Gates OKR Key Result creation through the unified ledger | Adds `KR-TECH-UTIL` (Technician Utilization Rate) under `OKR-SVCDEL-SLA` — a real key result tracing back to the dispatch problem in Maria's case. |
| 21 | `21_g18a_demo_decisions.sql` | Drives the two `20_g18a_demo_views.sql` outcomes to terminal state (one Approved+Applied, one Rejected) | The concrete "approved" and "blocked" proof points Ci Zhu shows the auditor as evidence the gate is real, not theoretical. |
| 22 | `22_victoria_data_product_owners_followup.sql` | Backfills Victoria Tan's real Data Product Owners role grant on Customer Operations | Closes a real gap in Victoria's own authority over the exact data product (`DP-CUST360`) that holds Maria's record. |
| 23 | `23_g20_synthetic_governance_attestation.sql` | Lightweight attested records for domains, OKR Objectives, Data Product Certification, Purview scan completion | Ensures every foundational object touching Maria's case (not just the stakeholder-tied moments) has *some* governance record — no "zero gate" gaps. |
| 24 | `24_g19_ontology_governance_completeness.sql` | Real certification/recertification/ownership-validation lifecycle for OKR Objectives | Gives `OKR-SVCDEL-SLA` (the SLA-protection objective born from Maria's case) a full, real approval lifecycle, not just a synthetic stamp. |
| 25 | `25_g19_ai_instruction_lifecycle_gate.sql` | AI Instruction effective-date activation and rollback scenarios | Proves the Data Agent's Maria-facing grounding content can be safely versioned and rolled back if a flawed edit slips through. |
| 26 | `26_g19_data_product_certification_lifecycle.sql` | Real certify/de-certify/expiration-review lifecycle for Data Products | Gives `DP-SVCPERF` (Service Performance — the data product behind Maria's missed dispatch) a real certification cycle, distinct from publish/access. |
| 27 | `27_g19_g18_cde_ontology_mapping.sql` | Maps a pending view to a real CDE; maps an approved view to its Key Result | Ties `vw_technician_utilization_summary` (built to explain dispatch load, Maria's root cause) to `KR-TECH-UTIL` — closing the ontology loop. |
| 28 | `28_g19_semantic_promotion_gate.sql` | Creates the Approved request that `09_reconcile_semantic_model` reconciles into a real new semantic-model measure | The final step that turns the technician-utilization insight born from Maria's case into a real, governed, queryable measure. |

---

## Validation performed

- **Structural:** all 27 files confirmed present after the move (`git status` shows 27 renames, zero deletions/additions), tracked with history via `git mv`.
- **Reference integrity:** repo-wide search confirms zero remaining un-prefixed `sql/NN_name.sql` `Path()` references in `tools/*.py` (12 references across 9 files, all updated and each file re-compiled clean).
- **Notebook comments:** all `sql/NN_name.sql` citations in notebook source (8 occurrences across `01_setup_source_data.Notebook` and `02_build_metadata_foundation.Notebook`) updated to the new paths; both notebooks re-compiled clean.
- **Stale naming:** repo-wide search confirms zero remaining pre-consolidation `nb_XX` notebook references inside any `sql/*.sql` file.
- **Broken links:** markdown links in `docs/governance-lifecycle-restage-review.md`, `docs/purview_expected_vs_live_delta.md`, and `docs/ten-notebook-governance-reorg-plan.md` that pointed at the old flat `sql/NN_name.sql` paths were updated to resolve correctly.
- **Actionable runbooks:** `docs/runbooks/phase4-gated-governance-workflow.md` and `docs/runbooks/p1-native-term-publication.md` (the only two runbooks with literal `:r sql/...` / "run sql/..." executable instructions) updated to the new paths.
- **Historical logs left untouched:** dated build-progress documents (`docs/build-scorecard.md`, `docs/design-gap-analysis.md`, `docs/Enercare-Demo-SemPy-Design-Guide.md`, and similar point-in-time records) were intentionally **not** edited — their `sql/NN` citations describe what was true at the time and remain historically accurate; this document is the current authoritative index going forward.
- **No live database changes:** this was a source-control and documentation repack only. No script was executed against `sqldemo` as part of this work.

## Addendum (2026-08-16) — notebook 1 governance-metadata duplication removed

After this repack, `01_setup_source_data.Notebook` was found to still carry its own embedded
copy of the governance-metadata schema/seed SQL (the same content as `06_purview_metadata_schema.sql`
/ `07_seed_purview_metadata.sql` / `11_ontology_okr_schema.sql` / `12_seed_ontology_okrs.sql`
above), and that copy had drifted behind — it was missing a `governance_domain_stewards` column
the real script already had. The duplicate create/seed logic was removed from the notebook; it
now only verifies `dbo.governance_domains` is populated and raises a `RuntimeError` naming these
four scripts if it isn't. `06`/`07`/`11`/`12` are now the sole source of this metadata — see
`docs/01_Notebook_Description.md` for the updated notebook description.
