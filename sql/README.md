# SQL seed taxonomy for the Enercare governance demo

This folder is the SQL execution surface for the repo, but it has drifted over time into a historical sequence rather than a demo-aligned taxonomy. The scripts are still valid and referenced by notebook code, so this document acts as the canonical index and staging map while preserving backward compatibility.

## Canonical demo taxonomy

### 1. Source foundation
These build the authoritative transaction model in sub2.

- `02_sub2_sql_source_schema.sql` — core seven-table source schema
- `04_purview_demo_extensions.sql` — extended PII and governance tables
- `05_seed_purview_demo_data.sql` — synthetic operational data and scenario seed rows

### 2. Metadata and stewardship baseline
These define the governance catalog and SQL-first metadata plane.

- `06_purview_metadata_schema.sql` — governance domains, data products, glossary terms, CDEs, role assignments, labels
- `07_seed_purview_metadata.sql` — domain / product / glossary / CDE / access / label baseline data
- `08_workspace_identity_login.sql` — identity and SQL-login alignment for Fabric / workspace contexts

### 3. Governance request and approval gates
These implement the gated-change lifecycle and the approval ledger.

- `09_gated_governance_requests_schema.sql` — generic request/approval schema
- `10_seed_gated_governance_scenarios.sql` — PendingApproval scenario seed rows
- `13_closed_loop_governance_ledger.sql` — unified ledger and event model
- `14_migrate_legacy_governance_to_unified_ledger.sql` — backfill from legacy approval records
- `15_reconcile_gt_sla_duplicate_governance.sql` — de-dupe / supersede legacy records
- `16_add_ai_instruction_gate.sql` — AI instruction approval gate
- `17_backfill_role_assignment_ledger.sql` — P3/P4 role-assignment evidence
- `18_add_okr_approval_gate.sql` — OKR approval gate
- `21_g18a_demo_decisions.sql` — final Approved/Rejected decisions for the demo objects
- `22_victoria_data_product_owners_followup.sql` — follow-up governance actions and receipts
- `23_g20_synthetic_governance_attestation.sql` — attested governance state for stale or synthetic objects
- `24_g19_ontology_governance_completeness.sql` — ontology completeness / evidence lifecycle
- `25_g19_ai_instruction_lifecycle_gate.sql` — AI guidance lifecycle gate
- `26_g19_data_product_certification_lifecycle.sql` — data-product certification lifecycle
- `27_g19_g18_cde_ontology_mapping.sql` — CDE / glossary / ontology mapping gate
- `28_g19_semantic_promotion_gate.sql` — semantic promotion gate

### 4. SQL-native @tag and discovery
These represent the metadata intake layer that is source-of-truth for governance discovery.

- `19_tag_annotation_extraction.sql` — native extraction of SQL `@tag:` comment markers into governance_requests / governance_events
- `20_g18a_demo_views.sql` — approved and rejected demo views used to exercise the tag lifecycle

### 5. Ontology and business objective layer
These support the business, semantic, and data-product objective layer.

- `11_ontology_okr_schema.sql` — governance_okrs / governance_okr_key_results / governance_okr_data_products
- `12_seed_ontology_okrs.sql` — seed OKR and key-result records

### 6. Purview publication and downstream governance state
These view the SQL metadata as a downstream governance source, not the authoring layer.

- `06_purview_metadata_schema.sql` and `07_seed_purview_metadata.sql` are the SQL-source metadata objects consumed by Purview and Fabric
- `19_tag_annotation_extraction.sql` and `21_g18a_demo_decisions.sql` drive the policy/approval path into downstream validation

## Recommended execution order by notebook lifecycle

This is the canonical sequence for demo execution and matches the notebook flow more closely than the historical numbering:

1. `02_sub2_sql_source_schema.sql`
2. `04_purview_demo_extensions.sql`
3. `05_seed_purview_demo_data.sql`
4. `06_purview_metadata_schema.sql`
5. `07_seed_purview_metadata.sql`
6. `09_gated_governance_requests_schema.sql`
7. `10_seed_gated_governance_scenarios.sql`
8. `11_ontology_okr_schema.sql`
9. `12_seed_ontology_okrs.sql`
10. `13_closed_loop_governance_ledger.sql`
11. `19_tag_annotation_extraction.sql`
12. `20_g18a_demo_views.sql`
13. `21_g18a_demo_decisions.sql`
14. follow-on governance, licensing, and attestation scripts as required by the active demo stage

## Why this structure

- It groups SQL work by real demo contract, not by file-creation chronology.
- It keeps the governance ask clearly separate from source-data schema and SQL-native tag extraction.
- It matches the metadata lifecycle used by the notebooks: foundation -> governance baseline -> approval -> ontology -> tag-driven discovery -> downstream publication.
- It preserves existing filename stability so notebook and automation code do not break while the repo is being standardized.

## Recommended next-step modernization

The next cleanup step, once the active notebook paths are fully stabilized, is to physically move these files into a phase-based directory layout such as:

- `sql/01-foundation/`
- `sql/02-governance-baseline/`
- `sql/03-governance-gates/`
- `sql/04-tag-and-discovery/`
- `sql/05-ontology-and-closure/`

This would mirror the notebook numbering and make the file system itself match the taxonomy above. For now, this README is the canonical source of truth and the backward-compatible index.
