# Brookfield Enercare SQL Metadata Mirror

This repository is the maintained source-control surface for the current Enercare build.

- sub1: Fabric workspace, semantic model, report, and notebooks
- sub2: Azure SQL authoritative source and mirroring input
- sub3: Purview governance and catalog plane

## Live Architecture

```text
nb_01_setup_demo_environment
    -> lh_enercare_demo baseline tables in Fabric
    -> nb_05a_publish_synthetic_data_to_sql
    -> Azure SQL sqldemo in sub2
    -> Fabric mirrored database sqldemo in sub1
    -> nb_03_pbi_star_schema rebuilds lh_enercare_demo star schema
    -> nb_02 and nb_04a curate metadata in lh_metadata
    -> nb_04 and nb_05 apply semantic metadata with SemPy and SemPy Labs
    -> Purview in sub3 scans Fabric semantic models and SQL assets
```

## Semantic Write-Back Standard

SemPy and SemPy Labs are the primary write-back model for semantic metadata.

- SemPy reads semantic model objects and metadata state.
- SemPy Labs writes table, column, measure descriptions and AI annotations.
- TMDL files in fabric/BrookfieldEnercare.SemanticModel remain source-controlled artifacts,
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

1. nb_01_setup_demo_environment
2. nb_05a_publish_synthetic_data_to_sql
3. Fabric mirror sync from sqldemo
4. nb_03_pbi_star_schema
5. nb_02_metadata_pipeline_demo
6. nb_04a_extend_metadata_schema
7. nb_04_sempy_writeback (SemPy and SemPy Labs metadata write-back)
8. nb_05_push_qa_verified_answers (SemPy Labs AI annotation write-back)
9. nb_05b_test_sql_connectivity

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
