# Ten-Notebook Governance Reorganization Plan

## Objective

Reorganize the repo around a single governance-first lifecycle while standardizing the SQL @tag workflow as the metadata intake mechanism.

The design is intentionally simple:

- SQL is the customer-authored metadata source
- @tag metadata defines the managed object contract
- SQL-native extraction creates the governed request
- stewardship decides approval
- only approved metadata reaches the lakehouse and semantic model
- Fabric and Purview read the approved state downstream

This replaces notebook sprawl with a lifecycle architecture that is understandable and auditable.

---

## Principles

1. One lifecycle, not many tools
   - The repo should describe one metadata lifecycle from definition to approval to consumption.
   - Individual notebooks are execution stages, not separate governance systems.

2. SQL as the metadata source-of-truth
   - Managed metadata is authored in SQL object definitions.
   - The DDL comments and the SQL governance ledger are the canonical intake path.

3. @tag as the standard metadata contract
   - The @tag fields define the managed metadata contract.
   - Every supported managed object uses the same contract.
   - Unmanaged objects stay out of the workflow.

4. Stewardship is required
   - Metadata is never auto-applied just because it exists in SQL.
   - Steward approval is the enforcement gate.

5. Semantic model and Purview are downstream consumers
   - Both read approved metadata.
   - Neither should be treated as an independent metadata authoring layer.

---

## Canonical metadata contract

The managed-object contract should be standardized to the same base schema across all object types.

Required fields:

- domain
- owner
- sensitivity
- semantic_role
- business_use

Optional fields:

- steward
- data_product
- cde
- source_system
- quality_rule
- retention_policy
- effective_date
- approved_by

Implementation rule:

- The SQL DDL trigger extracts the @tag payload from the object definition.
- The SQL proc creates a SourceTagAnnotationDetected request in the governance ledger.
- The notebook layer surfaces the request for steward review.
- Approved payloads are transformed into lakehouse metadata rows and semantic-model annotations.

---

## Target 10-notebook flow

### 1. Environment and source baseline
Purpose:
- create the synthetic operational data
- provision the source tables and baseline workspace
- establish the environment for the governance lifecycle

Current repo inputs:
- [nb_01_environment_and_source_baseline.Notebook](../nb_01_environment_and_source_baseline.Notebook)
- [nb_02_sql_source_publish_and_mirror.Notebook](../nb_02_sql_source_publish_and_mirror.Notebook)

Outcome:
- source data exists in SQL and is mirrored into Fabric

---

### 2. Source inventory and SQL metadata discovery
Purpose:
- discover source objects and their schema
- detect changed or newly managed SQL objects
- route any @tag metadata to the governance ledger

Current repo inputs:
- [nb_04_metadata_discovery_and_stewardship.Notebook](../nb_04_metadata_discovery_and_stewardship.Notebook)
- [sql/19_tag_annotation_extraction.sql](../sql/19_tag_annotation_extraction.sql)
- [sql/20_g18a_demo_views.sql](../sql/20_g18a_demo_views.sql)

Outcome:
- pending governance requests appear for review
- no metadata is applied without review

---

### 3. Governance backlog and stewardship intake
Purpose:
- expose the currently pending @tag requests
- allow stewardship to triage, approve, reject, or defer
- record the decision in the governance ledger

Current repo inputs:
- [nb_04_metadata_discovery_and_stewardship.Notebook](../nb_04_metadata_discovery_and_stewardship.Notebook)
- [nb_10_governance_validation_and_healthcheck.Notebook](../nb_10_governance_validation_and_healthcheck.Notebook)

Outcome:
- one steward-facing queue of pending metadata requests
- approved and rejected decisions are traceable

---

### 4. Curated metadata staging in lh_metadata
Purpose:
- stage approved metadata into the working metadata store
- merge managed metadata with customer-supplied governance records
- create the canonical metadata working tables

Current repo inputs:
- [nb_05_metadata_staging_and_schema.Notebook](../nb_05_metadata_staging_and_schema.Notebook)
- [nb_07a_ingest_customer_files.Notebook](../nb_07a_ingest_customer_files.Notebook)
- [nb_07b_merge_customer_metadata.Notebook](../nb_07b_merge_customer_metadata.Notebook)

Outcome:
- approved metadata exists in the lakehouse working layer
- metadata is ready for semantic-model application

---

### 5. Semantic model metadata apply
Purpose:
- apply approved descriptions, certifications, and annotations to the semantic model
- keep model writeback constrained to approved metadata only

Current repo inputs:
- [nb_06_semantic_apply_and_certification.Notebook](../nb_06_semantic_apply_and_certification.Notebook)
- [nb_07_ai_grounding_and_verified_answers.Notebook](../nb_07_ai_grounding_and_verified_answers.Notebook)

Outcome:
- the semantic model reflects only approved metadata
- AI grounding uses authorized metadata and not raw notebook guesswork

---

### 6. AI and business metadata grounding
Purpose:
- ensure the AI instructions and verified answers are certified and governed
- separate draft content from approved content
- maintain a clear evidence trail for business answers

Current repo inputs:
- [nb_07_ai_grounding_and_verified_answers.Notebook](../nb_07_ai_grounding_and_verified_answers.Notebook)
- [nb_11_gated_governance_sync.Notebook](../nb_11_gated_governance_sync.Notebook)

Outcome:
- AI grounding is tied to approved governance decisions
- an uncertified instruction never becomes the active runtime answer

---

### 7. Domain, product, and glossary publication
Purpose:
- publish governed catalog objects to Purview
- keep catalog publication aligned to approved business metadata

Current repo inputs:
- [nb_08_purview_publication_stage.Notebook](../nb_08_purview_publication_stage.Notebook)
- [nb_08_purview_glossary_cde.Notebook](../nb_08_purview_glossary_cde.Notebook)

