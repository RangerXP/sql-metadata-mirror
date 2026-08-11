$ErrorActionPreference = "Stop"

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$ownerId = "47a147a5-ce27-46e9-be8c-ccb9f0d4f9ff"  # Sean Kelley - placeholder id (synthetic CSV UPNs aren't real Entra identities here)
$results = @()

# code, name, type, description, owner1, owner2 (optional), steward
$domains = @(
    @{
        code = "DOM-CUSTOPS"
        name = "Customer Operations"
        type = "DataDomain"
        description = "Customer master data, customer relationship records, consent records, and operations-facing interaction history. Authority for personal identifiers and consent state across Enercare."
        owner1Upn = "Victoria.Tan@enercare.ca"; owner1Name = "Victoria Tan"
        owner2Upn = "Ci.Zhu@enercare.ca"; owner2Name = "Ci Zhu"
        stewardUpn = "Rupal.Solanki@enercare.ca"; stewardName = "Rupal Solanki"
    }
    @{
        code = "DOM-SVCDEL"
        name = "Service Delivery"
        type = "FunctionalUnit"
        description = "Field operations service requests, work orders, technician dispatch, equipment registry, and territorial service zones. Authority for service-event and asset records."
        owner1Upn = "ranbir.singh@enercare.ca"; owner1Name = "Ranbir Singh"
        owner2Upn = "Ci.Zhu@enercare.ca"; owner2Name = "Ci Zhu"
        stewardUpn = "Shruthi.Srinivas@enercare.ca"; stewardName = "Shruthi Srinivas"
    }
    @{
        code = "DOM-REVCON"
        name = "Revenue and Contracts"
        type = "Regulatory"
        description = "Products, contracts, billing transactions, and revenue recognition surfaces subject to Ontario Consumer Protection Act and financial reporting controls. Includes auto-renewal disclosure compliance."
        owner1Upn = "Ci.Zhu@enercare.ca"; owner1Name = "Ci Zhu"
        owner2Upn = "ranbir.singh@enercare.ca"; owner2Name = "Ranbir Singh"
        stewardUpn = "Ci.Zhu@enercare.ca"; stewardName = "Ci Zhu"
    }
)

$idMap = @{}
foreach ($d in $domains) {
    $managedAttributes = @(
        @{ name = "OwnerPrimary"; value = "$($d.owner1Name) ($($d.owner1Upn))" }
        @{ name = "OwnerSecondary"; value = "$($d.owner2Name) ($($d.owner2Upn))" }
        @{ name = "Steward"; value = "$($d.stewardName) ($($d.stewardUpn))" }
    )
    $body = @{
        name = $d.name
        type = $d.type
        status = "Published"
        description = "<div>$($d.description)</div>"
        managedAttributes = $managedAttributes
    }
    $jsonBody = $body | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-RestMethod -Uri "$base/businessdomains" -Headers $headers -Method POST -Body $jsonBody
        $idMap[$d.code] = $resp.id
        $results += "CREATED DOMAIN $($d.code) -> $($resp.id)"
    } catch {
        $results += "ERROR creating domain $($d.code): $($_.ErrorDetails.Message)"
    }
}

$output = @{ results = $results; idMap = $idMap }
$output | ConvertTo-Json -Depth 10 | Out-File -FilePath "$PSScriptRoot\_tmp_domains_result.json" -Encoding utf8
"DONE"
