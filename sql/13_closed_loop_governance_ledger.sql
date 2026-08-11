/*
================================================================================
Purpose:
  Durable SQL ledger for the native-first closed-loop governance architecture.
  Microsoft Purview remains the approval authority for supported publication
  workflows; these tables preserve normalized request state, immutable events,
  governed versions, target receipts, and stable cross-system object mappings.

Scope:
  Additive P0/P1 foundation. This script does not replace the legacy
  dbo.governance_change_requests table or create a SQL approval interface.
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.governance_requests', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_requests (
        request_id                 VARCHAR(64)     NOT NULL,
        request_type               VARCHAR(64)     NOT NULL,
        authority                  VARCHAR(32)     NOT NULL,
        authority_request_id       VARCHAR(128)    NULL,
        target_system              VARCHAR(32)     NOT NULL,
        target_object_type         VARCHAR(64)     NOT NULL,
        target_object_id           VARCHAR(256)    NOT NULL,
        target_object_label        NVARCHAR(256)   NOT NULL,
        requested_by               VARCHAR(255)    NULL,
        requested_at               DATETIME2(7)    NULL,
        decided_by                 VARCHAR(255)    NULL,
        decided_at                 DATETIME2(7)    NULL,
        current_status             VARCHAR(32)     NOT NULL,
        proposed_payload           NVARCHAR(MAX)   NULL,
        source_snapshot            NVARCHAR(MAX)   NULL,
        last_observed_at           DATETIME2(7)    NOT NULL CONSTRAINT DF_governance_requests_last_observed_at DEFAULT SYSUTCDATETIME(),
        completed_at               DATETIME2(7)    NULL,
        failure_reason             NVARCHAR(2000)  NULL,
        CONSTRAINT PK_governance_requests PRIMARY KEY CLUSTERED (request_id),
        CONSTRAINT CK_governance_requests_authority CHECK (authority IN ('Purview','SQL')),
        CONSTRAINT CK_governance_requests_status CHECK (
            current_status IN ('Draft','Submitted','PendingApproval','Approved','Applying','Validated','Completed','Rejected','Failed','Superseded')
        ),
        CONSTRAINT CK_governance_requests_proposed_payload_json CHECK (proposed_payload IS NULL OR ISJSON(proposed_payload) = 1),
        CONSTRAINT CK_governance_requests_source_snapshot_json CHECK (source_snapshot IS NULL OR ISJSON(source_snapshot) = 1)
    );

    CREATE INDEX IX_governance_requests_status
        ON dbo.governance_requests (current_status, last_observed_at)
        INCLUDE (authority, target_object_type, target_object_id);

    CREATE UNIQUE INDEX UX_governance_requests_authority_request
        ON dbo.governance_requests (authority, authority_request_id)
        WHERE authority_request_id IS NOT NULL;
END
GO

IF OBJECT_ID(N'dbo.governance_events', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_events (
        event_id                   BIGINT          IDENTITY(1,1) NOT NULL,
        request_id                 VARCHAR(64)     NOT NULL,
        event_type                 VARCHAR(64)     NOT NULL,
        event_status               VARCHAR(32)     NOT NULL,
        source_system              VARCHAR(32)     NOT NULL,
        source_event_id            VARCHAR(256)    NOT NULL,
        actor_id                   VARCHAR(255)    NULL,
        occurred_at                DATETIME2(7)    NOT NULL,
        observed_at                DATETIME2(7)    NOT NULL CONSTRAINT DF_governance_events_observed_at DEFAULT SYSUTCDATETIME(),
        payload                    NVARCHAR(MAX)   NULL,
        payload_hash               CHAR(64)        NULL,
        CONSTRAINT PK_governance_events PRIMARY KEY CLUSTERED (event_id),
        CONSTRAINT FK_governance_events_request FOREIGN KEY (request_id) REFERENCES dbo.governance_requests(request_id),
        CONSTRAINT UQ_governance_events_source UNIQUE (source_system, source_event_id),
        CONSTRAINT CK_governance_events_payload_json CHECK (payload IS NULL OR ISJSON(payload) = 1)
    );

    CREATE INDEX IX_governance_events_request
        ON dbo.governance_events (request_id, occurred_at, event_id);
END
GO

IF OBJECT_ID(N'dbo.governed_object_versions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governed_object_versions (
        version_id                 BIGINT          IDENTITY(1,1) NOT NULL,
        request_id                 VARCHAR(64)     NOT NULL,
        source_system              VARCHAR(32)     NOT NULL,
        object_type                VARCHAR(64)     NOT NULL,
        object_id                  VARCHAR(256)    NOT NULL,
        source_version_id          VARCHAR(256)    NOT NULL,
        lifecycle_status           VARCHAR(32)     NOT NULL,
        definition_hash            CHAR(64)        NOT NULL,
        object_payload             NVARCHAR(MAX)   NOT NULL,
        effective_at               DATETIME2(7)    NOT NULL,
        observed_at                DATETIME2(7)    NOT NULL CONSTRAINT DF_governed_object_versions_observed_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_governed_object_versions PRIMARY KEY CLUSTERED (version_id),
        CONSTRAINT FK_governed_object_versions_request FOREIGN KEY (request_id) REFERENCES dbo.governance_requests(request_id),
        CONSTRAINT UQ_governed_object_versions_source UNIQUE (source_system, object_type, object_id, source_version_id),
        CONSTRAINT CK_governed_object_versions_payload_json CHECK (ISJSON(object_payload) = 1)
    );

    CREATE INDEX IX_governed_object_versions_object
        ON dbo.governed_object_versions (source_system, object_type, object_id, effective_at DESC);
END
GO

IF OBJECT_ID(N'dbo.governance_target_receipts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_target_receipts (
        receipt_id                 BIGINT          IDENTITY(1,1) NOT NULL,
        request_id                 VARCHAR(64)     NOT NULL,
        target_system              VARCHAR(32)     NOT NULL,
        target_object_type         VARCHAR(64)     NOT NULL,
        target_object_id           VARCHAR(256)    NOT NULL,
        receipt_type               VARCHAR(64)     NOT NULL,
        expected_hash              CHAR(64)        NULL,
        observed_hash              CHAR(64)        NULL,
        validation_status          VARCHAR(16)     NOT NULL,
        observed_at                DATETIME2(7)    NOT NULL CONSTRAINT DF_governance_target_receipts_observed_at DEFAULT SYSUTCDATETIME(),
        evidence_payload           NVARCHAR(MAX)   NOT NULL,
        CONSTRAINT PK_governance_target_receipts PRIMARY KEY CLUSTERED (receipt_id),
        CONSTRAINT FK_governance_target_receipts_request FOREIGN KEY (request_id) REFERENCES dbo.governance_requests(request_id),
        CONSTRAINT UQ_governance_target_receipts_target UNIQUE (request_id, target_system, target_object_type, target_object_id, receipt_type),
        CONSTRAINT CK_governance_target_receipts_status CHECK (validation_status IN ('Pending','Passed','Failed')),
        CONSTRAINT CK_governance_target_receipts_evidence_json CHECK (ISJSON(evidence_payload) = 1)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_object_mappings', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_object_mappings (
        mapping_id                 BIGINT          IDENTITY(1,1) NOT NULL,
        mapping_type               VARCHAR(64)     NOT NULL,
        source_system              VARCHAR(32)     NOT NULL,
        source_object_type         VARCHAR(64)     NOT NULL,
        source_object_id           VARCHAR(256)    NOT NULL,
        target_system              VARCHAR(32)     NOT NULL,
        target_object_type         VARCHAR(64)     NOT NULL,
        target_object_id           VARCHAR(256)    NOT NULL,
        mapping_status             VARCHAR(16)     NOT NULL CONSTRAINT DF_governance_object_mappings_status DEFAULT 'Active',
        mapping_metadata           NVARCHAR(MAX)   NULL,
        created_at                 DATETIME2(7)    NOT NULL CONSTRAINT DF_governance_object_mappings_created_at DEFAULT SYSUTCDATETIME(),
        last_validated_at          DATETIME2(7)    NULL,
        CONSTRAINT PK_governance_object_mappings PRIMARY KEY CLUSTERED (mapping_id),
        CONSTRAINT UQ_governance_object_mappings_pair UNIQUE (
            mapping_type, source_system, source_object_type, source_object_id,
            target_system, target_object_type, target_object_id
        ),
        CONSTRAINT CK_governance_object_mappings_status CHECK (mapping_status IN ('Active','Inactive','Superseded')),
        CONSTRAINT CK_governance_object_mappings_metadata_json CHECK (mapping_metadata IS NULL OR ISJSON(mapping_metadata) = 1)
    );
END
GO

PRINT 'Native-first closed-loop governance ledger is ready.';
GO