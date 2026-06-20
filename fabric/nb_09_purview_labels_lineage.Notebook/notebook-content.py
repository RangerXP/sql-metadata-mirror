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

# Cell 1: Imports and Config
# Purpose: Initialize Spark session, import required libraries, and set Purview/Fabric configuration.
# Outputs: Purview endpoint URL, deployment mode flags, output paths, and Enercare workspace identifiers.

import hashlib
import json
import os
import base64
import shutil
import subprocess
import time
import uuid
from urllib.parse import quote
import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
PURVIEW_ACCOUNT_NAME = "Purview-West3"
PURVIEW_BASE_URL = f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"
APPLY_CHANGES = True
SQL_MIRROR_ONLY_DEPLOYMENT = True
PURVIEW_PUBLISH_OVERRIDE = True
OUTPUT_ROOT = "/lakehouse/default/Files/purview_publish/phase_06_07_labels_lineage"
PURVIEW_HTTP_TIMEOUT_SECONDS = 60
MAX_ENTITY_RESOLUTION_SECONDS = 120
MAX_EDGES_TO_RESOLVE = 50
FAIL_ON_TOKEN_ACQUISITION_ERROR = False
TOKEN_RESOURCE_CANDIDATES = ["https://purview.azure.net"]
TOKEN_OUTER_RETRY_ATTEMPTS = 1
DISABLE_LIVE_PURVIEW_PUBLISH = False
TOKEN_ACQUISITION_MODE = "manual"  # auto | manual | azcli | tokenlibrary
PURGE_BEFORE_REWRITE = True
MANUAL_PURVIEW_BEARER_TOKEN = os.getenv("MANUAL_PURVIEW_BEARER_TOKEN", "").strip()
AZ_CLI_TIMEOUT_SECONDS = 15

WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
SQL_SOURCE_NAME = "ENERCARE-SQL-SOURCE"
FABRIC_SOURCE_NAME = "ENERCARE-FABRIC-SOURCE"
SEMANTIC_MODEL_NAME = "BrookfieldEnercare"
SEMANTIC_MODEL_LOGICAL_ID = "d19d7f14-ae22-9fde-462b-dafb983dfb0a"
SQL_SERVER_FQDN = "sqlserver-sk2wus3.database.windows.net"

print(f"Purview account: {PURVIEW_ACCOUNT_NAME}")
print(f"Apply changes: {APPLY_CHANGES}")
print(f"Output root: {OUTPUT_ROOT}")

# Cell 1 complete: Configuration initialized


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 1a: Optional Manual Token Helper (Runtime Only)
# Purpose: Keep a paste-ready helper block in notebook flow without storing a token in git.
# Usage: Uncomment these lines, paste a fresh token, run Cell 1a, then run Cell 6.

# import os
# os.environ["MANUAL_PURVIEW_BEARER_TOKEN"] = "PASTE_FRESH_PURVIEW_TOKEN_HERE"
# MANUAL_PURVIEW_BEARER_TOKEN = os.environ.get("MANUAL_PURVIEW_BEARER_TOKEN", "").strip()

# Cell 1a complete: Manual token helper available


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read Metadata Tables
# Purpose: Load CDEs, label assignments, and data products from lh_metadata lakehouse.
# Outputs: DataFrames for cdes, label_assignments (optional), and data_products with row counts.

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


cde_df, cde_source = _read_table("cdes")
labels_df, labels_source = _read_table("label_assignments", required=False)
glossary_df, glossary_source = _read_table("glossary_terms", required=False)
data_products_df, data_products_source = _read_table("data_products")

if labels_df is None:
    print("[WARN] metadata.label_assignments not found; label rules will be inferred from CDE values when possible.")

print(f"cdes rows: {cde_df.count()} (source={cde_source})")
if labels_df is not None:
    print(f"label_assignments rows: {labels_df.count()} (source={labels_source})")
if glossary_df is not None:
    print(f"glossary_terms rows: {glossary_df.count()} (source={glossary_source})")
print(f"data_products rows: {data_products_df.count()} (source={data_products_source})")

# Cell 2 complete: Metadata tables loaded


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build Sensitivity Label and CDE Classification Manifests
# Purpose: Derive sensitivity labels separately from CDE classifications.
# Outputs: typedef_payload (CDE classification definitions), sensitivity_label_manifest, cde_classification_manifest.


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _guid():
    return f"-{uuid.uuid4().int % 1000000000}"


def _split_tokens(raw_value):
    text = _safe_text(raw_value)
    if not text:
        return []
    tokens = []
    for piece in text.replace("\n", ";").replace("|", ";").split(";"):
        item = piece.strip()
        if item:
            tokens.append(item)
    return tokens


CDE_CLASSIFICATION_NAME = "EnercareCDE"
NORTHSTAR_CLASSIFICATIONS = {
    "EnercareBilling": "Billing",
    "EnercareExecutive": "Executive",
    "EnercareCustomer": "Customer",
    "EnercareServiceEncounter": "ServiceEncounter",
    "EnercareKPIAnalyst": "KPIAnalyst",
}

DISALLOWED_CLASSIFICATION_TYPEDEFS = {
    "EnercareSensitivityConfidential",
    "EnercareSensitivityExecutiveKpi",
    "EnercareSensitivityGeneral",
    "EnercareSensitivityGovernanceAdmin",
    "EnercareSensitivityHighlyConfidential",
    "EnercareSensitivityInternal",
    "EnercareSensitivityOperationsSensitive",
    "EnercareSensitivityPciRestricted",
    "EnercareSensitivityPrivacyRestricted",
}

SENSITIVITY_LABEL_CANONICAL = {
    "general": "Internal",
    "internal": "Internal",
    "executive kpi": "Internal",
    "confidential": "Confidential",
    "operations sensitive": "Confidential",
    "governance admin": "Confidential",
    "highly confidential": "Highly Confidential",
    "pci restricted": "Highly Confidential",
    "privacy restricted": "Highly Confidential",
}

CANONICAL_LABEL_POLICY = {
    "Internal": "Internal business use; broad collaboration allowed.",
    "Confidential": "Restricted to approved internal teams; governance controls required.",
    "Highly Confidential": "Strictly restricted regulated data; explicit approval and enhanced controls required.",
}


def _normalize_sensitivity_label(raw_label: str) -> str:
    text = _safe_text(raw_label)
    if not text:
        return ""
    return SENSITIVITY_LABEL_CANONICAL.get(text.lower(), text)


def _classification_def(name: str, description: str):
    return {
        "category": "CLASSIFICATION",
        "name": name,
        "description": description,
        "attributeDefs": [
            {"name": "cde_id", "typeName": "string", "isOptional": True},
            {"name": "cde_name", "typeName": "string", "isOptional": True},
            {"name": "assignment_source", "typeName": "string", "isOptional": True},
            {"name": "rule", "typeName": "string", "isOptional": True},
        ],
    }


def _derive_northstar_classes(asset_ref: str, cde_id: str, cde_name: str, parent_term: str, owner_role: str):
    text = " ".join(
        [
            _safe_text(asset_ref).lower(),
            _safe_text(cde_id).lower(),
            _safe_text(cde_name).lower(),
            _safe_text(parent_term).lower(),
            _safe_text(owner_role).lower(),
        ]
    )

    classes = set()
    if any(x in text for x in ["billing", "contract", "pan", "bank", "payment", "finance"]):
        classes.add("EnercareBilling")
    if any(x in text for x in ["customer", "consent", "complaint", "sin", "dob", "pii"]):
        classes.add("EnercareCustomer")
    if any(x in text for x in ["service_request", "service_requests", "service_account", "service_accounts", "service_zone", "service_zones", "svc", "encounter", "interaction", "work order"]):
        classes.add("EnercareServiceEncounter")
    if any(x in text for x in ["_measures", "/measures/", "kpi", "fcr", "csat", "nps", "aht", "sla", "renewal"]):
        classes.add("EnercareKPIAnalyst")
    if any(x in text for x in ["leadership", "executive", "report", "semanticmodel", "brookfieldenercare.report"]):
        classes.add("EnercareExecutive")

    return sorted(classes)

labels = set()
label_policy_by_name = {}
cde_has_sensitivity_label = "sensitivity_label" in cde_df.columns
if cde_has_sensitivity_label:
    for row in cde_df.select("sensitivity_label").distinct().collect():
        label = _normalize_sensitivity_label(getattr(row, "sensitivity_label", None))
        if label:
            labels.add(label)
if labels_df is not None and "label_name" in labels_df.columns:
    for row in labels_df.collect():
        raw_label = _safe_text(getattr(row, "label_name", None))
        label = _normalize_sensitivity_label(raw_label)
        if label:
            labels.add(label)
            source_policy = _safe_text(getattr(row, "protection_policy", None))
            label_policy_by_name[label.lower()] = {
                "sensitivity_tier": _normalize_sensitivity_label(getattr(row, "sensitivity_tier", None)) or label,
                "protection_policy": source_policy or CANONICAL_LABEL_POLICY.get(label, ""),
            }

