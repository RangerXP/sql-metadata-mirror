param(
    [string]$WorkspaceId = "b976cac2-7754-4061-88c2-61c0ac016a99",
    [string]$SemanticModelName = "BrookfieldEnercare",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$draftPath = Join-Path $repoRoot "fabric/ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/draft/semantic-model-BrookfieldEnercare/datasource.json"
$publishedPath = Join-Path $repoRoot "fabric/ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/published/semantic-model-BrookfieldEnercare/datasource.json"

if (-not (Test-Path $draftPath) -or -not (Test-Path $publishedPath)) {
    throw "Data Agent datasource files were not found under fabric/.../DataAgent/Files/Config."
}

$items = az rest --method get --url "https://api.fabric.microsoft.com/v1/workspaces/$WorkspaceId/items" --resource "https://api.fabric.microsoft.com" --output json | ConvertFrom-Json
$semantic = $items.value | Where-Object { $_.type -eq "SemanticModel" -and $_.displayName -eq $SemanticModelName } | Select-Object -First 1

if (-not $semantic) {
    throw "SemanticModel '$SemanticModelName' was not found in workspace '$WorkspaceId'."
}

$targetArtifactId = $semantic.id
$targetWorkspaceId = $WorkspaceId

Write-Host "Target semantic model ID: $targetArtifactId"
Write-Host "Target workspace ID:     $targetWorkspaceId"

function Update-DataSourceFile {
    param([string]$Path)

    $json = Get-Content $Path -Raw | ConvertFrom-Json
    $changed = $false

    if ($json.artifactId -ne $targetArtifactId) {
        Write-Host "[$Path] artifactId: $($json.artifactId) -> $targetArtifactId"
        $json.artifactId = $targetArtifactId
        $changed = $true
    }

    if ($json.workspaceId -ne $targetWorkspaceId) {
        Write-Host "[$Path] workspaceId: $($json.workspaceId) -> $targetWorkspaceId"
        $json.workspaceId = $targetWorkspaceId
        $changed = $true
    }

    if ($json.elements) {
        $measures = $json.elements | Where-Object { $_.display_name -eq "_Measures" } | Select-Object -First 1
        if ($measures -and -not $measures.is_selected) {
            Write-Host "[$Path] _Measures table selected: false -> true"
            $measures.is_selected = $true
            $changed = $true
        }
    }

    if ($Apply -and $changed) {
        $json | ConvertTo-Json -Depth 100 | Set-Content $Path -NoNewline
    }

    return $changed
}

$draftChanged = Update-DataSourceFile -Path $draftPath
$publishedChanged = Update-DataSourceFile -Path $publishedPath

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry run complete. Use -Apply to write changes."
    exit 0
}

if ($draftChanged -or $publishedChanged) {
    Write-Host ""
    Write-Host "Datasource files updated. Next steps:"
    Write-Host "1) git status -sb"
    Write-Host "2) git add <both datasource.json files>"
    Write-Host "3) git commit -m 'Repair Data Agent semantic link after Fabric sync'"
    Write-Host "4) git push"
} else {
    Write-Host ""
    Write-Host "No changes needed. Datasource files are already aligned."
}
