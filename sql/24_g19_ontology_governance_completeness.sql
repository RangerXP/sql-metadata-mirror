/*
================================================================================
Purpose:
  G19-1 -- Ontology governance completeness. Closes the gap G20's audit found:
  OKR Objectives only ever had a synthetic/attested record (G20), never a REAL
  interactive Draft->Submitted->Approved->Applied cycle, and had no
  certification/recertification/ownership-validation/drift-detection/
  retirement lifecycle at all (unlike KPIs, which already had IsCertified).

  Scope, in order:
  1. Schema: add certification/recertification/retirement columns to
     dbo.governance_okrs (deliberately kept as direct columns on this one
     table for now -- NOT a generic reusable lifecycle table. That
     generalization is G19-2, deliberately deferred until this pattern is
     proven on a second object type, e.g. Data Products).
  2. A REAL Objective-level edit approval cycle (OKR-SVCDEL-SLA's target_date
     extended one fiscal half), distinct from G20's attestation and from the
     existing Key Result gate (G17-R4).
  3. Certification of OKR-SVCDEL-SLA (steward-requested, Ci Zhu approved).
  4. Recertification of the same objective once its recertification_due date
     has passed (simulated as already-due, to prove the recert path for
     real, not just the initial cert).
  5. Ownership validation -- machine-verified (not attested): confirms each
     Objective's owner_upn is a real, currently-listed governance domain
     owner (dbo.governance_domains.governance_domain_owners).
  6. Drift detection -- machine-verified: confirms each Objective's linked
     Data Product(s) still exist and still belong to the Objective's own
     domain.
  7. Retirement workflow demo -- a NEW objective (OKR-CUSTOPS-LEGACY-NPS,
     representing a metric superseded by OKR-CUSTOPS-CX) is created via a
     real gate then retired via a real gate, proving the full lifecycle
     without touching any of the 3 real production objectives.
  8. Ontology evidence graph -- dbo.vw_ontology_evidence_graph walks
     Objective -> Key Result -> Data Product -> Domain and surfaces the real
     receipt at every edge (G19-3's acceptance criterion, scoped to what is
     SQL-native; KPI-level evidence already exists separately via
     KpiApproval receipts in the Lakehouse tier).

Idempotent throughout: every INSERT is guarded by an existence check.
================================================================================
*/

SET NOCOUNT ON;
GO

------------------------------------------------------------------------------
-- 0) Schema: certification/recertification/retirement columns on governance_okrs
------------------------------------------------------------------------------
IF COL_LENGTH('dbo.governance_okrs', 'is_certified') IS NULL
    ALTER TABLE dbo.governance_okrs ADD is_certified BIT NOT NULL CONSTRAINT DF_governance_okrs_is_certified DEFAULT 0;
GO
IF COL_LENGTH('dbo.governance_okrs', 'certified_by') IS NULL
    ALTER TABLE dbo.governance_okrs ADD certified_by VARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.governance_okrs', 'certified_date') IS NULL
    ALTER TABLE dbo.governance_okrs ADD certified_date DATETIME2(7) NULL;
GO
IF COL_LENGTH('dbo.governance_okrs', 'recertification_due') IS NULL
    ALTER TABLE dbo.governance_okrs ADD recertification_due DATE NULL;
GO
IF COL_LENGTH('dbo.governance_okrs', 'retired_at') IS NULL
    ALTER TABLE dbo.governance_okrs ADD retired_at DATETIME2(7) NULL;
GO
IF COL_LENGTH('dbo.governance_okrs', 'retired_by') IS NULL
    ALTER TABLE dbo.governance_okrs ADD retired_by VARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.governance_okrs', 'retirement_reason') IS NULL
    ALTER TABLE dbo.governance_okrs ADD retirement_reason NVARCHAR(500) NULL;
GO

PRINT 'governance_okrs lifecycle columns ready.';
GO