if not labels:
    labels.add("Internal")

cde_rows = cde_df.collect()

glossary_term_code_to_name = {}
if glossary_df is not None:
    glossary_cols = {c.lower(): c for c in glossary_df.columns}
    code_col = glossary_cols.get("term_code")
    name_col = glossary_cols.get("term_name") or glossary_cols.get("name")
    if code_col and name_col:
        for row in glossary_df.collect():
            code = _safe_text(getattr(row, code_col, None)).upper()
            name = _safe_text(getattr(row, name_col, None))
            if code and name:
                glossary_term_code_to_name[code] = name

classification_defs = [_classification_def(CDE_CLASSIFICATION_NAME, "CDE")]
for class_name, class_desc in NORTHSTAR_CLASSIFICATIONS.items():
    classification_defs.append(_classification_def(class_name, class_desc))

classification_defs = [
    d for d in classification_defs if _safe_text(d.get("name", "")) not in DISALLOWED_CLASSIFICATION_TYPEDEFS
]

typedef_payload = {"classificationDefs": classification_defs}

sensitivity_label_manifest = []
cde_classification_manifest = []
glossary_term_manifest = []
asset_description_manifest = []
for row in cde_rows:
    label = _normalize_sensitivity_label(getattr(row, "sensitivity_label", None))
    cde_id = _safe_text(getattr(row, "cde_id", None) or getattr(row, "cde_code", None) or getattr(row, "cde_name", None))
    cde_name = _safe_text(getattr(row, "cde_name", None) or cde_id)
    parent_term = _safe_text(getattr(row, "parent_glossary_term", None))
    owner_role = _safe_text(getattr(row, "owner_role", None))
    cde_definition = _safe_text(getattr(row, "business_definition", None))

    policy = label_policy_by_name.get(label.lower(), {}) if label else {}
    sensitivity_tier = _safe_text(policy.get("sensitivity_tier", "")) or label
    protection_policy = _safe_text(policy.get("protection_policy", "")) or CANONICAL_LABEL_POLICY.get(label, "")

    for token in _split_tokens(getattr(row, "bound_columns", None)):
        if cde_has_sensitivity_label and label:
            sensitivity_label_manifest.append(
                {
                    "asset_ref": token,
                    "label_name": label,
                    "sensitivity_tier": sensitivity_tier,
                    "protection_policy": protection_policy,
                    "assignment_source": "CDE",
                    "rule": cde_id,
                }
            )

        glossary_term = parent_term or cde_name
        glossary_term = glossary_term_code_to_name.get(_safe_text(glossary_term).upper(), glossary_term)
        if _safe_text(glossary_term):
            glossary_term_manifest.append(
                {
                    "asset_ref": token,
                    "term_name": _safe_text(glossary_term),
                    "assignment_source": "CDE",
                    "rule": cde_id,
                }
            )

        if cde_definition:
            asset_description_manifest.append(
                {
                    "asset_ref": token,
                    "description": cde_definition,
                    "assignment_source": "CDE",
                    "rule": cde_id,
                }
            )

        cde_classification_manifest.append(
            {
                "asset_ref": token,
                "classification": CDE_CLASSIFICATION_NAME,
                "label_name": "",
                "sensitivity_tier": "",
                "protection_policy": "",
                "assignment_source": "CDE",
                "rule": cde_id,
                "cde_id": cde_id,
                "cde_name": cde_name,
            }
        )

        for northstar_class in _derive_northstar_classes(token, cde_id, cde_name, parent_term, owner_role):
            cde_classification_manifest.append(
                {
                    "asset_ref": token,
                    "classification": northstar_class,
                    "label_name": "",
                    "sensitivity_tier": "",
                    "protection_policy": "",
                    "assignment_source": "NorthStar",
                    "rule": f"{cde_id}:{northstar_class}",
                    "cde_id": cde_id,
                    "cde_name": cde_name,
                }
            )

if not cde_has_sensitivity_label:
    print("[Cell 3] cdes.sensitivity_label not found; using label_assignments as sensitivity source.")

if labels_df is not None:
    for row in labels_df.collect():
        raw_label = _safe_text(getattr(row, "label_name", None))
        label = _normalize_sensitivity_label(raw_label)
        assets = _safe_text(getattr(row, "applies_to_asset_ids", None) or getattr(row, "enforcement_target", None))
        rule = _safe_text(getattr(row, "assignment_rule", None) or getattr(row, "label_id", None) or raw_label)
        sensitivity_tier = _normalize_sensitivity_label(getattr(row, "sensitivity_tier", None)) or label
        protection_policy = _safe_text(getattr(row, "protection_policy", None)) or CANONICAL_LABEL_POLICY.get(label, "")
        for token in _split_tokens(assets):
            sensitivity_label_manifest.append(
                {
                    "asset_ref": token,
                    "label_name": label,
                    "sensitivity_tier": sensitivity_tier,
                    "protection_policy": protection_policy,
                    "assignment_source": "LabelPolicy",
                    "rule": rule,
                }
            )

            for northstar_class in _derive_northstar_classes(token, rule, label, "", ""):
                cde_classification_manifest.append(
                    {
                        "asset_ref": token,
                        "classification": northstar_class,
                        "label_name": "",
                        "sensitivity_tier": "",
                        "protection_policy": "",
                        "assignment_source": "LabelPolicy-NorthStar",
                        "rule": rule,
                        "cde_id": "",
                        "cde_name": label,
                    }
                )

if not glossary_term_manifest and glossary_df is not None:
    glossary_term_name_col = None
    for candidate in ("term_name", "name"):
        if candidate in glossary_df.columns:
            glossary_term_name_col = candidate
            break

    glossary_bound_assets_col = None
    for candidate in ("bound_assets", "applies_to_asset_ids"):
        if candidate in glossary_df.columns:
            glossary_bound_assets_col = candidate
            break

    if glossary_term_name_col and glossary_bound_assets_col:
        for row in glossary_df.collect():
            term_name = _safe_text(getattr(row, glossary_term_name_col, None))
            rule = _safe_text(getattr(row, "term_code", None) or term_name)
            definition = _safe_text(getattr(row, "definition", None))
            for token in _split_tokens(getattr(row, glossary_bound_assets_col, None)):
                if term_name and token:
                    glossary_term_manifest.append(
                        {
                            "asset_ref": token,
                            "term_name": term_name,
                            "assignment_source": "GlossaryTable",
                            "rule": rule,
                        }
                    )
                    if definition:
                        asset_description_manifest.append(
                            {
                                "asset_ref": token,
                                "description": definition,
                                "assignment_source": "GlossaryTable",
                                "rule": rule,
                            }
                        )

        if glossary_term_manifest:
            print(
                f"[Cell 3] Glossary fallback populated {len(glossary_term_manifest)} rows "
                "from glossary_terms.bound_assets."
            )

classification_manifest = cde_classification_manifest
classification_manifest = [
    row
    for row in classification_manifest
    if _safe_text(row.get("classification", "")) not in DISALLOWED_CLASSIFICATION_TYPEDEFS
]

if not glossary_term_manifest:
    print("[Cell 3][WARN] No glossary term rows prepared from CDE metadata.")

print(f"Classification defs prepared: {len(classification_defs)}")
print(f"Sensitivity label rows prepared: {len(sensitivity_label_manifest)}")
print(f"CDE manifest rows prepared: {len(cde_classification_manifest)}")
print(f"Classification manifest rows prepared: {len(classification_manifest)}")
print(f"Glossary term rows prepared: {len(glossary_term_manifest)}")
print(f"Asset description rows prepared: {len(asset_description_manifest)}")
print("Classification names prepared:")
for item in sorted({d.get("name", "") for d in classification_defs if d.get("name", "")}):
    print(f" - {item}")

# Cell 3 complete: Sensitivity labels and CDE classification manifests built


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Build SQL to Fabric Lineage Edge Manifest
# Purpose: Extract lineage relationships from data_products (SQL source tables → Fabric target assets).
# Outputs: lineage_edges list with process qualified names, source/target references, and data product context.


def _table_ref_from_sql_asset(asset_ref: str):
    parts = asset_ref.split(".")
    if len(parts) >= 2 and parts[0].lower() == "dbo":
        return f"mssql://sqldemo/dbo/{parts[1]}"
    return None


def _fabric_ref_from_asset(asset_ref: str):
    if asset_ref.startswith("lh_enercare_demo."):
        _, table_name = asset_ref.split(".", 1)
        return f"fabric://{WORKSPACE_ID}/lakehouses/lh_enercare_demo/tables/{table_name}"
    if asset_ref.startswith(f"{SEMANTIC_MODEL_NAME}/"):
        return f"fabric://{WORKSPACE_ID}/semanticModels/{SEMANTIC_MODEL_NAME}/{asset_ref.split('/', 1)[1]}"
    return None


