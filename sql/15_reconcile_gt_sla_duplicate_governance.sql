/*
================================================================================
Purpose:
  G17-R2 — Reconcile the duplicate GT-SLA governance record. The same
  real-world glossary term was governed twice, under two disconnected
  systems:
    - SQL-LEGACY-GCR-GT-001 (authority='SQL', legacy Phase 4 gate, Completed 2026-08-09)
    - PV-GT-SLA-0359C207890E4EB1B8AB (authority='Purview', native workflow, Completed 2026-08-11)

  The Purview-native request is the more rigorous, API-verified evidence
  chain (PublicationReadback + SemanticModelReadback both Passed) and is
  designated the authoritative record going forward. The legacy SQL request
  is marked Superseded (a valid terminal state per the ledger's CHECK
  constraint), not deleted -- its history remains queryable, but
  current_status makes clear it is no longer the governing decision.

  A governance_object_mappings row links the two so a future query can
  answer "these two request rows describe the same object" without guessing
  from target_object_label text matching.

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

DECLARE @legacy_request_id   VARCHAR(64) = 'SQL-LEGACY-GCR-GT-001';
DECLARE @native_request_id   VARCHAR(64) = 'PV-GT-SLA-0359C207890E4EB1B8AB';

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @legacy_request_id)
BEGIN
    PRINT 'Legacy GT-SLA request not found -- nothing to reconcile.';
    RETURN;
END

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @native_request_id)
BEGIN
    PRINT 'Native GT-SLA request not found -- nothing to reconcile.';
    RETURN;
END

-- 1) Mark the legacy request Superseded, preserving its own completed_at as history.
UPDATE dbo.governance_requests
SET current_status = 'Superseded',
    failure_reason = 'Superseded by native Purview workflow request ' + @native_request_id + ' (Completed 2026-08-11, real PublicationReadback + SemanticModelReadback evidence). See G17-R2.'
WHERE request_id = @legacy_request_id
  AND current_status <> 'Superseded';

PRINT 'Legacy request status updated: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @legacy_request_id   VARCHAR(64) = 'SQL-LEGACY-GCR-GT-001';
DECLARE @native_request_id   VARCHAR(64) = 'PV-GT-SLA-0359C207890E4EB1B8AB';

-- 2) Record a supersession event on the legacy request for the audit trail.
IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_events
    WHERE source_system = 'SQL' AND source_event_id = @legacy_request_id + ':SupersededByNativeWorkflow'
)
INSERT INTO dbo.governance_events (
    request_id, event_type, event_status, source_system, source_event_id,
    actor_id, occurred_at, observed_at, payload
)
SELECT
    @legacy_request_id, 'SupersededByNativeWorkflow', 'Superseded', 'SQL',
    @legacy_request_id + ':SupersededByNativeWorkflow',
    'sean.kelley@microsoft.com', SYSUTCDATETIME(), SYSUTCDATETIME(),
    (SELECT @native_request_id AS supersededByRequestId,
            'G17-R2 reconciliation: same real-world GT-SLA glossary term governed under two systems; native Purview workflow designated authoritative.' AS note
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'Supersession event recorded: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @legacy_request_id   VARCHAR(64) = 'SQL-LEGACY-GCR-GT-001';
DECLARE @native_request_id   VARCHAR(64) = 'PV-GT-SLA-0359C207890E4EB1B8AB';

-- 3) Link the two object identities via governance_object_mappings.
IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_object_mappings
    WHERE mapping_type = 'LegacyToNativeGovernanceReconciliation'
      AND source_system = 'SQL' AND source_object_type = 'GlossaryTerm'
      AND target_system = 'Purview' AND target_object_type = 'GlossaryTerm'
      AND source_object_id = (SELECT target_object_id FROM dbo.governance_requests WHERE request_id = @legacy_request_id)
      AND target_object_id = (SELECT target_object_id FROM dbo.governance_requests WHERE request_id = @native_request_id)
)
INSERT INTO dbo.governance_object_mappings (
    mapping_type, source_system, source_object_type, source_object_id,
    target_system, target_object_type, target_object_id,
    mapping_status, mapping_metadata, last_validated_at
)
SELECT
    'LegacyToNativeGovernanceReconciliation', 'SQL', 'GlossaryTerm',
    (SELECT target_object_id FROM dbo.governance_requests WHERE request_id = @legacy_request_id),
    'Purview', 'GlossaryTerm',
    (SELECT target_object_id FROM dbo.governance_requests WHERE request_id = @native_request_id),
    'Active',
    (SELECT @legacy_request_id AS legacyRequestId, @native_request_id AS nativeRequestId,
            'GT-SLA reconciled under G17-R2' AS note
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
    SYSUTCDATETIME();

PRINT 'Object mapping recorded: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

PRINT 'G17-R2 GT-SLA reconciliation complete.';
GO
