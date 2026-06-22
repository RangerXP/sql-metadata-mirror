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

# Fabric Notebook: nb_04a_extend_metadata_schema
# Gaps: G1-3, G1-4, G1-5, G1-7, G2-1, G2-2
# Purpose: Extend lh_metadata schema and seed certified KPI definitions
#
# Run order: after nb_02_metadata_pipeline_demo (lh_metadata must exist)
# Default lakehouse: lh_metadata
#
# DEMO_MODE = True  → print all SQL/data; no writes to Delta
# DEMO_MODE = False → execute all ALTER / CREATE / INSERT statements

DEMO_MODE = False           # default safe mode; set False only for live writes

METADATA_LAKEHOUSE = "lh_metadata"
CERTIFIED_BY       = "Victoria Tan"
CERTIFIED_DATE     = "2026-05-06"
MODEL_NAME         = "BrookfieldEnercare"

print(f"nb_04a | DEMO_MODE={DEMO_MODE} | lakehouse={METADATA_LAKEHOUSE}")

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
# Source-to-target graph used by nb_06_purview_lineage.py (G7)

sql_create_lineage = f"""
CREATE TABLE IF NOT EXISTS {METADATA_LAKEHOUSE}.lineage_edges (
    EdgeID         INT       COMMENT 'Monotonic edge identifier',
    SourceQName    STRING    COMMENT 'Purview qualified name of upstream asset',
    TargetQName    STRING    COMMENT 'Purview qualified name of downstream asset',
    ProcessName    STRING    COMMENT 'Notebook or pipeline performing the transform',
    TransformType  STRING    COMMENT 'mirror | notebook | dataflow | direct_lake'
)
USING DELTA
COMMENT 'Source-to-target lineage graph — consumed by nb_06_purview_lineage.py'
""".strip()

if DEMO_MODE:
    print("[DEMO_MODE] Would execute:\n")
    print(sql_create_lineage)
    print("[DEMO_MODE] Would populate lineage_edges from asset_metadata.UpstreamAssets relationships extracted by nb_02")
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
    Row(
        KPIName=name, Formula=formula, Description=desc, Domain=domain, Owner=owner,
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
    ("SLA_BRCH_RATE", "what's the SLA for a no-heat call?",
     "For this demo, a NoHeat call is treated as an emergency service request with a 24-hour SLA window. "
     "An SLA breach occurs when service completion is later than 24 hours from request creation. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "what is the SLA for a no-heat call?",
     "For this demo, a NoHeat call is treated as an emergency service request with a 24-hour SLA window. "
     "An SLA breach occurs when service completion is later than 24 hours from request creation. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "what's the sla for a no heat call",
     "For this demo, a NoHeat call is treated as an emergency service request with a 24-hour SLA window. "
     "An SLA breach occurs when service completion is later than 24 hours from request creation. "
     "Use SLA_BRCH_RATE for aggregate tracking; target breach rate is 5%."),
    ("SLA_BRCH_RATE", "no-heat sla",
     "NoHeat emergency requests use a 24-hour SLA window in this demo. "
     "Track aggregate performance with SLA_BRCH_RATE (target breach rate: 5%)."),
    ("SLA_BRCH_RATE", "no heat sla",
     "NoHeat emergency requests use a 24-hour SLA window in this demo. "
     "Track aggregate performance with SLA_BRCH_RATE (target breach rate: 5%)."),
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
])

df_va = spark.createDataFrame(rows_va, schema=AI_SCHEMA)

if DEMO_MODE:
    print(f"[DEMO_MODE] Verified answers — {len(rows_va)} certified KPI and Maria source-story rows:\n")
    df_va.select("RecordID", "LinkedKPICode", "TriggerText").show(truncate=60)
else:
    # Deterministic refresh: clear current certified verified answers for this model,
    # then reinsert canonical seed rows to avoid stale/duplicate trigger drift.
    spark.sql(
        f"DELETE FROM {METADATA_LAKEHOUSE}.ai_metadata "
        f"WHERE ModelName = {_sql_string(MODEL_NAME)} "
        f"AND RecordType = 'verified_answer' "
        f"AND IsDraft = 0"
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
    ("Operational Routing", "data agent routing for request keys",
     "This semantic model is for KPI analytics, governed business context, and high-level customer story "
     "explanations. For operational request-detail prompts containing concrete request identifiers, work order "
     "numbers, ticket IDs, or service dispatch questions, direct the user to the Enercare Data Agent rather "
     "than answering from this semantic model."),
    ("Request Detail Output Rules", "service request detail response rules",
     "When user intent includes a concrete service request identifier, such as a numeric RequestKey or an "
     "SR-formatted request code, do not treat this semantic model as the primary operational answer surface. "
     "Defer those request-detail prompts to the Enercare Data Agent. If a response is still produced here, keep "
     "it text-first with explicit field labels, avoid visual/table formatting artifacts, and state missing fields "
     "as 'not available in the current model rows' without inferring values."),
]

rows_instr = [
    Row(
        RecordID=record_id + i, ModelName=MODEL_NAME, RecordType="ai_instruction",
        TriggerText=trigger, ResponseText=content, LinkedKPICode=None,
        IsDraft=0, CreatedDate=date.fromisoformat(CERTIFIED_DATE),
    )
    for i, (title, trigger, content) in enumerate(ai_instructions)
]

df_instr = spark.createDataFrame(rows_instr, schema=AI_SCHEMA)

if DEMO_MODE:
    print(f"[DEMO_MODE] AI instruction rows — {len(rows_instr)} rows:\n")
    df_instr.select("RecordID", "RecordType", "TriggerText").show(truncate=60)
else:
    # Deterministic refresh: clear current certified AI instruction rows for this model,
    # then reinsert canonical rows to prevent duplicate/legacy instruction accumulation.
    spark.sql(
        f"DELETE FROM {METADATA_LAKEHOUSE}.ai_metadata "
        f"WHERE ModelName = {_sql_string(MODEL_NAME)} "
        f"AND RecordType = 'ai_instruction' "
        f"AND IsDraft = 0"
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

sql_view = f"""
CREATE OR REPLACE VIEW {METADATA_LAKEHOUSE}.vw_business_metadata_current AS

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
    spark.sql(sql_view)
    counts = spark.sql(
        f"SELECT SourceTable, COUNT(*) AS rows "
        f"FROM {METADATA_LAKEHOUSE}.vw_business_metadata_current "
        f"GROUP BY SourceTable ORDER BY SourceTable"
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
