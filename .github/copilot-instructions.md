# GitHub Copilot Instructions — Brookfield Enercare SQL Metadata Mirror

## What This Repo Is

Maintained git source for the current Enercare deployment pattern:

- `sub1`: Microsoft Fabric workspace and semantic-model plane
- `sub2`: Azure SQL authoritative source and Fabric mirroring input
- `sub3`: Purview governance plane

Primary repo surface is `fabric/`. Do not recreate duplicate notebook mirrors elsewhere.

## Repo Structure

```text
/
|- .github/
|  \- copilot-instructions.md
|- context/
|- docs/
|  |- design-gap-analysis.md
|  \- sub2-sql-source-mapping.md
|- fabric/
|  |- BrookfieldEnercare.Report/
|  |- BrookfieldEnercare.SemanticModel/
|  |- Enercare Data Agent.DataAgent/
|  |- Enercare Governance Agent.DataAgent/
|  |- lh_enercare_demo.Lakehouse/
|  |- lh_metadata.Lakehouse/
|  |- nb_01_setup_demo_environment.Notebook/
|  |- nb_02_metadata_pipeline_demo.Notebook/
|  |- nb_03_pbi_star_schema.Notebook/
|  |- nb_04a_extend_metadata_schema.Notebook/
|  |- nb_04_generate_tmdl.Notebook/
|  |- nb_05a_publish_synthetic_data_to_sql.Notebook/
|  |- nb_05b_test_sql_connectivity.Notebook/
|  \- nb_05_push_qa_verified_answers.Notebook/
|- sql/
|  \- 02_sub2_sql_source_schema.sql
|- sql-private-dns-vnet-link.bicep
\- sql-private-dns-vnet-link.json
```

## Maintained Deployment Rules

1. Treat `fabric/` as the single git source-of-truth for Fabric items.
2. Keep only the current deployment assets in this repo.
3. Do not add duplicate notebook source mirrors outside `fabric/`.
4. Do not add presentation exports, zip exports, walkthrough notebooks, or legacy setup packages.
5. No secrets in repo. Load credentials from environment variables or Key Vault-backed runtime configuration.

## Current Execution Path

1. `nb_01_setup_demo_environment` seeds the Fabric baseline.
2. `nb_05a_publish_synthetic_data_to_sql` publishes the authoritative seven-table source into Azure SQL in `sub2`.
3. Fabric mirroring ingests that source into `sqldemo-mirror`.
4. `nb_03_pbi_star_schema` rebuilds the DirectLake star schema from the mirrored source.
5. `nb_02_metadata_pipeline_demo`, `nb_04a_extend_metadata_schema`, `nb_04_generate_tmdl`, and `nb_05_push_qa_verified_answers` maintain metadata and Copilot grounding.
6. `nb_05b_test_sql_connectivity` remains the smoke test for private SQL access.

## Notebook Conventions

- Fabric notebooks live only as `fabric/nb_0N_name.Notebook/` folders with `.platform` and `notebook-content.py`.
- Preserve existing Fabric metadata headers when editing notebook content.
- Use `DEMO_MODE = True` for dry-run support where the notebook already follows that pattern.
- Match existing column naming such as `IsDraft`, `IsCertified`, `DefinitionHash`, `AssetName`, and `ColumnName`.

## Semantic Model Rules

- Keep the git-backed TMDL + Fabric Items API path as the baseline write-back approach.
- Preserve `lineageTag`, `sourceLineageTag`, `annotation`, and `partition` blocks when updating TMDL.
- Only certified KPI content should propagate into semantic-model grounding surfaces.

## Context Files

- `context/kpi-definitions.json`
- `context/enercare-schemas.json`
- `context/data-gen-config.json`
- `context/purview-type-defs.json`
- `context/api-endpoints.json`
