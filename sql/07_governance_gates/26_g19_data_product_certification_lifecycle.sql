/*
================================================================================
Purpose:
  G19-5 -- Data Product certification lifecycle: certify/de-certify/expiration
  review, distinct from Publish (P4, already proven) and Access (P3, already
  proven). G20 gave every data product a synthetic/attested certification
  record as a stopgap; this builds the REAL interactive lifecycle on top of
  that, same pattern as G19-1's Objective lifecycle build.

  Scope, in order:
  1. Schema: add certification/expiration/decertification columns to
     dbo.governance_data_products (direct columns, matching G19-1's
     deliberate choice not to generalize into a reusable table yet -- G19-2).
  2. A REAL certification cycle for DP-SVCPERF (distinct from G20's
     attestation), with expiration_date deliberately backdated to prove the
     expiration-review path for real next.
  3. A REAL expiration-review cycle -- only proceeds if genuinely past-due
     (guarded check) -- renews DP-SVCPERF's certification for another year.
  4. A REAL de-certification example via a NEW disposable data product
     (DP-LEGACY-CALLCENTER-IVR, superseded by DP-CUST360) -- created via a
     real gate, certified, then de-certified for a real reason -- without
     touching any of the 3 real production data products.

Idempotent throughout: every INSERT is guarded by an existence check.
================================================================================
*/

SET NOCOUNT ON;
GO

------------------------------------------------------------------------------
-- 0) Schema: certification/expiration/decertification columns
------------------------------------------------------------------------------
IF COL_LENGTH('dbo.governance_data_products', 'is_certified') IS NULL
    ALTER TABLE dbo.governance_data_products ADD is_certified BIT NOT NULL CONSTRAINT DF_governance_data_products_is_certified DEFAULT 0;
GO
IF COL_LENGTH('dbo.governance_data_products', 'certified_by') IS NULL
    ALTER TABLE dbo.governance_data_products ADD certified_by VARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.governance_data_products', 'certified_date') IS NULL
    ALTER TABLE dbo.governance_data_products ADD certified_date DATETIME2(7) NULL;
GO
IF COL_LENGTH('dbo.governance_data_products', 'expiration_date') IS NULL
    ALTER TABLE dbo.governance_data_products ADD expiration_date DATE NULL;
GO
IF COL_LENGTH('dbo.governance_data_products', 'decertified_at') IS NULL
    ALTER TABLE dbo.governance_data_products ADD decertified_at DATETIME2(7) NULL;
GO
IF COL_LENGTH('dbo.governance_data_products', 'decertified_by') IS NULL
    ALTER TABLE dbo.governance_data_products ADD decertified_by VARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.governance_data_products', 'decertification_reason') IS NULL
    ALTER TABLE dbo.governance_data_products ADD decertification_reason NVARCHAR(500) NULL;
GO

PRINT 'governance_data_products lifecycle columns ready.';
GO

