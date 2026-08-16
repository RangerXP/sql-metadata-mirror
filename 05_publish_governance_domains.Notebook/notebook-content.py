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
import time
from pyspark.sql import SparkSession

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
PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_TOKEN_CACHE_PATH = "Files/purview_publish/.purview_token_cache.json"
SQL_MIRROR_ONLY_DEPLOYMENT = False
PURVIEW_PUBLISH_OVERRIDE = True
APPLY_CHANGES = True
# Optional manual bearer token fallback for when Fabric's TokenLibrary call to the
# Purview audience is unavailable. Capture with:
#   az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv
PURVIEW_ACCESS_TOKEN = os.getenv("PURVIEW_ACCESS_TOKEN", "").strip()


def _table_candidates(table_name: str):
    return [
        f"{METADATA_SCHEMA}.{table_name}",
        f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.{table_name}",
        table_name,
    ]


def _read_table(table_name: str):
    last_error = None
    for candidate in _table_candidates(table_name):
        try:
            # Force a metadata refresh so mirrored-table schema drift (stale catalog
            # cache vs. current Delta log, e.g. mid-replication) doesn't surface as a
            # column-resolution error later.
            try:
                spark.sql(f"REFRESH TABLE {candidate}")
            except Exception:
                pass
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex
    raise RuntimeError(f"Could not resolve table '{table_name}'. Last error: {last_error}")