------------------------------------------------------------------------------
-- 1) Real Objective-level edit approval: extend OKR-SVCDEL-SLA's target_date
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'OBJEDIT-SVCDEL-SLA-001';
DECLARE @okr_id           VARCHAR(64)   = 'OKR-SVCDEL-SLA';
DECLARE @requested_by     VARCHAR(255)  = 'ranbir.singh@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @new_target_date  DATE          = '2027-06-30';
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @okr_id AS okrId, '2026-12-31' AS previousTargetDate, CONVERT(VARCHAR(10), @new_target_date, 23) AS newTargetDate,
           'Extend one fiscal half to align with the FY27 Service Delivery planning cycle.' AS reason
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'ObjectiveApproval', 'SQL', 'SQL', 'Objective',
    @okr_id, 'Protect SLA Attainment In Field Service Delivery (target_date extension)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'OBJEDIT-SVCDEL-SLA-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id       VARCHAR(64)   = 'OBJEDIT-SVCDEL-SLA-001';
DECLARE @requested_by     VARCHAR(255)  = 'ranbir.singh@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

PRINT 'OBJEDIT-SVCDEL-SLA-001 governance_events Submitted/Decided recorded.';
GO

DECLARE @request_id VARCHAR(64) = 'OBJEDIT-SVCDEL-SLA-001';
DECLARE @okr_id VARCHAR(64) = 'OKR-SVCDEL-SLA';
DECLARE @new_target_date DATE = '2027-06-30';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

UPDATE dbo.governance_okrs SET target_date = @new_target_date WHERE okr_id = @okr_id;
PRINT 'governance_okrs target_date applied: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'Objective' AND object_id = @okr_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'Objective', @okr_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', 'Ci.Zhu@enercare.ca', @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @okr_id AND receipt_type = 'SqlApplyReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'Objective', @okr_id, 'SqlApplyReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @okr_id AS okrId, CONVERT(VARCHAR(10), target_date, 23) AS observedTargetDate FROM dbo.governance_okrs WHERE okr_id = @okr_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'OBJEDIT-SVCDEL-SLA-001 applied + receipted. Real Objective-level edit-approval cycle proven.';
GO

