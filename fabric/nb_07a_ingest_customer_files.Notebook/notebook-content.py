# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
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

print(f"CSV root: {CSV_ROOT}")
print(f"Target schema: {TARGET_LAKEHOUSE}.{SCHEMA}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Validation helpers

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


def load_csv_as_pandas(filename: str) -> pd.DataFrame:
    path = f"{CSV_ROOT}/{filename}"
    sdf = spark.read.option("header", True).csv(path)
    return sdf.toPandas()


def write_table_from_pandas(df: pd.DataFrame, table_name: str) -> int:
    sdf = spark.createDataFrame(df)
    full_table = f"{TARGET_LAKEHOUSE}.{SCHEMA}.{table_name}"
    (
        sdf.write
        .mode("overwrite")
        .format("delta")
        .saveAsTable(full_table)
    )
    return int(sdf.count())


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: domain-charter.csv -> lh_metadata.metadata.domains

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

domains_df = load_csv_as_pandas("domain-charter.csv")
validate_csv(domains_df, domains_required, {"domain_type": domain_type_allowed})
count_domains = write_table_from_pandas(domains_df, "domains")
print(f"domains loaded: {count_domains}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: data-product-catalog.csv -> lh_metadata.metadata.data_products

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

data_products_df = load_csv_as_pandas("data-product-catalog.csv")
validate_csv(data_products_df, data_products_required, {"product_type": product_type_allowed})
count_data_products = write_table_from_pandas(data_products_df, "data_products")
print(f"data_products loaded: {count_data_products}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: glossary-master.csv -> lh_metadata.metadata.glossary_terms

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

glossary_df = load_csv_as_pandas("glossary-master.csv")
validate_csv(glossary_df, glossary_required)
count_glossary = write_table_from_pandas(glossary_df, "glossary_terms")
print(f"glossary_terms loaded: {count_glossary}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: cde-catalog.csv -> lh_metadata.metadata.cdes

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

cde_df = load_csv_as_pandas("cde-catalog.csv")
validate_csv(cde_df, cde_required, {"expected_data_type": expected_type_allowed})
count_cdes = write_table_from_pandas(cde_df, "cdes")
print(f"cdes loaded: {count_cdes}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: role-directory.csv -> lh_metadata.metadata.role_assignments

roles_required = [
    "role_id",
    "principal_email",
    "principal_display_name",
    "role_type",
    "scope_target",
    "scope_target_type",
    "governance_layer",
]

roles_df = load_csv_as_pandas("role-directory.csv")
validate_csv(roles_df, roles_required)
count_roles = write_table_from_pandas(roles_df, "role_assignments")
print(f"role_assignments loaded: {count_roles}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 8: label-policy.csv -> lh_metadata.metadata.label_assignments

labels_required = [
    "label_id",
    "label_name",
    "sensitivity_tier",
    "protection_policy",
    "applies_to_asset_ids",
    "scope",
]

labels_df = load_csv_as_pandas("label-policy.csv")
validate_csv(labels_df, labels_required)
count_labels = write_table_from_pandas(labels_df, "label_assignments")
print(f"label_assignments loaded: {count_labels}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 9: Summary counts (expected vs actual)

summary_query = """
SELECT 'domains' AS t, COUNT(*) AS actual, 3 AS expected FROM lh_metadata.metadata.domains
UNION ALL
SELECT 'data_products' AS t, COUNT(*) AS actual, 3 AS expected FROM lh_metadata.metadata.data_products
UNION ALL
SELECT 'glossary_terms' AS t, COUNT(*) AS actual, 35 AS expected FROM lh_metadata.metadata.glossary_terms
UNION ALL
SELECT 'cdes' AS t, COUNT(*) AS actual, 12 AS expected FROM lh_metadata.metadata.cdes
UNION ALL
SELECT 'role_assignments' AS t, COUNT(*) AS actual, 48 AS expected FROM lh_metadata.metadata.role_assignments
UNION ALL
SELECT 'label_assignments' AS t, COUNT(*) AS actual, 9 AS expected FROM lh_metadata.metadata.label_assignments
ORDER BY t
"""

summary_df = spark.sql(summary_query).withColumn(
    "status",
    F.when(F.col("actual") == F.col("expected"), F.lit("GREEN")).otherwise(F.lit("YELLOW")),
)

display(summary_df)
