$ErrorActionPreference = "Stop"

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$domainData = Get-Content "$PSScriptRoot\_tmp_domains_result.json" -Raw | ConvertFrom-Json
$domainMap = @{}
foreach ($p in $domainData.idMap.PSObject.Properties) { $domainMap[$p.Name] = $p.Value }
$ownerId = "47a147a5-ce27-46e9-be8c-ccb9f0d4f9ff"  # Sean Kelley - placeholder owner (synthetic CSV UPNs aren't real Entra identities here)

$results = @()

# Clean up throwaway schema-probe CDEs from discovery pass (all Draft, directly deletable)
$existing = Invoke-RestMethod -Uri "$base/criticaldataelements" -Headers $headers -Method GET
foreach ($cde in $existing.value) {
    if ($cde.name -like "ZZProbeCDE*") {
        try {
            Invoke-RestMethod -Uri "$base/criticaldataelements/$($cde.id)" -Headers $headers -Method DELETE | Out-Null
            $results += "DELETED probe $($cde.name) $($cde.id)"
        } catch {
            $results += "DELETE-PROBE-ERROR $($cde.name): $($_.ErrorDetails.Message)"
        }
    }
}

# code, name, domainCode, termCode, dataType(Text|Number), regulator, regulatorBasis, ownerUpn, stewardUpn, sensitivity, validationRule, boundColumns, description
$cdes = @(
    @{code="CDE-ACCTNUM";      name="Account Number";              domainCode="DOM-CUSTOPS"; termCode="GT-ACCOUNT";  dataType="Text";   regulator="Internal";  basis="Operational Identifier";        owner="Ci.Zhu@enercare.ca";      steward="Rupal.Solanki@enercare.ca"; sensitivity="Internal";            rule="Format ^[A-Z0-9]{8,20}`$";                                    cols="dbo.customers.account_number;dbo.service_accounts.account_number"; def="Customer-facing primary identifier used on bills and portals. Must be unique and immutable."}
    @{code="CDE-SIN";          name="Social Insurance Number";      domainCode="DOM-CUSTOPS"; termCode="GT-SIN";      dataType="Text";   regulator="PIPEDA";    basis="Personal Information";          owner="Ci.Zhu@enercare.ca";      steward="Ci.Zhu@enercare.ca";        sensitivity="Highly Confidential"; rule="Full = ^\d{3}-\d{3}-\d{3}`$ with Luhn check; partial = ^\d{4}`$"; cols="dbo.customers.sin_last_4;dbo.employees.sin_full"; def="Canadian government identifier. Highly Confidential when stored in full; partial last-4 stored only when business need is documented."}
    @{code="CDE-EMAIL";        name="Email Address";                domainCode="DOM-CUSTOPS"; termCode="GT-PII";      dataType="Text";   regulator="CASL";      basis="Commercial Electronic Message Identifier"; owner="Ci.Zhu@enercare.ca"; steward="Rupal.Solanki@enercare.ca"; sensitivity="Confidential";        rule="Format ^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}`$";               cols="dbo.customers.email;dbo.employees.email"; def="Email is a CASL-relevant identifier. Marketing use requires an active Granted consent record."}
    @{code="CDE-PHONE";        name="Phone Number";                 domainCode="DOM-CUSTOPS"; termCode="GT-PII";      dataType="Text";   regulator="CASL";      basis="DNC-list-eligible identifier";  owner="Ci.Zhu@enercare.ca";      steward="Rupal.Solanki@enercare.ca"; sensitivity="Confidential";        rule="E.164 or NANP format";                                          cols="dbo.customers.phone;dbo.employees.phone"; def="Phone is a CASL-relevant identifier and subject to Do Not Call list management."}
    @{code="CDE-POSTAL";       name="Postal Code";                  domainCode="DOM-CUSTOPS"; termCode="GT-FSA";      dataType="Text";   regulator="PIPEDA";    basis="Geographic PII";                owner="Ci.Zhu@enercare.ca";      steward="Rupal.Solanki@enercare.ca"; sensitivity="Confidential";        rule="Canadian format ^[A-Z]\d[A-Z] ?\d[A-Z]\d`$";                    cols="dbo.customers.postal_code;dbo.service_accounts.postal_code;dbo.employees.home_postal_code"; def="Canadian six-character postal code. Marketing analytics must use FSA-only (first three characters)."}
    @{code="CDE-SVCADDR";      name="Service Address";              domainCode="DOM-CUSTOPS"; termCode="GT-PREMISE";  dataType="Text";   regulator="PIPEDA";    basis="Geographic PII";                owner="Ci.Zhu@enercare.ca";      steward="Rupal.Solanki@enercare.ca"; sensitivity="Confidential";        rule="Non-null free-text street address";                             cols="dbo.service_accounts.service_address"; def="Residential service address. Combined with name produces re-identifiable PII."}
    @{code="CDE-GEO";          name="Geographic Coordinates";       domainCode="DOM-CUSTOPS"; termCode="GT-GEOPII";   dataType="Number"; regulator="PIPEDA";    basis="Precise location PII";          owner="Ci.Zhu@enercare.ca";      steward="Rupal.Solanki@enercare.ca"; sensitivity="Confidential";        rule="-90 to 90 lat; -180 to 180 long";                               cols="dbo.service_accounts.latitude;dbo.service_accounts.longitude"; def="Sub-FSA-precision coordinates. Higher sensitivity than postal code."}
    @{code="CDE-PAN";          name="Payment Account Number Partial"; domainCode="DOM-REVCON"; termCode="GT-PCISCOPE"; dataType="Text";  regulator="PCI DSS";   basis="PCI-scope token";                owner="Ci.Zhu@enercare.ca";      steward="Ci.Zhu@enercare.ca";        sensitivity="Highly Confidential"; rule="Format ^\d{4}`$";                                               cols="dbo.billing_transactions.card_pan_last_4"; def="Last four digits of card PAN. Demo storage only; production stores tokenized references."}
    @{code="CDE-BANKROUTE";    name="Bank Routing Partial";         domainCode="DOM-REVCON"; termCode=$null;          dataType="Text";   regulator=$null;       basis="Financial Identifier";           owner="Ci.Zhu@enercare.ca";      steward="Ci.Zhu@enercare.ca";        sensitivity="Highly Confidential"; rule="Format ^\d{4}`$";                                               cols="dbo.billing_transactions.bank_routing_last_4"; def="Last four digits of bank routing. Used for pre-authorized debit reconciliation only."}
    @{code="CDE-CONTRACTAMT";  name="Contract Monthly Amount";      domainCode="DOM-REVCON"; termCode="GT-CONTRACT"; dataType="Number"; regulator="OEB";       basis="Material Financial Element";     owner="Ci.Zhu@enercare.ca";      steward="Ci.Zhu@enercare.ca";        sensitivity="Confidential";        rule="Positive decimal up to 9999.99";                                cols="dbo.contracts.monthly_amount"; def="Monthly recurring amount per contract. Aggregated to MRR for management reporting."}
    @{code="CDE-CONSENTSTATE"; name="Consent State";                domainCode="DOM-CUSTOPS"; termCode="GT-CONSENT"; dataType="Text";   regulator="PIPEDA";    basis="Consent Record";                 owner="Ci.Zhu@enercare.ca";      steward="Ci.Zhu@enercare.ca";        sensitivity="Confidential";        rule="In set Granted Withdrawn Expired";                              cols="dbo.customer_consents.consent_status;dbo.customer_consents.consent_type"; def="Current consent state per type. Drives marketing eligibility and DSAR compliance."}
    @{code="CDE-COMPLAINTREF"; name="Regulator Case Reference";     domainCode="DOM-CUSTOPS"; termCode="GT-COMPLAINT"; dataType="Text"; regulator="OEB/OCPA";  basis="Regulator Linkage";              owner="Ci.Zhu@enercare.ca";      steward="Rupal.Solanki@enercare.ca"; sensitivity="Internal";            rule="Format ^[A-Z]{3,5}-\d{4}-\d{4}`$";                              cols="dbo.customer_complaints.regulator_case_ref"; def="External regulator-assigned case identifier. Required for reportable complaints."}
)

