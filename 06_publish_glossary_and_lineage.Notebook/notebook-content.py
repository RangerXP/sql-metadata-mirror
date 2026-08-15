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
import base64
import time
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
SEMANTIC_MODEL_NAME = "BrookfieldEnercare"
PURVIEW_ACCOUNT_NAME = os.getenv("PURVIEW_ACCOUNT_NAME", "Purview-West3")
PURVIEW_API_BASE_URL = (
    os.getenv("PURVIEW_API_BASE_URL", "").strip()
    or os.getenv("PURVIEW_PRIVATE_ENDPOINT_URL", "").strip()
    or os.getenv("PURVIEW_PRIVATE_BASE_URL", "").strip()
)
PURVIEW_ACCESS_TOKEN = os.getenv("PURVIEW_ACCESS_TOKEN", "").strip()
PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_TOKEN_CACHE_PATH = "Files/purview_publish/.purview_token_cache.json"
PURVIEW_BASE_URL = (
    PURVIEW_API_BASE_URL.rstrip("/")
    if PURVIEW_API_BASE_URL
    else f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"
)

# Dry-run is the committed default; live publish requires explicit runtime opt-in.
DEFAULT_LIVE_PUBLISH = _env_bool("PURVIEW_DEFAULT_LIVE_PUBLISH", False)
PURVIEW_GLOSSARY_GUID = os.getenv("PURVIEW_GLOSSARY_GUID", "").strip()
PURVIEW_GLOSSARY_NAME = os.getenv("PURVIEW_GLOSSARY_NAME", "Enercare Glossary").strip()
SQL_MIRROR_ONLY_DEPLOYMENT = _env_bool("SQL_MIRROR_ONLY_DEPLOYMENT", not DEFAULT_LIVE_PUBLISH)
PURVIEW_PUBLISH_OVERRIDE = _env_bool("PURVIEW_PUBLISH_OVERRIDE", DEFAULT_LIVE_PUBLISH)
APPLY_CHANGES = _env_bool("PURVIEW_APPLY_CHANGES", DEFAULT_LIVE_PUBLISH)
OUTPUT_ROOT = "Files/purview_publish/phase_04_05_glossary_cde"

# Explicit aliases for shorthand semantic measure bindings used in source metadata.
MEASURE_TOKEN_ALIASES = {
    "fcr": ["FCR Rate", "First Contact Resolution", "FCR"],
    "nps": ["NPS", "Net Promoter Score"],
    "csat": ["CSAT", "Customer Satisfaction"],
}

# Token-specific search hints for hard-to-resolve bindings.
ASSET_TOKEN_SEARCH_HINTS = {
    "brookfieldenercare/_measures/fcr": [
        "FCR Rate",
        "First Contact Resolution",
        "dbo.service_requests",
        "service_requests",
    ],
}

# Deterministic fallback: KPI measure tokens map to canonical governed assets when a measure entity is not discoverable.
KPI_MEASURE_FALLBACK_ASSET_TOKENS = {
    "brookfieldenercare/_measures/fcr": "dbo.service_requests",
}

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

if APPLY_CHANGES:
    print("[RUN] Approved live publish requested. Ensure the runtime environment has the required Purview credentials.")


def _log_nb08_diagnostic(stage: str, error: Exception):
    import traceback
    diag_row = {
        "stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error)[:4000],
        "traceback": traceback.format_exc()[:8000],
    }
    try:
        spark.createDataFrame([diag_row]).write.format("delta").mode("append").saveAsTable("nb08_diagnostics_log")
        print(f"[DIAG] Logged failure at stage '{stage}' to nb08_diagnostics_log")
    except Exception as log_ex:
        print(f"[DIAG] Could not log diagnostic for stage '{stage}': {log_ex}")
        print(f"[DIAG] Original error at stage '{stage}': {type(error).__name__}: {error}")
        print(traceback.format_exc())


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
            # Spark's catalog can cache a stale schema (e.g. a dropped/renamed column)
            # across sessions; refresh before reading to avoid collectToPython mismatches.
            try:
                spark.catalog.refreshTable(candidate)
            except Exception:
                pass
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex
    raise RuntimeError(f"Could not resolve table '{table_name}'. Last error: {last_error}")


def _require_columns(table_name: str, df):
    available = {c.lower(): c for c in df.columns}
    missing = [c for c in REQUIRED_TABLES[table_name] if c.lower() not in available]
    if missing:
        raise RuntimeError(f"{table_name} missing required column(s): {missing}. Available: {df.columns}")


# Columns actually read further down. Pruning to this set avoids collectToPython
# failures when the Delta table's schema has stale/unmaterialized columns
# (e.g. a schema-declared column from another notebook's write that this
# session's cached plan still references but the current data doesn't have).
GLOSSARY_COLUMNS_NEEDED = [
    "term_code", "term_name", "definition", "status", "acronyms", "resources", "bound_assets",
]
CDE_COLUMNS_NEEDED = [
    "cde_id", "cde_code", "cde_name", "domain_code", "parent_glossary_term", "expected_data_type",
    "sensitivity_label", "status", "owner_upn", "owner_role", "steward_upn", "bound_columns",
    "validation_rule", "description", "business_definition",
]


def _prune_columns(df, needed_columns):
    available = {c.lower(): c for c in df.columns}
    select_cols = [available[c] for c in needed_columns if c in available]
    return df.select(*select_cols)


try:
    glossary_df, glossary_source = _read_table("glossary_terms")
    cde_df, cde_source = _read_table("cdes")

    _require_columns("glossary_terms", glossary_df)
    _require_columns("cdes", cde_df)

    glossary_df = _prune_columns(glossary_df, GLOSSARY_COLUMNS_NEEDED)
    cde_df = _prune_columns(cde_df, CDE_COLUMNS_NEEDED)

    glossary_count = glossary_df.count()
    cde_count = cde_df.count()

    if glossary_count == 0:
        raise RuntimeError("metadata.glossary_terms is empty. Run nb_07a ingestion before this notebook.")
    if cde_count == 0:
        raise RuntimeError("metadata.cdes is empty. Run nb_07a ingestion before this notebook.")


    print(f"glossary_terms rows: {glossary_count} (source={glossary_source})")
    print(f"cdes rows: {cde_count} (source={cde_source})")
except Exception as ex:
    _log_nb08_diagnostic("cell2_read_validate", ex)
    raise


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


def _safe_external_url(value):
    text = _safe_text(value)
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return text
    return ""


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

try:
    term_payloads = []
    for row in glossary_df.collect():
        term_name = _safe_text(getattr(row, "term_name", None))
        term_code = _safe_text(getattr(row, "term_code", None) or term_name)
        if not term_name:
            continue
        resource_url = _safe_external_url(getattr(row, "resources", None))
        body = {
            "name": term_name,
            "shortDescription": term_code,
            "longDescription": _safe_text(getattr(row, "definition", None)),
            "status": _safe_text(getattr(row, "status", None)) or "Draft",
            "abbreviation": _safe_text(getattr(row, "acronyms", None)),
            "resources": [{"displayName": term_code, "url": resource_url}] if resource_url else [],
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
                    "glossary_term_code": _safe_text(getattr(row, "parent_glossary_term", None)),
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
except Exception as ex:
    _log_nb08_diagnostic("cell3_build_payloads", ex)
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Write dry-run payloads and validation manifest

try:
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
except Exception as ex:
    _log_nb08_diagnostic("cell4_write_validation", ex)
    raise


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Optional live publish to Purview


def _headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request(method: str, path: str, token: str, body=None, params=None):
    url = f"{PURVIEW_BASE_URL}{path}"
    response = requests.request(method, url, headers=_headers(token), json=body, params=params, timeout=60)
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

    # Fail fast on expired/near-expiry tokens to avoid mid-run 401 errors.
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        exp = int(claims.get("exp", 0))
    except Exception:
        exp = 0

    if exp <= 0:
        raise RuntimeError(
            "PURVIEW_ACCESS_TOKEN could not be validated for expiry. "
            "Regenerate it: az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv"
        )

    now_epoch = int(__import__("time").time())
    if exp <= now_epoch + 60:
        raise RuntimeError(
            "PURVIEW_ACCESS_TOKEN is expired or will expire in under 60 seconds. "
            "Regenerate it with: az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv"
        )

    print("[AUTH] Using captured PURVIEW_ACCESS_TOKEN only.")
    return token


def _read_shared_purview_token_cache():
    # Cache is shared (via lakehouse Files) across nb_07/nb_08/nb_09 sessions so a
    # sign-in done in one notebook doesn't have to be repeated in the others.
    cache_path = PURVIEW_TOKEN_CACHE_PATH  # NameError here means Cell 1 wasn't run
    try:
        raw = mssparkutils.fs.head(cache_path, 65536)
        cached = json.loads(raw)
        token = _safe_text(cached.get("access_token", ""))
        expires_on = float(cached.get("expires_on", 0))
    except Exception:
        return ""
    if not token or expires_on <= __import__("time").time() + 120:
        return ""
    return token


def _write_shared_purview_token_cache(token: str, expires_on: float):
    try:
        mssparkutils.fs.mkdirs("Files/purview_publish")
        mssparkutils.fs.put(
            PURVIEW_TOKEN_CACHE_PATH,
            json.dumps({"access_token": token, "expires_on": expires_on}),
            True,
        )
    except Exception as exc:
        print(f"[WARN] Could not write shared Purview token cache: {exc}")


def _get_purview_token_via_device_code(tenant_id: str) -> str:
    try:
        from azure.identity import DeviceCodeCredential
    except ImportError:
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "azure-identity"], check=True)
        from azure.identity import DeviceCodeCredential

    def _print_device_code(verification_uri, user_code, expires_on):
        print(f"[AUTH] Open {verification_uri} in any browser and enter code: {user_code}")

    credential = DeviceCodeCredential(
        client_id="04b07795-8ddb-461a-bbee-02f9e1bf7b46",
        tenant_id=tenant_id,
        prompt_callback=_print_device_code,
    )
    result = credential.get_token("https://purview.azure.net/.default")
    _write_shared_purview_token_cache(result.token, result.expires_on)
    return result.token


