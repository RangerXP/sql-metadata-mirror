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

# Cell 1: Imports and Config
# Purpose: Initialize Spark session, import required libraries, and set Purview/Fabric configuration.
# Outputs: Purview endpoint URL, deployment mode flags, output paths, and Enercare workspace identifiers.

import hashlib
import json
import time
import uuid
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
PURVIEW_HTTP_TIMEOUT_SECONDS = 20
MAX_ENTITY_RESOLUTION_SECONDS = 120
MAX_EDGES_TO_RESOLVE = 50
FAIL_ON_TOKEN_ACQUISITION_ERROR = False
TOKEN_RESOURCE_CANDIDATES = ["https://purview.azure.net"]
TOKEN_OUTER_RETRY_ATTEMPTS = 1

WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
SQL_SOURCE_NAME = "ENERCARE-SQL-SOURCE"
FABRIC_SOURCE_NAME = "ENERCARE-FABRIC-SOURCE"
SEMANTIC_MODEL_NAME = "BrookfieldEnercare"

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
data_products_df, data_products_source = _read_table("data_products")

if labels_df is None:
    print("[WARN] metadata.label_assignments not found; label rules will be inferred from CDE values when possible.")

print(f"cdes rows: {cde_df.count()} (source={cde_source})")
if labels_df is not None:
    print(f"label_assignments rows: {labels_df.count()} (source={labels_source})")
print(f"data_products rows: {data_products_df.count()} (source={data_products_source})")

# Cell 2 complete: Metadata tables loaded


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build Classification TypeDefs and Manifests
# Purpose: Create Purview classification typedefs for sensitivity labels and build asset classification manifest.
# Outputs: typedef_payload (classification definitions), classification_manifest (asset-label mappings).


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


def _label_to_type_name(label_name: str) -> str:
    cleaned = "".join(ch for ch in _safe_text(label_name).title() if ch.isalnum())
    return f"EnercareSensitivity{cleaned or 'Unspecified'}"


labels = set()
cde_has_sensitivity_label = "sensitivity_label" in cde_df.columns
if cde_has_sensitivity_label:
    for row in cde_df.select("sensitivity_label").distinct().collect():
        label = _safe_text(getattr(row, "sensitivity_label", None))
        if label:
            labels.add(label)
if labels_df is not None and "label_name" in labels_df.columns:
    for row in labels_df.select("label_name").distinct().collect():
        label = _safe_text(getattr(row, "label_name", None))
        if label:
            labels.add(label)

if not labels:
    labels.add("Internal")

classification_defs = []
for label in sorted(labels):
    classification_defs.append(
        {
            "category": "CLASSIFICATION",
            "name": _label_to_type_name(label),
            "description": f"Enercare governance sensitivity label: {label}",
            "attributeDefs": [
                {"name": "label_name", "typeName": "string", "isOptional": True},
                {"name": "assignment_source", "typeName": "string", "isOptional": True},
                {"name": "rule", "typeName": "string", "isOptional": True},
            ],
        }
    )

typedef_payload = {"classificationDefs": classification_defs}

classification_manifest = []
if cde_has_sensitivity_label:
    for row in cde_df.collect():
        label = _safe_text(getattr(row, "sensitivity_label", None))
        if not label:
            continue
        cde_id = _safe_text(getattr(row, "cde_id", None) or getattr(row, "cde_code", None) or getattr(row, "cde_name", None))
        for token in _split_tokens(getattr(row, "bound_columns", None)):
            classification_manifest.append(
                {
                    "asset_ref": token,
                    "classification": _label_to_type_name(label),
                    "label_name": label,
                    "assignment_source": "CDE",
                    "rule": cde_id,
                }
            )
else:
    print("[Cell 3] cdes.sensitivity_label not found; using label_assignments as classification source.")

if labels_df is not None:
    for row in labels_df.collect():
        label = _safe_text(getattr(row, "label_name", None))
        assets = _safe_text(getattr(row, "applies_to_asset_ids", None) or getattr(row, "enforcement_target", None))
        rule = _safe_text(getattr(row, "assignment_rule", None))
        for token in _split_tokens(assets):
            classification_manifest.append(
                {
                    "asset_ref": token,
                    "classification": _label_to_type_name(label),
                    "label_name": label,
                    "assignment_source": "LabelPolicy",
                    "rule": rule,
                }
            )