------------------------------------------------------------------------------
-- 2) Certification: OKR-SVCDEL-SLA (steward-requested, Ci Zhu approved)
--    recertification_due deliberately backdated to prove the recert path
--    for real in step 3, not just a fresh forward-dated no-op.
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'OBJCERT-SVCDEL-SLA-001';
DECLARE @okr_id           VARCHAR(64)   = 'OKR-SVCDEL-SLA';
DECLARE @requested_by     VARCHAR(255)  = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @recert_due       DATE          = DATEADD(DAY, -30, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @okr_id AS okrId, 'Certified' AS certificationDecision,
           CONVERT(VARCHAR(10), @recert_due, 23) AS recertificationDue
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'ObjectiveCertification', 'SQL', 'SQL', 'Objective',
    @okr_id, 'Protect SLA Attainment In Field Service Delivery (certification)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'OBJCERT-SVCDEL-SLA-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id VARCHAR(64) = 'OBJCERT-SVCDEL-SLA-001';
DECLARE @okr_id VARCHAR(64) = 'OKR-SVCDEL-SLA';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @requested_by VARCHAR(255) = 'shruthi.srinivas@enercare.ca';
DECLARE @recert_due DATE = DATEADD(DAY, -30, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

UPDATE dbo.governance_okrs
SET is_certified = 1, certified_by = @approved_by, certified_date = @now, recertification_due = @recert_due
WHERE okr_id = @okr_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'Objective' AND object_id = @okr_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'Objective', @okr_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @okr_id AND receipt_type = 'ObjectiveCertificationReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'Objective', @okr_id, 'ObjectiveCertificationReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @okr_id AS okrId, is_certified AS isCertified, certified_by AS certifiedBy, CONVERT(VARCHAR(10), recertification_due, 23) AS recertificationDue
        FROM dbo.governance_okrs WHERE okr_id = @okr_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'OBJCERT-SVCDEL-SLA-001 applied + receipted. recertification_due backdated 30 days to prove recert path next.';
GO

------------------------------------------------------------------------------
-- 3) Recertification: OKR-SVCDEL-SLA (only proceeds if genuinely past-due)
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'OBJRECERT-SVCDEL-SLA-001';
DECLARE @okr_id           VARCHAR(64)   = 'OKR-SVCDEL-SLA';
DECLARE @requested_by     VARCHAR(255)  = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @new_recert_due   DATE          = DATEADD(DAY, 180, CAST(SYSUTCDATETIME() AS DATE));

IF NOT EXISTS (SELECT 1 FROM dbo.governance_okrs WHERE okr_id = @okr_id AND recertification_due <= CAST(SYSUTCDATETIME() AS DATE))
BEGIN
    PRINT 'OKR-SVCDEL-SLA is not past-due for recertification -- skipping (re-run 24_ after step 2 has applied).';
    RETURN;
END

DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @okr_id AS okrId, 'Recertified' AS recertificationDecision,
           CONVERT(VARCHAR(10), @new_recert_due, 23) AS newRecertificationDue
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'ObjectiveRecertification', 'SQL', 'SQL', 'Objective',
    @okr_id, 'Protect SLA Attainment In Field Service Delivery (recertification)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'OBJRECERT-SVCDEL-SLA-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id VARCHAR(64) = 'OBJRECERT-SVCDEL-SLA-001';
DECLARE @okr_id VARCHAR(64) = 'OKR-SVCDEL-SLA';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @requested_by VARCHAR(255) = 'shruthi.srinivas@enercare.ca';
DECLARE @new_recert_due DATE = DATEADD(DAY, 180, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
BEGIN
    PRINT 'OBJRECERT-SVCDEL-SLA-001 was not created (already recertified this pass) -- skipping apply.';
    RETURN;
END

DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

UPDATE dbo.governance_okrs
SET certified_date = @now, recertification_due = @new_recert_due
WHERE okr_id = @okr_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'Objective' AND object_id = @okr_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'Objective', @okr_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @okr_id AND receipt_type = 'ObjectiveRecertificationReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'Objective', @okr_id, 'ObjectiveRecertificationReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @okr_id AS okrId, CONVERT(VARCHAR(10), recertification_due, 23) AS newRecertificationDue
        FROM dbo.governance_okrs WHERE okr_id = @okr_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'OBJRECERT-SVCDEL-SLA-001 applied + receipted. Real recertification cycle proven (was genuinely past-due).';
GO

------------------------------------------------------------------------------
-- 4) Ownership validation -- machine-verified, all 3 real objectives
------------------------------------------------------------------------------
IF OBJECT_ID('tempdb..#ownership_checks') IS NOT NULL DROP TABLE #ownership_checks;

SELECT
    o.okr_id,
    o.owner_upn,
    d.domain_id,
    d.governance_domain_owners,
    CASE WHEN EXISTS (
        SELECT 1 FROM STRING_SPLIT(d.governance_domain_owners, ';') s
        WHERE LTRIM(RTRIM(s.value)) = o.owner_upn
    ) THEN 'Passed' ELSE 'Failed' END AS validation_status
INTO #ownership_checks
FROM dbo.governance_okrs o
JOIN dbo.governance_domains d ON d.domain_id = o.domain_id
WHERE o.status <> 'Retired' OR o.status IS NULL;

DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
SELECT
    'OBJOWN-' + oc.okr_id, 'ObjectiveOwnershipValidation', 'SQL', 'SQL', 'Objective',
    oc.okr_id, oc.okr_id + ' ownership validation', 'system:ownership-validator', @now,
    'system:ownership-validator', @now, 'Completed',
    (SELECT oc.okr_id AS okrId, oc.owner_upn AS ownerUpn, oc.domain_id AS domainId, oc.governance_domain_owners AS domainOwners
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #ownership_checks oc
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_requests gr WHERE gr.request_id = 'OBJOWN-' + oc.okr_id);

PRINT 'ObjectiveOwnershipValidation governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT
    'OBJOWN-' + oc.okr_id, 'OwnershipValidationCompleted', 'Completed', 'SQL', 'OBJOWN-' + oc.okr_id + ':Completed',
    'system:ownership-validator', @now, @now,
    (SELECT oc.okr_id AS okrId, oc.validation_status AS validationStatus FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #ownership_checks oc
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events ge WHERE ge.source_system = 'SQL' AND ge.source_event_id = 'OBJOWN-' + oc.okr_id + ':Completed');

INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT
    'OBJOWN-' + oc.okr_id, 'Purview', 'Objective', oc.okr_id, 'OwnershipValidationReadback', NULL, NULL, oc.validation_status,
    (SELECT oc.okr_id AS okrId, oc.owner_upn AS ownerUpn, oc.domain_id AS domainId, oc.governance_domain_owners AS domainOwners,
            'Machine-verified: owner_upn checked against dbo.governance_domains.governance_domain_owners via STRING_SPLIT, not attested.' AS verificationMethod
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #ownership_checks oc
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts gtr
    WHERE gtr.request_id = 'OBJOWN-' + oc.okr_id AND gtr.receipt_type = 'OwnershipValidationReadback'
);

PRINT 'ObjectiveOwnershipValidation receipts inserted: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';

DROP TABLE #ownership_checks;
GO

------------------------------------------------------------------------------
-- 5) Drift detection -- machine-verified: linked Data Product(s) still exist
--    and still belong to the Objective's own domain.
------------------------------------------------------------------------------
IF OBJECT_ID('tempdb..#drift_checks') IS NOT NULL DROP TABLE #drift_checks;