def _resolve_purview_token() -> str:
    if PURVIEW_ACCESS_TOKEN:
        print("[AUTH] Using PURVIEW_ACCESS_TOKEN supplied for this notebook.")
        return _capture_purview_access_token(PURVIEW_ACCESS_TOKEN)

    cached_token = _read_shared_purview_token_cache()
    if cached_token:
        print("[AUTH] Reusing cached Purview token acquired from another notebook/session.")
        return cached_token

    print("[AUTH] No token supplied and no valid cached token found; starting device-code sign-in.")
    return _get_purview_token_via_device_code(PURVIEW_TENANT_ID)


def _extract_glossary_guid(glossary_obj) -> str:
    if not isinstance(glossary_obj, dict):
        return ""
    return _safe_text(glossary_obj.get("guid", "") or glossary_obj.get("id", ""))


def _create_glossary(token: str, glossary_name: str) -> str:
    create_body = {
        "name": glossary_name,
        "shortDescription": "Auto-created by nb_08_purview_glossary_cde for glossary term publish",
    }
    create_status, create_response = _request("POST", "/catalog/api/atlas/v2/glossary", token, create_body)
    if create_status not in (200, 201):
        raise RuntimeError(
            f"Could not create glossary '{glossary_name}': HTTP {create_status} | {create_response[:500]}"
        )

    try:
        created = json.loads(create_response)
    except Exception as ex:
        raise RuntimeError(f"Glossary create response parse failed. {ex}")

    guid = _extract_glossary_guid(created)
    if not guid:
        raise RuntimeError(f"Glossary created but guid was missing in response: {create_response[:500]}")
    print(f"[GLOSSARY] Created glossary '{glossary_name}' with guid {guid}")
    return guid


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

    if not isinstance(glossaries, list):
        raise RuntimeError(f"Unexpected glossary list response shape: {type(glossaries)}")

    if not glossaries:
        if not PURVIEW_GLOSSARY_NAME:
            raise RuntimeError("No glossaries found and PURVIEW_GLOSSARY_NAME is empty.")
        return _create_glossary(token, PURVIEW_GLOSSARY_NAME)

    if PURVIEW_GLOSSARY_NAME:
        for glossary in glossaries:
            if _safe_text(glossary.get("name", "")).lower() == PURVIEW_GLOSSARY_NAME.lower():
                guid = _extract_glossary_guid(glossary)
                if guid:
                    return guid

    if len(glossaries) == 1:
        guid = _extract_glossary_guid(glossaries[0])
        if guid:
            return guid

    names = [_safe_text(g.get("name", "")) for g in glossaries]
    raise RuntimeError(
        "Multiple glossaries found and no match for PURVIEW_GLOSSARY_NAME. "
        f"Available glossaries: {names}. Set PURVIEW_GLOSSARY_NAME or PURVIEW_GLOSSARY_GUID."
    )


def _list_glossary_terms(glossary_guid: str, auth_token: str):
    status, body = _request("GET", f"/catalog/api/atlas/v2/glossary/{glossary_guid}/terms", auth_token)
    if status != 200:
        return []
    try:
        payload = json.loads(body)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _build_term_guid_index(glossary_guid: str, auth_token: str):
    terms = _list_glossary_terms(glossary_guid, auth_token)
    index = {}
    for term in terms:
        guid = _safe_text(term.get("guid", "") or term.get("id", ""))
        if not guid:
            continue

        name = _safe_text(term.get("name", "")).lower()
        short_desc = _safe_text(term.get("shortDescription", "")).lower()

        if name:
            index.setdefault(("name", name), guid)
        if short_desc:
            index.setdefault(("code", short_desc), guid)
    return index


def _search_purview_assets(token: str, keywords: str, limit: int = 50):
    status, body = _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": keywords, "limit": limit},
        params={"api-version": "2023-09-01"},
    )
    if status != 200:
        return []
    try:
        payload = json.loads(body)
    except Exception:
        return []
    entities = payload.get("value") or []
    return entities if isinstance(entities, list) else []


def _resolve_semantic_model_anchor(auth_token: str):
    candidates = _search_purview_assets(auth_token, SEMANTIC_MODEL_NAME, limit=50)
    best = None
    best_score = 0
    for entity in candidates:
        entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
        guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
        name = _safe_text(entity.get("name", ""))
        qualified_name = _safe_text(entity.get("qualifiedName", ""))
        if not guid:
            continue

        score = 0
        if name.lower() == SEMANTIC_MODEL_NAME.lower():
            score += 8
        if SEMANTIC_MODEL_NAME.lower() in qualified_name.lower():
            score += 4
        if entity_type in {"powerbi_dataset", "powerbi_semantic_model", "fabric_semantic_model"}:
            score += 8
        elif "semantic" in entity_type or "dataset" in entity_type:
            score += 4

        if score > best_score:
            best_score = score
            best = {
                "guid": guid,
                "entityType": entity_type,
                "name": name,
                "qualifiedName": qualified_name,
            }

    return best if best_score > 0 else None


def _set_entity_owner(entity_guid: str, owner_upn: str, auth_token: str):
    owner = _safe_text(owner_upn)
    if not owner:
        return "skipped", "owner is empty"

    status, body = _request("GET", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}", auth_token)
    if status != 200:
        return "failed", f"HTTP {status} | {body[:220]}"

    try:
        payload = json.loads(body)
        entity = payload.get("entity") if isinstance(payload, dict) else {}
        attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
    except Exception:
        return "failed", "entity read payload was not valid JSON"

    current_owner = _safe_text(attributes.get("owner", ""))
    if current_owner.lower() == owner.lower():
        return "existing", ""

    update_payload = {
        "entity": {
            "typeName": _safe_text(entity.get("typeName", "")),
            "guid": _safe_text(entity.get("guid", entity_guid)) or entity_guid,
            "attributes": {
                "qualifiedName": _safe_text(attributes.get("qualifiedName", "")),
                "name": _safe_text(attributes.get("name", "")),
                "owner": owner,
            },
        }
    }

    attempts = [
        ("PUT", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}"),
        ("PUT", "/catalog/api/atlas/v2/entity"),
        ("POST", "/catalog/api/atlas/v2/entity"),
    ]
    for method, path in attempts:
        update_status, update_body = _request(method, path, auth_token, body=update_payload)
        if update_status in (200, 201, 204):
            return "assigned", ""
        if update_status in (400, 404, 405):
            continue
        return "failed", f"{method} {path} -> HTTP {update_status} | {update_body[:220]}"

    return "failed", "no compatible endpoint accepted owner update"


def _parse_bound_asset_token(token_text: str):
    token = _safe_text(token_text)
    lower = token.lower()

    if lower.startswith("dbo."):
        parts = token.split(".")
        if len(parts) >= 3:
            return {
                "kind": "SqlColumn",
                "table": parts[1].strip().lower(),
                "column": ".".join(parts[2:]).strip().lower(),
                "token": token,
            }
        if len(parts) == 2:
            return {
                "kind": "SqlTable",
                "table": parts[1].strip().lower(),
                "column": "",
                "token": token,
            }

    if "/_Measures/" in token:
        pieces = [p.strip() for p in token.split("/") if p.strip()]
        measure_name = pieces[-1] if pieces else token
        return {
            "kind": "Measure",
            "table": "_measures",
            "column": measure_name.lower(),
            "token": token,
        }

    if "/" in token:
        pieces = [p.strip() for p in token.split("/") if p.strip()]
        if len(pieces) >= 3:
            return {
                "kind": "ModelColumn",
                "table": pieces[-2].lower(),
                "column": pieces[-1].lower(),
                "token": token,
            }
        if len(pieces) == 2:
            return {
                "kind": "ModelTable",
                "table": pieces[-1].lower(),
                "column": "",
                "token": token,
            }

    return {"kind": "Unknown", "table": "", "column": "", "token": token}


def _asset_query_candidates(parsed_token):
    candidates = []
    kind = parsed_token["kind"]
    table = parsed_token["table"]
    column = parsed_token["column"]
    raw = parsed_token["token"]

    if kind == "SqlColumn":
        candidates.extend([f"{table} {column}", f"dbo {table} {column}", f"{table}.{column}"])
    elif kind == "SqlTable":
        candidates.extend([f"{table}", f"dbo {table}", f"dbo.{table}"])
    elif kind in ("Measure", "ModelColumn"):
        candidates.extend([f"{column}", f"{table} {column}", raw])
    elif kind == "ModelTable":
        candidates.extend([f"{table}", raw])
    else:
        candidates.append(raw)

    seen = set()
    unique = []
    for candidate in candidates:
        text = _safe_text(candidate)
        if text and text not in seen:
            unique.append(text)
            seen.add(text)
    return unique


def _score_asset_candidate(entity, parsed_token):
    qualified_name = _safe_text(entity.get("qualifiedName", "")).lower()
    entity_name = _safe_text(entity.get("name", "")).lower()
    entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
    table = parsed_token["table"]
    column = parsed_token["column"]
    kind = parsed_token["kind"]

    score = 0
    if kind in ("SqlColumn", "SqlTable") and "mssql://" in qualified_name:
        score += 3
    if kind in ("Measure", "ModelColumn", "ModelTable") and (
        "fabric://" in qualified_name or "powerbi://" in qualified_name or "semantic" in qualified_name
    ):
        score += 3
    if table and table in qualified_name:
        score += 4
    if column and column in qualified_name:
        score += 5
    if table and table == entity_name:
        score += 2
    if column and column == entity_name:
        score += 2
    if kind in ("SqlColumn", "ModelColumn") and "column" in entity_type:
        score += 2
    if kind in ("SqlTable", "ModelTable") and "table" in entity_type:
        score += 2
    if kind == "Measure" and "measure" in entity_type:
        score += 2
    return score


def _is_glossary_term_entity(entity) -> bool:
    entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
    return "glossaryterm" in entity_type or "atlasglossaryterm" in entity_type


def _compact_token(value: str) -> str:
    return "".join(ch for ch in _safe_text(value).lower() if ch.isalnum())


