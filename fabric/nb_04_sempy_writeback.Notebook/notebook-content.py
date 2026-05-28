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

# Fabric Notebook: nb_04_sempy_writeback
# Gap: G3 - Metadata write-back to semantic model
# Purpose: Read curated metadata from lh_metadata and write table/column/measure
#          descriptions plus AI instructions into the semantic model using
#          SemPy (read) and SemPy Labs (write).
#
# DEMO_MODE = True  -> dry-run (prints write plan, no model mutation)
# DEMO_MODE = False -> live (applies SemPy Labs writes)

DEMO_MODE   = True
MODEL_NAME  = "BrookfieldEnercare"
METADATA_LH = "lh_metadata"

SEMANTIC_TABLE_METADATA_ALIASES = {
    "dim_customer": ["vw_customer_360", "customers"],
    "dim_equipment": ["vw_equipment_health", "equipment_registry"],
    "fct_contract_month": ["vw_monthly_revenue", "contracts"],
    "fct_service_request": ["vw_service_backlog", "service_requests"],
}

SEMANTIC_COLUMN_METADATA_ALIASES = {
    "dim_customer": {
        "CustomerKey": ["customer_id"],
        "AccountNumber": ["account_number"],
        "CustomerType": ["customer_type"],
        "Status": ["status"],
        "City": ["city"],
        "PostalCode": ["postal_code"],
        "CreatedDate": ["created_date"],
    },
    "dim_equipment": {
        "EquipmentKey": ["equipment_id"],
        "EquipmentType": ["equipment_type"],
        "Make": ["make"],
        "Model": ["model"],
        "SerialNumber": ["serial_number"],
        "OwnershipType": ["ownership_type"],
        "FuelType": ["fuel_type"],
        "InstallDate": ["install_date"],
        "AgeYears": ["age_years"],
        "IsUnderWarranty": ["is_under_warranty"],
    },
    "fct_contract_month": {
        "ContractKey": ["contract_id"],
        "ServiceAccountKey": ["service_account_id"],
        "ContractStatus": ["contract_status"],
        "MonthlyAmount": ["monthly_amount"],
        "IsNew": ["is_new"],
        "IsChurn": ["is_churn"],
    },
    "fct_service_request": {
        "RequestKey": ["request_id"],
        "RequestType": ["request_type"],
        "Priority": ["priority"],
        "Status": ["status"],
        "Description": ["description"],
        "TechnicianId": ["technician_id"],
        "IsSlaBreachFlag": ["is_sla_breach"],
    },
}

SEMANTIC_FALLBACK_TABLE_DESCRIPTIONS = {
    "dim_customer": "Enercare customer dimension. One row per customer account across Residential, Commercial, and MUR segments.",
    "dim_date": "Calendar date dimension used for daily, monthly, fiscal, and trend analysis.",
    "dim_equipment": "Equipment assets linked to service accounts for warranty, aging, and field-service analysis.",
    "dim_product": "Product dimension for rental, protection, heating, cooling, and smart-home offerings.",
    "dim_service_account": "Service account dimension representing service addresses, utility context, and lifecycle attributes.",
    "fct_billing": "Billing transactions used for revenue and payment-status analysis.",
    "fct_contract_month": "Contract month spine used for MRR, new business, and churn analysis.",
    "fct_service_request": "Service-request fact table with SLA, completion, and operational workflow attributes.",
}

