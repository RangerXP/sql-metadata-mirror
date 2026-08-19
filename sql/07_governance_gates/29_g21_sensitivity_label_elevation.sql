/*
================================================================================
Purpose:
  G21 -- Sensitivity label elevation demo scenario. Proves that a governance
  decision (elevating a Critical Data Element's sensitivity classification)
  has a real, live, enforced consequence -- not just a database row changing.

  Scenario: dbo.service_accounts.latitude/longitude (CDE-GEO, "Geo Coordinates",
  bound to glossary term GT-GEOPII) is currently classified LBL-007
  "Operations Sensitive" (Confidential tier). This elevates it to a new label,
  LBL-010 "Enercare Highly Confidential", which corresponds to a REAL Microsoft
  Purview Information Protection sensitivity label already published in the
  tenant (GUID 0dd498ed-386a-4f71-aa94-2dda1b6e34e5) and backed by a real DLP
  policy ("Enercare Sensitivity Elevation Restrict Access") that restricts
  access to content carrying that label to the item's owner only.

  Cast (matches real ownership already in the seed data -- see
  07_seed_purview_metadata.sql's GT-GEOPII row and purview/role-directory.csv):
    - Requester: Ranbir Singh (GT-GEOPII's real owner_upn)
    - Approver:  Victoria Tan (GT-GEOPII's additional_owners_upn; the repo's
                 designated Privacy Officer (Functional) role)
    - Denied user (real Entra identity, not part of this SQL scope): Rupal
                 Solanki -- Customer 360/consent steward, no legitimate
                 business tie to service-account geolocation data.

  Scope of THIS script: the SQL-controlled portion only -- request creation,
  approval, and the SQL-side reclassification (moving CDE-GEO's bound columns
  from LBL-007 to LBL-010). This intentionally leaves current_status at
  'Approved', not 'Completed' -- the remaining required receipts (Purview
  Data Map Atlas tag refresh, and the real Fabric-item MIP label applied via
  the Power BI Admin setLabels API) require external API calls that happen in
  a notebook step, per the Closed-Loop Contract: "SQL transitions the request
  to Completed only after all required receipts pass."

  See docs/sensitivity-label-elevation-demo-design.md for the full design.

Idempotent throughout: every INSERT is guarded by an existence check.
================================================================================
*/

SET NOCOUNT ON;
GO

------------------------------------------------------------------------------
-- 0) Schema: link a governance_label_assignments row to a real MIP label GUID
------------------------------------------------------------------------------
IF COL_LENGTH('dbo.governance_label_assignments', 'mip_label_guid') IS NULL
    ALTER TABLE dbo.governance_label_assignments ADD mip_label_guid VARCHAR(64) NULL;
GO

------------------------------------------------------------------------------
-- 1) Create the SensitivityLabelElevation request (Ranbir requests,
--    Victoria approves) -- proposed_payload captures the before/after state
------------------------------------------------------------------------------
DECLARE @request_id VARCHAR(64) = 'SLELEV-CDE-GEO-001';
DECLARE @requested_by VARCHAR(255) = 'ranbir.singh@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT
        'CDE-GEO' AS cdeId,
        'GT-GEOPII' AS glossaryTermCode,
        'dbo.service_accounts.latitude;dbo.service_accounts.longitude' AS boundColumns,
        'LBL-007' AS fromLabelId,
        'Operations Sensitive' AS fromSensitivityTier,
        'LBL-010' AS toLabelId,
        'Enercare Highly Confidential' AS toSensitivityTier,
        '0dd498ed-386a-4f71-aa94-2dda1b6e34e5' AS mipLabelGuid,
        'Precise lat/long tied to a named customer service account is effectively home-address-precision PII, not just an operations/dispatch concern.' AS justification
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'SensitivityLabelElevation', 'SQL', 'SQL', 'CriticalDataElement',
    'CDE-GEO', 'Geo Coordinates (CDE-GEO) sensitivity elevation to Enercare Highly Confidential',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'SLELEV-CDE-GEO-001 governance_requests: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s).';
GO