def _resolve_asset_guid_for_token(token: str, auth_token: str, term_name: str = ""):
    parsed = _parse_bound_asset_token(token)
    best = None
    best_score = 0

    token_key = _safe_text(token).lower()
    explicit_hints = ASSET_TOKEN_SEARCH_HINTS.get(token_key, [])
    for keywords in explicit_hints:
        for entity in _search_purview_assets(auth_token, keywords, limit=50):
            if _is_glossary_term_entity(entity):
                continue
            guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
            if not guid:
                continue
            score = _score_asset_candidate(entity, parsed)
            # Lift score floor for explicit token hints.
            score = max(score, 3)
            if score > best_score:
                best_score = score
                best = guid

    for keywords in _asset_query_candidates(parsed):
        for entity in _search_purview_assets(auth_token, keywords, limit=50):
            if _is_glossary_term_entity(entity):
                continue
            guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
            if not guid:
                continue
            score = _score_asset_candidate(entity, parsed)
            if score > best_score:
                best_score = score
                best = guid

    # Fallback for short KPI aliases (example: FCR) that map to longer measure names.
    if not best and parsed["kind"] == "Measure":
        alias = _compact_token(parsed["column"])
        fallback_queries = []
        if term_name:
            fallback_queries.append(term_name)
        if alias:
            fallback_queries.append(alias)
            alias_targets = MEASURE_TOKEN_ALIASES.get(alias, [])
            fallback_queries.extend(alias_targets)

        for keywords in fallback_queries:
            for entity in _search_purview_assets(auth_token, keywords, limit=50):
                if _is_glossary_term_entity(entity):
                    continue
                guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
                if not guid:
                    continue
                entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
                qualified_name = _safe_text(entity.get("qualifiedName", "")).lower()
                display_name = _safe_text(entity.get("name", "")).lower()
                display_compact = _compact_token(display_name)

                if "measure" not in entity_type and "semantic" not in qualified_name:
                    continue

                if alias and alias in _compact_token(qualified_name):
                    return guid
                if alias and alias in display_compact:
                    return guid
                if term_name and _compact_token(term_name) and _compact_token(term_name) in display_compact:
                    return guid

    # Final deterministic KPI fallback to canonical assets.
    if not best:
        fallback_token = KPI_MEASURE_FALLBACK_ASSET_TOKENS.get(token_key, "")
        if fallback_token and _safe_text(fallback_token).lower() != token_key:
            fallback_parsed = _parse_bound_asset_token(fallback_token)
            fallback_best = None
            fallback_score = 0
            for keywords in _asset_query_candidates(fallback_parsed):
                for entity in _search_purview_assets(auth_token, keywords, limit=50):
                    if _is_glossary_term_entity(entity):
                        continue
                    guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
                    if not guid:
                        continue
                    score = _score_asset_candidate(entity, fallback_parsed)
                    if score > fallback_score:
                        fallback_score = score
                        fallback_best = guid
            if fallback_best and fallback_score > 0:
                return fallback_best

    return best if best_score > 0 else ""


def _resolve_glossary_term_guid(term_name: str, term_code: str, term_guid_index):
    by_name = term_guid_index.get(("name", _safe_text(term_name).lower()), "")
    if by_name:
        return by_name
    by_code = term_guid_index.get(("code", _safe_text(term_code).lower()), "")
    if by_code:
        return by_code
    return ""


def _self_heal_term_short_description(term_guid: str, desired_code: str, auth_token: str) -> bool:
    # Terms created under an earlier/stale numbering convention (e.g. shortDescription
    # "GT-001" while the current source data's term_code is "GT-CUSTOMER") can never be
    # resolved by code, which silently blocks CDE-to-Term and asset-association lookups.
    # Bring the live term's shortDescription back in sync with the current term_code.
    status, body = _request("GET", f"/catalog/api/atlas/v2/glossary/term/{term_guid}", auth_token)
    if status != 200:
        return False
    try:
        current = json.loads(body)
    except Exception:
        return False
    if _safe_text(current.get("shortDescription", "")) == desired_code:
        return False
    current["shortDescription"] = desired_code
    put_status, _ = _request("PUT", f"/catalog/api/atlas/v2/glossary/term/{term_guid}", auth_token, current)
    return put_status in (200, 201)


def _assign_term_to_entity(term_guid: str, entity_guid: str, auth_token: str):
    if _safe_text(term_guid) == _safe_text(entity_guid):
        return "skipped", "term_guid equals entity_guid"

    # Guardrail: skip invalid targets that are themselves glossary terms.
    meta_status, meta_body = _request("GET", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}", auth_token)
    if meta_status == 200:
        try:
            meta = json.loads(meta_body)
            target_type = _safe_text(
                (meta.get("entity") or {}).get("typeName", "")
                or (meta.get("entity") or {}).get("type", "")
            ).lower()
            if "glossaryterm" in target_type or "atlasglossaryterm" in target_type:
                return "skipped", f"invalid target type: {target_type}"
        except Exception:
            pass

    status, body = _request(
        "POST",
        f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities",
        auth_token,
        body=[{"guid": entity_guid}],
    )
    if status in (200, 201, 204):
        return "assigned", ""
    if status == 409 or "already exists" in body.lower():
        return "existing", ""
    return "failed", f"HTTP {status} | {body[:300]}"


publish_guard_active = SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE

if publish_guard_active:
    print("[GUARD] SQL-mirror-only deployment is active. Set PURVIEW_PUBLISH_OVERRIDE=True for live Purview publish.")
