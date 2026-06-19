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

# Explicit aliases for shorthand semantic measure bindings used in source metadata.
MEASURE_TOKEN_ALIASES = {
    "fcr": ["FCR Rate", "First Contact Resolution", "FCR"],
    "nps": ["NPS", "Net Promoter Score"],
    "csat": ["CSAT", "Customer Satisfaction"],
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

    print("[AUTH] Using captured PURVIEW_ACCESS_TOKEN only.")
    return token


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


def _compact_token(value: str) -> str:
    return "".join(ch for ch in _safe_text(value).lower() if ch.isalnum())


def _resolve_asset_guid_for_token(token: str, auth_token: str, term_name: str = ""):
    parsed = _parse_bound_asset_token(token)
    best = None
    best_score = 0

    for keywords in _asset_query_candidates(parsed):
        for entity in _search_purview_assets(auth_token, keywords, limit=50):
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

    return best if best_score > 0 else ""


def _resolve_glossary_term_guid(term_name: str, term_code: str, term_guid_index):
    by_name = term_guid_index.get(("name", _safe_text(term_name).lower()), "")
    if by_name:
        return by_name
    by_code = term_guid_index.get(("code", _safe_text(term_code).lower()), "")
    if by_code:
        return by_code
    return ""


def _assign_term_to_entity(term_guid: str, entity_guid: str, auth_token: str):
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
    if typedef_status not in (200, 201, 409) and "already exists" not in typedef_body.lower():
        raise RuntimeError(f"TypeDef publish failed: HTTP {typedef_status} | {typedef_body[:500]}")
    print(f"TypeDefs publish result: HTTP {typedef_status}")

    entity_status, entity_body = _request("POST", "/catalog/api/atlas/v2/entity/bulk", token, cde_payload)
    if entity_status not in (200, 201):
        raise RuntimeError(f"CDE entity publish failed: HTTP {entity_status} | {entity_body[:500]}")
    print(f"CDE entity publish result: HTTP {entity_status}")

    created_terms = 0
    existing_terms = 0
    failed_terms = []
    term_guid_by_code = {}
    total_terms = len(term_payloads)
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
        else:
            failed_terms.append((term["term_code"], term_status, term_body[:300]))
        if index % 5 == 0 or index == total_terms:
            print(
                f"Progress: {index}/{total_terms} | "
                f"created={created_terms} existing={existing_terms} failed={len(failed_terms)}"
            )

    if failed_terms:
        sample = failed_terms[0]
        raise RuntimeError(
            "Glossary term publish completed with failures. "
            f"failed={len(failed_terms)} first_failure=({sample[0]}, HTTP {sample[1]}, {sample[2]})"
        )

    print(
        "Glossary term publish complete. "
        f"created={created_terms} existing={existing_terms} failed=0"
    )

    print("Starting glossary-to-asset association...")
    term_guid_index = _build_term_guid_index(resolved_glossary_guid, token)
    print(f"Glossary term index loaded: {len(term_guid_index)} key(s)")
    association_attempts = 0
    association_assigned = 0
    association_existing = 0
    unresolved_term_count = 0
    unresolved_asset_tokens = []
    failed_associations = []

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
                if len(unresolved_asset_tokens) < 25:
                    unresolved_asset_tokens.append(f"{term_code}:{asset_token}")

        for entity_guid in entity_guids:
            association_attempts += 1
            outcome, details = _assign_term_to_entity(term_guid, entity_guid, token)
            if outcome == "assigned":
                association_assigned += 1
            elif outcome == "existing":
                association_existing += 1
            else:
                failed_associations.append((term_code, entity_guid, details))

    print(
        "Glossary association summary: "
        f"attempted={association_attempts} assigned={association_assigned} "
        f"existing={association_existing} unresolved_terms={unresolved_term_count} "
        f"unresolved_tokens={len(unresolved_asset_tokens)} failed={len(failed_associations)}"
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
