# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "824f4a52-baa0-4c3f-88dc-203c1d85c89a",
# META       "default_lakehouse_name": "lh_metadata",
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99",
# META       "known_lakehouses": [
# META         {
# META           "id": "824f4a52-baa0-4c3f-88dc-203c1d85c89a"
# META         },
# META         {
# META           "id": "e9b09e4e-b7b9-4208-b9ec-bb3433154555"
# META         }
# META       ]
# META     },
# META     "warehouse": {
# META       "known_warehouses": []
# META     }
# META   }
# META }

# CELL ********************

import struct
from datetime import datetime, timezone

import pyodbc
from pyspark.sql.types import StringType, StructField, StructType

# ---------------------------------------------------------------------------
# G18-A thin reader: SOURCE_TAG_DETECTED rows are extracted natively in SQL
# (sql/19_tag_annotation_extraction.sql's dbo.usp_extract_tag_annotations,
# fired automatically by trg_tag_annotation_extraction on view/proc DDL) and
# land as Draft/Submitted rows in dbo.governance_requests. This notebook's
# only job is to surface those pending rows into lh_metadata for stewards to
# review -- it does NOT parse, approve, or apply anything itself.
#
# REPLACES the previous standalone Python/regex @tag-parsing prototype that
# lived in this notebook (hardcoded SQL_MODULES dict + HEADER_RE parser +
# unconditional overwrites of asset_metadata/column_metadata/kpi_metadata).
# That prototype was never wired to production and has been fully removed;
# the original content is preserved at
# tools/backups/nb_02_metadata_pipeline_demo.notebook-content.ORIGINAL-2026-08-13.py.bak
# for reference/restore if ever needed.
# ---------------------------------------------------------------------------

META_LAKEHOUSE = "lh_metadata"
DETECTIONS_TABLE = f"{META_LAKEHOUSE}.source_tag_detections"  # new, dedicated table -- does not
                                                                # share a name with any existing
                                                                # governed table (kpi_metadata,
                                                                # ai_metadata, asset_metadata, etc.)

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30

DEMO_MODE = True  # default safe mode; set False only for a live read + upsert run

print(f"DEMO_MODE         : {DEMO_MODE}")
print(f"Metadata lakehouse: {META_LAKEHOUSE}")
print(f"Detections table  : {DETECTIONS_TABLE}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256


def get_sql_connection():
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    token = mssparkutils.credentials.getToken("https://database.windows.net/")
    encoded_token = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(encoded_token)}s", len(encoded_token), encoded_token)
    return pyodbc.connect(
        connection_string,
        attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=False,
    )


# Read-only: pending (not yet decided) SOURCE_TAG_DETECTED requests, straight from the
# unified governance ledger -- no separate staging table, per the append-only/
# one-current-state-row contract in docs/closed-loop-governance-reference-model.md.
connection = get_sql_connection()
cursor = connection.cursor()
try:
    cursor.execute(
        """
        SELECT request_id, target_object_id, target_object_label, current_status,
               requested_by, requested_at, proposed_payload
        FROM dbo.governance_requests
        WHERE request_type = 'SourceTagAnnotationDetected'
          AND current_status IN ('Draft', 'Submitted')
        """
    )
    pending_rows = cursor.fetchall()
finally:
    cursor.close()
    connection.close()

print(f"Pending SOURCE_TAG_DETECTED rows: {len(pending_rows)}")
for row in pending_rows:
    print(f"  {row.request_id}  {row.target_object_id}  status={row.current_status}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

detections_schema = StructType([
    StructField("RequestId", StringType(), False),
    StructField("TargetObjectId", StringType(), False),
    StructField("TargetObjectLabel", StringType(), True),
    StructField("CurrentStatus", StringType(), False),
    StructField("RequestedBy", StringType(), True),
    StructField("RequestedAtUtc", StringType(), True),
    StructField("ProposedPayloadJson", StringType(), True),
    StructField("LastReadUtc", StringType(), False),
])

read_at = datetime.now(timezone.utc).isoformat()
detection_rows = [
    (
        row.request_id,
        row.target_object_id,
        row.target_object_label,
        row.current_status,
        row.requested_by,
        row.requested_at.isoformat() if row.requested_at else None,
        row.proposed_payload,
        read_at,
    )
    for row in pending_rows
]

if DEMO_MODE:
    print(f"[DEMO_MODE] Would upsert {len(detection_rows)} row(s) into {DETECTIONS_TABLE}; no write performed.")
else:
    df_detections = spark.createDataFrame(detection_rows, schema=detections_schema)
    df_detections.write.format("delta").mode("overwrite").saveAsTable(DETECTIONS_TABLE)
    print(f"{DETECTIONS_TABLE}: {df_detections.count()} row(s) written (pending steward review).")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

