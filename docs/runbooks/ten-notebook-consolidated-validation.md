# Ten-Notebook Consolidated Validation Runbook

## Purpose

Validate the ten consolidated Fabric notebooks in lifecycle order. Each stage must be submitted through the Fabric REST API, monitored to a terminal state, and checked against its expected governance evidence before the next stage runs.

This runbook is the execution companion to:

- `docs/ten-notebook-governance-reorg-plan.md`
- `docs/sql-metadata-governance-standard.md`
- `docs/Enercare-Demo-SemPy-Design-Guide.md`
- `docs/design-gap-analysis.md`
- `docs/maria-northstar-validation-plan.md`

The sequence is fail-fast. A failed or ambiguous stage stops the sequence until its output and downstream state are understood.

## Preconditions

1. Fabric Source Control has refreshed `main` into workspace `Enercare-West3`.
2. The workspace contains exactly these ten notebook items:

   - `01_setup_source_data`
   - `02_build_metadata_foundation`
   - `03_build_semantic_model`
   - `04_writeback_governed_metadata`
   - `05_publish_governance_domains`
   - `06_publish_glossary_and_lineage`
   - `07_apply_approved_changes`
   - `08_validate_governance_evidence`
   - `09_reconcile_semantic_model`
   - `10_reset_demo`

3. The Fabric identity can read and run notebooks in workspace `b976cac2-7754-4061-88c2-61c0ac016a99`.
4. The SQL source, mirrored database, lakehouses, semantic model, Purview private endpoint, and required connections are available.
5. Capture the initial item inventory before execution:

```powershell
$workspace = "b976cac2-7754-4061-88c2-61c0ac016a99"
$items = az rest --method get `
  --url "https://api.fabric.microsoft.com/v1/workspaces/$workspace/items" `
  --resource "https://api.fabric.microsoft.com" | ConvertFrom-Json
$items.value | Sort-Object displayName | Select-Object id, displayName, type
```

Do not run this sequence against the old `nb_01` through `nb_18` workspace items. If the inventory still shows the old names, stop and refresh Fabric Source Control first.

## REST Execution Harness

The Fabric job pattern used by this runbook is:

```text
POST /v1/workspaces/{workspaceId}/items/{itemId}/jobs/instances?jobType=RunNotebook
GET  /v1/workspaces/{workspaceId}/jobs/instances/{jobInstanceId}
```

Use the live item ID returned by the workspace inventory. Do not use the `.platform` logical ID as the runtime job ID.

```powershell
$ErrorActionPreference = "Stop"
$workspace = "b976cac2-7754-4061-88c2-61c0ac016a99"
$resource = "https://api.fabric.microsoft.com"

function Get-FabricItems {
    (az rest --method get `
        --url "https://api.fabric.microsoft.com/v1/workspaces/$workspace/items" `
        --resource $resource | ConvertFrom-Json).value
}

function Invoke-FabricNotebook {
    param(
        [Parameter(Mandatory)] [string] $DisplayName,
        [int] $TimeoutMinutes = 45
    )

    $item = Get-FabricItems | Where-Object {
        $_.type -eq "Notebook" -and $_.displayName -eq $DisplayName
    }
    if (-not $item) { throw "Notebook is not published in Fabric: $DisplayName" }

    $run = az rest --method post `
        --url "https://api.fabric.microsoft.com/v1/workspaces/$workspace/items/$($item.id)/jobs/instances?jobType=RunNotebook" `
        --resource $resource | ConvertFrom-Json
    $jobId = if ($run.id) { $run.id } elseif ($run.jobInstanceId) { $run.jobInstanceId } else { throw "No job ID returned for $DisplayName" }

    $deadline = (Get-Date).ToUniversalTime().AddMinutes($TimeoutMinutes)
    do {
        Start-Sleep -Seconds 15
        $state = az rest --method get `
            --url "https://api.fabric.microsoft.com/v1/workspaces/$workspace/jobs/instances/$jobId" `
            --resource $resource | ConvertFrom-Json
        $status = [string]$state.status
        Write-Host "$DisplayName | job=$jobId | status=$status"
        if ((Get-Date).ToUniversalTime() -gt $deadline) { throw "Timed out: $DisplayName job $jobId" }
    } while ($status -notin @("Completed", "Failed", "Cancelled", "Deduped"))

    if ($status -ne "Completed") { throw "$DisplayName ended in $status; job=$jobId" }
    [pscustomobject]@{ Notebook = $DisplayName; ItemId = $item.id; JobId = $jobId; Status = $status }
}
```

