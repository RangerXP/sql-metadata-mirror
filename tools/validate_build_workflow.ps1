param(
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$issues = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Issue {
    param([string]$Message)
    $issues.Add($Message)
}

function Add-Warning {
    param([string]$Message)
    $warnings.Add($Message)
}

Write-Host "Validating build workflow guardrails..." -ForegroundColor Cyan

# Git baseline checks
$gitStatus = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Add-Issue "Unable to run git status in repository root."
} elseif ($gitStatus) {
    Add-Warning "Working tree is not clean. Commit/stash/discard local changes before sync-sensitive operations."
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    Add-Issue "Unable to determine current git branch."
} elseif ($branch -ne "main") {
    Add-Warning "Current branch is '$branch' (expected 'main' for this workflow)."
}

$null = git fetch origin --quiet
if ($LASTEXITCODE -ne 0) {
    Add-Warning "Unable to fetch origin for ahead/behind check."
} else {
    $counts = (git rev-list --left-right --count origin/main...HEAD).Trim()
    if ($counts -match "^(\d+)\s+(\d+)$") {
        $behind = [int]$Matches[1]
        $ahead = [int]$Matches[2]
        if ($behind -gt 0) {
            Add-Issue "Local branch is behind origin/main by $behind commit(s). Pull/rebase before proceeding."
        }
        if ($ahead -gt 0) {
            Add-Warning "Local branch is ahead of origin/main by $ahead commit(s). Push before Fabric Source Control update."
        }
    } else {
        Add-Warning "Could not parse ahead/behind status from git rev-list output."
    }
}

# Canonical Data Agent structure checks
$fabricRoot = Join-Path $repoRoot "fabric"
$canonicalAgentPath = Join-Path $fabricRoot "Enercare Data Agent.DataAgent"
if (-not (Test-Path $canonicalAgentPath)) {
    Add-Issue "Missing canonical Data Agent folder: fabric/Enercare Data Agent.DataAgent"
}

$dataAgentDirs = Get-ChildItem -Path $fabricRoot -Directory -Filter "*.DataAgent" -ErrorAction SilentlyContinue
$enercareAgentDirs = $dataAgentDirs | Where-Object { $_.Name -like "*Enercare Data Agent*" }
if (-not $enercareAgentDirs -or $enercareAgentDirs.Count -ne 1) {
    Add-Issue "Expected exactly 1 Enercare Data Agent directory, found $($enercareAgentDirs.Count)."
}

$requiredConfigFiles = @(
    "Files/Config/data_agent.json",
    "Files/Config/publish_info.json",
    "Files/Config/draft/stage_config.json",
    "Files/Config/published/stage_config.json"
)

foreach ($relativePath in $requiredConfigFiles) {
    $fullPath = Join-Path $canonicalAgentPath $relativePath
    if (-not (Test-Path $fullPath)) {
        Add-Issue "Missing required Data Agent file: fabric/Enercare Data Agent.DataAgent/$relativePath"
    }
}

# Trigger condition reminder: if latest commit touched Fabric items, sync must follow push.
$lastCommitFiles = git diff-tree --no-commit-id --name-only -r HEAD
if ($LASTEXITCODE -eq 0 -and $lastCommitFiles) {
    $touchedFabricItems = $lastCommitFiles | Where-Object {
        $_ -match "^fabric/.+\.DataAgent/" -or $_ -match "^fabric/.+\.Notebook/"
    }
    if ($touchedFabricItems) {
        Add-Warning "Latest commit touched Fabric item definitions. Confirm Fabric Source Control refresh/update is completed before more portal/API edits."
    }
}

Write-Host ""
if ($issues.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "PASS: Workflow guardrails validated." -ForegroundColor Green
    exit 0
}

if ($issues.Count -gt 0) {
    Write-Host "Blocking issues:" -ForegroundColor Red
    foreach ($issue in $issues) {
        Write-Host " - $issue"
    }
}

if ($warnings.Count -gt 0) {
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host " - $warning"
    }
}

Write-Host ""
Write-Host "Suggested next actions:" -ForegroundColor Cyan
Write-Host " 1. Resolve blocking issues first."
Write-Host " 2. If Fabric items changed, complete Fabric Source Control update to zero pending conflicts."
Write-Host " 3. Re-run: ./tools/validate_build_workflow.ps1"

if ($issues.Count -gt 0 -or ($Strict -and $warnings.Count -gt 0)) {
    exit 1
}

exit 0
