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
import os
import uuid
import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in ("1", "true", "yes", "y", "on")

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
PURVIEW_ACCOUNT_NAME = os.getenv("PURVIEW_ACCOUNT_NAME", "Purview-West3")
PURVIEW_API_BASE_URL = os.getenv("PURVIEW_API_BASE_URL", "").strip()
PURVIEW_ACCESS_TOKEN = os.getenv("PURVIEW_ACCESS_TOKEN", "").strip()
PURVIEW_BASE_URL = (
    PURVIEW_API_BASE_URL.rstrip("/")
    if PURVIEW_API_BASE_URL
    else f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"
)

# Default this notebook to live publish unless explicitly disabled.
DEFAULT_LIVE_PUBLISH = _env_bool("PURVIEW_DEFAULT_LIVE_PUBLISH", True)
PURVIEW_GLOSSARY_GUID = os.getenv("PURVIEW_GLOSSARY_GUID", "").strip()
PURVIEW_GLOSSARY_NAME = os.getenv("PURVIEW_GLOSSARY_NAME", "Enercare Glossary").strip()
SQL_MIRROR_ONLY_DEPLOYMENT = _env_bool("SQL_MIRROR_ONLY_DEPLOYMENT", not DEFAULT_LIVE_PUBLISH)
PURVIEW_PUBLISH_OVERRIDE = _env_bool("PURVIEW_PUBLISH_OVERRIDE", DEFAULT_LIVE_PUBLISH)
APPLY_CHANGES = _env_bool("PURVIEW_APPLY_CHANGES", DEFAULT_LIVE_PUBLISH)
OUTPUT_ROOT = "Files/purview_publish/phase_04_05_glossary_cde"

REQUIRED_TABLES = {
    "glossary_terms": ["term_code", "term_name", "definition", "status", "bound_assets"],
    "cdes": ["cde_name", "expected_data_type", "status", "bound_columns"],
}

print(f"Purview account: {PURVIEW_ACCOUNT_NAME}")
print(f"Purview API base URL: {PURVIEW_BASE_URL}")
print(f"Purview access token provided via env: {bool(PURVIEW_ACCESS_TOKEN)}")
print(f"Purview glossary name: {PURVIEW_GLOSSARY_NAME}")
print(f"Purview glossary guid provided: {bool(PURVIEW_GLOSSARY_GUID)}")
print(f"Apply changes: {APPLY_CHANGES}")
print(f"Publish override: {PURVIEW_PUBLISH_OVERRIDE}")
print(f"SQL mirror guard: {SQL_MIRROR_ONLY_DEPLOYMENT}")
print(f"Output root: {OUTPUT_ROOT}")

if APPLY_CHANGES and SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE:
    # Explicit live runs should not silently stay in guard mode.
    PURVIEW_PUBLISH_OVERRIDE = True
    print("[LIVE RUN] APPLY_CHANGES=True detected. Auto-enabling PURVIEW_PUBLISH_OVERRIDE.")


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
    ("glossary_target_configured", int(bool(PURVIEW_GLOSSARY_GUID) or bool(PURVIEW_GLOSSARY_NAME)), "INFO"),
]
validation_df = spark.createDataFrame(validation_rows, ["check_name", "check_value", "status"])

validation_table_candidates = []
if METADATA_SCHEMA:
    validation_table_candidates.append(f"{METADATA_SCHEMA}.purview_phase_04_05_validation")
validation_table_candidates.append("purview_phase_04_05_validation")

validation_table_written = None
last_validation_error = None
for table_name in validation_table_candidates:
    try:
        validation_df.write.mode("overwrite").format("delta").saveAsTable(table_name)
        validation_table_written = table_name
        break
    except Exception as ex:
        last_validation_error = ex

if not validation_table_written:
    raise RuntimeError(
        "Could not write validation table. "
        f"Tried: {validation_table_candidates}. Last error: {last_validation_error}"
    )

print(f"Payloads written to: {OUTPUT_ROOT}")
print(f"Validation table written to: {validation_table_written}")
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


def _capture_purview_access_token(raw_token: str) -> str:
    token = (raw_token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    # Basic JWT shape check to fail fast on copy/paste mistakes.
    if token.count(".") != 2:
        raise RuntimeError(
            "PURVIEW_ACCESS_TOKEN is missing or malformed. "
            "Capture a token with: az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv"
        )

    print("[AUTH] Using captured PURVIEW_ACCESS_TOKEN only.")
    return token


def _resolve_glossary_guid(token: str) -> str:
    if PURVIEW_GLOSSARY_GUID:
        return PURVIEW_GLOSSARY_GUID

    status, body = _request("GET", "/catalog/api/atlas/v2/glossary", token)
    if status != 200:
        raise RuntimeError(f"Could not list glossaries for GUID resolution: HTTP {status} | {body[:500]}")

    try:
        glossaries = json.loads(body)
    except Exception as ex:
        raise RuntimeError(f"Could not parse glossary list response. {ex}")

    if not isinstance(glossaries, list) or not glossaries:
        raise RuntimeError("No glossaries found in Purview. Create a glossary or set PURVIEW_GLOSSARY_GUID.")

    if PURVIEW_GLOSSARY_NAME:
        for glossary in glossaries:
            if _safe_text(glossary.get("name", "")).lower() == PURVIEW_GLOSSARY_NAME.lower():
                return _safe_text(glossary.get("guid", ""))

    if len(glossaries) == 1:
        return _safe_text(glossaries[0].get("guid", ""))

    names = [_safe_text(g.get("name", "")) for g in glossaries]
    raise RuntimeError(
        "Multiple glossaries found and no match for PURVIEW_GLOSSARY_NAME. "
        f"Available glossaries: {names}. Set PURVIEW_GLOSSARY_NAME or PURVIEW_GLOSSARY_GUID."
    )


publish_guard_active = SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE

if publish_guard_active:
    print("[GUARD] SQL-mirror-only deployment is active. Set PURVIEW_PUBLISH_OVERRIDE=True for live Purview publish.")
elif not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
else:
    token = _capture_purview_access_token(PURVIEW_ACCESS_TOKEN)

    # Quick endpoint probe to fail fast when account/base URL is misconfigured.
    probe_status, probe_body = _request("GET", "/catalog/api/atlas/v2/types/typedefs", token)
    if probe_status not in (200, 401):
        raise RuntimeError(
            f"Purview endpoint probe failed: HTTP {probe_status}. "
            f"Check PURVIEW_ACCOUNT_NAME/PURVIEW_API_BASE_URL. Body: {probe_body[:500]}"
        )

    resolved_glossary_guid = _resolve_glossary_guid(token)
    if not resolved_glossary_guid:
        raise RuntimeError("Could not resolve glossary GUID. Set PURVIEW_GLOSSARY_GUID or PURVIEW_GLOSSARY_NAME.")
    print(f"Resolved glossary guid: {resolved_glossary_guid}")

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
        payload = dict(term["payload"])
        payload["anchor"] = {"glossaryGuid": resolved_glossary_guid}
        term_status, term_body = _request("POST", "/catalog/api/atlas/v2/glossary/term", token, payload)
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