Record the returned `Notebook`, `ItemId`, `JobId`, and `Status` for every stage. The job status is execution evidence; it is not by itself business validation.

## Ordered Validation Sequence

### 1. `01_setup_source_data`

**Purpose:** establish the environment and authoritative source data.

**Run:** `Invoke-FabricNotebook "01_setup_source_data"`

**Validate:**

- source tables exist in Azure SQL `sqldemo`
- the expected mirrored database and `lh_enercare_demo` objects are available
- the notebook completes without source-connection or lakehouse errors
- baseline row counts are recorded

**Evidence:** Fabric job readback, SQL source row-count query, mirror availability check.

### 2. `02_build_metadata_foundation`

**Purpose:** discover SQL metadata, stage customer metadata, and prepare the governed working layer.

**Run:** `Invoke-FabricNotebook "02_build_metadata_foundation"`

**Validate:**

- `@tag` detections appear in `lh_metadata`
- required fields are present: `domain`, `owner`, `sensitivity`, `semantic_role`, `business_use`
- pending governance requests are visible
- no raw tag is applied directly to the semantic model
- customer-file and SQL-mirror metadata are reconciled without silently dropping governed fields

**Evidence:** `source_tag_detections`, governance request counts, required-field validation output.

### 3. `03_build_semantic_model`

**Purpose:** build or refresh the DirectLake star schema from the mirrored source.

**Run:** `Invoke-FabricNotebook "03_build_semantic_model"`

**Validate:**

- expected fact and dimension tables are present
- source lineage identifiers remain stable
- the semantic model is readable after the build
- no governance approval is bypassed by the schema build

**Evidence:** table inventory, semantic model refresh/readback, source-to-model mapping.

### 4. `04_writeback_governed_metadata`

**Purpose:** apply approved descriptions, certifications, and AI grounding metadata through SemPy/SemPy Labs.

**Run:** `Invoke-FabricNotebook "04_writeback_governed_metadata"`

**Validate:**

- only approved and certified rows are written
- `IsDraft=0` and certification conditions are enforced
- semantic descriptions and annotations are readable after writeback
- verified answers remain distinct from general AI instructions

**Evidence:** before/after semantic metadata readback, certification counts, annotation payload hashes.

### 5. `05_publish_governance_domains`

**Purpose:** publish approved domains and data products to Purview.

**Run:** `Invoke-FabricNotebook "05_publish_governance_domains"`

**Validate:**

- domain and data-product payloads are generated from approved metadata
- owner and steward assignments are populated
- publication is idempotent
- Purview API readback finds the published entities

**Evidence:** job output, Atlas entity GUIDs, publication receipt, owner/steward validation.

### 6. `06_publish_glossary_and_lineage`

**Purpose:** publish glossary terms, CDEs, classifications, sensitivity labels, and the SQL-to-Fabric lineage manifest.

**Run:** `Invoke-FabricNotebook "06_publish_glossary_and_lineage"`

**Validate:**

- glossary and CDE objects are present or idempotently updated
- sensitivity labels normalize to `General`, `Internal`, `Confidential`, or `Highly Confidential`
- label publication is part of the approved governance payload
- SQL, mirror, lakehouse, and semantic-model qualified names resolve to live Purview entities
- lineage process entities are created for the expected edges

