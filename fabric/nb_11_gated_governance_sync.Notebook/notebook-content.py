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
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Fabric Notebook: nb_11_gated_governance_sync
# Phase 4 Milestone P4-4 (docs/Enercare-Demo-SemPy-Design-Guide.md SS5D)
# Purpose: automated "apply on approve" step for the gated-governance workflow.
#
# Reads dbo.governance_change_requests directly from the sub2 Azure SQL source
# (not the lh_metadata mirror copy, to avoid acting on stale Approved status),
# dispatches each Approved/unapplied row by request_type to the target governed
# object, then stamps status='Applied'/applied_at back on the SQL source.
#
# Run after: an operator has moved a request from PendingApproval to Approved
# (see docs/runbooks/phase4-gated-governance-workflow.md step 2 per scenario).
# Run before: nb_04_sempy_writeback -> nb_05_push_qa_verified_answers ->
#             nb_07_publish_to_purview / nb_08 / nb_09 -> nb_10 rescoring.
# This notebook only performs the APPLY step; the downstream re-publish chain
# remains a separate manual run per docs/design-gap-analysis.md G13-5 (deferred).
#
# DEMO_MODE = True  -> print every planned mutation; no SQL/Delta writes
# DEMO_MODE = False -> execute the apply + status-stamp writes live

DEMO_MODE = True            # default safe mode; set False only for a live scenario run

METADATA_LAKEHOUSE = "lh_metadata"
MODEL_NAME         = "BrookfieldEnercare"
SERVER_NAME        = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME      = "sqldemo"
SQL_PORT           = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE      = "tokenlibrary"  # tokenlibrary | managed_identity

print(f"nb_11 | DEMO_MODE={DEMO_MODE} | lakehouse={METADATA_LAKEHOUSE} | sql={SERVER_NAME}/{DATABASE_NAME}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: SQL connection helpers (same auth pattern as nb_05a_publish_synthetic_data_to_sql)

import json
import struct
import time
from datetime import date

import pyodbc

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256


def get_sql_access_token():
    scopes = ["https://database.windows.net/", "https://database.windows.net"]
    last_error = None
    for scope in scopes:
        started_at = time.time()
        try:
            token = mssparkutils.credentials.getToken(scope)
            print(f"Acquired Azure SQL token for scope: {scope} in {round(time.time() - started_at, 1)}s")
            return token
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError("Azure SQL token acquisition failed.")


def get_sql_connection():
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    if SQL_AUTH_MODE == "managed_identity":
        conn_str += "Authentication=ActiveDirectoryMsi;"
        return pyodbc.connect(conn_str, autocommit=False)

    access_token = get_sql_access_token()
    odbc_token = access_token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(odbc_token)}s", len(odbc_token), odbc_token)
    return pyodbc.connect(conn_str, attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct}, autocommit=False)


if DEMO_MODE:
    print("[DEMO_MODE] Skipping live SQL connection setup.")
else:
    sql_conn = get_sql_connection()
    print("SQL connection established for Phase 4 apply step.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read Approved / unapplied requests directly from the SQL source

sql_select_pending_apply = """
SELECT request_id, request_type, domain_id, target_object_id, target_object_label,
       change_summary, proposed_payload, previous_payload, requested_by_upn,
       approver_upn, approved_at
FROM dbo.governance_change_requests
WHERE status = 'Approved' AND applied_at IS NULL
ORDER BY approved_at
""".strip()

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_select_pending_apply)
    # Fabric-mirrored read-only copy stands in for a live SQL read during dry runs.
    pending_df = spark.sql(
        f"SELECT * FROM {METADATA_LAKEHOUSE}.governance_change_requests "
        "WHERE status = 'Approved' AND applied_at IS NULL ORDER BY approved_at"
    ).toPandas()