elif not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
else:
    token = _resolve_purview_token()

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

    # Register each entityDef individually: Atlas's bulk typedefs POST is atomic across
    # the whole payload, so mixing an already-existing type with a new one can silently
    # block the new type's creation even though the response looks like a benign "already exists".
    for entity_def in typedef_payload.get("entityDefs", []):
        def_name = entity_def.get("name", "<unknown>")
        def_status, def_body = _request(
            "POST", "/catalog/api/atlas/v2/types/typedefs", token, {"entityDefs": [entity_def]}
        )
        if def_status in (200, 201):
            print(f"[APPLIED] typedef {def_name}: HTTP {def_status}")
        elif def_status in (400, 409) and "already exists" in def_body.lower():
            print(f"[INFO] typedef {def_name} already exists: HTTP {def_status}")
        else:
            raise RuntimeError(f"TypeDef publish failed for {def_name}: HTTP {def_status} | {def_body[:500]}")

    entity_max_attempts = 4
    entity_backoff_seconds = 10.0
    entity_status, entity_body = None, ""
    for attempt in range(1, entity_max_attempts + 1):
        entity_status, entity_body = _request("POST", "/catalog/api/atlas/v2/entity/bulk", token, cde_payload)
        if entity_status in (200, 201):
            break
        if entity_status == 400 and "ATLAS-400-00-014" in entity_body and "does not exist" in entity_body.lower():
            print(f"[RETRY] entity/bulk attempt {attempt}/{entity_max_attempts} hit type-cache lag, retrying...")
            time.sleep(entity_backoff_seconds)
            continue
        break
    if entity_status not in (200, 201):
        raise RuntimeError(f"CDE entity publish failed: HTTP {entity_status} | {entity_body[:500]}")
    print(f"CDE entity publish result: HTTP {entity_status}")

    created_terms = 0
    existing_terms = 0
    healed_terms = 0
    failed_terms = []
    term_guid_by_code = {}
    total_terms = len(term_payloads)

    # Build the name/code -> guid index up front so already-existing terms can be
    # resolved and self-healed in the same pass, not just newly-created ones.
    term_guid_index = _build_term_guid_index(resolved_glossary_guid, token)
    print(f"Glossary term index loaded: {len(term_guid_index)} key(s)")

    print(f"Starting glossary term publish for {total_terms} terms...")
    for index, term in enumerate(term_payloads, start=1):
        print(f"Publishing term {index}/{total_terms}: {term['term_code']}")
        payload = dict(term["payload"])
        payload["anchor"] = {"glossaryGuid": resolved_glossary_guid}
        term_status, term_body = _request("POST", "/catalog/api/atlas/v2/glossary/term", token, payload)
        if term_status in (200, 201):
            created_terms += 1
            try:
                created_term = json.loads(term_body)
                guid = _safe_text(created_term.get("guid", "") or created_term.get("id", ""))
                if guid:
                    term_guid_by_code[term["term_code"]] = guid
            except Exception:
                pass
        elif term_status == 409 or "already exists" in term_body.lower():
            existing_terms += 1
            term_name = _safe_text(payload.get("name", ""))
            existing_guid = _resolve_glossary_term_guid(term_name, term["term_code"], term_guid_index)
            if existing_guid:
                term_guid_by_code[term["term_code"]] = existing_guid
                try:
                    if _self_heal_term_short_description(existing_guid, term["term_code"], token):
                        healed_terms += 1
                except Exception:
                    pass
        else:
            failed_terms.append((term["term_code"], term_status, term_body[:300]))
        if index % 5 == 0 or index == total_terms:
            print(
                f"Progress: {index}/{total_terms} | "
                f"created={created_terms} existing={existing_terms} healed={healed_terms} failed={len(failed_terms)}"
            )

    if failed_terms:
        sample = failed_terms[0]
        raise RuntimeError(
            "Glossary term publish completed with failures. "
            f"failed={len(failed_terms)} first_failure=({sample[0]}, HTTP {sample[1]}, {sample[2]})"
        )

    print(
        "Glossary term publish complete. "
        f"created={created_terms} existing={existing_terms} healed={healed_terms} failed=0"
    )

    print("Starting glossary-to-asset association...")
    semantic_anchor = _resolve_semantic_model_anchor(token)
    if semantic_anchor:
        print(
            "Semantic-model anchor resolved for fallback association: "
            f"{semantic_anchor['name']} ({semantic_anchor['guid']})"
        )
    else:
        print(
            "[WARN] Semantic-model anchor not resolved; glossary associations will only target resolved bound assets."
        )

    # Promote at least one governed owner onto the semantic model asset for first-class contact visibility.
    if semantic_anchor:
        owner_candidates = []
        for term in term_payloads:
            payload = term.get("payload", {})
            owner = _safe_text(payload.get("owner_upn", ""))
            steward = _safe_text(payload.get("steward_upn", ""))
            if owner:
                owner_candidates.append(owner)
            if steward:
                owner_candidates.append(steward)
        owner_applied = False
        for owner in owner_candidates:
            owner_outcome, owner_details = _set_entity_owner(semantic_anchor["guid"], owner, token)
            if owner_outcome in ("assigned", "existing"):
                owner_applied = True
                print(f"Semantic-model owner update outcome: {owner_outcome} ({owner})")
                break
            if owner_details:
                print(f"[WARN] Semantic-model owner update failed for {owner}: {owner_details}")
        if not owner_applied and owner_candidates:
            print("[WARN] Could not apply owner/steward contact onto semantic-model anchor.")

    # G11-1 ontology fix: CDE entities have carried glossary_term_code as a flat
    # string attribute since nb_08 was first built, but were never assigned to
    # their parent glossary Term as a real Purview relationship (the CDE's own
    # Atlas entity never appeared in that Term's "assignedEntities" graph edge).
    # Resolve each CDE's real (server-assigned) GUID by qualifiedName and assign
    # it to its parent term using the same _assign_term_to_entity helper already
    # used below for bound-asset associations.
    def _find_entity_guid_by_qualified_name(type_name: str, qualified_name: str, auth_token: str) -> str:
        status, body = _request(
            "GET",
            f"/catalog/api/atlas/v2/entity/uniqueAttribute/type/{type_name}",
            auth_token,
            params={"attr:qualifiedName": qualified_name},
        )
        if status != 200:
            return ""
        try:
            payload = json.loads(body)
        except Exception:
            return ""
        return _safe_text((payload.get("entity") or {}).get("guid", ""))

    cde_term_attempts = 0
    cde_term_assigned = 0
    cde_term_existing = 0
    cde_term_skipped = 0
    cde_term_unresolved_entity = 0
    cde_term_unresolved_term = 0
    failed_cde_term_links = []
    for entity in cde_entities:
        attrs = entity["attributes"]
        cde_id = attrs["cde_id"]
        term_code = _safe_text(attrs.get("glossary_term_code", ""))
        if not term_code:
            continue

        term_guid = term_guid_by_code.get(term_code, "") or _resolve_glossary_term_guid(term_code, term_code, term_guid_index)
        if not term_guid:
            cde_term_unresolved_term += 1
            continue

        cde_entity_guid = _find_entity_guid_by_qualified_name("EnercareCriticalDataElement", attrs["qualifiedName"], token)
        if not cde_entity_guid:
            cde_term_unresolved_entity += 1
            continue

        cde_term_attempts += 1
        outcome, details = _assign_term_to_entity(term_guid, cde_entity_guid, token)
        if outcome == "assigned":
            cde_term_assigned += 1
        elif outcome == "existing":
            cde_term_existing += 1
        elif outcome == "skipped":
            cde_term_skipped += 1
        else:
            failed_cde_term_links.append((cde_id, term_code, details))

    print(
        "CDE-to-GlossaryTerm relationship summary: "
        f"attempted={cde_term_attempts} assigned={cde_term_assigned} existing={cde_term_existing} "
        f"skipped={cde_term_skipped} unresolved_entity={cde_term_unresolved_entity} "
        f"unresolved_term={cde_term_unresolved_term} failed={len(failed_cde_term_links)}"
    )
    if failed_cde_term_links:
        sample = failed_cde_term_links[0]
        raise RuntimeError(
            "CDE-to-GlossaryTerm relationship assignment completed with failures. "
            f"failed={len(failed_cde_term_links)} first_failure=({sample[0]}, {sample[1]}, {sample[2]})"
        )

    association_attempts = 0
    association_assigned = 0
    association_existing = 0
    association_skipped = 0
    unresolved_term_count = 0
    unresolved_asset_tokens = []
    failed_associations = []
    fallback_anchor_links = 0

    for term in term_payloads:
        term_code = term["term_code"]
        term_name = _safe_text(term["payload"].get("name", ""))
        term_guid = term_guid_by_code.get(term_code, "")
        if not term_guid:
            term_guid = _resolve_glossary_term_guid(term_name, term_code, term_guid_index)
            if term_guid:
                term_guid_by_code[term_code] = term_guid

        if not term_guid:
            unresolved_term_count += 1
            continue

        bound_tokens = term.get("bound_assets", [])
        if not bound_tokens:
            continue

        entity_guids = []
        seen_guids = set()
        for asset_token in bound_tokens:
            entity_guid = _resolve_asset_guid_for_token(asset_token, token, term_name=term_name)
            if entity_guid:
                if entity_guid not in seen_guids:
                    entity_guids.append(entity_guid)
                    seen_guids.add(entity_guid)
            else:
                if semantic_anchor and semantic_anchor.get("guid"):
                    anchor_guid = semantic_anchor["guid"]
                    if anchor_guid not in seen_guids:
                        entity_guids.append(anchor_guid)
                        seen_guids.add(anchor_guid)
                        fallback_anchor_links += 1
                elif len(unresolved_asset_tokens) < 25:
                    unresolved_asset_tokens.append(f"{term_code}:{asset_token}")

        for entity_guid in entity_guids:
            association_attempts += 1
            outcome, details = _assign_term_to_entity(term_guid, entity_guid, token)
            if outcome == "assigned":
                association_assigned += 1
            elif outcome == "existing":
                association_existing += 1
            elif outcome == "skipped":
                association_skipped += 1
            else:
                failed_associations.append((term_code, entity_guid, details))

    print(
        "Glossary association summary: "
        f"attempted={association_attempts} assigned={association_assigned} "
        f"existing={association_existing} skipped={association_skipped} unresolved_terms={unresolved_term_count} "
        f"unresolved_tokens={len(unresolved_asset_tokens)} anchor_fallback_links={fallback_anchor_links} "
        f"failed={len(failed_associations)}"
    )
    if unresolved_asset_tokens:
        print(f"Unresolved asset token samples: {unresolved_asset_tokens[:10]}")

    if failed_associations:
        sample = failed_associations[0]
        raise RuntimeError(
            "Glossary association completed with failures. "
            f"failed={len(failed_associations)} first_failure=({sample[0]}, {sample[1]}, {sample[2]})"
        )


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
PURVIEW_ACCOUNT_NAME = os.getenv("PURVIEW_ACCOUNT_NAME", "Purview-West3")
PURVIEW_API_BASE_URL = (
    os.getenv("PURVIEW_API_BASE_URL", "").strip()
    or os.getenv("PURVIEW_PRIVATE_ENDPOINT_URL", "").strip()
    or os.getenv("PURVIEW_PRIVATE_BASE_URL", "").strip()
)
PURVIEW_BASE_URL = (
    PURVIEW_API_BASE_URL.rstrip("/")
    if PURVIEW_API_BASE_URL
    else f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"
)
APPLY_CHANGES = True
SQL_MIRROR_ONLY_DEPLOYMENT = False
PURVIEW_PUBLISH_OVERRIDE = True
OUTPUT_ROOT = "/lakehouse/default/Files/purview_publish/phase_06_07_labels_lineage"
PURVIEW_HTTP_TIMEOUT_SECONDS = 60
MAX_ENTITY_RESOLUTION_SECONDS = 120
MAX_EDGES_TO_RESOLVE = 50
FAIL_ON_TOKEN_ACQUISITION_ERROR = False
TOKEN_RESOURCE_CANDIDATES = ["https://purview.azure.net"]
TOKEN_OUTER_RETRY_ATTEMPTS = 1
DISABLE_LIVE_PURVIEW_PUBLISH = False
TOKEN_ACQUISITION_MODE = "auto"  # auto | manual | azcli | tokenlibrary | devicecode
PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_TOKEN_CACHE_PATH = "Files/purview_publish/.purview_token_cache.json"
# Keep purge off for normal runs to reduce API round-trips and runtime.
# Enable only when you explicitly want a cleanup cycle.
PURGE_BEFORE_REWRITE = False
MANUAL_PURVIEW_BEARER_TOKEN = os.getenv("MANUAL_PURVIEW_BEARER_TOKEN", "").strip()
AZ_CLI_TIMEOUT_SECONDS = 15

WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
SQL_SOURCE_NAME = "ENERCARE-SQL-SOURCE"
FABRIC_SOURCE_NAME = "ENERCARE-FABRIC-SOURCE"
SEMANTIC_MODEL_NAME = "BrookfieldEnercare"
SEMANTIC_MODEL_LOGICAL_ID = "d19d7f14-ae22-9fde-462b-dafb983dfb0a"
SEMANTIC_DATASET_QUALIFIED_NAME = (
    "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/"
    "datasets/8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c"
)
SQL_SERVER_FQDN = "sqlserver-sk2wus3.database.windows.net"
MEASURE_ENTITY_TYPENAME = "EnercareSemanticMeasure"
EXPECTED_MEASURE_ASSET_REFS = [
    "BrookfieldEnercare/_Measures/FCR",
    "BrookfieldEnercare/_Measures/NPS",
    "BrookfieldEnercare/_Measures/CSAT",
    "BrookfieldEnercare/_Measures/AvgHandleTime",
    "BrookfieldEnercare/_Measures/RepeatComplaintRate",
]

print(f"Purview account: {PURVIEW_ACCOUNT_NAME}")
print(f"Apply changes: {APPLY_CHANGES}")
print(f"Output root: {OUTPUT_ROOT}")


def _log_nb09_diagnostic(stage: str, error: Exception):
    import traceback
    diag_row = {
        "stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error)[:4000],
        "traceback": traceback.format_exc()[:8000],
    }
    try:
        spark.createDataFrame([diag_row]).write.format("delta").mode("append").saveAsTable("nb09_diagnostics_log")
        print(f"[DIAG] Logged failure at stage '{stage}' to nb09_diagnostics_log")
    except Exception as log_ex:
        print(f"[DIAG] Could not log diagnostic for stage '{stage}': {log_ex}")
        print(f"[DIAG] Original error at stage '{stage}': {type(error).__name__}: {error}")
        print(traceback.format_exc())


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

import os
os.environ["MANUAL_PURVIEW_BEARER_TOKEN"] = ""
MANUAL_PURVIEW_BEARER_TOKEN = os.environ.get("MANUAL_PURVIEW_BEARER_TOKEN", "").strip()

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
            # Spark's catalog can cache a stale schema (e.g. a dropped/renamed column,
            # or a schema seen by another notebook sharing this warm pool/session)
            # across notebook runs; refresh before reading to avoid collectToPython
            # mismatches. Same fix validated in nb_08_purview_glossary_cde.
            try:
                spark.catalog.refreshTable(candidate)
            except Exception:
                pass
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex
    if required:
        raise RuntimeError(f"Could not resolve table '{table_name}'. Last error: {last_error}")
    return None, None


