/*
================================================================================
Purpose:
  Extend the sub2 SQL source schema (sqlserver-sk2wus3.database.windows.net /
  sqldemo) with the columns and tables required to exercise every Purview use
  case in docs/purview-governance-brief.md.

Scope:
  - ALTER on existing 7 tables to add classifiable PII (DOB, SIN partial, GPS,
    payment partials) and a steward owner column.
  - CREATE 6 new tables: employees, customer_consents, customer_complaints,
    service_zones, data_owners_directory, audit_data_access.

Run order:
  1. Run after 02_sub2_sql_source_schema.sql.
  2. Run before 05_seed_purview_demo_data.sql (the seed script).
  3. After Fabric mirror picks up the new shape, re-run nb_03_pbi_star_schema
     to fold the new columns into the gold star schema.

Notes:
  - Net-new columns are NULLable so this script is safe to run on a populated
    database; backfill via the seed script.
  - Foreign keys are added inline; existing seed data must not violate them.
================================================================================
*/

SET NOCOUNT ON;
GO

/* ------------------------------------------------------------------------------
   1. Customer PII extensions
------------------------------------------------------------------------------ */

IF COL_LENGTH('dbo.customers', 'date_of_birth') IS NULL
    ALTER TABLE dbo.customers ADD date_of_birth DATE NULL;
GO

IF COL_LENGTH('dbo.customers', 'sin_last_4') IS NULL
    ALTER TABLE dbo.customers ADD sin_last_4 CHAR(4) NULL;
GO

IF COL_LENGTH('dbo.customers', 'owner_email') IS NULL
    ALTER TABLE dbo.customers ADD owner_email VARCHAR(255) NULL;
GO

IF COL_LENGTH('dbo.customers', 'marketing_consent') IS NULL
    ALTER TABLE dbo.customers ADD marketing_consent BIT NULL;
GO

/* ------------------------------------------------------------------------------
   2. Service account geo coordinates (Confidential — location PII)
------------------------------------------------------------------------------ */

IF COL_LENGTH('dbo.service_accounts', 'latitude') IS NULL
    ALTER TABLE dbo.service_accounts ADD latitude DECIMAL(9, 6) NULL;
GO

IF COL_LENGTH('dbo.service_accounts', 'longitude') IS NULL
    ALTER TABLE dbo.service_accounts ADD longitude DECIMAL(9, 6) NULL;
GO

IF COL_LENGTH('dbo.service_accounts', 'service_zone_code') IS NULL
    ALTER TABLE dbo.service_accounts ADD service_zone_code VARCHAR(16) NULL;
GO

/* ------------------------------------------------------------------------------
   2b. Service request no-show causality (WP-1 backfit for P3I-003)
------------------------------------------------------------------------------ */

IF COL_LENGTH('dbo.service_requests', 'no_show_reason_code') IS NULL
    ALTER TABLE dbo.service_requests ADD no_show_reason_code VARCHAR(64) NULL;
GO

/* ------------------------------------------------------------------------------
   3. Billing PCI / financial partials (Highly Confidential)
------------------------------------------------------------------------------ */

IF COL_LENGTH('dbo.billing_transactions', 'bank_routing_last_4') IS NULL
    ALTER TABLE dbo.billing_transactions ADD bank_routing_last_4 CHAR(4) NULL;
GO

IF COL_LENGTH('dbo.billing_transactions', 'card_pan_last_4') IS NULL
    ALTER TABLE dbo.billing_transactions ADD card_pan_last_4 CHAR(4) NULL;
GO

/* ------------------------------------------------------------------------------
   4. Employees / technicians (resolves service_requests.technician_id)
   - sin_full is intentionally present here to exercise the Canada SIN
     classifier in Purview at the Highly Confidential tier.
------------------------------------------------------------------------------ */

