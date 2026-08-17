/*
================================================================================
Purpose:
  Surgical backfill for a confirmed regression: governance_domain_stewards
  (governance_domains), stewards (governance_data_products), and steward_upn
  (governance_cdes) were found entirely NULL on the live sub2 source on
  2026-08-17, despite sql/07_seed_purview_metadata.sql already declaring the
  correct values (matching the original 2026-08-08 fix documented in
  docs/design-gap-analysis.md G10). All other columns (status, owners, etc.)
  were confirmed intact -- only these 3 steward columns had reverted to NULL.

  This script updates ONLY the steward columns, keyed by the existing primary
  identifier, rather than re-running the full DELETE+INSERT seed (07_seed_
  purview_metadata.sql also reseeds governance_cdes/governance_glossary_terms,
  which can carry live governance-gate approval state on top of the base seed
  -- a full reseed risks wiping that). Safe to re-run (idempotent UPDATEs).
================================================================================
*/

SET NOCOUNT ON;
GO

UPDATE dbo.governance_domains SET governance_domain_stewards = 'Rupal.Solanki@enercare.ca' WHERE domain_id = 'DOM-CUSTOPS';
UPDATE dbo.governance_domains SET governance_domain_stewards = 'Shruthi.Srinivas@enercare.ca' WHERE domain_id = 'DOM-SVCDEL';
UPDATE dbo.governance_domains SET governance_domain_stewards = 'Ci.Zhu@enercare.ca' WHERE domain_id = 'DOM-REVCON';
GO

UPDATE dbo.governance_data_products SET stewards = 'Rupal.Solanki@enercare.ca' WHERE data_product_id = 'DP-CUST360';
UPDATE dbo.governance_data_products SET stewards = 'Shruthi.Srinivas@enercare.ca' WHERE data_product_id = 'DP-SVCPERF';
UPDATE dbo.governance_data_products SET stewards = 'Ci.Zhu@enercare.ca' WHERE data_product_id = 'DP-BILLHEALTH';
GO

UPDATE dbo.governance_cdes SET steward_upn = 'Rupal.Solanki@enercare.ca' WHERE cde_id = 'CDE-CUST-ID';
UPDATE dbo.governance_cdes SET steward_upn = 'Shruthi.Srinivas@enercare.ca' WHERE cde_id = 'CDE-SVCACCT-ID';
UPDATE dbo.governance_cdes SET steward_upn = 'Ci.Zhu@enercare.ca' WHERE cde_id = 'CDE-CONTRACT-ID';
UPDATE dbo.governance_cdes SET steward_upn = 'Shruthi.Srinivas@enercare.ca' WHERE cde_id = 'CDE-REQ-ID';
UPDATE dbo.governance_cdes SET steward_upn = 'Rupal.Solanki@enercare.ca' WHERE cde_id = 'CDE-CONSENT-STATUS';
UPDATE dbo.governance_cdes SET steward_upn = 'Rupal.Solanki@enercare.ca' WHERE cde_id = 'CDE-SIN';
UPDATE dbo.governance_cdes SET steward_upn = 'Rupal.Solanki@enercare.ca' WHERE cde_id = 'CDE-DOB';
UPDATE dbo.governance_cdes SET steward_upn = 'Shruthi.Srinivas@enercare.ca' WHERE cde_id = 'CDE-GEO';
UPDATE dbo.governance_cdes SET steward_upn = 'Ci.Zhu@enercare.ca' WHERE cde_id = 'CDE-PAN-LAST4';
UPDATE dbo.governance_cdes SET steward_upn = 'Ci.Zhu@enercare.ca' WHERE cde_id = 'CDE-BANK-LAST4';
UPDATE dbo.governance_cdes SET steward_upn = 'Rupal.Solanki@enercare.ca' WHERE cde_id = 'CDE-OWNER-UPN';
UPDATE dbo.governance_cdes SET steward_upn = 'Rupal.Solanki@enercare.ca' WHERE cde_id = 'CDE-AUDIT-PURPOSE';
GO

/* ------------------------------------------------------------------------------
   Verification
------------------------------------------------------------------------------ */
SELECT 'governance_domains' AS [table_name], COUNT(*) AS [null_stewards]
FROM dbo.governance_domains WHERE governance_domain_stewards IS NULL
UNION ALL
SELECT 'governance_data_products', COUNT(*) FROM dbo.governance_data_products WHERE stewards IS NULL
UNION ALL
SELECT 'governance_cdes', COUNT(*) FROM dbo.governance_cdes WHERE steward_upn IS NULL;
GO

PRINT 'Steward column backfill complete.';
GO
