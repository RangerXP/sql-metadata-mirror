$ErrorActionPreference = "Stop"

$token = az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
$base = "https://b7e47691-9726-4f67-a302-e567815f3522-api.purview-service.microsoft.com/datagovernance/catalog"

$domainData = Get-Content "$PSScriptRoot\_tmp_domains_result.json" -Raw | ConvertFrom-Json
$domainMap = @{}
foreach ($p in $domainData.idMap.PSObject.Properties) { $domainMap[$p.Name] = $p.Value }

$ownerId = "47a147a5-ce27-46e9-be8c-ccb9f0d4f9ff"  # Sean Kelley - placeholder owner for all synthetic CSV owner_upn values (not resolvable Entra identities in this demo tenant)

# code, name, acronym, parentCode, domainCode, definition, resourceUrl
$terms = @(
    @{code="GT-ACCOUNT";   name="Account";                                          acronym=$null;    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="A relationship record uniquely identifying a customer entity within Enercare billing and service systems. Carries an account_number that is the customer-facing identifier on bills and portals."; url="https://www.enercare.ca/about/governance/glossary#account"}
    @{code="GT-CUST";      name="Customer";                                         acronym=$null;    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="The contracting party for one or more service accounts. May be a residential individual or a business entity."; url="https://www.enercare.ca/about/governance/glossary#customer"}
    @{code="GT-PREMISE";   name="Premise";                                          acronym=$null;    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="The physical location where service is delivered. May be different from the billing address. Identified by service_address."; url="https://www.oeb.ca/glossary"}
    @{code="GT-SVCACCT";   name="Service Account";                                  acronym=$null;    parentCode="GT-ACCOUNT"; domainCode="DOM-CUSTOPS"; def="A billing relationship between a customer and a service or product. A customer may have multiple service accounts across utilities and products."; url="https://www.enercare.ca/about/governance/glossary#service-account"}
    @{code="GT-FSA";       name="Forward Sortation Area";                          acronym="FSA";    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="The first three characters of a Canadian postal code. Identifies a regional postal sortation area and is the minimum location-PII granularity used for marketing analytics."; url="https://www.canadapost-postescanada.ca/cpc/en/support/articles/addressing-guidelines/postal-codes.page"}
    @{code="GT-PIPEDA";    name="Personal Information Protection and Electronic Documents Act"; acronym="PIPEDA"; parentCode=$null; domainCode="DOM-CUSTOPS"; def="Federal Canadian privacy law that governs how private-sector organizations collect use and disclose personal information. Establishes consent withdrawal as a customer right."; url="https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/"}
    @{code="GT-CASL";      name="Canadian Anti-Spam Legislation";                  acronym="CASL";   parentCode=$null;      domainCode="DOM-CUSTOPS"; def="Federal Canadian law requiring express consent for commercial electronic messages. Withdrawal must be honored within ten business days."; url="https://crtc.gc.ca/eng/internet/anti.htm"}
    @{code="GT-CONSENT";   name="Customer Consent";                                acronym=$null;    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="A recorded customer authorization to perform a specific data use defined by consent_type. Carries a legal_basis a granted_date and a withdrawn_date."; url="https://www.priv.gc.ca/en/privacy-topics/collecting-personal-information/consent/"}
    @{code="GT-COMPLAINT"; name="Customer Complaint";                             acronym=$null;    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="A formally logged customer grievance recorded against a service account or billing event. Regulator-reportable complaints carry a regulator_case_ref."; url="https://www.enercare.ca/about/governance/glossary#complaint"}
    @{code="GT-SVCREQ";    name="Service Request";                                acronym=$null;    parentCode=$null;      domainCode="DOM-SVCDEL"; def="A work order created in response to a customer-reported issue or scheduled maintenance event."; url="https://www.enercare.ca/about/governance/glossary#service-request"}
    @{code="GT-WORKORDER"; name="Work Order";                                     acronym=$null;    parentCode="GT-SVCREQ"; domainCode="DOM-SVCDEL"; def="Synonym for Service Request used in technician dispatch context."; url=$null}
    @{code="GT-TECH";      name="Technician";                                     acronym=$null;    parentCode=$null;      domainCode="DOM-SVCDEL"; def="A field employee assigned to fulfill service requests. Identified by employee_id and upn."; url="https://www.enercare.ca/about/governance/glossary#technician"}
    @{code="GT-SVCZONE";   name="Service Zone";                                   acronym=$null;    parentCode=$null;      domainCode="DOM-SVCDEL"; def="A territorial unit aligned to dispatch boundaries SLA targets and field supervision. Forms a parent-child hierarchy across Province > Region > Zone."; url="https://www.enercare.ca/about/governance/glossary#service-zone"}
    @{code="GT-FCR";       name="First Call Resolution";                         acronym="FCR";    parentCode=$null;      domainCode="DOM-SVCDEL"; def="The percentage of customer interactions that are fully resolved during the first contact without follow-up. Calculated monthly on the call-center plane."; url="https://www.enercare.ca/about/governance/kpi#fcr"}
    @{code="GT-MTTR";      name="Mean Time To Repair";                           acronym="MTTR";   parentCode=$null;      domainCode="DOM-SVCDEL"; def="Average elapsed time from service request creation to completion. Reported per equipment type and per service zone."; url="https://www.enercare.ca/about/governance/kpi#mttr"}
    @{code="GT-TRUCKROLL"; name="Truck Roll";                                    acronym=$null;    parentCode=$null;      domainCode="DOM-SVCDEL"; def="A physical technician dispatch to a service address. Carries a cost-recovery impact and SLA window."; url="https://www.enercare.ca/about/governance/glossary#truck-roll"}
    @{code="GT-SLA";       name="Service Level Agreement";                      acronym="SLA";    parentCode=$null;      domainCode="DOM-SVCDEL"; def="The contracted or policy-defined response and resolution targets per service-request priority and service zone."; url="https://www.enercare.ca/about/governance/glossary#sla"}
    @{code="GT-EQUIP";     name="Equipment Registry";                           acronym=$null;    parentCode=$null;      domainCode="DOM-SVCDEL"; def="The installed-base record of all furnaces water heaters and air conditioners under contract. Includes serial_number ownership_type and warranty_expiry."; url="https://www.enercare.ca/about/governance/glossary#equipment"}
    @{code="GT-CONTRACT";  name="Contract";                                     acronym=$null;    parentCode=$null;      domainCode="DOM-REVCON"; def="A revenue agreement binding a customer to a recurring product. Carries auto_renew start_date end_date and monthly_amount."; url="https://www.enercare.ca/about/governance/glossary#contract"}
    @{code="GT-AUTORENEW"; name="Auto-Renewal";                                 acronym=$null;    parentCode="GT-CONTRACT"; domainCode="DOM-REVCON"; def="The contract clause that extends the agreement at term end absent customer cancellation. Subject to Ontario Consumer Protection Act disclosure requirements."; url="https://www.ontario.ca/laws/statute/02c30"}
    @{code="GT-MRR";       name="Monthly Recurring Revenue";                    acronym="MRR";    parentCode=$null;      domainCode="DOM-REVCON"; def="Sum of monthly_amount across all active contracts at a given month boundary. Primary revenue metric for forecast and board reporting."; url="https://www.enercare.ca/about/governance/kpi#mrr"}
    @{code="GT-ARR";       name="Annual Recurring Revenue";                     acronym="ARR";    parentCode="GT-MRR";    domainCode="DOM-REVCON"; def="Monthly Recurring Revenue multiplied by 12."; url="https://www.enercare.ca/about/governance/kpi#arr"}
    @{code="GT-CHURN";     name="Churn Rate";                                   acronym=$null;    parentCode=$null;      domainCode="DOM-REVCON"; def="Contract cancellations in a period divided by active contracts at the start of the period. Reported as monthly customer churn and revenue churn."; url="https://www.enercare.ca/about/governance/kpi#churn"}
    @{code="GT-NETREV";    name="Net Revenue";                                  acronym=$null;    parentCode=$null;      domainCode="DOM-REVCON"; def="Billed revenue minus refunds credits and tax amounts. The revenue line used for management reporting."; url="https://www.enercare.ca/about/governance/kpi#net-revenue"}
    @{code="GT-BILLCYCLE"; name="Billing Cycle";                               acronym=$null;    parentCode=$null;      domainCode="DOM-REVCON"; def="The repeating period over which billing transactions are aggregated for a contract. Aligned to billing_frequency on the product record."; url="https://www.enercare.ca/about/governance/glossary#billing-cycle"}
    @{code="GT-OEB";       name="Ontario Energy Board";                        acronym="OEB";    parentCode=$null;      domainCode="DOM-REVCON"; def="The regulator overseeing sub-metering distribution and utility-billing conduct in Ontario. Has reporting obligations for billing-conduct complaints."; url="https://www.oeb.ca/"}
    @{code="GT-OCPA";      name="Ontario Consumer Protection Act";             acronym="OCPA";   parentCode=$null;      domainCode="DOM-REVCON"; def="The provincial law governing residential contract auto-renewal disclosure and cancellation rights. Reportable violations carry a regulator_case_ref."; url="https://www.ontario.ca/laws/statute/02c30"}
    @{code="GT-PCISCOPE";  name="PCI Scope";                                   acronym="PCI";    parentCode=$null;      domainCode="DOM-REVCON"; def="Any object that stores transmits or processes primary account number data. PAN partials such as card_pan_last_4 remain in scope and carry handling restrictions."; url="https://www.pcisecuritystandards.org/pci_security/"}
    @{code="GT-SIN";       name="Social Insurance Number";                     acronym="SIN";    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="The 9-digit Canadian government identifier issued to working residents. Highly Confidential when stored in full; partial last-4 is Confidential."; url="https://www.canada.ca/en/employment-social-development/services/sin.html"}
    @{code="GT-PII";       name="Personally Identifiable Information";         acronym="PII";    parentCode=$null;      domainCode="DOM-CUSTOPS"; def="Any data point that alone or in combination can identify a natural person. Includes name email phone DOB SIN address."; url=$null}
    @{code="GT-GEOPII";    name="Geographic PII";                             acronym=$null;    parentCode="GT-PII";    domainCode="DOM-CUSTOPS"; def="Location data that identifies a person's residence or workplace. Coordinates beyond FSA precision are Confidential."; url="https://www.priv.gc.ca/en/privacy-topics/technology/online-privacy-tracking-cookies/geolocation/"}
    @{code="GT-DSAR";      name="Data Subject Access Request";                acronym="DSAR";   parentCode=$null;      domainCode="DOM-CUSTOPS"; def="A formal customer request to receive or delete personal data held by Enercare. PIPEDA mandates response within thirty calendar days."; url="https://www.priv.gc.ca/en/privacy-topics/access-to-personal-information/02_05_d_27/"}
)

