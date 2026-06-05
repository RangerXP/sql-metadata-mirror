/*
================================================================================
Purpose:
  Create SQL-first governance metadata tables so Purview/Fabric metadata can be
  maintained in SQL and mirrored into OneLake.

Pattern:
  - dbo.governance_* tables are the source-of-truth in sqldemo.
  - Fabric mirrored database reflects these tables.
  - nb_07a can read mirrored SQL first and only fall back to CSV bootstrap.
================================================================================
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.governance_domains', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_domains (
        domain_id                    VARCHAR(64)   NOT NULL,
        domain_name                  NVARCHAR(200) NOT NULL,
        domain_type                  VARCHAR(64)   NOT NULL,
        description                  NVARCHAR(1000) NULL,
        parent_domain                VARCHAR(64)   NULL,
        status                       VARCHAR(32)   NOT NULL,
        governance_domain_owners     NVARCHAR(1000) NULL,
        governance_domain_creators   NVARCHAR(1000) NULL,
        CONSTRAINT PK_governance_domains PRIMARY KEY CLUSTERED (domain_id)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_data_products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_data_products (
        data_product_id              VARCHAR(64)   NOT NULL,
        data_product_name            NVARCHAR(200) NOT NULL,
        product_type                 VARCHAR(64)   NOT NULL,
        business_use_case            NVARCHAR(1000) NULL,
        audience                     NVARCHAR(400) NULL,
        owners                       NVARCHAR(1000) NULL,
        attached_assets              NVARCHAR(MAX) NULL,
        access_policy                NVARCHAR(MAX) NULL,
        status                       VARCHAR(32)   NOT NULL,
        parent_domain_id             VARCHAR(64)   NOT NULL,
        CONSTRAINT PK_governance_data_products PRIMARY KEY CLUSTERED (data_product_id)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_glossary_terms', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_glossary_terms (
        term_code                    VARCHAR(64)   NOT NULL,
        term_name                    NVARCHAR(200) NOT NULL,
        acronyms                     NVARCHAR(200) NULL,
        parent_term_code             VARCHAR(64)   NULL,
        domain_code                  VARCHAR(64)   NULL,
        owner_upn                    VARCHAR(255)  NULL,
        additional_owners_upn        NVARCHAR(1000) NULL,
        definition                   NVARCHAR(MAX) NOT NULL,
        status                       VARCHAR(32)   NOT NULL,
        is_cde                       BIT           NOT NULL,
        industry_origin              VARCHAR(64)   NULL,
        resources                    NVARCHAR(MAX) NULL,
        bound_assets                 NVARCHAR(MAX) NULL,
        CONSTRAINT PK_governance_glossary_terms PRIMARY KEY CLUSTERED (term_code)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_cdes', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_cdes (
        cde_id                       VARCHAR(64)   NOT NULL,
        cde_name                     NVARCHAR(200) NOT NULL,
        expected_data_type           VARCHAR(32)   NOT NULL,
        business_definition          NVARCHAR(MAX) NOT NULL,
        owner_role                   VARCHAR(128)  NULL,
        status                       VARCHAR(32)   NOT NULL,
        parent_glossary_term         VARCHAR(64)   NULL,
        bound_columns                NVARCHAR(MAX) NULL,
        CONSTRAINT PK_governance_cdes PRIMARY KEY CLUSTERED (cde_id)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_role_assignments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_role_assignments (
        role_id                      VARCHAR(64)   NOT NULL,
        principal_email              VARCHAR(255)  NOT NULL,
        principal_display_name       NVARCHAR(200) NOT NULL,
        role_type                    VARCHAR(128)  NOT NULL,
        scope_target                 NVARCHAR(300) NOT NULL,
        scope_target_type            VARCHAR(64)   NOT NULL,
        governance_layer             VARCHAR(64)   NOT NULL,
        CONSTRAINT PK_governance_role_assignments PRIMARY KEY CLUSTERED (role_id)
    );
END
GO

IF OBJECT_ID(N'dbo.governance_label_assignments', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.governance_label_assignments (
        label_id                     VARCHAR(64)   NOT NULL,
        label_name                   NVARCHAR(200) NOT NULL,
        sensitivity_tier             VARCHAR(64)   NOT NULL,
        protection_policy            NVARCHAR(MAX) NULL,
        applies_to_asset_ids         NVARCHAR(MAX) NULL,
        scope                        VARCHAR(128)  NOT NULL,
        CONSTRAINT PK_governance_label_assignments PRIMARY KEY CLUSTERED (label_id)
    );
END
GO

PRINT 'Purview metadata schema tables are ready.';
GO
