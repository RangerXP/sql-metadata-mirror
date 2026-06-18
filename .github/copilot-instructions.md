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
|  |- ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/   (Enercare Data Agent — operational request/SLA lookup)
|  |- lh_enercare_demo.Lakehouse/
|  |- lh_metadata.Lakehouse/
|  |- nb_01_setup_demo_environment.Notebook/
|  |- nb_02_metadata_pipeline_demo.Notebook/
|  |- nb_03_pbi_star_schema.Notebook/
|  |- nb_04a_extend_metadata_schema.Notebook/
|  |- nb_04_sempy_writeback.Notebook/
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
3. Fabric mirroring ingests that source into `sqldemo`.
4. `nb_03_pbi_star_schema` rebuilds the DirectLake star schema from the mirrored source.
5. `nb_02_metadata_pipeline_demo`, `nb_04a_extend_metadata_schema`, `nb_04_sempy_writeback`, and `nb_05_push_qa_verified_answers` maintain metadata and Copilot grounding using SemPy and SemPy Labs.
6. `nb_05b_test_sql_connectivity` remains the smoke test for private SQL access.

## Notebook Conventions

- Fabric notebooks live only as `fabric/nb_0N_name.Notebook/` folders with `.platform` and `notebook-content.py`.
- Preserve existing Fabric metadata headers when editing notebook content.
- Use `DEMO_MODE = True` for dry-run support where the notebook already follows that pattern.
- Match existing column naming such as `IsDraft`, `IsCertified`, `DefinitionHash`, `AssetName`, and `ColumnName`.

## Semantic Model Rules

- Use SemPy (read) and SemPy Labs (write) as the baseline semantic write-back approach.
- Preserve git-backed TMDL artifacts in `fabric/BrookfieldEnercare.SemanticModel/definition/` as source-controlled deployment assets.
- Preserve `lineageTag`, `sourceLineageTag`, `annotation`, and `partition` blocks when updating TMDL artifacts.
- Only certified KPI content should propagate into semantic-model grounding surfaces.

## Context Files

- `context/kpi-definitions.json`
- `context/enercare-schemas.json`
- `context/data-gen-config.json`
- `context/purview-type-defs.json`
- `context/api-endpoints.json`

## MCP Custom Definition (Operator Mode)

Use this behavior when supporting this repo owner, who is not a software developer and needs explicit Git guidance during testing.

### Primary Intent

- Give concrete, command-by-command pull/push instructions.
- Prefer small safe steps over abstract Git explanations.
- Do not ask the user to decide low-level Git strategy unless there is a real conflict.

### Required Git Workflow for Testing

1. Start each testing cycle by checking repo state and syncing:
	 - `git status -sb`
	 - `git pull --rebase origin main`
2. Make one intent change at a time (single topic per commit).
3. Stage only explicit files that match that intent.
4. Run minimal validation relevant to the changed files.
5. Before push, run:
	 - `git status -sb`
	 - `git pull --rebase origin main`
6. Push immediately after validation and approval:
	 - `git push`

### Approval Gates (Simple)

- Gate A - File Gate:
	- Only expected files are changed.
- Gate B - Behavior Gate:
	- The test behavior requested by the user is confirmed.
- Gate C - Push Gate:
	- Branch is synced/rebased and ready for push.

The assistant should explicitly call out Gate A/B/C before pushing.

### Commit Scope Rules

- Do not batch unrelated changes in one commit.
- Prefer one commit per behavior change.
- If a change touches both draft and published Data Agent configs, keep them in the same commit.
- If a change touches Data Agent plus notebook guidance, split into two commits unless the user asks for a combined release commit.

### Conflict Handling Rules

- If push is rejected, run `git pull --rebase origin main` once and retry push.
- If rebase conflict occurs, stop and present a short, file-specific choice to the user with recommended option.
- Never use destructive recovery commands.
- If rebase metadata is stale, use non-interactive cleanup and continue with normal rebase flow.

### Fabric Sync Safety Rules

- Treat git as source of truth for item definitions.
- Do not alternate UI edits and local git edits in the same unresolved cycle.
- After push, instruct the user to run Fabric Source Control refresh/update before new UI edits.

### Response Style for This User

- Use short numbered steps.
- Include exact commands to run.
- State expected output in plain language.
- End each operational instruction with one clear next action.