def _split_sql_and_fabric_assets(tokens):
    sql_assets = []
    fabric_assets = []
    for token in tokens:
        t = _safe_text(token)
        if not t:
            continue
        if t.lower().startswith("dbo."):
            sql_assets.append(t)
            continue
        if t.startswith("lh_enercare_demo.") or t.startswith(f"{SEMANTIC_MODEL_NAME}/"):
            fabric_assets.append(t)
            continue
    return sql_assets, fabric_assets


lineage_edges = []
for row in data_products_df.collect():
    product_name = _safe_text(getattr(row, "data_product_name", None) or getattr(row, "product_name", None))

    attached_tokens = _split_tokens(getattr(row, "attached_assets", None))
    explicit_sql_tokens = _split_tokens(getattr(row, "sql_assets", None))
    explicit_fabric_tokens = _split_tokens(getattr(row, "fabric_assets", None) or getattr(row, "semantic_model_assets", None))

    inferred_sql_assets, inferred_fabric_assets = _split_sql_and_fabric_assets(attached_tokens)

    sql_assets = explicit_sql_tokens or inferred_sql_assets
    fabric_assets = explicit_fabric_tokens or inferred_fabric_assets

    source_refs = [ref for ref in (_table_ref_from_sql_asset(asset) for asset in sql_assets) if ref]
    target_refs = [ref for ref in (_fabric_ref_from_asset(asset) for asset in fabric_assets) if ref]

    for source_ref in source_refs:
        for target_ref in target_refs:
            edge_hash = hashlib.sha1(f"{source_ref}|{target_ref}".encode("utf-8")).hexdigest()[:12]
            lineage_edges.append(
                {
                    "process_qualified_name": f"enercare://lineage/{product_name.replace(' ', '-').lower()}/{edge_hash}",
                    "process_name": f"{product_name} SQL to Fabric lineage",
                    "source": source_ref,
                    "target": target_ref,
                    "data_product": product_name,
                }
            )

print(f"Lineage edge rows prepared: {len(lineage_edges)}")

# Cell 4 complete: Lineage edge manifest prepared


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Write Payloads and Validation Summary
# Purpose: Export sensitivity labels, CDE classifications, and lineage payloads to Azure Data Lake.
#          Create validation table tracking readiness of all artifacts (G9 checklist).
# Outputs: JSON files in OUTPUT_ROOT; metadata.purview_phase_06_07_validation table.

def _normalize_output_root(path: str) -> str:
    raw = (path or "").strip()
    if not raw:
        return "Files/purview_publish/phase_06_07_labels_lineage"

    cleaned = raw.replace("\\", "/").strip("/")
    lowered = cleaned.lower()

    if lowered.startswith("files/") or lowered.startswith("tables/"):
        return cleaned

    if lowered.startswith("lakehouse/default/files/"):
        suffix = cleaned[len("lakehouse/default/files/") :]
        return f"Files/{suffix}" if suffix else "Files"

    if lowered.startswith("lakehouse/default/tables/"):
        suffix = cleaned[len("lakehouse/default/tables/") :]
        return f"Tables/{suffix}" if suffix else "Tables"

    return f"Files/{cleaned}"


output_root = _normalize_output_root(OUTPUT_ROOT)

mssparkutils.fs.mkdirs(output_root)
mssparkutils.fs.put(f"{output_root}/classification_typedefs.json", json.dumps(typedef_payload, indent=2), True)
mssparkutils.fs.put(f"{output_root}/sensitivity_label_manifest.json", json.dumps(sensitivity_label_manifest, indent=2), True)
mssparkutils.fs.put(f"{output_root}/classification_manifest.json", json.dumps(classification_manifest, indent=2), True)
mssparkutils.fs.put(f"{output_root}/glossary_term_manifest.json", json.dumps(glossary_term_manifest, indent=2), True)
mssparkutils.fs.put(f"{output_root}/lineage_edges.json", json.dumps(lineage_edges, indent=2), True)

legacy_typedef_count = sum(
    1
    for item in classification_defs
    if _safe_text(item.get("name", "")) in DISALLOWED_CLASSIFICATION_TYPEDEFS
)
legacy_manifest_count = sum(
    1
    for item in classification_manifest
    if _safe_text(item.get("classification", "")) in DISALLOWED_CLASSIFICATION_TYPEDEFS
)
service_encounter_present = int(
    any(_safe_text(item.get("name", "")) == "EnercareServiceEncounter" for item in classification_defs)
)

validation_rows = [
    ("classification_defs_prepared", len(classification_defs), "PASS" if classification_defs else "FAIL"),
    ("sensitivity_label_rows", len(sensitivity_label_manifest), "PASS" if sensitivity_label_manifest else "WARN"),
    ("classification_manifest_rows", len(classification_manifest), "PASS" if classification_manifest else "FAIL"),
    ("glossary_term_rows", len(glossary_term_manifest), "PASS" if glossary_term_manifest else "WARN"),
    ("lineage_edges_prepared", len(lineage_edges), "PASS" if lineage_edges else "WARN"),
    ("legacy_sensitivity_typedefs_in_payload", legacy_typedef_count, "PASS" if legacy_typedef_count == 0 else "FAIL"),
    ("legacy_sensitivity_classifications_in_manifest", legacy_manifest_count, "PASS" if legacy_manifest_count == 0 else "FAIL"),
    ("service_encounter_typedef_present", service_encounter_present, "PASS" if service_encounter_present == 1 else "FAIL"),
    ("sql_source_name_configured", int(bool(SQL_SOURCE_NAME)), "PASS"),
    ("fabric_source_name_configured", int(bool(FABRIC_SOURCE_NAME)), "PASS"),
]
validation_df = spark.createDataFrame(validation_rows, ["check_name", "check_value", "status"])

validation_table_candidates = [
    f"{METADATA_SCHEMA}.purview_phase_06_07_validation",
    "purview_phase_06_07_validation",
]
validation_table_name = None
last_validation_error = None
for candidate in validation_table_candidates:
    try:
        validation_df.write.mode("overwrite").format("delta").saveAsTable(candidate)
        validation_table_name = candidate
        break
    except Exception as ex:
        last_validation_error = ex

if validation_table_name is None:
    raise RuntimeError(
        f"Unable to write validation table. Tried {validation_table_candidates}. Last error: {last_validation_error}"
    )

print(f"Payloads written to: {output_root}")
print(f"Validation table written to: {validation_table_name}")
display(validation_df.orderBy("check_name"))

# Cell 5 complete: Payloads written and validation table created


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Optional Live Publish to Purview Atlas
# Purpose: Publish classification typedefs and lineage process entities to Purview via Atlas API.
#          Resolve scanned asset GUIDs by qualifiedName and register lineage input/output relationships.
# Guard: SQL_MIRROR_ONLY_DEPLOYMENT + PURVIEW_PUBLISH_OVERRIDE control live execution.
# Outputs: Classification typedefs registered; lineage processes (with input/output edges) published.
#          Unresolved edges reported for debugging qualifiedName pattern mismatches.


def _headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request(method: str, path: str, token: str, body: dict = None, params: dict = None):
    url = f"{PURVIEW_BASE_URL}{path}"
    response = requests.request(
        method,
        url,
        headers=_headers(token),
        json=body,
        params=params,
        timeout=PURVIEW_HTTP_TIMEOUT_SECONDS,
    )
    return response.status_code, response.text


def _post_json(path: str, token: str, body: dict):
    return _request("POST", path, token, body=body)


def _path_quote(value: str) -> str:
    return quote(_safe_text(value), safe="")


def _is_invalid_classification_target(entity) -> bool:
    entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
    return (
        "glossaryterm" in entity_type
        or "atlasglossaryterm" in entity_type
        or "atlasglossary" in entity_type
        or "classification" in entity_type
    )


