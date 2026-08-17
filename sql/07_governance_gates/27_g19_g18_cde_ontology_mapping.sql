/*
================================================================================
Purpose:
  G19-6 (part 1 of 2) -- extend G18-A's discovery->classify->approve chain
  with a CDE mapping step and an ontology mapping step, closing the two
  gaps flagged in G18-A's own findings ("Only CDE mapping and actual
  semantic-model TMDL promotion remain genuinely open").

Scenarios:
  1. CDE mapping: dbo.vw_contract_renewal_pipeline (left genuinely Submitted/
     pending by G18-A -- selects contract_id, product_id, contract_status,
     auto_renew from dbo.contracts) is mapped to the real CDE-CONTRACT-ID
     ("Contract Identifier") -- a genuine fit, not a contrived one. Requested
     by Ci Zhu (Revenue and Contracts domain owner), approved by Ranbir Singh
     (cross-domain governance reviewer, same role he plays in the G19-4
     rollback scenario).
  2. Having a real CDE mapping now justifies finally deciding the pending
     object: TAG-D0BF6E496681E6B0 is APPROVED (Ci Zhu, domain owner) and
     applied -- the same real snapshot+receipt+Completed pattern as G18-A's
     other approved object (sql/07_governance_gates/21_g18a_demo_decisions.sql).
  3. Ontology mapping: dbo.vw_technician_utilization_summary (already
     Approved+Completed via G18-A) is mapped to the real Key Result
     KR-TECH-UTIL ("Technician Utilization Rate At Or Above Target",
     G17-R4) -- the view was literally built to serve this KR's
     metric_source, a genuine existing relationship, not invented for this
     task. Requested by Shruthi Srinivas (the KR's original requester),
     approved by Ci Zhu.

Part 2 (real semantic-model TOM promotion) is a separate step in
09_reconcile_semantic_model, since it requires Spark/SemPy Labs, not T-SQL.

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

------------------------------------------------------------------------------
-- 1) CDE mapping: vw_contract_renewal_pipeline -> CDE-CONTRACT-ID
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'CDEMAP-CONTRACT-RENEWAL-001';
DECLARE @object_id        VARCHAR(256)  = 'dbo.vw_contract_renewal_pipeline';
DECLARE @cde_id           VARCHAR(64)   = 'CDE-CONTRACT-ID';
DECLARE @requested_by     VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'ranbir.singh@enercare.ca';
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @object_id AS sourceObjectId, @cde_id AS cdeId,
           'contract_id column in this view maps directly to the Contract Identifier CDE.' AS mappingRationale
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'SourceObjectCdeMapping', 'SQL', 'SQL', 'SqlModuleTagAnnotation',
    @object_id, 'vw_contract_renewal_pipeline -> CDE-CONTRACT-ID mapping',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'CDEMAP-CONTRACT-RENEWAL-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id VARCHAR(64) = 'CDEMAP-CONTRACT-RENEWAL-001';
DECLARE @object_id VARCHAR(256) = 'dbo.vw_contract_renewal_pipeline';
DECLARE @requested_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'ranbir.singh@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'SqlModuleTagAnnotation' AND object_id = @object_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @object_id AND receipt_type = 'CdeMappingReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, 'CdeMappingReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @object_id AS sourceObjectId, 'CDE-CONTRACT-ID' AS cdeId FROM dbo.governance_cdes WHERE cde_id = 'CDE-CONTRACT-ID' FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'CDEMAP-CONTRACT-RENEWAL-001 applied + receipted.';
GO

------------------------------------------------------------------------------
-- 2) Now that a real CDE mapping justifies it, decide the pending object.
------------------------------------------------------------------------------
DECLARE @request_id VARCHAR(64) = 'TAG-D0BF6E496681E6B0';
DECLARE @object_id VARCHAR(256) = 'dbo.vw_contract_renewal_pipeline';
DECLARE @approver VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

UPDATE dbo.governance_requests
SET current_status = 'Approved', decided_by = @approver, decided_at = @now
WHERE request_id = @request_id AND current_status = 'Submitted';

IF NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided')
INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approver, @now, @now, proposed_payload
FROM dbo.governance_requests WHERE request_id = @request_id;

PRINT 'Contract renewal pipeline view: Approved (CDE-backed).';
GO

DECLARE @request_id VARCHAR(64) = 'TAG-D0BF6E496681E6B0';
DECLARE @object_id VARCHAR(256) = 'dbo.vw_contract_renewal_pipeline';
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
    WHERE request_id = @request_id AND target_object_id = @object_id AND receipt_type = 'SqlApplyReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
VALUES (@request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, 'SqlApplyReadback', @definition_hash, @definition_hash, 'Passed',
        (SELECT @object_id AS objectId, @definition_hash AS observedHash, @now AS observedAt FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id AND current_status = 'Approved';

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', 'Ci.Zhu@enercare.ca', @now, @now, @proposed_payload
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

PRINT 'Contract renewal pipeline view: Applied + Completed, receipt Passed. G18-A''s 3rd demo object now has a real terminal state.';
GO

------------------------------------------------------------------------------
-- 3) Ontology mapping: vw_technician_utilization_summary -> KR-TECH-UTIL
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'ONTOMAP-TECHUTIL-001';
DECLARE @object_id        VARCHAR(256)  = 'dbo.vw_technician_utilization_summary';
DECLARE @key_result_id    VARCHAR(64)   = 'KR-TECH-UTIL';
DECLARE @requested_by     VARCHAR(255)  = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @object_id AS sourceObjectId, @key_result_id AS keyResultId,
           'This view is the real metric_source for KR-TECH-UTIL (Technician Utilization Rate At Or Above Target).' AS mappingRationale
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'SourceObjectOntologyMapping', 'SQL', 'SQL', 'SqlModuleTagAnnotation',
    @object_id, 'vw_technician_utilization_summary -> KR-TECH-UTIL ontology mapping',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'ONTOMAP-TECHUTIL-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id VARCHAR(64) = 'ONTOMAP-TECHUTIL-001';
DECLARE @object_id VARCHAR(256) = 'dbo.vw_technician_utilization_summary';
DECLARE @key_result_id VARCHAR(64) = 'KR-TECH-UTIL';
DECLARE @requested_by VARCHAR(255) = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'SqlModuleTagAnnotation' AND object_id = @object_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @object_id AND receipt_type = 'OntologyMappingReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'SqlModuleTagAnnotation', @object_id, 'OntologyMappingReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @object_id AS sourceObjectId, @key_result_id AS keyResultId FROM dbo.governance_okr_key_results WHERE key_result_id = @key_result_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'ONTOMAP-TECHUTIL-001 applied + receipted.';
GO

PRINT 'G19-6 part 1 (CDE mapping + ontology mapping) complete -- next: 09_reconcile_semantic_model for the real TOM mutation.';
GO
