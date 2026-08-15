# Fabric notebook source
# Consolidated notebook stage: 10_reset_demo.Notebook
# Source sections are retained in lifecycle order.

# ===== BEGIN SOURCE: archive/nb_18_demo_reset.Notebook =====


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

# Fabric Notebook: nb_18_demo_reset
# Purpose: G19 demo-repeatability -- move every G19 demo request back to its pre-decision
# status (Submitted / PendingApproval / Approved-not-yet-applied, matching each workstream's
# own starting point) and undo the specific field changes THAT decision caused, so the whole
# G19 approval narrative can be re-demoed live, indefinitely, without re-running any SQL setup
# scripts.
#
# Explicit scope decisions (user direction, 2026-08-13):
#   - This is about REQUEST STATUS, not deleting anything. No governed object row is ever
#     deleted by this notebook.
#   - The two disposable demo objects (OKR-CUSTOPS-LEGACY-NPS, DP-LEGACY-CALLCENTER-IVR) keep
#     their CREATE decision applied (the object keeps existing) -- only their LATER decisions
#     (Certify, Retire/Decertify) are reset, so a presenter can re-demo "certify it, then decide
#     to retire it" repeatedly without recreating the object each time.
#   - The 3 real production objects this session touched (OKR-SVCDEL-SLA, DP-SVCPERF) have ALL
#     their G19 requests reset back to the TRUE pre-G19 baseline (no prior create step to
#     preserve -- they predate this whole project phase).
#   - G18-A's `vw_contract_renewal_pipeline` tag request and G19-6's CDE/ontology-mapping/
#     semantic-promotion requests all reset back to their pre-decision state; the semantic
#     model measure itself is removed (so nb_17 can recreate it fresh next time).
#   - AI Instruction demo rows (G19-4) are removed from ai_metadata back to the original
#     baseline row; the legacy governance_change_requests rows reset to PendingApproval.
#
# DEMO_MODE = True  -> print every planned reset; no SQL/Delta/TOM writes
# DEMO_MODE = False -> execute the reset live

DEMO_MODE = True

METADATA_LAKEHOUSE = "lh_metadata"
MODEL_NAME = "BrookfieldEnercare"
SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30

print(f"nb_18_demo_reset | DEMO_MODE={DEMO_MODE}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: SQL connection helper (same pattern as nb_11/nb_16/nb_17)

import struct

import pyodbc

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256


def get_sql_connection():
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};"
        "Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    token = mssparkutils.credentials.getToken("https://database.windows.net/")
    encoded_token = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(encoded_token)}s", len(encoded_token), encoded_token)
    return pyodbc.connect(conn_str, attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct}, autocommit=False)


if DEMO_MODE:
    print("[DEMO_MODE] Skipping live SQL connection setup.")