IF OBJECT_ID(N'dbo.employees', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.employees (
        employee_id        INT            NOT NULL,
        upn                VARCHAR(255)   NOT NULL,
        first_name         NVARCHAR(100)  NOT NULL,
        last_name          NVARCHAR(100)  NOT NULL,
        email              VARCHAR(255)   NOT NULL,
        phone              VARCHAR(25)    NULL,
        role               VARCHAR(64)    NOT NULL,
        department         VARCHAR(64)    NOT NULL,
        manager_employee_id INT           NULL,
        hire_date          DATE           NOT NULL,
        sin_full           CHAR(11)       NULL,  -- XXX-XXX-XXX, Canadian SIN
        date_of_birth      DATE           NULL,
        home_postal_code   VARCHAR(10)    NULL,
        is_active          BIT            NOT NULL,
        CONSTRAINT PK_employees PRIMARY KEY CLUSTERED (employee_id),
        CONSTRAINT UQ_employees_upn UNIQUE (upn),
        CONSTRAINT FK_employees_manager FOREIGN KEY (manager_employee_id)
            REFERENCES dbo.employees (employee_id)
    );

    CREATE INDEX IX_employees_role ON dbo.employees (role);
END
GO

/* ------------------------------------------------------------------------------
   5. Service zones (Service Delivery territorial hierarchy)
------------------------------------------------------------------------------ */

IF OBJECT_ID(N'dbo.service_zones', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.service_zones (
        zone_code          VARCHAR(16)    NOT NULL,
        zone_name          NVARCHAR(100)  NOT NULL,
        parent_zone_code   VARCHAR(16)    NULL,
        province           CHAR(2)        NOT NULL,
        zone_manager_upn   VARCHAR(255)   NULL,
        sla_target_minutes INT            NULL,
        CONSTRAINT PK_service_zones PRIMARY KEY CLUSTERED (zone_code),
        CONSTRAINT FK_service_zones_parent FOREIGN KEY (parent_zone_code)
            REFERENCES dbo.service_zones (zone_code)
    );
END
GO

/* ------------------------------------------------------------------------------
   6. Customer consents (PIPEDA / CASL)
------------------------------------------------------------------------------ */

IF OBJECT_ID(N'dbo.customer_consents', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_consents (
        consent_id         INT            NOT NULL,
        customer_id        INT            NOT NULL,
        consent_type       VARCHAR(40)    NOT NULL,  -- Marketing-Email, Marketing-SMS, Data-Sharing, Retention
        consent_status     VARCHAR(16)    NOT NULL,  -- Granted, Withdrawn, Expired
        legal_basis        VARCHAR(40)    NOT NULL,  -- PIPEDA, CASL, ContractNecessity
        granted_date       DATE           NULL,
        withdrawn_date     DATE           NULL,
        source_channel     VARCHAR(40)    NULL,      -- Web, CallCenter, Paper, AppPush
        captured_by_upn    VARCHAR(255)   NULL,
        CONSTRAINT PK_customer_consents PRIMARY KEY CLUSTERED (consent_id),
        CONSTRAINT FK_customer_consents_customer FOREIGN KEY (customer_id)
            REFERENCES dbo.customers (customer_id)
    );

    CREATE INDEX IX_customer_consents_customer_id ON dbo.customer_consents (customer_id);
    CREATE INDEX IX_customer_consents_type_status ON dbo.customer_consents (consent_type, consent_status);
END
GO

/* ------------------------------------------------------------------------------
   7. Customer complaints (Ontario Consumer Protection Act story)
------------------------------------------------------------------------------ */

IF OBJECT_ID(N'dbo.customer_complaints', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_complaints (
        complaint_id       INT            NOT NULL,
        customer_id        INT            NOT NULL,
        service_account_id INT            NULL,
        complaint_type     VARCHAR(40)    NOT NULL,  -- Billing, Service, AutoRenew, Privacy, Other
        severity           VARCHAR(16)    NOT NULL,  -- Low, Medium, High, RegulatorReportable
        opened_date        DATE           NOT NULL,
        closed_date        DATE           NULL,
        status             VARCHAR(24)    NOT NULL,
        assigned_to_upn    VARCHAR(255)   NULL,
        description        NVARCHAR(1000) NULL,
        regulator_case_ref VARCHAR(64)    NULL,
        CONSTRAINT PK_customer_complaints PRIMARY KEY CLUSTERED (complaint_id),
        CONSTRAINT FK_customer_complaints_customer FOREIGN KEY (customer_id)
            REFERENCES dbo.customers (customer_id),
        CONSTRAINT FK_customer_complaints_service_account FOREIGN KEY (service_account_id)
            REFERENCES dbo.service_accounts (service_account_id)
    );

    CREATE INDEX IX_customer_complaints_severity ON dbo.customer_complaints (severity, status);
END
GO

/* ------------------------------------------------------------------------------
   8. Data owners directory (T1 ground-truth for object ownership)
------------------------------------------------------------------------------ */

IF OBJECT_ID(N'dbo.data_owners_directory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.data_owners_directory (
        owner_id           INT            NOT NULL,
        object_schema      VARCHAR(64)    NOT NULL,
        object_name        VARCHAR(128)   NOT NULL,
        object_type        VARCHAR(32)    NOT NULL,  -- Table, View, Procedure
        data_owner_upn     VARCHAR(255)   NOT NULL,
        data_steward_upn   VARCHAR(255)   NOT NULL,
        domain_code        VARCHAR(32)    NOT NULL,  -- joins to domain-charter.csv
        last_reviewed_date DATE           NOT NULL,
        CONSTRAINT PK_data_owners_directory PRIMARY KEY CLUSTERED (owner_id),
        CONSTRAINT UQ_data_owners_directory_object UNIQUE (object_schema, object_name)
    );
END
GO

/* ------------------------------------------------------------------------------
   9. Audit data access (purpose-of-use / data observability story)
------------------------------------------------------------------------------ */

IF OBJECT_ID(N'dbo.audit_data_access', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_data_access (
        audit_id           BIGINT         NOT NULL,
        accessed_at        DATETIME2      NOT NULL,
        accessor_upn       VARCHAR(255)   NOT NULL,
        accessor_role      VARCHAR(64)    NULL,
        object_schema      VARCHAR(64)    NOT NULL,
        object_name        VARCHAR(128)   NOT NULL,
        operation          VARCHAR(16)    NOT NULL,  -- SELECT, EXPORT, MASK
        rows_affected      INT            NULL,
        purpose_of_use     VARCHAR(64)    NULL,      -- BillingSupport, RegulatorReport, MarketingCampaign, DataScience
        contains_pii       BIT            NOT NULL,
        CONSTRAINT PK_audit_data_access PRIMARY KEY CLUSTERED (audit_id)
    );

    CREATE INDEX IX_audit_data_access_accessed_at ON dbo.audit_data_access (accessed_at DESC);
    CREATE INDEX IX_audit_data_access_object ON dbo.audit_data_access (object_schema, object_name);
END
GO

/* ------------------------------------------------------------------------------
   10. Wire foreign keys that depend on now-existing tables
------------------------------------------------------------------------------ */

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_service_requests_employee'
)
ALTER TABLE dbo.service_requests
ADD CONSTRAINT FK_service_requests_employee FOREIGN KEY (technician_id)
    REFERENCES dbo.employees (employee_id);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_service_accounts_service_zone'
)
ALTER TABLE dbo.service_accounts
ADD CONSTRAINT FK_service_accounts_service_zone FOREIGN KEY (service_zone_code)
    REFERENCES dbo.service_zones (zone_code);
GO

PRINT 'Purview demo extensions applied successfully.';
GO
