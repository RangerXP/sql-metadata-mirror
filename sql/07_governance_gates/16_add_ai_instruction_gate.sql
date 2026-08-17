/*
================================================================================
Purpose:
  G17-R3 — Gate AI Instructions (PBI_AI_Instructions / ai_metadata RecordType=
  'ai_instruction') through the same Draft -> PendingApproval -> Approved ->
  Applied gate already proven for KPI/CDE/Verified-Answer/Glossary-Term, using
  the existing dbo.governance_change_requests table and 07_apply_approved_changes's
  apply-step dispatcher (apply_verified_answer_certification is already generic across
  RecordType, so no new handler function is needed -- only a new
  DISPATCH entry, added separately in the notebook).

Scenario:
  New AI instruction "Escalation Guidance" (RecordType='ai_instruction') --
  guidance for when Copilot/the Data Agent should direct a user to escalate to
  a human supervisor rather than continue answering. Requested by Rupal
  Solanki (Data Steward, Customer Operations -- closest existing stakeholder
  to AI-answer-quality concerns), approved by Ci Zhu (constant Phase 4
  approver, same as all 4 prior gates).

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

-- 1) Extend the request_type CHECK constraint to allow AI_INSTRUCTION_CERTIFICATION.
IF EXISTS (
    SELECT 1 FROM sys.check_constraints
    WHERE name = 'CK_gcr_request_type' AND parent_object_id = OBJECT_ID('dbo.governance_change_requests')
)
BEGIN
    ALTER TABLE dbo.governance_change_requests DROP CONSTRAINT CK_gcr_request_type;
END
GO

ALTER TABLE dbo.governance_change_requests WITH CHECK
    ADD CONSTRAINT CK_gcr_request_type CHECK (
        request_type IN (
            'KPI_APPROVAL', 'VERIFIED_ANSWER_CERTIFICATION', 'CDE_CLASSIFICATION',
            'GLOSSARY_TERM_DEFINITION', 'AI_INSTRUCTION_CERTIFICATION'
        )
    );
GO

PRINT 'CK_gcr_request_type extended to allow AI_INSTRUCTION_CERTIFICATION.';
GO

-- 2) Seed the new scenario as PendingApproval (only if not already seeded).
DECLARE @request_id VARCHAR(64) = 'GCR-AII-001';

IF NOT EXISTS (SELECT 1 FROM dbo.governance_change_requests WHERE request_id = @request_id)
BEGIN
    INSERT INTO dbo.governance_change_requests (
        request_id, request_type, domain_id, target_object_id, target_object_label,
        change_summary, proposed_payload, previous_payload, requested_by_upn,
        requested_at, status
    )
    VALUES (
        @request_id,
        'AI_INSTRUCTION_CERTIFICATION',
        NULL,
        NULL,
        'Escalation Guidance (AI Instruction)',
        'New AI instruction guiding Copilot/Data Agent on when to direct a customer to escalate to a human supervisor.',
        N'{
            "RecordType": "ai_instruction",
            "TriggerText": "escalation",
            "ResponseText": "Escalate to a human supervisor when: the customer explicitly requests a supervisor or manager; a service request has missed its committed SLA window and the customer expresses dissatisfaction; billing dispute exceeds standard credit authority; or safety/emergency language is detected (e.g. gas smell, no heat in freezing conditions). Do not attempt to resolve these categories with a scripted answer -- acknowledge the concern and hand off.",
            "LinkedKPICode": null,
            "domain": "DOM-CUSTOPS",
            "owner": "rupal.solanki@MngEnvMCAP660444.onmicrosoft.com",
            "sensitivity": "Internal",
            "semantic_role": "ai_instruction",
            "business_use": "Data Agent escalation guidance"
        }',
        NULL,
        'rupal.solanki@MngEnvMCAP660444.onmicrosoft.com',
        SYSUTCDATETIME(),
        'PendingApproval'
    );
    PRINT 'Seeded ' + @request_id + ' as PendingApproval.';
END
ELSE
BEGIN
    PRINT @request_id + ' already exists -- seed skipped.';
END
GO

-- 3) Approve the scenario (Ci Zhu, constant Phase 4 approver).
DECLARE @request_id VARCHAR(64) = 'GCR-AII-001';

UPDATE dbo.governance_change_requests
SET status = 'Approved', approver_upn = 'ci.zhu@MngEnvMCAP660444.onmicrosoft.com', approved_at = SYSUTCDATETIME()
WHERE request_id = @request_id AND status = 'PendingApproval';

PRINT 'Approval applied: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

PRINT 'G17-R3 seed+approve complete -- ready for 07_apply_approved_changes apply-on-approve run.';
GO
