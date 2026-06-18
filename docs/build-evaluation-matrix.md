# Build Evaluation Matrix (nb_01 -> nb_07)

Purpose: provide a clean, repeatable rebuild matrix to validate sequencing, dependencies, and north-star alignment for the Enercare demo construct.

Source alignment:
- Design construct: docs/Enercare-Demo-SemPy-Design-Guide.md
- Execution plan (2-day cadence): docs/purview-2-day-execution-plan.md
- North star: docs/purview-maria-north-star-scenario.md

## How To Use

1. Run notebooks in matrix order.
2. For each row, record evidence and status.
3. If a row fails, stop and resolve before moving to dependent rows.
4. At the end, score north-star criteria NS-1 through NS-8.

## Source Control Guardrails (Mandatory)

1. Canonical Data Agent folder pattern:
`fabric/Enercare Data Agent.DataAgent/` is the only valid repo path for the primary operational agent.
Do not keep or create parallel GUID-named DataAgent folders for the same display name.
2. Sync checkpoint after git pushes:
If a commit changes any file under `fabric/*.DataAgent/` or any `fabric/*.Notebook/`, stop and run Fabric Source Control sync before any additional live workspace edits.
3. Do not interleave unsynced planes:
Do not patch Fabric item metadata through API/portal while pending Source Control updates or conflicts exist.
4. Conflict recovery rule:
If Fabric reports duplicate-name conflicts for a Data Agent, treat git as source of truth, remove unbound workspace duplicates, then re-run Source Control update.

## Run Metadata

| Field | Value |
|---|---|
| Run ID | |
| Date/Time (UTC) | |
| Workspace | |
| Branch/Commit | |
| Operator | |
| Notes | |

### Status Key

| Value | Meaning |
|---|---|
| NOT RUN | Step not executed yet in this run |
| PASS | Step executed and acceptance checks passed |
| FAIL | Step executed and one or more acceptance checks failed |
| BLOCKED | Step could not run due to unmet dependency or environment issue |
| N/A | Not applicable for this run mode |

### Recommended Run ID Format

`YYYYMMDD-HHMM-<operator>-rebuild-01`

Example: `20260608-1545-sean-rebuild-01`

## North-Star Criteria Legend

| ID | Criterion |
|---|---|
| NS-1 | Single customer identity across surfaces |
| NS-2 | Single KPI definition across agent, report, governance |
| NS-3 | Privacy controls enforced by governed data surfaces |
| NS-4 | Regulatory compliance traceable to terms/CDEs/assets |
| NS-5 | Sensitivity labels/policies enforce behavior |
| NS-6 | Lineage answers source-to-consumption provenance |
| NS-7 | Data agent answers in business language with context |
| NS-8 | Tom/Victoria/Ci Zhu see one reconciled truth |

## Ordered Build Matrix