# Columns actually read further down (Cells 3/4). Pruning to this set avoids
# collectToPython/IllegalStateException failures when a Delta table's cached
# schema has stale/unmaterialized columns (e.g. a schema-declared column from
# another notebook's write that this session's cached plan still references
# but the current data doesn't have). Same fix validated in nb_08.
CDE_COLUMNS_NEEDED = [
    "sensitivity_label", "cde_id", "cde_code", "cde_name", "parent_glossary_term",
    "owner_role", "business_definition", "bound_columns",
]
LABELS_COLUMNS_NEEDED = [
    "label_name", "protection_policy", "sensitivity_tier", "applies_to_asset_ids",
    "enforcement_target", "assignment_rule", "label_id",
]
GLOSSARY_COLUMNS_NEEDED = [
    "term_code", "term_name", "name", "definition", "bound_assets", "applies_to_asset_ids",
]
DATA_PRODUCTS_COLUMNS_NEEDED = [
    "data_product_id", "product_id", "attached_assets", "data_product_name",
    "product_name", "sql_assets", "fabric_assets", "semantic_model_assets",
]


def _prune_columns(df, needed_columns):
    if df is None:
        return None
    available = {c.lower(): c for c in df.columns}
    select_cols = [available[c] for c in needed_columns if c in available]
    if not select_cols:
        return df
    return df.select(*select_cols)


try:
    cde_df, cde_source = _read_table("cdes")
    labels_df, labels_source = _read_table("label_assignments", required=False)
    glossary_df, glossary_source = _read_table("glossary_terms", required=False)
    data_products_df, data_products_source = _read_table("data_products")

    cde_df = _prune_columns(cde_df, CDE_COLUMNS_NEEDED)
    labels_df = _prune_columns(labels_df, LABELS_COLUMNS_NEEDED)
    glossary_df = _prune_columns(glossary_df, GLOSSARY_COLUMNS_NEEDED)
    data_products_df = _prune_columns(data_products_df, DATA_PRODUCTS_COLUMNS_NEEDED)

    if labels_df is None:
        print("[WARN] metadata.label_assignments not found; label rules will be inferred from CDE values when possible.")

    print(f"cdes rows: {cde_df.count()} (source={cde_source})")
    if labels_df is not None:
        print(f"label_assignments rows: {labels_df.count()} (source={labels_source})")
    if glossary_df is not None:
        print(f"glossary_terms rows: {glossary_df.count()} (source={glossary_source})")
    print(f"data_products rows: {data_products_df.count()} (source={data_products_source})")
except Exception as ex:
    _log_nb09_diagnostic("cell2_read_validate", ex)
    raise

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


def _is_probable_asset_ref(token: str) -> bool:
    text = _safe_text(token)
    if not text:
        return False

    lower = text.lower()
    if lower.startswith(("dbo.", "mssql://", "lh_", "fabric://")):
        return True
    if text.startswith("BrookfieldEnercare/") or text.startswith("BrookfieldEnercare."):
        return True
    if lower.startswith("dp-") and ":overview" in lower:
        return True
    return False


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

data_product_anchor_asset = {}
semantic_asset_candidates = []
for row in data_products_df.collect():
    dp_id = _safe_text(getattr(row, "data_product_id", None) or getattr(row, "product_id", None)).upper()
    attached_assets = _split_tokens(getattr(row, "attached_assets", None))

    anchor = ""
    for token in attached_assets:
        if _safe_text(token).lower().startswith(("dbo.", "mssql://")):
            anchor = _safe_text(token)
            break
    if not anchor and attached_assets:
        anchor = _safe_text(attached_assets[0])

    if dp_id and anchor:
        data_product_anchor_asset[dp_id] = anchor

    for token in attached_assets:
        t = _safe_text(token)
        if t.startswith("BrookfieldEnercare/"):
            semantic_asset_candidates.append(t)

default_semantic_asset = semantic_asset_candidates[0] if semantic_asset_candidates else "dbo.customers"


def _normalize_asset_token(token: str):
    raw = _safe_text(token)
    if not raw:
        return "", "empty"

    lower = raw.lower()

    if lower.startswith("dp-") and ":overview" in lower:
        dp_id = raw.split(":", 1)[0].strip().upper()
        mapped = _safe_text(data_product_anchor_asset.get(dp_id, ""))
        if mapped:
            return mapped, "dp_overview_to_anchor"
        return "", "dp_overview_unmapped"

    if raw in {"BrookfieldEnercare.Report", "BrookfieldEnercare.SemanticModel"}:
        return default_semantic_asset, "fabric_item_to_anchor"

    if raw.startswith("BrookfieldEnercare/_Measures/"):
        return raw, "semantic_measure_ref"

    if lower.startswith("lh_metadata."):
        return "dbo.data_owners_directory", "metadata_lakehouse_to_sql_anchor"

    if not _is_probable_asset_ref(raw):
        return "", "non_asset_metadata"

    return raw, "as_is"


def _normalize_asset_tokens(raw_value):
    normalized = []
    reasons = []
    for token in _split_tokens(raw_value):
        mapped, reason = _normalize_asset_token(token)
        reasons.append(reason)
        if mapped:
            normalized.append(mapped)
    deduped = []
    seen = set()
    for token in normalized:
        key = token.lower()
        if key not in seen:
            deduped.append(token)
            seen.add(key)
    return deduped, reasons


token_normalization_counts = {}


def _track_token_reasons(reasons):
    for reason in reasons:
        token_normalization_counts[reason] = token_normalization_counts.get(reason, 0) + 1


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

    tokens, reasons = _normalize_asset_tokens(getattr(row, "bound_columns", None))
    _track_token_reasons(reasons)
    for token in tokens:
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
        tokens, reasons = _normalize_asset_tokens(assets)
        _track_token_reasons(reasons)
        for token in tokens:
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
            tokens, reasons = _normalize_asset_tokens(getattr(row, glossary_bound_assets_col, None))
            _track_token_reasons(reasons)
            for token in tokens:
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


def _measure_slug(name: str):
    text = _safe_text(name)
    if not text:
        return ""
    lowered = text.lower()
    clean_chars = [ch if ch.isalnum() else "_" for ch in lowered]
    slug = "".join(clean_chars)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _measure_entity_qn(asset_ref: str):
    text = _safe_text(asset_ref)
    if not text.startswith(f"{SEMANTIC_MODEL_NAME}/_Measures/"):
        return ""
    measure_name = _safe_text(text.split("/")[-1])
    slug = _measure_slug(measure_name)
    if not slug:
        return ""
    return f"enercare://semantic/{SEMANTIC_MODEL_NAME.lower()}/measure/{slug}"


measure_entity_manifest = []
measure_seen = set()
for manifest_row in sensitivity_label_manifest + classification_manifest + glossary_term_manifest + asset_description_manifest:
    asset_ref = _safe_text(manifest_row.get("asset_ref", ""))
    qn = _measure_entity_qn(asset_ref)
    if not qn:
        continue

    key = qn.lower()
    if key in measure_seen:
        continue
    measure_seen.add(key)

    measure_name = _safe_text(asset_ref.split("/")[-1])
    measure_entity_manifest.append(
        {
            "asset_ref": asset_ref,
            "measure_name": measure_name,
            "qualified_name": qn,
            "semantic_model_name": SEMANTIC_MODEL_NAME,
        }
    )

for asset_ref in EXPECTED_MEASURE_ASSET_REFS:
    qn = _measure_entity_qn(asset_ref)
    if not qn:
        continue
    key = qn.lower()
    if key in measure_seen:
        continue
    measure_seen.add(key)
    measure_entity_manifest.append(
        {
            "asset_ref": asset_ref,
            "measure_name": _safe_text(asset_ref.split("/")[-1]),
            "qualified_name": qn,
            "semantic_model_name": SEMANTIC_MODEL_NAME,
            "assignment_source": "ExpectedCoreMeasures",
        }
    )

print(f"Classification defs prepared: {len(classification_defs)}")
print(f"Sensitivity label rows prepared: {len(sensitivity_label_manifest)}")
print(f"CDE manifest rows prepared: {len(cde_classification_manifest)}")
print(f"Classification manifest rows prepared: {len(classification_manifest)}")
print(f"Glossary term rows prepared: {len(glossary_term_manifest)}")
print(f"Asset description rows prepared: {len(asset_description_manifest)}")
print(f"Measure entity rows prepared: {len(measure_entity_manifest)}")
if token_normalization_counts:
    print("Token normalization summary:")
    for reason in sorted(token_normalization_counts.keys()):
        print(f" - {reason}: {token_normalization_counts[reason]}")
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


def _canonical_sql_qname(raw_qn: str):
    qn = _safe_text(raw_qn)
    if not qn or not qn.lower().startswith("mssql://"):
        return qn
    if qn.lower().startswith("mssql://" + SQL_SERVER_FQDN.lower()):
        return qn
    if qn.lower().startswith("mssql://sqldemo/"):
        suffix = qn[len("mssql://sqldemo/") :]
        return f"mssql://{SQL_SERVER_FQDN}/sqldemo/{suffix}"
    return qn


def _canonical_fabric_qname(raw_qn: str):
    qn = _safe_text(raw_qn)
    if not qn:
        return qn
    lowered = qn.lower()
    if lowered.startswith("fabric://"):
        suffix = qn[len("fabric://") :]
        if "/lakehouses/" in suffix:
            lakehouse_prefix, table_name = suffix.split("/lakehouses/", 1)
            if "/tables/" in table_name:
                lakehouse_name, table_part = table_name.split("/tables/", 1)
                if lakehouse_name.lower() == "lh_enercare_demo":
                    return f"https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/{table_part}"
                return f"https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/lakehouses/{lakehouse_name}/tables/{table_part}"
        if "/tables/" in suffix:
            lakehouse_name, table_name = suffix.split("/tables/", 1)
            return f"https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/lakehouses/{lakehouse_name}/tables/{table_name}"
    if lowered.startswith("https://app.fabric.microsoft.com/"):
        return qn
    return qn


def _table_ref_from_sql_asset(asset_ref: str):
    parts = asset_ref.split(".")
    if len(parts) >= 2 and parts[0].lower() == "dbo":
        qn = f"mssql://{SQL_SERVER_FQDN}/sqldemo/dbo/{parts[1]}"
        return _canonical_sql_qname(qn)
    return None


