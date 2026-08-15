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

Current repo input:
- [01_setup_source_data.Notebook](../01_setup_source_data.Notebook)

Outcome:
- source data exists in SQL and is mirrored into Fabric

---

### 2. Source inventory and SQL metadata discovery
Purpose:
- discover source objects and their schema
- detect changed or newly managed SQL objects
- route any @tag metadata to the governance ledger

Current repo input:
- [02_build_metadata_foundation.Notebook](../02_build_metadata_foundation.Notebook)
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

Current repo input:
- [03_build_semantic_model.Notebook](../03_build_semantic_model.Notebook)

Outcome:
- one steward-facing queue of pending metadata requests
- approved and rejected decisions are traceable

---

### 4. Curated metadata staging in lh_metadata
Purpose:
- stage approved metadata into the working metadata store
- merge managed metadata with customer-supplied governance records
- create the canonical metadata working tables

Current repo input:
- [04_writeback_governed_metadata.Notebook](../04_writeback_governed_metadata.Notebook)

Outcome:
- approved metadata exists in the lakehouse working layer
- metadata is ready for semantic-model application

---

### 5. Semantic model metadata apply
Purpose:
- apply approved descriptions, certifications, and annotations to the semantic model
- keep model writeback constrained to approved metadata only

Current repo input:
- [05_publish_governance_domains.Notebook](../05_publish_governance_domains.Notebook)

Outcome:
- the semantic model reflects only approved metadata
- AI grounding uses authorized metadata and not raw notebook guesswork

---

### 6. AI and business metadata grounding
Purpose:
- ensure the AI instructions and verified answers are certified and governed
- separate draft content from approved content
- maintain a clear evidence trail for business answers

Current repo input:
- [06_publish_glossary_and_lineage.Notebook](../06_publish_glossary_and_lineage.Notebook)

Outcome:
- AI grounding is tied to approved governance decisions
- an uncertified instruction never becomes the active runtime answer

---

### 7. Domain, product, and glossary publication
Purpose:
- publish governed catalog objects to Purview
- keep catalog publication aligned to approved business metadata

Current repo input:
- [07_apply_approved_changes.Notebook](../07_apply_approved_changes.Notebook)

Outcome:
- domains, products, terms, and CDEs are published from approved metadata state

---

### 8. Lineage and labels
Purpose:
- publish lineage and sensitivity labels
- connect SQL → mirror → lakehouse → semantic model evidence into a single lineage story

Current repo input:
- [08_validate_governance_evidence.Notebook](../08_validate_governance_evidence.Notebook)

Outcome:
- lineage is explicit and traceable across the stack

---

### 9. Governance validation and health checks
Purpose:
- validate that all required stewardship and governance checks pass
- confirm no action required before the demo is considered live

Current repo input:
- [09_reconcile_semantic_model.Notebook](../09_reconcile_semantic_model.Notebook)

Outcome:
- health check confirms the system is ready and evidence-backed

---

### 10. Audit, closeout, and proof narrative
Purpose:
- demonstrate the full chain from SQL metadata definition to approval to semantic-model usage and governance evidence
- provide the final demo proof for Maria / Victoria / Ci Zhu

Current repo input:
- [10_reset_demo.Notebook](../10_reset_demo.Notebook)

Outcome:
- a single authoritative proof narrative for the customer

---

## Current notebook-to-target mapping

| Current notebook | Target lifecycle stage |
|---|---|
| [01_setup_source_data.Notebook](../01_setup_source_data.Notebook) | 1 |
| [02_build_metadata_foundation.Notebook](../02_build_metadata_foundation.Notebook) | 2 |
| [03_build_semantic_model.Notebook](../03_build_semantic_model.Notebook) | 3 |
| [04_writeback_governed_metadata.Notebook](../04_writeback_governed_metadata.Notebook) | 4 |
| [05_publish_governance_domains.Notebook](../05_publish_governance_domains.Notebook) | 5 |
| [06_publish_glossary_and_lineage.Notebook](../06_publish_glossary_and_lineage.Notebook) | 6 |
| [07_apply_approved_changes.Notebook](../07_apply_approved_changes.Notebook) | 7 |
| [08_validate_governance_evidence.Notebook](../08_validate_governance_evidence.Notebook) | 8 |
| [09_reconcile_semantic_model.Notebook](../09_reconcile_semantic_model.Notebook) | 9 |
| [10_reset_demo.Notebook](../10_reset_demo.Notebook) | 10 |

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
