/*
================================================================================
Purpose:
  G19-4 -- AI Instruction lifecycle completeness: effective-date activation and
  rollback. Uses the SAME existing gate (dbo.governance_change_requests + nb_11's
  apply-step dispatcher) that GCR-AII-001 already proved for AI Instructions --
  not a new/parallel workflow.

Scenarios:
  1. GCR-AII-002 -- a NEW instruction ("Winter Weather Delay Communication",
     TriggerText='weather_delay') certified with a FUTURE EffectiveDate (14 days
     out, simulating a seasonal policy that shouldn't take effect until the
     winter service window opens). Requested by Shruthi Srinivas, approved by
     Ci Zhu (same pairing as every other Phase 4 gate).
  2. GCR-AII-003 -- a flawed edit to the EXISTING "escalation" instruction
     (GCR-AII-001) that removes the safety/emergency escalation clause --
     a real governance risk if left uncaught. Requested by Shruthi Srinivas
     (Service Delivery efficiency framing), mistakenly approved by Ci Zhu.
  3. GCR-AII-004 -- the rollback: Ranbir Singh catches the missing safety
     clause and requests reverting "escalation" to its prior certified text;
     approved by Ci Zhu. nb_11's apply_ai_instruction_rollback dynamically
     resolves the currently-active certified row for TriggerText='escalation'
     (GCR-AII-003's applied row) and the version immediately before it
     (GCR-AII-001's original row) -- no hardcoded RecordID needed.

  approved_at is staggered (003 before 004) so nb_11's ORDER BY approved_at
  processes the bad edit before the rollback in the same run.

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

-- 1) Extend the request_type CHECK constraint to allow AI_INSTRUCTION_ROLLBACK.
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
            'GLOSSARY_TERM_DEFINITION', 'AI_INSTRUCTION_CERTIFICATION', 'AI_INSTRUCTION_ROLLBACK'
        )
    );
GO

PRINT 'CK_gcr_request_type extended to allow AI_INSTRUCTION_ROLLBACK.';
GO

-- 2) GCR-AII-002: new instruction, future EffectiveDate.
IF NOT EXISTS (SELECT 1 FROM dbo.governance_change_requests WHERE request_id = 'GCR-AII-002')
BEGIN
    DECLARE @effective_date VARCHAR(10) = CONVERT(VARCHAR(10), DATEADD(DAY, 14, SYSUTCDATETIME()), 23);
    DECLARE @payload_002 NVARCHAR(MAX) = (
        SELECT 'ai_instruction' AS RecordType, 'weather_delay' AS TriggerText,
               'When a customer asks about a delayed technician visit during declared winter weather advisories, acknowledge the safety-driven schedule impact, confirm the new estimated arrival window from the dispatch system, and offer to notify them proactively if it shifts again. Do not commit to a specific time until dispatch confirms it.' AS ResponseText,
               CAST(NULL AS VARCHAR(64)) AS LinkedKPICode,
               @effective_date AS EffectiveDate
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
    );

    INSERT INTO dbo.governance_change_requests (
        request_id, request_type, domain_id, target_object_id, target_object_label,
        change_summary, proposed_payload, previous_payload, requested_by_upn,
        requested_at, status
    )
    VALUES (
        'GCR-AII-002', 'AI_INSTRUCTION_CERTIFICATION', NULL, NULL,
        'Winter Weather Delay Communication (AI Instruction, future-effective)',
        'New seasonal AI instruction guiding Copilot/Data Agent on weather-delay communication -- deliberately not effective until the winter service window opens.',
        @payload_002, NULL, 'shruthi.srinivas@MngEnvMCAP660444.onmicrosoft.com', SYSUTCDATETIME(), 'PendingApproval'
    );
    PRINT 'Seeded GCR-AII-002 as PendingApproval.';
END
ELSE
    PRINT 'GCR-AII-002 already exists -- seed skipped.';
GO

UPDATE dbo.governance_change_requests
SET status = 'Approved', approver_upn = 'ci.zhu@MngEnvMCAP660444.onmicrosoft.com', approved_at = DATEADD(SECOND, 1, SYSUTCDATETIME())
WHERE request_id = 'GCR-AII-002' AND status = 'PendingApproval';
PRINT 'GCR-AII-002 approval applied: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

-- 3) GCR-AII-003: flawed edit to "escalation" -- removes the safety/emergency clause.
IF NOT EXISTS (SELECT 1 FROM dbo.governance_change_requests WHERE request_id = 'GCR-AII-003')
BEGIN
    DECLARE @payload_003 NVARCHAR(MAX) = (
        SELECT 'ai_instruction' AS RecordType, 'escalation' AS TriggerText,
               'Escalate to a human supervisor when: the customer explicitly requests a supervisor or manager; a service request has missed its committed SLA window and the customer expresses dissatisfaction; billing dispute exceeds standard credit authority. Do not attempt to resolve these categories with a scripted answer -- acknowledge the concern and hand off.' AS ResponseText,
               CAST(NULL AS VARCHAR(64)) AS LinkedKPICode
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
    );

    INSERT INTO dbo.governance_change_requests (
        request_id, request_type, domain_id, target_object_id, target_object_label,
        change_summary, proposed_payload, previous_payload, requested_by_upn,
        requested_at, status
    )
    VALUES (
        'GCR-AII-003', 'AI_INSTRUCTION_CERTIFICATION', NULL, NULL,
        'Escalation Guidance (AI Instruction, edit -- simplifies criteria for Service Delivery efficiency)',
        'Proposed simplification of escalation criteria. NOTE: this edit unintentionally drops the safety/emergency escalation clause -- see GCR-AII-004 rollback.',
        @payload_003, NULL, 'shruthi.srinivas@MngEnvMCAP660444.onmicrosoft.com', SYSUTCDATETIME(), 'PendingApproval'
    );
    PRINT 'Seeded GCR-AII-003 as PendingApproval.';
END
ELSE
    PRINT 'GCR-AII-003 already exists -- seed skipped.';
GO

UPDATE dbo.governance_change_requests
SET status = 'Approved', approver_upn = 'ci.zhu@MngEnvMCAP660444.onmicrosoft.com', approved_at = DATEADD(SECOND, 2, SYSUTCDATETIME())
WHERE request_id = 'GCR-AII-003' AND status = 'PendingApproval';
PRINT 'GCR-AII-003 approval applied: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

-- 4) GCR-AII-004: rollback of GCR-AII-003 -- Ranbir Singh catches the missing safety clause.
IF NOT EXISTS (SELECT 1 FROM dbo.governance_change_requests WHERE request_id = 'GCR-AII-004')
BEGIN
    DECLARE @payload_004 NVARCHAR(MAX) = (
        SELECT 'ai_instruction' AS RecordType, 'escalation' AS TriggerText,
               'Missing safety/emergency escalation clause (gas smell, no heat in freezing conditions) -- GCR-AII-003''s simplification introduced a real safety-governance risk and must be reverted.' AS RollbackReason
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
    );

    INSERT INTO dbo.governance_change_requests (
        request_id, request_type, domain_id, target_object_id, target_object_label,
        change_summary, proposed_payload, previous_payload, requested_by_upn,
        requested_at, status
    )
    VALUES (
        'GCR-AII-004', 'AI_INSTRUCTION_ROLLBACK', NULL, NULL,
        'Escalation Guidance (AI Instruction, rollback of GCR-AII-003)',
        'Revert "escalation" instruction to its prior certified text -- GCR-AII-003 dropped the safety/emergency clause.',
        @payload_004, NULL, 'ranbir.singh@MngEnvMCAP660444.onmicrosoft.com', SYSUTCDATETIME(), 'PendingApproval'
    );
    PRINT 'Seeded GCR-AII-004 as PendingApproval.';
END
ELSE
    PRINT 'GCR-AII-004 already exists -- seed skipped.';
GO

UPDATE dbo.governance_change_requests
SET status = 'Approved', approver_upn = 'ci.zhu@MngEnvMCAP660444.onmicrosoft.com', approved_at = DATEADD(SECOND, 3, SYSUTCDATETIME())
WHERE request_id = 'GCR-AII-004' AND status = 'PendingApproval';
PRINT 'GCR-AII-004 approval applied: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

PRINT 'G19-4 seed+approve complete -- ready for nb_11 apply-on-approve run (processes 002, then 003, then 004, by approved_at).';
GO
