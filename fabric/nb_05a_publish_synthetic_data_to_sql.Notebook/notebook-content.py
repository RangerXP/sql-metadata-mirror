# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e9b09e4e-b7b9-4208-b9ec-bb3433154555",
# META       "default_lakehouse_name": "lh_enercare_demo",
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99",
# META       "known_lakehouses": [
# META         {
# META           "id": "e9b09e4e-b7b9-4208-b9ec-bb3433154555"
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
WORKSPACE_ID              = "b976cac2-7754-4061-88c2-61c0ac016a99"
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
