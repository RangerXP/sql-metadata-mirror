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


def _write_table(df, table_name: str, mode: str = "overwrite"):
    candidates = [
        f"{METADATA_SCHEMA}.{table_name}",
        f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.{table_name}",
        table_name,
    ]
    last_error = None
    for candidate in candidates:
        try:
            writer = df.write.mode(mode).format("delta")
            if mode == "overwrite":
                writer = writer.option("overwriteSchema", "true")
            writer.saveAsTable(candidate)
            return candidate
        except Exception as ex:
            last_error = ex
    raise RuntimeError(f"Could not write table '{table_name}'. Last error: {last_error}")


domains_df, domains_source = _read_table("domains")
data_products_df, data_products_source = _read_table("data_products")
glossary_df, glossary_source = _read_table("glossary_terms")
cde_df, cde_source = _read_table("cdes")
roles_df, roles_source = _read_table("role_assignments", required=False)
labels_df, labels_source = _read_table("label_assignments", required=False)
# Try semantic_annotation_plan first, then sm_annotations as the production write target
semantic_annotations_df, semantic_annotations_source = _read_table("semantic_annotation_plan", required=False)
if semantic_annotations_df is None:
    semantic_annotations_df, semantic_annotations_source = _read_table("sm_annotations", required=False)
    if semantic_annotations_df is not None:
        print(f"[Cell 2] semantic_annotation_plan not found; using sm_annotations ({semantic_annotations_source}).")

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
    for name in ["owners", "owner_upn", "business_owner", "governance_domain_owners", "owner_role"]:
        if name in df.columns:
            return F.col(name)
    return F.lit(None)


def _steward_column(df):
    for name in ["steward_upn", "data_steward", "steward_name", "stewards", "governance_domain_stewards"]:
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
    _steward_column(domains_df).alias("steward"),
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
# Steward gate: all object types now carry a steward UPN sourced from governance_domain_stewards
# (domains), stewards (data products), and steward_upn (CDEs) added to the SQL-first schema.
scorecard_df = scorecard_df.withColumn(
    "has_steward",
    F.length(F.trim(F.coalesce(F.col("steward"), F.lit("")))) > 0
)
scorecard_df = scorecard_df.withColumn(
    "has_owner",
    F.length(F.trim(F.coalesce(F.col("owner"), F.lit("")))) > 0
)
scorecard_df = scorecard_df.withColumn("is_certified_or_published", F.col("status").isin(CERTIFICATION_STATUSES))
scorecard_df = scorecard_df.withColumn(
    "stage_status",
    F.when(F.col("has_owner") & F.col("has_steward") & F.col("is_certified_or_published"), F.lit("PASS")).otherwise(F.lit("ACTION_REQUIRED")),
)

