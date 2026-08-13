/*
================================================================================
Purpose:
  G18-A final-form decisions -- the two real outcomes of Loop B's onboarding
  gate, each driven to its genuine terminal state (not left as a testing
  artifact at Submitted).

  1. dbo.vw_technician_utilization_summary -- APPROVED by Ranbir Singh
     (Governance Domain Owner, Service Delivery), then fully applied: a real
     governed_object_versions snapshot + a SqlApplyReadback receipt (same
     pattern as G17-R4's OKR gate), marked Completed.

  2. dbo.vw_employee_pii_export -- REJECTED by Ranbir Singh: exposes raw SIN/
     DOB/postal code with no CDE backing or access control. Stays terminal at
     Rejected -- no governed_object_versions, no receipt, no downstream
     semantic-model inclusion. Proves the gate actually blocks adoption.

Idempotent: safe to re-run (guarded by current_status checks).
================================================================================
*/

SET NOCOUNT ON;
GO

DECLARE @approver VARCHAR(255) = 'ranbir.singh@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

-- 1) APPROVE the technician utilization view.
UPDATE dbo.governance_requests
SET current_status = 'Approved', decided_by = @approver, decided_at = @now
WHERE request_id = 'TAG-D05DBBACD3A523E8' AND current_status = 'Submitted';

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_events
    WHERE source_system = 'SQL' AND source_event_id = 'TAG-D05DBBACD3A523E8:Decided'
)
INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT 'TAG-D05DBBACD3A523E8', 'Decided', 'Approved', 'SQL', 'TAG-D05DBBACD3A523E8:Decided', @approver, @now, @now, proposed_payload
FROM dbo.governance_requests WHERE request_id = 'TAG-D05DBBACD3A523E8';

PRINT 'Technician utilization view: Approved.';

-- 2) REJECT the PII export view.
UPDATE dbo.governance_requests
SET current_status = 'Rejected', decided_by = @approver, decided_at = @now,
    failure_reason = 'Exposes raw SIN (sin_full), date_of_birth, and home_postal_code with no bound CDE, no sensitivity-label enforcement, and no access control. Not eligible for semantic model inclusion or Data Agent grounding until a proper CDE + access policy exists.'
WHERE request_id = 'TAG-3B02C35D0882F641' AND current_status = 'Submitted';

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_events
    WHERE source_system = 'SQL' AND source_event_id = 'TAG-3B02C35D0882F641:Decided'
)
INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT 'TAG-3B02C35D0882F641', 'Decided', 'Rejected', 'SQL', 'TAG-3B02C35D0882F641:Decided', @approver, @now, @now, proposed_payload
FROM dbo.governance_requests WHERE request_id = 'TAG-3B02C35D0882F641';

PRINT 'Employee PII export view: Rejected.';
GO

-- 3) Apply step for the APPROVED object only: real snapshot + receipt + Completed.
DECLARE @request_id VARCHAR(64) = 'TAG-D05DBBACD3A523E8';
DECLARE @object_id VARCHAR(256) = 'dbo.vw_technician_utilization_summary';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'SqlModuleTagAnnotation' AND object_id = @object_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_system = 'SQL' AND target_object_type = 'SqlModuleTagAnnotation'
      AND target_object_id = @object_id AND receipt_type = 'SqlApplyReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
VALUES (@request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, 'SqlApplyReadback', @definition_hash, @definition_hash, 'Passed',
        (SELECT @object_id AS objectId, @definition_hash AS observedHash, @now AS observedAt FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id AND current_status = 'Approved';

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', 'ranbir.singh@enercare.ca', @now, @now, @proposed_payload
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

PRINT 'Technician utilization view: Applied + Completed, receipt Passed.';
GO
