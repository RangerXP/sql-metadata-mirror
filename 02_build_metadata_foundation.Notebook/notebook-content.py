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

import json
import struct
from datetime import datetime, timezone

import pyodbc
from pyspark.sql.types import StringType, StructField, StructType

# ---------------------------------------------------------------------------
# G18-A thin reader: SOURCE_TAG_DETECTED rows are extracted natively in SQL
# (sql/02_metadata_foundation/19_tag_annotation_extraction.sql's dbo.usp_extract_tag_annotations,
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

DEMO_MODE = False  # live run refreshes the current steward-review queue

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


REQUIRED_TAG_KEYS = {"domain", "owner", "sensitivity", "semantic_role", "business_use"}
CANONICAL_SENSITIVITY_LABELS = {
    "general": "General",
    "internal": "Internal",
    "confidential": "Confidential",
    "highly confidential": "Highly Confidential",
    "pci restricted": "Highly Confidential",
    "privacy restricted": "Highly Confidential",
}


def _safe_json_loads(payload):
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    try:
        obj = json.loads(payload)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        print(f"[WARN] Invalid JSON payload encountered: {payload[:200] if isinstance(payload, str) else payload}")
        return {}


def _normalize_sensitivity_label(raw_value):
    if raw_value is None:
        return ""
    text = str(raw_value).strip()
    if not text:
        return ""
    return CANONICAL_SENSITIVITY_LABELS.get(text.lower(), text)


def validate_tag_request_payload(payload):
    payload_obj = _safe_json_loads(payload)
    missing = sorted(REQUIRED_TAG_KEYS - set((str(k).lower() for k in payload_obj.keys())))
    if missing:
        raise ValueError(f"SourceTagAnnotationDetected payload missing required keys: {', '.join(missing)}")

    sensitivity_value = payload_obj.get("sensitivity") or payload_obj.get("sensitivity_label")
    normalized_sensitivity = _normalize_sensitivity_label(sensitivity_value)
    if not normalized_sensitivity:
        raise ValueError("SourceTagAnnotationDetected payload missing a valid Purview sensitivity label")
    valid_labels = {value.lower() for value in CANONICAL_SENSITIVITY_LABELS.values()}
    if normalized_sensitivity.lower() not in valid_labels:
        raise ValueError(f"Unsupported sensitivity label '{normalized_sensitivity}' for Purview application")
    payload_obj["sensitivity"] = normalized_sensitivity
    payload_obj["sensitivity_label"] = normalized_sensitivity
    return payload_obj


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

validated_pending_rows = []
for row in pending_rows:
    try:
        validate_tag_request_payload(row.proposed_payload)
        validated_pending_rows.append(row)
    except Exception as exc:
        print(f"[REJECTED] {row.request_id} invalid @tag payload: {exc}")

pending_rows = validated_pending_rows

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

# CELL ********************

# Extend lh_metadata schema and seed certified KPI definitions
# Gaps: G1-3, G1-4, G1-5, G1-7, G2-1, G2-2
#
# Prerequisite: lh_metadata must already exist
# Default lakehouse: lh_metadata
#
# DEMO_MODE = True  → print all SQL/data; no writes to Delta
# DEMO_MODE = False → execute all ALTER / CREATE / INSERT statements

DEMO_MODE = False           # default safe mode; set False only for live writes

METADATA_LAKEHOUSE = "lh_metadata"
CERTIFIED_BY       = "Victoria Tan"
CERTIFIED_DATE     = "2026-05-06"
MODEL_NAME         = "BrookfieldEnercare"

print(f"DEMO_MODE={DEMO_MODE} | lakehouse={METADATA_LAKEHOUSE}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-3, G2-1 — Extend kpi_metadata: add certification + call-center columns
# Delta does not support DEFAULT in ADD COLUMNS — add columns first,
# then set defaults separately with ALTER COLUMN SET DEFAULT.

sql_alter_kpi_add = f"""
ALTER TABLE {METADATA_LAKEHOUSE}.kpi_metadata
ADD COLUMNS (
    KPICode            STRING,
    IsCertified        INT,
    Version            INT,
    PreviousFormula    STRING,
    CertifiedBy        STRING,
    CertifiedDate      DATE,
    TargetValue        DOUBLE,
    WarningThreshold   DOUBLE,
    CriticalThreshold  DOUBLE,
    UnitType           STRING
)
""".strip()

sql_enable_defaults   = f"ALTER TABLE {METADATA_LAKEHOUSE}.kpi_metadata SET TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')"
sql_default_certified = f"ALTER TABLE {METADATA_LAKEHOUSE}.kpi_metadata ALTER COLUMN IsCertified SET DEFAULT 0"
sql_default_version   = f"ALTER TABLE {METADATA_LAKEHOUSE}.kpi_metadata ALTER COLUMN Version SET DEFAULT 1"

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_alter_kpi_add)
    print(sql_enable_defaults)
    print(sql_default_certified)
    print(sql_default_version)
else:
    existing_cols = [c.name for c in spark.table(f"{METADATA_LAKEHOUSE}.kpi_metadata").schema]
    if "KPICode" not in existing_cols:
        spark.sql(sql_alter_kpi_add)
        print("kpi_metadata: 10 columns added")
    else:
        print("kpi_metadata: extension columns already present — skipping ADD COLUMNS")
    spark.sql(sql_enable_defaults)
    spark.sql(sql_default_certified)
    spark.sql(sql_default_version)
    print("kpi_metadata: defaults set")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-4 — Create ai_metadata table
# Stores verified answers, AI instructions, term mappings per semantic model

sql_create_ai_metadata = f"""
CREATE TABLE IF NOT EXISTS {METADATA_LAKEHOUSE}.ai_metadata (
    RecordID       INT,
    ModelName      STRING,
    RecordType     STRING    COMMENT 'verified_answer | ai_instruction | term_mapping',
    TriggerText    STRING    COMMENT 'Question phrase or term that activates this record',
    ResponseText   STRING    COMMENT 'Verified answer text or AI instruction content',
    LinkedKPICode  STRING,
    IsDraft        INT,
    CreatedDate    DATE
)
USING DELTA
COMMENT 'Copilot AI configuration — verified answers, instructions, term mappings'
""".strip()

sql_ai_enable_defaults  = f"ALTER TABLE {METADATA_LAKEHOUSE}.ai_metadata SET TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')"
sql_ai_default_isdraft  = f"ALTER TABLE {METADATA_LAKEHOUSE}.ai_metadata ALTER COLUMN IsDraft SET DEFAULT 1"

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_create_ai_metadata)
    print(sql_ai_enable_defaults)
    print(sql_ai_default_isdraft)
else:
    try:
        spark.sql(sql_create_ai_metadata)
        spark.sql(sql_ai_enable_defaults)
        spark.sql(sql_ai_default_isdraft)
    except Exception as e:
        if "DELTA_PATH_DOES_NOT_EXIST" in str(e):
            print("  [WARN] Ghost catalog entry — dropping and recreating ai_metadata")
            spark.sql(f"DROP TABLE IF EXISTS {METADATA_LAKEHOUSE}.ai_metadata")
            spark.sql(sql_create_ai_metadata)
            spark.sql(sql_ai_enable_defaults)
            spark.sql(sql_ai_default_isdraft)
        else:
            raise
    print("ai_metadata table created")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Phase 4 Milestone P4-2 — ai_metadata certification columns
# Mirrors the IsCertified/CertifiedBy/CertifiedDate pattern already on kpi_metadata,
# so 07_apply_approved_changes (P4-4) can certify verified answers the same way.

sql_alter_ai_add = f"""
ALTER TABLE {METADATA_LAKEHOUSE}.ai_metadata
ADD COLUMNS (
    IsCertified    INT,
    CertifiedBy    STRING,
    CertifiedDate  DATE
)
""".strip()

sql_ai_default_certified = f"ALTER TABLE {METADATA_LAKEHOUSE}.ai_metadata ALTER COLUMN IsCertified SET DEFAULT 0"

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_alter_ai_add)
    print(sql_ai_default_certified)
else:
    existing_ai_cols = [c.name for c in spark.table(f"{METADATA_LAKEHOUSE}.ai_metadata").schema]
    if "IsCertified" not in existing_ai_cols:
        spark.sql(sql_alter_ai_add)
        spark.sql(sql_ai_default_certified)
        print("ai_metadata: 3 certification columns added (IsCertified, CertifiedBy, CertifiedDate)")
    else:
        print("ai_metadata: certification columns already present — skipping ADD COLUMNS")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-5 — Create data_owners table
# Owner and steward registry per domain

sql_create_data_owners = f"""
CREATE TABLE IF NOT EXISTS {METADATA_LAKEHOUSE}.data_owners (
    Domain        STRING    COMMENT 'Business domain (Revenue, Customer, Operations, Call Center, Retention, Field Operations)',
    OwnerName     STRING,
    OwnerEmail    STRING,
    StewardName   STRING,
    StewardEmail  STRING
)
USING DELTA
COMMENT 'Domain data ownership registry — drives steward approval workflow (G9)'
""".strip()

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_create_data_owners)
    print("[DEMO_MODE] Would populate data_owners from distinct Domain / Owner / Steward values in asset_metadata")
else:
    spark.sql(sql_create_data_owners)
    spark.sql(f"""
    INSERT OVERWRITE {METADATA_LAKEHOUSE}.data_owners
    WITH owner_candidates AS (
        SELECT
            TRIM(Domain)  AS Domain,
            NULLIF(TRIM(Owner), '')   AS OwnerRaw,
            NULLIF(TRIM(Steward), '') AS StewardRaw
        FROM {METADATA_LAKEHOUSE}.asset_metadata
        WHERE COALESCE(TRIM(Domain), '') <> ''
          AND (
              COALESCE(TRIM(Owner), '') <> ''
              OR COALESCE(TRIM(Steward), '') <> ''
          )
    ),
    domain_owners AS (
        SELECT
            Domain,
            MAX(OwnerRaw)   AS OwnerRaw,
            MAX(StewardRaw) AS StewardRaw
        FROM owner_candidates
        GROUP BY Domain
    )
    SELECT
        Domain,
        OwnerRaw AS OwnerName,
        CASE WHEN OwnerRaw LIKE '%@%' THEN OwnerRaw ELSE NULL END AS OwnerEmail,
        StewardRaw AS StewardName,
        CASE WHEN StewardRaw LIKE '%@%' THEN StewardRaw ELSE NULL END AS StewardEmail
    FROM domain_owners
    ORDER BY Domain
    """)
    owners_n = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.data_owners").first()["n"]
    print(f"data_owners table created and populated: {owners_n} domain rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-7 — Create lineage_edges table
# Source-to-target graph used by the Purview lineage publication notebook (G7)

sql_create_lineage = f"""
CREATE TABLE IF NOT EXISTS {METADATA_LAKEHOUSE}.lineage_edges (
    EdgeID         INT       COMMENT 'Monotonic edge identifier',
    SourceQName    STRING    COMMENT 'Purview qualified name of upstream asset',
    TargetQName    STRING    COMMENT 'Purview qualified name of downstream asset',
    ProcessName    STRING    COMMENT 'Notebook or pipeline performing the transform',
    TransformType  STRING    COMMENT 'mirror | notebook | dataflow | direct_lake'
)
USING DELTA
COMMENT 'Source-to-target lineage graph — consumed by the Purview lineage publication notebook'
""".strip()

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_create_lineage)
    print("[DEMO_MODE] Would populate lineage_edges from asset_metadata.UpstreamAssets relationships extracted by this notebook")