def _fabric_ref_from_asset(asset_ref: str):
    if asset_ref.startswith("lh_enercare_demo."):
        _, table_name = asset_ref.split(".", 1)
        return f"https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/{table_name}"
    if asset_ref.startswith(f"{SEMANTIC_MODEL_NAME}/"):
        asset_name = asset_ref.split('/', 1)[1]
        return f"https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/{asset_name}"
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
mssparkutils.fs.put(f"{output_root}/measure_entity_manifest.json", json.dumps(measure_entity_manifest, indent=2), True)
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
    ("measure_entity_rows", len(measure_entity_manifest), "PASS" if measure_entity_manifest else "WARN"),
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


def _is_column_asset_ref(asset_ref: str) -> bool:
    raw = _safe_text(asset_ref)
    if not raw:
        return False

    lower = raw.lower()
    if lower.startswith("mssql://") and "#" in raw:
        return True

    if lower.startswith("dbo."):
        parts = raw.split(".")
        return len(parts) >= 3

    return False


def _is_measure_asset_ref(asset_ref: str):
    text = _safe_text(asset_ref)
    return text.startswith(f"{SEMANTIC_MODEL_NAME}/_Measures/")


def _measure_asset_name(asset_ref: str):
    if not _is_measure_asset_ref(asset_ref):
        return ""
    return _safe_text(asset_ref.split("/")[-1])


def _measure_entity_qualified_name(asset_ref: str):
    if not _is_measure_asset_ref(asset_ref):
        return ""
    measure_name = _measure_asset_name(asset_ref)
    slug = _measure_slug(measure_name)
    if not slug:
        return ""
    return f"enercare://semantic/{SEMANTIC_MODEL_NAME.lower()}/measure/{slug}"


def _build_measure_entity_type_def():
    return {
        "category": "ENTITY",
        "name": MEASURE_ENTITY_TYPENAME,
        "description": "Semantic model measure used for governance linkage in Purview.",
        "superTypes": ["Referenceable"],
        "attributeDefs": [
            {"name": "semanticModelName", "typeName": "string", "isOptional": False},
            {"name": "semanticModelGuid", "typeName": "string", "isOptional": True},
            {"name": "sourceAssetRef", "typeName": "string", "isOptional": True},
            {"name": "datasetQualifiedName", "typeName": "string", "isOptional": True},
        ],
    }


def _resolve_semantic_dataset_qualified_name(token: str):
    explicit_qn = _safe_text(SEMANTIC_DATASET_QUALIFIED_NAME)
    if explicit_qn:
        return explicit_qn

    status, body = _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": SEMANTIC_MODEL_NAME, "limit": 25},
        params={"api-version": "2023-09-01"},
    )
    if status != 200:
        return ""

    try:
        payload = json.loads(body)
    except Exception:
        return ""

    for entity in payload.get("value") or []:
        entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
        qn = _safe_text(entity.get("qualifiedName", ""))
        name = _safe_text(entity.get("name", ""))
        if (
            qn
            and name.lower() == SEMANTIC_MODEL_NAME.lower()
            and entity_type in {"powerbi_dataset", "fabric_semantic_model", "powerbi_semantic_model"}
        ):
            return qn

    return ""


def _resolve_semantic_model_anchor(token: str):
    dataset_qn = _resolve_semantic_dataset_qualified_name(token)
    if dataset_qn:
        entity = _find_entity_by_qualified_name(token, dataset_qn)
        if entity:
            return {
                "guid": _safe_text(entity.get("guid", "")),
                "entityType": _safe_text(entity.get("typeName", "") or entity.get("entityType", "")).lower(),
                "qualifiedName": _safe_text(entity.get("qualifiedName", "") or dataset_qn),
            }

    status, body = _request(
        "POST",
        "/datamap/api/search/query",
        token,
        body={"keywords": SEMANTIC_MODEL_NAME, "limit": 25},
        params={"api-version": "2023-09-01"},
    )
    if status != 200:
        return None

    try:
        payload = json.loads(body)
    except Exception:
        return None

    best = None
    best_score = 0
    for entity in payload.get("value") or []:
        guid = _safe_text(entity.get("id", "") or entity.get("guid", ""))
        if not guid:
            continue

        name = _safe_text(entity.get("name", ""))
        qn = _safe_text(entity.get("qualifiedName", ""))
        entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()

        score = 0
        if name.lower() == SEMANTIC_MODEL_NAME.lower():
            score += 8
        if SEMANTIC_MODEL_NAME.lower() in qn.lower():
            score += 4
        if entity_type in {"powerbi_dataset", "fabric_semantic_model", "powerbi_semantic_model"}:
            score += 8
        elif "semantic" in entity_type or "dataset" in entity_type:
            score += 4

        if score > best_score:
            best_score = score
            best = {
                "guid": guid,
                "entityType": entity_type,
                "qualifiedName": qn,
            }

    return best if best_score > 0 else None


def _publish_measure_entities(token: str, measure_rows):
    stats = {"created": 0, "existing": 0, "failed": 0}
    resolution_map = {}
    if not measure_rows:
        return stats, resolution_map

    dataset_qn = _resolve_semantic_dataset_qualified_name(token)
    dataset_guid = ""
    dataset_type = ""
    if dataset_qn:
        dataset_entity = _find_entity_by_qualified_name(token, dataset_qn)
        if dataset_entity:
            dataset_guid = _safe_text(dataset_entity.get("guid", ""))
            dataset_type = _safe_text(dataset_entity.get("typeName", ""))
    if dataset_qn:
        print(f"[Cell 6] Semantic dataset anchor resolved: {dataset_qn}")
    else:
        print("[Cell 6][WARN] Semantic dataset anchor not found; publishing measure entities without datasetQualifiedName.")

    for row in measure_rows:
        asset_ref = _safe_text(row.get("asset_ref", ""))
        measure_name = _safe_text(row.get("measure_name", ""))
        qn = _safe_text(row.get("qualified_name", "")) or _measure_entity_qualified_name(asset_ref)
        if not asset_ref or not measure_name or not qn:
            continue

        existing = _find_entity_by_qualified_name(token, qn)
        if existing:
            stats["existing"] += 1
            resolution_map[asset_ref.lower()] = {
                "guid": _safe_text(existing.get("guid", "")),
                "entityType": _safe_text(existing.get("typeName", "") or MEASURE_ENTITY_TYPENAME).lower(),
                "qualifiedName": qn,
                "semanticModelGuid": dataset_guid,
                "semanticModelType": _safe_text(dataset_type).lower(),
                "semanticModelQualifiedName": dataset_qn,
            }
            continue

        payload = {
            "entities": [
                {
                    "typeName": MEASURE_ENTITY_TYPENAME,
                    "attributes": {
                        "qualifiedName": qn,
                        "name": measure_name,
                        "semanticModelName": SEMANTIC_MODEL_NAME,
                        "semanticModelGuid": dataset_guid,
                        "sourceAssetRef": asset_ref,
                        "datasetQualifiedName": dataset_qn,
                        "description": f"Semantic measure governance entity for {SEMANTIC_MODEL_NAME}/{measure_name}",
                    },
                }
            ]
        }
        status, body = _post_json("/catalog/api/atlas/v2/entity/bulk", token, payload)
        if status not in (200, 201):
            body_lower = _safe_text(body).lower()
            if "already exists" not in body_lower and "atlas-409" not in body_lower:
                stats["failed"] += 1
                continue

        refreshed = _find_entity_by_qualified_name(token, qn)
        if refreshed:
            stats["created"] += 1
            resolution_map[asset_ref.lower()] = {
                "guid": _safe_text(refreshed.get("guid", "")),
                "entityType": _safe_text(refreshed.get("typeName", "") or MEASURE_ENTITY_TYPENAME).lower(),
                "qualifiedName": qn,
                "semanticModelGuid": dataset_guid,
                "semanticModelType": _safe_text(dataset_type).lower(),
                "semanticModelQualifiedName": dataset_qn,
            }
        else:
            stats["failed"] += 1

    return stats, resolution_map


def _resolve_asset_for_classification(token: str, asset_ref: str):
    measure_qn = _measure_entity_qualified_name(asset_ref)
    if measure_qn:
        exact = _find_entity_by_qualified_name(token, measure_qn)
        if exact:
            return {
                "guid": _safe_text(exact.get("guid", "")),
                "entityType": _safe_text(exact.get("typeName", "") or MEASURE_ENTITY_TYPENAME).lower(),
                "qualifiedName": _safe_text(exact.get("qualifiedName", "") or measure_qn),
            }

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
    if explicit_table_qn and not explicit_column_qn:
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

            if explicit_column_qn and "column" not in entity_type and "#" not in qn:
                # For column asset refs, avoid resolving to table-level entities unless no column-like candidate exists.
                continue

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