print(f"Purview account: {PURVIEW_ACCOUNT_NAME}")
print(f"SQL mirror only deployment guard: {SQL_MIRROR_ONLY_DEPLOYMENT}")
print(f"Purview publish override: {PURVIEW_PUBLISH_OVERRIDE}")
print(f"Apply changes: {APPLY_CHANGES}")
print(f"Metadata source candidates: {_table_candidates('<table>')}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read governance tables

domains_df, domains_source = _read_table("domains")
data_products_df, data_products_source = _read_table("data_products")
role_assignments_df, roles_source = _read_table("role_assignments")
# G11-1 ontology layer: business Objectives/Key Results, linked to Data Products.
okrs_df, okrs_source = _read_table("okrs")
okr_key_results_df, okr_key_results_source = _read_table("okr_key_results")
okr_data_products_df, okr_data_products_source = _read_table("okr_data_products")

print(f"domains rows: {domains_df.count()} (source={domains_source})")
print(f"data_products rows: {data_products_df.count()} (source={data_products_source})")
print(f"role_assignments rows: {role_assignments_df.count()} (source={roles_source})")
print(f"okrs rows: {okrs_df.count()} (source={okrs_source})")
print(f"okr_key_results rows: {okr_key_results_df.count()} (source={okr_key_results_source})")
print(f"okr_data_products rows: {okr_data_products_df.count()} (source={okr_data_products_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build Atlas payloads for domains and data products


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _domain_qualified_name(domain_id: str) -> str:
    return f"enercare://governance/domain/{domain_id}"


def _product_qualified_name(product_id: str) -> str:
    return f"enercare://governance/data-product/{product_id}"


def _okr_qualified_name(okr_id: str) -> str:
    return f"enercare://governance/okr/{okr_id}"


def _key_result_qualified_name(key_result_id: str) -> str:
    return f"enercare://governance/okr-key-result/{key_result_id}"


def _guid() -> str:
    return f"-{uuid.uuid4().int % 1000000000}"


# Keep typedefs minimal and idempotent for Day 2 demo publish.
typedef_payload = {
    "entityDefs": [
        {
            "category": "ENTITY",
            "name": "EnercareGovernanceDomain",
            "description": "Governance domain from lh_metadata.metadata.domains",
            "superTypes": ["Referenceable"],
            "attributeDefs": [
                {"name": "domain_id", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "domain_name", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "domain_type", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "status", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "owners", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "creators", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "description", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
            ],
        },
        {
            "category": "ENTITY",
            "name": "EnercareDataProduct",
            "description": "Data product from lh_metadata.metadata.data_products",
            "superTypes": ["Referenceable"],
            "attributeDefs": [
                {"name": "data_product_id", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "data_product_name", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "product_type", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "status", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "owners", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "access_policy", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "audience", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "business_use_case", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "parent_domain_id", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "parent_domain_qualified_name", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
            ],
        },
        {
            # G11-1 ontology layer: business Objective, linked to one or more Data
            # Products the same way Purview's native Unified Catalog OKR feature
            # links an Objective to its "Related data products".
            "category": "ENTITY",
            "name": "EnercareOKR",
            "description": "Business objective (OKR) from lh_metadata.metadata.okrs",
            "superTypes": ["Referenceable"],
            "attributeDefs": [
                {"name": "okr_id", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "okr_name", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "domain_id", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "domain_qualified_name", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "definition", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "owner_upn", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "target_date", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "status", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "linked_data_product_ids", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "linked_data_product_qualified_names", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
            ],
        },
        {
            # G11-1 ontology layer: Key Result under an Objective, linked back to its
            # parent OKR and to the KPI/measure it tracks (kpi_metadata.KPICode or a
            # BrookfieldEnercare/_Measures/<name> asset ref).
            "category": "ENTITY",
            "name": "EnercareOKRKeyResult",
            "description": "OKR key result from lh_metadata.metadata.okr_key_results",
            "superTypes": ["Referenceable"],
            "attributeDefs": [
                {"name": "key_result_id", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "result_name", "typeName": "string", "isOptional": False, "cardinality": "SINGLE"},
                {"name": "parent_okr_id", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "parent_okr_qualified_name", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "metric_source", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "goal_amount", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "progress_amount", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "max_amount", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
                {"name": "progress_status", "typeName": "string", "isOptional": True, "cardinality": "SINGLE"},
            ],
        },
    ]
}


def _resolve_domain_id(row):
    return _safe_text(getattr(row, "domain_id", None) or getattr(row, "domain_code", None))


def _resolve_product_id(row):
    return _safe_text(getattr(row, "data_product_id", None) or getattr(row, "product_code", None))


def _collect_with_refresh_retry(df, source_name, needed_columns):
    # Prune the projection to only the columns this notebook actually reads. Some
    # mirrored-table columns (e.g. domains.parent_domain) are declared in the Delta
    # schema but not materialized in the physical files, which fails .collect() on
    # the full row even though .count() succeeds. Selecting only needed columns
    # keeps the broken column out of the physical scan entirely.
    def _safe_select(candidate_df):
        cols = [c for c in needed_columns if c in candidate_df.columns]
        return candidate_df.select(*cols) if cols else candidate_df

    try:
        return _safe_select(df).collect()
    except Exception:
        spark.sql(f"REFRESH TABLE {source_name}")
        return _safe_select(spark.table(source_name)).collect()


DOMAIN_NEEDED_COLUMNS = [
    "domain_id",
    "domain_code",
    "domain_name",
    "domain_type",
    "status",
    "governance_domain_owners",
    "governance_domain_creators",
    "description",
]

PRODUCT_NEEDED_COLUMNS = [
    "data_product_id",
    "product_code",
    "data_product_name",
    "product_name",
    "product_type",
    "status",
    "published_status",
    "owners",
    "owner_upn",
    "access_policy",
    "audience",
    "business_use_case",
    "parent_domain_id",
]

domain_entities = []
domain_id_set = set()
for row in _collect_with_refresh_retry(domains_df, domains_source, DOMAIN_NEEDED_COLUMNS):
    domain_id = _resolve_domain_id(row)
    if not domain_id:
        continue

    domain_id_set.add(domain_id)

    domain_entities.append(
        {
            "typeName": "EnercareGovernanceDomain",
            "guid": _guid(),
            "attributes": {
                "qualifiedName": _domain_qualified_name(domain_id),
                "name": _safe_text(getattr(row, "domain_name", None)) or domain_id,
                "domain_id": domain_id,
                "domain_name": _safe_text(getattr(row, "domain_name", None)),
                "domain_type": _safe_text(getattr(row, "domain_type", None)),
                "status": _safe_text(getattr(row, "status", None)),
                "owners": _safe_text(getattr(row, "governance_domain_owners", None)),
                "creators": _safe_text(getattr(row, "governance_domain_creators", None)),
                "description": _safe_text(getattr(row, "description", None)),
            },
        }
    )

product_entities = []
products_total = 0
products_with_parent_domain = 0
products_unresolved_parent_domain = 0
for row in _collect_with_refresh_retry(data_products_df, data_products_source, PRODUCT_NEEDED_COLUMNS):
    product_id = _resolve_product_id(row)
    if not product_id:
        continue

    products_total += 1
    parent_domain_id = _safe_text(getattr(row, "parent_domain_id", None))
    parent_domain_qn = _domain_qualified_name(parent_domain_id) if parent_domain_id else ""

    if parent_domain_id:
        products_with_parent_domain += 1
        if parent_domain_id not in domain_id_set:
            products_unresolved_parent_domain += 1

    product_entities.append(
        {
            "typeName": "EnercareDataProduct",
            "guid": _guid(),
            "attributes": {
                "qualifiedName": _product_qualified_name(product_id),
                "name": _safe_text(getattr(row, "data_product_name", None) or getattr(row, "product_name", None)) or product_id,
                "data_product_id": product_id,
                "data_product_name": _safe_text(getattr(row, "data_product_name", None) or getattr(row, "product_name", None)),
                "product_type": _safe_text(getattr(row, "product_type", None)),
                "status": _safe_text(getattr(row, "status", None) or getattr(row, "published_status", None)),
                "owners": _safe_text(getattr(row, "owners", None) or getattr(row, "owner_upn", None)),
                "access_policy": _safe_text(getattr(row, "access_policy", None)),
                "audience": _safe_text(getattr(row, "audience", None)),
                "business_use_case": _safe_text(getattr(row, "business_use_case", None)),
                "parent_domain_id": parent_domain_id,
                "parent_domain_qualified_name": parent_domain_qn,
            },
        }
    )

OKR_NEEDED_COLUMNS = [
    "okr_id",
    "okr_name",
    "domain_id",
    "definition",
    "owner_upn",
    "target_date",
    "status",
]

OKR_KEY_RESULT_NEEDED_COLUMNS = [
    "key_result_id",
    "okr_id",
    "result_name",
    "metric_source",
    "goal_amount",
    "progress_amount",
    "max_amount",
    "progress_status",
]

OKR_DATA_PRODUCT_NEEDED_COLUMNS = ["okr_id", "data_product_id"]

# okr_id -> list[data_product_id], from the governance_okr_data_products link table.
okr_linked_product_ids = {}
for row in _collect_with_refresh_retry(okr_data_products_df, okr_data_products_source, OKR_DATA_PRODUCT_NEEDED_COLUMNS):
    okr_id = _safe_text(getattr(row, "okr_id", None))
    product_id = _safe_text(getattr(row, "data_product_id", None))
    if not okr_id or not product_id:
        continue
    okr_linked_product_ids.setdefault(okr_id, []).append(product_id)

okr_entities = []
okr_id_set = set()
okrs_with_resolved_products = 0
okrs_with_unresolved_products = 0
resolved_product_ids = {e["attributes"]["data_product_id"] for e in product_entities}
for row in _collect_with_refresh_retry(okrs_df, okrs_source, OKR_NEEDED_COLUMNS):
    okr_id = _safe_text(getattr(row, "okr_id", None))
    if not okr_id:
        continue

    okr_id_set.add(okr_id)
    linked_product_ids = okr_linked_product_ids.get(okr_id, [])
    unresolved_products = [pid for pid in linked_product_ids if pid not in resolved_product_ids]
    if linked_product_ids and not unresolved_products:
        okrs_with_resolved_products += 1
    elif unresolved_products:
        okrs_with_unresolved_products += 1

    domain_id = _safe_text(getattr(row, "domain_id", None))

    okr_entities.append(
        {
            "typeName": "EnercareOKR",
            "guid": _guid(),
            "attributes": {
                "qualifiedName": _okr_qualified_name(okr_id),
                "name": _safe_text(getattr(row, "okr_name", None)) or okr_id,
                "okr_id": okr_id,
                "okr_name": _safe_text(getattr(row, "okr_name", None)),
                "domain_id": domain_id,
                "domain_qualified_name": _domain_qualified_name(domain_id) if domain_id else "",
                "definition": _safe_text(getattr(row, "definition", None)),
                "owner_upn": _safe_text(getattr(row, "owner_upn", None)),
                "target_date": _safe_text(getattr(row, "target_date", None)),
                "status": _safe_text(getattr(row, "status", None)),
                "linked_data_product_ids": ";".join(linked_product_ids),
                "linked_data_product_qualified_names": ";".join(_product_qualified_name(pid) for pid in linked_product_ids),
            },
        }
    )

key_result_entities = []
key_results_total = 0
key_results_with_parent_okr = 0
for row in _collect_with_refresh_retry(okr_key_results_df, okr_key_results_source, OKR_KEY_RESULT_NEEDED_COLUMNS):
    key_result_id = _safe_text(getattr(row, "key_result_id", None))
    if not key_result_id:
        continue

    key_results_total += 1
    parent_okr_id = _safe_text(getattr(row, "okr_id", None))
    if parent_okr_id and parent_okr_id in okr_id_set:
        key_results_with_parent_okr += 1

    key_result_entities.append(
        {
            "typeName": "EnercareOKRKeyResult",
            "guid": _guid(),
            "attributes": {
                "qualifiedName": _key_result_qualified_name(key_result_id),
                "name": _safe_text(getattr(row, "result_name", None)) or key_result_id,
                "key_result_id": key_result_id,
                "result_name": _safe_text(getattr(row, "result_name", None)),
                "parent_okr_id": parent_okr_id,
                "parent_okr_qualified_name": _okr_qualified_name(parent_okr_id) if parent_okr_id else "",
                "metric_source": _safe_text(getattr(row, "metric_source", None)),
                "goal_amount": _safe_text(getattr(row, "goal_amount", None)),
                "progress_amount": _safe_text(getattr(row, "progress_amount", None)),
                "max_amount": _safe_text(getattr(row, "max_amount", None)),
                "progress_status": _safe_text(getattr(row, "progress_status", None)),
            },
        }
    )

payload = {"entities": domain_entities + product_entities + okr_entities + key_result_entities}

print(f"Domain entities prepared: {len(domain_entities)}")
print(f"Data product entities prepared: {len(product_entities)}")
print(f"OKR entities prepared: {len(okr_entities)}")
print(f"OKR key result entities prepared: {len(key_result_entities)}")
print(f"Total entities prepared: {len(payload['entities'])}")
print(f"Products with parent_domain_id: {products_with_parent_domain} / {products_total}")
print(f"Products with unresolved parent_domain_id: {products_unresolved_parent_domain}")
print(f"OKRs with resolved linked data products: {okrs_with_resolved_products}")
print(f"OKRs with unresolved linked data products: {okrs_with_unresolved_products}")
print(f"Key results with resolved parent OKR: {key_results_with_parent_okr} / {key_results_total}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Save dry-run payload artifacts for review

output_root = "Files/purview_publish"

mssparkutils.fs.mkdirs(output_root)
mssparkutils.fs.put(f"{output_root}/typedefs_day2.json", json.dumps(typedef_payload, indent=2), True)
mssparkutils.fs.put(f"{output_root}/entities_day2.json", json.dumps(payload, indent=2), True)

print(f"Payloads written to: {output_root}")
print(" - typedefs_day2.json")
print(" - entities_day2.json")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4a: Acquire a Purview bearer token, reusing a cached one if another notebook
# (nb_07/nb_08/nb_09) already signed in recently, otherwise via interactive
# device-code sign-in. No terminal or copy-pasting a token needed: if a sign-in is
# required, running this cell prints a URL and a short one-time code. Open the URL
# in any browser tab, enter the code, approve the sign-in, and the token is captured
# straight into PURVIEW_ACCESS_TOKEN below and cached for the other notebooks to reuse.
# Uses the public "Azure CLI" client ID, which users in this tenant are already
# consented for, so no app registration/admin consent step is required.
#
# Fallback (e.g. no outbound internet from this Spark session): comment out this
# cell's body and instead set PURVIEW_ACCESS_TOKEN directly to a token captured with
#   az account get-access-token --resource https://purview.azure.net --query accessToken -o tsv

if "PURVIEW_TENANT_ID" not in globals() or "PURVIEW_TOKEN_CACHE_PATH" not in globals():
    raise RuntimeError(
        "PURVIEW_TENANT_ID/PURVIEW_TOKEN_CACHE_PATH are not defined. Run Cell 1 in this "
        "kernel session first (they reset on kernel/session restart), then re-run Cell 4a."
    )


def _read_shared_purview_token_cache():
    try:
        raw = mssparkutils.fs.head(PURVIEW_TOKEN_CACHE_PATH, 65536)
    except Exception:
        return ""
    try:
        cached = json.loads(raw)
        cached_token = (cached.get("access_token") or "").strip()
        expires_on = float(cached.get("expires_on", 0))
    except Exception:
        return ""
    if not cached_token or expires_on <= time.time() + 120:
        return ""
    return cached_token


def _write_shared_purview_token_cache(token: str, expires_on: float):
    try:
        mssparkutils.fs.mkdirs("Files/purview_publish")
        mssparkutils.fs.put(
            PURVIEW_TOKEN_CACHE_PATH,
            json.dumps({"access_token": token, "expires_on": expires_on}),
            True,
        )
    except Exception as exc:
        print(f"[Cell 4a][WARN] Could not write shared Purview token cache: {exc}")


# Plain subprocess install (not the %pip magic): %pip install restarts the Fabric
# kernel on every invocation, which wipes Cell 1's globals and re-triggers the
# guard above on the very next line. Only install if the import genuinely fails.
try:
    from azure.identity import DeviceCodeCredential
except ImportError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "azure-identity"], check=True)
    from azure.identity import DeviceCodeCredential

_AZURE_CLI_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


def _print_device_code(verification_uri, user_code, expires_on):
    print(f"[Cell 4a] Open {verification_uri} in any browser and enter code: {user_code}")


PURVIEW_ACCESS_TOKEN = _read_shared_purview_token_cache()
if PURVIEW_ACCESS_TOKEN:
    print("[Cell 4a] Reusing cached Purview token acquired from another notebook/session.")
else:
    print("[Cell 4a] No valid cached token found; starting device-code sign-in.")
    _purview_credential = DeviceCodeCredential(
        client_id=_AZURE_CLI_CLIENT_ID,
        tenant_id=PURVIEW_TENANT_ID,
        prompt_callback=_print_device_code,
    )
    _purview_token_result = _purview_credential.get_token("https://purview.azure.net/.default")
    PURVIEW_ACCESS_TOKEN = _purview_token_result.token
    _write_shared_purview_token_cache(_purview_token_result.token, _purview_token_result.expires_on)
    print("[Cell 4a] Purview token acquired via device-code sign-in and cached for other notebooks.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Optional live publish to Purview Atlas


def _purview_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post_json(path: str, token: str, body: dict):
    url = f"{PURVIEW_BASE_URL}{path}"
    resp = requests.post(url, headers=_purview_headers(token), json=body, timeout=60)
    return resp.status_code, resp.text


def _get_purview_token_with_retry(resource: str, max_attempts: int = 3, backoff_seconds: float = 5.0):
    manual_token = (PURVIEW_ACCESS_TOKEN or "").strip().strip('"').strip("'")
    if manual_token == "PASTE_TOKEN_HERE":
        manual_token = ""
    if manual_token:
        if manual_token.count(".") != 2:
            print(
                "[Cell 5][WARN] PURVIEW_ACCESS_TOKEN does not look like a well-formed JWT "
                "(expected 3 dot-separated segments). Check for stray quotes/whitespace/newlines "
                "left over from copy-pasting the az CLI output."
            )
        print("[Cell 5] Using manually supplied PURVIEW_ACCESS_TOKEN (TokenLibrary bypassed).")
        return manual_token

    # Fabric's Token Management service occasionally returns a transient 500; retry before failing the cell.
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return mssparkutils.credentials.getToken(resource)
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                print(f"[WARN] getToken attempt {attempt}/{max_attempts} failed: {exc}. Retrying in {backoff_seconds}s...")
                time.sleep(backoff_seconds)
    raise RuntimeError(
        "TokenLibrary getToken failed after retries and no PURVIEW_ACCESS_TOKEN fallback was supplied. "
        "Set PURVIEW_ACCESS_TOKEN (e.g. via 'az account get-access-token --resource https://purview.azure.net "
        f"--query accessToken -o tsv') to bypass the failing TokenLibrary call. Last error: {last_error}"
    )


if SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE:
    print(
        "[GUARD] SQL-mirror-only deployment is active. "
        "Live Purview publish is disabled for this run. "
        "Set PURVIEW_PUBLISH_OVERRIDE=True to intentionally enable publish."
    )
elif not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
else:
    if PURVIEW_ACCESS_TOKEN and PURVIEW_ACCESS_TOKEN != "PASTE_TOKEN_HERE":
        print("[Cell 5] PURVIEW_ACCESS_TOKEN is set; TokenLibrary will be bypassed.")
    else:
        print(
            "[Cell 5][WARN] PURVIEW_ACCESS_TOKEN is not set. Falling back to "
            "mssparkutils.credentials.getToken, which is known to fail intermittently "
            "with Spark_System_TM_INTERNAL_ERROR in this workspace. To avoid that, run "
            "'az account get-access-token --resource https://purview.azure.net "
            "--query accessToken -o tsv' locally, then in a cell before this one set "
            "PURVIEW_ACCESS_TOKEN = \"<token>\" (do not run Cell 1 again afterward)."
        )
    token = _get_purview_token_with_retry("https://purview.azure.net")

    # Atlas's bulk /types/typedefs POST is atomic across the whole request: if the
    # payload mixes entityDefs that already exist (from a prior publish) with ones
    # that are genuinely new, the server can reject the entire batch as "already
    # exists" even though the new types were never created. Registering each
    # entityDef individually guarantees a pre-existing type never blocks creation
    # of a new one in the same run.
    for entity_def in typedef_payload.get("entityDefs", []):
        single_payload = {"entityDefs": [entity_def]}
        def_name = entity_def.get("name", "<unknown>")
        def_status, def_body = _post_json("/catalog/api/atlas/v2/types/typedefs", token, single_payload)
        if def_status in (200, 201):
            print(f"[APPLIED] TypeDef '{def_name}' registered/updated.")
        elif def_status in (400, 409) and "already exists" in def_body.lower():
            print(f"[INFO] TypeDef '{def_name}' already exists. Continuing.")
        else:
            raise RuntimeError(f"TypeDef registration failed for '{def_name}': HTTP {def_status} | {def_body[:500]}")

    # Purview's Atlas type cache can lag briefly after a typedef create/update
    # response comes back 200/201, causing an immediately-following entity/bulk
    # call to fail with ATLAS-400-00-014 "Type ENTITY with name <X> does not
    # exist" even though the typedef call genuinely just succeeded. Retry the
    # entity upsert a few times with a short backoff before giving up.
    entity_max_attempts = 4
    entity_backoff_seconds = 10.0
    entity_status, entity_body = None, ""
    for attempt in range(1, entity_max_attempts + 1):
        entity_status, entity_body = _post_json("/catalog/api/atlas/v2/entity/bulk", token, payload)
        if entity_status in (200, 201):
            break
        type_not_found = (
            entity_status == 400
            and "ATLAS-400-00-014" in entity_body
            and "does not exist" in entity_body.lower()
        )
        if type_not_found and attempt < entity_max_attempts:
            print(
                f"[WARN] Entity upsert attempt {attempt}/{entity_max_attempts} failed because a newly "
                f"registered type is not yet visible to Atlas (type-cache propagation lag). "
                f"Retrying in {entity_backoff_seconds}s..."
            )
            time.sleep(entity_backoff_seconds)
            continue
        break

    if entity_status in (200, 201):
        print("[APPLIED] Domain, data-product, OKR, and OKR key result entities upserted.")
    else:
        raise RuntimeError(f"Entity upsert failed: HTTP {entity_status} | {entity_body[:500]}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Publish summary

publish_guard_active = SQL_MIRROR_ONLY_DEPLOYMENT and not PURVIEW_PUBLISH_OVERRIDE
live_publish_enabled = APPLY_CHANGES and not publish_guard_active

summary_rows = [
    ("domains_prepared", len(domain_entities)),
    ("data_products_prepared", len(product_entities)),
    ("products_with_parent_domain", products_with_parent_domain),
    ("products_unresolved_parent_domain", products_unresolved_parent_domain),
    ("roles_available", role_assignments_df.count()),
    ("okrs_prepared", len(okr_entities)),
    ("okr_key_results_prepared", len(key_result_entities)),
    ("okrs_with_resolved_products", okrs_with_resolved_products),
    ("okrs_with_unresolved_products", okrs_with_unresolved_products),
    ("key_results_with_parent_okr", key_results_with_parent_okr),
    ("publish_guard_active", int(publish_guard_active)),
    ("live_publish_enabled", int(live_publish_enabled)),
    ("apply_changes", int(APPLY_CHANGES)),
]

summary_df = spark.createDataFrame(summary_rows, ["metric", "value"]).orderBy("metric")
display(summary_df)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
