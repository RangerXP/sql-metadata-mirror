/*
================================================================================
Purpose:
  Phase 4 — Gated Governance & Self-Healing Semantic Model Sync.
  Creates the single audit-trailed workflow table that models a proposed
  metadata change moving through Draft -> PendingApproval -> Approved/Rejected
  -> Applied, for all four gate types used in the demo:
    KPI_APPROVAL | VERIFIED_ANSWER_CERTIFICATION | CDE_CLASSIFICATION | GLOSSARY_TERM_DEFINITION

Pattern:
  - dbo.governance_change_requests is the source-of-truth request/approval log
    in sqldemo, mirrored into Fabric same as the other dbo.governance_* tables.
  - The live governed object (kpi_metadata / ai_metadata / governance_cdes /
    governance_glossary_terms) is only mutated once a request reaches Approved
    and the sync step (07_apply_approved_changes) applies it.
  - approved_by / approved_at companion columns are added to
    governance_cdes and governance_glossary_terms so the "who certified this"
    fact lives on the object itself, not only in the request log.

See: docs/Enercare-Demo-SemPy-Design-Guide.md §5D (Phase 4) and
     docs/runbooks/phase4-gated-governance-workflow.md for the operating workflow.
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.governance_change_requests', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_change_requests (
        request_id            VARCHAR(64)    NOT NULL,
        request_type          VARCHAR(32)    NOT NULL, -- KPI_APPROVAL | VERIFIED_ANSWER_CERTIFICATION | CDE_CLASSIFICATION | GLOSSARY_TERM_DEFINITION
        domain_id              VARCHAR(64)    NULL,     -- FK-style reference to governance_domains.domain_id
        target_object_id       VARCHAR(128)   NULL,     -- KPICode / ai_metadata RecordID / cde_id / term_code (NULL if the request creates a brand-new object)
        target_object_label    NVARCHAR(200)  NOT NULL, -- human-readable name for demo narration
        change_summary         NVARCHAR(500)  NOT NULL,
        proposed_payload       NVARCHAR(MAX)  NOT NULL, -- JSON snapshot of the proposed new values
        previous_payload       NVARCHAR(MAX)  NULL,     -- JSON snapshot of prior values (NULL if new object)
        requested_by_upn       VARCHAR(255)   NOT NULL,
        requested_at           DATETIME2(0)   NOT NULL CONSTRAINT DF_gcr_requested_at DEFAULT SYSUTCDATETIME(),
        status                 VARCHAR(32)    NOT NULL CONSTRAINT DF_gcr_status DEFAULT 'Draft', -- Draft | PendingApproval | Approved | Rejected | Applied
        approver_upn            VARCHAR(255)   NULL,
        approved_at             DATETIME2(0)   NULL,
        rejection_reason        NVARCHAR(500)  NULL,
        applied_at               DATETIME2(0)   NULL,     -- stamped once semantic-model/Purview write-back completes
        CONSTRAINT PK_governance_change_requests PRIMARY KEY CLUSTERED (request_id),
        CONSTRAINT CK_gcr_request_type CHECK (request_type IN ('KPI_APPROVAL','VERIFIED_ANSWER_CERTIFICATION','CDE_CLASSIFICATION','GLOSSARY_TERM_DEFINITION')),
        CONSTRAINT CK_gcr_status CHECK (status IN ('Draft','PendingApproval','Approved','Rejected','Applied'))
    );
END
GO

IF COL_LENGTH('dbo.governance_glossary_terms', 'approved_by') IS NULL
    ALTER TABLE dbo.governance_glossary_terms ADD approved_by VARCHAR(255) NULL;
GO

IF COL_LENGTH('dbo.governance_glossary_terms', 'approved_at') IS NULL
    ALTER TABLE dbo.governance_glossary_terms ADD approved_at DATETIME2(0) NULL;
GO

IF COL_LENGTH('dbo.governance_glossary_terms', 'previous_definition') IS NULL
    ALTER TABLE dbo.governance_glossary_terms ADD previous_definition NVARCHAR(MAX) NULL;
GO

IF COL_LENGTH('dbo.governance_cdes', 'classification_approved_by') IS NULL
    ALTER TABLE dbo.governance_cdes ADD classification_approved_by VARCHAR(255) NULL;
GO

IF COL_LENGTH('dbo.governance_cdes', 'classification_approved_at') IS NULL
    ALTER TABLE dbo.governance_cdes ADD classification_approved_at DATETIME2(0) NULL;
GO

PRINT 'Phase 4 gated-governance schema (governance_change_requests + approval columns) is ready.';
GO
