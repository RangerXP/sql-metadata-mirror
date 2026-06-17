# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "0ee837e4-2fd3-40d9-b228-1f167b504b7d",
# META       "default_lakehouse_name": "lh_enercare_demo",
# META       "default_lakehouse_workspace_id": "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4",
# META       "known_lakehouses": [
# META         {
# META           "id": "0ee837e4-2fd3-40d9-b228-1f167b504b7d"
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
DEMO_LAKEHOUSE            = "lh_enercare_demo"
WORKSPACE_ID              = "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4"
SERVER_NAME               = "sqlserver-sk2.database.windows.net"
DATABASE_NAME             = "sqldemo"
SQL_PORT                  = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
TARGET_SCHEMA             = "dbo"
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
print(f"Workspace      : {WORKSPACE_ID}")
print(f"Source lakehouse: {DEMO_LAKEHOUSE}")
print(f"Target SQL DB  : {SERVER_NAME}:{SQL_PORT} / {DATABASE_NAME}")
print(f"Target schema  : {TARGET_SCHEMA}")
print("Load order     :", ", ".join(LOAD_ORDER))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: JDBC config and token helper

import time

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
    raise last_error


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


if DEMO_MODE:
    print("[DRY RUN] Skipping token acquisition.")
else:
    sql_access_token = get_sql_access_token()
    print("Acquired Microsoft Entra access token for Azure SQL.")


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

if DEMO_MODE:
    print("[DRY RUN] No JDBC writes attempted.")
else:
    write_results = []

    for table_name in LOAD_ORDER:
        target_table = f"{TARGET_SCHEMA}.{table_name}"
        source_df = transform_for_sql(table_name, spark.table(f"{DEMO_LAKEHOUSE}.{table_name}"))
        source_count = source_df.count()

        print(f"Writing {table_name} -> {target_table} ({source_count} rows)")

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

# Cell B0: Build pyodbc connection for Phase B SQL script execution

import struct
import pyodbc

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256

if DEMO_MODE:
    print("[DRY RUN] Skipping pyodbc connection setup for Phase B cells.")
else:
    odbc_token = get_sql_access_token().encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(odbc_token)}s", len(odbc_token), odbc_token)
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    conn = pyodbc.connect(
        conn_str,
        attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=False,
    )
    print("pyodbc connection established for Phase B cells.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B0A: Validate required SQL script files in Lakehouse Files

from pathlib import Path

FILES_SQL_ROOT = Path("/lakehouse/default/Files/sql")
REQUIRED_SQL_FILES = [
    "04_purview_demo_extensions.sql",
    "05_seed_purview_demo_data.sql",
    "06_purview_metadata_schema.sql",
    "07_seed_purview_metadata.sql",
]

missing_sql_files = [name for name in REQUIRED_SQL_FILES if not (FILES_SQL_ROOT / name).exists()]

if missing_sql_files:
    raise FileNotFoundError(
        "Missing SQL scripts in Lakehouse Files/sql: "
        + ", ".join(missing_sql_files)
        + ". Upload sql/04-07 from this repo into /lakehouse/default/Files/sql and rerun B0A."
    )

print("B0A preflight complete. SQL scripts available:")
for name in REQUIRED_SQL_FILES:
    print(f"  - {FILES_SQL_ROOT / name}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# CELL B1 — Execute sql/04_purview_demo_extensions.sql (DDL)

import os

SQL_REPO_ROOT = "/lakehouse/default/Files/sql"
DDL_FILE = os.path.join(SQL_REPO_ROOT, "04_purview_demo_extensions.sql")


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
    print("[DRY RUN] Skipping DDL execution for 04_purview_demo_extensions.sql")
else:
    with open(DDL_FILE, "r", encoding="utf-8") as f:
        ddl_script = f.read()

    batches = split_sql_batches(ddl_script)
    print(f"DDL script: {len(batches)} batches to execute")

    cur = conn.cursor()
    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            conn.commit()
        except Exception as e:
            print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")

    print("DDL applied: 04_purview_demo_extensions.sql")


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

# CELL B3 — Execute sql/05_seed_purview_demo_data.sql (seed data)

SEED_FILE = os.path.join(SQL_REPO_ROOT, "05_seed_purview_demo_data.sql")

if DEMO_MODE:
    print("[DRY RUN] Skipping seed execution for 05_seed_purview_demo_data.sql")
else:
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        seed_script = f.read()

    batches = split_sql_batches(seed_script)
    print(f"Seed script: {len(batches)} batches to execute")

    cur = conn.cursor()
    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            conn.commit()
        except Exception as e:
            print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")

    print("Seed applied: 05_seed_purview_demo_data.sql")


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

# CELL B4A — Execute SQL-first metadata scripts (06 schema + 07 seed)

METADATA_SCHEMA_FILE = os.path.join(SQL_REPO_ROOT, "06_purview_metadata_schema.sql")
METADATA_SEED_FILE = os.path.join(SQL_REPO_ROOT, "07_seed_purview_metadata.sql")


def execute_sql_file(sql_file_path: str, friendly_name: str) -> None:
    with open(sql_file_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

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
    print("[DRY RUN] Skipping metadata schema/seed execution for 06/07 SQL scripts")
else:
    execute_sql_file(METADATA_SCHEMA_FILE, "Metadata schema")
    print("DDL applied: 06_purview_metadata_schema.sql")

    execute_sql_file(METADATA_SEED_FILE, "Metadata seed")
    print("Seed applied: 07_seed_purview_metadata.sql")


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
    print("sin_luhn_generator not found. Using notebook-local SIN helper fallback.")

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
