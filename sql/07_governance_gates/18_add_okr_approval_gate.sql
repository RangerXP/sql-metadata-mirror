/*
================================================================================
Purpose:
  G17-R4 — Gate OKR Key Result creation through the unified closed-loop ledger
  (no legacy-schema detour: OKRs never had ANY approval gate before, so this
  goes straight into dbo.governance_requests/events/governed_object_versions/
  governance_target_receipts, matching G18's own precedent for new workstreams).

Scenario:
  New Key Result "Technician Utilization Rate At Or Above Target" under the
  existing OKR-SVCDEL-SLA ("Protect SLA Attainment In Field Service Delivery",
  Service Delivery domain, owner Ranbir Singh). Requested by Shruthi Srinivas
  (Data Steward, Service Delivery -- same pairing as P4), approved by Ci Zhu
  (constant Phase 4 approver, same as every other G14/G17-R3 gate).

Scope (matches R3's actual scope): Draft -> Approved -> Applied (real INSERT
into dbo.governance_okr_key_results) -> SqlApplyReadback receipt -> Completed.
Downstream Purview republish (05_publish_governance_domains) is a separate, later step, same as how
KPI/CDE gates don't force an immediate Purview republish either.

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

DECLARE @request_id       VARCHAR(64)  = 'OKR-SVCDEL-TECHUTIL-001';
DECLARE @okr_id           VARCHAR(64)  = 'OKR-SVCDEL-SLA';
DECLARE @key_result_id    VARCHAR(64)  = 'KR-TECH-UTIL';
DECLARE @requested_by     VARCHAR(255) = 'Shruthi.Srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT
        @key_result_id AS keyResultId,
        @okr_id AS okrId,
        'Technician Utilization Rate At Or Above Target' AS resultName,
        'lh_enercare_demo.fct_service_request derived technician utilization' AS metricSource,
        85.00 AS goalAmount,
        79.50 AS progressAmount,
        100.00 AS maxAmount,
        'AtRisk' AS progressStatus
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

IF NOT EXISTS (SELECT 1 FROM dbo.governance_okrs WHERE okr_id = @okr_id)
BEGIN
    PRINT 'Parent OKR ' + @okr_id + ' not found -- aborting.';
    RETURN;
END

IF EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
BEGIN
    PRINT @request_id + ' already exists -- nothing to do.';
    RETURN;
END

-- 1) governance_requests: Draft -> Approved directly (mirrors the already-decided demo pattern
--    used for every other G14/G17-R3 gate scenario, rather than requiring a live two-step wait).
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'OkrApproval', 'SQL', 'SQL', 'OkrKeyResult',
    @key_result_id, 'Technician Utilization Rate (KR under ' + @okr_id + ')',
    @requested_by, @now, @approved_by, @now, 'Approved', @proposed_payload
);

PRINT 'governance_requests row inserted.';
GO

DECLARE @request_id     VARCHAR(64) = 'OKR-SVCDEL-TECHUTIL-001';
DECLARE @okr_id         VARCHAR(64) = 'OKR-SVCDEL-SLA';
DECLARE @key_result_id  VARCHAR(64) = 'KR-TECH-UTIL';
DECLARE @requested_by   VARCHAR(255) = 'Shruthi.Srinivas@enercare.ca';
DECLARE @approved_by    VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

-- 2) governance_events: Submitted + Decided.
INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

PRINT 'governance_events Submitted/Decided recorded.';
GO

DECLARE @request_id     VARCHAR(64) = 'OKR-SVCDEL-TECHUTIL-001';
DECLARE @okr_id         VARCHAR(64) = 'OKR-SVCDEL-SLA';
DECLARE @key_result_id  VARCHAR(64) = 'KR-TECH-UTIL';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

-- 3) Apply: real INSERT into the actual governed object table.
IF NOT EXISTS (SELECT 1 FROM dbo.governance_okr_key_results WHERE key_result_id = @key_result_id)
INSERT INTO dbo.governance_okr_key_results (key_result_id, okr_id, result_name, metric_source, goal_amount, progress_amount, max_amount, progress_status)
VALUES (@key_result_id, @okr_id, 'Technician Utilization Rate At Or Above Target',
        'lh_enercare_demo.fct_service_request derived technician utilization', 85.00, 79.50, 100.00, 'AtRisk');

PRINT 'governance_okr_key_results apply: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';

-- 4) governed_object_versions: immutable applied snapshot.
IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'OkrKeyResult' AND object_id = @key_result_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'OkrKeyResult', @key_result_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

PRINT 'governed_object_versions inserted.';

-- 5) governance_events: Applied.
INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', 'ci.zhu@MngEnvMCAP660444.onmicrosoft.com', @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

PRINT 'governance_events Applied recorded.';
GO

DECLARE @request_id     VARCHAR(64) = 'OKR-SVCDEL-TECHUTIL-001';
DECLARE @key_result_id  VARCHAR(64) = 'KR-TECH-UTIL';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

-- 6) Real read-back receipt: confirm the applied row genuinely exists with the expected values.
DECLARE @observed_payload NVARCHAR(MAX) = (
    SELECT @key_result_id AS keyResultId, okr_id AS okrId, result_name AS resultName,
           metric_source AS metricSource, goal_amount AS goalAmount,
           progress_amount AS progressAmount, max_amount AS maxAmount,
           progress_status AS progressStatus
    FROM dbo.governance_okr_key_results WHERE key_result_id = @key_result_id
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);
DECLARE @observed_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @observed_payload), 2);
DECLARE @expected_hash CHAR(64) = (
    SELECT CONVERT(CHAR(64), HASHBYTES('SHA2_256', proposed_payload), 2)
    FROM dbo.governance_requests WHERE request_id = @request_id
);
DECLARE @validation_status VARCHAR(16) = CASE WHEN @observed_hash = @expected_hash THEN 'Passed' ELSE 'Failed' END;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_system = 'SQL' AND target_object_type = 'OkrKeyResult'
      AND target_object_id = @key_result_id AND receipt_type = 'SqlApplyReadback'
)
BEGIN
    DECLARE @evidence_payload NVARCHAR(MAX) = (
        SELECT @key_result_id AS keyResultId, @observed_hash AS observedHash, @expected_hash AS expectedHash, @now AS observedAt
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
    );
    INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
    VALUES (@request_id, 'SQL', 'OkrKeyResult', @key_result_id, 'SqlApplyReadback', @expected_hash, @observed_hash, @validation_status, @evidence_payload);
END

PRINT 'governance_target_receipts inserted: validation_status=' + @validation_status;

-- 7) Mark Completed only if the receipt passed.
IF @validation_status = 'Passed'
    UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;
ELSE
    UPDATE dbo.governance_requests SET current_status = 'Failed', failure_reason = 'SqlApplyReadback hash mismatch' WHERE request_id = @request_id;

DECLARE @final_status VARCHAR(32) = (SELECT current_status FROM dbo.governance_requests WHERE request_id = @request_id);
PRINT 'G17-R4 OKR Key Result gate complete: current_status=' + @final_status;
GO
