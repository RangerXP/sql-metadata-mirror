$ErrorActionPreference = "Stop"

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$domainData = Get-Content "$PSScriptRoot\_tmp_domains_result.json" -Raw | ConvertFrom-Json
$domainMap = @{}
foreach ($p in $domainData.idMap.PSObject.Properties) { $domainMap[$p.Name] = $p.Value }

$dpData = Get-Content "$PSScriptRoot\_tmp_dataproducts_result.json" -Raw | ConvertFrom-Json
$dataProductMap = @{}
foreach ($p in $dpData.idMap.PSObject.Properties) { $dataProductMap[$p.Name] = $p.Value }
$ownerId = "47a147a5-ce27-46e9-be8c-ccb9f0d4f9ff"  # Sean Kelley - placeholder owner (synthetic CSV UPNs aren't real Entra identities here)

$results = @()

# Clean up throwaway schema-probe objectives (and their key results) from discovery pass
$existingObjectives = Invoke-RestMethod -Uri "$base/objectives" -Headers $headers -Method GET
foreach ($obj in $existingObjectives.value) {
    $isProbe = $false
    if ($obj.managedAttributes) {
        foreach ($attr in $obj.managedAttributes) {
            if ($attr.name -eq "Name" -and $attr.value -like "ZZProbe*") { $isProbe = $true }
        }
    }
    if ($obj.definition -like "Test def*") { $isProbe = $true }
    if ($isProbe) {
        try {
            $krs = Invoke-RestMethod -Uri "$base/objectives/$($obj.id)/keyresults" -Headers $headers -Method GET
            foreach ($kr in $krs.value) {
                Invoke-RestMethod -Uri "$base/objectives/$($obj.id)/keyresults/$($kr.id)" -Headers $headers -Method DELETE | Out-Null
                $results += "DELETED probe KR $($kr.id)"
            }
            Invoke-RestMethod -Uri "$base/objectives/$($obj.id)" -Headers $headers -Method DELETE | Out-Null
            $results += "DELETED probe objective $($obj.id)"
        } catch {
            $results += "DELETE-PROBE-ERROR $($obj.id): $($_.ErrorDetails.Message)"
        }
    }
}

# code, name, domainCode, definition, ownerUpn, targetDate, dataProductCode, keyResults[]
$okrs = @(
    @{
        code = "OKR-SVCDEL-SLA"
        name = "Protect SLA Attainment In Field Service Delivery"
        domainCode = "DOM-SVCDEL"
        definition = "Hold SLA breach exposure at or below target across all service-request queues, closing the auto-suppression dispatch gap surfaced in Act 2 of the Maria northstar scenario."
        ownerUpn = "ranbir.singh@enercare.ca"
        targetDate = "2026-12-31"
        dataProductCode = "DP-SVCPERF"
        keyResults = @(
            @{ code = "KR-SLA-BREACH"; name = "SLA Breach Rate At Or Below Target"; metricSource = "kpi_metadata.SLA_BRCH_RATE"; goal = 5.00; max = 100.00 }
        )
    }
    @{
        code = "OKR-CUSTOPS-CX"
        name = "Improve Call-Center Customer Experience"
        domainCode = "DOM-CUSTOPS"
        definition = "Raise first-contact resolution and customer satisfaction for call-center interactions to their certified target thresholds."
        ownerUpn = "Victoria.Tan@enercare.ca"
        targetDate = "2026-12-31"
        dataProductCode = "DP-CUST360"
        keyResults = @(
            @{ code = "KR-FCR-RATE"; name = "First Contact Resolution At Or Above Target"; metricSource = "kpi_metadata.FCR"; goal = 78.00; max = 100.00 }
            @{ code = "KR-CSAT-SCORE"; name = "Customer Satisfaction At Or Above Target"; metricSource = "kpi_metadata.CSAT"; goal = 4.20; max = 5.00 }
        )
    }
    @{
        code = "OKR-REVCON-RETAIN"
        name = "Protect Renewal Revenue And Reduce Repeat Billing Complaints"
        domainCode = "DOM-REVCON"
        definition = "Sustain protection-plan renewal rate at target while reducing the rate of customers filing more than one billing complaint per period."
        ownerUpn = "Ci.Zhu@enercare.ca"
        targetDate = "2026-12-31"
        dataProductCode = "DP-BILLHEALTH"
        keyResults = @(
            @{ code = "KR-PP-RENEWAL"; name = "Protection Plan Renewal Rate At Or Above Target"; metricSource = "kpi_metadata.PP_RNW_RATE"; goal = 82.00; max = 100.00 }
            @{ code = "KR-REPEAT-COMPLAINT"; name = "Repeat Billing Complaint Rate Reduced"; metricSource = "BrookfieldEnercare/_Measures/RepeatComplaintRate"; goal = 10.00; max = 100.00 }
        )
    }
)

$idMap = @{}
foreach ($o in $okrs) {
    $managedAttributes = @(
        @{ name = "Name"; value = $o.name }
        @{ name = "LinkedDataProduct"; value = "$($o.dataProductCode) ($($dataProductMap[$o.dataProductCode]))" }
        @{ name = "OwnerUpn"; value = $o.ownerUpn }
    )
    $body = @{
        domain = $domainMap[$o.domainCode]
        status = "Published"
        definition = $o.definition
        targetDate = $o.targetDate
        contacts = @{ owner = @(@{ id = $ownerId; description = "Owner" }) }
        managedAttributes = $managedAttributes
    }
    $jsonBody = $body | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-RestMethod -Uri "$base/objectives" -Headers $headers -Method POST -Body $jsonBody
        $idMap[$o.code] = $resp.id
        $results += "CREATED OBJECTIVE $($o.code) -> $($resp.id)"

        foreach ($kr in $o.keyResults) {
            $krDefinition = "$($kr.name) - tracks $($kr.metricSource). Goal $($kr.goal) / Max $($kr.max)."
            $krBody = @{
                status = "NotTrack"
                domainId = $domainMap[$o.domainCode]
                definition = $krDefinition
                goal = $kr.goal
                max = $kr.max
                progress = 0.0
            }
            $krJsonBody = $krBody | ConvertTo-Json -Depth 10
            try {
                $krResp = Invoke-RestMethod -Uri "$base/objectives/$($resp.id)/keyresults" -Headers $headers -Method POST -Body $krJsonBody
                $idMap["$($o.code)/$($kr.code)"] = $krResp.id
                $results += "CREATED KEYRESULT $($o.code)/$($kr.code) -> $($krResp.id)"
            } catch {
                $results += "ERROR creating KR $($o.code)/$($kr.code): $($_.ErrorDetails.Message)"
            }
        }
    } catch {
        $results += "ERROR creating objective $($o.code): $($_.ErrorDetails.Message)"
    }
}

$output = @{ results = $results; idMap = $idMap }
$output | ConvertTo-Json -Depth 10 | Out-File -FilePath "$PSScriptRoot\_tmp_okr_result.json" -Encoding utf8
"DONE"