Outcome:
- domains, products, terms, and CDEs are published from approved metadata state

---

### 8. Lineage and labels
Purpose:
- publish lineage and sensitivity labels
- connect SQL → mirror → lakehouse → semantic model evidence into a single lineage story

Current repo inputs:
- [nb_09_lineage_and_labels_stage.Notebook](../nb_09_lineage_and_labels_stage.Notebook)

Outcome:
- lineage is explicit and traceable across the stack

---

### 9. Governance validation and health checks
Purpose:
- validate that all required stewardship and governance checks pass
- confirm no action required before the demo is considered live

Current repo inputs:
- [nb_10_governance_validation_and_healthcheck.Notebook](../nb_10_governance_validation_and_healthcheck.Notebook)

Outcome:
- health check confirms the system is ready and evidence-backed

---

### 10. Audit, closeout, and proof narrative
Purpose:
- demonstrate the full chain from SQL metadata definition to approval to semantic-model usage and governance evidence
- provide the final demo proof for Maria / Victoria / Ci Zhu

Current repo inputs:
- [docs/maria-northstar-validation-plan.md](../docs/maria-northstar-validation-plan.md)
- [docs/closed-loop-governance-reference-model.md](../docs/closed-loop-governance-reference-model.md)
- [docs/purview-maria-north-star-scenario.md](../docs/purview-maria-north-star-scenario.md)

Outcome:
- a single authoritative proof narrative for the customer

---

## Current notebook-to-target mapping

| Current notebook | Target lifecycle stage |
|---|---|
| [nb_01_environment_and_source_baseline.Notebook](../nb_01_environment_and_source_baseline.Notebook) | 1 |
| [nb_02_sql_source_publish_and_mirror.Notebook](../nb_02_sql_source_publish_and_mirror.Notebook) | 1 |
| [nb_03_star_schema_and_source_model.Notebook](../nb_03_star_schema_and_source_model.Notebook) | 1 / 2 |
| [nb_04_metadata_discovery_and_stewardship.Notebook](../nb_04_metadata_discovery_and_stewardship.Notebook) | 2 / 3 |
| [nb_05_metadata_staging_and_schema.Notebook](../nb_05_metadata_staging_and_schema.Notebook) | 4 |
| [nb_07a_ingest_customer_files.Notebook](../nb_07a_ingest_customer_files.Notebook) | 4 |
| [nb_07b_merge_customer_metadata.Notebook](../nb_07b_merge_customer_metadata.Notebook) | 4 |
| [nb_06_semantic_apply_and_certification.Notebook](../nb_06_semantic_apply_and_certification.Notebook) | 5 |
| [nb_07_ai_grounding_and_verified_answers.Notebook](../nb_07_ai_grounding_and_verified_answers.Notebook) | 5 / 6 |
| [nb_08_purview_publication_stage.Notebook](../nb_08_purview_publication_stage.Notebook) | 7 |
| [nb_08_purview_glossary_cde.Notebook](../nb_08_purview_glossary_cde.Notebook) | 7 |
| [nb_09_lineage_and_labels_stage.Notebook](../nb_09_lineage_and_labels_stage.Notebook) | 8 |
| [nb_10_governance_validation_and_healthcheck.Notebook](../nb_10_governance_validation_and_healthcheck.Notebook) | 9 |
| [nb_11_gated_governance_sync.Notebook](../nb_11_gated_governance_sync.Notebook) | 3 / 6 |
| [nb_12_purview_workflow_sync.Notebook](../nb_12_purview_workflow_sync.Notebook) | 10 |
| [nb_13_semantic_reconcile.Notebook](../nb_13_semantic_reconcile.Notebook) | 10 |
| [nb_14_purview_access_sync.Notebook](../nb_14_purview_access_sync.Notebook) | 10 |
| [nb_15_purview_dataproduct_sync.Notebook](../nb_15_purview_dataproduct_sync.Notebook) | 10 |
| [nb_16_dataproduct_semantic_reconcile.Notebook](../nb_16_dataproduct_semantic_reconcile.Notebook) | 10 |
| [nb_17_g18_semantic_promotion.Notebook](../nb_17_g18_semantic_promotion.Notebook) | 10 |

---

## Recommended migration sequence

### Phase 1: standardize the contract
- move all managed metadata definitions to the @tag standardized contract
- ensure SQL DDL extraction is the only detection path
- keep notebooks as read/approval/apply orchestration only

### Phase 2: consolidate notebook ownership
- collapse implementation-over-detail notebooks into the 10 lifecycle stages above
- keep the notebook names short and lifecycle-oriented
- remove duplicate or overlapping logic

### Phase 3: reduce the working surface
- merge overlapping Purview publication flows into one stage
- keep workflow-proof notebooks only where they illustrate evidence or approval readback
- remove one-off scratch and temporary notebooks from the committed path

### Phase 4: formalize the demo proof narrative
- align the runbook and docs to the 10-stage lifecycle
- make the Maria/Victoria/Ci Zhu scenario a direct translation of the governance stages above

---

## Acceptance criteria

The reorganization is successful when:

- a SQL object definition is the starting point for metadata management
- the @tag workflow is the standard metadata intake mechanism
- stewardship review is required before runtime metadata adoption
- lineage from SQL to semantic model to Purview is explicit and traceable
- the demo can be explained as a single governing lifecycle instead of a set of disconnected notebooks

---

## Final decision

The repo should be reorganized around this principle:

> metadata is governed by SQL, approved by stewardship, applied through the semantic model, and consumed by Purview and Copilot as the downstream proof of the approved state.

This is the structure that makes the architecture coherent and keeps the demo centered on governance, stewardship, and lineage rather than notebook mechanics.
