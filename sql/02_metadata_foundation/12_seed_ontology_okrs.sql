/*
================================================================================
Purpose:
  Seed the 3 Enercare business-objective OKRs (one per governance domain),
  their key results (tied to real kpi_metadata KPICodes / measure asset refs
  from 02_build_metadata_foundation), and their links to the existing 3
  data products. Closes G11-1's business-objective layer.

Expected output counts:
  - governance_okrs: 3
  - governance_okr_key_results: 5
  - governance_okr_data_products: 3
================================================================================
*/

SET NOCOUNT ON;
GO

/* ------------------------------------------------------------------------------
   1. OKRs (3, one per domain)
------------------------------------------------------------------------------ */
DELETE FROM dbo.governance_okr_key_results;
DELETE FROM dbo.governance_okr_data_products;
DELETE FROM dbo.governance_okrs;

INSERT INTO dbo.governance_okrs
(okr_id, okr_name, domain_id, definition, owner_upn, target_date, status)
VALUES
('OKR-SVCDEL-SLA',    'Protect SLA Attainment In Field Service Delivery', 'DOM-SVCDEL',  'Hold SLA breach exposure at or below target across all service-request queues, closing the auto-suppression dispatch gap surfaced in Act 2 of the Maria northstar scenario.', 'ranbir.singh@enercare.ca', '2026-12-31', 'Published'),
('OKR-CUSTOPS-CX',    'Improve Call-Center Customer Experience',          'DOM-CUSTOPS', 'Raise first-contact resolution and customer satisfaction for call-center interactions to their certified target thresholds.', 'Victoria.Tan@enercare.ca', '2026-12-31', 'Published'),
('OKR-REVCON-RETAIN', 'Protect Renewal Revenue And Reduce Repeat Billing Complaints', 'DOM-REVCON', 'Sustain protection-plan renewal rate at target while reducing the rate of customers filing more than one billing complaint per period.', 'Ci.Zhu@enercare.ca', '2026-12-31', 'Published');
GO

/* ------------------------------------------------------------------------------
   2. Key results (5) - metric_source ties to kpi_metadata.KPICode
      (02_build_metadata_foundation) or a
      BrookfieldEnercare/_Measures/<name> asset ref where no KPICode exists yet.
      goal/max amounts match the certified thresholds documented in
      02_build_metadata_foundation's
      AI Data Schema (FCR 78%, CSAT 4.2/5, PP_RNW_RATE 82%, SLA_BRCH_RATE 5%).
------------------------------------------------------------------------------ */
-- NOTE: progress_amount must NEVER be seeded as NULL. An all-NULL column across
-- every row causes Spark to infer NullType when 02_build_metadata_foundation converts this table to a
-- pandas/Spark DataFrame, which Delta then declares in the schema but does not
-- physically materialize in the Parquet files -- an identical failure class to
-- the historical domains.parent_domain issue. This breaks 05_publish_governance_domains's column-pruned
-- .collect() with "Couldn't find progress_amount#... in [...]" even though the
-- column is listed in df.columns. Always seed a real numeric value.
INSERT INTO dbo.governance_okr_key_results
(key_result_id, okr_id, result_name, metric_source, goal_amount, progress_amount, max_amount, progress_status)
VALUES
('KR-SLA-BREACH',      'OKR-SVCDEL-SLA',    'SLA Breach Rate At Or Below Target',        'kpi_metadata.SLA_BRCH_RATE', 5.00,  3.80, 100.00, 'OnTrack'),
('KR-FCR-RATE',        'OKR-CUSTOPS-CX',    'First Contact Resolution At Or Above Target','kpi_metadata.FCR',           78.00, 81.50, 100.00, 'OnTrack'),
('KR-CSAT-SCORE',      'OKR-CUSTOPS-CX',    'Customer Satisfaction At Or Above Target',   'kpi_metadata.CSAT',          4.20,  4.35, 5.00,   'OnTrack'),
('KR-PP-RENEWAL',      'OKR-REVCON-RETAIN', 'Protection Plan Renewal Rate At Or Above Target','kpi_metadata.PP_RNW_RATE', 82.00, 84.00, 100.00, 'OnTrack'),
('KR-REPEAT-COMPLAINT','OKR-REVCON-RETAIN', 'Repeat Billing Complaint Rate Reduced',      'BrookfieldEnercare/_Measures/RepeatComplaintRate', 10.00, 14.50, 100.00, 'AtRisk');
GO

/* ------------------------------------------------------------------------------
   3. OKR -> Data Product links (3) - Purview's native "related data products"
      relationship on OKRs.
------------------------------------------------------------------------------ */
INSERT INTO dbo.governance_okr_data_products
(okr_id, data_product_id)
VALUES
('OKR-SVCDEL-SLA',    'DP-SVCPERF'),
('OKR-CUSTOPS-CX',    'DP-CUST360'),
('OKR-REVCON-RETAIN', 'DP-BILLHEALTH');
GO

SELECT 'governance_okrs' AS t, COUNT(*) AS actual, 3 AS expected FROM dbo.governance_okrs
UNION ALL SELECT 'governance_okr_key_results', COUNT(*), 5 FROM dbo.governance_okr_key_results
UNION ALL SELECT 'governance_okr_data_products', COUNT(*), 3 FROM dbo.governance_okr_data_products
ORDER BY t;
GO