| Seq | Stage | Notebook/Step | Dependency Reads | Expected Producer (Earlier Stage) | Expected Outputs | Validation Check | North-Star Link | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Baseline data seed | fabric/nb_01_setup_demo_environment.Notebook | none (seed source) | n/a | lh_enercare_demo source tables populated | row counts present for products/customers/service_accounts/equipment_registry/contracts/service_requests/billing_transactions | NS-1, NS-2 | PASS | Completed. Call-center tables written: cc_agents=15, ref_cc_billing_adj_category=12, fct_cc_interactions=300, fct_cc_transcript_turns=3479. `ref_cc_billing_adj_category` flagged as optional orphaned governance review only; non-blocking for nb_04 writeback. |
| 2 | SQL authoritative publish | fabric/nb_05a_publish_synthetic_data_to_sql.Notebook | lh_enercare_demo.* | Seq 1 | sqldemo dbo base tables loaded; sql/04-07 applied; governance tables seeded | SQL row-count checks GREEN for base + governance sets | NS-4, NS-6 | | |
| 3 | Mirror operational sync | Fabric mirror refresh (non-notebook) | sqldemo dbo tables | Seq 2 | mirrored SQL tables visible under sqldemo/sqldemo-mirror | all expected mirrored tables visible and queryable | NS-6 | | |
| 4 | Star schema rebuild | fabric/nb_03_pbi_star_schema.Notebook | mirrored dbo tables (or fallback) | Seq 3 (or Seq 1 fallback) | dim/fact model tables rebuilt in lh_enercare_demo | notebook completes; output table counts present | NS-1, NS-2 | | |
| 5 | Metadata pipeline | fabric/nb_02_metadata_pipeline_demo.Notebook | lh_enercare_demo.* | Seq 1/4 | lh_metadata.asset_metadata/column_metadata/kpi_metadata/vw_business_metadata_current | view and table counts non-zero; metadata rows load | NS-2, NS-6 | PASS | Run summary: assets_extracted=4, columns_extracted=53, kpis_extracted=12. Phases 0-3 complete. Notebook summary reported Phase 4/5 as dry-run; treated as observed notebook behavior and non-blocking for sequencing into nb_04a/nb_04. |
| 6 | Metadata schema extension | fabric/nb_04a_extend_metadata_schema.Notebook | lh_metadata.kpi_metadata, asset_metadata | Seq 5 | lh_metadata.ai_metadata/data_owners/lineage_edges and extended kpi metadata | tables exist; seeded rows present | NS-2, NS-4, NS-6 | | |
| 7 | Governance metadata ingest (SQL-mirror first) | fabric/nb_07a_ingest_customer_files.Notebook | mirrored governance tables (governance_*) | Seq 2 + Seq 3 | lh_metadata.metadata.domains/data_products/glossary_terms/cdes/role_assignments/label_assignments | expected counts 3/3/35/12/48/9 | NS-2, NS-4 | | |
| 8 | Semantic annotation merge | fabric/nb_07b_merge_customer_metadata.Notebook | lh_metadata.metadata.* + semantic inventory | Seq 7 | lh_metadata.metadata.sm_annotations | sm_annotations row count > 0 and key coverage by annotation type | NS-2, NS-7 | | |
| 9 | SemPy writeback | fabric/nb_04_sempy_writeback.Notebook | lh_metadata.vw_business_metadata_current, kpi_metadata, ai_metadata, optional sm_annotations | Seq 5/6 and optional Seq 8 | semantic model descriptions/annotations updated | target model objects show expected description/annotation updates | NS-2, NS-7, NS-8 | | |
| 10 | Verified Q&A push | fabric/nb_05_push_qa_verified_answers.Notebook | lh_metadata.ai_metadata | Seq 6 | semantic model instruction/verified-answer annotation payload | annotation present in model and within configured length | NS-7, NS-8 | | |
| 11 | Purview admin SIT setup | fabric/nb_06a_create_sin_backstop.Notebook | Purview API access (no SQL table dependency) | operational prerequisite | ENERCARE.PRIVACY.SIN_BACKSTOP enabled | verify classification and rule enabled | NS-3, NS-5 | | |
| 12 | Purview publish (guarded) | fabric/nb_07_publish_to_purview.Notebook | lh_metadata.metadata.domains/data_products/role_assignments | Seq 7 | payload artifacts; optional live publish if override enabled | guard status expected for SQL-mirror-only runs; payload files generated | NS-4, NS-6, NS-8 | | |

## Preflight Baseline (Static, before live run)

This section captures the expected sequencing verdict from the current construct before executing notebooks. Update only if architecture changes.