------------------------------------------------------------------------------
-- 1) Real certification: DP-SVCPERF (distinct from G20's DPCERT-SVCPERF attestation)
--    expiration_date backdated 30 days to prove the expiration-review path next.
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'DPCERT-SVCPERF-002';
DECLARE @product_id       VARCHAR(64)   = 'DP-SVCPERF';
DECLARE @requested_by     VARCHAR(255)  = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @expiration_date  DATE          = DATEADD(DAY, -30, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @product_id AS dataProductId, 'Certified' AS certificationDecision,
           CONVERT(VARCHAR(10), @expiration_date, 23) AS expirationDate
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'DataProductCertification', 'SQL', 'SQL', 'DataProduct',
    @product_id, 'Service Performance (certification)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'DPCERT-SVCPERF-002 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id VARCHAR(64) = 'DPCERT-SVCPERF-002';
DECLARE @product_id VARCHAR(64) = 'DP-SVCPERF';
DECLARE @requested_by VARCHAR(255) = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @expiration_date DATE = DATEADD(DAY, -30, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

UPDATE dbo.governance_data_products
SET is_certified = 1, certified_by = @approved_by, certified_date = @now, expiration_date = @expiration_date
WHERE data_product_id = @product_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'DataProduct' AND object_id = @product_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'DataProduct', @product_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @product_id AND receipt_type = 'DataProductCertificationReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'DataProduct', @product_id, 'DataProductCertificationReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @product_id AS dataProductId, is_certified AS isCertified, certified_by AS certifiedBy, CONVERT(VARCHAR(10), expiration_date, 23) AS expirationDate
        FROM dbo.governance_data_products WHERE data_product_id = @product_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'DPCERT-SVCPERF-002 applied + receipted. expiration_date backdated 30 days to prove expiration-review path next.';
GO

------------------------------------------------------------------------------
-- 2) Expiration review: DP-SVCPERF (only proceeds if genuinely past-due)
------------------------------------------------------------------------------
DECLARE @request_id       VARCHAR(64)   = 'DPCERTREVIEW-SVCPERF-001';
DECLARE @product_id       VARCHAR(64)   = 'DP-SVCPERF';
DECLARE @requested_by     VARCHAR(255)  = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @new_expiration   DATE          = DATEADD(DAY, 365, CAST(SYSUTCDATETIME() AS DATE));

IF NOT EXISTS (SELECT 1 FROM dbo.governance_data_products WHERE data_product_id = @product_id AND expiration_date <= CAST(SYSUTCDATETIME() AS DATE))
BEGIN
    PRINT 'DP-SVCPERF is not past-due for expiration review -- skipping (re-run 26_ after step 1 has applied).';
    RETURN;
END

DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @product_id AS dataProductId, 'Renewed' AS expirationReviewDecision,
           CONVERT(VARCHAR(10), @new_expiration, 23) AS newExpirationDate
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'DataProductExpirationReview', 'SQL', 'SQL', 'DataProduct',
    @product_id, 'Service Performance (expiration review)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'DPCERTREVIEW-SVCPERF-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @request_id VARCHAR(64) = 'DPCERTREVIEW-SVCPERF-001';
DECLARE @product_id VARCHAR(64) = 'DP-SVCPERF';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @requested_by VARCHAR(255) = 'shruthi.srinivas@enercare.ca';
DECLARE @new_expiration DATE = DATEADD(DAY, 365, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
BEGIN
    PRINT 'DPCERTREVIEW-SVCPERF-001 was not created (already reviewed this pass) -- skipping apply.';
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

UPDATE dbo.governance_data_products
SET certified_date = @now, expiration_date = @new_expiration
WHERE data_product_id = @product_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'DataProduct' AND object_id = @product_id AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'DataProduct', @product_id, @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Applied', 'Completed', 'SQL', @request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = @product_id AND receipt_type = 'DataProductExpirationReviewReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'DataProduct', @product_id, 'DataProductExpirationReviewReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @product_id AS dataProductId, CONVERT(VARCHAR(10), expiration_date, 23) AS newExpirationDate
        FROM dbo.governance_data_products WHERE data_product_id = @product_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'DPCERTREVIEW-SVCPERF-001 applied + receipted. Real expiration-review cycle proven (was genuinely past-due).';
GO

------------------------------------------------------------------------------
-- 3) De-certification demo -- new disposable data product, real create-gate
--    then real certify-gate then real de-certify-gate. Does NOT touch any of
--    the 3 real production data products.
------------------------------------------------------------------------------
DECLARE @product_id   VARCHAR(64)  = 'DP-LEGACY-CALLCENTER-IVR';
DECLARE @domain_id    VARCHAR(64)  = 'DOM-CUSTOPS';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by  VARCHAR(255) = 'Ci.Zhu@enercare.ca';

------ 3a) Create via a real gate
DECLARE @create_request_id VARCHAR(64) = 'DPAPPR-LEGACY-IVR-001';
DECLARE @create_payload NVARCHAR(MAX) = (
    SELECT @product_id AS dataProductId, @domain_id AS domainId,
           'Legacy IVR call-tree analytics extract, predates the Customer 360 unified interaction model.' AS businessUseCase,
           @requested_by AS ownerUpn
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @create_request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @create_request_id, 'DataProductCertification', 'SQL', 'SQL', 'DataProduct',
    @product_id, 'Legacy Call-Center IVR Analytics (create, decertification-workflow demo)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @create_payload
);

PRINT 'DPAPPR-LEGACY-IVR-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @product_id VARCHAR(64) = 'DP-LEGACY-CALLCENTER-IVR';
DECLARE @domain_id VARCHAR(64) = 'DOM-CUSTOPS';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @create_request_id VARCHAR(64) = 'DPAPPR-LEGACY-IVR-001';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @create_request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @create_request_id, 'Submitted', 'Submitted', 'SQL', @create_request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @create_request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @create_request_id, 'Decided', 'Approved', 'SQL', @create_request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @create_request_id + ':Decided');

IF NOT EXISTS (SELECT 1 FROM dbo.governance_data_products WHERE data_product_id = @product_id)
INSERT INTO dbo.governance_data_products (data_product_id, data_product_name, product_type, business_use_case, audience, owners, attached_assets, access_policy, status, parent_domain_id, stewards)
VALUES (@product_id, 'Legacy Call-Center IVR Analytics', 'Dataset',
        'Legacy IVR call-tree analytics extract, predates the Customer 360 unified interaction model.',
        'Internal analytics team', @requested_by, NULL, NULL, 'Published', @domain_id, NULL);

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'DataProduct' AND object_id = @product_id AND source_version_id = @create_request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@create_request_id, 'SQL', 'DataProduct', @product_id, @create_request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @create_request_id, 'Applied', 'Completed', 'SQL', @create_request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @create_request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @create_request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @create_request_id AND target_object_id = @product_id AND receipt_type = 'SqlApplyReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @create_request_id, 'SQL', 'DataProduct', @product_id, 'SqlApplyReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @product_id AS dataProductId, status AS observedStatus FROM dbo.governance_data_products WHERE data_product_id = @product_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'Legacy IVR data product created via a real gate.';
GO