else:
    spark.sql(sql_create_lineage)
    spark.sql(f"""
    INSERT OVERWRITE {METADATA_LAKEHOUSE}.lineage_edges
    WITH asset_lineage AS (
        SELECT
            ObjectName,
            UpstreamAssets
        FROM {METADATA_LAKEHOUSE}.asset_metadata
        WHERE COALESCE(TRIM(UpstreamAssets), '') <> ''
    ),
    exploded_edges AS (
        SELECT
            ObjectName,
            TRIM(upstream_asset) AS UpstreamAsset
        FROM asset_lineage
        LATERAL VIEW explode(split(UpstreamAssets, ' \\| ')) e AS upstream_asset
    ),
    cleaned_edges AS (
        SELECT DISTINCT
            REGEXP_REPLACE(UpstreamAsset, '^demo\\.', '') AS UpstreamObject,
            ObjectName
        FROM exploded_edges
        WHERE COALESCE(TRIM(UpstreamAsset), '') <> ''
    )
    SELECT
        ROW_NUMBER() OVER (ORDER BY UpstreamObject, ObjectName) AS EdgeID,
        CONCAT('mssql://enercare_demo/demo/', UpstreamObject) AS SourceQName,
        CONCAT('mssql://enercare_demo/demo/', ObjectName)     AS TargetQName,
        'nb_02_metadata_pipeline_demo'                        AS ProcessName,
        'notebook'                                            AS TransformType
    FROM cleaned_edges
    ORDER BY EdgeID
    """)
    lineage_n = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.lineage_edges").first()["n"]
    print(f"lineage_edges table created and populated: {lineage_n} edges")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G2-2 Set A — Seed kpi_metadata with 12 existing DAX measures
# IsCertified=0 — pending business sign-off from Victoria/Ranbir

from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, DateType
from datetime import date

KPI_SCHEMA = StructType([
    StructField("KPIName",            StringType(),  True),
    StructField("Formula",            StringType(),  True),
    StructField("Domain",             StringType(),  True),
    StructField("Owner",              StringType(),  True),
    StructField("Description",        StringType(),  True),
    StructField("IsDraft",            IntegerType(), True),
    StructField("KPICode",            StringType(),  True),
    StructField("IsCertified",        IntegerType(), True),
    StructField("Version",            IntegerType(), True),
    StructField("PreviousFormula",    StringType(),  True),
    StructField("CertifiedBy",        StringType(),  True),
    StructField("CertifiedDate",      DateType(),    True),
    StructField("TargetValue",        DoubleType(),  True),
    StructField("WarningThreshold",   DoubleType(),  True),
    StructField("CriticalThreshold",  DoubleType(),  True),
    StructField("UnitType",           StringType(),  True),
])

existing_measures = [
    ("Total MRR",             "total_mrr",             "Revenue",
     'CALCULATE(SUM(fct_billing[Amount]), fct_billing[TransactionType] = "MonthlyCharge", fct_billing[Status] = "Posted")',
     "currency"),
    ("New MRR",               "new_mrr",               "Revenue",
     "SUMX(FILTER(fct_contract_month, fct_contract_month[IsNew] = 1), fct_contract_month[MonthlyAmount])",
     "currency"),
    ("Churned MRR",           "churned_mrr",           "Revenue",
     "SUMX(FILTER(fct_contract_month, fct_contract_month[IsChurn] = 1), fct_contract_month[MonthlyAmount])",
     "currency"),
    ("Net MRR Change",        "net_mrr_change",        "Revenue",
     "[New MRR] - [Churned MRR]",
     "currency"),
    ("Active Customer Count", "active_customer_count", "Customer",
     'CALCULATE(COUNTROWS(dim_customer), dim_customer[Status] = "Active")',
     "count"),
    ("Active Contract Count", "active_contract_count", "Customer",
     'CALCULATE(COUNTROWS(fct_contract_month), fct_contract_month[ContractStatus] = "Active")',
     "count"),
    ("Avg Lifetime Value",    "avg_lifetime_value",    "Customer",
     'AVERAGEX(dim_customer, CALCULATE(SUMX(FILTER(fct_billing, fct_billing[Status] = "Posted"), fct_billing[Amount])))',
     "currency"),
    ("Avg Tenure Months",     "avg_tenure_months",     "Customer",
     "AVERAGEX(dim_customer, DATEDIFF(dim_customer[CreatedDate], TODAY(), MONTH))",
     "count"),
    ("SLA Breach Count",      "sla_breach_count",      "Operations",
     "SUMX(fct_service_request, fct_service_request[IsSlaBreachFlag])",
     "count"),
    ("SLA Compliance Rate",   "sla_compliance_rate",   "Operations",
     "DIVIDE(COUNTROWS(fct_service_request) - [SLA Breach Count], COUNTROWS(fct_service_request))",
     "percentage"),
    ("Warranty Coverage Rate","warranty_coverage_rate","Operations",
     "DIVIDE(SUMX(dim_equipment, dim_equipment[IsUnderWarranty]), COUNTROWS(dim_equipment))",
     "percentage"),
    ("Avg Equipment Age Years","avg_equipment_age_years","Operations",
     "AVERAGEX(dim_equipment, dim_equipment[AgeYears])",
     "decimal"),
]

rows_set_a = [
    Row(
        KPIName=name, Formula=formula, Domain=domain, Owner="analytics@enercare.ca",
        Description=f"{name} — DAX measure from BrookfieldEnercare semantic model. Pending business certification.",
        IsDraft=0, KPICode=code, IsCertified=0, Version=1,
        PreviousFormula=None, CertifiedBy=None, CertifiedDate=None,
        TargetValue=None, WarningThreshold=None, CriticalThreshold=None, UnitType=unit,
    )
    for name, code, domain, formula, unit in existing_measures
]

df_set_a = spark.createDataFrame(rows_set_a, schema=KPI_SCHEMA)

if DEMO_MODE:
    print(f"[DEMO_MODE] Set A — {len(rows_set_a)} existing DAX measures (IsCertified=0):\n")
    df_set_a.select("KPIName", "KPICode", "Domain", "IsCertified", "UnitType").show(truncate=False)
else:
    existing_count = spark.sql(
        f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.kpi_metadata WHERE KPICode IS NOT NULL"
    ).first()["n"]
    if existing_count > 0:
        print(f"Skipping Set A seed — {existing_count} KPI rows already present")
    else:
        df_set_a.write.format("delta").mode("append").option("mergeSchema", "true") \
                .saveAsTable(f"{METADATA_LAKEHOUSE}.kpi_metadata")
        print(f"kpi_metadata seeded: {len(rows_set_a)} existing DAX measures")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G2-2 Set B — Seed kpi_metadata with 5 certified call center KPIs
# IsCertified=1 — pre-certified for demo by CERTIFIED_BY

certified_date_obj = date.fromisoformat(CERTIFIED_DATE)


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"

cc_kpi_defs = [
    ("First Contact Resolution",      "FCR",          "Call Center",    "ranbir.singh@enercare.ca",
    'VAR _hasDateFilter = ISCROSSFILTERED(dim_date[DateKey]) || ISCROSSFILTERED(dim_date[FullDate]) VAR _anchorDate = MAXX(ALL(dim_date), dim_date[FullDate]) RETURN IF(_hasDateFilter, DIVIDE(CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[fcr_flag] = 1), COUNTROWS(fct_cc_interactions)), CALCULATE(DIVIDE(CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[fcr_flag] = 1), COUNTROWS(fct_cc_interactions)), DATESINPERIOD(dim_date[FullDate], _anchorDate, -12, MONTH)))',
     "Percentage of customer interactions resolved without a follow-up within 5 business days. "
     "An interaction is resolved if no subsequent inbound contact occurs from the same customer "
     "about the same issue within the window. Target: 78%.",
     0.78, 0.72, 0.65, "percentage"),
    ("Customer Satisfaction Score",   "CSAT",         "Call Center",    "ranbir.singh@enercare.ca",
    'VAR _hasDateFilter = ISCROSSFILTERED(dim_date[DateKey]) || ISCROSSFILTERED(dim_date[FullDate]) VAR _anchorDate = MAXX(ALL(dim_date), dim_date[FullDate]) RETURN IF(_hasDateFilter, AVERAGEX(FILTER(fct_cc_interactions, NOT ISBLANK(fct_cc_interactions[csat_score])), fct_cc_interactions[csat_score]), CALCULATE(AVERAGEX(FILTER(fct_cc_interactions, NOT ISBLANK(fct_cc_interactions[csat_score])), fct_cc_interactions[csat_score]), DATESINPERIOD(dim_date[FullDate], _anchorDate, -12, MONTH)))',
     "Average post-call IVR survey score on a 1–5 scale (5 = very satisfied). "
     "Survey is offered to all inbound calls; response rate ~22%. "
     "Score is weighted by queue type for aggregate reporting. Target: 4.2.",
     4.2, 3.8, 3.4, "score_1_to_5"),
    ("Protection Plan Renewal Rate",  "PP_RNW_RATE",  "Retention",      "victoria.tan@enercare.ca",
    'VAR _hasDateFilter = ISCROSSFILTERED(dim_date[DateKey]) || ISCROSSFILTERED(dim_date[FullDate]) VAR _anchorDate = MAXX(ALL(dim_date), dim_date[FullDate]) RETURN IF(_hasDateFilter, DIVIDE(CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[pp_renewal_outcome] = "accepted"), CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[queue_type] = "pp_renewal")), CALCULATE(DIVIDE(CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[pp_renewal_outcome] = "accepted"), CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[queue_type] = "pp_renewal")), DATESINPERIOD(dim_date[FullDate], _anchorDate, -12, MONTH)))',
     "Percentage of expiring Protection Plan contracts successfully renewed within the renewal window "
     "(30 days before to 15 days after contract end date). Applies to HVAC_PLAN and WH_RENTAL_PLAN. "
     "Excludes mid-term cancellations. Target: 82%.",
     0.82, 0.75, 0.68, "percentage"),
    ("Average Handle Time",           "AHT",          "Call Center",    "ranbir.singh@enercare.ca",
    'VAR _hasDateFilter = ISCROSSFILTERED(dim_date[DateKey]) || ISCROSSFILTERED(dim_date[FullDate]) VAR _anchorDate = MAXX(ALL(dim_date), dim_date[FullDate]) RETURN IF(_hasDateFilter, AVERAGEX(fct_cc_interactions, fct_cc_interactions[handle_time_sec] + fct_cc_interactions[hold_time_sec]), CALCULATE(AVERAGEX(fct_cc_interactions, fct_cc_interactions[handle_time_sec] + fct_cc_interactions[hold_time_sec]), DATESINPERIOD(dim_date[FullDate], _anchorDate, -12, MONTH)))',
     "Average seconds of agent engagement per interaction: talk time + hold time + after-call wrap-up. "
     "Measured per queue type. Targets: billing=420s, emergency=300s, PP_renewal=480s.",
     420.0, 480.0, 540.0, "seconds"),
    ("SLA Breach Rate",               "SLA_BRCH_RATE","Field Operations","ranbir.singh@enercare.ca",
     'DIVIDE(CALCULATE(COUNTROWS(fct_sv_service_visits), fct_sv_service_visits[sla_breach_flg] = "Y"), '
     'COUNTROWS(fct_sv_service_visits))',
     "Percentage of field service visits where the technician did not arrive within the committed window. "
     "SLA windows: emergency=4h, maintenance=scheduled date, repair=next business day. Target: 5%.",
     0.05, 0.10, 0.15, "percentage"),
]

