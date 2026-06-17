# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "7b504b7d-1f16-b228-40d9-2fd30ee837e4",
# META       "default_lakehouse_name": "lh_enercare_demo",
# META       "default_lakehouse_workspace_id": "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4",
# META       "known_lakehouses": [
# META         {
# META           "id": "7b504b7d-1f16-b228-40d9-2fd30ee837e4"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Fabric Notebook: nb_05a_publish_synthetic_data_to_sql
# Purpose: Publish the seven transactional Enercare source tables from
#          lh_enercare_demo into Azure SQL in sub2 so SQL becomes the
#          authoritative mirrored source.
#
# Run after:
#   - nb_01_setup_demo_environment
#   - sql/02_sub2_sql_source_schema.sql executed against sqldemo
#
# DEMO_MODE = True  -> dry-run only
# DEMO_MODE = False -> acquire an Entra token and write rows to Azure SQL

from pyspark.sql import functions as F

DEMO_MODE                 = False
NOTEBOOK_BUILD_TAG        = "2026-06-17 notebook-owned-sql"
DEMO_LAKEHOUSE            = "lh_enercare_demo"
WORKSPACE_ID              = "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4"
SERVER_NAME               = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME             = "sqldemo"
SQL_PORT                  = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
TARGET_SCHEMA             = "dbo"
BASE_TABLE_LOAD_MODE      = "replace"  # replace | append | skip_existing
PHASE_B_CHILD_TABLES      = ["customer_complaints", "customer_consents"]
LOAD_ORDER = [
    "products",
    "customers",
    "service_accounts",
    "equipment_registry",
    "contracts",
    "service_requests",
    "billing_transactions",
]

print(f"nb_05a_publish_synthetic_data_to_sql | DEMO_MODE={DEMO_MODE}")
print(f"Notebook build : {NOTEBOOK_BUILD_TAG}")
print(f"Workspace      : {WORKSPACE_ID}")
print(f"Source lakehouse: {DEMO_LAKEHOUSE}")
print(f"Target SQL DB  : {SERVER_NAME}:{SQL_PORT} / {DATABASE_NAME}")
print(f"Target schema  : {TARGET_SCHEMA}")
print(f"Base load mode : {BASE_TABLE_LOAD_MODE}")
print("Load order     :", ", ".join(LOAD_ORDER))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: JDBC/ODBC config and token helper

import struct
import time
import pyodbc

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256
sql_access_token = None
conn = None

JDBC_URL = (
    f"jdbc:sqlserver://{SERVER_NAME}:{SQL_PORT};"
    f"database={DATABASE_NAME};"
    "encrypt=true;"
    "trustServerCertificate=false;"
    "hostNameInCertificate=*.database.windows.net;"
    f"loginTimeout={SQL_LOGIN_TIMEOUT_SECONDS};"
)


def get_sql_access_token():
    scopes = [
        "https://database.windows.net/",
        "https://database.windows.net",
    ]
    last_error = None
    for scope in scopes:
        started_at = time.time()
        print(f"Requesting Azure SQL token for scope: {scope}")
        try:
            token = mssparkutils.credentials.getToken(scope)
            elapsed_seconds = round(time.time() - started_at, 1)
            print(f"Acquired Azure SQL token for scope: {scope} in {elapsed_seconds} seconds")
            return token
        except Exception as exc:
            elapsed_seconds = round(time.time() - started_at, 1)
            print(f"Token acquisition failed for scope: {scope} after {elapsed_seconds} seconds")
            print(str(exc))
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("Azure SQL token acquisition failed before any token request was attempted.")


def transform_for_sql(table_name, df):
    if table_name == "products":
        return df.withColumn("is_active", F.col("is_active").cast("boolean"))
    if table_name == "contracts":
        return df.withColumn("auto_renew", F.col("auto_renew").cast("boolean"))
    return df


def read_target_count(table_name, access_token):
    target_table = f"{TARGET_SCHEMA}.{table_name}"
    query = f"SELECT COUNT(1) AS row_count FROM {target_table}"
    count_df = (
        spark.read.format("jdbc")
        .option("url", JDBC_URL)
        .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
        .option("query", query)
        .option("accessToken", access_token)
        .load()
    )
    return int(count_df.first()["row_count"])


def get_sql_odbc_connection(access_token):
    odbc_token = access_token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(odbc_token)}s", len(odbc_token), odbc_token)
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    return pyodbc.connect(
        conn_str,
        attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=False,
    )


if DEMO_MODE:
    print("[DRY RUN] Skipping token acquisition.")
