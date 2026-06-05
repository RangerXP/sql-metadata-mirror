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

ANNOTATION_KEYS = {
    "cde": "CDE_Member_Of",
    "glossary": "Glossary_Term_References",
    "label": "Sensitivity_Label",
    "owner": "Data_Product_Owner",
}

print(f"Semantic model: {SEMANTIC_MODEL}")
print(f"Metadata source: {METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.*")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read metadata source tables

glossary_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.glossary_terms")
cde_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.cdes")
data_products_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.data_products")

# Optional table in case labels were ingested already.
try:
    labels_df = spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.label_assignments")
except Exception:
    labels_df = None
    print("[WARN] metadata.label_assignments not found; Sensitivity_Label rows will be sourced only from CDE metadata.")

print(f"glossary_terms rows: {glossary_df.count()}")
print(f"cdes rows: {cde_df.count()}")
print(f"data_products rows: {data_products_df.count()}")
if labels_df is not None:
    print(f"label_assignments rows: {labels_df.count()}")


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

# Cell 6: Write lh_metadata.metadata.sm_annotations (overwrite)

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

(
    annotations_sdf.write
    .mode("overwrite")
    .format("delta")
    .saveAsTable(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.sm_annotations")
)

print(f"sm_annotations rows written: {annotations_sdf.count()}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Summary by annotation key

summary_df = (
    spark.table(f"{METADATA_LAKEHOUSE}.{METADATA_SCHEMA}.sm_annotations")
    .groupBy("annotation_key")
    .agg(F.count("*").alias("annotation_count"))
    .orderBy("annotation_key")
)

display(summary_df)