def _classification_query_candidates(asset_ref: str):
    raw = _safe_text(asset_ref)
    candidates = []
    if not raw:
        return candidates

    candidates.append(raw)

    lower = raw.lower()
    if lower.startswith("dbo."):
        parts = raw.split(".")
        if len(parts) >= 3:
            table = parts[1]
            column = ".".join(parts[2:])
            candidates.extend([f"{table}.{column}", f"{table} {column}", table])
        elif len(parts) == 2:
            table = parts[1]
            candidates.extend([table, f"dbo {table}"])
    elif "/" in raw:
        pieces = [p.strip() for p in raw.split("/") if p.strip()]
        if pieces:
            candidates.append(pieces[-1])
        if len(pieces) >= 2:
            candidates.append(f"{pieces[-2]} {pieces[-1]}")

    if "." in raw:
        dot_parts = [p.strip() for p in raw.split(".") if p.strip()]
        if dot_parts:
            candidates.append(dot_parts[-1])
        if len(dot_parts) >= 2:
            candidates.append(" ".join(dot_parts[-2:]))

    if "semanticmodel" in lower:
        candidates.extend(["semantic model", SEMANTIC_MODEL_NAME])
    if "report" in lower:
        candidates.extend(["report", "brookfieldenercare report", SEMANTIC_MODEL_NAME])

    seen = set()
    unique = []
    for candidate in candidates:
        text = _safe_text(candidate)
        if text and text not in seen:
            unique.append(text)
            seen.add(text)
    return unique


def _asset_ref_to_column_qualified_name(asset_ref: str):
    raw = _safe_text(asset_ref)
    if not raw:
        return ""

    lower = raw.lower()
    if lower.startswith("mssql://") and "#" in raw:
        return raw

    if lower.startswith("dbo."):
        parts = raw.split(".")
        if len(parts) >= 3:
            table_name = _safe_text(parts[1])
            column_name = _safe_text(".".join(parts[2:]))
            if table_name and column_name:
                return f"mssql://{SQL_SERVER_FQDN}/sqldemo/dbo/{table_name}#{column_name}"

    return ""


def _asset_ref_to_table_qualified_name(asset_ref: str):
    raw = _safe_text(asset_ref)
    if not raw:
        return ""

    lower = raw.lower()
    if lower.startswith("mssql://") and "#" not in raw:
        return raw

    if lower.startswith("dbo."):
        parts = raw.split(".")
        if len(parts) >= 2:
            table_name = _safe_text(parts[1])
            if table_name:
                return f"mssql://{SQL_SERVER_FQDN}/sqldemo/dbo/{table_name}"

    return ""


def _resolve_asset_for_classification(token: str, asset_ref: str):
    explicit_column_qn = _asset_ref_to_column_qualified_name(asset_ref)
    if explicit_column_qn:
        exact = _find_entity_by_qualified_name(token, explicit_column_qn)
        if exact:
            return {
                "guid": _safe_text(exact.get("guid", "")),
                "entityType": _safe_text(exact.get("typeName", "")).lower(),
                "qualifiedName": _safe_text(exact.get("qualifiedName", "")),
            }

    explicit_table_qn = _asset_ref_to_table_qualified_name(asset_ref)
    if explicit_table_qn:
        exact = _find_entity_by_qualified_name(token, explicit_table_qn)
        if exact:
            return {
                "guid": _safe_text(exact.get("guid", "")),
                "entityType": _safe_text(exact.get("typeName", "")).lower(),
                "qualifiedName": _safe_text(exact.get("qualifiedName", "")),
            }

    best = None
    best_score = 0

    for keywords in _classification_query_candidates(asset_ref):
        status, body = _request(
            "POST",
            "/datamap/api/search/query",
            token,
            body={"keywords": keywords, "limit": 50},
            params={"api-version": "2023-09-01"},
        )
        if status != 200:
            continue

        try:
            payload = json.loads(body)
        except Exception:
            continue

        for entity in payload.get("value") or []:
            if _is_invalid_classification_target(entity):
                continue

            guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
            if not guid:
                continue

            qn = _safe_text(entity.get("qualifiedName", "")).lower()
            name = _safe_text(entity.get("name", "")).lower()
            entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()

            score = 0
            asset_lower = _safe_text(asset_ref).lower()
            if asset_lower and asset_lower in qn:
                score += 5
            if explicit_column_qn and qn == explicit_column_qn.lower():
                score += 10
            if _safe_text(keywords).lower() in qn:
                score += 3
            if _safe_text(keywords).lower() == name:
                score += 2
            if "column" in entity_type:
                score += 3
            if "table" in entity_type:
                score += 1
            if explicit_column_qn and "table" in entity_type:
                score -= 2

            if score > best_score:
                best_score = score
                best = {
                    "guid": guid,
                    "entityType": entity_type,
                    "qualifiedName": _safe_text(entity.get("qualifiedName", "")),
                }

    return best


def _resolve_glossary_term_guid(token: str, term_name: str):
    term_text = _safe_text(term_name)
    if not term_text:
        return ""

    term_text = glossary_term_code_to_name.get(term_text.upper(), term_text)

    status, body = _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": term_text, "limit": 25},
        params={"api-version": "2023-09-01"},
    )
    if status != 200:
        return ""

    try:
        payload = json.loads(body)
    except Exception:
        return ""

    target = term_text.lower()
    for entity in payload.get("value") or []:
        entity_name = _safe_text(entity.get("name", ""))
        qn = _safe_text(entity.get("qualifiedName", ""))
        entity_id = _safe_text(entity.get("id", "") or entity.get("guid", ""))
        if not entity_id:
            continue
        if qn and "@" in qn and (entity_name.lower() == target or target in entity_name.lower()):
            return entity_id

    return ""


