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

# Fabric Notebook: nb_05b_test_sql_connectivity
# Purpose: Minimal JDBC smoke test for sqlserver-sk2wus3 over the Enercare
#          workspace managed private endpoint.
#
# DEMO_MODE = True  -> dry-run only
# DEMO_MODE = False -> acquire an Entra token and run a small query
#
# This notebook intentionally avoids hardcoded secrets. If token-based auth
# is not available for the notebook runtime identity, use a Key Vault-backed
# secret path outside this repo.

DEMO_MODE                  = False
WORKSPACE_ID               = "b976cac2-7754-4061-88c2-61c0ac016a99"
SERVER_NAME                = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME              = "sqldemo"
SQL_PORT                   = 1433
SQL_LOGIN_TIMEOUT_SECONDS  = 30
TEST_QUERY                 = "SELECT 1 AS connectivity_check"

print(f"nb_05b_test_sql_connectivity | DEMO_MODE={DEMO_MODE}")
print(f"Workspace: {WORKSPACE_ID}")
print(f"Target: {SERVER_NAME}:{SQL_PORT} / {DATABASE_NAME}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Build JDBC config and acquire token

import base64
import json

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
        try:
            return mssparkutils.credentials.getToken(scope)
        except Exception as exc:
            last_error = exc
    raise last_error


def describe_access_token(token: str):
    payload = token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload + padding))
    return {
        "aud": claims.get("aud"),
        "appid": claims.get("appid"),
        "name": claims.get("name"),
        "oid": claims.get("oid"),
        "scp": claims.get("scp"),
        "tid": claims.get("tid"),
        "upn": claims.get("upn"),
    }


print("JDBC URL prepared.")
print(f"Smoke-test query: {TEST_QUERY}")

if DEMO_MODE:
    print("[DRY RUN] Skipping token acquisition and JDBC call.")
    print("[DRY RUN] Switch DEMO_MODE=False to run the query through the workspace managed private endpoint.")
else:
    sql_access_token = get_sql_access_token()
    print("Acquired Microsoft Entra access token for Azure SQL.")
    print("Token identity claims:")
    print(describe_access_token(sql_access_token))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Execute minimal JDBC connectivity test

if DEMO_MODE:
    print("[DRY RUN] No JDBC connection attempted.")
else:
    try:
        test_df = (
            spark.read.format("jdbc")
            .option("url", JDBC_URL)
            .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver")
            .option("query", TEST_QUERY)
            .option("accessToken", sql_access_token)
            .load()
        )

        print("JDBC connectivity test succeeded.")
        print(f"Rows returned: {test_df.count()}")
        display(test_df)
    except Exception as exc:
        print("JDBC connectivity reached Azure SQL but the database rejected the principal.")
        print("Provision the token identity as an external user in the target database, then rerun the notebook.")
        print("Suggested SQL as the Entra admin:")
        print("  CREATE USER [<upn-or-display-name>] FROM EXTERNAL PROVIDER;")
        print("  ALTER ROLE db_datareader ADD MEMBER [<upn-or-display-name>];")
        raise

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
