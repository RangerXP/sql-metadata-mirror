param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$canonicalWorkspaceId = "00000000-0000-0000-0000-000000000000"
$canonicalArtifactId = "d19d7f14-ae22-9fde-462b-dafb983dfb0a"

$changes = New-Object System.Collections.Generic.List[string]
$issues = New-Object System.Collections.Generic.List[string]

function Add-Change {
    param([string]$Message)
    $changes.Add($Message)
}

function Add-Issue {
    param([string]$Message)
    $issues.Add($Message)
}

function Update-DataSourceFile {
    param(
        [string]$Path,
        [string]$DisplayPath
    )

    if (-not (Test-Path $Path)) {
        Add-Issue "Missing datasource file: $DisplayPath"
        return
    }

    try {
        $json = Get-Content -Raw $Path | ConvertFrom-Json
    } catch {
        Add-Issue "Invalid JSON: $DisplayPath"
        return
    }

    $changed = $false

    if ($json.workspaceId -ne $canonicalWorkspaceId) {
        Add-Change "$DisplayPath workspaceId: $($json.workspaceId) -> $canonicalWorkspaceId"
        $json.workspaceId = $canonicalWorkspaceId
        $changed = $true
    }

    if ($json.artifactId -ne $canonicalArtifactId) {
        Add-Change "$DisplayPath artifactId: $($json.artifactId) -> $canonicalArtifactId"
        $json.artifactId = $canonicalArtifactId
        $changed = $true
    }

    if ($Apply -and $changed) {
        $json | ConvertTo-Json -Depth 100 | Set-Content $Path -NoNewline
    }
}

function Update-NotebookHeaderWorkspaceId {
    param(
        [string]$Path,
        [string]$DisplayPath
    )

    if (-not (Test-Path $Path)) {
        Add-Issue "Missing notebook source file: $DisplayPath"
        return
    }

    $content = Get-Content -Raw $Path
    $pattern = '(?m)^# META\s+"workspaceId":\s+"[^"]+"'

    if (-not [regex]::IsMatch($content, $pattern)) {
        Add-Issue "No notebook metadata workspaceId header found: $DisplayPath"
        return
    }

    $replacement = '# META       "workspaceId": "' + $canonicalWorkspaceId + '"'
    $updated = [regex]::Replace($content, $pattern, $replacement)

    if ($updated -ne $content) {
        Add-Change "$DisplayPath notebook header workspaceId normalized to canonical 0000 value"
        if ($Apply) {
            Set-Content -Path $Path -Value $updated -NoNewline
        }
    }
}

Write-Host "Normalizing Fabric canonical state..." -ForegroundColor Cyan

$datasourceFiles = @(
    @{
        Path = "ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/draft/semantic-model-BrookfieldEnercare/datasource.json"
        Display = "ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/draft/semantic-model-BrookfieldEnercare/datasource.json"
    },
    @{
        Path = "ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/published/semantic-model-BrookfieldEnercare/datasource.json"
        Display = "ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/published/semantic-model-BrookfieldEnercare/datasource.json"
    }
)

foreach ($entry in $datasourceFiles) {
    $fullPath = Join-Path $repoRoot $entry.Path
    Update-DataSourceFile -Path $fullPath -DisplayPath $entry.Display
}

$notebookFiles = @(
    @{
        Path = "04_writeback_governed_metadata.Notebook/notebook-content.py"
        Display = "04_writeback_governed_metadata.Notebook/notebook-content.py"
    }
)

foreach ($entry in $notebookFiles) {
    $fullPath = Join-Path $repoRoot $entry.Path
    Update-NotebookHeaderWorkspaceId -Path $fullPath -DisplayPath $entry.Display
}

Write-Host ""
if ($issues.Count -gt 0) {
    Write-Host "Issues:" -ForegroundColor Red
    foreach ($issue in $issues) {
        Write-Host " - $issue"
    }
}

if ($changes.Count -eq 0) {
    Write-Host "No canonicalization changes required." -ForegroundColor Green
} else {
    if ($Apply) {
        Write-Host "Applied changes:" -ForegroundColor Green
    } else {
        Write-Host "Proposed changes (dry-run):" -ForegroundColor Yellow
    }

    foreach ($change in $changes) {
        Write-Host " - $change"
    }
}

Write-Host ""
if (-not $Apply) {
    Write-Host "Dry run complete. Re-run with -Apply to write canonical values."
}

if ($issues.Count -gt 0) {
    exit 1
}

exit 0