def _is_glossary_term_assigned(token: str, term_guid: str, entity_guid: str):
    status, body = _request("GET", f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities", token)
    if status != 200:
        return False

    try:
        payload = json.loads(body)
    except Exception:
        return False

    entities = payload if isinstance(payload, list) else []
    target_guid = _safe_text(entity_guid)
    for entity in entities:
        if _safe_text(entity.get("guid", "")) == target_guid:
            return True
    return False


def _apply_glossary_term(token: str, entity_guid: str, term_guid: str, entity_type: str = ""):
    if _is_glossary_term_assigned(token, term_guid, entity_guid):
        return "existing", ""

    payload = [{"guid": entity_guid, "typeName": _safe_text(entity_type)}]
    status, body = _request("POST", f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities", token, body=payload)
    if status in (200, 201, 202, 204):
        return "assigned", ""

    if _is_glossary_term_assigned(token, term_guid, entity_guid):
        return "existing", ""

    return "failed", f"HTTP {status} | {body[:300]}"


def _apply_classification(
    token: str,
    entity_guid: str,
    classification_name: str,
    label_name: str,
    assignment_source: str,
    rule: str,
    sensitivity_tier: str = "",
    protection_policy: str = "",
    cde_id: str = "",
    cde_name: str = "",
):
    attributes = {}
    if _safe_text(label_name):
        attributes["label_name"] = label_name
    if _safe_text(sensitivity_tier):
        attributes["sensitivity_tier"] = sensitivity_tier
    if _safe_text(protection_policy):
        attributes["protection_policy"] = protection_policy
    if _safe_text(assignment_source):
        attributes["assignment_source"] = assignment_source
    if _safe_text(rule):
        attributes["rule"] = rule
    if _safe_text(cde_id):
        attributes["cde_id"] = cde_id
    if _safe_text(cde_name):
        attributes["cde_name"] = cde_name

    payload = [
        {
            "typeName": classification_name,
            "attributes": attributes,
        }
    ]

    status, body = _request("POST", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}/classifications", token, body=payload)
    if status in (200, 201, 204):
        return "assigned", ""
    body_lower = body.lower()
    if (
        status == 409
        or "already exists" in body_lower
        or "already associated with classification" in body_lower
        or "ATLAS-409" in body
        or "ATLAS-400-00-01A" in body
    ):
        return "existing", ""
    return "failed", f"HTTP {status} | {body[:300]}"


def _apply_sensitivity_label(token: str, entity_guid: str, label_name: str):
    path = f"/catalog/api/atlas/v2/entity/guid/{entity_guid}/labels"
    compact = "".join(ch for ch in _safe_text(label_name) if ch.isalnum())
    label_candidates = []
    for candidate in (_safe_text(label_name), compact):
        text = _safe_text(candidate)
        if text and text not in label_candidates:
            label_candidates.append(text)

    methods = ("POST", "PUT")
    attempts = []
    for candidate_label in label_candidates:
        payloads = (
            [candidate_label],
            {"labels": [candidate_label]},
            {"labels": [{"name": candidate_label}]},
        )

        for method in methods:
            for payload in payloads:
                status, body = _request(method, path, token, body=payload)
                if status in (200, 201, 204):
                    return "assigned", ""

                body_lower = body.lower()
                if (
                    status == 409
                    or "already exists" in body_lower
                    or "already associated" in body_lower
                    or "duplicate" in body_lower
                    or "ATLAS-409" in body
                    or "ATLAS-400-00-01A" in body
                ):
                    return "existing", ""

                attempts.append((candidate_label, method, payload, status, body[:220]))

                if status in (400, 404, 405):
                    continue

                return "failed", f"HTTP {status} | {body[:300]}"

    if attempts:
        candidate_label, method, payload, status, body = attempts[-1]
        payload_preview = json.dumps(payload)[:120]
        return (
            "failed",
            f"Label apply not accepted for '{candidate_label}' via {method} payload={payload_preview} | HTTP {status} | {body}",
        )

    return "failed", "Atlas labels endpoint did not accept available payload formats for this account."


def _apply_asset_description(token: str, entity_guid: str, description: str):
    text = _safe_text(description)
    if not text:
        return "skipped", ""

    status, body = _request("GET", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}", token)
    if status != 200:
        return "failed", f"Failed to read entity before description update: HTTP {status} | {body[:220]}"

    try:
        payload = json.loads(body)
    except Exception:
        return "failed", "Entity read payload was not valid JSON."

    entity = payload.get("entity") if isinstance(payload, dict) else None
    if not isinstance(entity, dict):
        return "failed", "Entity read payload missing 'entity' object."

    attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
    current_description = _safe_text(attributes.get("description", ""))
    if current_description == text:
        return "existing", ""

    update_payload = {
        "entity": {
            "typeName": _safe_text(entity.get("typeName", "")),
            "guid": _safe_text(entity.get("guid", entity_guid)) or entity_guid,
            "attributes": {
                "qualifiedName": _safe_text(attributes.get("qualifiedName", "")),
                "name": _safe_text(attributes.get("name", "")),
                "description": text,
            },
        }
    }

    attempts = [
        ("PUT", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}", update_payload),
        ("PUT", "/catalog/api/atlas/v2/entity", update_payload),
        ("POST", "/catalog/api/atlas/v2/entity", update_payload),
    ]

    last_error = ""
    for method, path, payload in attempts:
        status, body = _request(method, path, token, body=payload)
        if status in (200, 201, 204):
            return "assigned", ""
        if status in (400, 404, 405):
            last_error = f"{method} {path} -> HTTP {status} | {body[:220]}"
            continue
        return "failed", f"{method} {path} -> HTTP {status} | {body[:300]}"

    return "failed", last_error or "No compatible endpoint accepted asset description update."


def _purge_classification(token: str, entity_guid: str, classification_name: str):
    path = (
        f"/catalog/api/atlas/v2/entity/guid/{entity_guid}"
        f"/classification/{_path_quote(classification_name)}"
    )
    status, body = _request("DELETE", path, token)
    if status in (200, 202, 204):
        return "purged", ""

    body_lower = _safe_text(body).lower()
    if status in (400, 404) or "not found" in body_lower:
        return "absent", ""

    return "failed", f"HTTP {status} | {body[:300]}"


def _purge_sensitivity_label(token: str, entity_guid: str, label_name: str):
    compact = "".join(ch for ch in _safe_text(label_name) if ch.isalnum())
    label_candidates = []
    for candidate in (_safe_text(label_name), compact):
        text = _safe_text(candidate)
        if text and text not in label_candidates:
            label_candidates.append(text)

    last_error = ""
    for candidate in label_candidates:
        path = f"/catalog/api/atlas/v2/entity/guid/{entity_guid}/labels/{_path_quote(candidate)}"
        status, body = _request("DELETE", path, token)
        if status in (200, 202, 204):
            return "purged", ""

        body_lower = _safe_text(body).lower()
        if status in (400, 404) or "not found" in body_lower:
            continue

        last_error = f"HTTP {status} | {body[:220]}"

    if last_error:
        return "failed", last_error
    return "absent", ""


def _normalize_bearer_token(raw_token: str) -> str:
    token = _safe_text(raw_token).strip().strip("\"").strip("'")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _jwt_diagnostics(token: str):
    parts = _safe_text(token).split(".")
    if len(parts) < 2:
        return None

    try:
        payload_segment = parts[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        payload_json = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception:
        return None

    exp = payload.get("exp")
    aud = _safe_text(payload.get("aud", ""))
    tid = _safe_text(payload.get("tid", ""))
    now_utc = int(time.time())
    expires_in_sec = int(exp) - now_utc if exp is not None else None
    return {
        "aud": aud,
        "tid": tid,
        "exp": exp,
        "expires_in_sec": expires_in_sec,
    }


def _get_purview_token_from_manual() -> str:
    token = _safe_text(globals().get("MANUAL_PURVIEW_BEARER_TOKEN", ""))
    if not token:
        token = _safe_text(os.environ.get("PURVIEW_BEARER_TOKEN", ""))
    token = _normalize_bearer_token(token)
    if not token:
        raise RuntimeError(
            "No manual token provided. Set MANUAL_PURVIEW_BEARER_TOKEN in Cell 1 "
            "or environment variable PURVIEW_BEARER_TOKEN."
        )

    diag = _jwt_diagnostics(token)
    if diag:
        print(
            "[Cell 6] Manual token diagnostics: "
            f"aud={diag['aud'] or '<none>'} tid={diag['tid'] or '<none>'} "
            f"expires_in_sec={diag['expires_in_sec']}"
        )

    print("[Cell 6] Using manually supplied Purview bearer token.")
    return token


def _get_purview_token_via_az_cli() -> str:
    if shutil.which("az") is None:
        raise RuntimeError(
            "'az' CLI is not available in this runtime. "
            "Use TOKEN_ACQUISITION_MODE='manual' with MANUAL_PURVIEW_BEARER_TOKEN, "
            "or run publish outside the notebook runtime."
        )

    cmd = [
        "az",
        "account",
        "get-access-token",
        "--resource",
        "https://purview.azure.net",
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=AZ_CLI_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as ex:
        raise RuntimeError(f"Azure CLI token command failed to execute: {ex}")

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"Azure CLI token command failed (exit {result.returncode}): {stderr}")

    token = _safe_text(result.stdout)
    if not token:
        raise RuntimeError("Azure CLI returned an empty access token.")

    print("[Cell 6] Acquired Purview token via Azure CLI.")
    return token


def _get_purview_token_via_tokenlibrary() -> str:
    last_error = None

    for resource in TOKEN_RESOURCE_CANDIDATES:
        for attempt in range(1, TOKEN_OUTER_RETRY_ATTEMPTS + 1):
            try:
                token = mssparkutils.credentials.getToken(resource)
                if token and _safe_text(token):
                    print(f"[Cell 6] Acquired Purview token using TokenLibrary resource='{resource}' on attempt {attempt}.")
                    return token
            except Exception as ex:
                last_error = ex

            if attempt < TOKEN_OUTER_RETRY_ATTEMPTS:
                time.sleep(3 * attempt)

    raise RuntimeError(
        f"Failed to acquire Purview token via TokenLibrary after retries. Last error: {last_error}"
    )


def _get_purview_token_with_retry() -> str:
    mode = _safe_text(globals().get("TOKEN_ACQUISITION_MODE", "auto")).lower()
    if mode not in {"auto", "manual", "azcli", "tokenlibrary"}:
        raise RuntimeError(f"Unsupported TOKEN_ACQUISITION_MODE='{mode}'. Use auto, manual, azcli, or tokenlibrary.")

    if mode == "manual":
        return _get_purview_token_from_manual()

    if mode == "azcli":
        return _get_purview_token_via_az_cli()

    if mode == "tokenlibrary":
        return _get_purview_token_via_tokenlibrary()

    # auto mode: prefer manual token, then Azure CLI, then TokenLibrary.
    try:
        return _get_purview_token_from_manual()
    except Exception as manual_ex:
        print(f"[Cell 6][WARN] Manual token path unavailable; trying Azure CLI. Error: {manual_ex}")

    try:
        return _get_purview_token_via_az_cli()
    except Exception as az_ex:
        print(f"[Cell 6][WARN] Azure CLI token path failed; falling back to TokenLibrary. Error: {az_ex}")
        return _get_purview_token_via_tokenlibrary()


def _probe_token(token: str):
    return _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": "dbo", "limit": 1},
        params={"api-version": "2023-09-01"},
    )


def _ensure_valid_token(token: str) -> str:
    status, body = _probe_token(token)
    if status == 200:
        return token

    body_lower = _safe_text(body).lower()
    if status != 401 and "invalid token" not in body_lower and "unauthenticated" not in body_lower:
        print(f"[Cell 6][WARN] Token probe returned HTTP {status}; continuing with current token.")
        return token

    print("[Cell 6][WARN] Supplied token appears invalid or expired; attempting fallback token acquisition.")
    fallback_errors = []
    for fn in (_get_purview_token_via_az_cli, _get_purview_token_via_tokenlibrary):
        try:
            candidate = fn()
            probe_status, _ = _probe_token(candidate)
            if probe_status == 200:
                print(f"[Cell 6] Switched to fallback token provider: {fn.__name__}")
                return candidate
            fallback_errors.append(f"{fn.__name__}: probe HTTP {probe_status}")
        except Exception as ex:
            fallback_errors.append(f"{fn.__name__}: {ex}")

    raise RuntimeError(
        "Purview token is invalid/expired and fallback acquisition failed. "
        f"Details: {' | '.join(fallback_errors)}"
    )


def _find_entity_by_qualified_name(token: str, qualified_name: str):
    # Datamap search is the stable endpoint for finding ingested assets by qualifiedName.
    status, body = _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": qualified_name, "limit": 25},
        params={"api-version": "2023-09-01"},
    )
    if status != 200:
        return None

    try:
        payload = json.loads(body)
    except Exception:
        return None

    entities = payload.get("value") or []
    if not entities:
        return None

    entity = None
    for candidate in entities:
        if _safe_text(candidate.get("qualifiedName")) == qualified_name:
            entity = candidate
            break
    if entity is None:
        return None

    return {
        "guid": entity.get("id") or entity.get("guid"),
        "typeName": entity.get("entityType") or entity.get("typeName"),
        "qualifiedName": qualified_name,
    }


def _find_entity_by_basic_search(token: str, query_text: str, role: str):
    status, body = _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": query_text, "limit": 50},
        params={"api-version": "2023-09-01"},
    )
    if status != 200:
        return None

    try:
        payload = json.loads(body)
    except Exception:
        return None

    entities = payload.get("value") or []
    if not entities:
        return None

    query_lower = _safe_text(query_text).lower()
    for entity in entities:
        qualified_name = _safe_text(entity.get("qualifiedName"))
        qn_lower = qualified_name.lower()
        if not qn_lower:
            continue
        if query_lower and query_lower not in qn_lower:
            continue
        if role == "source" and "mssql://" not in qn_lower:
            continue
        if role == "target" and not any(
            marker in qn_lower
            for marker in (
                "fabric://",
                "powerbi://",
                "https://app.fabric.microsoft.com/",
                "https://app.powerbi.com/",
            )
        ):
            continue
        return {
            "guid": entity.get("id") or entity.get("guid"),
            "typeName": entity.get("entityType") or entity.get("typeName"),
            "qualifiedName": qualified_name,
        }

    return None


