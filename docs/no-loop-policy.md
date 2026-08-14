# No-Loop Policy for Fabric Sync Canonicalization

## Purpose

Prevent repeated git churn where Fabric Source Control rewrites selected metadata fields (for example `workspaceId` and Data Agent semantic datasource bindings) after local repairs.

This policy defines canonical states that the repo should keep, introduces a guard normalizer for pre-commit use, and adds a Gate D check to block drift from entering `main`.

## Canonical States by File

### 1) Data Agent semantic datasource files

Files:

- `ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/draft/semantic-model-BrookfieldEnercare/datasource.json`
- `ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/published/semantic-model-BrookfieldEnercare/datasource.json`

Required canonical values:

- `workspaceId = 00000000-0000-0000-0000-000000000000`
- `artifactId  = d19d7f14-ae22-9fde-462b-dafb983dfb0a` (semantic model logicalId)

Policy note: do not keep objectId/live workspace overrides in git for these files, because Fabric sync may rewrite them back and create loops.

### 2) Notebook environment metadata headers

Files:

- `nb_04_sempy_writeback.Notebook/notebook-content.py`
- `nb_05_push_qa_verified_answers.Notebook/notebook-content.py`

Required canonical value inside header metadata when present:

- `"workspaceId": "00000000-0000-0000-0000-000000000000"`

Policy note: runtime workspace binding should be resolved in notebook logic and config, not from exported notebook environment header IDs.

### 3) Semantic model definition artifacts

Scope:

- `BrookfieldEnercare.SemanticModel/definition/**`

Required policy:

- Keep business logic, DAX, annotations, and TMDL artifacts as source of truth.
- Do not introduce a `0000` policy for model logic files unless Fabric export explicitly requires it for a specific metadata field.

## Guard Script

Use:

- `./tools/normalize_fabric_canonical_state.ps1` (dry-run)
- `./tools/normalize_fabric_canonical_state.ps1 -Apply` (write canonical values)

Recommended pre-commit sequence:

1. `./tools/normalize_fabric_canonical_state.ps1 -Apply`
2. `git status -sb`
3. `./tools/validate_build_workflow.ps1 -Strict`
4. Commit only after Gate D passes

## Gate D (No-Loop Canonical Gate)

Gate D blocks commit/push readiness when either of these conditions is true:

1. Required Data Agent datasource files are not in canonical logicalId/`0000` state.
2. Guard-managed notebook metadata headers are not in canonical `workspaceId = 0000` state.

Gate D must be treated as blocking in strict validation mode.

## Operational Rule

If Fabric sync rewrites these fields after local edits, prefer canonical repo state and avoid repeated manual repairs unless doing a one-off production troubleshooting activity outside normal sync workflow.
