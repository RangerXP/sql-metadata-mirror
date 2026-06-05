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
import uuid
import requests
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
PURVIEW_ACCOUNT_NAME = "Purview-West3"
PURVIEW_BASE_URL = f"https://{PURVIEW_ACCOUNT_NAME}.purview.azure.com"
APPLY_CHANGES = False

print(f"Purview account: {PURVIEW_ACCOUNT_NAME}")
print(f"Apply changes: {APPLY_CHANGES}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read governance tables

domains_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.domains")
data_products_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.data_products")
role_assignments_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.role_assignments")

print(f"domains rows: {domains_df.count()}")
print(f"data_products rows: {data_products_df.count()}")
print(f"role_assignments rows: {role_assignments_df.count()}")


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
            ],
        },
    ]
}


def _resolve_domain_id(row):
    return _safe_text(getattr(row, "domain_id", None) or getattr(row, "domain_code", None))


def _resolve_product_id(row):
    return _safe_text(getattr(row, "data_product_id", None) or getattr(row, "product_code", None))


domain_entities = []
for row in domains_df.collect():
    domain_id = _resolve_domain_id(row)
    if not domain_id:
        continue

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
for row in data_products_df.collect():
    product_id = _resolve_product_id(row)
    if not product_id:
        continue

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
            },
        }
    )

payload = {"entities": domain_entities + product_entities}

print(f"Domain entities prepared: {len(domain_entities)}")
print(f"Data product entities prepared: {len(product_entities)}")
print(f"Total entities prepared: {len(payload['entities'])}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Save dry-run payload artifacts for review

output_root = "/lakehouse/default/Files/purview_publish"

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


if not APPLY_CHANGES:
    print("[DRY RUN] APPLY_CHANGES=False. Skipping Purview API calls.")
else:
    token = mssparkutils.credentials.getToken("https://purview.azure.net")

    typedef_status, typedef_body = _post_json("/catalog/api/atlas/v2/types/typedefs", token, typedef_payload)
    if typedef_status in (200, 201):
        print("[APPLIED] TypeDefs registered/updated.")
    elif typedef_status == 400 and "already exists" in typedef_body.lower():
        print("[INFO] TypeDefs already exist. Continuing.")
    else:
        raise RuntimeError(f"TypeDefs registration failed: HTTP {typedef_status} | {typedef_body[:500]}")

    entity_status, entity_body = _post_json("/catalog/api/atlas/v2/entity/bulk", token, payload)
    if entity_status in (200, 201):
        print("[APPLIED] Domain and data-product entities upserted.")
    else:
        raise RuntimeError(f"Entity upsert failed: HTTP {entity_status} | {entity_body[:500]}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Publish summary

summary_rows = [
    ("domains_prepared", len(domain_entities)),
    ("data_products_prepared", len(product_entities)),
    ("roles_available", role_assignments_df.count()),
    ("apply_changes", int(APPLY_CHANGES)),
]

summary_df = spark.createDataFrame(summary_rows, ["metric", "value"]).orderBy("metric")
display(summary_df)