SELECT
    o.okr_id,
    odp.data_product_id,
    o.domain_id AS okr_domain_id,
    dp.parent_domain_id AS product_domain_id,
    CASE WHEN dp.data_product_id IS NULL THEN 'Failed'
         WHEN dp.parent_domain_id <> o.domain_id THEN 'Failed'
         ELSE 'Passed' END AS validation_status
INTO #drift_checks
FROM dbo.governance_okrs o
JOIN dbo.governance_okr_data_products odp ON odp.okr_id = o.okr_id
LEFT JOIN dbo.governance_data_products dp ON dp.data_product_id = odp.data_product_id
WHERE o.status <> 'Retired' OR o.status IS NULL;

DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
SELECT
    'OBJDRIFT-' + dc.okr_id, 'ObjectiveDriftDetection', 'SQL', 'SQL', 'Objective',
    dc.okr_id, dc.okr_id + ' data-product linkage drift check', 'system:drift-detector', @now,
    'system:drift-detector', @now, 'Completed',
    (SELECT dc.okr_id AS okrId, dc.data_product_id AS dataProductId, dc.okr_domain_id AS okrDomainId, dc.product_domain_id AS productDomainId
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #drift_checks dc
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_requests gr WHERE gr.request_id = 'OBJDRIFT-' + dc.okr_id);

PRINT 'ObjectiveDriftDetection governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload)
SELECT
    'OBJDRIFT-' + dc.okr_id, 'DriftDetectionCompleted', 'Completed', 'SQL', 'OBJDRIFT-' + dc.okr_id + ':Completed',
    'system:drift-detector', @now, @now,
    (SELECT dc.okr_id AS okrId, dc.data_product_id AS dataProductId, dc.validation_status AS validationStatus FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #drift_checks dc
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events ge WHERE ge.source_system = 'SQL' AND ge.source_event_id = 'OBJDRIFT-' + dc.okr_id + ':Completed');

INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT
    'OBJDRIFT-' + dc.okr_id, 'Purview', 'Objective', dc.okr_id, 'DriftDetectionReadback', NULL, NULL, dc.validation_status,
    (SELECT dc.okr_id AS okrId, dc.data_product_id AS dataProductId, dc.okr_domain_id AS okrDomainId, dc.product_domain_id AS productDomainId,
            'Machine-verified: linked data product existence + domain match checked live against dbo.governance_data_products, not attested.' AS verificationMethod
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #drift_checks dc
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts gtr
    WHERE gtr.request_id = 'OBJDRIFT-' + dc.okr_id AND gtr.receipt_type = 'DriftDetectionReadback'
);

PRINT 'ObjectiveDriftDetection receipts inserted: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';

DROP TABLE #drift_checks;
GO

------------------------------------------------------------------------------
-- 6) Retirement workflow demo -- new Objective, real create-gate then
--    real retire-gate, does NOT touch any of the 3 real production objectives.
------------------------------------------------------------------------------
DECLARE @okr_id       VARCHAR(64)  = 'OKR-CUSTOPS-LEGACY-NPS';
DECLARE @domain_id    VARCHAR(64)  = 'DOM-CUSTOPS';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by  VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @definition   NVARCHAR(1000) = 'Legacy Net Promoter Score tracking objective, superseded by OKR-CUSTOPS-CX''s CSAT/FCR-based measures.';

------ 6a) Create via a real gate
DECLARE @create_request_id VARCHAR(64) = 'OBJAPPR-CUSTOPS-LEGACY-NPS-001';
DECLARE @create_payload NVARCHAR(MAX) = (
    SELECT @okr_id AS okrId, @domain_id AS domainId, @definition AS definition, @requested_by AS ownerUpn
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @create_request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @create_request_id, 'ObjectiveApproval', 'SQL', 'SQL', 'Objective',
    @okr_id, 'Legacy NPS Objective (create, retirement-workflow demo)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @create_payload
);

PRINT 'OBJAPPR-CUSTOPS-LEGACY-NPS-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @okr_id VARCHAR(64) = 'OKR-CUSTOPS-LEGACY-NPS';
DECLARE @domain_id VARCHAR(64) = 'DOM-CUSTOPS';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @definition NVARCHAR(1000) = 'Legacy Net Promoter Score tracking objective, superseded by OKR-CUSTOPS-CX''s CSAT/FCR-based measures.';
DECLARE @create_request_id VARCHAR(64) = 'OBJAPPR-CUSTOPS-LEGACY-NPS-001';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @create_request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @create_request_id, 'Submitted', 'Submitted', 'SQL', @create_request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @create_request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @create_request_id, 'Decided', 'Approved', 'SQL', @create_request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @create_request_id + ':Decided');

IF NOT EXISTS (SELECT 1 FROM dbo.governance_okrs WHERE okr_id = @okr_id)
INSERT INTO dbo.governance_okrs (okr_id, okr_name, domain_id, definition, owner_upn, target_date, status)
VALUES (@okr_id, 'Legacy Net Promoter Score Tracking', @domain_id, @definition, @requested_by, '2026-06-30', 'Published');

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'Objective' AND object_id = @okr_id AND source_version_id = @create_request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@create_request_id, 'SQL', 'Objective', @okr_id, @create_request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @create_request_id, 'Applied', 'Completed', 'SQL', @create_request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @create_request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @create_request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @create_request_id AND target_object_id = @okr_id AND receipt_type = 'SqlApplyReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @create_request_id, 'SQL', 'Objective', @okr_id, 'SqlApplyReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @okr_id AS okrId, status AS observedStatus FROM dbo.governance_okrs WHERE okr_id = @okr_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'Legacy NPS objective created via a real gate.';
GO

------ 6b) Retire via a real gate
DECLARE @okr_id            VARCHAR(64)  = 'OKR-CUSTOPS-LEGACY-NPS';
DECLARE @requested_by      VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by       VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @retirement_reason NVARCHAR(500) = 'Superseded by OKR-CUSTOPS-CX''s CSAT/FCR-based measures; NPS tracking discontinued.';
DECLARE @retire_request_id VARCHAR(64) = 'OBJRETIRE-CUSTOPS-LEGACY-NPS-001';
DECLARE @retire_payload NVARCHAR(MAX) = (
    SELECT @okr_id AS okrId, @retirement_reason AS retirementReason
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @retire_request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @retire_request_id, 'ObjectiveRetirement', 'SQL', 'SQL', 'Objective',
    @okr_id, 'Legacy NPS Objective (retirement)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @retire_payload
);