print(f"Classification defs prepared: {len(classification_defs)}")
print(f"Classification manifest rows prepared: {len(classification_manifest)}")

# Cell 3 complete: Classification typedefs and manifests built


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
# Purpose: Export classification typedefs, manifest, and lineage edges to Azure Data Lake.
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
mssparkutils.fs.put(f"{output_root}/classification_manifest.json", json.dumps(classification_manifest, indent=2), True)
mssparkutils.fs.put(f"{output_root}/lineage_edges.json", json.dumps(lineage_edges, indent=2), True)

validation_rows = [
    ("classification_defs_prepared", len(classification_defs), "PASS" if classification_defs else "FAIL"),
    ("classification_manifest_rows", len(classification_manifest), "PASS" if classification_manifest else "FAIL"),
    ("lineage_edges_prepared", len(lineage_edges), "PASS" if lineage_edges else "WARN"),
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


def _get_purview_token_with_retry() -> str:
    last_error = None

    for resource in TOKEN_RESOURCE_CANDIDATES:
        for attempt in range(1, TOKEN_OUTER_RETRY_ATTEMPTS + 1):
            try:
                token = mssparkutils.credentials.getToken(resource)
                if token and _safe_text(token):
                    print(f"[Cell 6] Acquired Purview token using resource='{resource}' on attempt {attempt}.")
                    return token
            except Exception as ex:
                last_error = ex

            if attempt < TOKEN_OUTER_RETRY_ATTEMPTS:
                time.sleep(3 * attempt)

    raise RuntimeError(
        f"Failed to acquire Purview token after retries. Last error: {last_error}"
    )


def _find_entity_by_qualified_name(token: str, qualified_name: str):
    # Atlas DSL query returns discovered assets with guid/typeName when the qualifiedName matches.
    query = f"from * where qualifiedName = '{qualified_name}'"
    status, body = _request("GET", "/catalog/api/atlas/v2/search/dsl", token, params={"query": query, "limit": 1})
    if status != 200:
        return None

    try:
        payload = json.loads(body)
    except Exception:
        return None

    entities = payload.get("entities") or []
    if not entities:
        return None

    entity = entities[0]
    return {
        "guid": entity.get("guid"),
        "typeName": entity.get("typeName"),
        "qualifiedName": qualified_name,
    }


def _build_lineage_process_entities(token: str):
    process_entities = []
    unresolved = []
    lookup_cache = {}
    started_at = time.time()

    def _cached_find(qualified_name: str):
        if qualified_name in lookup_cache:
            return lookup_cache[qualified_name]
        result = _find_entity_by_qualified_name(token, qualified_name)
        lookup_cache[qualified_name] = result
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

        source_entity = _cached_find(source_qn)
        target_entity = _cached_find(target_qn)

        if not source_entity or not target_entity:
            unresolved.append(
                {
                    "process_qualified_name": edge["process_qualified_name"],
                    "source": source_qn,
                    "target": target_qn,
                    "source_found": bool(source_entity),
                    "target_found": bool(target_entity),
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
    f"fail_on_token_error={fail_on_token_error}"
)

if publish_guard_active:
    print("[GUARD] SQL-mirror-only deployment is active. Set PURVIEW_PUBLISH_OVERRIDE=True for live Purview publish.")
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
        print("[Cell 6] Publishing classification typedefs...")
        typedef_status, typedef_body = _post_json("/catalog/api/atlas/v2/types/typedefs", token, typedef_payload)
        if typedef_status not in (200, 201) and "already exists" not in typedef_body.lower():
            raise RuntimeError(f"Classification typedef publish failed: HTTP {typedef_status} | {typedef_body[:500]}")
        print(f"Classification typedef publish result: HTTP {typedef_status}")

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

        print("[INFO] Asset classification attachment remains manifest-driven. Resolve asset GUIDs from scan results before applying live classifications.")

# Cell 6 complete: Classification typedefs and lineage processes published (or dry-run executed)
# G9-1 closure: Purview lineage graph modeling now has live Atlas publish step (no longer manifest-only)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