print(f"nb_04_sempy_writeback | DEMO_MODE={DEMO_MODE}")
print(f"Target model: {MODEL_NAME}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Imports

import sempy.fabric as fabric

try:
    import sempy_labs as labs
except Exception as ex:
    labs = None
    print("[WARN] sempy_labs import failed.")
    print("       Install semantic-link-labs in this environment to run write-back.")
    print(f"       Detail: {ex}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read curated metadata from lh_metadata

meta_df = spark.sql(f"SELECT * FROM {METADATA_LH}.vw_business_metadata_current")
rows = meta_df.collect()


def _norm(value: str) -> str:
    return value.strip().lower()


def _dedupe_preserve_order(values):
    seen = set()
    result = []
    for value in values:
        if not value:
            continue
        key = _norm(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _table_candidates(table_name: str):
    return _dedupe_preserve_order([table_name] + SEMANTIC_TABLE_METADATA_ALIASES.get(table_name, []))


def _column_candidates(table_name: str, semantic_column: str):
    return _dedupe_preserve_order(
        [semantic_column] + SEMANTIC_COLUMN_METADATA_ALIASES.get(table_name, {}).get(semantic_column, [])
    )


table_descs = {
    _norm(r.ObjectKey): r.Description
    for r in rows
    if r.RecordCategory == "asset" and r.Description
}

col_descs = {}
for r in rows:
    if r.RecordCategory == "column" and r.Description and r.TriggerText and r.ObjectKey:
        tbl = r.ObjectKey.split(".")[0] if "." in r.ObjectKey else r.ObjectKey
        col_descs[(_norm(tbl), _norm(r.TriggerText))] = r.Description

try:
    kpi_df = spark.sql(
        f"SELECT KpiName, Description FROM {METADATA_LH}.kpi_metadata WHERE IsCertified = 1"
    )
    kpi_descs = {r.KpiName: r.Description for r in kpi_df.collect() if r.Description}
except Exception:
    kpi_descs = {}
    print("[WARN] kpi_metadata missing IsCertified/Description")

try:
    ai_df = spark.sql(
        f"SELECT ResponseText FROM {METADATA_LH}.ai_metadata"
        f" WHERE IsDraft = 0 AND RecordType = 'ai_instruction'"
    )
    ai_instructions = [r.ResponseText for r in ai_df.collect() if r.ResponseText]
except Exception:
    ai_instructions = []
    print("[WARN] ai_metadata not found")

print(f"Loaded: {len(table_descs)} table descriptions")
print(f"Loaded: {len(col_descs)} column descriptions")
print(f"Loaded: {len(kpi_descs)} certified KPI descriptions")
print(f"Loaded: {len(ai_instructions)} AI instructions")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Read semantic model inventory with SemPy

tables_df = fabric.list_tables(dataset=MODEL_NAME)
columns_df = fabric.list_columns(dataset=MODEL_NAME)
measures_df = fabric.list_measures(dataset=MODEL_NAME)

semantic_tables = sorted({str(r[0]) for r in tables_df.select("Name").collect()})
semantic_columns = sorted(
    {(str(r[0]), str(r[1])) for r in columns_df.select("Table Name", "Column Name").collect()}
)
semantic_measures = sorted(
    {(str(r[0]), str(r[1])) for r in measures_df.select("Table Name", "Measure Name").collect()}
)

print(f"SemPy inventory: {len(semantic_tables)} table(s), {len(semantic_columns)} column(s), {len(semantic_measures)} measure(s)")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Build write plan


def resolve_table_description(table_name: str):
    for candidate in _table_candidates(table_name):
        desc = table_descs.get(_norm(candidate))
        if desc:
            return desc, candidate
    fallback = SEMANTIC_FALLBACK_TABLE_DESCRIPTIONS.get(table_name)
    if fallback:
        return fallback, "fallback"
    return None, None


def resolve_column_description(table_name: str, semantic_column: str):
    for table_candidate in _table_candidates(table_name):
        for column_candidate in _column_candidates(table_name, semantic_column):
            desc = col_descs.get((_norm(table_candidate), _norm(column_candidate)))
            if desc:
                return desc, table_candidate, column_candidate
    return None, None, None


planned_table_updates = []
planned_column_updates = []
planned_measure_updates = []

for table_name in semantic_tables:
    desc, source_table = resolve_table_description(table_name)
    if desc:
        planned_table_updates.append((table_name, desc, source_table))

for table_name, column_name in semantic_columns:
    desc, source_table, source_column = resolve_column_description(table_name, column_name)
    if desc:
        planned_column_updates.append((table_name, column_name, desc, source_table, source_column))

for table_name, measure_name in semantic_measures:
    desc = kpi_descs.get(measure_name)
    if desc:
        planned_measure_updates.append((table_name, measure_name, desc))

annotation_payload = " | ".join(ai_instructions).strip()

print("SemPy write plan:")
print(f"  Tables  : {len(planned_table_updates)}")
print(f"  Columns : {len(planned_column_updates)}")
print(f"  Measures: {len(planned_measure_updates)}")
print(f"  Annotation payload present: {bool(annotation_payload)}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Apply SemPy Labs writes


def _set_object_description(table_name: str, object_type: str, object_name: str, description: str):
    method = getattr(labs, "set_object_description", None)
    if method is None:
        raise RuntimeError("SemPy Labs method set_object_description is not available")

    if object_type == "Table":
        return method(dataset=MODEL_NAME, table_name=table_name, description=description)

    if object_type == "Column":
        return method(dataset=MODEL_NAME, table_name=table_name, column_name=object_name, description=description)

    if object_type == "Measure":
        return method(dataset=MODEL_NAME, table_name=table_name, measure_name=object_name, description=description)

    raise ValueError(f"Unsupported object_type: {object_type}")


def _set_ai_annotation(value: str):
    method = getattr(labs, "set_semantic_model_annotation", None)
    if method is not None:
        return method(
            dataset=MODEL_NAME,
            annotation_name="PBI_AI_Instructions",
            annotation_value=value,
        )

    method = getattr(labs, "set_annotation", None)
    if method is not None:
        return method(
            dataset=MODEL_NAME,
            annotation_name="PBI_AI_Instructions",
            annotation_value=value,
        )

    raise RuntimeError("No supported SemPy Labs annotation writer found")


if DEMO_MODE:
    print("[DRY RUN] SemPy Labs writes skipped")
else:
    if labs is None:
        raise RuntimeError("DEMO_MODE=False requires sempy_labs to be installed")

    for table_name, description, source in planned_table_updates:
        _set_object_description(table_name, "Table", table_name, description)
        print(f"  [APPLIED] table   {table_name:<28} source={source}")

    for table_name, column_name, description, source_table, source_column in planned_column_updates:
        _set_object_description(table_name, "Column", column_name, description)
        print(f"  [APPLIED] column  {table_name}.{column_name:<20} source={source_table}.{source_column}")

    for table_name, measure_name, description in planned_measure_updates:
        _set_object_description(table_name, "Measure", measure_name, description)
        print(f"  [APPLIED] measure {table_name}.{measure_name}")

    if annotation_payload:
        _set_ai_annotation(annotation_payload)
        print(f"  [APPLIED] annotation PBI_AI_Instructions ({len(ai_instructions)} instruction(s))")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Summary

print("\n=== SemPy write-back summary ===")
print(f"  Model: {MODEL_NAME}")
print(f"  Table descriptions planned:   {len(planned_table_updates)}")
print(f"  Column descriptions planned:  {len(planned_column_updates)}")
print(f"  Measure descriptions planned: {len(planned_measure_updates)}")
print(f"  AI instructions available:    {len(ai_instructions)}")
print(f"  Status: {'DRY RUN' if DEMO_MODE else 'APPLIED'}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