rows_set_b = [
    # Keyword order must match KPI_SCHEMA field order — createDataFrame(rows, schema=...)
    # binds Row values positionally, not by name.
    Row(
        KPIName=name, Formula=formula, Domain=domain, Owner=owner, Description=desc,
        IsDraft=0, KPICode=code, IsCertified=1, Version=1,
        PreviousFormula=None, CertifiedBy=CERTIFIED_BY, CertifiedDate=certified_date_obj,
        TargetValue=tgt, WarningThreshold=warn, CriticalThreshold=crit, UnitType=unit,
    )
    for name, code, domain, owner, formula, desc, tgt, warn, crit, unit in cc_kpi_defs
]

df_set_b = spark.createDataFrame(rows_set_b, schema=KPI_SCHEMA)

if DEMO_MODE:
    print(f"[DEMO_MODE] Set B — {len(rows_set_b)} certified call center KPIs (IsCertified=1):\n")
    df_set_b.select("KPICode", "KPIName", "Domain", "TargetValue", "UnitType", "CertifiedBy").show(truncate=False)
else:
    seed_kpi_codes = ", ".join(_sql_string(r.KPICode) for r in rows_set_b)
    spark.sql(f"DELETE FROM {METADATA_LAKEHOUSE}.kpi_metadata WHERE KPICode IN ({seed_kpi_codes})")
    df_set_b.write.format("delta").mode("append").option("mergeSchema", "true") \
            .saveAsTable(f"{METADATA_LAKEHOUSE}.kpi_metadata")
    print(f"kpi_metadata refreshed: {len(rows_set_b)} certified call center KPIs")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-4, G4 — Seed ai_metadata: certified KPI and Maria source-story verified answers
# Pre-approved (IsDraft=0) — ready for Copilot "Prep Data for AI"