else:
    sql_access_token = get_sql_access_token()
    print("Acquired Microsoft Entra access token for Azure SQL.")
    conn = get_sql_odbc_connection(sql_access_token)
    print("pyodbc connection established for SQL control statements.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Source inventory and preflight validation

source_inventory = []
for table_name in LOAD_ORDER:
    source_df = spark.table(f"{DEMO_LAKEHOUSE}.{table_name}")
    source_count = source_df.count()
    source_inventory.append((table_name, source_count))
    print(f"Source table {table_name:<20} {source_count:>5} rows")

inventory_df = spark.createDataFrame(source_inventory, ["table_name", "source_row_count"])
display(inventory_df)

if DEMO_MODE:
    print("[DRY RUN] Execute sql/02_sub2_sql_source_schema.sql before running with DEMO_MODE=False.")
    print("[DRY RUN] This notebook appends rows into the target SQL tables in dependency order.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Publish source tables to Azure SQL


def clear_base_tables(connection):
    cur = connection.cursor()
    print("Clearing base tables in reverse dependency order before reload...")
    for table_name in PHASE_B_CHILD_TABLES:
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        cur.execute("SELECT OBJECT_ID(?)", target_table)
        if cur.fetchone()[0] is not None:
            print(f"  DELETE FROM {target_table}")
            cur.execute(f"DELETE FROM {target_table}")

    for table_name in reversed(LOAD_ORDER):
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        print(f"  DELETE FROM {target_table}")
        cur.execute(f"DELETE FROM {target_table}")
    connection.commit()


def target_matches_source(table_name, source_count, access_token):
    try:
        return read_target_count(table_name, access_token) == source_count
    except Exception:
        return False

if DEMO_MODE:
    print("[DRY RUN] No JDBC writes attempted.")
else:
    if BASE_TABLE_LOAD_MODE not in {"append", "replace", "skip_existing"}:
        raise ValueError("BASE_TABLE_LOAD_MODE must be one of: append, replace, skip_existing")

    if BASE_TABLE_LOAD_MODE == "replace":
        clear_base_tables(conn)

    write_results = []

    for table_name in LOAD_ORDER:
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        source_df = transform_for_sql(table_name, spark.table(f"{DEMO_LAKEHOUSE}.{table_name}"))
        source_count = source_df.count()

        print(f"Writing {table_name} -> {target_table} ({source_count} rows)")

        if BASE_TABLE_LOAD_MODE == "skip_existing" and target_matches_source(table_name, source_count, sql_access_token):
            target_count = read_target_count(table_name, sql_access_token)
            write_results.append((table_name, source_count, target_count, True))
            print(f"Skipped {target_table}: target count already matches source ({target_count})")
            continue

        (
            source_df.write.format("jdbc")
            .option("url", JDBC_URL)
            .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
            .option("dbtable", target_table)
            .option("accessToken", sql_access_token)
            .mode("append")
            .save()
        )

        target_count = read_target_count(table_name, sql_access_token)
        write_results.append((table_name, source_count, target_count, target_count >= source_count))
        print(f"Validated {target_table}: {target_count} rows now present")

    results_df = spark.createDataFrame(
        write_results,
        ["table_name", "source_row_count", "target_row_count", "target_at_least_source"],
    )
    print("Publish complete.")
    display(results_df)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Post-run notes

print("Next steps:")
print("  1. Reconcile exact row counts in Azure SQL after the initial load.")
print("  2. Create SQL views/procs for metadata extraction only after the source tables are stable.")
print("  3. Stand up Fabric mirroring against the Azure SQL source.")
print("  4. If rerunning this load, clear target tables in reverse dependency order first.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell B0: Confirm pyodbc connection for Phase B SQL script execution

if DEMO_MODE:
    print("[DRY RUN] Skipping pyodbc connection setup for Phase B cells.")
else:
    try:
        conn.cursor().execute("SELECT 1")
        print("pyodbc connection ready for Phase B cells.")
    except Exception:
        conn = get_sql_odbc_connection(sql_access_token)
        print("pyodbc connection re-established for Phase B cells.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B0A: Define notebook-owned SQL scripts

PURVIEW_DEMO_EXTENSIONS_SQL = r"""
SET NOCOUNT ON;
GO
IF COL_LENGTH('dbo.customers', 'date_of_birth') IS NULL ALTER TABLE dbo.customers ADD date_of_birth DATE NULL;
GO
IF COL_LENGTH('dbo.customers', 'sin_last_4') IS NULL ALTER TABLE dbo.customers ADD sin_last_4 CHAR(4) NULL;
GO
IF COL_LENGTH('dbo.customers', 'owner_email') IS NULL ALTER TABLE dbo.customers ADD owner_email VARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.customers', 'marketing_consent') IS NULL ALTER TABLE dbo.customers ADD marketing_consent BIT NULL;
GO
IF COL_LENGTH('dbo.service_accounts', 'latitude') IS NULL ALTER TABLE dbo.service_accounts ADD latitude DECIMAL(9, 6) NULL;
GO
IF COL_LENGTH('dbo.service_accounts', 'longitude') IS NULL ALTER TABLE dbo.service_accounts ADD longitude DECIMAL(9, 6) NULL;
GO
IF COL_LENGTH('dbo.service_accounts', 'service_zone_code') IS NULL ALTER TABLE dbo.service_accounts ADD service_zone_code VARCHAR(16) NULL;
GO
IF COL_LENGTH('dbo.billing_transactions', 'bank_routing_last_4') IS NULL ALTER TABLE dbo.billing_transactions ADD bank_routing_last_4 CHAR(4) NULL;
GO
IF COL_LENGTH('dbo.billing_transactions', 'card_pan_last_4') IS NULL ALTER TABLE dbo.billing_transactions ADD card_pan_last_4 CHAR(4) NULL;
GO
IF OBJECT_ID(N'dbo.employees', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.employees (
        employee_id INT NOT NULL,
        upn VARCHAR(255) NOT NULL,
        first_name NVARCHAR(100) NOT NULL,
        last_name NVARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL,
        phone VARCHAR(25) NULL,
        role VARCHAR(64) NOT NULL,
        department VARCHAR(64) NOT NULL,
        manager_employee_id INT NULL,
        hire_date DATE NOT NULL,
        sin_full CHAR(11) NULL,
        date_of_birth DATE NULL,
        home_postal_code VARCHAR(10) NULL,
        is_active BIT NOT NULL,
        CONSTRAINT PK_employees PRIMARY KEY CLUSTERED (employee_id),
        CONSTRAINT UQ_employees_upn UNIQUE (upn)
    );
END
GO
IF OBJECT_ID(N'dbo.service_zones', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.service_zones (
        zone_code VARCHAR(16) NOT NULL,
        zone_name NVARCHAR(100) NOT NULL,
        parent_zone_code VARCHAR(16) NULL,
        province CHAR(2) NOT NULL,
        zone_manager_upn VARCHAR(255) NULL,
        sla_target_minutes INT NULL,
        CONSTRAINT PK_service_zones PRIMARY KEY CLUSTERED (zone_code)
    );
END
GO
IF OBJECT_ID(N'dbo.customer_consents', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_consents (
        consent_id INT NOT NULL,
        customer_id INT NOT NULL,
        consent_type VARCHAR(40) NOT NULL,
        consent_status VARCHAR(16) NOT NULL,
        legal_basis VARCHAR(40) NOT NULL,
        granted_date DATE NULL,
        withdrawn_date DATE NULL,
        source_channel VARCHAR(40) NULL,
        captured_by_upn VARCHAR(255) NULL,
        CONSTRAINT PK_customer_consents PRIMARY KEY CLUSTERED (consent_id),
        CONSTRAINT FK_customer_consents_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers (customer_id)
    );
END
GO
IF OBJECT_ID(N'dbo.customer_complaints', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.customer_complaints (
        complaint_id INT NOT NULL,
        customer_id INT NOT NULL,
        service_account_id INT NULL,
        complaint_type VARCHAR(40) NOT NULL,
        severity VARCHAR(16) NOT NULL,
        opened_date DATE NOT NULL,
        closed_date DATE NULL,
        status VARCHAR(24) NOT NULL,
        assigned_to_upn VARCHAR(255) NULL,
        description NVARCHAR(1000) NULL,
        regulator_case_ref VARCHAR(64) NULL,
        CONSTRAINT PK_customer_complaints PRIMARY KEY CLUSTERED (complaint_id),
        CONSTRAINT FK_customer_complaints_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers (customer_id),
        CONSTRAINT FK_customer_complaints_service_account FOREIGN KEY (service_account_id) REFERENCES dbo.service_accounts (service_account_id)
    );
END
GO
IF OBJECT_ID(N'dbo.data_owners_directory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.data_owners_directory (
        owner_id INT NOT NULL,
        object_schema VARCHAR(64) NOT NULL,
        object_name VARCHAR(128) NOT NULL,
        object_type VARCHAR(32) NOT NULL,
        data_owner_upn VARCHAR(255) NOT NULL,
        data_steward_upn VARCHAR(255) NOT NULL,
        domain_code VARCHAR(32) NOT NULL,
        last_reviewed_date DATE NOT NULL,
        CONSTRAINT PK_data_owners_directory PRIMARY KEY CLUSTERED (owner_id),
        CONSTRAINT UQ_data_owners_directory_object UNIQUE (object_schema, object_name)
    );
END
GO
IF OBJECT_ID(N'dbo.audit_data_access', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_data_access (
        audit_id BIGINT NOT NULL,
        accessed_at DATETIME2 NOT NULL,
        accessor_upn VARCHAR(255) NOT NULL,
        accessor_role VARCHAR(64) NULL,
        object_schema VARCHAR(64) NOT NULL,
        object_name VARCHAR(128) NOT NULL,
        operation VARCHAR(16) NOT NULL,
        rows_affected INT NULL,
        purpose_of_use VARCHAR(64) NULL,
        contains_pii BIT NOT NULL,
        CONSTRAINT PK_audit_data_access PRIMARY KEY CLUSTERED (audit_id)
    );
END
GO
PRINT 'Purview demo extensions applied successfully.';
GO
"""

PURVIEW_DEMO_SEED_SQL = r"""
SET NOCOUNT ON;
GO
DELETE FROM dbo.customer_complaints;
DELETE FROM dbo.customer_consents;
DELETE FROM dbo.audit_data_access;
DELETE FROM dbo.data_owners_directory;
DELETE FROM dbo.employees;
DELETE FROM dbo.service_zones;
GO
INSERT INTO dbo.service_zones (zone_code, zone_name, parent_zone_code, province, zone_manager_upn, sla_target_minutes) VALUES
('CA-ON','Ontario',NULL,'ON','ranbir.singh@enercare.ca',NULL),
('CA-ON-GTA','Greater Toronto Area',NULL,'ON','ranbir.singh@enercare.ca',120),
('CA-ON-GTA-N','GTA North',NULL,'ON','mhuang@enercare.ca',90),
('CA-ON-GTA-S','GTA South',NULL,'ON','mhuang@enercare.ca',90),
('CA-ON-GTA-E','GTA East',NULL,'ON','rpatel@enercare.ca',90),
('CA-ON-GTA-W','GTA West',NULL,'ON','rpatel@enercare.ca',90),
('CA-ON-OTT','Ottawa Region',NULL,'ON','Rupal.Solanki@enercare.ca',150),
('CA-ON-SWO','Southwestern Ontario',NULL,'ON','Rupal.Solanki@enercare.ca',180);
GO
INSERT INTO dbo.employees (employee_id, upn, first_name, last_name, email, phone, role, department, manager_employee_id, hire_date, sin_full, date_of_birth, home_postal_code, is_active) VALUES
(1,'Victoria.Tan@enercare.ca','Victoria','Tan','Victoria.Tan@enercare.ca','+1-416-555-0101','Chief Customer Officer','Executive',NULL,'2016-04-01',NULL,'1976-04-22','M5V',1),
(2,'ranbir.singh@enercare.ca','Ranbir','Singh','ranbir.singh@enercare.ca','+1-416-555-0102','Enercare Leadership Data Plane','Engineering',1,'2020-02-15',NULL,'1981-03-22','M4Y',1),
(3,'Ci.Zhu@enercare.ca','Ci','Zhu','Ci.Zhu@enercare.ca','+1-437-860-6862','Senior Manager Data Strategy','Data Office',1,'2021-06-07',NULL,'1985-11-04','L3R',1),
(4,'Rupal.Solanki@enercare.ca','Rupal','Solanki','Rupal.Solanki@enercare.ca','+1-416-555-0104','Data Steward','Data Office',3,'2020-09-21',NULL,'1979-06-30','M4W',1),
(5,'Shruthi.Srinivas@enercare.ca','Shruthi','Srinivas','Shruthi.Srinivas@enercare.ca','+1-416-555-0105','Data Steward','Data Office',3,'2018-01-10',NULL,'1971-09-15','L4C',1),
(101,'tnguyen@enercare.ca','Tom','Nguyen','tnguyen@enercare.ca','+1-416-555-1101','Service Technician','Field Ops',2,'2022-03-14',NULL,'1990-04-12','L6T',1),
(102,'smehta@enercare.ca','Sneha','Mehta','smehta@enercare.ca','+1-416-555-1102','Service Technician','Field Ops',2,'2021-11-01',NULL,'1988-07-19','L5N',1),
(103,'bfontaine@enercare.ca','Benoit','Fontaine','bfontaine@enercare.ca','+1-416-555-1103','Service Technician','Field Ops',2,'2020-05-08',NULL,'1985-01-25','K2H',1),
(104,'kahmed@enercare.ca','Karim','Ahmed','kahmed@enercare.ca','+1-416-555-1104','Service Technician','Field Ops',2,'2023-02-20',NULL,'1992-12-03','L1S',1),
(105,'mhuang@enercare.ca','Mei','Huang','mhuang@enercare.ca','+1-416-555-1105','Field Supervisor','Field Ops',2,'2019-08-18',NULL,'1983-05-21','L4G',1),
(106,'rpatel@enercare.ca','Rashmi','Patel','rpatel@enercare.ca','+1-416-555-1106','Field Supervisor','Field Ops',2,'2019-10-04',NULL,'1982-09-08','L8N',1);
GO
UPDATE dbo.customers SET date_of_birth = COALESCE(date_of_birth, DATEADD(DAY, -((ABS(CHECKSUM(NEWID())) % 14600) + 7300), CAST(GETDATE() AS DATE))), owner_email = COALESCE(owner_email, CASE customer_id % 3 WHEN 0 THEN 'Rupal.Solanki@enercare.ca' WHEN 1 THEN 'Shruthi.Srinivas@enercare.ca' ELSE 'Ci.Zhu@enercare.ca' END), marketing_consent = COALESCE(marketing_consent, CASE WHEN customer_id % 4 = 0 THEN 0 ELSE 1 END);
GO
UPDATE dbo.service_accounts SET latitude = COALESCE(latitude, 43.4 + (ABS(CHECKSUM(NEWID())) % 700) / 1000.0), longitude = COALESCE(longitude, -79.8 + (ABS(CHECKSUM(NEWID())) % 900) / 1000.0), service_zone_code = COALESCE(service_zone_code, CASE ABS(CHECKSUM(NEWID())) % 6 WHEN 0 THEN 'CA-ON-GTA-N' WHEN 1 THEN 'CA-ON-GTA-S' WHEN 2 THEN 'CA-ON-GTA-E' WHEN 3 THEN 'CA-ON-GTA-W' WHEN 4 THEN 'CA-ON-OTT' ELSE 'CA-ON-SWO' END);
GO
UPDATE dbo.billing_transactions SET bank_routing_last_4 = COALESCE(bank_routing_last_4, RIGHT('0000' + CAST(ABS(CHECKSUM(NEWID())) % 10000 AS VARCHAR(4)), 4)), card_pan_last_4 = COALESCE(card_pan_last_4, RIGHT('0000' + CAST(ABS(CHECKSUM(NEWID())) % 10000 AS VARCHAR(4)), 4));
GO
;WITH n AS (SELECT TOP (30) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects), consent_types AS (SELECT 1 AS k, 'Marketing-Email' AS t, 'CASL' AS lb UNION ALL SELECT 2,'Marketing-SMS','CASL' UNION ALL SELECT 3,'Data-Sharing','PIPEDA' UNION ALL SELECT 4,'Retention','PIPEDA')
INSERT INTO dbo.customer_consents (consent_id, customer_id, consent_type, consent_status, legal_basis, granted_date, withdrawn_date, source_channel, captured_by_upn)
SELECT (n.rn - 1) * 4 + ct.k, n.rn, ct.t, CASE WHEN (n.rn + ct.k) % 5 = 0 THEN 'Withdrawn' ELSE 'Granted' END, ct.lb, DATEADD(DAY, -((n.rn * 7 + ct.k * 13) % 800), CAST(GETDATE() AS DATE)), NULL, 'CallCenter', 'Rupal.Solanki@enercare.ca' FROM n CROSS JOIN consent_types ct;
GO
;WITH n AS (SELECT TOP (18) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.customer_complaints (complaint_id, customer_id, service_account_id, complaint_type, severity, opened_date, closed_date, status, assigned_to_upn, description, regulator_case_ref)
SELECT rn, ((rn * 3) % 50) + 1, NULL, CASE rn % 4 WHEN 0 THEN 'Privacy' WHEN 1 THEN 'Billing' WHEN 2 THEN 'Service' ELSE 'AutoRenew' END, CASE WHEN rn IN (3, 7, 15) THEN 'RegulatorReportable' WHEN rn % 3 = 0 THEN 'High' ELSE 'Medium' END, DATEADD(DAY, -rn, CAST(GETDATE() AS DATE)), NULL, CASE WHEN rn % 3 = 0 THEN 'Escalated' ELSE 'Resolved' END, 'Rupal.Solanki@enercare.ca', CONCAT('Synthetic complaint ', rn), CASE WHEN rn IN (3, 7, 15) THEN CONCAT('REG-2026-', RIGHT(CONCAT('0000', rn), 4)) ELSE NULL END FROM n;
GO
INSERT INTO dbo.data_owners_directory (owner_id, object_schema, object_name, object_type, data_owner_upn, data_steward_upn, domain_code, last_reviewed_date) VALUES
(1,'dbo','customers','Table','Victoria.Tan@enercare.ca','Rupal.Solanki@enercare.ca','DOM-CUSTOPS','2026-05-20'),(2,'dbo','service_accounts','Table','Victoria.Tan@enercare.ca','Rupal.Solanki@enercare.ca','DOM-CUSTOPS','2026-05-20'),(3,'dbo','customer_consents','Table','Victoria.Tan@enercare.ca','Victoria.Tan@enercare.ca','DOM-CUSTOPS','2026-05-20'),(4,'dbo','customer_complaints','Table','Victoria.Tan@enercare.ca','Rupal.Solanki@enercare.ca','DOM-CUSTOPS','2026-05-20'),(5,'dbo','employees','Table','Victoria.Tan@enercare.ca','Victoria.Tan@enercare.ca','DOM-CUSTOPS','2026-05-20'),(6,'dbo','equipment_registry','Table','ranbir.singh@enercare.ca','Shruthi.Srinivas@enercare.ca','DOM-SVCDEL','2026-05-20'),(7,'dbo','service_requests','Table','ranbir.singh@enercare.ca','Shruthi.Srinivas@enercare.ca','DOM-SVCDEL','2026-05-20'),(8,'dbo','service_zones','Table','ranbir.singh@enercare.ca','Shruthi.Srinivas@enercare.ca','DOM-SVCDEL','2026-05-20'),(9,'dbo','products','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-REVCON','2026-05-20'),(10,'dbo','contracts','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-REVCON','2026-05-20'),(11,'dbo','billing_transactions','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-REVCON','2026-05-20'),(12,'dbo','data_owners_directory','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-CUSTOPS','2026-05-20'),(13,'dbo','audit_data_access','Table','Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca','DOM-CUSTOPS','2026-05-20');
GO
;WITH n AS (SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects a CROSS JOIN sys.objects b)
INSERT INTO dbo.audit_data_access (audit_id, accessed_at, accessor_upn, accessor_role, object_schema, object_name, operation, rows_affected, purpose_of_use, contains_pii)
SELECT rn, DATEADD(HOUR, -rn, SYSUTCDATETIME()), CASE rn % 5 WHEN 0 THEN 'Victoria.Tan@enercare.ca' WHEN 1 THEN 'Ci.Zhu@enercare.ca' WHEN 2 THEN 'Rupal.Solanki@enercare.ca' WHEN 3 THEN 'Shruthi.Srinivas@enercare.ca' ELSE 'ranbir.singh@enercare.ca' END, 'Data Reader', 'dbo', CASE rn % 6 WHEN 0 THEN 'customers' WHEN 1 THEN 'service_accounts' WHEN 2 THEN 'billing_transactions' WHEN 3 THEN 'customer_consents' WHEN 4 THEN 'service_requests' ELSE 'contracts' END, 'SELECT', 1 + (rn % 100), CASE rn % 4 WHEN 0 THEN 'BillingSupport' WHEN 1 THEN 'RegulatorReport' WHEN 2 THEN 'MarketingCampaign' ELSE 'DataScience' END, CASE WHEN rn % 6 IN (0, 1, 2, 3) THEN 1 ELSE 0 END FROM n;
GO
PRINT 'Purview demo seed complete.';
GO
"""

PURVIEW_METADATA_SCHEMA_SQL = r"""
SET NOCOUNT ON;
GO
IF OBJECT_ID(N'dbo.governance_domains', N'U') IS NULL CREATE TABLE dbo.governance_domains (domain_id VARCHAR(64) NOT NULL, domain_name NVARCHAR(200) NOT NULL, domain_type VARCHAR(64) NOT NULL, description NVARCHAR(1000) NULL, parent_domain VARCHAR(64) NULL, status VARCHAR(32) NOT NULL, governance_domain_owners NVARCHAR(1000) NULL, governance_domain_creators NVARCHAR(1000) NULL, CONSTRAINT PK_governance_domains PRIMARY KEY CLUSTERED (domain_id));
GO
IF OBJECT_ID(N'dbo.governance_data_products', N'U') IS NULL CREATE TABLE dbo.governance_data_products (data_product_id VARCHAR(64) NOT NULL, data_product_name NVARCHAR(200) NOT NULL, product_type VARCHAR(64) NOT NULL, business_use_case NVARCHAR(1000) NULL, audience NVARCHAR(400) NULL, owners NVARCHAR(1000) NULL, attached_assets NVARCHAR(MAX) NULL, access_policy NVARCHAR(MAX) NULL, status VARCHAR(32) NOT NULL, parent_domain_id VARCHAR(64) NOT NULL, CONSTRAINT PK_governance_data_products PRIMARY KEY CLUSTERED (data_product_id));
GO
IF OBJECT_ID(N'dbo.governance_glossary_terms', N'U') IS NULL CREATE TABLE dbo.governance_glossary_terms (term_code VARCHAR(64) NOT NULL, term_name NVARCHAR(200) NOT NULL, acronyms NVARCHAR(200) NULL, parent_term_code VARCHAR(64) NULL, domain_code VARCHAR(64) NULL, owner_upn VARCHAR(255) NULL, additional_owners_upn NVARCHAR(1000) NULL, definition NVARCHAR(MAX) NOT NULL, status VARCHAR(32) NOT NULL, is_cde BIT NOT NULL, industry_origin VARCHAR(64) NULL, resources NVARCHAR(MAX) NULL, bound_assets NVARCHAR(MAX) NULL, CONSTRAINT PK_governance_glossary_terms PRIMARY KEY CLUSTERED (term_code));
GO
IF OBJECT_ID(N'dbo.governance_cdes', N'U') IS NULL CREATE TABLE dbo.governance_cdes (cde_id VARCHAR(64) NOT NULL, cde_name NVARCHAR(200) NOT NULL, expected_data_type VARCHAR(32) NOT NULL, business_definition NVARCHAR(MAX) NOT NULL, owner_role VARCHAR(128) NULL, status VARCHAR(32) NOT NULL, parent_glossary_term VARCHAR(64) NULL, bound_columns NVARCHAR(MAX) NULL, CONSTRAINT PK_governance_cdes PRIMARY KEY CLUSTERED (cde_id));
GO
IF OBJECT_ID(N'dbo.governance_role_assignments', N'U') IS NULL CREATE TABLE dbo.governance_role_assignments (role_id VARCHAR(64) NOT NULL, principal_email VARCHAR(255) NOT NULL, principal_display_name NVARCHAR(200) NOT NULL, role_type VARCHAR(128) NOT NULL, scope_target NVARCHAR(300) NOT NULL, scope_target_type VARCHAR(64) NOT NULL, governance_layer VARCHAR(64) NOT NULL, CONSTRAINT PK_governance_role_assignments PRIMARY KEY CLUSTERED (role_id));
GO
IF OBJECT_ID(N'dbo.governance_label_assignments', N'U') IS NULL CREATE TABLE dbo.governance_label_assignments (label_id VARCHAR(64) NOT NULL, label_name NVARCHAR(200) NOT NULL, sensitivity_tier VARCHAR(64) NOT NULL, protection_policy NVARCHAR(MAX) NULL, applies_to_asset_ids NVARCHAR(MAX) NULL, scope VARCHAR(128) NOT NULL, CONSTRAINT PK_governance_label_assignments PRIMARY KEY CLUSTERED (label_id));
GO
PRINT 'Purview metadata schema tables are ready.';
GO
"""

PURVIEW_METADATA_SEED_SQL = r"""
SET NOCOUNT ON;
GO
DELETE FROM dbo.governance_label_assignments; DELETE FROM dbo.governance_role_assignments; DELETE FROM dbo.governance_cdes; DELETE FROM dbo.governance_glossary_terms; DELETE FROM dbo.governance_data_products; DELETE FROM dbo.governance_domains;
GO
INSERT INTO dbo.governance_domains (domain_id, domain_name, domain_type, description, parent_domain, status, governance_domain_owners, governance_domain_creators) VALUES ('DOM-CUSTOPS','Customer Operations','Data domain','Customer support, consent, complaint, and profile stewardship domain.',NULL,'Published','Victoria.Tan@enercare.ca;Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com'),('DOM-SVCDEL','Service Delivery','Data domain','Field service scheduling, work-order execution, and SLA governance.',NULL,'Published','ranbir.singh@enercare.ca;Ci.Zhu@enercare.ca','Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com'),('DOM-REVCON','Revenue and Contracts','Data domain','Billing, contracts, renewals, and financial governance domain.',NULL,'Published','Ci.Zhu@enercare.ca;ranbir.singh@enercare.ca','Ci.Zhu@enercare.ca;Alison.Pouw@microsoft.com');
GO
INSERT INTO dbo.governance_data_products (data_product_id, data_product_name, product_type, business_use_case, audience, owners, attached_assets, access_policy, status, parent_domain_id) VALUES ('DP-CUST360','Customer 360','Master and reference data','Single customer profile and consent posture for call-center and compliance operations.','Call Center;Privacy;Leadership','Victoria.Tan@enercare.ca','dbo.customers;dbo.customer_consents;BrookfieldEnercare/dim_customer','Role-based access with privacy approval for regulated attributes.','Published','DOM-CUSTOPS'),('DP-SVCPERF','Service Performance','Dataset','Track service request performance, technician throughput, and SLA adherence.','Field Operations;Leadership','ranbir.singh@enercare.ca','dbo.service_requests;dbo.service_accounts;dbo.service_zones;BrookfieldEnercare/fct_service_requests','Operational use for service planning and SLA management.','Published','DOM-SVCDEL'),('DP-BILLHEALTH','Billing Health','Dataset','Monitor billing accuracy, repeat complaints, and contract renewal outcomes.','Finance;Customer Care;Leadership','Ci.Zhu@enercare.ca','dbo.billing_transactions;dbo.contracts;dbo.customer_complaints;BrookfieldEnercare/fct_billing','Access requires finance and governance approval for sensitive fields.','Published','DOM-REVCON');
GO
;WITH n AS (SELECT TOP (35) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.governance_glossary_terms (term_code, term_name, acronyms, parent_term_code, domain_code, owner_upn, additional_owners_upn, definition, status, is_cde, industry_origin, resources, bound_assets)
SELECT CONCAT('GT-', RIGHT(CONCAT('000', rn), 3)), CASE rn WHEN 1 THEN 'Customer' WHEN 2 THEN 'Social Insurance Number' WHEN 3 THEN 'Customer Consent' WHEN 4 THEN 'PCI Scope Data' WHEN 5 THEN 'Service Request' WHEN 6 THEN 'First Contact Resolution' WHEN 7 THEN 'Contract' WHEN 8 THEN 'Billing Transaction' WHEN 9 THEN 'Data Owner' WHEN 10 THEN 'Data Access Audit' ELSE CONCAT('Governance Term ', rn) END, CASE rn WHEN 2 THEN 'SIN' WHEN 4 THEN 'PCI' WHEN 6 THEN 'FCR' ELSE NULL END, NULL, CASE rn % 3 WHEN 0 THEN 'DOM-REVCON' WHEN 1 THEN 'DOM-CUSTOPS' ELSE 'DOM-SVCDEL' END, 'Ci.Zhu@enercare.ca', 'Victoria.Tan@enercare.ca', CONCAT('Notebook-owned governance term definition ', rn), 'Published', CASE WHEN rn <= 12 THEN 1 ELSE 0 END, 'Generic', 'internal://glossary/notebook', CASE rn WHEN 1 THEN 'dbo.customers.customer_id' WHEN 2 THEN 'dbo.employees.sin_full;dbo.customers.sin_last_4' WHEN 3 THEN 'dbo.customer_consents' WHEN 4 THEN 'dbo.billing_transactions.card_pan_last_4;dbo.billing_transactions.bank_routing_last_4' WHEN 5 THEN 'dbo.service_requests' WHEN 6 THEN 'BrookfieldEnercare/_Measures/FCR' ELSE 'dbo.customers;dbo.service_requests' END FROM n;
GO
INSERT INTO dbo.governance_cdes (cde_id, cde_name, expected_data_type, business_definition, owner_role, status, parent_glossary_term, bound_columns) VALUES ('CDE-CUST-ID','Customer Identifier','number','Unique enterprise identifier for customer entities.','Data Steward','Published','GT-001','dbo.customers.customer_id'),('CDE-SVCACCT-ID','Service Account Identifier','number','Unique identifier for service account records.','Data Steward','Published','GT-005','dbo.service_accounts.service_account_id'),('CDE-CONTRACT-ID','Contract Identifier','number','Unique identifier for customer contracts.','Data Steward','Published','GT-007','dbo.contracts.contract_id'),('CDE-REQ-ID','Service Request Identifier','number','Unique service request key.','Data Steward','Published','GT-005','dbo.service_requests.request_id'),('CDE-CONSENT-STATUS','Consent Status','text','Current legal status of customer consent record.','Privacy Officer','Published','GT-003','dbo.customer_consents.consent_status'),('CDE-SIN','Social Insurance Number','text','Canadian SIN full or partial representation.','Privacy Officer','Published','GT-002','dbo.employees.sin_full;dbo.customers.sin_last_4'),('CDE-DOB','Date Of Birth','date','Customer date of birth for identity and eligibility checks.','Privacy Officer','Published','GT-001','dbo.customers.date_of_birth'),('CDE-GEO','Geo Coordinates','text','Service account latitude and longitude values.','Data Steward','Published','GT-001','dbo.service_accounts.latitude;dbo.service_accounts.longitude'),('CDE-PAN-LAST4','Card PAN Last 4','text','Last four digits of payment card number.','Finance Steward','Published','GT-004','dbo.billing_transactions.card_pan_last_4'),('CDE-BANK-LAST4','Bank Routing Last 4','text','Last four digits of bank routing details.','Finance Steward','Published','GT-004','dbo.billing_transactions.bank_routing_last_4'),('CDE-OWNER-UPN','Data Owner UPN','text','UPN of assigned data owner for governed object.','Data Governance Admin','Published','GT-009','dbo.data_owners_directory.data_owner_upn'),('CDE-AUDIT-PURPOSE','Audit Purpose Of Use','text','Declared purpose for data access event.','Data Governance Admin','Published','GT-010','dbo.audit_data_access.purpose_of_use');
GO
;WITH n AS (SELECT TOP (48) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.governance_role_assignments (role_id, principal_email, principal_display_name, role_type, scope_target, scope_target_type, governance_layer)
SELECT CONCAT('R', RIGHT(CONCAT('000', rn), 3)), CASE rn % 6 WHEN 0 THEN 'seankelley@microsoft.com' WHEN 1 THEN 'Ci.Zhu@enercare.ca' WHEN 2 THEN 'Victoria.Tan@enercare.ca' WHEN 3 THEN 'ranbir.singh@enercare.ca' WHEN 4 THEN 'Rupal.Solanki@enercare.ca' ELSE 'Shruthi.Srinivas@enercare.ca' END, CONCAT('Governance Principal ', rn), CASE rn % 5 WHEN 0 THEN 'Data Governance Administrator' WHEN 1 THEN 'Governance Domain Owner' WHEN 2 THEN 'Data Product Owner' WHEN 3 THEN 'Data Steward' ELSE 'Global Catalog Reader' END, CASE rn % 4 WHEN 0 THEN 'Enercare' WHEN 1 THEN 'DOM-CUSTOPS' WHEN 2 THEN 'DOM-SVCDEL' ELSE 'DOM-REVCON' END, CASE WHEN rn % 4 = 0 THEN 'Collection' ELSE 'Domain' END, CASE WHEN rn % 4 = 0 THEN 'Tenant' ELSE 'Domain' END FROM n;
GO
;WITH n AS (SELECT TOP (9) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS rn FROM sys.objects)
INSERT INTO dbo.governance_label_assignments (label_id, label_name, sensitivity_tier, protection_policy, applies_to_asset_ids, scope)
SELECT CONCAT('LBL-', RIGHT(CONCAT('000', rn), 3)), CASE rn WHEN 1 THEN 'General' WHEN 2 THEN 'Internal' WHEN 3 THEN 'Confidential' WHEN 4 THEN 'Highly Confidential' WHEN 5 THEN 'PCI Restricted' WHEN 6 THEN 'Privacy Restricted' WHEN 7 THEN 'Operations Sensitive' WHEN 8 THEN 'Executive KPI' ELSE 'Governance Admin' END, CASE WHEN rn IN (4,5,6) THEN 'Highly Confidential' WHEN rn IN (3,7,9) THEN 'Confidential' WHEN rn = 1 THEN 'General' ELSE 'Internal' END, 'Notebook-owned policy seed.', CASE rn WHEN 4 THEN 'dbo.employees.sin_full;dbo.customers.sin_last_4' WHEN 5 THEN 'dbo.billing_transactions.card_pan_last_4' ELSE 'dbo.customers;BrookfieldEnercare.SemanticModel' END, 'Tenant' FROM n;
GO
PRINT 'Purview SQL-first metadata seed complete.';
GO
"""

print("B0A complete. SQL scripts are defined inline in this notebook; no Lakehouse Files upload is required.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B1 — Execute notebook-owned Purview demo extension DDL


def split_sql_batches(script: str) -> list[str]:
    batches = []
    current = []
    for line in script.splitlines():
        if line.strip().upper() == "GO":
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    tail = "\n".join(current).strip()
    if tail:
        batches.append(tail)
    return batches


if DEMO_MODE:
    print("[DRY RUN] Skipping notebook-owned Purview demo extension DDL")
else:
    batches = split_sql_batches(PURVIEW_DEMO_EXTENSIONS_SQL)
    print(f"DDL script: {len(batches)} batches to execute")

    cur = conn.cursor()
    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            conn.commit()
        except Exception as e:
            print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")

    print("DDL applied: notebook-owned Purview demo extensions")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B2 — Verify DDL applied

verify_ddl_sql = """
SELECT 'new tables present'                    AS check_name,
       COUNT(*)                                AS count_actual,
       6                                       AS count_expected
  FROM sys.tables
 WHERE name IN ('employees','service_zones','customer_consents',
                'customer_complaints','data_owners_directory','audit_data_access')
UNION ALL
SELECT 'customers PII columns added',
       CASE WHEN COL_LENGTH('dbo.customers','date_of_birth')   IS NOT NULL
              AND COL_LENGTH('dbo.customers','sin_last_4')     IS NOT NULL
              AND COL_LENGTH('dbo.customers','owner_email')    IS NOT NULL
              AND COL_LENGTH('dbo.customers','marketing_consent') IS NOT NULL
            THEN 4 ELSE 0 END,
       4
UNION ALL
SELECT 'service_accounts GPS columns added',
       CASE WHEN COL_LENGTH('dbo.service_accounts','latitude')          IS NOT NULL
              AND COL_LENGTH('dbo.service_accounts','longitude')         IS NOT NULL
              AND COL_LENGTH('dbo.service_accounts','service_zone_code') IS NOT NULL
            THEN 3 ELSE 0 END,
       3
UNION ALL
SELECT 'billing_transactions payment partials added',
       CASE WHEN COL_LENGTH('dbo.billing_transactions','bank_routing_last_4') IS NOT NULL
              AND COL_LENGTH('dbo.billing_transactions','card_pan_last_4')    IS NOT NULL
            THEN 2 ELSE 0 END,
       2;
"""

if DEMO_MODE:
    print("[DRY RUN] Skipping DDL verification query.")
else:
    cur.execute(verify_ddl_sql)
    rows = cur.fetchall()
    print(f"\n{'check_name':45s} {'actual':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "RED"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B3 — Execute notebook-owned Purview demo seed data

if DEMO_MODE:
    print("[DRY RUN] Skipping notebook-owned Purview demo seed data")
else:
    batches = split_sql_batches(PURVIEW_DEMO_SEED_SQL)
    print(f"Seed script: {len(batches)} batches to execute")

    cur = conn.cursor()
    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            conn.commit()
        except Exception as e:
            print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")

    print("Seed applied: notebook-owned Purview demo seed data")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B4 — Verify seed counts

verify_seed_sql = """
SELECT 'employees'              AS table_name, COUNT(*) AS row_count, 11  AS expected FROM dbo.employees
UNION ALL
SELECT 'service_zones',                        COUNT(*),                8      FROM dbo.service_zones
UNION ALL
SELECT 'customer_consents',                    COUNT(*),              120      FROM dbo.customer_consents
UNION ALL
SELECT 'customer_complaints',                  COUNT(*),               18      FROM dbo.customer_complaints
UNION ALL
SELECT 'data_owners_directory',                COUNT(*),               13      FROM dbo.data_owners_directory
UNION ALL
SELECT 'audit_data_access',                    COUNT(*),              200      FROM dbo.audit_data_access
UNION ALL
SELECT 'customers with DOB backfilled',        COUNT(*),               50      FROM dbo.customers
 WHERE date_of_birth IS NOT NULL
UNION ALL
SELECT 'service_accounts with GPS backfilled', COUNT(*),               56      FROM dbo.service_accounts
 WHERE latitude IS NOT NULL;
"""

if DEMO_MODE:
    print("[DRY RUN] Skipping seed verification query.")
else:
    cur.execute(verify_seed_sql)
    rows = cur.fetchall()
    print(f"\n{'table_name':45s} {'rows':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "YELLOW"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B4A — Execute notebook-owned SQL-first metadata schema and seed


def execute_sql_script(sql_script: str, friendly_name: str) -> None:
    batches = split_sql_batches(sql_script)
    print(f"{friendly_name}: {len(batches)} batches to execute")

    local_cur = conn.cursor()
    for i, batch in enumerate(batches, 1):
        try:
            local_cur.execute(batch)
            conn.commit()
        except Exception as e:
            print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")


if DEMO_MODE:
    print("[DRY RUN] Skipping notebook-owned metadata schema/seed execution")
else:
    execute_sql_script(PURVIEW_METADATA_SCHEMA_SQL, "Metadata schema")
    print("DDL applied: notebook-owned Purview metadata schema")

    execute_sql_script(PURVIEW_METADATA_SEED_SQL, "Metadata seed")
    print("Seed applied: notebook-owned Purview metadata seed")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B4B — Verify SQL-first metadata row counts

verify_metadata_sql = """
SELECT 'governance_domains'          AS table_name, COUNT(*) AS row_count,  3 AS expected FROM dbo.governance_domains
UNION ALL
SELECT 'governance_data_products',                    COUNT(*),              3               FROM dbo.governance_data_products
UNION ALL
SELECT 'governance_glossary_terms',                   COUNT(*),             35               FROM dbo.governance_glossary_terms
UNION ALL
SELECT 'governance_cdes',                             COUNT(*),             12               FROM dbo.governance_cdes
UNION ALL
SELECT 'governance_role_assignments',                 COUNT(*),             48               FROM dbo.governance_role_assignments
UNION ALL
SELECT 'governance_label_assignments',                COUNT(*),              9               FROM dbo.governance_label_assignments;
"""

if DEMO_MODE:
    print("[DRY RUN] Skipping metadata row count verification.")
else:
    cur.execute(verify_metadata_sql)
    rows = cur.fetchall()
    print(f"\n{'table_name':45s} {'rows':>8s} {'expected':>10s}  status")
    print("-" * 80)
    for r in rows:
        status = "GREEN" if r[1] == r[2] else "YELLOW"
        print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B5 — Backfill Luhn-valid SIN fields

import sys
import random

TOOLS_PATH = "/lakehouse/default/Files/tools"
if TOOLS_PATH not in sys.path:
    sys.path.insert(0, TOOLS_PATH)

try:
    from sin_luhn_generator import generate_synthetic_sin, hyphenated, is_luhn_valid  # noqa: E402
    print("Using sin_luhn_generator from Lakehouse Files/tools.")
except Exception:
    print("Optional sin_luhn_generator not found in Lakehouse Files/tools; using built-in notebook SIN helper fallback.")

    def _digits(value: str) -> str:
        return "".join(ch for ch in str(value) if ch.isdigit())

    def _luhn_check_digit(eight_digits: str) -> str:
        total = 0
        for i, ch in enumerate(reversed(eight_digits), start=1):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return str((10 - (total % 10)) % 10)

    def is_luhn_valid(sin_value: str) -> bool:
        digits = _digits(sin_value)
        if len(digits) != 9:
            return False
        return _luhn_check_digit(digits[:8]) == digits[8]

    def generate_synthetic_sin(first_digit: str = "9", rng: random.Random | None = None) -> str:
        rng = rng or random.Random()
        prefix = first_digit if first_digit and first_digit.isdigit() else "9"
        body = "".join(str(rng.randint(0, 9)) for _ in range(7))
        first_eight = f"{prefix}{body}"
        return first_eight + _luhn_check_digit(first_eight)

    def hyphenated(sin_value: str) -> str:
        digits = _digits(sin_value)
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:9]}"

if DEMO_MODE:
    print("[DRY RUN] Skipping SIN backfill updates.")
else:
    rng = random.Random(20260605)

    cur.execute("SELECT employee_id FROM dbo.employees WHERE sin_full IS NULL")
    emp_ids = [row[0] for row in cur.fetchall()]
    print(f"Backfilling sin_full for {len(emp_ids)} employees...")

    for emp_id in emp_ids:
        sin9 = generate_synthetic_sin(first_digit="9", rng=rng)
        cur.execute(
            "UPDATE dbo.employees SET sin_full = ? WHERE employee_id = ?",
            hyphenated(sin9), emp_id,
        )
    conn.commit()
    print(f"  employees.sin_full populated: {len(emp_ids)} rows")

    cur.execute("SELECT customer_id FROM dbo.customers WHERE sin_last_4 IS NULL")
    cust_ids = [row[0] for row in cur.fetchall()]
    print(f"Backfilling sin_last_4 for {len(cust_ids)} customers...")

    for cust_id in cust_ids:
        sin9 = generate_synthetic_sin(first_digit="9", rng=rng)
        cur.execute(
            "UPDATE dbo.customers SET sin_last_4 = ? WHERE customer_id = ?",
            sin9[-4:], cust_id,
        )
    conn.commit()
    print(f"  customers.sin_last_4 populated: {len(cust_ids)} rows")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B6 — Spot-check SIN Luhn validity

if DEMO_MODE:
    print("[DRY RUN] Skipping SIN validity spot-check.")
else:
    cur.execute("SELECT TOP 5 employee_id, sin_full FROM dbo.employees ORDER BY NEWID()")
    samples = cur.fetchall()

    print("\nSIN Luhn validation spot-check (Layer 1 backstop):")
    print(f"{'employee_id':>12s}  {'sin_full':>15s}  result")
    print("-" * 45)
    all_valid = True
    for emp_id, sin_full in samples:
        valid = is_luhn_valid(sin_full)
        all_valid = all_valid and valid
        print(f"{emp_id:>12d}  {sin_full:>15s}  {'GREEN' if valid else 'RED'}")

    print(f"\nOverall: {'ALL GREEN — Layer 1 backstop ready' if all_valid else 'RED — investigate generator'}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
