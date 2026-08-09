/*
================================================================================
Purpose:
  Seed the four Phase 4 gated-change demo scenarios into
  dbo.governance_change_requests, each in status = 'PendingApproval' so the
  live demo can walk the approval step on stage (UPDATE ... SET status =
  'Approved', approver_upn = ..., approved_at = SYSUTCDATETIME()).

  Each scenario maps to one Maria-northstar stakeholder as requester, with
  Ci Zhu (Governance Admin / Glossary co-owner across all 3 domains) as the
  constant approver — mirroring her Act 3 role ("it would mean someone
  edited the semantic-model ... requires my review").

Expected output count:
  - governance_change_requests: 4 (one per gate type)
================================================================================
*/

SET NOCOUNT ON;
GO

DELETE FROM dbo.governance_change_requests
WHERE request_id IN ('GCR-KPI-001', 'GCR-VA-001', 'GCR-CDE-001', 'GCR-GT-001');
GO

/* ------------------------------------------------------------------------------
   1. KPI_APPROVAL — re-certify SLA_BRCH_RATE (v1 -> v2) closing the Maria
      auto-suppression dispatch bug found in Act 2.
      Requested by: Ranbir Singh (Domain Owner DOM-SVCDEL, KPI owner)
      Approved by:  Ci Zhu (Governance Admin)
------------------------------------------------------------------------------ */
INSERT INTO dbo.governance_change_requests
(request_id, request_type, domain_id, target_object_id, target_object_label, change_summary, proposed_payload, previous_payload, requested_by_upn, status)
VALUES
(
    'GCR-KPI-001', 'KPI_APPROVAL', 'DOM-SVCDEL', 'SLA_BRCH_RATE', 'SLA Breach Rate (Field Operations)',
    'Tighten SLA Breach Rate definition to explicitly exclude auto-suppressed technician queue entries from the SLA clock, closing the mis-dispatch pattern found in the Maria Castellanos repeat-complaint investigation (Act 2).',
    N'{"KPICode":"SLA_BRCH_RATE","Version":2,"PreviousFormula":"DIVIDE(CALCULATE(COUNTROWS(fct_sv_service_visits), fct_sv_service_visits[sla_breach_flg] = \"Y\"), COUNTROWS(fct_sv_service_visits))","Description":"Percentage of field service visits where the technician did not arrive within the committed window. SLA windows: emergency=4h, maintenance=scheduled date, repair=next business day. A technician queue entry auto-suppressed by an unrelated SLA-exceeded flag must be released and re-dispatched within 1 hour; failure to do so counts as a breach regardless of the original committed window. Target: 5%.","WarningThreshold":0.08,"CriticalThreshold":0.12}',
    N'{"KPICode":"SLA_BRCH_RATE","Version":1,"WarningThreshold":0.10,"CriticalThreshold":0.15}',
    'ranbir.singh@enercare.ca', 'PendingApproval'
);
GO

/* ------------------------------------------------------------------------------
   2. VERIFIED_ANSWER_CERTIFICATION — SLA credit-policy Q&A drafted from Tom's
      call script (Act 1.3), pending steward QA review before it is certified
      into the Data Agent's verified-answer set.
      Requested by: Rupal Solanki (Data Steward DOM-CUSTOPS)
      Approved by:  Ci Zhu (Governance Admin)
------------------------------------------------------------------------------ */
INSERT INTO dbo.governance_change_requests
(request_id, request_type, domain_id, target_object_id, target_object_label, change_summary, proposed_payload, previous_payload, requested_by_upn, status)
VALUES
(
    'GCR-VA-001', 'VERIFIED_ANSWER_CERTIFICATION', 'DOM-CUSTOPS', NULL, 'SLA credit-policy verified answer',
    'Certify a new verified answer for the Data Agent explaining the no-heat SLA credit policy Tom used on Maria''s call, so future agents get the same governed answer.',
    N'{"RecordType":"verified_answer","TriggerText":"What is our SLA credit policy for a no-heat call during heating season?","ResponseText":"Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a 24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution.","LinkedKPICode":"SLA_BRCH_RATE"}',
    NULL,
    'Rupal.Solanki@enercare.ca', 'PendingApproval'
);
GO

/* ------------------------------------------------------------------------------
   3. CDE_CLASSIFICATION — new CDE-COMPLAINTREF nominated Highly Confidential
      because a repeat/high-severity complaint can auto-generate a
      regulator_case_ref (OEB-reportable), following Tom's complaint log in
      Act 1.4.
      Requested by: Shruthi Srinivas (Data Steward DOM-SVCDEL)
      Approved by:  Ci Zhu (Information Protection Admin)
------------------------------------------------------------------------------ */
INSERT INTO dbo.governance_change_requests
(request_id, request_type, domain_id, target_object_id, target_object_label, change_summary, proposed_payload, previous_payload, requested_by_upn, status)
VALUES
(
    'GCR-CDE-001', 'CDE_CLASSIFICATION', 'DOM-SVCDEL', NULL, 'CDE-COMPLAINTREF (Complaint Reference)',
    'Register a new Critical Data Element for the complaint reference/regulator case reference field, classified Highly Confidential because it can carry an OEB regulator_case_ref.',
    N'{"cde_id":"CDE-COMPLAINTREF","cde_name":"Complaint Reference","expected_data_type":"text","business_definition":"Unique reference for a logged customer complaint; auto-generates a regulator_case_ref when severity/repeat criteria mark it RegulatorReportable under OEB rules.","owner_role":"Data Steward","status":"Highly Confidential","parent_glossary_term":"GT-COMPLAINT","bound_columns":"dbo.customer_complaints.complaint_ref;dbo.customer_complaints.regulator_case_ref"}',
    NULL,
    'Shruthi.Srinivas@enercare.ca', 'PendingApproval'
);
GO

/* ------------------------------------------------------------------------------
   4. GLOSSARY_TERM_DEFINITION — formally publish GT-SLA (referenced
      narratively in the Maria north-star scenario, §1.3, but never actually
      registered), with the exact definition Tom used to resolve Maria's
      credit dispute.
      Requested by: Victoria Tan (Domain Owner DOM-CUSTOPS, drove the Act 2 fix)
      Approved by:  Ci Zhu (Governance Admin)
------------------------------------------------------------------------------ */
INSERT INTO dbo.governance_change_requests
(request_id, request_type, domain_id, target_object_id, target_object_label, change_summary, proposed_payload, previous_payload, requested_by_upn, status)
VALUES
(
    'GCR-GT-001', 'GLOSSARY_TERM_DEFINITION', 'DOM-SVCDEL', NULL, 'GT-SLA (Service Level Agreement)',
    'Publish GT-SLA with an explicit, auditable definition of the no-heat SLA and its credit remedy, closing a gap where the term was used narratively but never registered in the glossary.',
    N'{"term_code":"GT-SLA","term_name":"Service Level Agreement","parent_term_code":null,"domain_code":"DOM-SVCDEL","owner_upn":"ranbir.singh@enercare.ca","additional_owners_upn":"Ci.Zhu@enercare.ca","definition":"Committed service response window by request type and season (e.g., 24-hour no-heat SLA during heating season) with an associated pro-rated daily credit remedy on breach, per the Total Home Protection Plan contract terms.","status":"Published","is_cde":0,"industry_origin":"Service Industry","resources":"internal://sla/policy","bound_assets":"dbo.contracts;dbo.service_requests"}',
    NULL,
    'Victoria.Tan@enercare.ca', 'PendingApproval'
);
GO

PRINT 'Phase 4 gated-change demo scenarios seeded: 4 requests in PendingApproval.';
GO
