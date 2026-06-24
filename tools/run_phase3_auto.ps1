param(
    [string]$Server = "sqlserver-sk2wus3.database.windows.net",
    [string]$Database = "sqldemo",
    [int]$MariaCustomerId = 18374622,
    [string]$MariaAccountNumber = "EC18374622",
    [switch]$RunSql
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$runbookDir = Join-Path $repoRoot "docs/runbooks"
$evidenceDir = Join-Path $runbookDir "phase3-step1-evidence"
$matrixPath = Join-Path $runbookDir "phase3-step1-traceability-matrix.csv"
$outDir = Join-Path $runbookDir "phase3-auto"

New-Item -ItemType Directory -Path $outDir -Force | Out-Null

function Split-TokenList {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return @()
    }

    return ($Value -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
}

function Export-SqlCsv {
    param(
        [string]$Name,
        [string]$Query
    )

    $outFile = Join-Path $evidenceDir ("{0}.csv" -f $Name)
    $tmpFile = "$outFile.tmp"

    $cmd = @(
        "-S", $Server,
        "-d", $Database,
        "-G",
        "-s", ",",
        "-W",
        "-Q", $Query
    )

    & sqlcmd @cmd | Set-Content -Path $tmpFile

    if ($LASTEXITCODE -ne 0) {
        throw "sqlcmd failed for dataset '$Name'."
    }

    $lines = Get-Content $tmpFile
    $cleanLines = $lines | Where-Object {
        $_ -and
        $_ -notmatch '^\(\d+ rows affected\)' -and
        $_ -notmatch '^-+$' -and
        $_ -notmatch '^Changed database context to'
    }

    Set-Content -Path $outFile -Value $cleanLines
    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue

    return $outFile
}

if ($RunSql) {
    Write-Host "Running Phase 3 Step 1 SQL extraction..." -ForegroundColor Cyan

    New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null

    $step1Queries = @(
        @{ Name = "customers_top200"; Query = "SELECT TOP 200 * FROM dbo.customers ORDER BY customer_id;" },
        @{ Name = "service_accounts_top200"; Query = "SELECT TOP 200 * FROM dbo.service_accounts ORDER BY service_account_id;" },
        @{ Name = "equipment_registry_top200"; Query = "SELECT TOP 200 * FROM dbo.equipment_registry ORDER BY equipment_id;" },
        @{ Name = "service_requests_top200"; Query = "SELECT TOP 200 * FROM dbo.service_requests ORDER BY request_id;" },
        @{ Name = "billing_transactions_top200"; Query = "SELECT TOP 200 * FROM dbo.billing_transactions ORDER BY transaction_id;" },
        @{ Name = "contracts_top200"; Query = "SELECT TOP 200 * FROM dbo.contracts ORDER BY contract_id;" },
        @{ Name = "customer_complaints_top200"; Query = "SELECT TOP 200 * FROM dbo.customer_complaints ORDER BY complaint_id;" },
        @{ Name = "customer_consents_top200"; Query = "SELECT TOP 200 * FROM dbo.customer_consents ORDER BY consent_id;" },
        @{ Name = "governance_glossary_terms_top200"; Query = "SELECT TOP 200 * FROM dbo.governance_glossary_terms ORDER BY term_code;" },
        @{ Name = "governance_cdes_top200"; Query = "SELECT TOP 200 * FROM dbo.governance_cdes ORDER BY cde_id;" },
        @{ Name = "maria_customer"; Query = "SELECT * FROM dbo.customers WHERE customer_id = $MariaCustomerId OR account_number = '$MariaAccountNumber';" },
        @{ Name = "maria_service_accounts"; Query = "SELECT * FROM dbo.service_accounts WHERE customer_id = $MariaCustomerId;" },
        @{ Name = "maria_equipment_registry"; Query = "SELECT * FROM dbo.equipment_registry WHERE service_account_id IN (SELECT service_account_id FROM dbo.service_accounts WHERE customer_id = $MariaCustomerId);" },
        @{ Name = "maria_service_requests"; Query = "SELECT * FROM dbo.service_requests WHERE service_account_id IN (SELECT service_account_id FROM dbo.service_accounts WHERE customer_id = $MariaCustomerId) ORDER BY created_date DESC;" },
        @{ Name = "maria_billing_transactions"; Query = "SELECT * FROM dbo.billing_transactions WHERE service_account_id IN (SELECT service_account_id FROM dbo.service_accounts WHERE customer_id = $MariaCustomerId) ORDER BY transaction_date DESC;" },
        @{ Name = "maria_customer_complaints"; Query = "SELECT * FROM dbo.customer_complaints WHERE customer_id = $MariaCustomerId ORDER BY opened_date DESC;" }
    )

    foreach ($q in $step1Queries) {
        Export-SqlCsv -Name $q.Name -Query $q.Query | Out-Null
    }
}

if (-not (Test-Path $matrixPath)) {
    throw "Required matrix file not found: $matrixPath"
}

$matrixRows = Import-Csv $matrixPath

$invalidStatuses = $matrixRows | Where-Object { $_.final_status -notin @("SUPPORTED", "BACKFIT_REQUIRED") }
if ($invalidStatuses.Count -gt 0) {
    throw "Matrix has invalid final_status values."
}

$requiredEvidence = @(
    "customers_top200.csv",
    "service_accounts_top200.csv",
    "equipment_registry_top200.csv",
    "service_requests_top200.csv",
    "billing_transactions_top200.csv",
    "contracts_top200.csv",
    "customer_complaints_top200.csv",
    "customer_consents_top200.csv",
    "governance_glossary_terms_top200.csv",
    "governance_cdes_top200.csv",
    "maria_customer.csv",
    "maria_service_accounts.csv",
    "maria_equipment_registry.csv",
    "maria_service_requests.csv",
    "maria_billing_transactions.csv",
    "maria_customer_complaints.csv"
)

$evidenceInventory = foreach ($name in $requiredEvidence) {
    $path = Join-Path $evidenceDir $name
    $exists = Test-Path $path
    $lineCount = if ($exists) { (Get-Content $path | Measure-Object -Line).Lines } else { 0 }

    [PSCustomObject]@{
        file = $name
        exists = $exists
        lines = $lineCount
    }
}

$inventoryPath = Join-Path $outDir "phase3-step1-evidence-inventory.csv"
$evidenceInventory | Export-Csv -NoTypeInformation -Path $inventoryPath

$measureRows = @()
$measureToRows = @{}

foreach ($row in $matrixRows) {
    $measures = Split-TokenList $row.semantic_measures
    foreach ($measure in $measures) {
        if (-not $measureToRows.ContainsKey($measure)) {
            $measureToRows[$measure] = New-Object System.Collections.Generic.List[object]
        }
        $measureToRows[$measure].Add($row)
    }
}

foreach ($entry in $measureToRows.GetEnumerator()) {
    $measureName = $entry.Key
    $rows = @($entry.Value)
    $allSupported = ($rows | Where-Object { $_.final_status -ne "SUPPORTED" }).Count -eq 0
    $intentIds = (($rows | ForEach-Object { $_.intent_id }) -join "; ")

    $measureRows += [PSCustomObject]@{
        measure_name = $measureName
        intent_ids = $intentIds
        kpi_certification_status = if ($allSupported) { "CERTIFIED_FOR_AGENT_USE" } else { "CONDITIONAL_PENDING_BACKFIT" }
        glossary_link_status = "REVIEW_REQUIRED"
        owner = "Domain Steward"
        next_action = if ($allSupported) { "Confirm glossary alignment and sign-off" } else { "Resolve linked BACKFIT_REQUIRED intents before certification" }
    }
}

$step2Path = Join-Path $outDir "phase3-step2-kpi-certification.csv"
$measureRows | Sort-Object measure_name | Export-Csv -NoTypeInformation -Path $step2Path

$promptRows = @(
    [PSCustomObject]@{ intent_key = "no-heat"; intent_id = "P3I-002"; prompt = "Customer says no heat since yesterday. What is current SLA status and next action?" },
    [PSCustomObject]@{ intent_key = "missed appointment"; intent_id = "P3I-003"; prompt = "Customer missed appointment and asks why technician did not arrive. What deterministic cause can be provided?" },
    [PSCustomObject]@{ intent_key = "billing while unresolved outage"; intent_id = "P3I-004"; prompt = "Customer has an unresolved outage and still sees charges. Explain whether billing exposure exists and what remediation applies." },
    [PSCustomObject]@{ intent_key = "credit eligibility"; intent_id = "P3I-006"; prompt = "Is this customer eligible for credit based on service outage and billing state?" },
    [PSCustomObject]@{ intent_key = "repeat complaint risk"; intent_id = "P3I-005"; prompt = "Does complaint history indicate repeat-complaint escalation risk?" }
)

$step3Rows = foreach ($row in $promptRows) {
    $matrix = $matrixRows | Where-Object { $_.intent_id -eq $row.intent_id } | Select-Object -First 1
    [PSCustomObject]@{
        intent_key = $row.intent_key
        intent_id = $row.intent_id
        expected_class = if ($matrix.final_status -eq "SUPPORTED") { "SUPPORTED" } else { "BACKFIT_REQUIRED" }
        prompt = $row.prompt
        expected_behavior = if ($matrix.final_status -eq "SUPPORTED") { "Return evidence-backed recommendation path." } else { "Return safe fallback and identify missing governed data attribute." }
    }
}

$step3Path = Join-Path $outDir "phase3-step3-smoke-prompts.csv"
$step3Rows | Export-Csv -NoTypeInformation -Path $step3Path

$draftStageConfigPath = Join-Path $repoRoot "fabric/ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/draft/stage_config.json"
$publishedStageConfigPath = Join-Path $repoRoot "fabric/ee82668f-baa4-9ac6-4e1d-3e762403f320.DataAgent/Files/Config/published/stage_config.json"

$requiredOrderTokens = @(
    "Account Status",
    "Service History",
    "Billing Status",
    "Support Call History",
    "Decision SLA"
)

function Test-OrderInText {
    param(
        [string]$Text,
        [string[]]$Tokens
    )

    $indexes = @()
    foreach ($token in $Tokens) {
        $idx = $Text.IndexOf($token, [System.StringComparison]::OrdinalIgnoreCase)
        $indexes += $idx
    }

    $allFound = ($indexes | Where-Object { $_ -lt 0 }).Count -eq 0
    $ascending = $true
    for ($i = 1; $i -lt $indexes.Count; $i++) {
        if ($indexes[$i] -lt $indexes[$i - 1]) {
            $ascending = $false
            break
        }
    }

    return [PSCustomObject]@{
        all_found = $allFound
        ascending = $ascending
        indexes = ($indexes -join ", ")
    }
}

$draftText = if (Test-Path $draftStageConfigPath) { Get-Content -Raw $draftStageConfigPath } else { "" }
$publishedText = if (Test-Path $publishedStageConfigPath) { Get-Content -Raw $publishedStageConfigPath } else { "" }

$draftOrder = Test-OrderInText -Text $draftText -Tokens $requiredOrderTokens
$publishedOrder = Test-OrderInText -Text $publishedText -Tokens $requiredOrderTokens

$step4Path = Join-Path $outDir "phase3-step4-ordering-check.md"
$step4Content = @(
    "# Phase 3 Step 4 Ordering Check",
    "",
    "## Required token order",
    "",
    "1. Account Status",
    "2. Service History",
    "3. Billing Status",
    "4. Support Call History",
    "5. Decision SLA",
    "",
    "## Draft stage config",
    "",
    "- all_found: $($draftOrder.all_found)",
    "- ascending: $($draftOrder.ascending)",
    "- indexes: $($draftOrder.indexes)",
    "",
    "## Published stage config",
    "",
    "- all_found: $($publishedOrder.all_found)",
    "- ascending: $($publishedOrder.ascending)",
    "- indexes: $($publishedOrder.indexes)",
    "",
    "## Result",
    "",
    "- pass: $([bool]($draftOrder.all_found -and $draftOrder.ascending -and $publishedOrder.all_found -and $publishedOrder.ascending))",
    "- note: This is a token-order guard and should be paired with runtime prompt checks in Fabric."
)
Set-Content -Path $step4Path -Value $step4Content

$backfitRows = $matrixRows | Where-Object { $_.final_status -eq "BACKFIT_REQUIRED" } | ForEach-Object {
    [PSCustomObject]@{
        intent_id = $_.intent_id
        intent_name = $_.intent_name
        owner = $_.owner
        gap_notes = $_.gap_notes
        next_action = $_.next_action
        target_date = "TBD"
        status = "OPEN"
        risk = "MEDIUM"
    }
}

$step5Path = Join-Path $outDir "phase3-step5-backfit-log.csv"
$backfitRows | Export-Csv -NoTypeInformation -Path $step5Path

$fileGatePass = @($inventoryPath, $step2Path, $step3Path, $step4Path, $step5Path) | ForEach-Object { Test-Path $_ } | Where-Object { $_ -eq $false } | Measure-Object | Select-Object -ExpandProperty Count
$fileGateStatus = if ($fileGatePass -eq 0) { "PASS" } else { "FAIL" }

$orderingPass = $draftOrder.all_found -and $draftOrder.ascending -and $publishedOrder.all_found -and $publishedOrder.ascending
$behaviorGateStatus = if ($orderingPass) { "PASS" } else { "PARTIAL" }
$publishGateStatus = "PENDING_MANUAL_FABRIC_SYNC"

$supportedCount = ($matrixRows | Where-Object { $_.final_status -eq "SUPPORTED" }).Count
$backfitCount = ($matrixRows | Where-Object { $_.final_status -eq "BACKFIT_REQUIRED" }).Count

$step6Path = Join-Path $outDir "phase3-step6-closeout-gate.md"
$step6Content = @(
    "# Phase 3 Closeout Gate (Auto-Generated)",
    "",
    "## Cycle status",
    "",
    "- P3-1: COMPLETE (conditional)",
    "- P3-2: AUTO-PREPARED (requires steward certification sign-off)",
    "- P3-3: AUTO-PREPARED smoke prompt pack",
    "- P3-4: ORDERING CHECK GENERATED",
    "- P3-5: BACKFIT LOG GENERATED",
    "- P3-6: READY FOR SIGN-OFF REVIEW",
    "",
    "## Gate summary",
    "",
    "- File Gate: $fileGateStatus",
    "- Behavior Gate: $behaviorGateStatus",
    "- Publish Gate: $publishGateStatus",
    "",
    "## Intent status",
    "",
    "- SUPPORTED: $supportedCount",
    "- BACKFIT_REQUIRED: $backfitCount",
    "",
    "## Manual pull-in points",
    "",
    "1. Domain owner + steward certify P3-2 KPI rows marked CERTIFIED_FOR_AGENT_USE.",
    "2. Run P3-3 smoke prompts in Fabric runtime and paste outputs for proof.",
    "3. Confirm draft/published Data Agent sync is complete in Fabric Source Control.",
    "4. Approve defer/implement decisions for all P3-5 backfit rows.",
    "",
    "## Generated artifacts",
    "",
    "- docs/runbooks/phase3-auto/phase3-step1-evidence-inventory.csv",
    "- docs/runbooks/phase3-auto/phase3-step2-kpi-certification.csv",
    "- docs/runbooks/phase3-auto/phase3-step3-smoke-prompts.csv",
    "- docs/runbooks/phase3-auto/phase3-step4-ordering-check.md",
    "- docs/runbooks/phase3-auto/phase3-step5-backfit-log.csv",
    "- docs/runbooks/phase3-auto/phase3-step6-closeout-gate.md"
)
Set-Content -Path $step6Path -Value $step6Content

Write-Host "Phase 3 automation complete." -ForegroundColor Green
Write-Host "Artifacts written to: docs/runbooks/phase3-auto" -ForegroundColor Green