| Seq | Expected Sequencing Verdict | Known Risk | Preflight Status |
|---|---|---|---|
| 1 | Root producer, no upstream dependency | Low | NOT RUN |
| 2 | Depends on Seq 1 | Medium: SQL auth/network; Phase B SQL is notebook-owned and does not require `/lakehouse/default/Files/sql` | NOT RUN |
| 3 | Depends on Seq 2 | Medium: mirror lag/refresh delays | NOT RUN |
| 4 | Depends on Seq 3 (or fallback to Seq 1 if explicitly enabled) | Medium: mirror table visibility | NOT RUN |
| 5 | Depends on Seq 1/4 data availability | Low | NOT RUN |
| 6 | Depends on Seq 5 metadata tables | Low | NOT RUN |
| 7 | Depends on Seq 2 + Seq 3 governance mirror tables | High: missing mirrored governance tables blocks run | NOT RUN |
| 8 | Depends on Seq 7 and semantic inventory access | Medium: model inventory access and lakehouse context | NOT RUN |
| 9 | Depends on Seq 5/6; stronger with Seq 8 | Medium: SemPy Labs package/runtime availability | NOT RUN |
| 10 | Depends on Seq 6 ai metadata | Low | NOT RUN |
| 11 | Independent of SQL table chain; Purview admin/API dependent | Medium: Purview role/token/API access | NOT RUN |
| 12 | Depends on Seq 7; publish path intentionally guardable | Medium: expected BLOCKED/N/A for SQL-mirror-only if guard active | NOT RUN |

## Gate Checks Before Seq 1

| Gate | Pass Condition | Result |
|---|---|---|
| Branch/commit pinned | Branch and commit captured in Run Metadata | |
| Lakehouse file mounts present | `/lakehouse/default/Files/tools` optional for SIN helper override; no `/lakehouse/default/Files/sql` upload required for `nb_05a` | |
| SQL connectivity smoke test | `nb_05b_test_sql_connectivity` succeeds (or known principal remediation documented) | |
| Mirror readiness path agreed | Operator confirms whether run uses mirrored source mode vs explicit fallback mode | |
| Purview mode declared | `SQL_MIRROR_ONLY_DEPLOYMENT` behavior accepted for this run | |

## Read/Write Dependency Assertions

Use this section to explicitly verify each dependency edge is valid in your run.

| Consumer Read | Producer Write | Check | Result |
|---|---|---|---|
| mirrored dbo base tables (nb_03) | nb_05a SQL publish + mirror sync | mirrored tables query succeeds | |
| lh_metadata.vw_business_metadata_current (nb_04) | nb_02 metadata pipeline | view exists and row count > 0 | PASS — nb_02 completed with metadata extraction summary (assets=4, columns=53, kpis=12); downstream nb_04 read path unlocked. |
| lh_metadata.ai_metadata (nb_05 push QA) | nb_04a schema extension/seed | table exists and contains active rows | |
| lh_metadata.metadata.* (nb_07b/nb_07 publish) | nb_07a ingest | expected six-table counts match | |
| lh_metadata.metadata.sm_annotations (optional nb_04 enrich) | nb_07b merge | table exists, non-zero rows | |

## Live Run Log

| Seq | Update |
|---|---|
| 1 | PASS — nb_01 completed. Operator note: "All tables ready. Run nb_02_metadata_pipeline_demo.py next." |
| 5 | PASS — nb_02 completed. Operator note: "Phases 0-3 completed; notebook summary showed Phase 4/5 dry-run behavior. Next: nb_04a. If needed, separately validate nb_02 comment/XP and Purview credentialed paths in a dedicated run." |

## Known Construct Notes

1. nb_06_purview_sql_grants is not part of the current branch construct.
2. Minimal SQL grant guidance survives in nb_05b as manual operator instructions.
3. nb_07_publish_to_purview is intentionally guardable for SQL-mirror-only deployment mode.
4. nb_04 can run without sm_annotations, but annotation-enrichment paths are stronger after nb_07b.

## Final North-Star Scorecard

| North-Star ID | Pass/Fail | Evidence |
|---|---|---|
| NS-1 | | |
| NS-2 | | |
| NS-3 | | |
| NS-4 | | |
| NS-5 | | |
| NS-6 | | |
| NS-7 | | |
| NS-8 | | |

## Overall Rebuild Outcome

| Decision | Value |
|---|---|
| Build Outcome | PASS / PARTIAL / FAIL |
| First Failing Sequence | |
| Primary Blocker | |
| Remediation Owner | |
| Retest Date | |