def _entity_lookup_candidates(qualified_name: str, role: str):
    candidates = []
    qn = _safe_text(qualified_name)
    if not qn:
        return candidates

    candidates.append(qn)

    if role == "source" and qn.startswith("mssql://"):
        parts = qn[len("mssql://") :].split("/")
        if len(parts) >= 3:
            db_name = parts[0]
            schema_name = parts[1]
            table_name = parts[2]
            candidates.append(f"mssql://{SQL_SERVER_FQDN}/{db_name}/{schema_name}/{table_name}")
            if schema_name.lower() == "dbo":
                candidates.append(f"mssql://{SQL_SERVER_FQDN}/{db_name}/demo/{table_name}")
                candidates.append(f"mssql://{db_name}/demo/{table_name}")

    if role == "target" and qn.startswith("fabric://") and "/semanticModels/" in qn:
        parts = qn.split("/")
        if len(parts) >= 6:
            workspace_id = parts[2]
            asset_name = parts[-1]
            candidates.append(f"fabric://{workspace_id}/semanticModels/{SEMANTIC_MODEL_LOGICAL_ID}/{asset_name}")
            candidates.append(f"fabric://{workspace_id}/semanticModels/{SEMANTIC_MODEL_NAME}/{asset_name}")

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)

    return unique


def _resolve_entity(token: str, qualified_name: str, role: str):
    candidates = _entity_lookup_candidates(qualified_name, role)

    for candidate in candidates:
        entity = _find_entity_by_qualified_name(token, candidate)
        if entity:
            entity["matched_by"] = "qualified_name"
            entity["matched_value"] = candidate
            return entity, candidates

    search_terms = []
    if role == "source":
        table_name = _safe_text(qualified_name.split("/")[-1]).split("#")[0]
        search_terms.append(table_name)
    else:
        base_name = _safe_text(qualified_name.split("/")[-1])
        search_terms.append(base_name)
        # Add singular/plural variants for Fabric targets
        if base_name.endswith("s"):
            search_terms.append(base_name[:-1])  # Try singular (remove trailing 's')
        else:
            search_terms.append(base_name + "s")  # Try plural (add 's')

    for term in search_terms:
        if not term:
            continue
        entity = _find_entity_by_basic_search(token, term, role)
        if entity:
            entity["matched_by"] = "basic_search"
            entity["matched_value"] = term
            return entity, candidates

    # Last-chance fallback: use the broader asset resolver logic used by classification/label/glossary flows.
    fallback = _resolve_asset_for_classification(token, qualified_name)
    if fallback:
        fallback["matched_by"] = "classification_resolver_fallback"
        fallback["matched_value"] = qualified_name
        if fallback.get("typeName") is None and fallback.get("entityType") is not None:
            fallback["typeName"] = fallback.get("entityType")
        return fallback, candidates

    return None, candidates


def _build_lineage_process_entities(token: str):
    process_entities = []
    unresolved = []
    lookup_cache = {}
    started_at = time.time()

    def _cached_find(qualified_name: str, role: str):
        cache_key = f"{role}:{qualified_name}"
        if cache_key in lookup_cache:
            return lookup_cache[cache_key]
        result = _resolve_entity(token, qualified_name, role)
        lookup_cache[cache_key] = result
        return result

    total_edges = len(lineage_edges)
    print(f"[Cell 6] Resolving entity GUIDs for {total_edges} lineage edges...")

    for idx, edge in enumerate(lineage_edges, start=1):
        elapsed = time.time() - started_at
        if elapsed > MAX_ENTITY_RESOLUTION_SECONDS:
            print(
                f"[Cell 6][WARN] Resolution time cap reached ({MAX_ENTITY_RESOLUTION_SECONDS}s). "
                f"Stopping after {idx - 1} edges."
            )
            unresolved.append(
                {
                    "process_qualified_name": "__resolution_timeout__",
                    "source": None,
                    "target": None,
                    "source_found": False,
                    "target_found": False,
                    "reason": "resolution_time_cap_reached",
                    "resolved_edges": idx - 1,
                    "total_edges": total_edges,
                }
            )
            break

        if idx > MAX_EDGES_TO_RESOLVE:
            print(
                f"[Cell 6][WARN] Edge cap reached ({MAX_EDGES_TO_RESOLVE}). "
                f"Stopping before edge {idx}."
            )
            unresolved.append(
                {
                    "process_qualified_name": "__resolution_edge_cap__",
                    "source": None,
                    "target": None,
                    "source_found": False,
                    "target_found": False,
                    "reason": "resolution_edge_cap_reached",
                    "resolved_edges": idx - 1,
                    "total_edges": total_edges,
                }
            )
            break

        if idx == 1 or idx % 10 == 0 or idx == total_edges:
            print(f"[Cell 6] Progress: {idx}/{total_edges}")

        source_qn = edge["source"]
        target_qn = edge["target"]
        print(f"[Cell 6] Resolving edge {idx}/{total_edges} | source={source_qn} | target={target_qn}")

        source_entity, source_candidates = _cached_find(source_qn, "source")
        target_entity, target_candidates = _cached_find(target_qn, "target")

        if not source_entity or not target_entity:
            unresolved.append(
                {
                    "process_qualified_name": edge["process_qualified_name"],
                    "source": source_qn,
                    "target": target_qn,
                    "source_found": bool(source_entity),
                    "target_found": bool(target_entity),
                    "source_candidates": source_candidates,
                    "target_candidates": target_candidates,
                }
            )
            continue

        process_entities.append(
            {
                "typeName": "Process",
                "attributes": {
                    "qualifiedName": edge["process_qualified_name"],
                    "name": edge["process_name"],
                    "description": f"{edge['data_product']} lineage: {source_qn} -> {target_qn}",
                },
                "relationshipAttributes": {
                    "inputs": [
                        {
                            "guid": source_entity["guid"],
                            "typeName": source_entity["typeName"],
                        }
                    ],
                    "outputs": [
                        {
                            "guid": target_entity["guid"],
                            "typeName": target_entity["typeName"],
                        }
                    ],
                },
            }
        )

    return process_entities, unresolved


publish_guard_active = SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE
fail_on_token_error = bool(globals().get("FAIL_ON_TOKEN_ACQUISITION_ERROR", False))

print(
    "[Cell 6] Entry | "
    f"APPLY_CHANGES={APPLY_CHANGES}, "
    f"SQL_MIRROR_ONLY_DEPLOYMENT={SQL_MIRROR_ONLY_DEPLOYMENT}, "
    f"PURVIEW_PUBLISH_OVERRIDE={PURVIEW_PUBLISH_OVERRIDE}, "
    f"purge_before_rewrite={PURGE_BEFORE_REWRITE}, "
    f"fail_on_token_error={fail_on_token_error}, "
    f"disable_live_publish={DISABLE_LIVE_PURVIEW_PUBLISH}, "
    f"token_mode={TOKEN_ACQUISITION_MODE}, "
    f"manual_token_supplied={bool(_safe_text(globals().get('MANUAL_PURVIEW_BEARER_TOKEN', '')))}"
)

