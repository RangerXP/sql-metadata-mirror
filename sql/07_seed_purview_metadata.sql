/*
================================================================================
Purpose:
  Seed synthetic governance metadata into SQL-first source tables for mirror.

Expected output counts:
  - governance_domains: 3
  - governance_data_products: 3
  - governance_glossary_terms: 35
  - governance_cdes: 12
  - governance_role_assignments: 48
  - governance_label_assignments: 9
================================================================================
*/

SET NOCOUNT ON;
GO

/* ------------------------------------------------------------------------------
   1. Domains (3)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_domains;

INSERT INTO dbo.governance_domains
(domain_id, domain_name, domain_type, description, parent_domain, status, governance_domain_owners, governance_domain_creators)
VALUES
('DOM-CUSTOPS', 'Customer Operations', 'Data domain', 'Customer support, consent, complaint, and profile stewardship domain.', NULL, 'Published', 'Victoria.Tan@enercare.ca;Ci.Zhu@enercare.ca', 'Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com'),
('DOM-SVCDEL',  'Service Delivery',    'Data domain', 'Field service scheduling, work-order execution, and SLA governance.', NULL, 'Published', 'ranbir.singh@enercare.ca;Ci.Zhu@enercare.ca', 'Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com'),
('DOM-REVCON',  'Revenue and Contracts','Data domain','Billing, contracts, renewals, and financial governance domain.', NULL, 'Published', 'Ci.Zhu@enercare.ca;ranbir.singh@enercare.ca', 'Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com');
GO

/* ------------------------------------------------------------------------------
   2. Data products (3)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_data_products;

INSERT INTO dbo.governance_data_products
(data_product_id, data_product_name, product_type, business_use_case, audience, owners, attached_assets, access_policy, status, parent_domain_id)
VALUES
('DP-CUST360', 'Customer 360', 'Master and reference data', 'Single customer profile and consent posture for call-center and compliance operations.', 'Call Center;Privacy;Leadership', 'Victoria.Tan@enercare.ca', 'dbo.customers;dbo.customer_consents;BrookfieldEnercare/dim_customer', 'Role-based access with privacy approval for regulated attributes.', 'Published', 'DOM-CUSTOPS'),
('DP-SVCPERF', 'Service Performance', 'Dataset', 'Track service request performance, technician throughput, and SLA adherence.', 'Field Operations;Leadership', 'ranbir.singh@enercare.ca', 'dbo.service_requests;dbo.service_accounts;dbo.service_zones;BrookfieldEnercare/fct_service_requests', 'Operational use for service planning and SLA management.', 'Published', 'DOM-SVCDEL'),
('DP-BILLHEALTH', 'Billing Health', 'Dataset', 'Monitor billing accuracy, repeat complaints, and contract renewal outcomes.', 'Finance;Customer Care;Leadership', 'Ci.Zhu@enercare.ca', 'dbo.billing_transactions;dbo.contracts;dbo.customer_complaints;BrookfieldEnercare/fct_billing', 'Access requires finance and governance approval for sensitive fields.', 'Published', 'DOM-REVCON');
GO

/* ------------------------------------------------------------------------------
   3. Glossary terms (35)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_glossary_terms;

INSERT INTO dbo.governance_glossary_terms
(term_code, term_name, acronyms, parent_term_code, domain_code, owner_upn, additional_owners_upn, definition, status, is_cde, industry_origin, resources, bound_assets)
VALUES
('GT-PII', 'Personally Identifiable Information', 'PII', NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca', 'Information that can directly or indirectly identify a customer or employee.', 'Published', 1, 'Canadian Regulatory', 'https://www.priv.gc.ca/en/', 'dbo.customers.customer_id;dbo.customers.email'),
('GT-SIN', 'Social Insurance Number', 'SIN', 'GT-PII', 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca', 'Canadian national identifier requiring highest protection controls.', 'Published', 1, 'Canadian Regulatory', 'https://www.canada.ca/en/employment-social-development/services/sin.html', 'dbo.employees.sin_full;dbo.customers.sin_last_4'),
('GT-GEOPII', 'Geolocation PII', NULL, 'GT-PII', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Victoria.Tan@enercare.ca', 'Latitude and longitude tied to customer service accounts.', 'Published', 1, 'Utility', 'https://www.priv.gc.ca/en/', 'dbo.service_accounts.latitude;dbo.service_accounts.longitude'),
('GT-CONSENT', 'Customer Consent', NULL, NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca', 'Recorded legal basis and status for customer permissions.', 'Published', 1, 'Canadian Regulatory', 'https://laws-lois.justice.gc.ca/eng/acts/P-8.6/', 'dbo.customer_consents'),
('GT-PCISCOPE', 'PCI Scope Data', 'PCI', NULL, 'DOM-REVCON', 'Ci.Zhu@enercare.ca', 'Victoria.Tan@enercare.ca', 'Payment and billing attributes governed under PCI controls.', 'Published', 1, 'Finance', 'https://www.pcisecuritystandards.org/', 'dbo.billing_transactions.card_pan_last_4;dbo.billing_transactions.bank_routing_last_4'),
('GT-SVCREQ', 'Service Request', 'WO', NULL, 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Customer-initiated service work item tracked through completion.', 'Published', 0, 'Service Industry', 'internal://runbooks/service-request', 'dbo.service_requests'),
('GT-FCR', 'First Contact Resolution', 'FCR', NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Rupal.Solanki@enercare.ca', 'Percentage of customer cases resolved on first interaction.', 'Published', 0, 'Service Industry', 'internal://kpi/fcr', 'BrookfieldEnercare/_Measures/FCR'),
('GT-NPS', 'Net Promoter Score', 'NPS', NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca', 'Customer advocacy metric based on promoter and detractor responses.', 'Published', 0, 'Service Industry', 'internal://kpi/nps', 'BrookfieldEnercare/_Measures/NPS'),
('GT-CSAT', 'Customer Satisfaction', 'CSAT', NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca', 'Average post-interaction customer satisfaction score.', 'Published', 0, 'Service Industry', 'internal://kpi/csat', 'BrookfieldEnercare/_Measures/CSAT'),
('GT-AHT', 'Average Handle Time', 'AHT', NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Rupal.Solanki@enercare.ca', 'Average duration to resolve customer interactions.', 'Published', 0, 'Service Industry', 'internal://kpi/aht', 'BrookfieldEnercare/_Measures/AvgHandleTime'),
('GT-REPEATCOMPLAINT', 'Repeat Complaint Rate', NULL, NULL, 'DOM-REVCON', 'Ci.Zhu@enercare.ca', 'Rupal.Solanki@enercare.ca', 'Rate of customers filing more than one complaint in measurement period.', 'Published', 0, 'Service Industry', 'internal://kpi/repeat-complaint', 'BrookfieldEnercare/_Measures/RepeatComplaintRate'),
('GT-CONTRACT', 'Contract', NULL, NULL, 'DOM-REVCON', 'Ci.Zhu@enercare.ca', 'ranbir.singh@enercare.ca', 'Customer agreement defining product entitlements and renewal terms.', 'Published', 0, 'Utility', 'internal://contracts/guide', 'dbo.contracts'),
('GT-AUTORENEW', 'Auto Renewal', NULL, 'GT-CONTRACT', 'DOM-REVCON', 'Ci.Zhu@enercare.ca', 'Victoria.Tan@enercare.ca', 'Automatic contract extension policy and lifecycle state.', 'Published', 0, 'Utility', 'internal://contracts/autorenew', 'dbo.contracts'),
('GT-BILLING', 'Billing Transaction', NULL, NULL, 'DOM-REVCON', 'Ci.Zhu@enercare.ca', 'Rupal.Solanki@enercare.ca', 'Financial ledger transaction linked to customer account and contract.', 'Published', 0, 'Finance', 'internal://billing/standards', 'dbo.billing_transactions'),
('GT-CUSTOMER', 'Customer', NULL, NULL, 'DOM-CUSTOPS', 'Victoria.Tan@enercare.ca', 'Rupal.Solanki@enercare.ca', 'Household or account holder receiving Enercare services.', 'Published', 1, 'Utility', 'internal://customer/model', 'dbo.customers'),
('GT-SVCZONE', 'Service Zone', NULL, NULL, 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Operational territory used for service routing and SLA planning.', 'Published', 0, 'Utility', 'internal://ops/zones', 'dbo.service_zones'),
('GT-EMPLOYEE', 'Employee', NULL, NULL, 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Ci.Zhu@enercare.ca', 'Internal workforce member participating in service or governance workflows.', 'Published', 1, 'Utility', 'internal://hr/data', 'dbo.employees'),
('GT-OWNER', 'Data Owner', NULL, NULL, 'DOM-CUSTOPS', 'Ci.Zhu@enercare.ca', 'Victoria.Tan@enercare.ca', 'Business owner accountable for data quality and use policy.', 'Published', 0, 'Generic', 'internal://governance/roles', 'dbo.data_owners_directory'),
('GT-AUDIT', 'Data Access Audit', NULL, NULL, 'DOM-CUSTOPS', 'Ci.Zhu@enercare.ca', 'Victoria.Tan@enercare.ca', 'Record of data access for compliance and monitoring.', 'Published', 0, 'Canadian Regulatory', 'internal://audit/controls', 'dbo.audit_data_access'),
('GT-EQUIP', 'Equipment', NULL, NULL, 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Installed customer equipment managed by service operations.', 'Published', 0, 'Utility', 'internal://asset/equipment', 'dbo.service_accounts'),
('GT-EQUIP-FURNACE', 'Furnace', 'Furnace', 'GT-EQUIP', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Forced-air heating equipment category for service routing.', 'Published', 0, 'Utility', 'internal://asset/equipment/furnace', 'dbo.service_accounts.equipment_type'),
('GT-EQUIP-AC', 'Air Conditioner', 'AC', 'GT-EQUIP', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Cooling system equipment category.', 'Published', 0, 'Utility', 'internal://asset/equipment/ac', 'dbo.service_accounts.equipment_type'),
('GT-EQUIP-WATERHEATER', 'Water Heater', 'WH', 'GT-EQUIP', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Storage water-heating equipment category.', 'Published', 0, 'Utility', 'internal://asset/equipment/water-heater', 'dbo.service_accounts.equipment_type'),
('GT-EQUIP-HEATPUMP', 'Heat Pump', 'HP', 'GT-EQUIP', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Heat pump equipment category.', 'Published', 0, 'Utility', 'internal://asset/equipment/heat-pump', 'dbo.service_accounts.equipment_type'),
('GT-EQUIP-HRV', 'Heat Recovery Ventilator', 'HRV', 'GT-EQUIP', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Ventilation equipment category.', 'Published', 0, 'Utility', 'internal://asset/equipment/hrv', 'dbo.service_accounts.equipment_type'),
('GT-EQUIP-TANKLESS', 'Tankless Water Heater', 'Tankless', 'GT-EQUIP', 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Shruthi.Srinivas@enercare.ca', 'Tankless hot water equipment category.', 'Published', 0, 'Utility', 'internal://asset/equipment/tankless', 'dbo.service_accounts.equipment_type');

;WITH n AS (
    SELECT TOP (9) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn
    FROM sys.objects
)
INSERT INTO dbo.governance_glossary_terms
(term_code, term_name, acronyms, parent_term_code, domain_code, owner_upn, additional_owners_upn, definition, status, is_cde, industry_origin, resources, bound_assets)
SELECT
    CONCAT('GT-AUTO-', RIGHT(CONCAT('00', CAST(rn AS VARCHAR(2))), 2)),
    CONCAT('Synthetic Governance Term ', rn),
    NULL,
    NULL,
    CASE WHEN rn % 3 = 1 THEN 'DOM-CUSTOPS' WHEN rn % 3 = 2 THEN 'DOM-SVCDEL' ELSE 'DOM-REVCON' END,
    'Ci.Zhu@enercare.ca',
    'Victoria.Tan@enercare.ca',
    CONCAT('Synthetic governance term for demo enrichment #', rn, '.'),
    'Published',
    CASE WHEN rn % 4 = 0 THEN 1 ELSE 0 END,
    'Generic',
    'internal://glossary/synthetic',
    'dbo.customers;dbo.service_requests'
FROM n;
GO

/* ------------------------------------------------------------------------------
   4. CDEs (12)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_cdes;

INSERT INTO dbo.governance_cdes
(cde_id, cde_name, expected_data_type, business_definition, owner_role, status, parent_glossary_term, bound_columns)
VALUES
('CDE-CUST-ID', 'Customer Identifier', 'number', 'Unique enterprise identifier for customer entities.', 'Data Steward', 'Published', 'GT-CUSTOMER', 'dbo.customers.customer_id;dbo.service_accounts.customer_id;dbo.contracts.customer_id'),
('CDE-SVCACCT-ID', 'Service Account Identifier', 'number', 'Unique identifier for service account records.', 'Data Steward', 'Published', 'GT-SVCREQ', 'dbo.service_accounts.service_account_id;dbo.service_requests.service_account_id'),
('CDE-CONTRACT-ID', 'Contract Identifier', 'number', 'Unique identifier for customer contracts.', 'Data Steward', 'Published', 'GT-CONTRACT', 'dbo.contracts.contract_id;dbo.billing_transactions.contract_id'),
('CDE-REQ-ID', 'Service Request Identifier', 'number', 'Unique service request key.', 'Data Steward', 'Published', 'GT-SVCREQ', 'dbo.service_requests.request_id'),
('CDE-CONSENT-STATUS', 'Consent Status', 'text', 'Current legal status of customer consent record.', 'Privacy Officer', 'Published', 'GT-CONSENT', 'dbo.customer_consents.consent_status'),
('CDE-SIN', 'Social Insurance Number', 'text', 'Canadian SIN full or partial representation.', 'Privacy Officer', 'Published', 'GT-SIN', 'dbo.employees.sin_full;dbo.customers.sin_last_4'),
('CDE-DOB', 'Date Of Birth', 'date', 'Customer date of birth for identity and eligibility checks.', 'Privacy Officer', 'Published', 'GT-PII', 'dbo.customers.date_of_birth'),
('CDE-GEO', 'Geo Coordinates', 'text', 'Service account latitude and longitude values.', 'Data Steward', 'Published', 'GT-GEOPII', 'dbo.service_accounts.latitude;dbo.service_accounts.longitude'),
('CDE-PAN-LAST4', 'Card PAN Last 4', 'text', 'Last four digits of payment card number.', 'Finance Steward', 'Published', 'GT-PCISCOPE', 'dbo.billing_transactions.card_pan_last_4'),
('CDE-BANK-LAST4', 'Bank Routing Last 4', 'text', 'Last four digits of bank routing details.', 'Finance Steward', 'Published', 'GT-PCISCOPE', 'dbo.billing_transactions.bank_routing_last_4'),
('CDE-OWNER-UPN', 'Data Owner UPN', 'text', 'UPN of assigned data owner for governed object.', 'Data Governance Admin', 'Published', 'GT-OWNER', 'dbo.data_owners_directory.data_owner_upn;dbo.data_owners_directory.data_steward_upn'),
('CDE-AUDIT-PURPOSE', 'Audit Purpose Of Use', 'text', 'Declared purpose for data access event.', 'Data Governance Admin', 'Published', 'GT-AUDIT', 'dbo.audit_data_access.purpose_of_use');
GO

/* ------------------------------------------------------------------------------
   5. Role assignments (48)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_role_assignments;

;WITH roles AS (
    SELECT * FROM (VALUES
      ('R001','Ci.Zhu@enercare.ca','Ci Zhu','Data Governance Administrator','Tenant','Tenant','Tenant'),
      ('R002','Alison.Pouw@microsoft.com','Alison Pouw','Governance Domain Creator','Tenant','Tenant','Tenant'),
      ('R003','Victoria.Tan@enercare.ca','Victoria Tan','Governance Domain Owner','DOM-CUSTOPS','Domain','Domain'),
      ('R004','Ci.Zhu@enercare.ca','Ci Zhu','Governance Domain Owner','DOM-CUSTOPS','Domain','Domain'),
      ('R005','ranbir.singh@enercare.ca','Ranbir Singh','Governance Domain Owner','DOM-SVCDEL','Domain','Domain'),
      ('R006','Ci.Zhu@enercare.ca','Ci Zhu','Governance Domain Owner','DOM-SVCDEL','Domain','Domain'),
      ('R007','Ci.Zhu@enercare.ca','Ci Zhu','Governance Domain Owner','DOM-REVCON','Domain','Domain'),
      ('R008','ranbir.singh@enercare.ca','Ranbir Singh','Governance Domain Owner','DOM-REVCON','Domain','Domain'),
      ('R009','Victoria.Tan@enercare.ca','Victoria Tan','Data Product Owner','DP-CUST360','DataProduct','Data Product'),
      ('R010','ranbir.singh@enercare.ca','Ranbir Singh','Data Product Owner','DP-SVCPERF','DataProduct','Data Product'),
      ('R011','Ci.Zhu@enercare.ca','Ci Zhu','Data Product Owner','DP-BILLHEALTH','DataProduct','Data Product'),
      ('R012','Rupal.Solanki@enercare.ca','Rupal Solanki','Data Steward','DOM-CUSTOPS','Domain','Domain')
    ) v(role_id, principal_email, principal_display_name, role_type, scope_target, scope_target_type, governance_layer)
), filler AS (
    SELECT TOP (36)
        ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn
    FROM sys.objects a
)
INSERT INTO dbo.governance_role_assignments
(role_id, principal_email, principal_display_name, role_type, scope_target, scope_target_type, governance_layer)
SELECT role_id, principal_email, principal_display_name, role_type, scope_target, scope_target_type, governance_layer
FROM roles
UNION ALL
SELECT
    CONCAT('R', RIGHT(CONCAT('000', CAST(12 + rn AS VARCHAR(3))), 3)) AS role_id,
    CASE rn % 6
        WHEN 1 THEN 'Shruthi.Srinivas@enercare.ca'
        WHEN 2 THEN 'Rupal.Solanki@enercare.ca'
        WHEN 3 THEN 'Victoria.Tan@enercare.ca'
        WHEN 4 THEN 'ranbir.singh@enercare.ca'
        WHEN 5 THEN 'Ci.Zhu@enercare.ca'
        ELSE 'seankelley@microsoft.com'
    END AS principal_email,
    CONCAT('Synthetic Principal ', rn) AS principal_display_name,
    CASE rn % 5
        WHEN 1 THEN 'Global Catalog Reader'
        WHEN 2 THEN 'Data Reader'
        WHEN 3 THEN 'Data Steward'
        WHEN 4 THEN 'Information Protection Admin'
        ELSE 'Data Product Contributor'
    END AS role_type,
    CASE rn % 4
        WHEN 1 THEN 'DOM-CUSTOPS'
        WHEN 2 THEN 'DOM-SVCDEL'
        WHEN 3 THEN 'DOM-REVCON'
        ELSE 'Enercare'
    END AS scope_target,
    CASE WHEN rn % 4 = 0 THEN 'Collection' ELSE 'Domain' END AS scope_target_type,
    CASE WHEN rn % 7 = 0 THEN 'Tenant' ELSE 'Domain' END AS governance_layer
FROM filler;
GO

/* ------------------------------------------------------------------------------
   6. Label assignments (9)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_label_assignments;

INSERT INTO dbo.governance_label_assignments
(label_id, label_name, sensitivity_tier, protection_policy, applies_to_asset_ids, scope)
VALUES
('LBL-001','General','General','No encryption; broad internal collaboration.','DP-CUST360:overview;DP-SVCPERF:overview;DP-BILLHEALTH:overview','Tenant'),
('LBL-002','Internal','Internal','Internal users only; no external sharing.','dbo.customers;dbo.service_requests;BrookfieldEnercare.Report','Tenant'),
('LBL-003','Confidential','Confidential','Restricted to approved support and leadership users.','dbo.customer_consents;dbo.customer_complaints;BrookfieldEnercare.SemanticModel','Tenant'),
('LBL-004','Highly Confidential','Highly Confidential','Explicit approval required; privacy and governance controls enforced.','dbo.employees.sin_full;dbo.customers.sin_last_4;dbo.billing_transactions.card_pan_last_4','Tenant'),
('LBL-005','PCI Restricted','Highly Confidential','PCI scoped data only; finance and compliance approval required.','dbo.billing_transactions.card_pan_last_4;dbo.billing_transactions.bank_routing_last_4','Tenant'),
('LBL-006','Privacy Restricted','Highly Confidential','Privacy office approval required for PII and SIN assets.','dbo.customers.date_of_birth;dbo.customers.sin_last_4;dbo.employees.sin_full','Tenant'),
('LBL-007','Operations Sensitive','Confidential','Service operations only; domain owner approval required.','dbo.service_accounts.latitude;dbo.service_accounts.longitude;dbo.service_zones','Tenant'),
('LBL-008','Executive KPI','Internal','Executive KPI consumption with certified semantic layer only.','BrookfieldEnercare/_Measures/NPS;BrookfieldEnercare/_Measures/CSAT;BrookfieldEnercare/_Measures/AvgHandleTime','Tenant'),
('LBL-009','Governance Admin','Confidential','Governance team only for policy authoring and audit controls.','dbo.data_owners_directory;dbo.audit_data_access;lh_metadata.metadata.sm_annotations','Tenant');
GO

/* ------------------------------------------------------------------------------
   7. Verification
------------------------------------------------------------------------------ */
SELECT 'governance_domains' AS [table_name], COUNT(*) AS [row_count] FROM dbo.governance_domains
UNION ALL SELECT 'governance_data_products', COUNT(*) FROM dbo.governance_data_products
UNION ALL SELECT 'governance_glossary_terms', COUNT(*) FROM dbo.governance_glossary_terms
UNION ALL SELECT 'governance_cdes', COUNT(*) FROM dbo.governance_cdes
UNION ALL SELECT 'governance_role_assignments', COUNT(*) FROM dbo.governance_role_assignments
UNION ALL SELECT 'governance_label_assignments', COUNT(*) FROM dbo.governance_label_assignments;
GO

PRINT 'Purview SQL-first metadata seed complete.';
GO
