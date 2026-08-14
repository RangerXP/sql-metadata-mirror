# Brookfield Enercare SQL Metadata Mirror

This repository is the maintained source-control surface for the current Enercare build.

- sub1: Fabric workspace, semantic model, report, and notebooks
- sub2: Azure SQL authoritative source and mirroring input
- sub3: Purview governance and catalog plane

## Central Tenant: Governance-First Metadata Management

This repo treats metadata management as a governed lifecycle, not as a notebook side effect.
The standard pattern is:

- SQL objects author metadata via structured @tag headers
- SQL-native extraction detects and classifies those tags
- the governance ledger records source discovery and approval state
- stewardship reviews and approves or rejects the proposed metadata
- only approved metadata is applied to the lakehouse / semantic model / Purview surfaces
- lineage and evidence are preserved as a first-class requirement

The canonical design documents are `docs/sql-metadata-governance-standard.md` and `docs/ten-notebook-governance-reorg-plan.md`.

## Live Architecture

```text
nb_01_environment_and_source_baseline
    -> lh_enercare_demo baseline tables in Fabric
    -> nb_02_sql_source_publish_and_mirror
    -> Azure SQL sqldemo in sub2
    -> Fabric mirrored database sqldemo in sub1
    -> nb_03_star_schema_and_source_model rebuilds lh_enercare_demo star schema
    -> SQL-native metadata discovery records @tag requests in the governance ledger
    -> nb_04_metadata_discovery_and_stewardship and nb_05_metadata_staging_and_schema curate approved metadata in lh_metadata
    -> nb_06_semantic_apply_and_certification and nb_07_ai_grounding_and_verified_answers apply semantic metadata with SemPy and SemPy Labs
    -> nb_08_purview_publication_stage and nb_09_lineage_and_labels_stage publish governed metadata lineage and catalog state
    -> nb_10_governance_validation_and_healthcheck confirms the evidence-backed lifecycle is healthy
```

## Semantic Write-Back Standard

SemPy and SemPy Labs are the primary write-back model for semantic metadata.

- SemPy reads semantic model objects and metadata state.
- SemPy Labs writes table, column, measure descriptions and AI annotations.
- TMDL files in BrookfieldEnercare.SemanticModel remain source-controlled artifacts,
  but direct REST mutation of TMDL is no longer the primary notebook method.

## Maintained Repo Surface

- .github
- context
- docs
- fabric
- sql
- sql-private-dns-vnet-link.bicep
- sql-private-dns-vnet-link.json

## Recommended Run Order

1. nb_01_environment_and_source_baseline
2. nb_02_sql_source_publish_and_mirror
3. Fabric mirror sync from sqldemo
4. nb_03_star_schema_and_source_model
5. nb_04_metadata_discovery_and_stewardship
6. nb_05_metadata_staging_and_schema
7. nb_06_semantic_apply_and_certification (SemPy and SemPy Labs metadata write-back)
8. nb_07_ai_grounding_and_verified_answers (SemPy Labs AI annotation write-back)
9. nb_08_purview_publication_stage
10. nb_09_lineage_and_labels_stage
11. nb_10_governance_validation_and_healthcheck

## Key Documents

- docs/Enercare-Demo-SemPy-Design-Guide.md
- docs/demo-explanation-guide.md
- docs/design-gap-analysis.md
- docs/sub2-sql-source-mapping.md

## Maintenance Rules

- Keep only current deployment assets in git.
- Treat fabric as the Fabric source-of-truth surface.
- Do not add duplicate notebook mirrors outside fabric.
- Do not commit secrets.