def _resolve_semantic_model_field_targets(token: str, asset_ref: str, limit: int = 5):
    asset_text = _safe_text(asset_ref)
    if not asset_text:
        return []

    parsed_column_name = ""
    parsed_table_name = ""
    parts = asset_text.split(".")
    if asset_text.lower().startswith("dbo.") and len(parts) >= 3:
        parsed_table_name = _safe_text(parts[1])
        parsed_column_name = _safe_text(".".join(parts[2:]))

    query_candidates = []
    if parsed_column_name:
        query_candidates.extend(
            [
                f"{SEMANTIC_MODEL_NAME} {parsed_column_name}",
                parsed_column_name,
                f"{parsed_table_name} {parsed_column_name}" if parsed_table_name else "",
            ]
        )
    else:
        query_candidates.extend([f"{SEMANTIC_MODEL_NAME} {asset_text}", asset_text])

    dataset_qn_cache_key = "_semantic_dataset_anchor_qn_cache"
    dataset_qn = _safe_text(globals().get(dataset_qn_cache_key, ""))
    if not dataset_qn:
        dataset_qn = _safe_text(_resolve_semantic_dataset_qualified_name(token))
        globals()[dataset_qn_cache_key] = dataset_qn

    dataset_qn_lower = dataset_qn.lower()
    dataset_id = ""
    if "/datasets/" in dataset_qn_lower:
        try:
            dataset_id = dataset_qn_lower.split("/datasets/", 1)[1].split("/", 1)[0]
        except Exception:
            dataset_id = ""

    if dataset_id and parsed_column_name:
        query_candidates.extend(
            [
                f"{dataset_id} {parsed_column_name}",
                f"datasets/{dataset_id} {parsed_column_name}",
            ]
        )

    def _norm_text(value: str):
        return "".join(ch for ch in _safe_text(value).lower() if ch.isalnum())

    parsed_column_norm = _norm_text(parsed_column_name)

    seen_queries = set()
    targets = []
    seen_guids = set()
    for query in query_candidates:
        q = _safe_text(query)
        if not q or q.lower() in seen_queries:
            continue
        seen_queries.add(q.lower())

        status, body = _request(
            "POST",
            "/datamap/api/search/query",
            token,
            body={"keywords": q, "limit": 50},
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
            if not guid or guid in seen_guids:
                continue

            entity_type = _safe_text(entity.get("entityType", "") or entity.get("typeName", "")).lower()
            qn = _safe_text(entity.get("qualifiedName", ""))
            name = _safe_text(entity.get("name", ""))
            qn_lower = qn.lower()

            # Keep entities from either semantic-model qn paths or dataset qn paths.
            is_semantic_model_path = "semanticmodels" in qn_lower and SEMANTIC_MODEL_NAME.lower() in qn_lower
            is_dataset_path = bool(dataset_qn_lower and dataset_qn_lower in qn_lower)
            is_dataset_id_path = bool(dataset_id and f"/datasets/{dataset_id}" in qn_lower)
            if not (is_semantic_model_path or is_dataset_path or is_dataset_id_path):
                continue

            # Focus on field-level entities where schema grid renders metadata.
            if "column" not in entity_type and parsed_column_name:
                if _norm_text(name) != parsed_column_norm:
                    continue

            if parsed_column_name and _norm_text(name) != parsed_column_norm:
                if parsed_column_norm not in _norm_text(qn):
                    continue

            seen_guids.add(guid)
            targets.append(
                {
                    "guid": guid,
                    "entityType": entity_type,
                    "qualifiedName": qn,
                }
            )

            if len(targets) >= limit:
                return targets

    return targets


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


def _get_purview_token_from_shared_cache() -> str:
    # Cache is shared (via lakehouse Files) across nb_07/nb_08/nb_09 sessions so a
    # sign-in done in one notebook doesn't have to be repeated in the others.
    cache_path = PURVIEW_TOKEN_CACHE_PATH  # NameError here means Cell 1 wasn't run
    try:
        raw = mssparkutils.fs.head(cache_path, 65536)
        cached = json.loads(raw)
        token = _safe_text(cached.get("access_token", ""))
        expires_on = float(cached.get("expires_on", 0))
    except Exception:
        raise RuntimeError("No valid shared Purview token cache found.")
    if not token or expires_on <= time.time() + 120:
        raise RuntimeError("Shared Purview token cache is empty or expired.")
    print("[Cell 6] Reusing cached Purview token acquired from another notebook/session.")
    return token


def _write_purview_token_to_shared_cache(token: str, expires_on: float):
    try:
        mssparkutils.fs.mkdirs("Files/purview_publish")
        mssparkutils.fs.put(
            PURVIEW_TOKEN_CACHE_PATH,
            json.dumps({"access_token": token, "expires_on": expires_on}),
            True,
        )
    except Exception as exc:
        print(f"[Cell 6][WARN] Could not write shared Purview token cache: {exc}")


def _get_purview_token_via_device_code() -> str:
    try:
        from azure.identity import DeviceCodeCredential
    except ImportError:
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "azure-identity"], check=True)
        from azure.identity import DeviceCodeCredential

    def _print_device_code(verification_uri, user_code, expires_on):
        print(f"[Cell 6] Open {verification_uri} in any browser and enter code: {user_code}")

    credential = DeviceCodeCredential(
        client_id="04b07795-8ddb-461a-bbee-02f9e1bf7b46",
        tenant_id=PURVIEW_TENANT_ID,
        prompt_callback=_print_device_code,
    )
    result = credential.get_token("https://purview.azure.net/.default")
    _write_purview_token_to_shared_cache(result.token, result.expires_on)
    print("[Cell 6] Acquired Purview token via device-code sign-in.")
    return result.token


def _get_purview_token_with_retry() -> str:
    mode = _safe_text(globals().get("TOKEN_ACQUISITION_MODE", "auto")).lower()
    if mode not in {"auto", "manual", "azcli", "tokenlibrary", "devicecode"}:
        raise RuntimeError(f"Unsupported TOKEN_ACQUISITION_MODE='{mode}'. Use auto, manual, azcli, tokenlibrary, or devicecode.")

    if mode == "manual":
        return _get_purview_token_from_manual()

    if mode == "azcli":
        return _get_purview_token_via_az_cli()

    if mode == "tokenlibrary":
        return _get_purview_token_via_tokenlibrary()

    if mode == "devicecode":
        return _get_purview_token_via_device_code()

    # auto mode: prefer the shared cache, then manual token, then Azure CLI, then
    # TokenLibrary, and finally an interactive device-code sign-in as last resort.
    try:
        return _get_purview_token_from_shared_cache()
    except Exception as cache_ex:
        print(f"[Cell 6][WARN] Shared token cache unavailable; trying manual token. Error: {cache_ex}")

    try:
        return _get_purview_token_from_manual()
    except Exception as manual_ex:
        print(f"[Cell 6][WARN] Manual token path unavailable; trying Azure CLI. Error: {manual_ex}")

    try:
        return _get_purview_token_via_az_cli()
    except Exception as az_ex:
        print(f"[Cell 6][WARN] Azure CLI token path failed; trying TokenLibrary. Error: {az_ex}")

    try:
        return _get_purview_token_via_tokenlibrary()
    except Exception as tl_ex:
        print(f"[Cell 6][WARN] TokenLibrary path failed; starting device-code sign-in. Error: {tl_ex}")
        return _get_purview_token_via_device_code()


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
    for fn in (_get_purview_token_from_shared_cache, _get_purview_token_via_az_cli, _get_purview_token_via_tokenlibrary, _get_purview_token_via_device_code):
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
            host = parts[0]
            db_name = parts[1]
            schema_name = parts[2]
            table_name = parts[3] if len(parts) >= 4 else ""
            if table_name:
                candidates.append(f"mssql://{SQL_SERVER_FQDN}/{db_name}/{schema_name}/{table_name}")
                if schema_name.lower() == "dbo":
                    candidates.append(f"mssql://{SQL_SERVER_FQDN}/{db_name}/demo/{table_name}")
                    candidates.append(f"mssql://{db_name}/demo/{table_name}")

    if role == "target":
        canon_qn = _canonical_fabric_qname(qn)
        if canon_qn != qn:
            candidates.append(canon_qn)
        if qn.startswith("fabric://") and "/semanticModels/" in qn:
            parts = qn.split("/")
            if len(parts) >= 6:
                workspace_id = parts[2]
                asset_name = parts[-1]
                candidates.append(f"fabric://{workspace_id}/semanticModels/{SEMANTIC_MODEL_LOGICAL_ID}/{asset_name}")
                candidates.append(f"fabric://{workspace_id}/semanticModels/{SEMANTIC_MODEL_NAME}/{asset_name}")
        if qn.startswith("https://app.fabric.microsoft.com/"):
            candidates.append(qn.replace("/lakehouses/" + qn.split("/lakehouses/",1)[1].split("/tables/",1)[0], "/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555"))

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

if DISABLE_LIVE_PURVIEW_PUBLISH:
    print("[DRY RUN] DISABLE_LIVE_PURVIEW_PUBLISH=True. Skipping token acquisition and Purview API calls.")