verified_answers = [
    ("FCR", "what is our FCR",
    "Use the FCR Rate measure from the semantic model. Default calculation window is rolling 12 months ending "
        "on the latest available model date unless the user specifies another range. FCR measures whether a "
        "customer's issue was resolved in a single interaction without a callback within 5 business days. "
        "Do not ask which report or area to use when the user asks this exact question."),
        ("FCR", "what is FCR",
        "Use the FCR Rate measure from the semantic model. Default calculation window is rolling 12 months ending "
        "on the latest available model date unless the user specifies another range. FCR means First Contact "
        "Resolution. Do not ask for more context when the user asks this exact question."),
    ("FCR", "first contact resolution",
     "First Contact Resolution Rate is the percentage of inbound interactions that did not generate a "
     "follow-up contact within 5 business days. It is our primary call center efficiency KPI."),
    ("FCR", "call back rate",
     "Callback rate is the inverse of FCR. If FCR is 78%, approximately 22% of customers contacted us "
     "again within 5 days about the same issue."),
    ("FCR", "how often do customers call back",
     "FCR tracks this. An FCR below 72% (warning threshold) means more than 28% of customers needed a "
     "follow-up contact within 5 business days."),
    ("CSAT", "what is our CSAT",
        "Use the Avg CSAT measure from the semantic model. Default calculation window is rolling 12 months ending "
        "on the latest available model date unless the user specifies another range. A NULL csat_score means the "
        "customer did not respond — do not treat it as a low score."),
    ("CSAT", "what is our CSAT?",
        "Use the Avg CSAT measure from the semantic model. Default calculation window is rolling 12 months ending "
        "on the latest available model date unless the user specifies another range. A NULL csat_score means the "
        "customer did not respond — do not treat it as a low score."),
    ("CSAT", "what is our csat",
        "Use the Avg CSAT measure from the semantic model. Default calculation window is rolling 12 months ending "
        "on the latest available model date unless the user specifies another range. A NULL csat_score means the "
        "customer did not respond — do not treat it as a low score."),
    ("CSAT", "customer satisfaction",
     "Customer satisfaction is measured via post-call IVR survey on a 1–5 scale. "
     "CSAT below 3.5 on a queue indicates a systemic issue, not individual agent performance."),
    ("CSAT", "how happy are customers",
     "Use the CSAT measure, which averages post-call survey responses. "
     "Only ~22% of customers respond — filter for non-null csat_score for accurate averages."),
    ("CSAT", "how happy are customers?",
     "Use the CSAT measure, which averages post-call survey responses. "
     "Only ~22% of customers respond — filter for non-null csat_score for accurate averages."),
    ("CSAT", "how happy are our customers",
     "Use the CSAT measure, which averages post-call survey responses. "
     "Only ~22% of customers respond — filter for non-null csat_score for accurate averages."),
    ("CSAT", "CSAT | Trigger: how happy are customers",
     "Use the CSAT measure, which averages post-call survey responses. "
     "Only ~22% of customers respond — filter for non-null csat_score for accurate averages."),
    ("CSAT", "satisfaction score",
     "CSAT averages the IVR survey score across interactions. "
     "Filter to completed surveys (csat_score IS NOT NULL) when calculating. Target: 4.2 out of 5."),
    ("PP_RNW_RATE", "PP renewal rate",
        "Use the PP Renewal Rate measure from the semantic model. Default calculation window is rolling 12 months "
        "ending on the latest available model date unless the user specifies another range. This is the primary "
        "retention KPI."),
    ("PP_RNW_RATE", "protection plan renewal",
     "Protection Plan Renewal Rate = renewed / (renewed + lapsed + cancelled) contracts that reached expiry. "
     "Applies to HVAC_PLAN and WH_RENTAL_PLAN product codes only."),
    ("PP_RNW_RATE", "how many customers renewed",
     "Use PP_RNW_RATE. Renewals can happen via inbound call, outbound retention call, online portal, or "
     "direct mail. Target: 82% renewal rate."),
    ("PP_RNW_RATE", "renewal rate",
     "PP Renewal Rate target is 82%. Customers calling the billing queue before renewal date and not renewing "
     "often signals billing confusion — cross-reference with AHT on billing queue."),
    ("PP_RNW_RATE", "contract renewal",
     "Contract renewal performance is tracked by PP_RNW_RATE. Renewal window: "
     "30 days before to 15 days after the contract end date."),
    # Certified 2026-08-10 via GCR-VA-001 (VERIFIED_ANSWER_CERTIFICATION, approved by Ci Zhu) —
    # supersedes the earlier generic 24-hour-window answer with the actual credit-policy remedy.
    # See sql/07_governance_gates/10_seed_gated_governance_scenarios.sql and governance_change_requests.GCR-VA-001.
    ("SLA_BRCH_RATE", "What is our SLA credit policy for a no-heat call during heating season?",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution."),
    ("SLA_BRCH_RATE", "what's the SLA for a no-heat call?",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "what’s the SLA for a no-heat call?",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "What’s the SLA for a no-heat call?",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "what is the SLA for a no-heat call?",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "what's the sla for a no heat call",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "no-heat sla",
     "NoHeat emergency requests use a 24-hour SLA window in this demo, with a daily pro-rated rental credit for "
     "every day past breach during heating season plus a full-month courtesy credit on final resolution. "
     "Track aggregate performance with SLA_BRCH_RATE (target breach rate: 5%)."),
    ("SLA_BRCH_RATE", "no heat sla",
     "NoHeat emergency requests use a 24-hour SLA window in this demo, with a daily pro-rated rental credit for "
     "every day past breach during heating season plus a full-month courtesy credit on final resolution. "
     "Track aggregate performance with SLA_BRCH_RATE (target breach rate: 5%)."),
    ("SLA_BRCH_RATE", "whats the sla for a no heat call",
     "Total Home Protection Plan customers are entitled to a daily pro-rated rental credit for every day past a "
     "24-hour no-heat SLA breach during heating season, plus a full-month courtesy credit on final resolution. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SVC_CASE", "what is the current status and recommended path for Maria Castellanos Service Account: 183746220",
     "Customer: Maria Castellanos | Service Account: 183746220 (EC18374622-SVC) | Incident / Request ID: 2026051142 | "
     "Account Status: Active | Equipment: Lennox SLP98V furnace (rental), equipment_id 183746221, status Active | "
     "Service History: Emergency Repair, priority Emergency, status InProgress, created 2026-06-13, scheduled 2026-06-14, completed not yet recorded | "
     "Dispatch / Technician status: Technician 105 assigned; pending technician reassignment after missed 24-hour SLA in GTA North dispatch notes | "
     "Contract Type / Terms: Active residential contract, product_id 4, monthly amount 89.95 | "
     "Billing Status: INV-MARIA-202606 posted (89.95 + 11.69 tax); CR-MARIA-SLA-202606 posted credit (-14.99) | "
     "Support Call History: Escalated service complaint exists for same customer/service account; missed no-heat SLA and billing concern captured | "
     "Dispute / Credit Eligibility: SLA credit already applied; review additional goodwill only if restoration delay continues | "
     "Fastest Compliant Reschedule Path: Immediate GTA North dispatch reassignment with confirmed ETA callback | "
     "Escalation Owner: GTA North dispatch supervisor with Billing Support coordination | "
     "Decision SLA: Emergency no-heat path requires same-day priority handling and breached 24-hour resolution target recovery | "
     "Recommended Next Actions: reassign technician now, confirm ETA, complete proactive callback, monitor for additional credits if delay persists | "
     "Notes: Use request-id-first lookup (2026051142) and service-account variant matching (183746220 / EC18374622-SVC) before any no-record fallback."),
    ("SVC_CASE", "find service records for Customer: Maria Castellanos Service Account: 183746220",
     "Service records for Maria Castellanos, service account 183746220: Request ID 2026051142, Emergency Repair, status InProgress, priority Emergency, created 2026-06-13, scheduled 2026-06-14, not completed. "
     "This open no-heat case has a documented missed 24-hour SLA with pending technician reassignment in GTA North dispatch notes."),
    ("SVC_CASE", "find service records for Customer: Maria Castellanos Service Account: 183746220v",
     "Service records for Maria Castellanos, service account 183746220: Request ID 2026051142, Emergency Repair, status InProgress, priority Emergency, created 2026-06-13, scheduled 2026-06-14, not completed. "
     "Input includes a trailing character variant ('183746220v'); normalize to numeric service account 183746220 before lookup. "
     "This open no-heat case has a documented missed 24-hour SLA with pending technician reassignment in GTA North dispatch notes."),
    ("SVC_CASE", "Customer: Maria Castellanos Service Account: 183746220 Incident / Request ID: 2026051142",
     "Customer: Maria Castellanos | Service Account: 183746220 (EC18374622-SVC) | Incident / Request ID: 2026051142 | "
     "Account Status: Active | Equipment: Lennox SLP98V furnace (rental), equipment_id 183746221, status Active | "
     "Service History: Emergency Repair, priority Emergency, status InProgress, created 2026-06-13, scheduled 2026-06-14, completed not yet recorded | "
     "Dispatch / Technician status: Technician 105 assigned; pending technician reassignment after missed 24-hour SLA in GTA North dispatch notes | "
     "Contract Type / Terms: Active residential contract, product_id 4, monthly amount 89.95 | "
     "Billing Status: INV-MARIA-202606 posted (89.95 + 11.69 tax); CR-MARIA-SLA-202606 posted credit (-14.99) | "
     "Support Call History: Escalated service complaint exists for same customer/service account; missed no-heat SLA and billing concern captured | "
     "Dispute / Credit Eligibility: SLA credit already applied; review additional goodwill only if restoration delay continues | "
     "Fastest Compliant Reschedule Path: Immediate GTA North dispatch reassignment with confirmed ETA callback | "
     "Escalation Owner: GTA North dispatch supervisor with Billing Support coordination | "
     "Decision SLA: Emergency no-heat path requires same-day priority handling and breached 24-hour resolution target recovery | "
     "Recommended Next Actions: reassign technician now, confirm ETA, complete proactive callback, monitor for additional credits if delay persists | "
     "Notes: request/account/customer tuple is a known seeded record and should not return all-fields-missing fallback."),
    ("SVC_CASE", "tell me about request id: 2026051142",
     "Request 2026051142 is an Emergency Repair no-heat furnace case for Maria Castellanos (service account 183746220 / EC18374622-SVC). "
     "Current state: InProgress, technician 105 noted, scheduled pending reassignment after 24-hour SLA breach. "
     "Billing context includes posted monthly charge INV-MARIA-202606 and posted SLA credit CR-MARIA-SLA-202606."),
    ("CSAT", "what should the auditor see for Maria",
     "The auditor should see one governed chain: DP-CUST360 for Maria's identity and consent, DP-SVCPERF "
     "for the NoHeat furnace request, DP-BILLHEALTH for the 89.95 monthly charge, and dbo.audit_data_access "
     "showing Tom Nguyen's CustomerService access."),
]

record_id = 1
rows_va = [
    Row(
        RecordID=i + 1, ModelName=MODEL_NAME, RecordType="verified_answer",
        TriggerText=trigger, ResponseText=response, LinkedKPICode=code,
        IsDraft=0, CreatedDate=date.fromisoformat(CERTIFIED_DATE),
        IsCertified=1, CertifiedBy=CERTIFIED_BY, CertifiedDate=date.fromisoformat(CERTIFIED_DATE),
    )
    for i, (code, trigger, response) in enumerate(verified_answers)
]
record_id = len(rows_va) + 1

AI_SCHEMA = StructType([
    StructField("RecordID",      IntegerType(), True),
    StructField("ModelName",     StringType(),  True),
    StructField("RecordType",    StringType(),  True),
    StructField("TriggerText",   StringType(),  True),
    StructField("ResponseText",  StringType(),  True),
    StructField("LinkedKPICode", StringType(),  True),
    StructField("IsDraft",       IntegerType(), True),
    StructField("CreatedDate",   DateType(),    True),
    StructField("IsCertified",   IntegerType(), True),
    StructField("CertifiedBy",   StringType(),  True),
    StructField("CertifiedDate", DateType(),    True),
])

df_va = spark.createDataFrame(rows_va, schema=AI_SCHEMA)

if DEMO_MODE:
    print(f"[DEMO_MODE] Verified answers — {len(rows_va)} certified KPI and Maria source-story rows:\n")
    df_va.select("RecordID", "LinkedKPICode", "TriggerText").show(truncate=60)
else:
    # Deterministic refresh: clear current baseline-seed verified answers for this model, then
    # reinsert canonical seed rows. G17-R3 structural fix (same root cause as the ai_instruction
    # guard below): a real 2026-08-10 regression silently wiped a governance-approved
    # (IsCertified=1) verified answer via this exact blanket DELETE, only patched at the time by
    # baking the approved text into the hardcoded rows_va list below. That workaround does not
    # protect any FUTURE governance-approved verified answer not yet added to this list -- this
    # guard closes the root cause instead: only rows NOT certified, or certified under this
    # notebook's own baseline-seed authority (CERTIFIED_BY = "Victoria Tan"), are eligible for this reseed --
    spark.sql(
        f"DELETE FROM {METADATA_LAKEHOUSE}.ai_metadata "
        f"WHERE ModelName = {_sql_string(MODEL_NAME)} "
        f"AND RecordType = 'verified_answer' "
        f"AND IsDraft = 0 "
        f"AND (IsCertified IS NULL OR IsCertified = 0 OR CertifiedBy = {_sql_string(CERTIFIED_BY)})"
    )
    df_va.write.format("delta").mode("append").option("mergeSchema", "true") \
         .saveAsTable(f"{METADATA_LAKEHOUSE}.ai_metadata")
    print(f"ai_metadata refreshed: {len(rows_va)} verified answers")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-4, G4 — Seed ai_metadata: model-level AI instruction rows
# Provides Copilot with business context, terminology, and certified KPI reference

certified_kpi_instruction = (
    "Five certified call center KPIs: "
    "FCR target 78% (warning <72%, critical <65%); "
    "CSAT target 4.2/5 (warning <3.8, critical <3.4); "
    "PP_RNW_RATE target 82% (warning <75%, critical <68%); "
    "AHT target 420s billing queue (warning >480s, critical >540s); "
    "SLA_BRCH_RATE target 5% (warning >10%, critical >15%). "
    "When no explicit date filter is requested, certified KPI answers default to a rolling 12-month window "
    "ending on the latest available model date. "
    f"Only IsCertified=1 KPIs have been approved by {CERTIFIED_BY}. "
    "Do not present non-certified measures as authoritative business KPIs. Use the semantic model measure "
    "definitions as the source of truth."
)

ai_instructions = [
    ("Business Context", "Enercare context",
     "Enercare is a Canadian home services company providing HVAC maintenance, water heater rentals, "
     "Protection Plans (PP), and Ecobee smart thermostat installation in Ontario. "
     "Billing systems: ZUORA (recurring), NS (NetSuite), CLARIFY (CRM/field service). "
     "PP = Protection Plan throughout this system. MRR = Monthly Recurring Revenue. "
     "The contact center handles billing, PP renewal, HVAC service, emergency, new sales, and Ecobee support queues."),
    ("Critical Terminology", "Enercare terminology",
     "FCR = First Contact Resolution (resolved without callback in 5 business days). "
     "CSAT = Customer Satisfaction Score (1–5 IVR survey, ~22% response rate). "
     "AHT = Average Handle Time (talk + hold + wrap seconds). "
     "PP_RNW_RATE = Protection Plan Renewal Rate (target 82%). "
     "SLA Breach = field technician missed committed service window. "
     "WH = Water Heater. HVAC = Heating Ventilation Air Conditioning. "
     "MUR = Multi-Unit Residential. FSA = Forward Sortation Area (first 3 chars of postal code)."),
    ("KPI Definitions", "certified KPI reference", certified_kpi_instruction),
    ("Maria Source Story", "Maria Castellanos furnace scenario",
     "Maria Castellanos is seeded as source customer account EC18374622, a residential customer in Markham "
     "FSA L4G. Her Lennox SLP98V furnace has a NoHeat service request in GTA North that missed the 24-hour "
     "SLA while an 89.95 monthly charge posted. Tom Nguyen is the agent, Victoria Tan reviews the "
     "customer-experience impact, Ci Zhu answers the audit lineage question, and Ranbir Singh owns the "
     "service dispatch remediation. Ground answers through Customer 360, Service Performance, Billing "
     "Health, customer_consents, customer_complaints, and audit_data_access."),
    ("Verified Answer Consistency", "verified answer output contract",
        "Apply this contract only to verified KPI analytics answers (metric/percentage/calculation outputs). "
        "Do not apply this contract to operational customer service issues, request/ticket status details, "
        "dispatch updates, or case-level troubleshooting responses. "
        "When a user question matches a verified trigger after lowercasing and trimming terminal punctuation "
        "(such as ?, !, .), return the verified answer directly without asking clarifying questions. "
          "For all verified KPI answers, always include an explicit calculation window. Default window is rolling "
      "12 months ending on the latest available model date, unless the user specifies a different date range. "
          "Do not ask a follow-up question just to establish the default KPI time window. "
     "When returning a KPI value, include: Calculation Window, Numerator, Denominator, and Applied Filters. "
     "Do not return KPI percentages without those context fields."),
    # NOTE (hybrid grounding refactor, 2026-08-10): the "Operational Routing", "Request Detail
    # Output Rules", and "Maria Seed Guardrail" rows previously seeded here were removed —
    # request-ID-first sequencing, account normalization, and required response-field structure
    # are agent-level interaction rules and are now owned solely by the Data Agent's
    # stage_config.json (aiInstructions). This annotation stays limited to KPI/business/glossary
    # meaning so the two layers stop restating each other.
]

rows_instr = [
    Row(
        RecordID=record_id + i, ModelName=MODEL_NAME, RecordType="ai_instruction",
        TriggerText=trigger, ResponseText=content, LinkedKPICode=None,
        IsDraft=0, CreatedDate=date.fromisoformat(CERTIFIED_DATE),
        IsCertified=1, CertifiedBy=CERTIFIED_BY, CertifiedDate=date.fromisoformat(CERTIFIED_DATE),
    )
    for i, (title, trigger, content) in enumerate(ai_instructions)
]

df_instr = spark.createDataFrame(rows_instr, schema=AI_SCHEMA)

if DEMO_MODE:
    print(f"[DEMO_MODE] AI instruction rows — {len(rows_instr)} rows:\n")
    df_instr.select("RecordID", "RecordType", "TriggerText").show(truncate=60)
else:
    # Deterministic refresh: clear current baseline-seed AI instruction rows for this model, then
    # reinsert canonical rows. G17-R3 structural fix: rows with IsCertified=1 stamped by a REAL
    # governance approval (07_apply_approved_changes's apply-on-approve, always the real approver's
    # UPN) must NEVER be
    # wiped by this hardcoded-list reseed. Only rows not certified, or certified under this
    # notebook's own baseline-seed authority (CERTIFIED_BY = "Victoria Tan"), are eligible for this reseed --
    # this closes the 2026-08-10 silent-wipe regression class of bug at its root, rather
    # than only patching it by keeping the hardcoded list in sync.
    spark.sql(
        f"DELETE FROM {METADATA_LAKEHOUSE}.ai_metadata "
        f"WHERE ModelName = {_sql_string(MODEL_NAME)} "
        f"AND RecordType = 'ai_instruction' "
        f"AND IsDraft = 0 "
        f"AND (IsCertified IS NULL OR IsCertified = 0 OR CertifiedBy = {_sql_string(CERTIFIED_BY)})"
    )
    df_instr.write.format("delta").mode("append").option("mergeSchema", "true") \
            .saveAsTable(f"{METADATA_LAKEHOUSE}.ai_metadata")
    print(f"ai_metadata refreshed: {len(rows_instr)} AI instruction rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# G1-9 — Rebuild vw_business_metadata_current
# Extends existing view to include ai_metadata with SourceTable discriminator

BUSINESS_METADATA_TABLE = "vw_business_metadata_current"

sql_view = f"""
SELECT
    'asset'          AS RecordCategory,
    'asset_metadata' AS SourceTable,
    ObjectName       AS ObjectKey,
    Description,
    Owner,
    Steward,
    Domain,
    Sensitivity,
    IsDraft,
    DefinitionHash,
    CAST(NULL AS STRING) AS KPICode,
    CAST(NULL AS INT)    AS IsCertified,
    CAST(NULL AS STRING) AS Formula,
    CAST(NULL AS STRING) AS TriggerText,
    CAST(NULL AS STRING) AS ResponseText
FROM {METADATA_LAKEHOUSE}.asset_metadata

UNION ALL

SELECT
    'column'           AS RecordCategory,
    'column_metadata'  AS SourceTable,
    CONCAT(a.ObjectName, '.', c.ColumnName) AS ObjectKey,
    c.Description,
    CAST(NULL AS STRING) AS Owner,
    CAST(NULL AS STRING) AS Steward,
    CAST(NULL AS STRING) AS Domain,
    CAST(NULL AS STRING) AS Sensitivity,
    c.IsDraft,
    CAST(NULL AS STRING) AS DefinitionHash,
    CAST(NULL AS STRING) AS KPICode,
    CAST(NULL AS INT)    AS IsCertified,
    CAST(NULL AS STRING) AS Formula,
    c.ColumnName         AS TriggerText,
    CAST(NULL AS STRING) AS ResponseText
FROM {METADATA_LAKEHOUSE}.column_metadata c
JOIN {METADATA_LAKEHOUSE}.asset_metadata a ON a.AssetId = c.AssetId

UNION ALL

SELECT
    'kpi'           AS RecordCategory,
    'kpi_metadata'  AS SourceTable,
    KPICode         AS ObjectKey,
    Description,
    Owner,
    CAST(NULL AS STRING) AS Steward,
    Domain,
    CAST(NULL AS STRING) AS Sensitivity,
    IsDraft,
    CAST(NULL AS STRING) AS DefinitionHash,
    KPICode,
    IsCertified,
    Formula,
    CAST(NULL AS STRING) AS TriggerText,
    CAST(NULL AS STRING) AS ResponseText
FROM {METADATA_LAKEHOUSE}.kpi_metadata

UNION ALL

SELECT
    RecordType           AS RecordCategory,
    'ai_metadata'        AS SourceTable,
    COALESCE(LinkedKPICode, ModelName) AS ObjectKey,
    ResponseText         AS Description,
    CAST(NULL AS STRING) AS Owner,
    CAST(NULL AS STRING) AS Steward,
    CAST(NULL AS STRING) AS Domain,
    CAST(NULL AS STRING) AS Sensitivity,
    IsDraft,
    CAST(NULL AS STRING) AS DefinitionHash,
    LinkedKPICode        AS KPICode,
    CAST(NULL AS INT)    AS IsCertified,
    CAST(NULL AS STRING) AS Formula,
    TriggerText,
    ResponseText
FROM {METADATA_LAKEHOUSE}.ai_metadata
""".strip()

if DEMO_MODE:
    print("[DEMO_MODE] Would rebuild vw_business_metadata_current with 4-branch UNION ALL.")
    print("Branches: asset_metadata | column_metadata | kpi_metadata | ai_metadata")
    print("\nFirst 500 chars of SQL:\n")
    print(sql_view[:500])
else:
    materialized_df = spark.sql(sql_view)
    try:
        spark.sql(f"DROP VIEW IF EXISTS {BUSINESS_METADATA_TABLE}")
    except Exception:
        pass
    try:
        spark.sql(f"DROP TABLE IF EXISTS {BUSINESS_METADATA_TABLE}")
    except Exception:
        pass
    (
        materialized_df.write
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .format("delta")
        .saveAsTable(BUSINESS_METADATA_TABLE)
    )
    spark.catalog.refreshTable(BUSINESS_METADATA_TABLE)
    counts = spark.sql(
        f"SELECT SourceTable, COUNT(*) AS rows "
        f"FROM {BUSINESS_METADATA_TABLE} "
        f"GROUP BY SourceTable ORDER BY SourceTable"
    )
    materialized_count = spark.table(BUSINESS_METADATA_TABLE).count()
    expected_materialized_count = (
        spark.table(f"{METADATA_LAKEHOUSE}.asset_metadata").count()
        + spark.table(f"{METADATA_LAKEHOUSE}.column_metadata").count()
        + spark.table(f"{METADATA_LAKEHOUSE}.kpi_metadata").count()
        + spark.table(f"{METADATA_LAKEHOUSE}.ai_metadata").count()
    )
    if materialized_count != expected_materialized_count:
        raise RuntimeError(
            "vw_business_metadata_current count mismatch: "
            f"expected={expected_materialized_count}, actual={materialized_count}"
        )
    print("vw_business_metadata_current rebuilt:")
    counts.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Summary

total_va    = len(rows_va)
total_instr = len(rows_instr)

if DEMO_MODE:
    print(f"""
lh_metadata schema extension — DEMO_MODE preview (no changes written)
  kpi_metadata:   +10 columns queued (ALTER TABLE)
  ai_metadata:    CREATE TABLE queued
  data_owners:    CREATE TABLE queued
  lineage_edges:  CREATE TABLE queued
  kpi_metadata:   17 KPIs queued (12 existing measures + 5 call center)
  ai_metadata:    {total_va} verified answers + {total_instr} AI instructions queued
  view:           vw_business_metadata_current rebuild queued

Set DEMO_MODE = False and re-run to execute.
Gaps addressed: G1-3 G1-4 G1-5 G1-7 G2-1 G2-2 G1-9
""")
else:
    kpi_n = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.kpi_metadata").first()["n"]
    ai_n  = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.ai_metadata").first()["n"]
    owners_n = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.data_owners").first()["n"]
    lineage_n = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_LAKEHOUSE}.lineage_edges").first()["n"]
    print(f"""
lh_metadata schema extension complete
  kpi_metadata:   10 new columns added | {kpi_n} total KPI rows
  ai_metadata:    created | {ai_n} total rows ({total_va} verified answers + {total_instr} instructions)
    data_owners:    created | {owners_n} populated domain rows
    lineage_edges:  created | {lineage_n} populated edges
  view:           vw_business_metadata_current rebuilt (4 branches)

Gaps closed: G1-3 [done]  G1-4 [done]  G1-5 [done]  G1-7 [done]  G2-1 [done]  G2-2 [done]  G1-9 [done]
""")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 1: Config and imports

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

CSV_ROOT = "/lakehouse/default/Files/purview"
SCHEMA = "metadata"
TARGET_LAKEHOUSE = "lh_metadata"
SOURCE_MODE = "sql_mirror"

# SQL-first lookup order for metadata source tables in mirrored SQL.
SQL_MIRROR_CATALOGS = ["sqldemo", "sqldemo_mirror", "sqldemo-mirror"]
SQL_MIRROR_SCHEMAS = ["dbo", "metadata"]
MIRROR_WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
# Keep both IDs to tolerate environment drift between mirror item GUID and logicalId.
MIRROR_ITEM_IDS = [
    "bf000a9e-6ac4-42a8-abe3-37c815bd2fe6",
    "09f6ffaf-5195-8491-4b62-625ebdf616e8",
]
MIRROR_DFS_HOSTS = [
    "onelake.dfs.fabric.microsoft.com",
    "westus3-onelake.dfs.fabric.microsoft.com",
]

SQL_SOURCE_TABLES = {
    "domains": ["governance_domains", "metadata_domains"],
    "data_products": ["governance_data_products", "metadata_data_products"],
    "glossary_terms": ["governance_glossary_terms", "metadata_glossary_terms"],
    "cdes": ["governance_cdes", "metadata_cdes"],
    "role_assignments": ["governance_role_assignments", "metadata_role_assignments"],
    "label_assignments": ["governance_label_assignments", "metadata_label_assignments"],
    "governance_change_requests": ["governance_change_requests"],
    "okrs": ["governance_okrs"],
    "okr_key_results": ["governance_okr_key_results"],
    "okr_data_products": ["governance_okr_data_products"],
}

print(f"CSV root: {CSV_ROOT}")
print(f"Target schema: {TARGET_LAKEHOUSE}.{SCHEMA}")
print(f"Source mode: {SOURCE_MODE}")

if SOURCE_MODE != "sql_mirror":
    raise ValueError("This step is configured for sql_mirror-only ingestion. Set SOURCE_MODE='sql_mirror'.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Validation helpers

print("[Cell 2] Initializing validation and source-resolution helpers...", flush=True)
print(
    f"[Cell 2] Source mode={SOURCE_MODE}; mirror catalogs={SQL_MIRROR_CATALOGS}; mirror schemas={SQL_MIRROR_SCHEMAS}",
    flush=True,
)
print(
    f"[Cell 2] Mirror path resolution enabled: workspace={MIRROR_WORKSPACE_ID}, item_ids={MIRROR_ITEM_IDS}",
    flush=True,
)

def validate_csv(df: pd.DataFrame, required_cols: list[str], enum_cols: dict[str, set[str]] | None = None) -> None:
    actual_cols = set(df.columns)
    missing = [c for c in required_cols if c not in actual_cols]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    enum_cols = enum_cols or {}
    for col_name, allowed in enum_cols.items():
        if col_name not in actual_cols:
            raise ValueError(f"Enum column not found: {col_name}")
        observed = set(df[col_name].dropna().astype(str).str.strip().unique())
        invalid = sorted(v for v in observed if v and v not in allowed)
        if invalid:
            raise ValueError(
                f"Column '{col_name}' has invalid enum values: {invalid}. "
                f"Allowed: {sorted(allowed)}"
            )


def try_load_sql_dataset(dataset_name: str) -> tuple[pd.DataFrame | None, str | None]:
    table_candidates = SQL_SOURCE_TABLES.get(dataset_name, [])
    attempted_names = []
    seen_names = set()

    def _identifier_variants(catalog: str, schema_name: str, table_name: str):
        return [
            f"{catalog}.{schema_name}.{table_name}",
            f"`{catalog}`.{schema_name}.{table_name}",
            f"`{catalog}`.`{schema_name}`.`{table_name}`",
        ]

    def _try_table(full_name: str):
        if full_name in seen_names:
            return None
        seen_names.add(full_name)
        attempted_names.append(full_name)
        try:
            # Mirror source schema (e.g. new ALTER TABLE ADD COLUMN) can lag behind the
            # Spark catalog's cached schema; force a refresh before reading.
            try:
                spark.catalog.refreshTable(full_name)
            except Exception:
                pass
            sdf = spark.table(full_name)
            return sdf.toPandas(), full_name
        except Exception:
            return None

    # Read physical mirror Delta paths first. The Spark catalog can return stale data
    # after a source refresh even when refreshTable succeeds.
    for host in MIRROR_DFS_HOSTS:
        for item_id in MIRROR_ITEM_IDS:
            for schema_name in SQL_MIRROR_SCHEMAS:
                for table_name in table_candidates:
                    delta_path = (
                        f"abfss://{MIRROR_WORKSPACE_ID}@{host}/"
                        f"{item_id}/Tables/{schema_name}/{table_name}"
                    )
                    source_name = f"delta.`{delta_path}`"
                    attempted_names.append(source_name)
                    try:
                        sdf = spark.read.format("delta").load(delta_path)
                        return sdf.toPandas(), source_name
                    except Exception:
                        continue

    # Fall back to registered mirror catalog names when direct paths are unavailable.
    for catalog in SQL_MIRROR_CATALOGS:
        for schema_name in SQL_MIRROR_SCHEMAS:
            for table_name in table_candidates:
                for full_name in _identifier_variants(catalog, schema_name, table_name):
                    loaded = _try_table(full_name)
                    if loaded is not None:
                        return loaded

    print(
        f"[Cell 2] SQL lookup miss for '{dataset_name}'. Attempted: {attempted_names}",
        flush=True,
    )
    return None, None


def load_metadata_dataset(dataset_name: str) -> tuple[pd.DataFrame, str]:
    sql_df, source_name = try_load_sql_dataset(dataset_name)
    if sql_df is not None:
        return sql_df, f"sql:{source_name}"

    raise ValueError(
        f"Mirrored metadata table for '{dataset_name}' was not found. "
        f"Checked catalogs={SQL_MIRROR_CATALOGS}, schemas={SQL_MIRROR_SCHEMAS}, candidates={SQL_SOURCE_TABLES.get(dataset_name, [])}. "
        "Prerequisite SQL objects appear missing from the mirrored source. "
        "Ensure sql/02_metadata_foundation/06_purview_metadata_schema.sql and sql/02_metadata_foundation/07_seed_purview_metadata.sql have been executed against sub2 Azure SQL, "
        "then refresh/confirm sqldemo mirror sync before rerunning this ingestion step. "
        "This step is SQL-mirror-only by design; direct CSV fallback is intentionally disabled."
    )


WRITTEN_TABLE_NAMES: dict[str, str] = {}


def write_table_from_pandas(df: pd.DataFrame, table_name: str) -> int:
    sdf = spark.createDataFrame(df)
    expected_count = int(len(df.index))
    table_candidates = [table_name]
    last_error = None
    for full_table in table_candidates:
        try:
            if table_name == "okr_key_results":
                spark.sql(f"DROP TABLE IF EXISTS {full_table}")
            (
                sdf.write
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .format("delta")
                .saveAsTable(full_table)
            )
            delta_log_path = f"Tables/{table_name}/_delta_log"
            if not mssparkutils.fs.exists(delta_log_path):
                raise RuntimeError(f"Physical Delta log is missing for {full_table}: {delta_log_path}")
            spark.catalog.refreshTable(full_table)
            actual_count = int(spark.table(full_table).count())
            if actual_count != expected_count:
                raise RuntimeError(
                    f"Post-write count mismatch for {full_table}: "
                    f"expected={expected_count}, actual={actual_count}"
                )
            WRITTEN_TABLE_NAMES[table_name] = full_table
            return actual_count
        except Exception as ex:
            last_error = ex
            continue

    raise RuntimeError(
        f"Unable to write table '{table_name}'. Tried {table_candidates}. Last error: {last_error}"
    )


def resolve_written_table_name(table_name: str) -> str:
    return WRITTEN_TABLE_NAMES.get(table_name, f"{SCHEMA}.{table_name}")


def summary_count_select(table_name: str, expected: int) -> str:
    resolved = resolve_written_table_name(table_name)
    return f"SELECT '{table_name}' AS t, COUNT(*) AS actual, {expected} AS expected FROM {resolved}"


def build_summary_query() -> str:
    checks = [
        ("domains", 3),
        ("data_products", 3),
        ("glossary_terms", 35),
        ("cdes", 12),
        ("role_assignments", 48),
        ("label_assignments", 9),
        ("governance_change_requests", 8),
        ("okrs", 3),
        ("okr_key_results", 5),
        ("okr_data_products", 3),
    ]
    return "\nUNION ALL\n".join(summary_count_select(name, expected) for name, expected in checks) + "\nORDER BY t"


print(f"[Cell 2] Helpers ready. SQL dataset keys: {sorted(SQL_SOURCE_TABLES.keys())}", flush=True)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: domain-charter.csv -> metadata.domains

domains_required = [
    "domain_id",
    "domain_name",
    "domain_type",
    "description",
    "parent_domain",
    "status",
    "governance_domain_owners",
    "governance_domain_creators",
]

domain_type_allowed = {
    "Data domain",
    "Functional unit",
    "Line of business",
    "Regulatory",
    "Project",
}

domains_df, domains_source = load_metadata_dataset("domains")
validate_csv(domains_df, domains_required, {"domain_type": domain_type_allowed})
count_domains = write_table_from_pandas(domains_df, "domains")
print(f"domains loaded: {count_domains} (source={domains_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: data-product-catalog.csv -> metadata.data_products

data_products_required = [
    "data_product_id",
    "data_product_name",
    "product_type",
    "business_use_case",
    "audience",
    "owners",
    "attached_assets",
    "access_policy",
    "status",
    "parent_domain_id",
]

product_type_allowed = {
    "Dataset",
    "Dashboards/Reports",
    "Master and reference data",
}

data_products_df, data_products_source = load_metadata_dataset("data_products")
validate_csv(data_products_df, data_products_required, {"product_type": product_type_allowed})
count_data_products = write_table_from_pandas(data_products_df, "data_products")
print(f"data_products loaded: {count_data_products} (source={data_products_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: glossary-master.csv -> metadata.glossary_terms

glossary_required = [
    "term_code",
    "term_name",
    "acronyms",
    "parent_term_code",
    "domain_code",
    "owner_upn",
    "additional_owners_upn",
    "definition",
    "status",
    "is_cde",
    "industry_origin",
    "resources",
    "bound_assets",
]

glossary_df, glossary_source = load_metadata_dataset("glossary_terms")
validate_csv(glossary_df, glossary_required)
count_glossary = write_table_from_pandas(glossary_df, "glossary_terms")
print(f"glossary_terms loaded: {count_glossary} (source={glossary_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: cde-catalog.csv -> metadata.cdes

cde_required = [
    "cde_id",
    "cde_name",
    "expected_data_type",
    "business_definition",
    "owner_role",
    "status",
    "parent_glossary_term",
    "bound_columns",
]

expected_type_allowed = {"number", "text", "date", "Boolean"}

cde_df, cde_source = load_metadata_dataset("cdes")
validate_csv(cde_df, cde_required, {"expected_data_type": expected_type_allowed})
count_cdes = write_table_from_pandas(cde_df, "cdes")
print(f"cdes loaded: {count_cdes} (source={cde_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: role-directory.csv -> metadata.role_assignments

roles_required = [
    "role_id",
    "principal_email",
    "principal_display_name",
    "role_type",
    "scope_target",
    "scope_target_type",
    "governance_layer",
]

roles_df, roles_source = load_metadata_dataset("role_assignments")
validate_csv(roles_df, roles_required)
count_roles = write_table_from_pandas(roles_df, "role_assignments")
print(f"role_assignments loaded: {count_roles} (source={roles_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 8: label-policy.csv -> metadata.label_assignments

labels_required = [
    "label_id",
    "label_name",
    "sensitivity_tier",
    "protection_policy",
    "applies_to_asset_ids",
    "scope",
]

labels_df, labels_source = load_metadata_dataset("label_assignments")
validate_csv(labels_df, labels_required)
count_labels = write_table_from_pandas(labels_df, "label_assignments")
print(f"label_assignments loaded: {count_labels} (source={labels_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 8b: Phase 4 (P4-1 prerequisite) - dbo.governance_change_requests -> metadata.governance_change_requests
# Read-only working copy for the gated-approval demo; 07_apply_approved_changes
# reads the live SQL source directly rather than this copy, to avoid mirror lag
# on the Approved status transition, but this copy keeps the request log
# queryable from the same BI surfaces as the other governance_* tables.

gcr_required = [
    "request_id",
    "request_type",
    "target_object_label",
    "change_summary",
    "proposed_payload",
    "requested_by_upn",
    "status",
]

gcr_df, gcr_source = load_metadata_dataset("governance_change_requests")
validate_csv(gcr_df, gcr_required)
count_gcr = write_table_from_pandas(gcr_df, "governance_change_requests")
print(f"governance_change_requests loaded: {count_gcr} (source={gcr_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 8c: Ontology/OKR layer (G11-1) - dbo.governance_okrs / _key_results /
# _data_products -> metadata.okrs / okr_key_results / okr_data_products
# Business-objective layer that Purview's native OKR business concept links
# directly to Data Products; closes the top of the ontology graph above
# GlossaryTerm -> CDE and DataProduct -> Domain (see sql/02_metadata_foundation/11_ontology_okr_schema.sql).

okrs_required = [
    "okr_id",
    "okr_name",
    "domain_id",
    "definition",
    "owner_upn",
    "status",
]

okrs_df, okrs_source = load_metadata_dataset("okrs")
validate_csv(okrs_df, okrs_required)
count_okrs = write_table_from_pandas(okrs_df, "okrs")
print(f"okrs loaded: {count_okrs} (source={okrs_source})")

okr_key_results_required = [
    "key_result_id",
    "okr_id",
    "result_name",
    "metric_source",
    "goal_amount",
    "max_amount",
    "progress_status",
]

okr_key_results_df, okr_key_results_source = load_metadata_dataset("okr_key_results")
validate_csv(okr_key_results_df, okr_key_results_required)
count_okr_key_results = write_table_from_pandas(okr_key_results_df, "okr_key_results")
print(f"okr_key_results loaded: {count_okr_key_results} (source={okr_key_results_source})")

okr_data_products_required = [
    "okr_id",
    "data_product_id",
]

okr_data_products_df, okr_data_products_source = load_metadata_dataset("okr_data_products")
validate_csv(okr_data_products_df, okr_data_products_required)
count_okr_data_products = write_table_from_pandas(okr_data_products_df, "okr_data_products")
print(f"okr_data_products loaded: {count_okr_data_products} (source={okr_data_products_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 9: Summary counts (expected vs actual)

summary_query = build_summary_query()

summary_df = spark.sql(summary_query).withColumn(
    "status",
    F.when(F.col("actual") == F.col("expected"), F.lit("GREEN")).otherwise(F.lit("YELLOW")),
)

display(summary_df)

non_green_checks = summary_df.where(F.col("status") != "GREEN").count()
if non_green_checks:
    raise RuntimeError(f"Metadata foundation validation failed: {non_green_checks} non-GREEN check(s).")

print("NB_02 metadata foundation complete; semantic annotation reconciliation runs next in this notebook.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 10: Imports and config
# Purpose: cross-reference ingested governance metadata (glossary/CDE/data-product/label
# associations) against the semantic model's actual table/column names, resolving aliases,
# and write the reconciled sm_annotations working table.

import re
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

spark = SparkSession.builder.getOrCreate()

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
SEMANTIC_MODEL = "BrookfieldEnercare"
REQUIRED_METADATA_TABLES = {
    "glossary_terms": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.glossary_terms",
    "cdes": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.cdes",
    "data_products": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.data_products",
    "label_assignments": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.label_assignments",
}

TABLE_NAME_ALIASES = {
    "glossary_terms": ["glossary_terms", "governance_glossary_terms", "metadata_glossary_terms"],
    "cdes": ["cdes", "governance_cdes", "metadata_cdes"],
    "data_products": ["data_products", "governance_data_products", "metadata_data_products"],
    "label_assignments": ["label_assignments", "governance_label_assignments", "metadata_label_assignments"],
}

ANNOTATION_KEYS = {
    "cde": "CDE_Member_Of",
    "glossary": "Glossary_Term_References",
    "label": "Sensitivity_Label",
    "owner": "Data_Product_Owner",
}

SQL_TO_SEMANTIC_TABLE_MAP = {
    "customers": ["dim_customer"],
    "service_accounts": ["dim_service_account", "fct_service_request"],
    "equipment_registry": ["dim_equipment"],
    "products": ["dim_product"],
    "contracts": ["fct_contract_month", "fct_billing"],
    "service_requests": ["fct_service_request"],
    "billing_transactions": ["fct_billing"],
    "customer_consents": ["dim_customer"],
    "customer_complaints": ["fct_billing", "dim_customer"],
    "service_zones": ["fct_service_request"],
}

SEMANTIC_TABLE_ALIASES = {
    "fct_service_requests": "fct_service_request",
}

print(f"Semantic model: {SEMANTIC_MODEL}")
print(f"Required metadata schema: {METADATA_LAKEHOUSE}.{METADATA_SCHEMA}")


def _table_candidates(table_name: str):
    required_name = REQUIRED_METADATA_TABLES.get(table_name)
    if not required_name:
        raise ValueError(f"Unknown required metadata table key: {table_name}")

    aliases = TABLE_NAME_ALIASES.get(table_name, [table_name])
    candidates = []

    # Try 3-part then 2-part then unqualified names to tolerate catalog/schema drift.
    for alias in aliases:
        candidates.extend([
            f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.{alias}",
            f"{METADATA_SCHEMA}.{alias}",
            alias,
        ])

    # Deduplicate while preserving order.
    deduped = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)

    return deduped


def _read_table(table_name: str):
    last_error = None
    candidates = _table_candidates(table_name)
    for candidate in candidates:
        try:
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex

    raise RuntimeError(
        f"Could not resolve table '{table_name}'. "
        f"Candidates tried: {candidates}. "
        f"Last error: {last_error}. "
        "Required source: lh_metadata staged tables (schema-qualified or unqualified). "
        "Prerequisite: run nb_07a_ingest_customer_files first to populate "
        "glossary_terms/cdes/data_products (and optionally label_assignments) in lh_metadata."
    )


def _write_table_name(table_name: str):
    # Use two-part name for Fabric Spark catalog compatibility.
    return f"{METADATA_SCHEMA}.{table_name}"


WRITTEN_TABLE_NAMES: dict[str, str] = {}


def _write_table_candidates(table_name: str):
    return [table_name]


def _write_with_fallback(sdf, table_name: str):
    expected_count = int(sdf.count())
    last_error = None
    for candidate in _write_table_candidates(table_name):
        try:
            (
                sdf.write
                .mode("overwrite")
                .format("delta")
                .saveAsTable(candidate)
            )
            spark.catalog.refreshTable(candidate)
            actual_count = int(spark.table(candidate).count())
            if actual_count != expected_count:
                raise RuntimeError(
                    f"Post-write count mismatch for {candidate}: "
                    f"expected={expected_count}, actual={actual_count}"
                )
            WRITTEN_TABLE_NAMES[table_name] = candidate
            return candidate
        except Exception as ex:
            last_error = ex

    raise RuntimeError(
        f"Could not write table '{table_name}'. Candidates tried: {_write_table_candidates(table_name)}. Last error: {last_error}"
    )


def _resolve_written_table_name(table_name: str):
    return WRITTEN_TABLE_NAMES.get(table_name, _write_table_name(table_name))


def _require_lakehouse_context():
    try:
        # A simple command that requires an attached default lakehouse context.
        spark.sql("SELECT current_database()").collect()
    except Exception as ex:
        raise RuntimeError(
            "No default lakehouse context is attached for this Spark session. "
            "Attach 'lh_metadata' as the default lakehouse for this notebook, then rerun Cell 1 and Cell 2. "
            "In Fabric: open the notebook Lakehouse selector and set default lakehouse to lh_metadata. "
            f"Original error: {ex}"
        )


def _log_nb02_diagnostic(stage: str, error: Exception):
    import traceback
    diag_row = {
        "stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error)[:4000],
        "traceback": traceback.format_exc()[:8000],
    }
    try:
        spark.createDataFrame([diag_row]).write.format("delta").mode("append").saveAsTable("nb02_diagnostics_log")
        print(f"[DIAG] Logged failure at stage '{stage}' to nb02_diagnostics_log")
    except Exception as log_ex:
        print(f"[DIAG] Could not log diagnostic for stage '{stage}': {log_ex}")
        print(f"[DIAG] Original error at stage '{stage}': {type(error).__name__}: {error}")


print(f"Required metadata tables: {REQUIRED_METADATA_TABLES}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 11: Read metadata source tables

try:
    print("[Cell 2] Starting metadata source reads...", flush=True)
    _require_lakehouse_context()
    print("[Cell 2] Lakehouse context check passed.", flush=True)

    glossary_df, glossary_source = _read_table("glossary_terms")
    print(f"[Cell 2] Resolved glossary_terms source: {glossary_source}", flush=True)

    cde_df, cde_source = _read_table("cdes")
    print(f"[Cell 2] Resolved cdes source: {cde_source}", flush=True)

    data_products_df, data_products_source = _read_table("data_products")
    print(f"[Cell 2] Resolved data_products source: {data_products_source}", flush=True)

    # Optional table in case labels were ingested already.
    try:
        labels_df, labels_source = _read_table("label_assignments")
        print(f"[Cell 2] Resolved label_assignments source: {labels_source}", flush=True)
    except Exception:
        labels_df = None
        labels_source = None
        print("[WARN] metadata.label_assignments not found; Sensitivity_Label rows will be sourced only from CDE metadata.", flush=True)


    def _safe_count(name, df):
        try:
            return df.count()
        except Exception as ex:
            print(f"[WARN] Could not count {name}: {ex}", flush=True)
            return None

    print(f"glossary_terms rows: {_safe_count('glossary_terms', glossary_df)} (source={glossary_source})", flush=True)
    print(f"cdes rows: {_safe_count('cdes', cde_df)} (source={cde_source})", flush=True)
    print(f"data_products rows: {_safe_count('data_products', data_products_df)} (source={data_products_source})", flush=True)
    if labels_df is not None:
        print(f"label_assignments rows: {_safe_count('label_assignments', labels_df)} (source={labels_source})", flush=True)

    print("[Cell 2] Metadata source reads completed.", flush=True)
except Exception as ex:
    _log_nb02_diagnostic("cell11_read_metadata_sources", ex)
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 12: Read semantic inventory with SemPy

USE_SEMPY_INVENTORY = False
fabric = None
if USE_SEMPY_INVENTORY:
    import sempy.fabric as fabric


def _collect_pairs(df, columns):
    if hasattr(df, "select") and hasattr(df, "collect"):
        return [tuple(row[c] for c in columns) for row in df.select(*columns).collect()]
    if hasattr(df, "iterrows"):
        return [tuple(row[c] for c in columns) for _, row in df.iterrows()]
    raise TypeError(f"Unsupported DataFrame type returned by SemPy: {type(df)}")


try:
    if not USE_SEMPY_INVENTORY:
        raise RuntimeError("SemPy inventory disabled; use MCP-verified sm_annotations targets.")
    tables_df = fabric.list_tables(dataset=SEMANTIC_MODEL)
    columns_df = fabric.list_columns(dataset=SEMANTIC_MODEL)
    measures_df = fabric.list_measures(dataset=SEMANTIC_MODEL)

    semantic_tables = sorted({str(name) for (name,) in _collect_pairs(tables_df, ["Name"])})
    semantic_columns = sorted({(str(t), str(c)) for t, c in _collect_pairs(columns_df, ["Table Name", "Column Name"])})
    semantic_measures = sorted({(str(t), str(m)) for t, m in _collect_pairs(measures_df, ["Table Name", "Measure Name"])})
except Exception:
    import traceback

    inventory_error = traceback.format_exc()
    print("[WARN] SemPy inventory failed; using verified sm_annotations targets.")
    print(inventory_error[-2000:])
    try:
        existing_annotations = spark.table("sm_annotations")
        semantic_tables = sorted(
            {
                str(row["table"])
                for row in existing_annotations.select("table").distinct().collect()
                if row["table"]
            }
        )
        semantic_columns = sorted(
            {
                (str(row["table"]), str(row["object_name"]))
                for row in existing_annotations.where(F.col("object_type") == "Column")
                .select("table", "object_name")
                .distinct()
                .collect()
            }
        )
        semantic_measures = sorted(
            {
                (str(row["table"]), str(row["object_name"]))
                for row in existing_annotations.where(F.col("object_type") == "Measure")
                .select("table", "object_name")
                .distinct()
                .collect()
            }
        )
        if not semantic_tables or not semantic_columns:
            raise RuntimeError(
                "SemPy inventory failed and sm_annotations did not contain a usable fallback inventory."
            )
    except Exception as fallback_ex:
        _log_nb02_diagnostic("cell12_sm_annotations_fallback", fallback_ex)
        raise

print(f"SemPy inventory: {len(semantic_tables)} table(s), {len(semantic_columns)} column(s), {len(semantic_measures)} measure(s)")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 13: Parse bound asset formats and build lookup maps


def _norm(value: str) -> str:
    return value.strip().lower()


def _canon(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(value))


def _split_bindings(raw: str):
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []

    pieces = re.split(r"[;,|\n]", text)
    return [p.strip() for p in pieces if p and p.strip()]


def _parse_asset_ref(token: str):
    # Formats supported:
    # - dbo.table.column
    # - dbo.table
    # - BrookfieldEnercare/table/column
    # - BrookfieldEnercare/_Measures/Measure Name
    source = token.strip()
    lower = source.lower()

    if lower == f"{SEMANTIC_MODEL.lower()}.semanticmodel":
        return {"kind": "Model", "table": None, "object": source, "source": source}

    if "/" in source:
        parts = [p.strip() for p in source.split("/") if p.strip()]
        if len(parts) >= 3 and parts[0].lower() == SEMANTIC_MODEL.lower():
            if parts[1] == "_Measures":
                return {"kind": "Measure", "table": "_Measures", "object": parts[2], "source": source}
            return {"kind": "Column", "table": parts[1], "object": parts[2], "source": source}
        if len(parts) == 2 and parts[0].lower() == SEMANTIC_MODEL.lower():
            return {"kind": "Table", "table": parts[1], "object": parts[1], "source": source}

    if "." in source and source.count(".") == 1:
        left, right = [p.strip() for p in source.split(".", 1)]
        if left.lower() == SEMANTIC_MODEL.lower():
            return {"kind": "Table", "table": right, "object": right, "source": source}

    if lower.startswith("dbo."):
        dotted = source.split(".")
        if len(dotted) >= 3:
            return {
                "kind": "SqlColumn",
                "table": dotted[1],
                "object": ".".join(dotted[2:]),
                "source": source,
            }
        if len(dotted) == 2:
            return {"kind": "SqlTable", "table": dotted[1], "object": dotted[1], "source": source}

    return {"kind": "Unknown", "table": None, "object": source, "source": source}


columns_by_name = {}
for table_name, column_name in semantic_columns:
    key = _norm(column_name)
    columns_by_name.setdefault(key, []).append((table_name, column_name))

measures_by_name = {}
for table_name, measure_name in semantic_measures:
    key = _norm(measure_name)
    measures_by_name.setdefault(key, []).append((table_name, measure_name))

measure_canon_pairs = [(_canon(m), t, m) for t, m in semantic_measures]

semantic_tables_by_name = {_norm(name): name for name in semantic_tables}


def _resolve_targets(parsed_asset):
    kind = parsed_asset["kind"]

    if kind == "Column":
        key = (_norm(parsed_asset["table"]), _norm(parsed_asset["object"]))
        matches = [
            (t, c)
            for t, c in semantic_columns
            if _norm(t) == key[0] and _norm(c) == key[1]
        ]
        return [("Column", t, c) for t, c in matches]

    if kind == "Measure":
        matches = [
            (t, m)
            for t, m in semantic_measures
            if _norm(m) == _norm(parsed_asset["object"]) and (t == parsed_asset["table"] or parsed_asset["table"] == "_Measures")
        ]
        if not matches:
            matches = measures_by_name.get(_norm(parsed_asset["object"]), [])
        if not matches:
            token_canon = _canon(parsed_asset["object"])
            matches = [(t, m) for m_canon, t, m in measure_canon_pairs if m_canon == token_canon]
        if not matches and len(_canon(parsed_asset["object"])) <= 6:
            token_canon = _canon(parsed_asset["object"])
            matches = [(t, m) for m_canon, t, m in measure_canon_pairs if token_canon and token_canon in m_canon]
        return [("Measure", t, m) for t, m in matches]

    if kind == "Table":
        table_key = _norm(parsed_asset["table"])
        table_key = _norm(SEMANTIC_TABLE_ALIASES.get(table_key, table_key))
        resolved_name = semantic_tables_by_name.get(table_key)
        if resolved_name:
            return [("Table", resolved_name, resolved_name)]
        return []

    if kind == "SqlColumn":
        matches = [("Column", t, c) for t, c in columns_by_name.get(_norm(parsed_asset["object"]), [])]
        if matches:
            return matches

        mapped_tables = SQL_TO_SEMANTIC_TABLE_MAP.get(_norm(parsed_asset.get("table") or ""), [])
        if mapped_tables:
            mapped_set = {_norm(t) for t in mapped_tables}
            scoped = [
                ("Column", t, c)
                for t, c in semantic_columns
                if _norm(t) in mapped_set and _norm(c) == _norm(parsed_asset["object"])
            ]
            if scoped:
                return scoped

        return []

    if kind == "SqlTable":
        mapped_tables = SQL_TO_SEMANTIC_TABLE_MAP.get(_norm(parsed_asset.get("table") or ""), [])
        resolved = []
        for table_name in mapped_tables:
            resolved_name = semantic_tables_by_name.get(_norm(table_name))
            if resolved_name:
                resolved.append(("Table", resolved_name, resolved_name))
        return resolved

    return []


print(
    f"[Cell 4] Parser ready. semantic_tables={len(semantic_tables)}, "
    f"semantic_columns={len(semantic_columns)}, semantic_measures={len(semantic_measures)}",
    flush=True,
)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 14: Build annotation rows

try:
    annotation_rows = []
    binding_stats = {
        "tokens_total": 0,
        "tokens_resolved": 0,
        "targets_total": 0,
    }
    unresolved_token_samples = set()


    def _append_annotation(targets, key_name, value):
        if value is None:
            return
        value_text = str(value).strip()
        if not value_text:
            return

        for object_type, table_name, object_name in targets:
            annotation_rows.append(
                {
                    "model": SEMANTIC_MODEL,
                    "table": table_name,
                    "object_type": object_type,
                    "object_name": object_name,
                    "annotation_key": key_name,
                    "annotation_value": value_text,
                }
            )


    def _resolve_targets_with_stats(token: str):
        binding_stats["tokens_total"] += 1
        parsed = _parse_asset_ref(token)
        targets = _resolve_targets(parsed)
        if targets:
            binding_stats["tokens_resolved"] += 1
            binding_stats["targets_total"] += len(targets)
        else:
            if parsed.get("kind") == "Model":
                return targets
            if len(unresolved_token_samples) < 20:
                unresolved_token_samples.add(token)
        return targets


    for row in glossary_df.collect():
        term_code = getattr(row, "term_code", None) or getattr(row, "term_name", None)
        term_name = getattr(row, "term_name", None)
        glossary_value = " | ".join([v for v in [term_code, term_name] if v])
        for token in _split_bindings(getattr(row, "bound_assets", None)):
            targets = _resolve_targets_with_stats(token)
            _append_annotation(targets, ANNOTATION_KEYS["glossary"], glossary_value)

    for row in cde_df.collect():
        cde_id = getattr(row, "cde_id", None) or getattr(row, "cde_code", None) or getattr(row, "cde_name", None)
        cde_name = getattr(row, "cde_name", None)
        cde_value = " | ".join([v for v in [cde_id, cde_name] if v])
        sensitivity = getattr(row, "sensitivity_label", None)

        for token in _split_bindings(getattr(row, "bound_columns", None)):
            targets = _resolve_targets_with_stats(token)
            _append_annotation(targets, ANNOTATION_KEYS["cde"], cde_value)
            _append_annotation(targets, ANNOTATION_KEYS["label"], sensitivity)

    if labels_df is not None:
        for row in labels_df.collect():
            label_name = getattr(row, "label_name", None)
            applies_to = getattr(row, "applies_to_asset_ids", None)
            for token in _split_bindings(applies_to):
                targets = _resolve_targets_with_stats(token)
                _append_annotation(targets, ANNOTATION_KEYS["label"], label_name)

    for row in data_products_df.collect():
        product_id = getattr(row, "data_product_id", None) or getattr(row, "product_code", None)
        owner = getattr(row, "owners", None) or getattr(row, "owner_upn", None) or getattr(row, "owner_name", None)

        owner_value_parts = [v for v in [product_id, owner] if v]
        owner_value = " | ".join(owner_value_parts)

        binding_fields = [
            getattr(row, "attached_assets", None),
            getattr(row, "semantic_model_assets", None),
            getattr(row, "fabric_assets", None),
            getattr(row, "sql_assets", None),
        ]
        binding_tokens = []
        for raw in binding_fields:
            binding_tokens.extend(_split_bindings(raw))

        for token in binding_tokens:
            targets = _resolve_targets_with_stats(token)
            _append_annotation(targets, ANNOTATION_KEYS["owner"], owner_value)

    print(f"Raw annotation rows created: {len(annotation_rows)}")
    print(
        f"[Cell 5] Binding resolution stats: tokens_total={binding_stats['tokens_total']}, "
        f"tokens_resolved={binding_stats['tokens_resolved']}, targets_total={binding_stats['targets_total']}",
        flush=True,
    )
    if unresolved_token_samples:
        sample = sorted(unresolved_token_samples)[:10]
        print(f"[Cell 5][WARN] Unresolved binding token sample ({len(sample)} shown): {sample}", flush=True)
except Exception as ex:
    _log_nb02_diagnostic("cell14_build_annotation_rows", ex)
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 15: Write sm_annotations (overwrite with schema fallback)

try:
    annotation_schema = StructType(
        [
            StructField("model", StringType(), False),
            StructField("table", StringType(), False),
            StructField("object_type", StringType(), False),
            StructField("object_name", StringType(), False),
            StructField("annotation_key", StringType(), False),
            StructField("annotation_value", StringType(), False),
        ]
    )

    annotations_sdf = spark.createDataFrame(annotation_rows, annotation_schema)
    annotations_sdf = annotations_sdf.dropDuplicates(
        ["model", "table", "object_type", "object_name", "annotation_key", "annotation_value"]
    )

    written_sm_annotations_table = _write_with_fallback(annotations_sdf, "sm_annotations")

    print(f"sm_annotations rows written: {annotations_sdf.count()}")
    print(f"sm_annotations target table: {written_sm_annotations_table}")
except Exception as ex:
    _log_nb02_diagnostic("cell15_write_sm_annotations", ex)
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 16: Summary by annotation key

try:
    summary_df = (
        spark.table(_resolve_written_table_name("sm_annotations"))
        .groupBy("annotation_key")
        .agg(F.count("*").alias("annotation_count"))
        .orderBy("annotation_key")
    )

    display(summary_df)
except Exception as ex:
    _log_nb02_diagnostic("cell16_summary", ex)
    raise

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
