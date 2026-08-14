# Governance Lifecycle Restage Review

## Scope

This is the first pass of the repo restage toward the governance-first model described in the repo standard and reorg plan.

The goal is not a blind rename. The goal is to separate the repo into lifecycle stages, reduce overlap, and preserve the real approval and evidence chain.

---

## Review findings

### 1) The repo already has the correct core lifecycle

The strongest architectural pieces are already coherent:

- SQL metadata intake via @tag headers and native extraction in [sql/19_tag_annotation_extraction.sql](../sql/19_tag_annotation_extraction.sql)
- stewardship review surface in [nb_02_metadata_pipeline_demo.Notebook/notebook-content.py](../nb_02_metadata_pipeline_demo.Notebook/notebook-content.py)
- semantic model apply in [nb_04_sempy_writeback.Notebook/notebook-content.py](../nb_04_sempy_writeback.Notebook/notebook-content.py)
- publish/readback evidence in [nb_12_purview_workflow_sync.Notebook/notebook-content.py](../nb_12_purview_workflow_sync.Notebook/notebook-content.py)

This is the correct lifecycle skeleton: source SQL -> governance request -> stewardship -> approved metadata -> runtime model -> publication evidence.

### 2) The real duplication is not in the core lifecycle; it is in the outer proof and ingestion family

The notebooks with the heaviest overlap are:

- [nb_07a_ingest_customer_files.Notebook](../nb_07a_ingest_customer_files.Notebook)
- [nb_07b_merge_customer_metadata.Notebook](../nb_07b_merge_customer_metadata.Notebook)
- [nb_07_publish_to_purview.Notebook](../nb_07_publish_to_purview.Notebook)
- [nb_08_purview_glossary_cde.Notebook](../nb_08_purview_glossary_cde.Notebook)
- [nb_09_purview_labels_lineage.Notebook](../nb_09_purview_labels_lineage.Notebook)
- [nb_10_purview_stewardship_ai.Notebook](../nb_10_purview_stewardship_ai.Notebook)
- [nb_11_gated_governance_sync.Notebook](../nb_11_gated_governance_sync.Notebook)
- [nb_12_purview_workflow_sync.Notebook](../nb_12_purview_workflow_sync.Notebook)
- [nb_13_semantic_reconcile.Notebook](../nb_13_semantic_reconcile.Notebook)
- [nb_14_purview_access_sync.Notebook](../nb_14_purview_access_sync.Notebook)
- [nb_15_purview_dataproduct_sync.Notebook](../nb_15_purview_dataproduct_sync.Notebook)
- [nb_16_dataproduct_semantic_reconcile.Notebook](../nb_16_dataproduct_semantic_reconcile.Notebook)

These are not all distinct concerns; several are evidence-proof wrappers around the same lifecycle state.

### 3) The best refactor is stage-based, not function-based

The strongest simplification is to group by lifecycle stage and keep proof notebooks as the last stage, not as parallel execution tracks.

This is consistent with the repo’s governance model and easier for a customer to understand.

---

## Recommendation: keep, merge, and stage

### Keep as primary core lifecycle

These should remain canonical and represent the main operational path:

- [nb_01_setup_demo_environment.Notebook](../nb_01_setup_demo_environment.Notebook)
- [nb_05a_publish_synthetic_data_to_sql.Notebook](../nb_05a_publish_synthetic_data_to_sql.Notebook)
- [nb_03_pbi_star_schema.Notebook](../nb_03_pbi_star_schema.Notebook)
- [nb_02_metadata_pipeline_demo.Notebook](../nb_02_metadata_pipeline_demo.Notebook)
- [nb_04a_extend_metadata_schema.Notebook](../nb_04a_extend_metadata_schema.Notebook)
- [nb_04_sempy_writeback.Notebook](../nb_04_sempy_writeback.Notebook)
- [nb_05_push_qa_verified_answers.Notebook](../nb_05_push_qa_verified_answers.Notebook)

These map cleanly to source -> metadata -> model apply.

