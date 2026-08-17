# SQL execution surface for the Enercare governance demo

This folder holds every T-SQL script executed against `sqldemo` (Azure SQL, `sqlserver-sk2wus3.database.windows.net`,
sub2) to build and operate the Enercare governance demo. Scripts are grouped into three
folders that mirror the current 10-notebook lifecycle (`01_setup_source_data.Notebook`
through `10_reset_demo.Notebook`) instead of file-creation chronology. File numbers are
preserved from the original historical sequence so existing citations, receipts, and
`PRINT` messages that reference a script by number (e.g. "run sql/27 first") still
resolve to the same artifact — only the folder location changed.

For the full artifact-to-use-case-narrative catalog, see
[`docs/sql-prep-catalog.md`](../docs/sql-prep-catalog.md).

## Folder structure

### `01_source_data/` — feeds `01_setup_source_data.Notebook`

The authoritative sub2 transactional schema and its Purview-classifier-ready extensions.

| Script | Purpose |
|---|---|
| `02_sub2_sql_source_schema.sql` | Core seven-table transactional source schema (products, customers, service_accounts, equipment_registry, contracts, service_requests, billing_transactions). |
| `04_purview_demo_extensions.sql` | Extends the seven tables with classifiable PII (DOB, SIN partial, GPS, payment partials); adds employees, customer_consents, customer_complaints, service_zones, data_owners_directory, audit_data_access. |
| `05_seed_purview_demo_data.sql` | Seeds synthetic operational data sized to fire Purview classifiers, including Maria Castellanos's consent/complaint/audit trail. |
| `08_workspace_identity_login.sql` | One-time grant of Fabric Mirroring access to `sqldemo` via the Enercare-West3 workspace identity. Environment prerequisite, not tied to a specific run. |

### `02_metadata_foundation/` — feeds `02_build_metadata_foundation.Notebook`

The SQL-first governance metadata plane (domains, data products, glossary, CDEs, roles,
labels, OKRs) plus the native `@tag:` discovery mechanism that this notebook's thin-reader
phase surfaces for steward review.

| Script | Purpose |
|---|---|
| `06_purview_metadata_schema.sql` | Governance domains, data products, glossary terms, CDEs, role assignments, label assignments — the SQL-first source of truth mirrored into Fabric. |
| `07_seed_purview_metadata.sql` | Baseline domain / data-product / glossary / CDE / role / label seed data (3 domains, 3 data products, 35 glossary terms, 12 CDEs, 48 roles, 9 labels). |
| `11_ontology_okr_schema.sql` | Business-objective layer: `governance_okrs`, `governance_okr_key_results`, `governance_okr_data_products`. |
| `12_seed_ontology_okrs.sql` | Seeds the 3 Enercare OKRs, 5 key results, and their data-product links. |
| `19_tag_annotation_extraction.sql` | Native T-SQL extraction of `@tag:` comment markers from view/procedure definitions into `governance_requests`/`governance_events` — the source this notebook's thin-reader phase surfaces for stewards. |
| `20_g18a_demo_views.sql` | Two demo views exercising the tag-discovery lifecycle: one approved (`vw_technician_utilization_summary`), one rejected for ungoverned PII (`vw_employee_pii_export`). |

### `07_governance_gates/` — feeds `07_apply_approved_changes.Notebook` and the closed-loop ledger consumed by `08_validate_governance_evidence.Notebook` / `09_reconcile_semantic_model.Notebook`

The gated-approval request/event ledger, every individual governance-gate demo scenario,
and the decisions that move them to their terminal state. This is the largest and most
heterogeneous category — see the SQL Prep catalog for the full per-script narrative tie-in.