$results = @()
$idMap = @{}

# Step 1: delete the existing bare "Account" term so it can be recreated with full metadata
try {
    $existing = Invoke-RestMethod -Uri "$base/terms" -Headers $headers -Method GET
    $existingAccount = $existing.value | Where-Object { $_.name -eq "Account" }
    foreach ($ea in $existingAccount) {
        if ($ea.status -eq "Published") {
            $patchBody = @{ name = "Account"; domain = $ea.domain; status = "Draft" } | ConvertTo-Json
            Invoke-RestMethod -Uri "$base/terms/$($ea.id)" -Headers $headers -Method PATCH -Body $patchBody | Out-Null
        }
        Invoke-RestMethod -Uri "$base/terms/$($ea.id)" -Headers $headers -Method DELETE | Out-Null
        $results += "DELETED existing Account term $($ea.id)"
    }
} catch {
    $results += "DELETE-EXISTING-ACCOUNT-ERROR: $($_.ErrorDetails.Message)"
}

# Step 2: create all terms with no parent dependency (pass 1), then children (pass 2)
$pass1 = $terms | Where-Object { -not $_.parentCode }
$pass2 = $terms | Where-Object { $_.parentCode }

foreach ($t in $pass1) {
    $body = @{
        name = $t.name
        domain = $domainMap[$t.domainCode]
        status = "Published"
        description = "<div>$($t.def)</div>"
        contacts = @{ owner = @(@{ id = $ownerId; description = "Owner" }) }
    }
    if ($t.acronym) { $body.acronyms = @($t.acronym) }
    if ($t.url) { $body.resources = @(@{ name = "Reference"; url = $t.url }) }
    $jsonBody = $body | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-RestMethod -Uri "$base/terms" -Headers $headers -Method POST -Body $jsonBody
        $idMap[$t.code] = $resp.id
        $results += "CREATED $($t.code) -> $($resp.id)"
    } catch {
        $results += "ERROR creating $($t.code): $($_.ErrorDetails.Message)"
    }
}