------------------------------------------------------------------------------
-- 2) Events: Submitted (Ranbir), Decided/Approved (Victoria)
------------------------------------------------------------------------------
DECLARE @request_id VARCHAR(64) = 'SLELEV-CDE-GEO-001';
DECLARE @requested_by VARCHAR(255) = 'ranbir.singh@enercare.ca';
DECLARE @approved_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Submitted', 'Submitted', 'SQL', @request_id + ':Submitted', @requested_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Submitted');

INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
SELECT @request_id, 'Decided', 'Approved', 'SQL', @request_id + ':Decided', @approved_by, @now, @now, @proposed_payload, @definition_hash
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @request_id + ':Decided');

PRINT 'SLELEV-CDE-GEO-001 Submitted/Decided events recorded.';
GO

------------------------------------------------------------------------------
-- 3) SQL-side apply: create LBL-010, move CDE-GEO's bound columns off LBL-007
--    onto LBL-010, record the version + a SQL-target receipt. Does NOT mark
--    the request Completed -- external Purview/Fabric receipts remain
--    outstanding (applied by a separate notebook step).
------------------------------------------------------------------------------
DECLARE @request_id VARCHAR(64) = 'SLELEV-CDE-GEO-001';
DECLARE @approved_by VARCHAR(255) = 'Victoria.Tan@enercare.ca';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (SELECT proposed_payload FROM dbo.governance_requests WHERE request_id = @request_id);
DECLARE @definition_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_label_assignments WHERE label_id = 'LBL-010')
INSERT INTO dbo.governance_label_assignments (label_id, label_name, sensitivity_tier, protection_policy, applies_to_asset_ids, scope, mip_label_guid)
VALUES (
    'LBL-010', 'Enercare Highly Confidential', 'Highly Confidential',
    'Real Microsoft Purview Information Protection label, backed by DLP policy Enercare Sensitivity Elevation Restrict Access (restrict access to content owner only).',
    'dbo.service_accounts.latitude;dbo.service_accounts.longitude',
    'Tenant',
    '0dd498ed-386a-4f71-aa94-2dda1b6e34e5'
);

UPDATE dbo.governance_label_assignments
SET applies_to_asset_ids = 'dbo.service_zones'
WHERE label_id = 'LBL-007'
  AND applies_to_asset_ids = 'dbo.service_accounts.latitude;dbo.service_accounts.longitude;dbo.service_zones';

IF NOT EXISTS (
    SELECT 1 FROM dbo.governed_object_versions
    WHERE source_system = 'SQL' AND object_type = 'SensitivityLabelAssignment' AND object_id = 'CDE-GEO' AND source_version_id = @request_id
)
INSERT INTO dbo.governed_object_versions (request_id, source_system, object_type, object_id, source_version_id, lifecycle_status, definition_hash, object_payload, effective_at)
VALUES (@request_id, 'SQL', 'SensitivityLabelAssignment', 'CDE-GEO', @request_id, 'Applied', @definition_hash, @proposed_payload, @now);

IF NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts
    WHERE request_id = @request_id AND target_object_id = 'CDE-GEO' AND receipt_type = 'SqlApplyReadback'
)
INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
SELECT @request_id, 'SQL', 'CriticalDataElement', 'CDE-GEO', 'SqlApplyReadback', @definition_hash, @definition_hash, 'Passed',
       (SELECT label_id, label_name, sensitivity_tier, applies_to_asset_ids, mip_label_guid
        FROM dbo.governance_label_assignments WHERE label_id = 'LBL-010'
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

PRINT 'CDE-GEO sensitivity elevated (SQL side): LBL-007 -> LBL-010 (Enercare Highly Confidential).';
PRINT 'Request remains Approved (not Completed) pending Purview Data Map + Fabric MIP label receipts.';
GO

------------------------------------------------------------------------------
-- 4) Verification query
------------------------------------------------------------------------------
SELECT request_id, request_type, authority, current_status, requested_by, decided_by
FROM dbo.governance_requests WHERE request_id = 'SLELEV-CDE-GEO-001';

SELECT label_id, label_name, sensitivity_tier, applies_to_asset_ids, mip_label_guid
FROM dbo.governance_label_assignments WHERE label_id IN ('LBL-007', 'LBL-010');
GO

PRINT 'G21 sensitivity label elevation (SQL-controlled portion) build complete.';
GO