else:
    sql_conn = get_sql_connection()
    print("SQL connection established for demo reset.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Generic unified-ledger request reset -- reverts current_status to Submitted (or a
# caller-specified target status), clears decision fields, and removes the Decided/Applied
# events + governed_object_versions + governance_target_receipts tied to that request.

def reset_unified_request(cursor, request_id, target_status="Submitted"):
    cursor.execute(
        "UPDATE dbo.governance_requests SET current_status = ?, decided_by = NULL, "
        "decided_at = NULL, completed_at = NULL, failure_reason = NULL WHERE request_id = ?",
        target_status, request_id,
    )
    cursor.execute(
        "DELETE FROM dbo.governance_events WHERE request_id = ? AND event_type IN ('Decided', 'Applied')",
        request_id,
    )
    cursor.execute("DELETE FROM dbo.governed_object_versions WHERE request_id = ?", request_id)
    cursor.execute("DELETE FROM dbo.governance_target_receipts WHERE request_id = ?", request_id)
    print(f"  reset {request_id} -> {target_status}")


def reset_legacy_request(cursor, request_id):
    cursor.execute(
        "UPDATE dbo.governance_change_requests SET status = 'PendingApproval', "
        "approver_upn = NULL, approved_at = NULL, applied_at = NULL WHERE request_id = ?",
        request_id,
    )
    print(f"  reset (legacy) {request_id} -> PendingApproval")


# --- G19-1: Objective requests -----------------------------------------------------------
# OKR-SVCDEL-SLA is a real production object (predates G19) -- revert fully to baseline.
OKR_REQUESTS_TO_RESET = [
    "OBJEDIT-SVCDEL-SLA-001",
    "OBJCERT-SVCDEL-SLA-001",
    "OBJRECERT-SVCDEL-SLA-001",
]
# OKR-CUSTOPS-LEGACY-NPS is disposable -- keep its CREATE applied, only reset the retirement.
LEGACY_NPS_REQUESTS_TO_RESET = [
    "OBJRETIRE-CUSTOPS-LEGACY-NPS-001",
]

# --- G19-5: Data Product requests --------------------------------------------------------
DP_REQUESTS_TO_RESET = [
    "DPCERT-SVCPERF-002",
    "DPCERTREVIEW-SVCPERF-001",
]
# DP-LEGACY-CALLCENTER-IVR is disposable -- keep its CREATE applied, only reset cert+decert.
LEGACY_IVR_REQUESTS_TO_RESET = [
    "DPCERT-LEGACY-IVR-001",
    "DPDECERT-LEGACY-IVR-001",
]

# --- G18-A / G19-6: source object gate + CDE/ontology mapping + semantic promotion --------
G18_G19_6_REQUESTS_TO_RESET = [
    "TAG-D0BF6E496681E6B0",        # vw_contract_renewal_pipeline's original G18-A tag request
    "CDEMAP-CONTRACT-RENEWAL-001",
    "ONTOMAP-TECHUTIL-001",
]
# SEMPROMO-TECHUTIL-001 was seeded directly as Approved (a system-to-system gate, not a
# steward-click moment) -- reset it back to Approved-not-yet-applied, not all the way to Submitted.
SEMANTIC_PROMOTION_REQUEST = "SEMPROMO-TECHUTIL-001"

ALL_SUBMITTED_RESETS = (
    OKR_REQUESTS_TO_RESET + LEGACY_NPS_REQUESTS_TO_RESET
    + DP_REQUESTS_TO_RESET + LEGACY_IVR_REQUESTS_TO_RESET
    + G18_G19_6_REQUESTS_TO_RESET
)

if DEMO_MODE:
    print("[DEMO_MODE] Would reset these unified-ledger requests to Submitted:")
    for rid in ALL_SUBMITTED_RESETS:
        print(f"  {rid}")
    print(f"[DEMO_MODE] Would reset {SEMANTIC_PROMOTION_REQUEST} to Approved (not yet applied).")
else:
    cursor = sql_conn.cursor()
    for rid in ALL_SUBMITTED_RESETS:
        reset_unified_request(cursor, rid, target_status="Submitted")
    reset_unified_request(cursor, SEMANTIC_PROMOTION_REQUEST, target_status="Approved")
    cursor.close()
    print("Unified-ledger requests reset.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Revert the actual field values these requests changed, back to pre-decision values.
# OKR-SVCDEL-SLA and DP-SVCPERF revert fully to their TRUE pre-G19 baseline (no prior demo
# step to preserve). The two disposable objects revert only to their POST-CREATE baseline
# (is_certified=0, status back to Published, retirement fields cleared) -- their create step
# stays applied per the explicit "keep the object, reset status only" scope decision.

if DEMO_MODE:
    print("[DEMO_MODE] Would revert:")
    print("  governance_okrs OKR-SVCDEL-SLA -> target_date=2026-12-31, is_certified=0, certified_by=NULL, certified_date=NULL, recertification_due=NULL")
    print("  governance_okrs OKR-CUSTOPS-LEGACY-NPS -> status=Published, retired_at=NULL, retired_by=NULL, retirement_reason=NULL")
    print("  governance_data_products DP-SVCPERF -> is_certified=0, certified_by=NULL, certified_date=NULL, expiration_date=NULL")
    print("  governance_data_products DP-LEGACY-CALLCENTER-IVR -> is_certified=0, certified_by=NULL, certified_date=NULL, expiration_date=NULL, status=Published, decertified_at=NULL, decertified_by=NULL, decertification_reason=NULL")
else:
    cursor = sql_conn.cursor()
    cursor.execute(
        "UPDATE dbo.governance_okrs SET target_date = '2026-12-31', is_certified = 0, "
        "certified_by = NULL, certified_date = NULL, recertification_due = NULL "
        "WHERE okr_id = 'OKR-SVCDEL-SLA'"
    )
    cursor.execute(
        "UPDATE dbo.governance_okrs SET status = 'Published', retired_at = NULL, "
        "retired_by = NULL, retirement_reason = NULL WHERE okr_id = 'OKR-CUSTOPS-LEGACY-NPS'"
    )
    cursor.execute(
        "UPDATE dbo.governance_data_products SET is_certified = 0, certified_by = NULL, "
        "certified_date = NULL, expiration_date = NULL WHERE data_product_id = 'DP-SVCPERF'"
    )
    cursor.execute(
        "UPDATE dbo.governance_data_products SET is_certified = 0, certified_by = NULL, "
        "certified_date = NULL, expiration_date = NULL, status = 'Published', "
        "decertified_at = NULL, decertified_by = NULL, decertification_reason = NULL "
        "WHERE data_product_id = 'DP-LEGACY-CALLCENTER-IVR'"
    )
    cursor.close()
    print("Governed object fields reverted.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Legacy AI Instruction requests (G19-4) -- reset to PendingApproval

LEGACY_AI_REQUESTS = ["GCR-AII-002", "GCR-AII-003", "GCR-AII-004"]

if DEMO_MODE:
    print("[DEMO_MODE] Would reset these legacy requests to PendingApproval:")
    for rid in LEGACY_AI_REQUESTS:
        print(f"  {rid}")
else:
    cursor = sql_conn.cursor()
    for rid in LEGACY_AI_REQUESTS:
        reset_legacy_request(cursor, rid)
    cursor.close()
    print("Legacy AI Instruction requests reset.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Commit the SQL-side reset (Cells 3-5 share one connection/transaction)

if DEMO_MODE:
    print("[DEMO_MODE] No SQL transaction to commit.")
else:
    try:
        sql_conn.commit()
        print("SQL reset committed.")
    except Exception:
        sql_conn.rollback()
        raise
    finally:
        sql_conn.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Lakehouse reset -- remove the AI Instruction demo rows from ai_metadata, keeping
# only the original pre-G19 baseline row (RecordID 40, the certified "escalation" instruction
# with its full safety/emergency clause).

if DEMO_MODE:
    preview_df = spark.sql(
        f"SELECT RecordID, TriggerText, IsCertified FROM {METADATA_LAKEHOUSE}.ai_metadata "
        "WHERE TriggerText IN ('escalation', 'weather_delay') AND RecordID <> 40 ORDER BY RecordID"
    ).toPandas()
    print("[DEMO_MODE] Would delete these ai_metadata rows:")
    print(preview_df.to_string(index=False))
else:
    spark.sql(
        f"DELETE FROM {METADATA_LAKEHOUSE}.ai_metadata "
        "WHERE TriggerText IN ('escalation', 'weather_delay') AND RecordID <> 40"
    )
    print("ai_metadata demo rows removed; RecordID 40 (original escalation baseline) preserved.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 8: Semantic model reset -- remove the "Technician Utilization Rate" measure so
# nb_17_g18_semantic_promotion can recreate it fresh in the next demo run.
# NOTE: Microsoft.AnalysisServices.Tabular must be imported from INSIDE an active
# connect_semantic_model session (see repo memory) -- never at module/cell top level.

TARGET_TABLE = "fct_service_request"
MEASURE_TO_REMOVE = "Technician Utilization Rate"


def find_by_name(collection, name):
    try:
        return collection[name]
    except Exception:
        pass
    target = name.strip().lower()
    for item in collection:
        item_name = getattr(item, "Name", None)
        if isinstance(item_name, str) and item_name.strip().lower() == target:
            return item
    return None


if DEMO_MODE:
    print(f"[DEMO_MODE] Would remove measure {TARGET_TABLE}.{MEASURE_TO_REMOVE} from {MODEL_NAME}.")
else:
    import subprocess
    import sys
    try:
        import sempy_labs
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "semantic-link-labs"], check=True)
    from sempy_labs.tom import connect_semantic_model

    with connect_semantic_model(dataset=MODEL_NAME, readonly=False) as tom:
        table = find_by_name(tom.model.Tables, TARGET_TABLE)
        measure = find_by_name(table.Measures, MEASURE_TO_REMOVE) if table is not None else None
        if measure is not None:
            table.Measures.Remove(measure)
            print(f"[APPLIED] Removed measure {TARGET_TABLE}.{MEASURE_TO_REMOVE}")
        else:
            print(f"Measure {TARGET_TABLE}.{MEASURE_TO_REMOVE} was already absent -- nothing to remove.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 9: Summary

print("Demo reset complete." if not DEMO_MODE else "Demo reset preview complete (DEMO_MODE=True, nothing changed).")
print("")
print("All reset requests are back at Submitted/PendingApproval/Approved-not-yet-applied.")
print("To re-demo: flip each request's status to Approved (a simple UPDATE, or via the live")
print("Purview/portal workflow where one exists) and re-run the matching apply notebook:")
print("  - nb_11_gated_governance_sync applies GCR-AII-002/003/004 into ai_metadata.")
print("  - nb_17_g18_semantic_promotion applies SEMPROMO-TECHUTIL-001 into the semantic model.")
print("  - All other resets (OKR/DataProduct/CDE/ontology-mapping edits) apply directly via a")
print("    small SQL UPDATE once Approved -- the original sql/24, sql/26, sql/27 scripts will")
print("    NOT reapply them (they're guarded by request_id existence, not status).")

# ===== END SOURCE: archive/nb_18_demo_reset.Notebook =====