if publish_guard_active:
    print("[GUARD] SQL-mirror-only deployment is active. Set PURVIEW_PUBLISH_OVERRIDE=True for live Purview publish.")
elif DISABLE_LIVE_PURVIEW_PUBLISH:
    print("[DRY RUN] DISABLE_LIVE_PURVIEW_PUBLISH=True. Skipping token acquisition and Purview API calls.")
elif not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
else:
    token = None
    unresolved_edges = []
    try:
        token = _get_purview_token_with_retry()
    except Exception as ex:
        if fail_on_token_error:
            raise

        print(f"[WARN] Token acquisition failed; skipping live publish. Error: {ex}")
        print("[DRY RUN FALLBACK] Payloads are ready from Cell 5. Retry Cell 6 later or publish outside Fabric runtime.")
        try:
            if "output_root" in globals():
                marker = {
                    "event": "purview_token_acquisition_failed",
                    "error": str(ex),
                    "timestamp_utc": int(time.time()),
                }
                mssparkutils.fs.put(
                    f"{output_root}/publish_blocked_token_error.json",
                    json.dumps(marker, indent=2),
                    True,
                )
        except Exception:
            pass

    if token:
        try:
            token = _ensure_valid_token(token)
        except Exception as ex:
            if fail_on_token_error:
                raise

            print(f"[WARN] Token validation failed; skipping live publish. Error: {ex}")
            print("[DRY RUN FALLBACK] Payloads are ready from Cell 5. Retry Cell 6 later or publish outside Fabric runtime.")
            try:
                if "output_root" in globals():
                    marker = {
                        "event": "purview_token_validation_failed",
                        "error": str(ex),
                        "timestamp_utc": int(time.time()),
                    }
                    mssparkutils.fs.put(
                        f"{output_root}/publish_blocked_token_error.json",
                        json.dumps(marker, indent=2),
                        True,
                    )
            except Exception:
                pass
            token = None

    if token:

        print("[Cell 6] Applying sensitivity labels from manifest...")
        label_assigned = 0
        label_existing = 0
        label_failed = []
        label_unresolved = []

        label_dedupe = set()
        label_rows = []
        for row in sensitivity_label_manifest:
            asset_ref = _safe_text(row.get("asset_ref", ""))
            label_name = _safe_text(row.get("label_name", ""))
            sensitivity_tier = _safe_text(row.get("sensitivity_tier", ""))
            protection_policy = _safe_text(row.get("protection_policy", ""))
            assignment_source = _safe_text(row.get("assignment_source", ""))
            rule = _safe_text(row.get("rule", ""))

            key = (asset_ref.lower(), label_name.lower())
            if not asset_ref or not label_name or key in label_dedupe:
                continue
            label_dedupe.add(key)

            label_rows.append(
                {
                    "asset_ref": asset_ref,
                    "label_name": label_name,
                    "sensitivity_tier": sensitivity_tier,
                    "protection_policy": protection_policy,
                    "assignment_source": assignment_source,
                    "rule": rule,
                }
            )

        total_label_rows = len(label_rows)

        if PURGE_BEFORE_REWRITE:
            print("[Cell 6] Purging managed sensitivity labels before rewrite...")
            label_purged = 0
            label_already_absent = 0
            label_purge_failed = []
            for row in label_rows:
                asset_ref = row["asset_ref"]
                label_name = row["label_name"]
                resolved = _resolve_asset_for_classification(token, asset_ref)
                if not resolved:
                    continue

                purge_outcome, purge_details = _purge_sensitivity_label(token, resolved["guid"], label_name)
                if purge_outcome == "purged":
                    label_purged += 1
                elif purge_outcome == "absent":
                    label_already_absent += 1
                else:
                    label_purge_failed.append((asset_ref, label_name, purge_details))

            print(
                "[Cell 6] Sensitivity label purge summary: "
                f"purged={label_purged} absent={label_already_absent} failed={len(label_purge_failed)}"
            )
            if label_purge_failed:
                print(f"[Cell 6][WARN] First sensitivity label purge failure: {label_purge_failed[0]}")

        print(f"[Cell 6] Sensitivity label rows to process: {total_label_rows}")
        for index, row in enumerate(label_rows, start=1):
            asset_ref = row["asset_ref"]
            label_name = row["label_name"]

            if index == 1 or index % 10 == 0 or index == total_label_rows:
                print(
                    f"[Cell 6] Sensitivity label progress: {index}/{total_label_rows} | "
                    f"assigned={label_assigned} existing={label_existing} "
                    f"unresolved={len(label_unresolved)} failed={len(label_failed)}"
                )

            resolved = _resolve_asset_for_classification(token, asset_ref)
            if not resolved:
                if len(label_unresolved) < 25:
                    label_unresolved.append(asset_ref)
                continue

            outcome, details = _apply_sensitivity_label(token, resolved["guid"], label_name)

            if outcome == "assigned":
                label_assigned += 1
            elif outcome == "existing":
                label_existing += 1
            else:
                label_failed.append((asset_ref, label_name, details))

        print(
            "[Cell 6] Sensitivity label summary: "
            f"assigned={label_assigned} existing={label_existing} "
            f"unresolved={len(label_unresolved)} failed={len(label_failed)}"
        )
        if label_unresolved:
            print(f"[Cell 6][WARN] Unresolved sensitivity label asset samples: {label_unresolved[:10]}")
        if label_failed:
            print(f"[Cell 6][WARN] First sensitivity label failure: {label_failed[0]}")

        print("[Cell 6] Publishing CDE classification typedefs...")
        typedef_status, typedef_body = _post_json("/catalog/api/atlas/v2/types/typedefs", token, typedef_payload)
        if typedef_status == 401:
            print("[Cell 6][WARN] Typedef publish returned 401; refreshing token and retrying once.")
            try:
                token = _ensure_valid_token(token)
                typedef_status, typedef_body = _post_json("/catalog/api/atlas/v2/types/typedefs", token, typedef_payload)
            except Exception as ex:
                if fail_on_token_error:
                    raise
                print(f"[WARN] Token refresh failed during typedef publish; skipping remaining live publish. Error: {ex}")
                print("[DRY RUN FALLBACK] Payloads are ready from Cell 5. Retry Cell 6 later or publish outside Fabric runtime.")
                typedef_status = 401
                typedef_body = f"token refresh failed: {ex}"
        if typedef_status not in (200, 201) and "already exists" not in typedef_body.lower():
            if fail_on_token_error:
                raise RuntimeError(f"Classification typedef publish failed: HTTP {typedef_status} | {typedef_body[:500]}")
            print(
                f"[WARN] Classification typedef publish failed (HTTP {typedef_status}); "
                "skipping CDE classification apply for this run."
            )
            classification_manifest = []
        print(f"Classification typedef publish result: HTTP {typedef_status}")

        print("[Cell 6] Applying CDE classifications from manifest...")
        classification_assigned = 0
        classification_existing = 0
        classification_failed = []
        classification_unresolved = []

        dedupe = set()
        classification_rows = []
        for row in classification_manifest:
            asset_ref = _safe_text(row.get("asset_ref", ""))
            classification_name = _safe_text(row.get("classification", ""))
            assignment_source = _safe_text(row.get("assignment_source", ""))
            rule = _safe_text(row.get("rule", ""))
            cde_id = _safe_text(row.get("cde_id", ""))
            cde_name = _safe_text(row.get("cde_name", ""))

            key = (asset_ref.lower(), classification_name.lower(), cde_id.lower())
            if not asset_ref or not classification_name or key in dedupe:
                continue
            dedupe.add(key)

            classification_rows.append(
                {
                    "asset_ref": asset_ref,
                    "classification_name": classification_name,
                    "assignment_source": assignment_source,
                    "rule": rule,
                    "cde_id": cde_id,
                    "cde_name": cde_name,
                }
            )

        total_classification_rows = len(classification_rows)

        if PURGE_BEFORE_REWRITE:
            print("[Cell 6] Purging managed classifications before rewrite...")
            class_purged = 0
            class_already_absent = 0
            class_purge_failed = []
            for row in classification_rows:
                asset_ref = row["asset_ref"]
                classification_name = row["classification_name"]
                resolved = _resolve_asset_for_classification(token, asset_ref)
                if not resolved:
                    continue

                purge_outcome, purge_details = _purge_classification(token, resolved["guid"], classification_name)
                if purge_outcome == "purged":
                    class_purged += 1
                elif purge_outcome == "absent":
                    class_already_absent += 1
                else:
                    class_purge_failed.append((asset_ref, classification_name, purge_details))

            print(
                "[Cell 6] Classification purge summary: "
                f"purged={class_purged} absent={class_already_absent} failed={len(class_purge_failed)}"
            )
            if class_purge_failed:
                print(f"[Cell 6][WARN] First classification purge failure: {class_purge_failed[0]}")

        print(f"[Cell 6] CDE classification rows to process: {total_classification_rows}")
        for index, row in enumerate(classification_rows, start=1):
            asset_ref = row["asset_ref"]
            classification_name = row["classification_name"]
            assignment_source = row["assignment_source"]
            rule = row["rule"]
            cde_id = row["cde_id"]
            cde_name = row["cde_name"]

            if index == 1 or index % 10 == 0 or index == total_classification_rows:
                print(
                    f"[Cell 6] CDE classification progress: {index}/{total_classification_rows} | "
                    f"assigned={classification_assigned} existing={classification_existing} "
                    f"unresolved={len(classification_unresolved)} failed={len(classification_failed)}"
                )

            resolved = _resolve_asset_for_classification(token, asset_ref)
            if not resolved:
                if len(classification_unresolved) < 25:
                    classification_unresolved.append(asset_ref)
                continue

            outcome, details = _apply_classification(
                token,
                resolved["guid"],
                classification_name,
                "",
                assignment_source,
                rule,
                cde_id=cde_id,
                cde_name=cde_name,
            )

            if outcome == "assigned":
                classification_assigned += 1
            elif outcome == "existing":
                classification_existing += 1
            else:
                classification_failed.append((asset_ref, classification_name, details))

        print(
            "[Cell 6] CDE classification summary: "
            f"assigned={classification_assigned} existing={classification_existing} "
            f"unresolved={len(classification_unresolved)} failed={len(classification_failed)}"
        )
        if classification_unresolved:
            print(f"[Cell 6][WARN] Unresolved CDE classification asset samples: {classification_unresolved[:10]}")
        if classification_failed:
            print(f"[Cell 6][WARN] First CDE classification failure: {classification_failed[0]}")

        print("[Cell 6] Applying glossary terms from manifest...")
        glossary_assigned = 0
        glossary_existing = 0
        glossary_failed = []
        glossary_unresolved_assets = []
        glossary_unresolved_terms = []

        glossary_rows = []
        glossary_dedupe = set()
        for row in glossary_term_manifest:
            asset_ref = _safe_text(row.get("asset_ref", ""))
            term_name = _safe_text(row.get("term_name", ""))
            assignment_source = _safe_text(row.get("assignment_source", ""))
            rule = _safe_text(row.get("rule", ""))
            key = (asset_ref.lower(), term_name.lower())
            if not asset_ref or not term_name or key in glossary_dedupe:
                continue
            glossary_dedupe.add(key)
            glossary_rows.append(
                {
                    "asset_ref": asset_ref,
                    "term_name": term_name,
                    "assignment_source": assignment_source,
                    "rule": rule,
                }
            )

        term_guid_cache = {}
        total_glossary_rows = len(glossary_rows)
        print(f"[Cell 6] Glossary term rows to process: {total_glossary_rows}")
        for index, row in enumerate(glossary_rows, start=1):
            asset_ref = row["asset_ref"]
            term_name = row["term_name"]

            if index == 1 or index % 10 == 0 or index == total_glossary_rows:
                print(
                    f"[Cell 6] Glossary term progress: {index}/{total_glossary_rows} | "
                    f"assigned={glossary_assigned} existing={glossary_existing} "
                    f"unresolved_assets={len(glossary_unresolved_assets)} "
                    f"unresolved_terms={len(glossary_unresolved_terms)} failed={len(glossary_failed)}"
                )

            resolved = _resolve_asset_for_classification(token, asset_ref)
            if not resolved:
                if len(glossary_unresolved_assets) < 25:
                    glossary_unresolved_assets.append(asset_ref)
                continue

            term_key = term_name.lower()
            term_guid = term_guid_cache.get(term_key, "")
            if not term_guid:
                term_guid = _resolve_glossary_term_guid(token, term_name)
                term_guid_cache[term_key] = term_guid

            if not term_guid:
                if len(glossary_unresolved_terms) < 25:
                    glossary_unresolved_terms.append(term_name)
                continue

            outcome, details = _apply_glossary_term(
                token,
                resolved["guid"],
                term_guid,
                resolved.get("entityType", ""),
            )
            if outcome == "assigned":
                glossary_assigned += 1
            elif outcome == "existing":
                glossary_existing += 1
            else:
                glossary_failed.append((asset_ref, term_name, details))

        print(
            "[Cell 6] Glossary term summary: "
            f"assigned={glossary_assigned} existing={glossary_existing} "
            f"unresolved_assets={len(glossary_unresolved_assets)} "
            f"unresolved_terms={len(glossary_unresolved_terms)} failed={len(glossary_failed)}"
        )
        if glossary_unresolved_assets:
            print(f"[Cell 6][WARN] Unresolved glossary asset samples: {glossary_unresolved_assets[:10]}")
        if glossary_unresolved_terms:
            print(f"[Cell 6][WARN] Unresolved glossary term samples: {glossary_unresolved_terms[:10]}")
        if glossary_failed:
            print(f"[Cell 6][WARN] First glossary assignment failure: {glossary_failed[0]}")

        print("[Cell 6] Applying asset descriptions from manifest...")
        description_assigned = 0
        description_existing = 0
        description_failed = []
        description_unresolved = []

        description_rows = []
        description_dedupe = set()
        for row in asset_description_manifest:
            asset_ref = _safe_text(row.get("asset_ref", ""))
            description = _safe_text(row.get("description", ""))
            normalized_asset_ref = _asset_ref_to_table_qualified_name(asset_ref) or asset_ref
            key = normalized_asset_ref.lower()
            if not normalized_asset_ref or not description or key in description_dedupe:
                continue
            description_dedupe.add(key)
            description_rows.append(
                {
                    "asset_ref": normalized_asset_ref,
                    "description": description,
                }
            )

        total_description_rows = len(description_rows)
        print(f"[Cell 6] Asset description rows to process: {total_description_rows}")
        for index, row in enumerate(description_rows, start=1):
            asset_ref = row["asset_ref"]
            description = row["description"]

            if index == 1 or index % 10 == 0 or index == total_description_rows:
                print(
                    f"[Cell 6] Asset description progress: {index}/{total_description_rows} | "
                    f"assigned={description_assigned} existing={description_existing} "
                    f"unresolved={len(description_unresolved)} failed={len(description_failed)}"
                )

            resolved = _resolve_asset_for_classification(token, asset_ref)
            if not resolved:
                if len(description_unresolved) < 25:
                    description_unresolved.append(asset_ref)
                continue

            outcome, details = _apply_asset_description(token, resolved["guid"], description)
            if outcome == "assigned":
                description_assigned += 1
            elif outcome == "existing":
                description_existing += 1
            elif outcome == "skipped":
                continue
            else:
                description_failed.append((asset_ref, details))

        print(
            "[Cell 6] Asset description summary: "
            f"assigned={description_assigned} existing={description_existing} "
            f"unresolved={len(description_unresolved)} failed={len(description_failed)}"
        )
        if description_unresolved:
            print(f"[Cell 6][WARN] Unresolved asset description samples: {description_unresolved[:10]}")
        if description_failed:
            print(f"[Cell 6][WARN] First asset description failure: {description_failed[0]}")

        process_entities, unresolved_edges = _build_lineage_process_entities(token)
        if not process_entities:
            print("[WARN] No lineage process entities were built. Verify qualifiedName patterns and scan freshness.")
        else:
            # Atlas entity/bulk supports upsert by qualifiedName for entity types.
            batch_size = 50
            published = 0
            total_batches = (len(process_entities) + batch_size - 1) // batch_size
            for i in range(0, len(process_entities), batch_size):
                batch = process_entities[i : i + batch_size]
                batch_number = (i // batch_size) + 1
                print(f"[Cell 6] Publishing lineage batch {batch_number}/{total_batches} ({len(batch)} entities)...")
                payload = {"entities": batch}
                entity_status, entity_body = _post_json("/catalog/api/atlas/v2/entity/bulk", token, payload)
                if entity_status not in (200, 201):
                    raise RuntimeError(f"Lineage process publish failed: HTTP {entity_status} | {entity_body[:500]}")
                published += len(batch)
            print(f"Lineage processes published: {published}")

        if unresolved_edges:
            print(f"[WARN] Unresolved lineage edges: {len(unresolved_edges)}")
            print("[WARN] First unresolved edge sample:")
            print(json.dumps(unresolved_edges[0], indent=2))

# Cell 6 complete: Classification typedefs and lineage processes published (or dry-run executed)
# G9-1 closure: Purview lineage graph modeling now has live Atlas publish step (no longer manifest-only)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
