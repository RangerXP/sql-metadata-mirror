# Links real scanned Azure SQL DataAssets to their Data Products in the Unified Catalog,
# superseding the managedAttributes text-workaround now that a live Purview scan exists.
# Re-runnable: relationship POSTs are idempotent per (dataProductId, entityId) pair.

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$dgBase = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$links = @(
  # Customer 360
  @{ dp = "22794e10-31d6-4f15-b4f0-8238a2657503"; dpName = "Customer 360"; asset = "customer_consents"; guid = "7dc3a39c-668e-4070-8977-77f6f6f60000" }
  @{ dp = "22794e10-31d6-4f15-b4f0-8238a2657503"; dpName = "Customer 360"; asset = "customer_complaints"; guid = "738df67c-3c16-45dc-85f7-56f6f6f60000" }

  # Service Performance
  @{ dp = "d5c9cc77-aaaf-4e07-9010-e3758d50cb87"; dpName = "Service Performance"; asset = "service_requests"; guid = "df87a5a0-1133-420d-baac-a8f6f6f60000" }
  @{ dp = "d5c9cc77-aaaf-4e07-9010-e3758d50cb87"; dpName = "Service Performance"; asset = "equipment_registry"; guid = "444e4b6a-17fb-42ca-9778-53f6f6f60000" }
  @{ dp = "d5c9cc77-aaaf-4e07-9010-e3758d50cb87"; dpName = "Service Performance"; asset = "service_zones"; guid = "78cfdfcd-15b8-43f8-ad1f-16f6f6f60000" }
  @{ dp = "d5c9cc77-aaaf-4e07-9010-e3758d50cb87"; dpName = "Service Performance"; asset = "employees"; guid = "1b3cff9b-38ae-4ae8-80b1-93f6f6f60000" }

  # Billing and Contract Health
  @{ dp = "514786ca-f94a-4859-8744-2f6f19090372"; dpName = "Billing and Contract Health"; asset = "products"; guid = "98ae7ff1-8c6a-4c1d-b030-b1f6f6f60000" }
  @{ dp = "514786ca-f94a-4859-8744-2f6f19090372"; dpName = "Billing and Contract Health"; asset = "contracts"; guid = "d12d7ac0-1234-4f79-b5a5-c4f6f6f60000" }
  @{ dp = "514786ca-f94a-4859-8744-2f6f19090372"; dpName = "Billing and Contract Health"; asset = "billing_transactions"; guid = "94b3da86-8850-4a05-b8e0-44f6f6f60000" }
)

$results = @()
foreach ($link in $links) {
  $uri = "$dgBase/dataproducts/$($link.dp)/relationships?entityType=DataAsset"
  $body = @{ entityType = "DataAsset"; entityId = $link.guid } | ConvertTo-Json
  try {
    $resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Post -Body $body
    $results += [pscustomobject]@{ dataProduct = $link.dpName; asset = $link.asset; status = "OK"; detail = $resp.relationshipType }
  } catch {
    $errDetail = if ($_.ErrorDetails) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    $results += [pscustomobject]@{ dataProduct = $link.dpName; asset = $link.asset; status = "ERROR"; detail = $errDetail }
  }
}

$results | ConvertTo-Json -Depth 6 | Out-File "$PSScriptRoot\_tmp_link_results.json"
Write-Output "done"
