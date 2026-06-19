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

# Cell 1: Config and imports

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

CSV_ROOT = "/lakehouse/default/Files/purview"
SCHEMA = "metadata"
TARGET_LAKEHOUSE = "lh_metadata"
SOURCE_MODE = "sql_mirror"

# SQL-first lookup order for metadata source tables in mirrored SQL.
SQL_MIRROR_CATALOGS = ["sqldemo", "sqldemo_mirror", "sqldemo-mirror"]
SQL_MIRROR_SCHEMAS = ["dbo", "metadata"]
MIRROR_WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
# Keep both IDs to tolerate environment drift between mirror item GUID and logicalId.
MIRROR_ITEM_IDS = [
    "bdf616e8-625e-4b62-8491-519509f6ffaf",
    "09f6ffaf-5195-8491-4b62-625ebdf616e8",
]
MIRROR_DFS_HOSTS = [
    "onelake.dfs.fabric.microsoft.com",
    "westus3-onelake.dfs.fabric.microsoft.com",
]

SQL_SOURCE_TABLES = {
    "domains": ["governance_domains", "metadata_domains"],
    "data_products": ["governance_data_products", "metadata_data_products"],
    "glossary_terms": ["governance_glossary_terms", "metadata_glossary_terms"],
    "cdes": ["governance_cdes", "metadata_cdes"],
    "role_assignments": ["governance_role_assignments", "metadata_role_assignments"],
    "label_assignments": ["governance_label_assignments", "metadata_label_assignments"],
}

print(f"CSV root: {CSV_ROOT}")
print(f"Target schema: {TARGET_LAKEHOUSE}.{SCHEMA}")
print(f"Source mode: {SOURCE_MODE}")

if SOURCE_MODE != "sql_mirror":
    raise ValueError("nb_07a is configured for sql_mirror-only ingestion. Set SOURCE_MODE='sql_mirror'.")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Validation helpers

print("[Cell 2] Initializing validation and source-resolution helpers...", flush=True)
print(
    f"[Cell 2] Source mode={SOURCE_MODE}; mirror catalogs={SQL_MIRROR_CATALOGS}; mirror schemas={SQL_MIRROR_SCHEMAS}",
    flush=True,
)
print(
    f"[Cell 2] Mirror path resolution enabled: workspace={MIRROR_WORKSPACE_ID}, item_ids={MIRROR_ITEM_IDS}",
    flush=True,
)

def validate_csv(df: pd.DataFrame, required_cols: list[str], enum_cols: dict[str, set[str]] | None = None) -> None:
    actual_cols = set(df.columns)
    missing = [c for c in required_cols if c not in actual_cols]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    enum_cols = enum_cols or {}
    for col_name, allowed in enum_cols.items():
        if col_name not in actual_cols:
            raise ValueError(f"Enum column not found: {col_name}")
        observed = set(df[col_name].dropna().astype(str).str.strip().unique())
        invalid = sorted(v for v in observed if v and v not in allowed)
        if invalid:
            raise ValueError(
                f"Column '{col_name}' has invalid enum values: {invalid}. "
                f"Allowed: {sorted(allowed)}"
            )


def try_load_sql_dataset(dataset_name: str) -> tuple[pd.DataFrame | None, str | None]:
    table_candidates = SQL_SOURCE_TABLES.get(dataset_name, [])
    attempted_names = []
    seen_names = set()

    def _identifier_variants(catalog: str, schema_name: str, table_name: str):
        return [
            f"{catalog}.{schema_name}.{table_name}",
            f"`{catalog}`.{schema_name}.{table_name}",
            f"`{catalog}`.`{schema_name}`.`{table_name}`",
        ]

    def _try_table(full_name: str):
        if full_name in seen_names:
            return None
        seen_names.add(full_name)
        attempted_names.append(full_name)
        try:
            sdf = spark.table(full_name)
            return sdf.toPandas(), full_name
        except Exception:
            return None

    for catalog in SQL_MIRROR_CATALOGS:
        for schema_name in SQL_MIRROR_SCHEMAS:
            for table_name in table_candidates:
                for full_name in _identifier_variants(catalog, schema_name, table_name):
                    loaded = _try_table(full_name)
                    if loaded is not None:
                        return loaded

    # Mirror tables may be readable only via Delta paths, depending on Spark catalog registration.
    for host in MIRROR_DFS_HOSTS:
        for item_id in MIRROR_ITEM_IDS:
            for schema_name in SQL_MIRROR_SCHEMAS:
                for table_name in table_candidates:
                    delta_path = (
                        f"abfss://{MIRROR_WORKSPACE_ID}@{host}/"
                        f"{item_id}/Tables/{schema_name}/{table_name}"
                    )
                    source_name = f"delta.`{delta_path}`"
                    attempted_names.append(source_name)
                    try:
                        sdf = spark.read.format("delta").load(delta_path)
                        return sdf.toPandas(), source_name
                    except Exception:
                        continue

    print(
        f"[Cell 2] SQL lookup miss for '{dataset_name}'. Attempted: {attempted_names}",
        flush=True,
    )
    return None, None


def load_metadata_dataset(dataset_name: str) -> tuple[pd.DataFrame, str]:
    sql_df, source_name = try_load_sql_dataset(dataset_name)
    if sql_df is not None:
        return sql_df, f"sql:{source_name}"

    raise ValueError(
        f"Mirrored metadata table for '{dataset_name}' was not found. "
        f"Checked catalogs={SQL_MIRROR_CATALOGS}, schemas={SQL_MIRROR_SCHEMAS}, candidates={SQL_SOURCE_TABLES.get(dataset_name, [])}. "
        "Prerequisite SQL objects appear missing from the mirrored source. "
        "Ensure sql/06_purview_metadata_schema.sql and sql/07_seed_purview_metadata.sql have been executed against sub2 Azure SQL, "
        "then refresh/confirm sqldemo mirror sync before rerunning nb_07a. "
        "nb_07a is SQL-mirror-only by design; direct CSV fallback is intentionally disabled."
    )