**Evidence:** Purview entity readback, classification readback, label assignment readback, lineage process GUIDs.

### 7. `07_apply_approved_changes`

**Purpose:** apply the SQL governance ledger rows that have reached `Approved`.

**Run:** `Invoke-FabricNotebook "07_apply_approved_changes"`

**Validate:**

- only `Approved` and unapplied requests are selected
- requests lacking required tag fields or a valid sensitivity label are rejected before apply
- applied rows receive `Applied` and `applied_at`
- semantic and Purview mutations correspond to the approved request payload

**Evidence:** request IDs before/after, approver identity, applied timestamps, mutation receipts.

### 8. `08_validate_governance_evidence`

**Purpose:** validate stewardship, approval, publication, sensitivity, and lineage evidence.

**Run:** `Invoke-FabricNotebook "08_validate_governance_evidence"`

**Validate:**

- no unexpected `ACTION_REQUIRED` results remain
- all required governance objects have owners, stewards, and sensitivity state
- approved requests have downstream evidence
- Purview entities and lineage edges resolve through the live Atlas API
- the Maria North Star chain is complete

**Evidence:** notebook scorecard, SQL governance ledger, Purview API report, lineage edge counts.

### 9. `09_reconcile_semantic_model`

**Purpose:** reconcile semantic-model governance state against approved catalog state.

**Run:** `Invoke-FabricNotebook "09_reconcile_semantic_model"`

**Validate:**

- semantic model annotations match approved metadata hashes
- drift is corrected without fabricating a new approval
- Purview and semantic-model identities remain mapped
- reconciliation is idempotent

**Evidence:** reconciliation rows, matching hashes, semantic readback, drift/restore result.

### 10. `10_reset_demo`

**Purpose:** restore the repeatable demo baseline after validation.

**Run:** `Invoke-FabricNotebook "10_reset_demo"`

**Validate:**

- demo reset is explicitly requested and completes successfully
- baseline rows and approved demo state are restored
- no unexpected production or tenant-wide objects are deleted
- the workspace is ready for a repeat run

**Evidence:** reset summary, baseline counts, post-reset governance status.

## Acceptance Gates

The run is accepted only when all of the following are true:

- all ten Fabric jobs finish `Completed`
- each job ID and output location is recorded
- SQL `@tag` values are visible in the metadata intake layer
- approval state is preserved in the governance ledger
- sensitivity label validation and publication pass
- Purview entity readback passes for the governed demo scope
- SQL → Fabric → Purview → semantic-model lineage is readable through Atlas
- semantic annotations match approved metadata
- the final scorecard has no unexplained `ACTION_REQUIRED` results
- reset returns the demo to a known repeatable baseline

## Archive Preservation Gate

The pre-consolidation sources are preserved on remote branch
`archive/pre-10-notebook-consolidation` at commit
`7a45cb7b0f0fcba618e0426938a1cdb2f344d759`.

Verified archive inventory:

- exactly 21 legacy `.Notebook` items
- 21 `notebook-content.py` files
- 21 `.platform` files
- zero incomplete notebook items
- both pre-consolidation commits `22f57b2` and `57229b0` are ancestors of the archive branch

The `main` branch intentionally contains zero tracked paths under `archive/` or
`fabric/`. Fabric workspace folders are independent workspace objects, not Git
archive definitions. Do not recreate an `archive` or `fabric` folder on `main`.

## Current Synchronization State

Fabric Git is connected to `RangerXP/sql-metadata-mirror`, branch `main`, at the
repository root. After the consolidated notebook format repairs, local `main` and
`origin/main` matched commit `7f14768ac19e6c0ea21dd185fd51eaeaef18cc40`.

Refresh Source Control and update from Git before submitting the first job. The
workspace inventory must show the ten consolidated notebooks and no legacy
notebooks or legacy workspace folders.