elif not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
elif SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE:
    print("[GUARD] SQL-mirror-only deployment is active. Set PURVIEW_PUBLISH_OVERRIDE=True for live Purview publish.")
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

        measure_resolution_map = {}
        semantic_anchor = _resolve_semantic_model_anchor(token)
        if semantic_anchor:
            print(
                "[Cell 6] Semantic-model anchor resolved for first-class metadata attachment: "
                f"{semantic_anchor.get('qualifiedName', '')} ({semantic_anchor.get('guid', '')})"
            )
        else:
            print("[Cell 6][WARN] Semantic-model anchor not resolved; metadata will only attach to resolved source assets.")

        if measure_entity_manifest:
            print(f"[Cell 6] Publishing semantic measure typedef ({MEASURE_ENTITY_TYPENAME})...")
            measure_typedef_payload = {"entityDefs": [_build_measure_entity_type_def()]}
            measure_type_status, measure_type_body = _post_json("/catalog/api/atlas/v2/types/typedefs", token, measure_typedef_payload)
            if measure_type_status not in (200, 201):
                body_lower = _safe_text(measure_type_body).lower()
                if (
                    "already exists" in body_lower
                    or "atlas-409" in body_lower
                    or measure_type_status == 409
                ):
                    print(f"[Cell 6] Measure typedef already exists (HTTP {measure_type_status}).")
                else:
                    print(
                        f"[Cell 6][WARN] Measure typedef publish failed: HTTP {measure_type_status} | "
                        f"{_safe_text(measure_type_body)[:220]}"
                    )
            else:
                print(f"[Cell 6] Measure typedef publish result: HTTP {measure_type_status}")

            print(f"[Cell 6] Publishing semantic measure entities from manifest ({len(measure_entity_manifest)} rows)...")
            measure_stats, measure_resolution_map = _publish_measure_entities(token, measure_entity_manifest)
            print(
                "[Cell 6] Semantic measure entity summary: "
                f"created={measure_stats['created']} existing={measure_stats['existing']} failed={measure_stats['failed']}"
            )
        else:
            print("[Cell 6] No semantic measure entities to publish from manifest.")

        asset_resolution_cache = {}

        def _resolve_asset_cached(asset_ref: str):
            key = _safe_text(asset_ref).lower()
            if not key:
                return None
            if key in measure_resolution_map:
                return measure_resolution_map[key]
            if key not in asset_resolution_cache:
                asset_resolution_cache[key] = _resolve_asset_for_classification(token, asset_ref)
            return asset_resolution_cache[key]

        print("[Cell 6] Applying sensitivity labels from manifest...")
        label_assigned = 0
        label_existing = 0
        label_failed = []
        label_unresolved = []
        anchor_label_assigned = 0
        anchor_label_existing = 0
        anchor_label_failed = []

        label_dedupe = set()
        label_rows = []
        anchor_label_dedupe = set()
        semantic_field_label_assigned = 0
        semantic_field_label_existing = 0
        semantic_field_label_failed = []
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
            anchor_label_dedupe.add(label_name.lower())

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
                resolved = _resolve_asset_cached(asset_ref)
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

            resolved = _resolve_asset_cached(asset_ref)
            semantic_field_targets = _resolve_semantic_model_field_targets(token, asset_ref)
            target_entities = []
            seen_target_guids = set()
            if resolved:
                target_entities.append(resolved)
                seen_target_guids.add(_safe_text(resolved.get("guid", "")))
            for semantic_target in semantic_field_targets:
                semantic_guid = _safe_text(semantic_target.get("guid", ""))
                if semantic_guid and semantic_guid not in seen_target_guids:
                    target_entities.append(semantic_target)
                    seen_target_guids.add(semantic_guid)
            if not target_entities and semantic_anchor:
                target_entities.append(semantic_anchor)

            if not target_entities:
                if len(label_unresolved) < 25:
                    label_unresolved.append(asset_ref)
                continue

            primary_guid = _safe_text(target_entities[0].get("guid", ""))
            for target in target_entities:
                outcome, details = _apply_sensitivity_label(token, target["guid"], label_name)
                target_guid = _safe_text(target.get("guid", ""))
                if target_guid == primary_guid:
                    if outcome == "assigned":
                        label_assigned += 1
                    elif outcome == "existing":
                        label_existing += 1
                    else:
                        label_failed.append((asset_ref, label_name, details))
                else:
                    if outcome == "assigned":
                        semantic_field_label_assigned += 1
                    elif outcome == "existing":
                        semantic_field_label_existing += 1
                    else:
                        semantic_field_label_failed.append((asset_ref, label_name, details))

        if semantic_anchor:
            for label_name_lower in sorted(anchor_label_dedupe):
                outcome, details = _apply_sensitivity_label(token, semantic_anchor["guid"], label_name_lower)
                if outcome == "assigned":
                    anchor_label_assigned += 1
                elif outcome == "existing":
                    anchor_label_existing += 1
                else:
                    anchor_label_failed.append((label_name_lower, details))

        print(
            "[Cell 6] Sensitivity label summary: "
            f"assigned={label_assigned} existing={label_existing} "
            f"unresolved={len(label_unresolved)} failed={len(label_failed)} "
            f"anchor_assigned={anchor_label_assigned} anchor_existing={anchor_label_existing} "
            f"anchor_failed={len(anchor_label_failed)} "
            f"semantic_field_assigned={semantic_field_label_assigned} "
            f"semantic_field_existing={semantic_field_label_existing} "
            f"semantic_field_failed={len(semantic_field_label_failed)}"
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
        anchor_classification_assigned = 0
        anchor_classification_existing = 0
        anchor_classification_failed = []

        dedupe = set()
        classification_rows = []
        anchor_classification_dedupe = set()
        semantic_field_class_assigned = 0
        semantic_field_class_existing = 0
        semantic_field_class_failed = []
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
            # Keep canonical classification casing for Atlas typeName matching.
            anchor_classification_dedupe.add((classification_name, cde_id, cde_name, assignment_source, rule))

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
                resolved = _resolve_asset_cached(asset_ref)
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
            column_asset_ref = _is_column_asset_ref(asset_ref)

            if index == 1 or index % 10 == 0 or index == total_classification_rows:
                print(
                    f"[Cell 6] CDE classification progress: {index}/{total_classification_rows} | "
                    f"assigned={classification_assigned} existing={classification_existing} "
                    f"unresolved={len(classification_unresolved)} failed={len(classification_failed)}"
                )

            resolved = _resolve_asset_cached(asset_ref)
            semantic_field_targets = _resolve_semantic_model_field_targets(token, asset_ref)
            target_entities = []
            seen_target_guids = set()

            # For column-like refs, prioritize semantic field entities so schema grid fields are updated first.
            for semantic_target in semantic_field_targets:
                semantic_guid = _safe_text(semantic_target.get("guid", ""))
                if semantic_guid and semantic_guid not in seen_target_guids:
                    target_entities.append(semantic_target)
                    seen_target_guids.add(semantic_guid)

            if resolved:
                resolved_guid = _safe_text(resolved.get("guid", ""))
                resolved_type = _safe_text(resolved.get("entityType", "")).lower()
                include_resolved = True
                if column_asset_ref and "column" not in resolved_type and semantic_field_targets:
                    # Avoid counting table-level binds as success when a field target was found.
                    include_resolved = False
                if include_resolved and resolved_guid and resolved_guid not in seen_target_guids:
                    target_entities.append(resolved)
                    seen_target_guids.add(resolved_guid)

            if not target_entities and semantic_anchor:
                target_entities.append(semantic_anchor)
            if not target_entities:
                if len(classification_unresolved) < 25:
                    classification_unresolved.append(asset_ref)
                continue

            primary_guid = _safe_text(target_entities[0].get("guid", ""))
            for target in target_entities:
                outcome, details = _apply_classification(
                    token,
                    target["guid"],
                    classification_name,
                    "",
                    assignment_source,
                    rule,
                    cde_id=cde_id,
                    cde_name=cde_name,
                )

                target_guid = _safe_text(target.get("guid", ""))
                if target_guid == primary_guid:
                    if outcome == "assigned":
                        classification_assigned += 1
                    elif outcome == "existing":
                        classification_existing += 1
                    else:
                        classification_failed.append((asset_ref, classification_name, details))
                else:
                    if outcome == "assigned":
                        semantic_field_class_assigned += 1
                    elif outcome == "existing":
                        semantic_field_class_existing += 1
                    else:
                        semantic_field_class_failed.append((asset_ref, classification_name, details))

        if semantic_anchor:
            for class_key in sorted(anchor_classification_dedupe):
                class_name = class_key[0]
                class_cde_id = class_key[1]
                class_cde_name = class_key[2]
                class_assignment_source = class_key[3]
                class_rule = class_key[4]
                outcome, details = _apply_classification(
                    token,
                    semantic_anchor["guid"],
                    class_name,
                    "",
                    class_assignment_source,
                    class_rule,
                    cde_id=class_cde_id,
                    cde_name=class_cde_name,
                )
                if outcome == "assigned":
                    anchor_classification_assigned += 1
                elif outcome == "existing":
                    anchor_classification_existing += 1
                else:
                    anchor_classification_failed.append((class_name, details))

        print(
            "[Cell 6] CDE classification summary: "
            f"assigned={classification_assigned} existing={classification_existing} "
            f"unresolved={len(classification_unresolved)} failed={len(classification_failed)} "
            f"anchor_assigned={anchor_classification_assigned} "
            f"anchor_existing={anchor_classification_existing} "
            f"anchor_failed={len(anchor_classification_failed)} "
            f"semantic_field_assigned={semantic_field_class_assigned} "
            f"semantic_field_existing={semantic_field_class_existing} "
            f"semantic_field_failed={len(semantic_field_class_failed)}"
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
        anchor_glossary_dedupe = set()
        semantic_field_glossary_assigned = 0
        semantic_field_glossary_existing = 0
        semantic_field_glossary_failed = []
        for row in glossary_term_manifest:
            asset_ref = _safe_text(row.get("asset_ref", ""))
            term_name = _safe_text(row.get("term_name", ""))
            assignment_source = _safe_text(row.get("assignment_source", ""))
            rule = _safe_text(row.get("rule", ""))
            key = (asset_ref.lower(), term_name.lower())
            if not asset_ref or not term_name or key in glossary_dedupe:
                continue
            glossary_dedupe.add(key)
            anchor_glossary_dedupe.add(term_name.lower())
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

            resolved = _resolve_asset_cached(asset_ref)
            semantic_field_targets = _resolve_semantic_model_field_targets(token, asset_ref)
            target_entities = []
            seen_target_guids = set()
            if resolved:
                target_entities.append(resolved)
                seen_target_guids.add(_safe_text(resolved.get("guid", "")))
            for semantic_target in semantic_field_targets:
                semantic_guid = _safe_text(semantic_target.get("guid", ""))
                if semantic_guid and semantic_guid not in seen_target_guids:
                    target_entities.append(semantic_target)
                    seen_target_guids.add(semantic_guid)
            if not target_entities and semantic_anchor:
                target_entities.append(semantic_anchor)
            if not target_entities:
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

            primary_guid = _safe_text(target_entities[0].get("guid", ""))
            for target in target_entities:
                outcome, details = _apply_glossary_term(
                    token,
                    target["guid"],
                    term_guid,
                    target.get("entityType", ""),
                )
                target_guid = _safe_text(target.get("guid", ""))
                if target_guid == primary_guid:
                    if outcome == "assigned":
                        glossary_assigned += 1
                    elif outcome == "existing":
                        glossary_existing += 1
                    else:
                        glossary_failed.append((asset_ref, term_name, details))
                else:
                    if outcome == "assigned":
                        semantic_field_glossary_assigned += 1
                    elif outcome == "existing":
                        semantic_field_glossary_existing += 1
                    else:
                        semantic_field_glossary_failed.append((asset_ref, term_name, details))

        anchor_glossary_assigned = 0
        anchor_glossary_existing = 0
        anchor_glossary_failed = []
        if semantic_anchor:
            for term_name_lower in sorted(anchor_glossary_dedupe):
                term_guid = term_guid_cache.get(term_name_lower, "")
                if not term_guid:
                    term_guid = _resolve_glossary_term_guid(token, term_name_lower)
                    term_guid_cache[term_name_lower] = term_guid
                if not term_guid:
                    continue

                outcome, details = _apply_glossary_term(
                    token,
                    semantic_anchor["guid"],
                    term_guid,
                    semantic_anchor.get("entityType", ""),
                )
                if outcome == "assigned":
                    anchor_glossary_assigned += 1
                elif outcome == "existing":
                    anchor_glossary_existing += 1
                else:
                    anchor_glossary_failed.append((term_name_lower, details))

        print(
            "[Cell 6] Glossary term summary: "
            f"assigned={glossary_assigned} existing={glossary_existing} "
            f"unresolved_assets={len(glossary_unresolved_assets)} "
            f"unresolved_terms={len(glossary_unresolved_terms)} failed={len(glossary_failed)} "
            f"anchor_assigned={anchor_glossary_assigned} "
            f"anchor_existing={anchor_glossary_existing} "
            f"anchor_failed={len(anchor_glossary_failed)} "
            f"semantic_field_assigned={semantic_field_glossary_assigned} "
            f"semantic_field_existing={semantic_field_glossary_existing} "
            f"semantic_field_failed={len(semantic_field_glossary_failed)}"
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

            resolved = _resolve_asset_cached(asset_ref)
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