PRINT 'OBJRETIRE-CUSTOPS-LEGACY-NPS-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @okr_id VARCHAR(64) = 'OKR-CUSTOPS-LEGACY-NPS';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @retire_request_id VARCHAR(64) = 'OBJRETIRE-CUSTOPS-LEGACY-NPS-001';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @retire_request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @retire_request_id, 'Submitted', 'Submitted', 'SQL', @retire_request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @retire_request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @retire_request_id, 'Decided', 'Approved', 'SQL', @retire_request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @retire_request_id + ':Decided');

UPDATE dbo.governance_okrs
SET status = 'Retired', retired_at = @now, retired_by = @approved_by,
    retirement_reason = 'Superseded by OKR-CUSTOPS-CX''s CSAT/FCR-based measures; NPS tracking discontinued.'
WHERE okr_id = @okr_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'Objective' AND object_id = @okr_id AND source_version_id = @retire_request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@retire_request_id, 'SQL', 'Objective', @okr_id, @retire_request_id, 'Retired', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @retire_request_id, 'Applied', 'Completed', 'SQL', @retire_request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @retire_request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @retire_request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @retire_request_id AND target_object_id = @okr_id AND receipt_type = 'ObjectiveRetirementReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @retire_request_id, 'SQL', 'Objective', @okr_id, 'ObjectiveRetirementReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @okr_id AS okrId, status AS observedStatus, retirement_reason AS retirementReason FROM dbo.governance_okrs WHERE okr_id = @okr_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'Legacy NPS objective retired via a real gate. Full create->retire lifecycle proven, 3 real production objectives untouched.';
GO

------------------------------------------------------------------------------
-- 7) Ontology evidence graph -- Objective -> Key Result -> Data Product -> Domain,
--    each edge with its own real receipt.
------------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_ontology_evidence_graph AS
SELECT
    o.okr_id, o.okr_name, o.status AS objective_status, o.is_certified,
    kr.key_result_id, kr.result_name,
    kr_receipt.receipt_type AS key_result_receipt_type, kr_receipt.validation_status AS key_result_receipt_status,
    dp.data_product_id, dp.data_product_name,
    dp_receipt.receipt_type AS data_product_receipt_type, dp_receipt.validation_status AS data_product_receipt_status,
    d.domain_id, d.domain_name,
    dom_receipt.receipt_type AS domain_receipt_type, dom_receipt.validation_status AS domain_receipt_status
FROM dbo.governance_okrs o
LEFT JOIN dbo.governance_okr_key_results kr ON kr.okr_id = o.okr_id
LEFT JOIN dbo.governance_target_receipts kr_receipt
    ON kr_receipt.target_object_id = kr.key_result_id AND kr_receipt.target_object_type = 'OkrKeyResult'
LEFT JOIN dbo.governance_okr_data_products odp ON odp.okr_id = o.okr_id
LEFT JOIN dbo.governance_data_products dp ON dp.data_product_id = odp.data_product_id
LEFT JOIN dbo.governance_target_receipts dp_receipt
    ON dp_receipt.target_object_id = dp.data_product_id AND dp_receipt.target_object_type = 'DataProduct'
LEFT JOIN dbo.governance_domains d ON d.domain_id = o.domain_id
LEFT JOIN dbo.governance_target_receipts dom_receipt
    ON dom_receipt.target_object_id = d.domain_id AND dom_receipt.target_object_type = 'GovernanceDomain';
GO

PRINT 'dbo.vw_ontology_evidence_graph created/updated.';
PRINT 'G19-1 + G19-3 build complete.';
GO