phase_08_scorecard_table = _write_table(scorecard_df, "purview_phase_08_stewardship_scorecard")
print(f"[Cell 3] Wrote stewardship scorecard to: {phase_08_scorecard_table}")
display(scorecard_df.orderBy("object_type", "object_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: DLP and governance-control readiness checks

high_sensitivity_labels = ["Confidential", "Highly Confidential"]

if "sensitivity_label" in cde_df.columns:
    sensitive_cde_count = cde_df.where(F.col("sensitivity_label").isin(*high_sensitivity_labels)).count()
elif labels_df is not None and "label_name" in labels_df.columns:
    labeled_sensitive_df = labels_df.where(F.col("label_name").isin(*high_sensitivity_labels))
    if "cde_id" in labeled_sensitive_df.columns and "cde_id" in cde_df.columns:
        sensitive_cde_count = (
            cde_df.join(labeled_sensitive_df.select("cde_id").distinct(), on="cde_id", how="inner")
            .select("cde_id")
            .distinct()
            .count()
        )
    else:
        sensitive_cde_count = labeled_sensitive_df.count()
    print("[Cell 4] cdes.sensitivity_label not found; deriving sensitive CDE coverage from label_assignments.")
else:
    sensitive_cde_count = 0
    print("[Cell 4][WARN] No sensitivity label columns found in cdes or label_assignments.")

label_policy_count = labels_df.count() if labels_df is not None else 0
high_label_count = 0
if labels_df is not None and "label_name" in labels_df.columns:
    high_label_count = labels_df.where(F.col("label_name").isin(*high_sensitivity_labels)).count()

controls_rows = [
    ("sensitive_cdes_identified", sensitive_cde_count, "PASS" if sensitive_cde_count > 0 else "FAIL"),
    ("label_policy_rows_available", label_policy_count, "PASS" if label_policy_count > 0 else "ACTION_REQUIRED"),
    ("confidential_label_rules_available", high_label_count, "PASS" if high_label_count > 0 else "ACTION_REQUIRED"),
    ("dlp_policy_mode_selected", 0, "WARN"),  # Manual operator gate — select alert-only/policy-tip/block before demo
]
controls_df = spark.createDataFrame(controls_rows, ["check_name", "check_value", "status"])
phase_09_controls_table = _write_table(controls_df, "purview_phase_09_controls_validation")
print(f"[Cell 4] Wrote controls validation to: {phase_09_controls_table}")
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
phase_10_ai_table = _write_table(ai_df, "purview_phase_10_ai_readiness_validation")
print(f"[Cell 5] Wrote AI readiness validation to: {phase_10_ai_table}")
display(ai_df.orderBy("check_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5a: Ontology (OKR) relationship integrity validation (G11-1)
# Confirms the business-objective layer (governance_okrs/okr_key_results/
# okr_data_products, published by nb_07) resolves cleanly: every OKR has at
# least one linked data product and every key result resolves to its parent OKR.

okrs_df, okrs_source = _read_table("okrs", required=False)
okr_key_results_df, okr_key_results_source = _read_table("okr_key_results", required=False)
okr_data_products_df, okr_data_products_source = _read_table("okr_data_products", required=False)

if okrs_df is not None:
    print(f"okrs rows: {okrs_df.count()} (source={okrs_source})")
if okr_key_results_df is not None:
    print(f"okr_key_results rows: {okr_key_results_df.count()} (source={okr_key_results_source})")
if okr_data_products_df is not None:
    print(f"okr_data_products rows: {okr_data_products_df.count()} (source={okr_data_products_source})")

okr_count = okrs_df.count() if okrs_df is not None else 0
key_result_count = okr_key_results_df.count() if okr_key_results_df is not None else 0
okr_link_count = okr_data_products_df.count() if okr_data_products_df is not None else 0

okrs_with_linked_product = 0
if okrs_df is not None and okr_data_products_df is not None and okr_count > 0:
    okrs_with_linked_product = (
        okrs_df.select("okr_id")
        .join(okr_data_products_df.select("okr_id").distinct(), on="okr_id", how="inner")
        .distinct()
        .count()
    )

key_results_with_parent = 0
if okr_key_results_df is not None and okrs_df is not None and key_result_count > 0:
    key_results_with_parent = (
        okr_key_results_df.select("key_result_id", "okr_id")
        .join(okrs_df.select(F.col("okr_id").alias("okr_id_r")), okr_key_results_df.okr_id == F.col("okr_id_r"), how="inner")
        .distinct()
        .count()
    )

ontology_rows = [
    ("okrs_available", okr_count, "PASS" if okr_count > 0 else "ACTION_REQUIRED"),
    ("okr_key_results_available", key_result_count, "PASS" if key_result_count > 0 else "ACTION_REQUIRED"),
    ("okrs_with_linked_data_product", okrs_with_linked_product, "PASS" if okr_count > 0 and okrs_with_linked_product == okr_count else "ACTION_REQUIRED"),
    ("key_results_with_resolved_parent_okr", key_results_with_parent, "PASS" if key_result_count > 0 and key_results_with_parent == key_result_count else "ACTION_REQUIRED"),
]
ontology_df = spark.createDataFrame(ontology_rows, ["check_name", "check_value", "status"])
phase_11_ontology_table = _write_table(ontology_df, "purview_phase_11_ontology_validation")
print(f"[Cell 5a] Wrote ontology relationship validation to: {phase_11_ontology_table}")
display(ontology_df.orderBy("check_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Write closeout manifest

def _normalize_output_root(path: str) -> str:
    p = (path or "").strip()
    if p.startswith("/lakehouse/default/"):
        p = p[len("/lakehouse/default/") :]
    elif p.startswith("lakehouse/default/"):
        p = p[len("lakehouse/default/") :]
    if p.startswith("/"):
        p = p[1:]
    if not p:
        return "Files/purview_publish/phase_08_10_stewardship_ai"
    if p.startswith("Files/") or p.startswith("Tables/"):
        return p
    return f"Files/{p}"


output_root = _normalize_output_root(OUTPUT_ROOT)
mssparkutils.fs.mkdirs(output_root)

manifest = {
    "generated_on": str(date.today()),
    "semantic_model": SEMANTIC_MODEL,
    "stage_tables": {
        "phase_08_scorecard": phase_08_scorecard_table,
        "phase_09_controls": phase_09_controls_table,
        "phase_10_ai_readiness": phase_10_ai_table,
        "phase_11_ontology": phase_11_ontology_table,
    },
    "manual_gate_notes": [
        "Select DLP policy mode before demo: alert-only, policy tip, or block.",
        "Only present AI answers as governed when semantic_annotation_plan rows exist for the served model objects.",
        "Review ACTION_REQUIRED rows before marking the milestone complete.",
    ],
}

mssparkutils.fs.put(f"{output_root}/stewardship_ai_closeout_manifest.json", json.dumps(manifest, indent=2), True)

summary_rows = []
for name, df in [
    ("phase_08_stewardship", scorecard_df),
    ("phase_09_controls", controls_df),
    ("phase_10_ai_readiness", ai_df),
    ("phase_11_ontology", ontology_df),
]:
    total = df.count()
    if "stage_status" in df.columns:
        action_required = df.where(F.col("stage_status") == "ACTION_REQUIRED").count()
    else:
        action_required = df.where(F.col("status") == "ACTION_REQUIRED").count()
    summary_rows.append((name, total, action_required, "PASS" if action_required == 0 else "ACTION_REQUIRED"))

summary_df = spark.createDataFrame(summary_rows, ["stage", "rows_checked", "action_required_rows", "status"])
phase_08_10_closeout_table = _write_table(summary_df, "purview_phase_08_10_closeout")

print(f"Closeout manifest written to: {output_root}")
print(f"[Cell 6] Wrote closeout summary to: {phase_08_10_closeout_table}")
display(summary_df.orderBy("stage"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }




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

# Fabric Notebook: nb_12_purview_workflow_sync
# Purpose: P1 proof for one Purview-native glossary term publication loop.
#
# This notebook observes the supported Unified Catalog term resource. The public
# Unified Catalog API does not currently expose workflow request/task resources,
# so request IDs, decision actors, and decision timestamps remain NULL unless a
# future supported response provides them. A Published observation is accepted as
# approval evidence only after this run correlation was previously observed Draft.

DEMO_MODE = True
WORKFLOW_CONFIGURED = False
RUN_CORRELATION_ID = ""  # Example: GT-SLA-2026-08-11-A; local correlation, not a Purview workflow ID.

PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_CATALOG_BASE_URL = (
    "https://b7e47691-9726-4f67-a302-e567815f3522-api."
    "purview-service.microsoft.com/datagovernance/catalog"
)
PURVIEW_TERM_ID = "b3b54277-3b36-47d8-831c-a2b9a5f02634"
PURVIEW_TERM_CODE = "GT-SLA"
PURVIEW_DOMAIN_ID = "9d82a6da-eed1-4dae-a036-84c1dcc65337"

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

print(
    f"nb_12 | DEMO_MODE={DEMO_MODE} | workflow_configured={WORKFLOW_CONFIGURED} | "
    f"term={PURVIEW_TERM_CODE}/{PURVIEW_TERM_ID}"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Authentication and connection helpers

import hashlib
import json
import struct
from datetime import datetime, timezone

import pyodbc
import requests

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256


def _get_fabric_token(scopes):
    last_error = None
    for scope in scopes:
        try:
            return mssparkutils.credentials.getToken(scope)
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError("Token acquisition failed.")


def get_purview_token():
    try:
        from azure.identity import DeviceCodeCredential
    except ImportError:
        import subprocess
        import sys

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "azure-identity"],
            check=True,
        )
        from azure.identity import DeviceCodeCredential

    def show_device_code(verification_uri, user_code, expires_on):
        print(
            f"[AUTH] Open {verification_uri} in an InPrivate browser and enter "
            f"code {user_code}. Sign in as the Sean account in tenant {PURVIEW_TENANT_ID}."
        )

    credential = DeviceCodeCredential(
        client_id="04b07795-8ddb-461a-bbee-02f9e1bf7b46",
        tenant_id=PURVIEW_TENANT_ID,
        prompt_callback=show_device_code,
    )
    return credential.get_token("https://purview.azure.net/.default").token


def get_sql_connection():
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    if SQL_AUTH_MODE == "managed_identity":
        return pyodbc.connect(connection_string + "Authentication=ActiveDirectoryMsi;", autocommit=False)

    token = _get_fabric_token(["https://database.windows.net/", "https://database.windows.net"])
    encoded_token = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(encoded_token)}s", len(encoded_token), encoded_token)
    return pyodbc.connect(
        connection_string,
        attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=False,
    )


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def publication_content_hash(term):
    content = dict(term)
    content.pop("status", None)
    return sha256_text(canonical_json(content))


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read and normalize the supported Unified Catalog term resource

response = requests.get(
    f"{PURVIEW_CATALOG_BASE_URL}/terms/{PURVIEW_TERM_ID}",
    headers={"Authorization": f"Bearer {get_purview_token()}"},
    timeout=60,
)
response.raise_for_status()
raw_term = response.json()

term_snapshot = {
    "id": raw_term.get("id"),
    "name": raw_term.get("name"),
    "domain": raw_term.get("domain"),
    "status": raw_term.get("status"),
    "description": raw_term.get("description"),
    "acronyms": raw_term.get("acronyms") or [],
    "parentId": raw_term.get("parentId"),
    "resources": raw_term.get("resources") or [],
}

if term_snapshot["id"] != PURVIEW_TERM_ID:
    raise RuntimeError("Unified Catalog returned an unexpected term ID.")
if term_snapshot["domain"] != PURVIEW_DOMAIN_ID:
    raise RuntimeError("GT-SLA is no longer assigned to the expected Service Delivery domain.")
if term_snapshot["status"] not in ("Draft", "Published"):
    raise RuntimeError(f"Unsupported term lifecycle status: {term_snapshot['status']!r}")

snapshot_json = canonical_json(term_snapshot)
definition_hash = sha256_text(snapshot_json)
content_hash = publication_content_hash(term_snapshot)
observed_at = utc_now()

print(
    f"Observed {PURVIEW_TERM_CODE}: status={term_snapshot['status']} "
    f"hash={definition_hash[:12]} observed_at={observed_at.isoformat()}Z"
)
print(json.dumps(term_snapshot, indent=2, ensure_ascii=True))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Enforce the P1 correlation and Draft-before-Published guardrails

if DEMO_MODE:
    print("[DEMO_MODE] Baseline observation only; no SQL ledger writes will occur.")
elif not WORKFLOW_CONFIGURED:
    raise RuntimeError(
        "Set WORKFLOW_CONFIGURED=True only after a native Term publish workflow is scoped "
        "to the Service Delivery governance domain."
    )
elif not RUN_CORRELATION_ID.strip():
    raise RuntimeError("RUN_CORRELATION_ID is required for a live P1 workflow observation.")

request_id = "PV-GT-SLA-" + sha256_text(RUN_CORRELATION_ID.strip())[:20].upper()
source_event_id = f"{request_id}:{term_snapshot['status']}:{definition_hash}"
request_payload = canonical_json(
    {
        "localCorrelationId": RUN_CORRELATION_ID.strip(),
        "definitionHash": definition_hash,
        "publicationContentHash": content_hash,
        "term": term_snapshot,
        "workflowEvidenceLimitations": {
            "authorityRequestId": "not exposed by the supported Unified Catalog API",
            "decisionActor": "not exposed by the supported Unified Catalog API",
            "decisionTimestamp": "not exposed by the supported Unified Catalog API",
        },
    }
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Persist one idempotent Draft or Published observation

if not DEMO_MODE:
    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT current_status, proposed_payload
            FROM dbo.governance_requests WITH (UPDLOCK, HOLDLOCK)
            WHERE request_id = ?
            """,
            request_id,
        )
        existing_row = cursor.fetchone()
        existing_status = existing_row[0] if existing_row else None
        existing_payload = json.loads(existing_row[1]) if existing_row and existing_row[1] else None

        if term_snapshot["status"] == "Published" and existing_status not in ("Draft", "Approved"):
            raise RuntimeError(
                "Refusing to record Published as approval evidence because this correlation "
                "has no prior Draft observation. Unpublish/edit GT-SLA, run this notebook once "
                "while Draft, submit it to the native workflow, then rerun after approval."
            )

        if existing_payload:
            expected_hash = existing_payload.get("publicationContentHash")
            if not expected_hash:
                expected_hash = publication_content_hash(existing_payload["term"])
        else:
            expected_hash = content_hash
        normalized_status = "Approved" if term_snapshot["status"] == "Published" else "Draft"

        if existing_row:
            cursor.execute(
                """
                UPDATE dbo.governance_requests
                SET current_status = ?, source_snapshot = ?, last_observed_at = ?, failure_reason = NULL
                WHERE request_id = ?
                """,
                normalized_status,
                snapshot_json,
                observed_at,
                request_id,
            )
        else:
            cursor.execute(
                """
                INSERT dbo.governance_requests (
                    request_id, request_type, authority, authority_request_id,
                    target_system, target_object_type, target_object_id, target_object_label,
                    current_status, proposed_payload, source_snapshot, last_observed_at
                ) VALUES (?, 'GLOSSARY_TERM_PUBLICATION', 'Purview', NULL,
                          'Purview', 'GlossaryTerm', ?, ?, ?, ?, ?, ?)
                """,
                request_id,
                PURVIEW_TERM_ID,
                term_snapshot["name"],
                normalized_status,
                request_payload,
                snapshot_json,
                observed_at,
            )

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM dbo.governance_events
                WHERE source_system = 'Purview' AND source_event_id = ?
            )
            INSERT dbo.governance_events (
                request_id, event_type, event_status, source_system, source_event_id,
                actor_id, occurred_at, observed_at, payload, payload_hash
            ) VALUES (?, ?, ?, 'Purview', ?, NULL, ?, ?, ?, ?)
            """,
            source_event_id,
            request_id,
            "TermPublishedObserved" if normalized_status == "Approved" else "TermDraftObserved",
            normalized_status,
            source_event_id,
            observed_at,
            observed_at,
            snapshot_json,
            definition_hash,
        )

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM dbo.governed_object_versions
                WHERE source_system = 'Purview' AND object_type = 'GlossaryTerm'
                  AND object_id = ? AND source_version_id = ?
            )
            INSERT dbo.governed_object_versions (
                request_id, source_system, object_type, object_id, source_version_id,
                lifecycle_status, definition_hash, object_payload, effective_at, observed_at
            ) VALUES (?, 'Purview', 'GlossaryTerm', ?, ?, ?, ?, ?, ?, ?)
            """,
            PURVIEW_TERM_ID,
            definition_hash,
            request_id,
            PURVIEW_TERM_ID,
            definition_hash,
            term_snapshot["status"],
            definition_hash,
            snapshot_json,
            observed_at,
            observed_at,
        )

        if normalized_status == "Approved":
            validation_status = "Passed" if content_hash == expected_hash else "Failed"
            evidence = canonical_json(
                {
                    "term": term_snapshot,
                    "expectedHash": expected_hash,
                    "observedHash": content_hash,
                    "observedAt": observed_at.isoformat() + "Z",
                    "decisionActor": None,
                    "decisionTimestamp": None,
                }
            )
            cursor.execute(
                """
                MERGE dbo.governance_target_receipts WITH (HOLDLOCK) AS target
                USING (SELECT ? AS request_id, 'Purview' AS target_system,
                              'GlossaryTerm' AS target_object_type, ? AS target_object_id,
                              'PublicationReadback' AS receipt_type) AS source
                ON target.request_id = source.request_id
                   AND target.target_system = source.target_system
                   AND target.target_object_type = source.target_object_type
                   AND target.target_object_id = source.target_object_id
                   AND target.receipt_type = source.receipt_type
                WHEN MATCHED THEN UPDATE SET
                    expected_hash = ?, observed_hash = ?, validation_status = ?,
                    observed_at = ?, evidence_payload = ?
                WHEN NOT MATCHED THEN INSERT (
                    request_id, target_system, target_object_type, target_object_id,
                    receipt_type, expected_hash, observed_hash, validation_status,
                    observed_at, evidence_payload
                ) VALUES (?, 'Purview', 'GlossaryTerm', ?, 'PublicationReadback',
                          ?, ?, ?, ?, ?);
                """,
                request_id,
                PURVIEW_TERM_ID,
                expected_hash,
                content_hash,
                validation_status,
                observed_at,
                evidence,
                request_id,
                PURVIEW_TERM_ID,
                expected_hash,
                content_hash,
                validation_status,
                observed_at,
                evidence,
            )
            if validation_status != "Passed":
                raise RuntimeError("Published term read-back did not match the Draft definition hash.")

        connection.commit()
        print(f"[APPLIED] request={request_id} status={normalized_status} event={source_event_id}")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Verify the durable P1 evidence contract

if not DEMO_MODE:
    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT current_status, authority_request_id, decided_by, decided_at
            FROM dbo.governance_requests
            WHERE request_id = ?
            """,
            request_id,
        )
        request_evidence = cursor.fetchone()

        cursor.execute(
            """
            SELECT event_type, COUNT(*)
            FROM dbo.governance_events
            WHERE request_id = ?
            GROUP BY event_type
            """,
            request_id,
        )
        event_counts = dict(cursor.fetchall())

        cursor.execute(
            """
            SELECT lifecycle_status, COUNT(*)
            FROM dbo.governed_object_versions
            WHERE request_id = ?
            GROUP BY lifecycle_status
            """,
            request_id,
        )
        version_counts = dict(cursor.fetchall())

        cursor.execute(
            """
            SELECT validation_status, expected_hash, observed_hash
            FROM dbo.governance_target_receipts
            WHERE request_id = ? AND target_system = 'Purview'
              AND target_object_type = 'GlossaryTerm' AND target_object_id = ?
              AND receipt_type = 'PublicationReadback'
            """,
            request_id,
            PURVIEW_TERM_ID,
        )
        publication_receipt = cursor.fetchone()

        if not request_evidence or request_evidence[0] != "Approved":
            raise RuntimeError("P1 verification failed: request is not Approved.")
        if any(request_evidence[index] is not None for index in range(1, 4)):
            raise RuntimeError("P1 verification failed: unsupported workflow fields must remain NULL.")
        if event_counts.get("TermDraftObserved") != 1 or event_counts.get("TermPublishedObserved") != 1:
            raise RuntimeError(f"P1 verification failed: unexpected event counts {event_counts!r}.")
        if version_counts.get("Draft") != 1 or version_counts.get("Published") != 1:
            raise RuntimeError(f"P1 verification failed: unexpected version counts {version_counts!r}.")
        if not publication_receipt or publication_receipt[0] != "Passed":
            raise RuntimeError("P1 verification failed: PublicationReadback did not pass.")
        if publication_receipt[1] != publication_receipt[2]:
            raise RuntimeError("P1 verification failed: publication receipt hashes differ.")

        print(
            f"[VERIFIED] request={request_id} status=Approved "
            f"events={event_counts} versions={version_counts} receipt=Passed"
        )
    finally:
        cursor.close()
        connection.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Completion boundary

print(
    "P1 Purview evidence collection finished. This notebook does not mark the request "
    "Completed; semantic-model reconciliation and its read-back receipt are a separate step."
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

