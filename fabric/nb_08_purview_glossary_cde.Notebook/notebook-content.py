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
import uuid
import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
PURVIEW_ACCOUNT_NAME = "Purview-West3"
PURVIEW_BASE_URL = f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"
PURVIEW_GLOSSARY_GUID = ""  # Required only when APPLY_CHANGES=True for glossary term creation.
SQL_MIRROR_ONLY_DEPLOYMENT = True
PURVIEW_PUBLISH_OVERRIDE = False
APPLY_CHANGES = False
OUTPUT_ROOT = "/lakehouse/default/Files/purview_publish/phase_04_05_glossary_cde"

REQUIRED_TABLES = {
    "glossary_terms": ["term_code", "term_name", "definition", "status", "bound_assets"],
    "cdes": ["cde_name", "expected_data_type", "sensitivity_label", "status", "bound_columns"],
}

print(f"Purview account: {PURVIEW_ACCOUNT_NAME}")
print(f"Apply changes: {APPLY_CHANGES}")
print(f"Output root: {OUTPUT_ROOT}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read and validate metadata source tables


def _table_candidates(table_name: str):
    return [
        f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.{table_name}",
        f"{METADATA_SCHEMA}.{table_name}",
        table_name,
    ]


def _read_table(table_name: str):
    last_error = None
    for candidate in _table_candidates(table_name):
        try:
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex
    raise RuntimeError(f"Could not resolve table '{table_name}'. Last error: {last_error}")


def _require_columns(table_name: str, df):
    available = {c.lower(): c for c in df.columns}
    missing = [c for c in REQUIRED_TABLES[table_name] if c.lower() not in available]
    if missing:
        raise RuntimeError(f"{table_name} missing required column(s): {missing}. Available: {df.columns}")


glossary_df, glossary_source = _read_table("glossary_terms")
cde_df, cde_source = _read_table("cdes")

_require_columns("glossary_terms", glossary_df)
_require_columns("cdes", cde_df)

glossary_count = glossary_df.count()
cde_count = cde_df.count()

if glossary_count == 0:
    raise RuntimeError("metadata.glossary_terms is empty. Run nb_07a ingestion before this notebook.")
if cde_count == 0:
    raise RuntimeError("metadata.cdes is empty. Run nb_07a ingestion before this notebook.")

print(f"glossary_terms rows: {glossary_count} (source={glossary_source})")
print(f"cdes rows: {cde_count} (source={cde_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build Purview typedefs and payloads


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _guid():
    return f"-{uuid.uuid4().int % 1000000000}"


def _cde_qualified_name(cde_id: str) -> str:
    return f"enercare://governance/cde/{cde_id}"


def _asset_tokens(raw_value):
    text = _safe_text(raw_value)
    if not text:
        return []
    tokens = []
    for piece in text.replace("\n", ";").replace("|", ";").split(";"):
        item = piece.strip()
        if item:
            tokens.append(item)
    return tokens


def _resolve_cde_id(row):
    return _safe_text(getattr(row, "cde_id", None) or getattr(row, "cde_code", None) or getattr(row, "cde_name", None)).replace(" ", "-").upper()


typedef_payload = {
    "entityDefs": [
        {
            "category": "ENTITY",
            "name": "EnercareCriticalDataElement",
            "description": "Enercare critical data element curated from lh_metadata.metadata.cdes",
            "superTypes": ["Referenceable"],
            "attributeDefs": [
                {"name": "cde_id", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "cde_name", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "domain_code", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "glossary_term_code", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "expected_data_type", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "sensitivity_label", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "status", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "owner_upn", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "steward_upn", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "bound_columns", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "validation_rule", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "description", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
            ],
        }
    ],
    "classificationDefs": [
        {
            "category": "CLASSIFICATION",
            "name": "EnercareCriticalDataElementClassification",
            "description": "Asset participates in an Enercare critical data element definition",
            "attributeDefs": [
                {"name": "cde_id", "typeName": "string", "isOptional": True},
                {"name": "sensitivity_label", "typeName": "string", "isOptional": True},
            ],
        }
    ],
}

term_payloads = []
for row in glossary_df.collect():
    term_name = _safe_text(getattr(row, "term_name", None))
    term_code = _safe_text(getattr(row, "term_code", None) or term_name)
    if not term_name:
        continue
    body = {
        "name": term_name,
        "shortDescription": term_code,
        "longDescription": _safe_text(getattr(row, "definition", None)),
        "status": _safe_text(getattr(row, "status", None)) or "Draft",
        "abbreviation": _safe_text(getattr(row, "acronyms", None)),
        "resources": [{"displayName": term_code, "url": _safe_text(getattr(row, "resources", None))}] if _safe_text(getattr(row, "resources", None)) else [],
    }
    if PURVIEW_GLOSSARY_GUID:
        body["anchor"] = {"glossaryGuid": PURVIEW_GLOSSARY_GUID}
    term_payloads.append({"term_code": term_code, "payload": body, "bound_assets": _asset_tokens(getattr(row, "bound_assets", None))})

cde_entities = []
for row in cde_df.collect():
    cde_id = _resolve_cde_id(row)
    if not cde_id:
        continue
    cde_name = _safe_text(getattr(row, "cde_name", None)) or cde_id
    cde_entities.append(
        {
            "typeName": "EnercareCriticalDataElement",
            "guid": _guid(),
            "attributes": {
                "qualifiedName": _cde_qualified_name(cde_id),
                "name": cde_name,
                "cde_id": cde_id,
                "cde_name": cde_name,
                "domain_code": _safe_text(getattr(row, "domain_code", None)),
                "glossary_term_code": _safe_text(getattr(row, "glossary_term_code", None)),
                "expected_data_type": _safe_text(getattr(row, "expected_data_type", None)),
                "sensitivity_label": _safe_text(getattr(row, "sensitivity_label", None)),
                "status": _safe_text(getattr(row, "status", None)),
                "owner_upn": _safe_text(getattr(row, "owner_upn", None) or getattr(row, "owner_role", None)),
                "steward_upn": _safe_text(getattr(row, "steward_upn", None)),
                "bound_columns": ";".join(_asset_tokens(getattr(row, "bound_columns", None))),
                "validation_rule": _safe_text(getattr(row, "validation_rule", None)),
                "description": _safe_text(getattr(row, "description", None) or getattr(row, "business_definition", None)),
            },
        }
    )

cde_payload = {"entities": cde_entities}

print(f"Glossary term payloads prepared: {len(term_payloads)}")
print(f"CDE entities prepared: {len(cde_entities)}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Write dry-run payloads and validation manifest

mssparkutils.fs.mkdirs(OUTPUT_ROOT)
mssparkutils.fs.put(f"{OUTPUT_ROOT}/typedefs_glossary_cde.json", json.dumps(typedef_payload, indent=2), True)
mssparkutils.fs.put(f"{OUTPUT_ROOT}/glossary_terms.json", json.dumps(term_payloads, indent=2), True)
mssparkutils.fs.put(f"{OUTPUT_ROOT}/cde_entities.json", json.dumps(cde_payload, indent=2), True)

validation_rows = [
    ("glossary_terms_source_rows", glossary_count, "PASS" if glossary_count > 0 else "FAIL"),
    ("cdes_source_rows", cde_count, "PASS" if cde_count > 0 else "FAIL"),
    ("glossary_payloads_prepared", len(term_payloads), "PASS" if term_payloads else "FAIL"),
    ("cde_entities_prepared", len(cde_entities), "PASS" if cde_entities else "FAIL"),
    ("glossary_guid_configured", int(bool(PURVIEW_GLOSSARY_GUID)), "INFO"),
]
validation_df = spark.createDataFrame(validation_rows, ["check_name", "check_value", "status"])
validation_df.write.mode("overwrite").format("delta").saveAsTable(f"{METADATA_SCHEMA}.purview_phase_04_05_validation")

print(f"Payloads written to: {OUTPUT_ROOT}")
display(validation_df.orderBy("check_name"))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Optional live publish to Purview


def _headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request(method: str, path: str, token: str, body=None):
    url = f"{PURVIEW_BASE_URL}{path}"
    response = requests.request(method, url, headers=_headers(token), json=body, timeout=60)
    return response.status_code, response.text


publish_guard_active = SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE

if publish_guard_active:
    print("[GUARD] SQL-mirror-only deployment is active. Set PURVIEW_PUBLISH_OVERRIDE=True for live Purview publish.")
elif not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
else:
    if not PURVIEW_GLOSSARY_GUID:
        raise RuntimeError("PURVIEW_GLOSSARY_GUID must be set before live glossary term creation.")

    token = mssparkutils.credentials.getToken("https://purview.azure.net")

    typedef_status, typedef_body = _request("POST", "/catalog/api/atlas/v2/types/typedefs", token, typedef_payload)
    if typedef_status not in (200, 201) and "already exists" not in typedef_body.lower():
        raise RuntimeError(f"TypeDef publish failed: HTTP {typedef_status} | {typedef_body[:500]}")
    print(f"TypeDefs publish result: HTTP {typedef_status}")

    entity_status, entity_body = _request("POST", "/catalog/api/atlas/v2/entity/bulk", token, cde_payload)
    if entity_status not in (200, 201):
        raise RuntimeError(f"CDE entity publish failed: HTTP {entity_status} | {entity_body[:500]}")
    print(f"CDE entity publish result: HTTP {entity_status}")

    created_terms = 0
    for term in term_payloads:
        term_status, term_body = _request("POST", "/catalog/api/atlas/v2/glossary/term", token, term["payload"])
        if term_status in (200, 201):
            created_terms += 1
        elif "already exists" not in term_body.lower():
            raise RuntimeError(f"Glossary term publish failed for {term['term_code']}: HTTP {term_status} | {term_body[:500]}")
    print(f"Glossary terms created or updated: {created_terms}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
