$ErrorActionPreference = "Stop"

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$domainData = Get-Content "$PSScriptRoot\_tmp_domains_result.json" -Raw | ConvertFrom-Json
$domainMap = @{}
foreach ($p in $domainData.idMap.PSObject.Properties) { $domainMap[$p.Name] = $p.Value }

$ownerId = "47a147a5-ce27-46e9-be8c-ccb9f0d4f9ff"  # Sean Kelley - placeholder id (synthetic CSV UPNs aren't real Entra identities here)
$results = @()

# Delete any existing data products (script is re-runnable; PATCH can't update these fields after creation)
$existing = Invoke-RestMethod -Uri "$base/dataproducts" -Headers $headers -Method GET
foreach ($dp in $existing.value) {
    try {
        Invoke-RestMethod -Uri "$base/dataproducts/$($dp.id)" -Headers $headers -Method DELETE | Out-Null
        $results += "DELETED existing data product $($dp.id) ($($dp.name))"
    } catch {
        $results += "DELETE-ERROR $($dp.id): $($_.ErrorDetails.Message)"
    }
}

$products = @(
    @{
        code = "DP-CUST360"
        name = "Customer 360"
        type = "MasterDataAndReferenceData"
        domainCode = "DOM-CUSTOPS"
        description = "Single customer view combining demographics, service-account portfolio, consent state, recent complaints, and recent billing - source of truth for customer-level downstream reports and any customer-experience analytics initiative."
        businessUse = "Customer-experience analytics; Marketing eligibility lookup; Privacy compliance reporting. Audience: Marketing Analytics, Customer Experience Operations, Privacy Office, Field Operations Supervisors."
        ownerUpn = "Victoria.Tan@enercare.ca"; ownerName = "Victoria Tan"
        stewardUpn = "Rupal.Solanki@enercare.ca"; stewardName = "Rupal Solanki"
        sensitivity = "Confidential"
        audience = "Marketing Analytics;Customer Experience Operations;Privacy Office;Field Operations Supervisors"
        permittedPurposes = "Customer-experience analytics;Marketing eligibility lookup;Privacy compliance reporting"
        approvalRequirements = "Manager approval + Privacy review for any access including SIN partials"
        accessApprovers = "Victoria.Tan@enercare.ca;Rupal.Solanki@enercare.ca"
        sqlAssets = "dbo.customers;dbo.customer_consents;dbo.customer_complaints"
        fabricAssets = "lh_enercare_demo.dim_customer;lh_enercare_demo.dim_service_account"
        semanticModelAssets = "BrookfieldEnercare/dim_customer;BrookfieldEnercare/dim_service_account"
    }
    @{
        code = "DP-SVCPERF"
        name = "Service Performance"
        type = "Dataset"
        domainCode = "DOM-SVCDEL"
        description = "Field service performance product covering service requests, technician utilization, equipment failure rates, SLA attainment, and call-center first call resolution - used for daily field-ops dashboards and quarterly SLA reviews."
        businessUse = "Operational reporting; Capacity planning; SLA compliance reporting. Audience: Field Operations, Engineering, Customer Experience."
        ownerUpn = "ranbir.singh@enercare.ca"; ownerName = "Ranbir Singh"
        stewardUpn = "Shruthi.Srinivas@enercare.ca"; stewardName = "Shruthi Srinivas"
        sensitivity = "Confidential"
        audience = "Field Operations;Engineering;Customer Experience"
        permittedPurposes = "Operational reporting;Capacity planning;SLA compliance reporting"
        approvalRequirements = "Manager approval"
        accessApprovers = "ranbir.singh@enercare.ca;Shruthi.Srinivas@enercare.ca"
        sqlAssets = "dbo.service_requests;dbo.equipment_registry;dbo.service_zones;dbo.employees"
        fabricAssets = "lh_enercare_demo.fct_service_request;lh_enercare_demo.dim_equipment;lh_enercare_demo.fct_cc_interactions"
        semanticModelAssets = "BrookfieldEnercare/fct_service_request;BrookfieldEnercare/dim_equipment;BrookfieldEnercare/fct_cc_interactions"
    }
    @{
        code = "DP-BILLHEALTH"
        name = "Billing and Contract Health"
        type = "Dataset"
        domainCode = "DOM-REVCON"
        description = "Monthly recurring revenue, contract churn, auto-renewal compliance, and billing health product - source for revenue forecast and Ontario Consumer Protection Act compliance reporting."
        businessUse = "Revenue forecast; Regulatory reporting; Churn analysis. Audience: Finance, Revenue Strategy, Regulatory Compliance."
        ownerUpn = "Ci.Zhu@enercare.ca"; ownerName = "Ci Zhu"
        stewardUpn = "Ci.Zhu@enercare.ca"; stewardName = "Ci Zhu"
        sensitivity = "Highly Confidential"
        audience = "Finance;Revenue Strategy;Regulatory Compliance"
        permittedPurposes = "Revenue forecast;Regulatory reporting;Churn analysis"
        approvalRequirements = "Manager approval + Finance review for full-amount access"
        accessApprovers = "Ci.Zhu@enercare.ca;ranbir.singh@enercare.ca"
        sqlAssets = "dbo.products;dbo.contracts;dbo.billing_transactions"
        fabricAssets = "lh_enercare_demo.fct_billing;lh_enercare_demo.fct_contract_month;lh_enercare_demo.dim_product"
        semanticModelAssets = "BrookfieldEnercare/fct_billing;BrookfieldEnercare/fct_contract_month;BrookfieldEnercare/dim_product"
    }
)

$idMap = @{}
foreach ($p in $products) {
    $body = @{
        name = $p.name
        type = $p.type
        domain = $domainMap[$p.domainCode]
        status = "Published"
        description = "<div>$($p.description)</div>"
        businessUse = "<div>$($p.businessUse)</div>"
        contacts = @{
            owner = @(@{ id = $ownerId; description = "$($p.ownerName) - Owner [$($p.ownerUpn)]" })
            steward = @(@{ id = $ownerId; description = "$($p.stewardName) - Steward [$($p.stewardUpn)]" })
        }
        managedAttributes = @(
            @{ name = "OwnerUpn"; value = $p.ownerUpn }
            @{ name = "StewardUpn"; value = $p.stewardUpn }
            @{ name = "SensitivityLabel"; value = $p.sensitivity }
            @{ name = "Audience"; value = $p.audience }
            @{ name = "PermittedPurposes"; value = $p.permittedPurposes }
            @{ name = "ApprovalRequirements"; value = $p.approvalRequirements }
            @{ name = "AccessApprovers"; value = $p.accessApprovers }
            @{ name = "SqlAssets"; value = $p.sqlAssets }
            @{ name = "FabricAssets"; value = $p.fabricAssets }
            @{ name = "SemanticModelAssets"; value = $p.semanticModelAssets }
        )
    }
    $jsonBody = $body | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-RestMethod -Uri "$base/dataproducts" -Headers $headers -Method POST -Body $jsonBody
        $idMap[$p.code] = $resp.id
        $results += "CREATED DATAPRODUCT $($p.code) -> $($resp.id)"
    } catch {
        $results += "ERROR creating data product $($p.code): $($_.ErrorDetails.Message)"
    }
}

$output = @{ results = $results; idMap = $idMap }
$output | ConvertTo-Json -Depth 10 | Out-File -FilePath "$PSScriptRoot\_tmp_dataproducts_result.json" -Encoding utf8
"DONE"
