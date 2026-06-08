# Build Evaluation Matrix (nb_01 -> nb_07)

Purpose: provide a clean, repeatable rebuild matrix to validate sequencing, dependencies, and north-star alignment for the Enercare demo construct.

Source alignment:
- Design construct: docs/Enercare-Demo-SemPy-Design-Guide.md
- Execution plan: docs/purview-5-day-execution-plan.md
- North star: docs/purview-maria-north-star-scenario.md

## How To Use

1. Run notebooks in matrix order.
2. For each row, record evidence and status.
3. If a row fails, stop and resolve before moving to dependent rows.
4. At the end, score north-star criteria NS-1 through NS-8.

## Run Metadata

| Field | Value |
|---|---|
| Run ID | |
| Date/Time (UTC) | |
| Workspace | |
| Branch/Commit | |
| Operator | |
| Notes | |

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
| 1 | Baseline data seed | fabric/nb_01_setup_demo_environment.Notebook | none (seed source) | n/a | lh_enercare_demo source tables populated | row counts present for products/customers/service_accounts/equipment_registry/contracts/service_requests/billing_transactions | NS-1, NS-2 | | |
| 2 | SQL authoritative publish | fabric/nb_05a_publish_synthetic_data_to_sql.Notebook | lh_enercare_demo.* | Seq 1 | sqldemo dbo base tables loaded; sql/04-07 applied; governance tables seeded | SQL row-count checks GREEN for base + governance sets | NS-4, NS-6 | | |
| 3 | Mirror operational sync | Fabric mirror refresh (non-notebook) | sqldemo dbo tables | Seq 2 | mirrored SQL tables visible under sqldemo/sqldemo-mirror | all expected mirrored tables visible and queryable | NS-6 | | |
| 4 | Star schema rebuild | fabric/nb_03_pbi_star_schema.Notebook | mirrored dbo tables (or fallback) | Seq 3 (or Seq 1 fallback) | dim/fact model tables rebuilt in lh_enercare_demo | notebook completes; output table counts present | NS-1, NS-2 | | |
| 5 | Metadata pipeline | fabric/nb_02_metadata_pipeline_demo.Notebook | lh_enercare_demo.* | Seq 1/4 | lh_metadata.asset_metadata/column_metadata/kpi_metadata/vw_business_metadata_current | view and table counts non-zero; metadata rows load | NS-2, NS-6 | | |
| 6 | Metadata schema extension | fabric/nb_04a_extend_metadata_schema.Notebook | lh_metadata.kpi_metadata, asset_metadata | Seq 5 | lh_metadata.ai_metadata/data_owners/lineage_edges and extended kpi metadata | tables exist; seeded rows present | NS-2, NS-4, NS-6 | | |
| 7 | Governance metadata ingest (SQL-mirror first) | fabric/nb_07a_ingest_customer_files.Notebook | mirrored governance tables (governance_*) | Seq 2 + Seq 3 | lh_metadata.metadata.domains/data_products/glossary_terms/cdes/role_assignments/label_assignments | expected counts 3/3/35/12/48/9 | NS-2, NS-4 | | |
| 8 | Semantic annotation merge | fabric/nb_07b_merge_customer_metadata.Notebook | lh_metadata.metadata.* + semantic inventory | Seq 7 | lh_metadata.metadata.sm_annotations | sm_annotations row count > 0 and key coverage by annotation type | NS-2, NS-7 | | |
| 9 | SemPy writeback | fabric/nb_04_sempy_writeback.Notebook | lh_metadata.vw_business_metadata_current, kpi_metadata, ai_metadata, optional sm_annotations | Seq 5/6 and optional Seq 8 | semantic model descriptions/annotations updated | target model objects show expected description/annotation updates | NS-2, NS-7, NS-8 | | |
| 10 | Verified Q&A push | fabric/nb_05_push_qa_verified_answers.Notebook | lh_metadata.ai_metadata | Seq 6 | semantic model instruction/verified-answer annotation payload | annotation present in model and within configured length | NS-7, NS-8 | | |
| 11 | Purview admin SIT setup | fabric/nb_06a_create_sin_backstop.Notebook | Purview API access (no SQL table dependency) | operational prerequisite | ENERCARE.PRIVACY.SIN_BACKSTOP enabled | verify classification and rule enabled | NS-3, NS-5 | | |
| 12 | Purview publish (guarded) | fabric/nb_07_publish_to_purview.Notebook | lh_metadata.metadata.domains/data_products/role_assignments | Seq 7 | payload artifacts; optional live publish if override enabled | guard status expected for SQL-mirror-only runs; payload files generated | NS-4, NS-6, NS-8 | | |

## Read/Write Dependency Assertions

Use this section to explicitly verify each dependency edge is valid in your run.

| Consumer Read | Producer Write | Check | Result |
|---|---|---|---|
| mirrored dbo base tables (nb_03) | nb_05a SQL publish + mirror sync | mirrored tables query succeeds | |
| lh_metadata.vw_business_metadata_current (nb_04) | nb_02 metadata pipeline | view exists and row count > 0 | |
| lh_metadata.ai_metadata (nb_05 push QA) | nb_04a schema extension/seed | table exists and contains active rows | |
| lh_metadata.metadata.* (nb_07b/nb_07 publish) | nb_07a ingest | expected six-table counts match | |
| lh_metadata.metadata.sm_annotations (optional nb_04 enrich) | nb_07b merge | table exists, non-zero rows | |

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
