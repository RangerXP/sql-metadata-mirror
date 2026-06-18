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

import re
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

spark = SparkSession.builder.getOrCreate()

METADATA_LAKEHOUSE = "lh_metadata"
METADATA_SCHEMA = "metadata"
SEMANTIC_MODEL = "BrookfieldEnercare"
REQUIRED_METADATA_TABLES = {
    "glossary_terms": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.glossary_terms",
    "cdes": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.cdes",
    "data_products": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.data_products",
    "label_assignments": f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.label_assignments",
}

TABLE_NAME_ALIASES = {
    "glossary_terms": ["glossary_terms", "governance_glossary_terms", "metadata_glossary_terms"],
    "cdes": ["cdes", "governance_cdes", "metadata_cdes"],
    "data_products": ["data_products", "governance_data_products", "metadata_data_products"],
    "label_assignments": ["label_assignments", "governance_label_assignments", "metadata_label_assignments"],
}

ANNOTATION_KEYS = {
    "cde": "CDE_Member_Of",
    "glossary": "Glossary_Term_References",
    "label": "Sensitivity_Label",
    "owner": "Data_Product_Owner",
}

print(f"Semantic model: {SEMANTIC_MODEL}")
print(f"Required metadata schema: {METADATA_LAKEHOUSE}.{METADATA_SCHEMA}")


def _table_candidates(table_name: str):
    required_name = REQUIRED_METADATA_TABLES.get(table_name)
    if not required_name:
        raise ValueError(f"Unknown required metadata table key: {table_name}")

    aliases = TABLE_NAME_ALIASES.get(table_name, [table_name])
    candidates = []

    # Try 3-part then 2-part then unqualified names to tolerate catalog/schema drift.
    for alias in aliases:
        candidates.extend([
            f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.{alias}",
            f"{METADATA_SCHEMA}.{alias}",
            alias,
        ])

    # Deduplicate while preserving order.
    deduped = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)

    return deduped


def _read_table(table_name: str):
    last_error = None
    candidates = _table_candidates(table_name)
    for candidate in candidates:
        try:
            return spark.table(candidate), candidate
        except Exception as ex:
            last_error = ex

    raise RuntimeError(
        f"Could not resolve table '{table_name}'. "
        f"Candidates tried: {candidates}. "
        f"Last error: {last_error}. "
        "Required source: lh_metadata staged tables (schema-qualified or unqualified). "
        "Prerequisite: run nb_07a_ingest_customer_files first to populate "
        "glossary_terms/cdes/data_products (and optionally label_assignments) in lh_metadata."
    )


def _write_table_name(table_name: str):
    # Use two-part name for Fabric Spark catalog compatibility.
    return f"{METADATA_SCHEMA}.{table_name}"


WRITTEN_TABLE_NAMES: dict[str, str] = {}


def _write_table_candidates(table_name: str):
    return [f"{METADATA_SCHEMA}.{table_name}", table_name]


def _write_with_fallback(sdf, table_name: str):
    last_error = None
    for candidate in _write_table_candidates(table_name):
        try:
            (
                sdf.write
                .mode("overwrite")
                .format("delta")
                .saveAsTable(candidate)
            )
            WRITTEN_TABLE_NAMES[table_name] = candidate
            return candidate
        except Exception as ex:
            last_error = ex

    raise RuntimeError(
        f"Could not write table '{table_name}'. Candidates tried: {_write_table_candidates(table_name)}. Last error: {last_error}"
    )


def _resolve_written_table_name(table_name: str):
    return WRITTEN_TABLE_NAMES.get(table_name, _write_table_name(table_name))


def _require_lakehouse_context():
    try:
        # A simple command that requires an attached default lakehouse context.
        spark.sql("SELECT current_database()").collect()
    except Exception as ex:
        raise RuntimeError(
            "No default lakehouse context is attached for this Spark session. "
            "Attach 'lh_metadata' as the default lakehouse for this notebook, then rerun Cell 1 and Cell 2. "
            "In Fabric: open the notebook Lakehouse selector and set default lakehouse to lh_metadata. "
            f"Original error: {ex}"
        )