| Script | Purpose |
|---|---|
| `09_gated_governance_requests_schema.sql` | Legacy `dbo.governance_change_requests` audit-trailed workflow table (Draft → PendingApproval → Approved/Rejected → Applied) for the four original Phase 4 gate types. |
| `10_seed_gated_governance_scenarios.sql` | Seeds the four Phase 4 demo scenarios in `PendingApproval`, one per Maria-northstar stakeholder, Ci Zhu as constant approver. |
| `13_closed_loop_governance_ledger.sql` | Durable unified ledger foundation: `governance_requests` / `governance_events` / `governed_object_versions` / `governance_target_receipts` / `governance_object_mappings`. |
| `14_migrate_legacy_governance_to_unified_ledger.sql` | Historical backfill of the 4 legacy `governance_change_requests` rows into the unified ledger (no re-approval). |
| `15_reconcile_gt_sla_duplicate_governance.sql` | Marks the legacy SQL `GT-SLA` gate `Superseded` in favor of the native Purview workflow's more rigorous evidence chain. |
| `16_add_ai_instruction_gate.sql` | Gates AI Instructions through the same Draft→Approved→Applied cycle already proven for KPI/CDE/Verified-Answer/Glossary-Term. |
| `17_backfill_role_assignment_ledger.sql` | Operator-attested backfill of Data Product / domain role-assignment evidence (Unified Catalog RBAC has no REST API). |
| `18_add_okr_approval_gate.sql` | Gates OKR Key Result creation through the unified ledger (OKRs had no prior approval gate). |
| `21_g18a_demo_decisions.sql` | Drives the two `20_g18a_demo_views.sql` outcomes to their real terminal state (one Approved+Applied, one Rejected). |
| `22_victoria_data_product_owners_followup.sql` | Backfills a real missing Data Product Owners role grant discovered live during the P3/P4 build. |
| `23_g20_synthetic_governance_attestation.sql` | Lightweight attested governance records for foundational objects that don't warrant a full interactive workflow (domains, OKR Objectives, Data Product Certification, Purview scan completion). |
| `24_g19_ontology_governance_completeness.sql` | Real interactive Objective-level certification/recertification/ownership-validation lifecycle for OKRs, beyond G20's attestation stopgap. |
| `25_g19_ai_instruction_lifecycle_gate.sql` | AI Instruction effective-date activation and rollback scenarios, same gate as `16`. |
| `26_g19_data_product_certification_lifecycle.sql` | Real Data Product certification/de-certification/expiration-review lifecycle, distinct from Publish (P4) and Access (P3). |
| `27_g19_g18_cde_ontology_mapping.sql` | Closes G18-A's two open gaps: maps a pending view to a real CDE, and maps an approved view to its Key Result. |
| `28_g19_semantic_promotion_gate.sql` | Creates the Approved request that `09_reconcile_semantic_model` reconciles into a real new semantic-model measure — gated on `27`'s ontology mapping already being Completed. |

## Recommended execution order

1. `01_source_data/02_sub2_sql_source_schema.sql`
2. `01_source_data/04_purview_demo_extensions.sql`
3. `01_source_data/05_seed_purview_demo_data.sql`
4. `01_source_data/08_workspace_identity_login.sql` (one-time, environment setup)
5. `02_metadata_foundation/06_purview_metadata_schema.sql`
6. `02_metadata_foundation/07_seed_purview_metadata.sql`
7. `02_metadata_foundation/11_ontology_okr_schema.sql`
8. `02_metadata_foundation/12_seed_ontology_okrs.sql`
9. `02_metadata_foundation/19_tag_annotation_extraction.sql`
10. `02_metadata_foundation/20_g18a_demo_views.sql`
11. `07_governance_gates/09_gated_governance_requests_schema.sql`
12. `07_governance_gates/10_seed_gated_governance_scenarios.sql`
13. `07_governance_gates/13_closed_loop_governance_ledger.sql`
14. `07_governance_gates/14_migrate_legacy_governance_to_unified_ledger.sql`
15. `07_governance_gates/15_reconcile_gt_sla_duplicate_governance.sql`
16. `07_governance_gates/16_add_ai_instruction_gate.sql`
17. `07_governance_gates/17_backfill_role_assignment_ledger.sql`
18. `07_governance_gates/18_add_okr_approval_gate.sql`
19. `07_governance_gates/21_g18a_demo_decisions.sql`
20. `07_governance_gates/22_victoria_data_product_owners_followup.sql`
21. `07_governance_gates/23_g20_synthetic_governance_attestation.sql`
22. `07_governance_gates/24_g19_ontology_governance_completeness.sql`
23. `07_governance_gates/25_g19_ai_instruction_lifecycle_gate.sql`
24. `07_governance_gates/26_g19_data_product_certification_lifecycle.sql`
25. `07_governance_gates/27_g19_g18_cde_ontology_mapping.sql`
26. `07_governance_gates/28_g19_semantic_promotion_gate.sql`

## Why this structure

- Folder names mirror the notebook that consumes each script, so "what SQL does notebook N need" is answerable by directory name alone.
- File numbers are preserved so every existing cross-reference — inside these scripts' own `PRINT`/comment text, in `tools/*.py` `Path()` dependencies, and in notebook comments — still identifies the same artifact; only the path prefix changed, and every prefix was updated in the same pass as this reorganization.
- `07_governance_gates/` is intentionally the largest folder: most individual gate/decision scripts are demo-state setup for `07_apply_approved_changes.Notebook` to apply, or evidence consumed by `08_validate_governance_evidence.Notebook` / `09_reconcile_semantic_model.Notebook`. The SQL Prep catalog carries the finer per-script narrative breakdown that a folder-only view can't.
- This repo no longer has stale `nb_XX` (pre-consolidation) notebook names anywhere in `sql/` — every cross-reference points at the current `NN_description.Notebook` naming.