else:
    cursor = sql_conn.cursor()
    cursor.execute(sql_select_pending_apply)
    columns = [c[0] for c in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    import pandas as pd
    pending_df = pd.DataFrame(rows, columns=columns)

print(f"Pending apply: {len(pending_df)} request(s)")
if len(pending_df) > 0:
    print(pending_df[["request_id", "request_type", "target_object_label"]].to_string(index=False))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Apply-step dispatch handlers, one per request_type

applied_request_ids = []
failed_requests = []


def _load_payload(raw_json: str) -> dict:
    return json.loads(raw_json) if raw_json else {}


def apply_kpi_approval(request_id, target_object_id, payload, approver_upn):
    kpi_code = payload.get("KPICode", target_object_id)
    set_clauses = ["IsCertified = 1", f"CertifiedBy = '{approver_upn}'", "CertifiedDate = current_date()"]
    if "Version" in payload:
        set_clauses.append(f"Version = {int(payload['Version'])}")
    if "PreviousFormula" in payload and payload["PreviousFormula"] is not None:
        escaped = str(payload["PreviousFormula"]).replace("'", "''")
        set_clauses.append(f"PreviousFormula = '{escaped}'")
    if "Description" in payload and payload["Description"] is not None:
        escaped = str(payload["Description"]).replace("'", "''")
        set_clauses.append(f"Description = '{escaped}'")
    if "WarningThreshold" in payload:
        set_clauses.append(f"WarningThreshold = {float(payload['WarningThreshold'])}")
    if "CriticalThreshold" in payload:
        set_clauses.append(f"CriticalThreshold = {float(payload['CriticalThreshold'])}")

    sql_update = (
        f"UPDATE {METADATA_LAKEHOUSE}.kpi_metadata SET {', '.join(set_clauses)} "
        f"WHERE KPICode = '{kpi_code}'"
    )
    if DEMO_MODE:
        print(f"[DEMO_MODE] [{request_id}] Would execute:\n{sql_update}")
    else:
        spark.sql(sql_update)
        print(f"[{request_id}] kpi_metadata updated for KPICode={kpi_code}")


def apply_verified_answer_certification(request_id, payload, approver_upn):
    from pyspark.sql import Row
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DateType

    if DEMO_MODE:
        next_id = -1
    else:
        next_id_row = spark.sql(f"SELECT COALESCE(MAX(RecordID), 0) + 1 AS next_id FROM {METADATA_LAKEHOUSE}.ai_metadata").first()
        next_id = int(next_id_row["next_id"])

    row = Row(
        RecordID=next_id,
        ModelName=MODEL_NAME,
        RecordType=payload.get("RecordType", "verified_answer"),
        TriggerText=payload.get("TriggerText"),
        ResponseText=payload.get("ResponseText"),
        LinkedKPICode=payload.get("LinkedKPICode"),
        IsDraft=0,
        CreatedDate=date.today(),
        IsCertified=1,
        CertifiedBy=approver_upn,
        CertifiedDate=date.today(),
    )
    if DEMO_MODE:
        print(f"[DEMO_MODE] [{request_id}] Would append to ai_metadata:\n{row.asDict()}")
    else:
        schema = StructType([
            StructField("RecordID", IntegerType(), True),
            StructField("ModelName", StringType(), True),
            StructField("RecordType", StringType(), True),
            StructField("TriggerText", StringType(), True),
            StructField("ResponseText", StringType(), True),
            StructField("LinkedKPICode", StringType(), True),
            StructField("IsDraft", IntegerType(), True),
            StructField("CreatedDate", DateType(), True),
            StructField("IsCertified", IntegerType(), True),
            StructField("CertifiedBy", StringType(), True),
            StructField("CertifiedDate", DateType(), True),
        ])
        spark.createDataFrame([row], schema=schema).write.format("delta").mode("append") \
            .saveAsTable(f"{METADATA_LAKEHOUSE}.ai_metadata")
        print(f"[{request_id}] ai_metadata appended: RecordID={next_id}")


def apply_cde_classification(request_id, payload, requested_by_upn, approver_upn):
    sql_insert = """
    INSERT INTO dbo.governance_cdes
        (cde_id, cde_name, expected_data_type, business_definition, owner_role, steward_upn, status,
         parent_glossary_term, bound_columns, classification_approved_by, classification_approved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
    """.strip()
    params = (
        payload.get("cde_id"), payload.get("cde_name"), payload.get("expected_data_type"),
        payload.get("business_definition"), payload.get("owner_role"), requested_by_upn,
        payload.get("status"), payload.get("parent_glossary_term"), payload.get("bound_columns"),
        approver_upn,
    )
    if DEMO_MODE:
        print(f"[DEMO_MODE] [{request_id}] Would execute:\n{sql_insert}\nparams={params}")
    else:
        cursor = sql_conn.cursor()
        cursor.execute(sql_insert, params)
        print(f"[{request_id}] governance_cdes row inserted: cde_id={payload.get('cde_id')}")


def apply_glossary_term_definition(request_id, payload, approver_upn):
    sql_insert = """
    INSERT INTO dbo.governance_glossary_terms
        (term_code, term_name, parent_term_code, domain_code, owner_upn, additional_owners_upn,
         definition, status, is_cde, industry_origin, resources, bound_assets, approved_by, approved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
    """.strip()
    params = (
        payload.get("term_code"), payload.get("term_name"), payload.get("parent_term_code"),
        payload.get("domain_code"), payload.get("owner_upn"), payload.get("additional_owners_upn"),
        payload.get("definition"), payload.get("status"), int(bool(payload.get("is_cde"))),
        payload.get("industry_origin"), payload.get("resources"), payload.get("bound_assets"),
        approver_upn,
    )
    if DEMO_MODE:
        print(f"[DEMO_MODE] [{request_id}] Would execute:\n{sql_insert}\nparams={params}")
    else:
        cursor = sql_conn.cursor()
        cursor.execute(sql_insert, params)
        print(f"[{request_id}] governance_glossary_terms row inserted: term_code={payload.get('term_code')}")


def stamp_applied(request_id):
    sql_update = (
        "UPDATE dbo.governance_change_requests "
        "SET status = 'Applied', applied_at = SYSUTCDATETIME() "
        "WHERE request_id = ?"
    )
    if DEMO_MODE:
        print(f"[DEMO_MODE] [{request_id}] Would execute:\n{sql_update}\nparams=({request_id},)")
    else:
        cursor = sql_conn.cursor()
        cursor.execute(sql_update, (request_id,))
        print(f"[{request_id}] governance_change_requests stamped status=Applied")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Dispatch loop - one request at a time, continue past individual failures

DISPATCH = {
    "KPI_APPROVAL": lambda r, payload: apply_kpi_approval(r["request_id"], r["target_object_id"], payload, r["approver_upn"]),
    "VERIFIED_ANSWER_CERTIFICATION": lambda r, payload: apply_verified_answer_certification(r["request_id"], payload, r["approver_upn"]),
    "CDE_CLASSIFICATION": lambda r, payload: apply_cde_classification(r["request_id"], payload, r["requested_by_upn"], r["approver_upn"]),
    "GLOSSARY_TERM_DEFINITION": lambda r, payload: apply_glossary_term_definition(r["request_id"], payload, r["approver_upn"]),
}

for _, request in pending_df.iterrows():
    request_id = request["request_id"]
    request_type = request["request_type"]
    try:
        payload = _load_payload(request["proposed_payload"])
        handler = DISPATCH.get(request_type)
        if handler is None:
            raise ValueError(f"Unknown request_type: {request_type}")
        handler(request, payload)
        stamp_applied(request_id)
        applied_request_ids.append(request_id)
    except Exception as exc:
        print(f"[{request_id}] FAILED: {exc}")
        failed_requests.append((request_id, str(exc)))

if not DEMO_MODE:
    if failed_requests:
        sql_conn.rollback()
        print(f"Rolled back — {len(failed_requests)} request(s) failed: {failed_requests}")
    else:
        sql_conn.commit()
        print(f"Committed — {len(applied_request_ids)} request(s) applied: {applied_request_ids}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Next-step guidance (downstream re-publish chain remains a manual run — G13-5)

print("Apply step complete.")
print(f"Applied: {applied_request_ids}")
print(f"Failed:  {failed_requests}")
print("")
print("Next: re-run in order to propagate the certified change downstream —")
print("  1. nb_07a_ingest_customer_files   (refresh lh_metadata.metadata.governance_cdes / governance_glossary_terms / governance_change_requests)")
print("  2. nb_04_sempy_writeback          (push certification into the semantic model)")
print("  3. nb_05_push_qa_verified_answers (refresh Data Agent verified answers)")
print("  4. nb_07_publish_to_purview / nb_08_purview_glossary_cde / nb_09_purview_labels_lineage (re-publish to Purview)")
print("  5. nb_10_purview_stewardship_ai   (confirm 0 ACTION_REQUIRED)")
