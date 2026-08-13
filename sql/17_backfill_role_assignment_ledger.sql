/*
================================================================================
Purpose:
  G17-R5 — Backfill lightweight RoleAssignment entries into the unified
  governance ledger for the domain-role / workflow-approver nominations made
  during the P3 (Data Product Access) and P4 (Data Product Publish) builds.

  Unified Catalog RBAC has no REST API (confirmed, see repo memory
  purview-api-notes.md "Unified Catalog RBAC role assignment") -- every grant
  below was a real, manual Purview-portal action performed by the operator.
  This is therefore operator-attested evidence (same honesty pattern as P3's
  nb_14), not independently machine-verified. It exists so "who is Data
  Product Owner on Service Delivery, since when, per whose action" is
  answerable from SQL, instead of being tribal/portal-only knowledge.

Design:
  - authority = 'Purview' (the role state itself lives in Purview RBAC, even
    though no API can read it back).
  - request_type = 'RoleAssignment'.
  - target_system = 'Purview', target_object_type = 'GovernanceDomainRole' |
    'DataProductRole' | 'CatalogRole' | 'WorkflowApprover'.
  - target_object_id encodes role+scope+principal for uniqueness and
    readability, e.g. 'DataProductOwners:DOM-SVCDEL:ranbir.singh@...'.
  - current_status = 'Completed' immediately (a role grant has no separate
    apply/validate phase distinct from the grant itself).
  - One governance_target_receipts row per entry, receipt_type =
    'OperatorAttestedRoleGrant', validation_status = 'Passed', clearly
    labeled as attested in the evidence payload.

Idempotent: safe to re-run (guarded by request_id existence check).
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID('tempdb..#role_grants') IS NOT NULL DROP TABLE #role_grants;

CREATE TABLE #role_grants (
    request_id          VARCHAR(64)   NOT NULL,
    target_object_type   VARCHAR(64)   NOT NULL,
    target_object_id      VARCHAR(256)  NOT NULL,
    target_object_label   NVARCHAR(256) NOT NULL,
    principal_upn         VARCHAR(255)  NOT NULL,
    scope_label            NVARCHAR(256) NOT NULL,
    granted_by             VARCHAR(255)  NOT NULL,
    scenario_tag            VARCHAR(8)    NOT NULL
);

INSERT INTO #role_grants (request_id, target_object_type, target_object_id, target_object_label, principal_upn, scope_label, granted_by, scenario_tag)
VALUES
    ('ROLE-P3-001', 'DataProductRole',       'Owner:DP-CUST360:victoria.tan',              'Victoria Tan - Data product owner (Basic details field), Customer 360',        'victoria.tan@MngEnvMCAP660444.onmicrosoft.com',  'DP-CUST360 (Customer Operations)', 'sean.kelley@microsoft.com', 'P3'),
    ('ROLE-P3-002', 'CatalogRole',           'GlobalCatalogReader:rupal.solanki',           'Rupal Solanki - Global Catalog Reader (tenant-wide)',                          'rupal.solanki@MngEnvMCAP660444.onmicrosoft.com', 'Tenant-wide',                      'sean.kelley@microsoft.com', 'P3'),
    ('ROLE-P3-003', 'WorkflowApprover',      'DataProductAccessApprover:DP-CUST360:victoria.tan', 'Victoria Tan - Data product access Approver + Privacy reviewer, Customer 360', 'victoria.tan@MngEnvMCAP660444.onmicrosoft.com',  'DP-CUST360 access policy',         'sean.kelley@microsoft.com', 'P3'),
    ('ROLE-P4-001', 'GovernanceDomainRole',  'GovernanceDomainOwner:DOM-SVCDEL:ranbir.singh', 'Ranbir Singh - Governance Domain Owner, Service Delivery',                    'ranbir.singh@MngEnvMCAP660444.onmicrosoft.com',  'Service Delivery domain',          'sean.kelley@microsoft.com', 'P4'),
    ('ROLE-P4-002', 'GovernanceDomainRole',  'DataProductOwners:DOM-SVCDEL:ranbir.singh',    'Ranbir Singh - Data Product Owners (domain-level), Service Delivery',         'ranbir.singh@MngEnvMCAP660444.onmicrosoft.com',  'Service Delivery domain',          'sean.kelley@microsoft.com', 'P4'),
    ('ROLE-P4-003', 'GovernanceDomainRole',  'DataSteward:DOM-SVCDEL:shruthi.srinivas',      'Shruthi Srinivas - Data Steward, Service Delivery',                            'shruthi.srinivas@MngEnvMCAP660444.onmicrosoft.com', 'Service Delivery domain',       'sean.kelley@microsoft.com', 'P4'),
    ('ROLE-P4-004', 'CatalogRole',           'GlobalCatalogReader:shruthi.srinivas',         'Shruthi Srinivas - Global Catalog Reader (tenant-wide)',                       'shruthi.srinivas@MngEnvMCAP660444.onmicrosoft.com', 'Tenant-wide',                    'sean.kelley@microsoft.com', 'P4'),
    ('ROLE-P4-005', 'WorkflowApprover',      'DataProductPublishApprover:DOM-SVCDEL:ranbir.singh', 'Ranbir Singh - Data product publish workflow approver, Service Delivery', 'ranbir.singh@MngEnvMCAP660444.onmicrosoft.com',  'Service Delivery Data Product Publish workflow', 'sean.kelley@microsoft.com', 'P4');

-- 1) governance_requests
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, authority_request_id,
    target_system, target_object_type, target_object_id, target_object_label,
    requested_by, requested_at, decided_by, decided_at,
    current_status, proposed_payload, source_snapshot, last_observed_at, completed_at
)
SELECT
    rg.request_id, 'RoleAssignment', 'Purview', NULL,
    'Purview', rg.target_object_type, rg.target_object_id, rg.target_object_label,
    rg.principal_upn, SYSUTCDATETIME(), rg.granted_by, SYSUTCDATETIME(),
    'Completed',
    (SELECT rg.principal_upn AS principalUpn, rg.scope_label AS scope, rg.scenario_tag AS scenarioTag,
            'Operator-attested: no Unified Catalog RBAC REST API exists to grant or read back this role assignment (confirmed, repo memory).' AS attestationLimitation
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
    NULL, SYSUTCDATETIME(), SYSUTCDATETIME()
FROM #role_grants rg
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_requests gr WHERE gr.request_id = rg.request_id);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_requests.';
GO

-- 2) governance_events: one attested grant event per role.
INSERT INTO dbo.governance_events (
    request_id, event_type, event_status, source_system, source_event_id,
    actor_id, occurred_at, observed_at, payload
)
SELECT
    rg.request_id, 'RoleGrantAttested', 'Completed', 'Purview',
    rg.request_id + ':RoleGrantAttested',
    rg.granted_by, SYSUTCDATETIME(), SYSUTCDATETIME(),
    (SELECT rg.principal_upn AS principalUpn, rg.target_object_label AS roleLabel, rg.scope_label AS scope
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #role_grants rg
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_events ge
    WHERE ge.source_system = 'Purview' AND ge.source_event_id = rg.request_id + ':RoleGrantAttested'
);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_events.';
GO

-- 3) governance_target_receipts: attested, not machine-verified.
INSERT INTO dbo.governance_target_receipts (
    request_id, target_system, target_object_type, target_object_id,
    receipt_type, expected_hash, observed_hash, validation_status, evidence_payload
)
SELECT
    rg.request_id, 'Purview', rg.target_object_type, rg.target_object_id,
    'OperatorAttestedRoleGrant', NULL, NULL, 'Passed',
    (SELECT rg.principal_upn AS principalUpn, rg.granted_by AS grantedBy, rg.scope_label AS scope,
            'Attested by the operator who directly performed this grant in the Purview portal (Roles tab / Manage access policies / Workflow approver picker, per scenario). No REST API exists to independently verify Unified Catalog RBAC role assignments.' AS attestationNote
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #role_grants rg
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts gtr
    WHERE gtr.request_id = rg.request_id AND gtr.receipt_type = 'OperatorAttestedRoleGrant'
);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_target_receipts.';
GO

DROP TABLE #role_grants;
GO

PRINT 'G17-R5 role-assignment ledger backfill complete.';
GO
