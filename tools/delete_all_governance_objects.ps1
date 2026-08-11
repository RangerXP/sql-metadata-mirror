$ErrorActionPreference = "Stop"

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$results = @()

function Delete-WithDraftFallback {
    param($uri, $label)
    try {
        Invoke-RestMethod -Uri $uri -Headers $headers -Method DELETE | Out-Null
        $script:results += "DELETED $label"
    } catch {
        # Published objects often can't be deleted directly - PATCH to Draft first, then retry
        try {
            $patchBody = '{"status":"Draft"}'
            Invoke-RestMethod -Uri $uri -Headers $headers -Method PATCH -Body $patchBody | Out-Null
            Invoke-RestMethod -Uri $uri -Headers $headers -Method DELETE | Out-Null
            $script:results += "DELETED (after draft) $label"
        } catch {
            $script:results += "DELETE-ERROR $label : $($_.ErrorDetails.Message)"
        }
    }
}

# 1. Key results (children of objectives)
$objectives = Invoke-RestMethod -Uri "$base/objectives" -Headers $headers -Method GET
foreach ($obj in $objectives.value) {
    $krs = Invoke-RestMethod -Uri "$base/objectives/$($obj.id)/keyresults" -Headers $headers -Method GET
    foreach ($kr in $krs.value) {
        Delete-WithDraftFallback -uri "$base/objectives/$($obj.id)/keyresults/$($kr.id)" -label "KeyResult $($kr.id)"
    }
}

# 2. Objectives
foreach ($obj in $objectives.value) {
    Delete-WithDraftFallback -uri "$base/objectives/$($obj.id)" -label "Objective $($obj.id)"
}

# 3. Critical Data Elements
$cdes = Invoke-RestMethod -Uri "$base/criticaldataelements" -Headers $headers -Method GET
foreach ($cde in $cdes.value) {
    Delete-WithDraftFallback -uri "$base/criticaldataelements/$($cde.id)" -label "CDE $($cde.id) ($($cde.name))"
}

# 4. Terms
$terms = Invoke-RestMethod -Uri "$base/terms" -Headers $headers -Method GET
foreach ($t in $terms.value) {
    Delete-WithDraftFallback -uri "$base/terms/$($t.id)" -label "Term $($t.id) ($($t.name))"
}

# 5. Data Products
$dps = Invoke-RestMethod -Uri "$base/dataproducts" -Headers $headers -Method GET
foreach ($dp in $dps.value) {
    Delete-WithDraftFallback -uri "$base/dataproducts/$($dp.id)" -label "DataProduct $($dp.id) ($($dp.name))"
}

# 6. Domains (last, after all children removed)
$domains = Invoke-RestMethod -Uri "$base/businessdomains" -Headers $headers -Method GET
foreach ($d in $domains.value) {
    Delete-WithDraftFallback -uri "$base/businessdomains/$($d.id)" -label "Domain $($d.id) ($($d.name))"
}

$results | Out-File -FilePath "$PSScriptRoot\_tmp_delete_all_result.txt" -Encoding utf8
"DONE"