foreach ($t in $pass2) {
    $parentId = $idMap[$t.parentCode]
    $body = @{
        name = $t.name
        domain = $domainMap[$t.domainCode]
        status = "Published"
        description = "<div>$($t.def)</div>"
        contacts = @{ owner = @(@{ id = $ownerId; description = "Owner" }) }
    }
    if ($parentId) { $body.parentId = $parentId }
    if ($t.acronym) { $body.acronyms = @($t.acronym) }
    if ($t.url) { $body.resources = @(@{ name = "Reference"; url = $t.url }) }
    $jsonBody = $body | ConvertTo-Json -Depth 10
    try {
        $resp = Invoke-RestMethod -Uri "$base/terms" -Headers $headers -Method POST -Body $jsonBody
        $idMap[$t.code] = $resp.id
        $results += "CREATED $($t.code) -> $($resp.id) (parent=$($t.parentCode)/$parentId)"
    } catch {
        $results += "ERROR creating $($t.code): $($_.ErrorDetails.Message)"
    }
}

$output = @{
    results = $results
    idMap = $idMap
}
$output | ConvertTo-Json -Depth 10 | Out-File -FilePath "$PSScriptRoot\_tmp_glossary_terms_result.json" -Encoding utf8
"DONE - wrote $PSScriptRoot\_tmp_glossary_terms_result.json"
