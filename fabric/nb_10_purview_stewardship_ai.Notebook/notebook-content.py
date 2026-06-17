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
# META     },
# META     "environment": {
# META       "environmentId": "f258b6d4-a1a7-b77b-4ffa-7812e76e51aa",
# META       "workspaceId": "00000000-0000-0000-0000-000000000000"
# META     }
# META   }
# META }

# CELL ********************

# Cell 1: Imports and config

import json
from datetime import date, timedelta
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
SEMANTIC_MODEL = "BrookfieldEnercare"
OUTPUT_ROOT = "/lakehouse/default/Files/purview_publish/phase_08_10_stewardship_ai"
CERTIFICATION_STATUSES = ["Certified", "Published", "Approved"]
STALE_REVIEW_DAYS = 180

print(f"Semantic model: {SEMANTIC_MODEL}")
print(f"Output root: {OUTPUT_ROOT}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read metadata tables


def _table_candidates(table_name: str):
    return [
        f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.{table_name}",
        f"{METADATA_SCHEMA}.{table_name}",
        table_name,
    ]


def _read_table(table_name: str, required=True):
    last_error = None
    for candidate in _table_candidates(table_name):
        try:
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex
    if required:
        raise RuntimeError(f"Could not resolve table '{table_name}'. Last error: {last_error}")
    return None, None


domains_df, domains_source = _read_table("domains")
data_products_df, data_products_source = _read_table("data_products")
glossary_df, glossary_source = _read_table("glossary_terms")
cde_df, cde_source = _read_table("cdes")
roles_df, roles_source = _read_table("role_assignments", required=False)
labels_df, labels_source = _read_table("label_assignments", required=False)
semantic_annotations_df, semantic_annotations_source = _read_table("semantic_annotation_plan", required=False)

print(f"domains rows: {domains_df.count()} (source={domains_source})")
print(f"data_products rows: {data_products_df.count()} (source={data_products_source})")
print(f"glossary_terms rows: {glossary_df.count()} (source={glossary_source})")
print(f"cdes rows: {cde_df.count()} (source={cde_source})")
if roles_df is not None:
    print(f"role_assignments rows: {roles_df.count()} (source={roles_source})")
if labels_df is not None:
    print(f"label_assignments rows: {labels_df.count()} (source={labels_source})")
if semantic_annotations_df is not None:
    print(f"semantic_annotation_plan rows: {semantic_annotations_df.count()} (source={semantic_annotations_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build stewardship and certification scorecard


def _column_or_null(df, column_name):
    return F.col(column_name) if column_name in df.columns else F.lit(None).alias(column_name)


def _status_column(df):
    for name in ["status", "published_status", "certification_status"]:
        if name in df.columns:
            return F.col(name)
    return F.lit(None)


def _owner_column(df):
    for name in ["owners", "owner_upn", "business_owner", "governance_domain_owners"]:
        if name in df.columns:
            return F.col(name)
    return F.lit(None)


def _steward_column(df):
    for name in ["steward_upn", "data_steward", "steward_name"]:
        if name in df.columns:
            return F.col(name)
    return F.lit(None)


def _id_column(df, candidates):
    for name in candidates:
        if name in df.columns:
            return F.col(name)
    return F.lit(None)


domain_score = domains_df.select(
    F.lit("Domain").alias("object_type"),
    _id_column(domains_df, ["domain_id", "domain_code"]).alias("object_id"),
    F.col("domain_name").alias("object_name"),
    _owner_column(domains_df).alias("owner"),
    F.lit(None).alias("steward"),
    _status_column(domains_df).alias("status"),
)

product_name_col = "data_product_name" if "data_product_name" in data_products_df.columns else "product_name"
product_score = data_products_df.select(
    F.lit("DataProduct").alias("object_type"),
    _id_column(data_products_df, ["data_product_id", "product_code"]).alias("object_id"),
    F.col(product_name_col).alias("object_name"),
    _owner_column(data_products_df).alias("owner"),
    _steward_column(data_products_df).alias("steward"),
    _status_column(data_products_df).alias("status"),
)

cde_score = cde_df.select(
    F.lit("CDE").alias("object_type"),
    _id_column(cde_df, ["cde_id", "cde_code"]).alias("object_id"),
    F.col("cde_name").alias("object_name"),
    _owner_column(cde_df).alias("owner"),
    _steward_column(cde_df).alias("steward"),
    _status_column(cde_df).alias("status"),
)

scorecard_df = domain_score.unionByName(product_score).unionByName(cde_score)
scorecard_df = scorecard_df.withColumn("has_owner", F.length(F.coalesce(F.col("owner"), F.lit(""))) > 0)
scorecard_df = scorecard_df.withColumn("has_steward", (F.col("object_type") == "Domain") | (F.length(F.coalesce(F.col("steward"), F.lit(""))) > 0))
scorecard_df = scorecard_df.withColumn("is_certified_or_published", F.col("status").isin(CERTIFICATION_STATUSES))
scorecard_df = scorecard_df.withColumn(
    "stage_status",
    F.when(F.col("has_owner") & F.col("has_steward") & F.col("is_certified_or_published"), F.lit("PASS")).otherwise(F.lit("ACTION_REQUIRED")),
)

scorecard_df.write.mode("overwrite").format("delta").saveAsTable(f"{METADATA_SCHEMA}.purview_phase_08_stewardship_scorecard")
display(scorecard_df.orderBy("object_type", "object_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: DLP and governance-control readiness checks

sensitive_cdes_df = cde_df.where(F.col("sensitivity_label").isin("Confidential", "Highly Confidential"))
sensitive_cde_count = sensitive_cdes_df.count()

label_policy_count = labels_df.count() if labels_df is not None else 0
high_label_count = 0
if labels_df is not None and "label_name" in labels_df.columns:
    high_label_count = labels_df.where(F.col("label_name").isin("Confidential", "Highly Confidential")).count()

controls_rows = [
    ("sensitive_cdes_identified", sensitive_cde_count, "PASS" if sensitive_cde_count > 0 else "FAIL"),
    ("label_policy_rows_available", label_policy_count, "PASS" if label_policy_count > 0 else "ACTION_REQUIRED"),
    ("confidential_label_rules_available", high_label_count, "PASS" if high_label_count > 0 else "ACTION_REQUIRED"),
    ("dlp_policy_mode_selected", 0, "ACTION_REQUIRED"),
]
controls_df = spark.createDataFrame(controls_rows, ["check_name", "check_value", "status"])
controls_df.write.mode("overwrite").format("delta").saveAsTable(f"{METADATA_SCHEMA}.purview_phase_09_controls_validation")
display(controls_df.orderBy("check_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: AI readiness validation

certified_product_count = product_score.where(F.col("status").isin(CERTIFICATION_STATUSES)).count()
glossary_bound_count = glossary_df.where(F.length(F.coalesce(F.col("bound_assets"), F.lit(""))) > 0).count() if "bound_assets" in glossary_df.columns else 0
cde_bound_count = cde_df.where(F.length(F.coalesce(F.col("bound_columns"), F.lit(""))) > 0).count() if "bound_columns" in cde_df.columns else 0
annotation_count = semantic_annotations_df.count() if semantic_annotations_df is not None else 0

ai_rows = [
    ("certified_or_published_products", certified_product_count, "PASS" if certified_product_count >= 3 else "ACTION_REQUIRED"),
    ("glossary_terms_bound_to_assets", glossary_bound_count, "PASS" if glossary_bound_count > 0 else "ACTION_REQUIRED"),
    ("cdes_bound_to_columns", cde_bound_count, "PASS" if cde_bound_count > 0 else "ACTION_REQUIRED"),
    ("semantic_annotation_plan_available", annotation_count, "PASS" if annotation_count > 0 else "ACTION_REQUIRED"),
]
ai_df = spark.createDataFrame(ai_rows, ["check_name", "check_value", "status"])
ai_df.write.mode("overwrite").format("delta").saveAsTable(f"{METADATA_SCHEMA}.purview_phase_10_ai_readiness_validation")
display(ai_df.orderBy("check_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Write closeout manifest

mssparkutils.fs.mkdirs(OUTPUT_ROOT)

manifest = {
    "generated_on": str(date.today()),
    "semantic_model": SEMANTIC_MODEL,
    "stage_tables": {
        "phase_08_scorecard": f"{METADATA_SCHEMA}.purview_phase_08_stewardship_scorecard",
        "phase_09_controls": f"{METADATA_SCHEMA}.purview_phase_09_controls_validation",
        "phase_10_ai_readiness": f"{METADATA_SCHEMA}.purview_phase_10_ai_readiness_validation",
    },
    "manual_gate_notes": [
        "Select DLP policy mode before demo: alert-only, policy tip, or block.",
        "Only present AI answers as governed when semantic_annotation_plan rows exist for the served model objects.",
        "Review ACTION_REQUIRED rows before marking the milestone complete.",
    ],
}

mssparkutils.fs.put(f"{OUTPUT_ROOT}/stewardship_ai_closeout_manifest.json", json.dumps(manifest, indent=2), True)

summary_rows = []
for name, df in [
    ("phase_08_stewardship", scorecard_df),
    ("phase_09_controls", controls_df),
    ("phase_10_ai_readiness", ai_df),
]:
    total = df.count()
    action_required = df.where(F.col("stage_status") == "ACTION_REQUIRED").count() if "stage_status" in df.columns else df.where(F.col("status") == "ACTION_REQUIRED").count()
    summary_rows.append((name, total, action_required, "PASS" if action_required == 0 else "ACTION_REQUIRED"))

summary_df = spark.createDataFrame(summary_rows, ["stage", "rows_checked", "action_required_rows", "status"])
summary_df.write.mode("overwrite").format("delta").saveAsTable(f"{METADATA_SCHEMA}.purview_phase_08_10_closeout")

print(f"Closeout manifest written to: {OUTPUT_ROOT}")
display(summary_df.orderBy("stage"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