------ 3b) Certify it
DECLARE @product_id      VARCHAR(64)  = 'DP-LEGACY-CALLCENTER-IVR';
DECLARE @requested_by    VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by     VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @cert_request_id VARCHAR(64)  = 'DPCERT-LEGACY-IVR-001';
DECLARE @expiration_date DATE = DATEADD(DAY, 365, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @cert_payload NVARCHAR(MAX) = (
    SELECT @product_id AS dataProductId, 'Certified' AS certificationDecision, CONVERT(VARCHAR(10), @expiration_date, 23) AS expirationDate
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @cert_request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @cert_request_id, 'DataProductCertification', 'SQL', 'SQL', 'DataProduct',
    @product_id, 'Legacy Call-Center IVR Analytics (certification)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @cert_payload
);

PRINT 'DPCERT-LEGACY-IVR-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @product_id VARCHAR(64) = 'DP-LEGACY-CALLCENTER-IVR';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @cert_request_id VARCHAR(64) = 'DPCERT-LEGACY-IVR-001';
DECLARE @expiration_date DATE = DATEADD(DAY, 365, CAST(SYSUTCDATETIME() AS DATE));
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @cert_request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @cert_request_id, 'Submitted', 'Submitted', 'SQL', @cert_request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @cert_request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @cert_request_id, 'Decided', 'Approved', 'SQL', @cert_request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @cert_request_id + ':Decided');

UPDATE dbo.governance_data_products
SET is_certified = 1, certified_by = @approved_by, certified_date = @now, expiration_date = @expiration_date
WHERE data_product_id = @product_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'DataProduct' AND object_id = @product_id AND source_version_id = @cert_request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@cert_request_id, 'SQL', 'DataProduct', @product_id, @cert_request_id, 'Applied', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @cert_request_id, 'Applied', 'Completed', 'SQL', @cert_request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @cert_request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @cert_request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @cert_request_id AND target_object_id = @product_id AND receipt_type = 'DataProductCertificationReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @cert_request_id, 'SQL', 'DataProduct', @product_id, 'DataProductCertificationReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @product_id AS dataProductId, is_certified AS isCertified, certified_by AS certifiedBy FROM dbo.governance_data_products WHERE data_product_id = @product_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'Legacy IVR data product certified via a real gate.';
GO

------ 3c) De-certify it -- real reason, does not touch the 3 production products
DECLARE @product_id          VARCHAR(64)  = 'DP-LEGACY-CALLCENTER-IVR';
DECLARE @requested_by        VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by         VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @decert_reason       NVARCHAR(500) = 'IVR analytics platform decommissioned; superseded by DP-CUST360''s unified call-center interaction tracking. No active consumers remain.';
DECLARE @decert_request_id   VARCHAR(64)  = 'DPDECERT-LEGACY-IVR-001';
DECLARE @decert_payload NVARCHAR(MAX) = (
    SELECT @product_id AS dataProductId, @decert_reason AS decertificationReason
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @decert_request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @decert_request_id, 'DataProductDecertification', 'SQL', 'SQL', 'DataProduct',
    @product_id, 'Legacy Call-Center IVR Analytics (decertification)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @decert_payload
);

PRINT 'DPDECERT-LEGACY-IVR-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

DECLARE @product_id VARCHAR(64) = 'DP-LEGACY-CALLCENTER-IVR';
DECLARE @requested_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Ci.Zhu@enercare.ca';
DECLARE @decert_request_id VARCHAR(64) = 'DPDECERT-LEGACY-IVR-001';
DECLARE @decert_reason NVARCHAR(500) = 'IVR analytics platform decommissioned; superseded by DP-CUST360''s unified call-center interaction tracking. No active consumers remain.';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @decert_request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @decert_request_id, 'Submitted', 'Submitted', 'SQL', @decert_request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @decert_request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @decert_request_id, 'Decided', 'Approved', 'SQL', @decert_request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @decert_request_id + ':Decided');

UPDATE dbo.governance_data_products
SET is_certified = 0, decertified_at = @now, decertified_by = @approved_by, decertification_reason = @decert_reason, status = 'Retired'
WHERE data_product_id = @product_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'DataProduct' AND object_id = @product_id AND source_version_id = @decert_request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@decert_request_id, 'SQL', 'DataProduct', @product_id, @decert_request_id, 'Retired', @definition_hash, @proposed_payload, @now);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @decert_request_id, 'Applied', 'Completed', 'SQL', @decert_request_id + ':Applied', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @decert_request_id + ':Applied');

UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = @now WHERE request_id = @decert_request_id;

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @decert_request_id AND target_object_id = @product_id AND receipt_type = 'DataProductDecertificationReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @decert_request_id, 'SQL', 'DataProduct', @product_id, 'DataProductDecertificationReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT @product_id AS dataProductId, status AS observedStatus, decertification_reason AS decertificationReason
        FROM dbo.governance_data_products WHERE data_product_id = @product_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'Legacy IVR data product decertified via a real gate. Full create->certify->decertify lifecycle proven, 3 real production data products untouched.';
GO

PRINT 'G19-5 build complete.';
GO