### Merge into a single governance ingestion/reconciliation stage

These should be merged into one stage: Data staging and reconciliation.

- [nb_07a_ingest_customer_files.Notebook](../nb_07a_ingest_customer_files.Notebook)
- [nb_07b_merge_customer_metadata.Notebook](../nb_07b_merge_customer_metadata.Notebook)

Reason:
- both are working-store preparation and reconciliation logic
- together they represent the approved metadata staging layer
- they do not need separate operational identities in the customer narrative

Suggested target name:
- `nb_04_metadata_staging_and_reconciliation` or similar

### Merge publication and policy logic into a single Purview publication stage

These should be combined under one publication stage.

- [nb_07_publish_to_purview.Notebook](../nb_07_publish_to_purview.Notebook)
- [nb_08_purview_glossary_cde.Notebook](../nb_08_purview_glossary_cde.Notebook)
- [nb_09_purview_labels_lineage.Notebook](../nb_09_purview_labels_lineage.Notebook)

Reason:
- they all publish approved metadata into the catalog or lineage plane
- they are not independent workflows from the customer’s perspective
- they should read from the same approved metadata output and act as one closeout stage

Suggested target name:
- `nb_07_purview_publication_stage`

### Keep the approval and audit proof notebooks separate but reduce their number

These are proof and validation notebooks, not primary lifecycle engines:

- [nb_10_purview_stewardship_ai.Notebook](../nb_10_purview_stewardship_ai.Notebook)
- [nb_11_gated_governance_sync.Notebook](../nb_11_gated_governance_sync.Notebook)
- [nb_12_purview_workflow_sync.Notebook](../nb_12_purview_workflow_sync.Notebook)
- [nb_13_semantic_reconcile.Notebook](../nb_13_semantic_reconcile.Notebook)
- [nb_14_purview_access_sync.Notebook](../nb_14_purview_access_sync.Notebook)
- [nb_15_purview_dataproduct_sync.Notebook](../nb_15_purview_dataproduct_sync.Notebook)
- [nb_16_dataproduct_semantic_reconcile.Notebook](../nb_16_dataproduct_semantic_reconcile.Notebook)
- [nb_17_g18_semantic_promotion.Notebook](../nb_17_g18_semantic_promotion.Notebook)
- [nb_18_demo_reset.Notebook](../nb_18_demo_reset.Notebook)

These belong in a final proof-and-replay stage.

Suggested stage name:
- `nb_09_governance_proof_and_reset`

That stage can host the validation/proof logic and reset logic without creating separate customer-facing branches.

---

## Proposed target 10-notebook structure

The repo should converge to this lifecycle order:

1. `nb_01_source_and_environment`
2. `nb_02_sql_publish_and_mirror_check`
3. `nb_03_source_inventory_and_tag_discovery`
4. `nb_04_governance_backlog_and_stewardship`
5. `nb_05_metadata_staging_and_reconciliation`
6. `nb_06_semantic_apply_and_grounding`
7. `nb_07_ai_grounding_and_verified_answers`
8. `nb_08_purview_publication_stage`
9. `nb_09_governance_validation_and_healthcheck`
10. `nb_10_proof_and_reset`

This is the most natural grouping for a customer demo and for the actual governance model.

---

## What to do next

This is the first actual restage pass. The next repo action should be:

1. preserve the current working notebooks as the source-of-truth baseline
2. create the target lifecycle groupings in docs and in a lightweight rename plan
3. only then apply file renames and small notebook content edits to match the new lifecycle names
4. keep the SQL @tag detection and approval path fixed while the notebook names and narrative are simplified

This staged approach prevents breaking the governance chain while reducing notebook surface area.

---

## Final assessment

The repo is already closer to the right lifecycle than it looks at first glance. The primary problem is organizational, not conceptual.

The central fix is to align the repo around these boundaries:

- source and inventory
- stewardship and approval
- metadata staging
- semantic apply
- Purview publication
- proof and reset

That is the correct restage target for the governance-first demo.
