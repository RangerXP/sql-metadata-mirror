/*
================================================================================
Purpose:
  G17-R1 — Migrate the 4 legacy dbo.governance_change_requests rows (KPI
  Approval, Verified Answer Certification, CDE Classification, Glossary Term
  Definition — all Phase 4 / G14 scenarios) into the unified closed-loop
  ledger (dbo.governance_requests / governance_events / governed_object_versions
  / governance_target_receipts) introduced in sql/07_governance_gates/13_closed_loop_governance_ledger.sql.

  This is a historical backfill, not a re-approval: no new decision is made,
  no governed object is mutated. It exists so "is this artifact closed-loop
  complete" can be answered from ONE table regardless of whether the original
  authority was SQL (legacy gate) or Purview (native workflow).

Design:
  - authority = 'SQL', authority_request_id = the legacy request_id (for
    traceability), target_system = 'SQL'.
  - request_type is mapped to PascalCase to match the native-workflow naming
    convention already used for DataProductAccess / DataProductPublish /
    GlossaryTermPublish.
  - Legacy status 'Applied' maps to the ledger's terminal 'Completed' state;
    other legacy statuses map 1:1 where they exist in the ledger's CHECK
    constraint.
  - One governed_object_versions row and one governance_target_receipts row
    (receipt_type = 'LegacyMigrationBackfill') are added per migrated request,
    clearly labeled as a backfill, not a freshly-validated read-back.
  - Fully set-based and idempotent: re-running this script is a no-op for
    already-migrated rows (guarded by the UX_governance_requests_authority_request
    unique index via NOT EXISTS checks).

Prerequisite:
  sql/07_governance_gates/13_closed_loop_governance_ledger.sql must already be applied.
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.governance_change_requests', N'U') IS NULL
BEGIN
    PRINT 'dbo.governance_change_requests does not exist — nothing to migrate.';
    RETURN;
END
GO

-- Staging: legacy rows not yet migrated, with mapped fields precomputed.
IF OBJECT_ID('tempdb..#legacy_migration') IS NOT NULL DROP TABLE #legacy_migration;

SELECT
    gcr.request_id                                                        AS legacy_request_id,
    gcr.request_type                                                      AS legacy_request_type,
    CASE gcr.request_type
        WHEN 'KPI_APPROVAL'                    THEN 'KpiApproval'
        WHEN 'VERIFIED_ANSWER_CERTIFICATION'    THEN 'VerifiedAnswerCertification'
        WHEN 'CDE_CLASSIFICATION'               THEN 'CdeClassification'
        WHEN 'GLOSSARY_TERM_DEFINITION'         THEN 'GlossaryTermDefinition'
        WHEN 'AI_INSTRUCTION_CERTIFICATION'     THEN 'AiInstructionCertification'
        ELSE 'LegacyUnknown'
    END                                                                    AS mapped_request_type,
    CASE gcr.request_type
        WHEN 'KPI_APPROVAL'                    THEN 'Kpi'
        WHEN 'VERIFIED_ANSWER_CERTIFICATION'    THEN 'VerifiedAnswer'
        WHEN 'CDE_CLASSIFICATION'               THEN 'CriticalDataElement'
        WHEN 'GLOSSARY_TERM_DEFINITION'         THEN 'GlossaryTerm'
        WHEN 'AI_INSTRUCTION_CERTIFICATION'     THEN 'AiInstruction'
        ELSE 'LegacyUnknownObject'
    END                                                                    AS mapped_object_type,
    'SQL-LEGACY-' + gcr.request_id                                         AS new_request_id,
    COALESCE(gcr.target_object_id, gcr.target_object_label)                AS target_object_id,
    gcr.target_object_id                                                   AS legacy_target_object_id_raw,
    gcr.target_object_label,
    gcr.requested_by_upn,
    gcr.requested_at,
    gcr.approver_upn,
    gcr.approved_at,
    CASE gcr.status
        WHEN 'Applied'         THEN 'Completed'
        WHEN 'Approved'        THEN 'Approved'
        WHEN 'Rejected'        THEN 'Rejected'
        WHEN 'PendingApproval' THEN 'PendingApproval'
        WHEN 'Draft'           THEN 'Draft'
        ELSE gcr.status
    END                                                                    AS mapped_status,
    gcr.proposed_payload,
    gcr.previous_payload,
    gcr.applied_at,
    gcr.rejection_reason,
    CONVERT(CHAR(64), HASHBYTES('SHA2_256', gcr.proposed_payload), 2)      AS definition_hash
INTO #legacy_migration
FROM dbo.governance_change_requests gcr
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_requests gr
    WHERE gr.authority = 'SQL' AND gr.authority_request_id = gcr.request_id
);

DECLARE @migrated_count INT = (SELECT COUNT(*) FROM #legacy_migration);
PRINT 'Legacy rows to migrate: ' + CAST(@migrated_count AS VARCHAR(10));

IF @migrated_count = 0
BEGIN
    PRINT 'Nothing to migrate — all legacy rows already have a unified ledger entry.';
    RETURN;
END
GO

-- 1) governance_requests: one row per migrated legacy request.
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, authority_request_id,
    target_system, target_object_type, target_object_id, target_object_label,
    requested_by, requested_at, decided_by, decided_at,
    current_status, proposed_payload, source_snapshot, last_observed_at,
    completed_at, failure_reason
)
SELECT
    lm.new_request_id, lm.mapped_request_type, 'SQL', lm.legacy_request_id,
    'SQL', lm.mapped_object_type, lm.target_object_id, lm.target_object_label,
    lm.requested_by_upn, lm.requested_at, lm.approver_upn, lm.approved_at,
    lm.mapped_status, lm.proposed_payload, lm.previous_payload,
    COALESCE(lm.applied_at, lm.approved_at, lm.requested_at),
    CASE WHEN lm.mapped_status = 'Completed' THEN lm.applied_at ELSE NULL END,
    lm.rejection_reason
FROM #legacy_migration lm;

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_requests.';
GO

-- 2) governance_events: Submitted / Decided / Applied history, reconstructed from legacy timestamps.
INSERT INTO dbo.governance_events (
    request_id, event_type, event_status, source_system, source_event_id,
    actor_id, occurred_at, observed_at, payload, payload_hash
)
SELECT
    lm.new_request_id, 'LegacySubmitted', 'Submitted', 'SQL',
    lm.legacy_request_id + ':Submitted',
    lm.requested_by_upn, lm.requested_at, lm.requested_at,
    lm.proposed_payload, lm.definition_hash
FROM #legacy_migration lm
WHERE lm.requested_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.governance_events ge
      WHERE ge.source_system = 'SQL' AND ge.source_event_id = lm.legacy_request_id + ':Submitted'
  );

INSERT INTO dbo.governance_events (
    request_id, event_type, event_status, source_system, source_event_id,
    actor_id, occurred_at, observed_at, payload, payload_hash
)
SELECT
    lm.new_request_id, 'LegacyDecided', lm.mapped_status, 'SQL',
    lm.legacy_request_id + ':Decided',
    lm.approver_upn, lm.approved_at, lm.approved_at,
    lm.proposed_payload, lm.definition_hash
FROM #legacy_migration lm
WHERE lm.approved_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.governance_events ge
      WHERE ge.source_system = 'SQL' AND ge.source_event_id = lm.legacy_request_id + ':Decided'
  );

INSERT INTO dbo.governance_events (
    request_id, event_type, event_status, source_system, source_event_id,
    actor_id, occurred_at, observed_at, payload, payload_hash
)
SELECT
    lm.new_request_id, 'LegacyApplied', 'Completed', 'SQL',
    lm.legacy_request_id + ':Applied',
    lm.approver_upn, lm.applied_at, lm.applied_at,
    lm.proposed_payload, lm.definition_hash
FROM #legacy_migration lm
WHERE lm.applied_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.governance_events ge
      WHERE ge.source_system = 'SQL' AND ge.source_event_id = lm.legacy_request_id + ':Applied'
  );

PRINT 'Backfilled governance_events history for migrated requests.';
GO

-- 3) governed_object_versions: the applied payload as one immutable version per object.
INSERT INTO dbo.governed_object_versions (
    request_id, source_system, object_type, object_id, source_version_id,
    lifecycle_status, definition_hash, object_payload, effective_at
)
SELECT
    lm.new_request_id, 'SQL', lm.mapped_object_type, lm.target_object_id,
    lm.legacy_request_id,
    CASE WHEN lm.mapped_status = 'Completed' THEN 'Applied' ELSE lm.mapped_status END,
    lm.definition_hash, lm.proposed_payload,
    COALESCE(lm.applied_at, lm.approved_at, lm.requested_at)
FROM #legacy_migration lm
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions gov
    WHERE gov.source_system = 'SQL' AND gov.object_type = lm.mapped_object_type
      AND gov.object_id = lm.target_object_id AND gov.source_version_id = lm.legacy_request_id
);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governed_object_versions.';
GO

-- 4) governance_target_receipts: one backfill receipt per migrated, completed request.
INSERT INTO dbo.governance_target_receipts (
    request_id, target_system, target_object_type, target_object_id,
    receipt_type, expected_hash, observed_hash, validation_status, evidence_payload
)
SELECT
    lm.new_request_id, 'SQL', lm.mapped_object_type, lm.target_object_id,
    'LegacyMigrationBackfill', lm.definition_hash, lm.definition_hash, 'Passed',
    (SELECT
        lm.legacy_request_id AS legacyRequestId,
        lm.legacy_request_type AS legacyRequestType,
        lm.applied_at AS legacyAppliedAt,
        CASE WHEN lm.legacy_target_object_id_raw IS NULL THEN CAST(1 AS BIT) ELSE CAST(0 AS BIT) END AS targetObjectIdBackfilledFromLabel,
        'Backfilled by sql/14_migrate_legacy_governance_to_unified_ledger.sql on ' + CONVERT(VARCHAR(33), SYSUTCDATETIME(), 127) AS migrationNote
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #legacy_migration lm
WHERE lm.mapped_status = 'Completed'
  AND NOT EXISTS (
      SELECT 1 FROM dbo.governance_target_receipts gtr
      WHERE gtr.request_id = lm.new_request_id AND gtr.receipt_type = 'LegacyMigrationBackfill'
  );

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_target_receipts.';
GO

DROP TABLE #legacy_migration;
GO

PRINT 'G17-R1 legacy governance migration complete.';
GO
