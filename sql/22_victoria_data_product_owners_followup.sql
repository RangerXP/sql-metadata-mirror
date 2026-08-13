/*
================================================================================
Purpose:
  Follow-up to G17-R5: record the real domain-level Data Product Owners role
  grant for Victoria Tan on Customer Operations -- confirmed live 2026-08-13
  as genuinely missing (she previously only had the per-product "Owner"
  metadata field on Customer 360, recorded as ROLE-P3-001, which is
  descriptive metadata only, not the real RBAC role). This was the likely
  root cause of her earlier 403 deleting an access request.

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

DECLARE @request_id VARCHAR(64) = 'ROLE-P3-004';
DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT 'DataProductOwners' AS roleName, 'DOM-CUSTOPS' AS domainCode, 'Customer Operations' AS domainName,
           'victoria.tan@MngEnvMCAP660444.onmicrosoft.com' AS grantedTo,
           'Confirmed missing live 2026-08-13 via domain Roles tab; added by operator' AS note
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
BEGIN
    INSERT INTO dbo.governance_requests (
        request_id, request_type, authority, target_system, target_object_type,
        target_object_id, target_object_label, requested_by, requested_at,
        decided_by, decided_at, current_status, proposed_payload, completed_at
    )
    VALUES (
        @request_id, 'RoleAssignment', 'Purview', 'Purview', 'GovernanceDomainRole',
        'DataProductOwners:DOM-CUSTOPS:victoria.tan', 'Victoria Tan - Data Product Owners (domain-level, real RBAC), Customer Operations',
        'sean.kelley@microsoft.com', @now, 'sean.kelley@microsoft.com', @now, 'Completed', @proposed_payload, @now
    );

    INSERT INTO dbo.governance_target_receipts (request_id, target_system, target_object_type, target_object_id, receipt_type, expected_hash, observed_hash, validation_status, evidence_payload)
    VALUES (@request_id, 'Purview', 'GovernanceDomainRole', 'DataProductOwners:DOM-CUSTOPS:victoria.tan', 'OperatorAttestedRoleGrant',
            CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2), CONVERT(CHAR(64), HASHBYTES('SHA2_256', @proposed_payload), 2),
            'Passed', @proposed_payload);

    PRINT 'ROLE-P3-004 recorded: Victoria Tan added to Data Product Owners, Customer Operations.';
END
ELSE
BEGIN
    PRINT 'ROLE-P3-004 already exists -- nothing to do.';
END
GO
