/*
================================================================================
Purpose:
  G20 -- close the remaining "zero gate of any kind" governance objects found
  by the 2026-08-13 stale-element audit (docs/design-gap-analysis.md G20):
  Governance Domains, OKR Objectives (distinct from Key Results), Data Product
  Certification (distinct from Publish/Access -- also closes DP-BILLHEALTH's
  total lack of any gated action), and Purview scan completion.

Scope decision (explicit user direction, 2026-08-13):
  Not every governed object needs a full interactive approval workflow. Only
  the core demo functions tied to a specific stakeholder moment (P1-P4, G13,
  G14, G17-R3/R4, G18-A) warrant that investment. These four categories are
  pre-assumed/foundational parts of the data model -- they are satisfied with
  a lightweight, honestly-labeled synthetic/attested governance record, same
  pattern as G17-R5's RoleAssignment backfill (`OperatorAttested*` receipt
  type), not a new interactive workflow or notebook.

  Every value below is grounded in real, already-true facts from this repo's
  live state (real domain/OKR/data-product owners from dbo.governance_domains
  / governance_okrs / governance_data_products, real Purview scan run
  outcomes from repo memory) -- nothing fabricated.

Design:
  - request_type in ('DomainPublication', 'ObjectiveApproval',
    'DataProductCertification', 'ScanCompletion') -- none of these existed in
    the ledger before this script.
  - target_system = 'Purview' for all four.
  - current_status = 'Completed' immediately (attestation of an
    already-true state, not a pending decision).
  - One governance_target_receipts row per entry, receipt_type =
    'OperatorAttested<RequestType>', validation_status = 'Passed', evidence
    payload explicitly notes this is attested/synthetic, not a live
    interactive workflow decision.

Idempotent: safe to re-run (guarded by request_id existence check).
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID('tempdb..#g20_records') IS NOT NULL DROP TABLE #g20_records;

CREATE TABLE #g20_records (
    request_id          VARCHAR(64)   NOT NULL,
    request_type         VARCHAR(64)   NOT NULL,
    target_object_type    VARCHAR(64)   NOT NULL,
    target_object_id       VARCHAR(256)  NOT NULL,
    target_object_label     NVARCHAR(256) NOT NULL,
    requested_by             VARCHAR(255)  NOT NULL,
    decided_by                VARCHAR(255)  NOT NULL,
    evidence_note              NVARCHAR(1000) NOT NULL
);

INSERT INTO #g20_records (request_id, request_type, target_object_type, target_object_id, target_object_label, requested_by, decided_by, evidence_note)
VALUES
    -- Governance Domains -- real owners pulled directly from dbo.governance_domains.governance_domain_owners
    ('DOMPUB-CUSTOPS',   'DomainPublication',        'GovernanceDomain', 'DOM-CUSTOPS',   'Customer Operations',       'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca',       N'Domain is live Published in Purview; both listed governance_domain_owners confirmed real.'),
    ('DOMPUB-SVCDEL',    'DomainPublication',        'GovernanceDomain', 'DOM-SVCDEL',    'Service Delivery',          'ranbir.singh@enercare.ca', 'Ci.Zhu@enercare.ca',       N'Domain is live Published in Purview; both listed governance_domain_owners confirmed real.'),
    ('DOMPUB-REVCON',    'DomainPublication',        'GovernanceDomain', 'DOM-REVCON',    'Revenue and Contracts',     'Ci.Zhu@enercare.ca',       'ranbir.singh@enercare.ca', N'Domain is live Published in Purview; both listed governance_domain_owners confirmed real.'),
    -- OKR Objectives -- distinct from Key Results (KR-TECH-UTIL already has a real interactive gate, G17-R4)
    ('OBJAPPR-CUSTOPS-CX',    'ObjectiveApproval', 'Objective', 'OKR-CUSTOPS-CX',       'Improve Call-Center Customer Experience',                   'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca',       N'Objective is live Published in Purview; owner_upn confirmed real from dbo.governance_okrs.'),
    ('OBJAPPR-SVCDEL-SLA',    'ObjectiveApproval', 'Objective', 'OKR-SVCDEL-SLA',       'Protect SLA Attainment In Field Service Delivery',          'ranbir.singh@enercare.ca', 'Ci.Zhu@enercare.ca',       N'Objective is live Published in Purview; owner_upn confirmed real from dbo.governance_okrs.'),
    ('OBJAPPR-REVCON-RETAIN', 'ObjectiveApproval', 'Objective', 'OKR-REVCON-RETAIN',    'Protect Renewal Revenue And Reduce Repeat Billing Complaints', 'Ci.Zhu@enercare.ca',   'ranbir.singh@enercare.ca', N'Objective is live Published in Purview; owner_upn confirmed real from dbo.governance_okrs.'),
    -- Data Product Certification -- distinct from Publish (P4)/Access (P3); also closes DP-BILLHEALTH's total lack of any gated action
    ('DPCERT-CUST360',    'DataProductCertification', 'DataProduct', 'DP-CUST360',    'Customer 360',        'Victoria.Tan@enercare.ca', 'Ci.Zhu@enercare.ca',       N'Data product is live Published in Purview; owner confirmed real from dbo.governance_data_products.'),
    ('DPCERT-SVCPERF',    'DataProductCertification', 'DataProduct', 'DP-SVCPERF',    'Service Performance', 'ranbir.singh@enercare.ca', 'Ci.Zhu@enercare.ca',       N'Data product is live Published in Purview; owner confirmed real from dbo.governance_data_products.'),
    ('DPCERT-BILLHEALTH',  'DataProductCertification', 'DataProduct', 'DP-BILLHEALTH', 'Billing Health',     'Ci.Zhu@enercare.ca',       'ranbir.singh@enercare.ca', N'First gated record of any kind for this product (previously zero governance trail); live Published in Purview, owner confirmed real from dbo.governance_data_products.'),
    -- Purview scan completion -- real scan runs already executed (repo memory), never had a ledger receipt
    ('SCAN-FABRIC-TENANT', 'ScanCompletion', 'PurviewScan', 'enercareFabricScan', 'Fabric tenant scan (Purview-West2, run 0164ff32-3a06-4db7-b97c-410bb09aa690)', 'system:purview-scan-scheduler', 'sean.kelley@microsoft.com', N'Real scan run 0164ff32-3a06-4db7-b97c-410bb09aa690: assetsDiscovered=25, assetsIngestedByPurview=24, 22 relationships ingested, CompletedWithExceptions accepted as good-enough by operator (repo memory purview-api-notes.md).'),
    ('SCAN-SQL-SOURCE',    'ScanCompletion', 'PurviewScan', 'enercareSqlScan',    'Azure SQL source scan (data source sqldemoEnercare)',                        'system:purview-scan-scheduler', 'sean.kelley@microsoft.com', N'Scan completed successfully per repo history (7-table source + 46 Fabric assets confirmed in catalog); specific run GUID was not captured at the time it ran.');

-- 1) governance_requests
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, authority_request_id,
    target_system, target_object_type, target_object_id, target_object_label,
    requested_by, requested_at, decided_by, decided_at,
    current_status, proposed_payload, source_snapshot, last_observed_at, completed_at
)
SELECT
    g.request_id, g.request_type, 'Purview', NULL,
    'Purview', g.target_object_type, g.target_object_id, g.target_object_label,
    g.requested_by, SYSUTCDATETIME(), g.decided_by, SYSUTCDATETIME(),
    'Completed',
    (SELECT g.evidence_note AS evidenceNote,
            'Synthetic/attested: pre-assumed data-model element, not a stakeholder-tied interactive workflow (2026-08-13 scope decision, see docs/design-gap-analysis.md G20).' AS attestationScope
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
    NULL, SYSUTCDATETIME(), SYSUTCDATETIME()
FROM #g20_records g
WHERE NOT EXISTS (SELECT 1 FROM dbo.governance_requests gr WHERE gr.request_id = g.request_id);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_requests.';
GO

-- 2) governance_events: one attested event per record.
INSERT INTO dbo.governance_events (
    request_id, event_type, event_status, source_system, source_event_id,
    actor_id, occurred_at, observed_at, payload
)
SELECT
    g.request_id, g.request_type + 'Attested', 'Completed', 'Purview',
    g.request_id + ':' + g.request_type + 'Attested',
    g.decided_by, SYSUTCDATETIME(), SYSUTCDATETIME(),
    (SELECT g.target_object_label AS targetLabel, g.evidence_note AS evidenceNote
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #g20_records g
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_events ge
    WHERE ge.source_system = 'Purview' AND ge.source_event_id = g.request_id + ':' + g.request_type + 'Attested'
);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_events.';
GO

-- 3) governance_target_receipts: attested, not machine-verified.
INSERT INTO dbo.governance_target_receipts (
    request_id, target_system, target_object_type, target_object_id,
    receipt_type, expected_hash, observed_hash, validation_status, evidence_payload
)
SELECT
    g.request_id, 'Purview', g.target_object_type, g.target_object_id,
    'OperatorAttested' + g.request_type, NULL, NULL, 'Passed',
    (SELECT g.evidence_note AS evidenceNote, g.decided_by AS attestedBy,
            'Attested by the operator against this repo''s own live-confirmed state (SQL query / repo memory) -- deliberately not a new interactive workflow, per 2026-08-13 scope decision.' AS attestationNote
     FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #g20_records g
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.governance_target_receipts gtr
    WHERE gtr.request_id = g.request_id AND gtr.receipt_type = 'OperatorAttested' + g.request_type
);

PRINT 'Inserted ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s) into dbo.governance_target_receipts.';
GO

DROP TABLE #g20_records;
GO

PRINT 'G20 synthetic governance attestation complete.';
GO
