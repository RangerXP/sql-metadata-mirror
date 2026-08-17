/*
================================================================================
Purpose:
  Extend the Purview governance metadata schema with the business-objective
  layer (Objectives and Key Results), closing the OKR half of G11-1 (formal
  ontology / typed relationships) in docs/design-gap-analysis.md.

Why OKRs:
  Microsoft Purview Unified Catalog's native OKR business concept links
  directly to Data Products ("Related data products") and to Governance
  Domains, giving a real typed-relationship edge from a business outcome
  down to the governed data that measures it. This repo already has the
  reverse edges (CDE -> GlossaryTerm via parent_glossary_term, GlossaryTerm ->
  Domain via domain_code, DataProduct -> Domain via parent_domain_id) but had
  no business-objective layer above the Data Product tier.

Note on domain hierarchy:
  dbo.governance_domains.parent_domain has existed since sql/02_metadata_foundation/06_purview_metadata_schema.sql
  (Purview Unified Catalog domain hierarchy supports up to 5 levels). This build keeps
  the existing 3 seeded domains flat and does not add a root domain — the
  established "3 domains" count is referenced throughout docs/slides/scripts
  and is out of scope for the OKR/ontology work. parent_domain remains
  available for a future hierarchy demo without any schema change needed.

Pattern:
  - dbo.governance_* tables remain the source-of-truth in sqldemo.
  - Fabric mirrored database reflects these tables.
  - 02_build_metadata_foundation ingests them into lh_metadata.metadata.*;
    05_publish_governance_domains publishes OKRs live to Purview (Atlas custom
    typedefs, consistent with the existing
    EnercareGovernanceDomain/EnercareDataProduct pattern) with
    relationshipAttributes-style links to Data Products.
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.governance_okrs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_okrs (
        okr_id            VARCHAR(64)    NOT NULL,
        okr_name           NVARCHAR(200)  NOT NULL,
        domain_id          VARCHAR(64)    NOT NULL,
        definition         NVARCHAR(1000) NOT NULL,
        owner_upn          VARCHAR(255)   NOT NULL,
        target_date        DATE           NULL,
        status             VARCHAR(32)    NOT NULL,
        CONSTRAINT PK_governance_okrs PRIMARY KEY CLUSTERED (okr_id),
        CONSTRAINT FK_governance_okrs_domain FOREIGN KEY (domain_id)
            REFERENCES dbo.governance_domains (domain_id)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_okr_key_results', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_okr_key_results (
        key_result_id      VARCHAR(64)    NOT NULL,
        okr_id             VARCHAR(64)    NOT NULL,
        result_name        NVARCHAR(200)  NOT NULL,
        -- KPICode in lh_metadata.kpi_metadata, or a BrookfieldEnercare/_Measures/<name>
        -- asset ref when the metric is only published as a semantic measure entity.
        metric_source      VARCHAR(200)   NOT NULL,
        goal_amount        DECIMAL(10, 2) NOT NULL,
        progress_amount    DECIMAL(10, 2) NULL,
        max_amount         DECIMAL(10, 2) NOT NULL,
        progress_status    VARCHAR(32)    NOT NULL,
        CONSTRAINT PK_governance_okr_key_results PRIMARY KEY CLUSTERED (key_result_id),
        CONSTRAINT FK_governance_okr_key_results_okr FOREIGN KEY (okr_id)
            REFERENCES dbo.governance_okrs (okr_id)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_okr_data_products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_okr_data_products (
        okr_id             VARCHAR(64)   NOT NULL,
        data_product_id    VARCHAR(64)   NOT NULL,
        CONSTRAINT PK_governance_okr_data_products PRIMARY KEY CLUSTERED (okr_id, data_product_id),
        CONSTRAINT FK_governance_okr_data_products_okr FOREIGN KEY (okr_id)
            REFERENCES dbo.governance_okrs (okr_id),
        CONSTRAINT FK_governance_okr_data_products_product FOREIGN KEY (data_product_id)
            REFERENCES dbo.governance_data_products (data_product_id)
    );
END
GO

PRINT 'Ontology/OKR schema is ready.';
GO