# term id map (already created via create_glossary_terms.ps1) - loaded from that script's output file
$termIdMapFile = "$PSScriptRoot\_tmp_glossary_terms_result.json"
$termIdMap = @{}
if (Test-Path $termIdMapFile) {
    $termData = Get-Content $termIdMapFile -Raw | ConvertFrom-Json
    foreach ($prop in $termData.idMap.PSObject.Properties) { $termIdMap[$prop.Name] = $prop.Value }
}

$idMap = @{}
foreach ($c in $cdes) {
    $managedAttributes = @()
    if ($c.termCode -and $termIdMap.ContainsKey($c.termCode)) {
        $managedAttributes += @{ name = "GlossaryTerm"; value = "$($c.termCode) ($($termIdMap[$c.termCode]))" }
    }
    if ($c.regulator) { $managedAttributes += @{ name = "Regulator"; value = $c.regulator } }
    if ($c.basis) { $managedAttributes += @{ name = "RegulatoryBasis"; value = $c.basis } }
    if ($c.sensitivity) { $managedAttributes += @{ name = "SensitivityLabel"; value = $c.sensitivity } }
    if ($c.rule) { $managedAttributes += @{ name = "ValidationRule"; value = $c.rule } }
    if ($c.cols) { $managedAttributes += @{ name = "BoundColumns"; value = $c.cols } }
    if ($c.owner) { $managedAttributes += @{ name = "OwnerUpn"; value = $c.owner } }
    if ($c.steward) { $managedAttributes += @{ name = "StewardUpn"; value = $c.steward } }

    $body = @{
        name = $c.name
        domain = $domainMap[$c.domainCode]
        status = "Published"
        dataType = $c.dataType
        description = "<div>$($c.def)</div>"
        contacts = @{ owner = @(@{ id = $ownerId; description = "Owner" }) }
        managedAttributes = $managedAttributes
    }
    $jsonBody = $body | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-RestMethod -Uri "$base/criticaldataelements" -Headers $headers -Method POST -Body $jsonBody
        $idMap[$c.code] = $resp.id
        $results += "CREATED $($c.code) -> $($resp.id)"
    } catch {
        $results += "ERROR creating $($c.code): $($_.ErrorDetails.Message)"
    }
}

$output = @{ results = $results; idMap = $idMap }
$output | ConvertTo-Json -Depth 10 | Out-File -FilePath "$PSScriptRoot\_tmp_cde_result.json" -Encoding utf8
"DONE"