print(f"Required metadata tables: {REQUIRED_METADATA_TABLES}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read metadata source tables

print("[Cell 2] Starting metadata source reads...", flush=True)
_require_lakehouse_context()
print("[Cell 2] Lakehouse context check passed.", flush=True)

glossary_df, glossary_source = _read_table("glossary_terms")
print(f"[Cell 2] Resolved glossary_terms source: {glossary_source}", flush=True)

cde_df, cde_source = _read_table("cdes")
print(f"[Cell 2] Resolved cdes source: {cde_source}", flush=True)

data_products_df, data_products_source = _read_table("data_products")
print(f"[Cell 2] Resolved data_products source: {data_products_source}", flush=True)

# Optional table in case labels were ingested already.
try:
    labels_df, labels_source = _read_table("label_assignments")
    print(f"[Cell 2] Resolved label_assignments source: {labels_source}", flush=True)
except Exception:
    labels_df = None
    labels_source = None
    print("[WARN] metadata.label_assignments not found; Sensitivity_Label rows will be sourced only from CDE metadata.", flush=True)


def _safe_count(name, df):
    try:
        return df.count()
    except Exception as ex:
        print(f"[WARN] Could not count {name}: {ex}", flush=True)
        return None

print(f"glossary_terms rows: {_safe_count('glossary_terms', glossary_df)} (source={glossary_source})", flush=True)
print(f"cdes rows: {_safe_count('cdes', cde_df)} (source={cde_source})", flush=True)
print(f"data_products rows: {_safe_count('data_products', data_products_df)} (source={data_products_source})", flush=True)
if labels_df is not None:
    print(f"label_assignments rows: {_safe_count('label_assignments', labels_df)} (source={labels_source})", flush=True)

print("[Cell 2] Metadata source reads completed.", flush=True)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read semantic inventory with SemPy

import sempy.fabric as fabric


def _collect_pairs(df, columns):
    if hasattr(df, "select") and hasattr(df, "collect"):
        return [tuple(row[c] for c in columns) for row in df.select(*columns).collect()]
    if hasattr(df, "iterrows"):
        return [tuple(row[c] for c in columns) for _, row in df.iterrows()]
    raise TypeError(f"Unsupported DataFrame type returned by SemPy: {type(df)}")


tables_df = fabric.list_tables(dataset=SEMANTIC_MODEL)
columns_df = fabric.list_columns(dataset=SEMANTIC_MODEL)
measures_df = fabric.list_measures(dataset=SEMANTIC_MODEL)

semantic_tables = sorted({str(name) for (name,) in _collect_pairs(tables_df, ["Name"])})
semantic_columns = sorted({(str(t), str(c)) for t, c in _collect_pairs(columns_df, ["Table Name", "Column Name"])})
semantic_measures = sorted({(str(t), str(m)) for t, m in _collect_pairs(measures_df, ["Table Name", "Measure Name"])})

print(f"SemPy inventory: {len(semantic_tables)} table(s), {len(semantic_columns)} column(s), {len(semantic_measures)} measure(s)")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Parse bound asset formats and build lookup maps


def _norm(value: str) -> str:
    return value.strip().lower()


def _split_bindings(raw: str):
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []

    pieces = re.split(r"[;,|\n]", text)
    return [p.strip() for p in pieces if p and p.strip()]


def _parse_asset_ref(token: str):
    # Formats supported:
    # - dbo.table.column
    # - dbo.table
    # - BrookfieldEnercare/table/column
    # - BrookfieldEnercare/_Measures/Measure Name
    source = token.strip()
    lower = source.lower()

    if "/" in source:
        parts = [p.strip() for p in source.split("/") if p.strip()]
        if len(parts) >= 3 and parts[0].lower() == SEMANTIC_MODEL.lower():
            if parts[1] == "_Measures":
                return {"kind": "Measure", "table": "_Measures", "object": parts[2], "source": source}
            return {"kind": "Column", "table": parts[1], "object": parts[2], "source": source}
        if len(parts) == 2 and parts[0].lower() == SEMANTIC_MODEL.lower():
            return {"kind": "Table", "table": parts[1], "object": parts[1], "source": source}

    if lower.startswith("dbo."):
        dotted = source.split(".")
        if len(dotted) >= 3:
            return {
                "kind": "SqlColumn",
                "table": dotted[1],
                "object": ".".join(dotted[2:]),
                "source": source,
            }
        if len(dotted) == 2:
            return {"kind": "SqlTable", "table": dotted[1], "object": dotted[1], "source": source}

    return {"kind": "Unknown", "table": None, "object": source, "source": source}


columns_by_name = {}
for table_name, column_name in semantic_columns:
    key = _norm(column_name)
    columns_by_name.setdefault(key, []).append((table_name, column_name))

measures_by_name = {}
for table_name, measure_name in semantic_measures:
    key = _norm(measure_name)
    measures_by_name.setdefault(key, []).append((table_name, measure_name))


def _resolve_targets(parsed_asset):
    kind = parsed_asset["kind"]

    if kind == "Column":
        key = (_norm(parsed_asset["table"]), _norm(parsed_asset["object"]))
        matches = [
            (t, c)
            for t, c in semantic_columns
            if _norm(t) == key[0] and _norm(c) == key[1]
        ]
        return [("Column", t, c) for t, c in matches]

    if kind == "Measure":
        matches = [
            (t, m)
            for t, m in semantic_measures
            if _norm(m) == _norm(parsed_asset["object"]) and (t == parsed_asset["table"] or parsed_asset["table"] == "_Measures")
        ]
        if not matches:
            matches = measures_by_name.get(_norm(parsed_asset["object"]), [])
        return [("Measure", t, m) for t, m in matches]

    if kind == "SqlColumn":
        return [("Column", t, c) for t, c in columns_by_name.get(_norm(parsed_asset["object"]), [])]

    return []


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Build annotation rows

annotation_rows = []


def _append_annotation(targets, key_name, value):
    if value is None:
        return
    value_text = str(value).strip()
    if not value_text:
        return

    for object_type, table_name, object_name in targets:
        annotation_rows.append(
            {
                "model": SEMANTIC_MODEL,
                "table": table_name,
                "object_type": object_type,
                "object_name": object_name,
                "annotation_key": key_name,
                "annotation_value": value_text,
            }
        )


for row in glossary_df.collect():
    term_code = getattr(row, "term_code", None) or getattr(row, "term_name", None)
    term_name = getattr(row, "term_name", None)
    glossary_value = " | ".join([v for v in [term_code, term_name] if v])
    for token in _split_bindings(getattr(row, "bound_assets", None)):
        parsed = _parse_asset_ref(token)
        targets = _resolve_targets(parsed)
        _append_annotation(targets, ANNOTATION_KEYS["glossary"], glossary_value)

for row in cde_df.collect():
    cde_id = getattr(row, "cde_id", None) or getattr(row, "cde_code", None) or getattr(row, "cde_name", None)
    cde_name = getattr(row, "cde_name", None)
    cde_value = " | ".join([v for v in [cde_id, cde_name] if v])
    sensitivity = getattr(row, "sensitivity_label", None)

    for token in _split_bindings(getattr(row, "bound_columns", None)):
        parsed = _parse_asset_ref(token)
        targets = _resolve_targets(parsed)
        _append_annotation(targets, ANNOTATION_KEYS["cde"], cde_value)
        _append_annotation(targets, ANNOTATION_KEYS["label"], sensitivity)

if labels_df is not None:
    for row in labels_df.collect():
        label_name = getattr(row, "label_name", None)
        applies_to = getattr(row, "applies_to_asset_ids", None)
        for token in _split_bindings(applies_to):
            parsed = _parse_asset_ref(token)
            targets = _resolve_targets(parsed)
            _append_annotation(targets, ANNOTATION_KEYS["label"], label_name)

for row in data_products_df.collect():
    product_id = getattr(row, "data_product_id", None) or getattr(row, "product_code", None)
    owner = getattr(row, "owners", None) or getattr(row, "owner_upn", None) or getattr(row, "owner_name", None)

    owner_value_parts = [v for v in [product_id, owner] if v]
    owner_value = " | ".join(owner_value_parts)

    binding_fields = [
        getattr(row, "attached_assets", None),
        getattr(row, "semantic_model_assets", None),
        getattr(row, "fabric_assets", None),
        getattr(row, "sql_assets", None),
    ]
    binding_tokens = []
    for raw in binding_fields:
        binding_tokens.extend(_split_bindings(raw))

    for token in binding_tokens:
        parsed = _parse_asset_ref(token)
        targets = _resolve_targets(parsed)
        _append_annotation(targets, ANNOTATION_KEYS["owner"], owner_value)

print(f"Raw annotation rows created: {len(annotation_rows)}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Write sm_annotations (overwrite with schema fallback)

annotation_schema = StructType(
    [
        StructField("model", StringType(), False),
        StructField("table", StringType(), False),
        StructField("object_type", StringType(), False),
        StructField("object_name", StringType(), False),
        StructField("annotation_key", StringType(), False),
        StructField("annotation_value", StringType(), False),
    ]
)

annotations_sdf = spark.createDataFrame(annotation_rows, annotation_schema)
annotations_sdf = annotations_sdf.dropDuplicates(
    ["model", "table", "object_type", "object_name", "annotation_key", "annotation_value"]
)

written_sm_annotations_table = _write_with_fallback(annotations_sdf, "sm_annotations")

print(f"sm_annotations rows written: {annotations_sdf.count()}")
print(f"sm_annotations target table: {written_sm_annotations_table}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Summary by annotation key

summary_df = (
    spark.table(_resolve_written_table_name("sm_annotations"))
    .groupBy("annotation_key")
    .agg(F.count("*").alias("annotation_count"))
    .orderBy("annotation_key")
)

display(summary_df)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