WRITTEN_TABLE_NAMES: dict[str, str] = {}


def write_table_from_pandas(df: pd.DataFrame, table_name: str) -> int:
    sdf = spark.createDataFrame(df)
    table_candidates = [f"{SCHEMA}.{table_name}", table_name]
    last_error = None
    for full_table in table_candidates:
        try:
            (
                sdf.write
                .mode("overwrite")
                .format("delta")
                .saveAsTable(full_table)
            )
            WRITTEN_TABLE_NAMES[table_name] = full_table
            return int(sdf.count())
        except Exception as ex:
            last_error = ex
            continue

    raise RuntimeError(
        f"Unable to write table '{table_name}'. Tried {table_candidates}. Last error: {last_error}"
    )


def resolve_written_table_name(table_name: str) -> str:
    return WRITTEN_TABLE_NAMES.get(table_name, f"{SCHEMA}.{table_name}")


def summary_count_select(table_name: str, expected: int) -> str:
    resolved = resolve_written_table_name(table_name)
    return f"SELECT '{table_name}' AS t, COUNT(*) AS actual, {expected} AS expected FROM {resolved}"


def build_summary_query() -> str:
    checks = [
        ("domains", 3),
        ("data_products", 3),
        ("glossary_terms", 35),
        ("cdes", 12),
        ("role_assignments", 48),
        ("label_assignments", 9),
    ]
    return "\nUNION ALL\n".join(summary_count_select(name, expected) for name, expected in checks) + "\nORDER BY t"


print(f"[Cell 2] Helpers ready. SQL dataset keys: {sorted(SQL_SOURCE_TABLES.keys())}", flush=True)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: domain-charter.csv -> metadata.domains

domains_required = [
    "domain_id",
    "domain_name",
    "domain_type",
    "description",
    "parent_domain",
    "status",
    "governance_domain_owners",
    "governance_domain_creators",
]

domain_type_allowed = {
    "Data domain",
    "Functional unit",
    "Line of business",
    "Regulatory",
    "Project",
}

domains_df, domains_source = load_metadata_dataset("domains")
validate_csv(domains_df, domains_required, {"domain_type": domain_type_allowed})
count_domains = write_table_from_pandas(domains_df, "domains")
print(f"domains loaded: {count_domains} (source={domains_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: data-product-catalog.csv -> metadata.data_products

data_products_required = [
    "data_product_id",
    "data_product_name",
    "product_type",
    "business_use_case",
    "audience",
    "owners",
    "attached_assets",
    "access_policy",
    "status",
    "parent_domain_id",
]

product_type_allowed = {
    "Dataset",
    "Dashboards/Reports",
    "Master and reference data",
}

data_products_df, data_products_source = load_metadata_dataset("data_products")
validate_csv(data_products_df, data_products_required, {"product_type": product_type_allowed})
count_data_products = write_table_from_pandas(data_products_df, "data_products")
print(f"data_products loaded: {count_data_products} (source={data_products_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: glossary-master.csv -> metadata.glossary_terms

glossary_required = [
    "term_code",
    "term_name",
    "acronyms",
    "parent_term_code",
    "domain_code",
    "owner_upn",
    "additional_owners_upn",
    "definition",
    "status",
    "is_cde",
    "industry_origin",
    "resources",
    "bound_assets",
]

glossary_df, glossary_source = load_metadata_dataset("glossary_terms")
validate_csv(glossary_df, glossary_required)
count_glossary = write_table_from_pandas(glossary_df, "glossary_terms")
print(f"glossary_terms loaded: {count_glossary} (source={glossary_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: cde-catalog.csv -> metadata.cdes

cde_required = [
    "cde_id",
    "cde_name",
    "expected_data_type",
    "business_definition",
    "owner_role",
    "status",
    "parent_glossary_term",
    "bound_columns",
]

expected_type_allowed = {"number", "text", "date", "Boolean"}

cde_df, cde_source = load_metadata_dataset("cdes")
validate_csv(cde_df, cde_required, {"expected_data_type": expected_type_allowed})
count_cdes = write_table_from_pandas(cde_df, "cdes")
print(f"cdes loaded: {count_cdes} (source={cde_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: role-directory.csv -> metadata.role_assignments

roles_required = [
    "role_id",
    "principal_email",
    "principal_display_name",
    "role_type",
    "scope_target",
    "scope_target_type",
    "governance_layer",
]

roles_df, roles_source = load_metadata_dataset("role_assignments")
validate_csv(roles_df, roles_required)
count_roles = write_table_from_pandas(roles_df, "role_assignments")
print(f"role_assignments loaded: {count_roles} (source={roles_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 8: label-policy.csv -> metadata.label_assignments

labels_required = [
    "label_id",
    "label_name",
    "sensitivity_tier",
    "protection_policy",
    "applies_to_asset_ids",
    "scope",
]

labels_df, labels_source = load_metadata_dataset("label_assignments")
validate_csv(labels_df, labels_required)
count_labels = write_table_from_pandas(labels_df, "label_assignments")
print(f"label_assignments loaded: {count_labels} (source={labels_source})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 9: Summary counts (expected vs actual)

summary_query = build_summary_query()

summary_df = spark.sql(summary_query).withColumn(
    "status",
    F.when(F.col("actual") == F.col("expected"), F.lit("GREEN")).otherwise(F.lit("YELLOW")),
)

display(summary_df)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
