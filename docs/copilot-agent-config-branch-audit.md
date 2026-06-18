# Copilot Agent Config Branch Audit

Date: 2026-06-17

## Scope

This audit compares local branches for the primary standalone Copilot/Data Agent configuration surfaces:

- `fabric/Enercare Data Agent.DataAgent/.platform`
- `fabric/Enercare Data Agent.DataAgent/Files/Config/publish_info.json`
- `fabric/Enercare Data Agent.DataAgent/Files/Config/draft/semantic-model-BrookfieldEnercare/datasource.json`
- `fabric/Enercare Data Agent.DataAgent/Files/Config/published/semantic-model-BrookfieldEnercare/datasource.json`

## Local Branch Matrix

| Branch | Display Name | Logical ID | publish_info description populated | Draft artifactId | Draft workspaceId | Published artifactId | Published workspaceId |
|---|---|---|---|---|---|---|---|
| `backup/pre-align-20260605-163022` | Enercare Data Agent | 055d08c7-95bb-aeb1-46dc-324ad9deeab0 | No | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 |
| `enercare` | Enercare Data Agent | 055d08c7-95bb-aeb1-46dc-324ad9deeab0 | No | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 |
| `main` | Enercare Data Agent West3 | 6cf71cf5-b97c-844e-4b6c-b653e32abc4b | Yes | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 |
| `main-sync-runbook` | Enercare Data Agent | 055d08c7-95bb-aeb1-46dc-324ad9deeab0 | No | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 | d19d7f14-ae22-9fde-462b-dafb983dfb0a | 00000000-0000-0000-0000-000000000000 |

## Findings

1. `main` is the only local branch with modern standalone-routing metadata:
- Unique display name (`Enercare Data Agent West3`)
- New logical ID (`6cf71cf5-b97c-844e-4b6c-b653e32abc4b`)
- Populated publish metadata for standalone routing behavior

2. All local branches currently carry the same datasource placeholder IDs:
- `artifactId = d19d7f14-ae22-9fde-462b-dafb983dfb0a`
- `workspaceId = 00000000-0000-0000-0000-000000000000`

3. Because placeholder IDs are present in both draft and published datasource files, branch consistency exists, but durable workspace binding is not represented in git.

## Recommendation

- Keep branch metadata changes from `main` (display name/logical ID/publish description), and enforce a guardrail that blocks builds when datasource IDs are placeholders.
