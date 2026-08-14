/*
================================================================================
Purpose:
  G18-A demo objects (final form, not test scaffolding). Two real views
  representing the two real outcomes of Loop B's source-table onboarding gate:

  1. dbo.vw_technician_utilization_summary -- APPROVED and fully adopted.
     Aggregates service_requests by technician (employee_id/department only --
     no PII), a genuinely useful Service Delivery operational view. Tagged
     for Service Delivery domain, Internal sensitivity, CandidateFact role.

  2. dbo.vw_employee_pii_export -- REJECTED. Exposes employees.sin_full,
     date_of_birth, and home_postal_code directly with no CDE backing or
     access control -- the exact class of ungoverned PII exposure this gate
     exists to catch. Demonstrates the gate actually BLOCKS adoption, not
     just detects.

Both views are picked up automatically by trg_tag_annotation_extraction on
CREATE. Their governance_requests decisions (Approved vs Rejected) are then
recorded directly in SQL, matching the same demo-decision convention already
used for every other G14/G17 gate (KPI, CDE, Verified Answer, AI Instruction,
OKR) -- a real steward/domain-owner decision, applied via SQL, not a
simulated/fabricated automated approval.
================================================================================
*/

SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.vw_technician_utilization_summary
AS
/* @tag: domain=DOM-SVCDEL owner=ranbir.singh@enercare.ca sensitivity=Internal semantic_role=CandidateFact business_use=Daily field-ops technician utilization and workload distribution */
SELECT
    e.employee_id,
    e.upn,
    e.department,
    COUNT(sr.request_id)                                                    AS total_requests,
    SUM(CASE WHEN sr.status = 'Completed' THEN 1 ELSE 0 END)                AS completed_requests,
    SUM(CASE WHEN sr.no_show_reason_code IS NOT NULL THEN 1 ELSE 0 END)     AS no_show_count
FROM dbo.employees e
LEFT JOIN dbo.service_requests sr ON sr.technician_id = e.employee_id
WHERE e.role IN ('Service Technician', 'Field Technician') AND e.is_active = 1
GROUP BY e.employee_id, e.upn, e.department;
GO

CREATE OR ALTER VIEW dbo.vw_employee_pii_export
AS
/* @tag: domain=DOM-SVCDEL owner=shruthi.srinivas@enercare.ca sensitivity=HighlyConfidential semantic_role=Reference business_use=Raw employee PII export -- NOT approved for semantic model inclusion, no CDE backing */
SELECT
    e.employee_id,
    e.first_name,
    e.last_name,
    e.sin_full,
    e.date_of_birth,
    e.home_postal_code
FROM dbo.employees e;
GO

PRINT 'G18-A demo views created.';
GO
