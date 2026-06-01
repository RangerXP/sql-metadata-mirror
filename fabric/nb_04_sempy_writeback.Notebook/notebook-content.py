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

# Fabric Notebook: nb_04_sempy_writeback
# Gap: G3 - Metadata write-back to semantic model
# Purpose: Read curated metadata from lh_metadata and write table/column/measure
#          descriptions plus AI instructions into the semantic model using
#          SemPy (read) and SemPy Labs (write).
#
# DEMO_MODE = True  -> dry-run (prints write plan, no model mutation)
# DEMO_MODE = False -> live (applies SemPy Labs writes)

DEMO_MODE   = False
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

# Optional overrides to map semantic measure names to KPI names/codes.
# Add entries here when a measure name does not naturally match kpi_metadata.
SEMANTIC_MEASURE_METADATA_ALIASES = {
    "_Measures": {
        # Add/adjust entries as needed for your KPI naming conventions.
        "Active Contract Count": ["Active Contracts", "ACTIVE_CONTRACTS", "KPI_ACTIVE_CONTRACTS"],
        "Active Customer Count": ["Active Customers", "ACTIVE_CUSTOMERS", "KPI_ACTIVE_CUSTOMERS"],
        "Avg Equipment Age Years": ["Equipment Age", "AVG_EQUIPMENT_AGE", "KPI_AVG_EQUIPMENT_AGE"],
        "Avg Handle Time (sec)": ["AHT", "AVG_HANDLE_TIME", "KPI_AHT"],
        "Avg Lifetime Value": ["LTV", "AVG_LIFETIME_VALUE", "KPI_LTV"],
        "Avg Tenure Months": ["Tenure", "AVG_TENURE_MONTHS", "KPI_AVG_TENURE_MONTHS"],
        "Churned MRR": ["Churn MRR", "MRR_CHURN", "KPI_CHURNED_MRR"],
        "Escalation Rate": ["Escalation", "ESCALATION_RATE", "KPI_ESCALATION_RATE"],
        "FCR Rate": ["FCR", "FIRST_CALL_RESOLUTION", "KPI_FCR"],
        "Avg CSAT": ["CSAT", "CUSTOMER_SATISFACTION", "KPI_CSAT"],
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

fabric = None
fabric_import_error = None

print("[INFO] sempy.fabric import deferred to Cell 4 (semantic inventory step).")

try:
    import sempy_labs as labs
except Exception as ex:
    labs = None

    if DEMO_MODE is False:
        print("[WARN] sempy_labs import failed.")
        print("       Install semantic-link-labs in this Fabric environment, then restart the notebook session.")
        print(f"       Detail: {ex}")
    else:
        print("[INFO] sempy_labs not installed. DEMO_MODE=True so write-back remains dry-run.")

EFFECTIVE_DEMO_MODE = DEMO_MODE or labs is None
if DEMO_MODE is False and labs is None:
    print("[WARN] DEMO_MODE=False requested, but sempy_labs is unavailable.")
    print("       Forcing dry-run mode for this execution.")

print(f"Cell 2 status: sempy_labs_loaded={labs is not None}, effective_demo_mode={EFFECTIVE_DEMO_MODE}")
print(f"Cell 2 status: sempy_fabric_loaded={fabric is not None}")



# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read curated metadata from lh_metadata

meta_df = spark.sql(f"SELECT * FROM {METADATA_LH}.vw_business_metadata_current")
rows = meta_df.collect()
print(f"Cell 3 status: loaded {len(rows)} row(s) from {METADATA_LH}.vw_business_metadata_current")


def _norm(value: str) -> str:
    return value.strip().lower()


def _norm_measure_key(value: str) -> str:
    # Normalize KPI/measure names across spaces, underscores, and case.
    return "".join(ch for ch in value.strip().lower() if ch.isalnum())


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
        f"""
        SELECT KpiName, KPICode, Description
        FROM {METADATA_LH}.kpi_metadata
        WHERE IsCertified = 1
        """
    )

    # Build a robust lookup so semantic measures can match by KPI name or KPI code.
    kpi_descs = {}
    kpi_rows = [r for r in kpi_df.collect() if r.Description]
    for r in kpi_rows:
        if r.KpiName:
            kpi_descs[r.KpiName] = r.Description
            kpi_descs[_norm_measure_key(r.KpiName)] = r.Description
        if r.KPICode:
            kpi_descs[r.KPICode] = r.Description
            kpi_descs[_norm_measure_key(r.KPICode)] = r.Description
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


def _first_non_empty_value(data, keys):
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


SEMANTIC_MEASURE_METADATA_ALIASES_RUNTIME = {"_Measures": {}}
_measure_alias_source_table = None

for candidate_table in [
    f"{METADATA_LH}.semantic_measure_kpi_map",
    f"{METADATA_LH}.measure_kpi_map",
    f"{METADATA_LH}.kpi_measure_map",
]:
    try:
        mapping_rows = [r.asDict(recursive=True) for r in spark.table(candidate_table).collect()]
        _measure_alias_source_table = candidate_table

        for raw_row in mapping_rows:
            row = {str(k).lower(): v for k, v in raw_row.items()}

            is_active = row.get("isactive", row.get("is_active", True))
            if is_active in (0, "0", False, "false", "False"):
                continue

            table_name = _first_non_empty_value(row, ["semantictablename", "table_name", "tablename"]) or "_Measures"
            measure_name = _first_non_empty_value(
                row,
                ["semanticmeasurename", "semantic_measure_name", "measurename", "measure_name"],
            )

            if not measure_name:
                continue

            alias_values = [
                _first_non_empty_value(row, ["kpiname", "kpi_name"]),
                _first_non_empty_value(row, ["kpicode", "kpi_code"]),
                _first_non_empty_value(row, ["alias", "aliasname", "alias_name"]),
            ]
            alias_values = [v for v in alias_values if v]
            if not alias_values:
                continue

            table_aliases = SEMANTIC_MEASURE_METADATA_ALIASES_RUNTIME.setdefault(table_name, {})
            existing = table_aliases.get(measure_name, [])
            table_aliases[measure_name] = _dedupe_preserve_order(existing + alias_values)

        break
    except Exception:
        continue

if _measure_alias_source_table:
    dynamic_pairs = sum(len(v) for v in SEMANTIC_MEASURE_METADATA_ALIASES_RUNTIME.values())
    print(f"Loaded dynamic measure alias mapping from {_measure_alias_source_table} ({dynamic_pairs} measure row(s))")
else:
    print("[INFO] No dynamic measure alias mapping table found; using in-code aliases.")

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

semantic_tables = []
semantic_columns = []
semantic_measures = []

if fabric is None:
    print("Cell 4 status: importing sempy.fabric...")
    try:
        import sempy.fabric as fabric
        print("Cell 4 status: sempy.fabric import succeeded")
    except Exception as ex:
        fabric = None
        fabric_import_error = ex
        tables_df = None
        columns_df = None
        measures_df = None
        print("[WARN] sempy.fabric import failed.")
        print("       Semantic model inventory/read operations will be skipped.")
        print(f"       Detail: {ex}")

if fabric is None:
    tables_df = None
    columns_df = None
    measures_df = None
    print("Cell 4 status: sempy.fabric unavailable; inventory skipped")
else:
    tables_df = fabric.list_tables(dataset=MODEL_NAME)
    columns_df = fabric.list_columns(dataset=MODEL_NAME)
    measures_df = fabric.list_measures(dataset=MODEL_NAME)
    print(
        "Cell 4 status: inventory fetched "
        f"(tables_df={type(tables_df).__name__}, columns_df={type(columns_df).__name__}, measures_df={type(measures_df).__name__})"
    )

def _collect_pairs(df, columns):
    # SemPy can return Spark or pandas DataFrames depending on runtime.
    if hasattr(df, "select") and hasattr(df, "collect"):
        return [tuple(row[c] for c in columns) for row in df.select(*columns).collect()]

    if hasattr(df, "iterrows"):
        return [tuple(row[c] for c in columns) for _, row in df.iterrows()]

    raise TypeError(f"Unsupported dataframe type from SemPy: {type(df)}")


if fabric is not None:
    semantic_tables = sorted({str(name) for (name,) in _collect_pairs(tables_df, ["Name"])})
    semantic_columns = sorted(
        {(str(table_name), str(column_name)) for table_name, column_name in _collect_pairs(columns_df, ["Table Name", "Column Name"]) }
    )
    semantic_measures = sorted(
        {(str(table_name), str(measure_name)) for table_name, measure_name in _collect_pairs(measures_df, ["Table Name", "Measure Name"]) }
    )

print(f"SemPy inventory: {len(semantic_tables)} table(s), {len(semantic_columns)} column(s), {len(semantic_measures)} measure(s)")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Build write plan

if "SEMANTIC_MEASURE_METADATA_ALIASES" not in globals():
    SEMANTIC_MEASURE_METADATA_ALIASES = {"_Measures": {}}
    print("[WARN] SEMANTIC_MEASURE_METADATA_ALIASES was not initialized; using empty defaults.")


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


def _merge_measure_alias_maps(primary_map, fallback_map):
    merged = {}
    for table_name, table_map in fallback_map.items():
        merged[table_name] = {k: list(v) for k, v in table_map.items()}

    for table_name, table_map in primary_map.items():
        current = merged.setdefault(table_name, {})
        for measure_name, aliases in table_map.items():
            current_aliases = current.get(measure_name, [])
            current[measure_name] = _dedupe_preserve_order(current_aliases + list(aliases))

    return merged


ACTIVE_MEASURE_ALIAS_MAP = _merge_measure_alias_maps(
    SEMANTIC_MEASURE_METADATA_ALIASES_RUNTIME,
    SEMANTIC_MEASURE_METADATA_ALIASES,
)


def measure_candidates(table_name: str, measure_name: str):
    aliases = ACTIVE_MEASURE_ALIAS_MAP.get(table_name, {}).get(measure_name, [])
    common_aliases = ACTIVE_MEASURE_ALIAS_MAP.get("_Measures", {}).get(measure_name, [])

    generated = [
        measure_name,
        measure_name.replace("_", " "),
        measure_name.replace("_", ""),
        measure_name.removeprefix("KPI_"),
        measure_name.removeprefix("kpi_"),
        measure_name.removeprefix("M_"),
        measure_name.removeprefix("m_"),
    ]

    return _dedupe_preserve_order(generated + aliases + common_aliases)


def resolve_measure_description(table_name: str, measure_name: str):
    for candidate in measure_candidates(table_name, measure_name):
        desc = (
            kpi_descs.get(candidate)
            or kpi_descs.get(_norm_measure_key(candidate))
        )
        if desc:
            return desc, candidate, "exact_or_alias"

    measure_key = _norm_measure_key(measure_name)
    if len(measure_key) >= 6:
        fuzzy_descriptions = []
        for kpi_key, desc in kpi_descs.items():
            if not isinstance(kpi_key, str):
                continue
            kpi_norm = _norm_measure_key(kpi_key)
            if not kpi_norm:
                continue
            if measure_key in kpi_norm or kpi_norm in measure_key:
                fuzzy_descriptions.append((kpi_key, desc))

        unique_descriptions = {d for _, d in fuzzy_descriptions}
        if len(unique_descriptions) == 1 and fuzzy_descriptions:
            source_key, only_desc = fuzzy_descriptions[0]
            return only_desc, source_key, "fuzzy_single"

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

unmatched_measures = []
for table_name, measure_name in semantic_measures:
    desc, matched_key, strategy = resolve_measure_description(table_name, measure_name)
    if desc:
        planned_measure_updates.append((table_name, measure_name, desc))
        print(f"  [MATCHED] measure {table_name}.{measure_name} <= {matched_key} ({strategy})")
    else:
        unmatched_measures.append(f"{table_name}.{measure_name}")

annotation_payload = " | ".join(ai_instructions).strip()

print("SemPy write plan:")
print(f"  Tables  : {len(planned_table_updates)}")
print(f"  Columns : {len(planned_column_updates)}")
print(f"  Measures: {len(planned_measure_updates)}")
print(f"  Annotation payload present: {bool(annotation_payload)}")
if unmatched_measures:
    print(f"  Unmatched semantic measures: {len(unmatched_measures)}")
    print("  Sample unmatched measures: " + ", ".join(unmatched_measures[:8]))


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Apply SemPy Labs writes

from importlib import import_module


def _set_object_description(table_name: str, object_type: str, object_name: str, description: str):
    if object_type not in {"Table", "Column", "Measure"}:
        raise ValueError(f"Unsupported object_type: {object_type}")

    base_kwargs = {
        "dataset": MODEL_NAME,
        "table_name": table_name,
        "description": description,
    }

    if object_type == "Table":
        attempts = [
            ("set_object_description", base_kwargs),
            ("set_table_description", base_kwargs),
        ]
    elif object_type == "Column":
        attempts = [
            ("set_object_description", {**base_kwargs, "column_name": object_name}),
            ("set_column_description", {**base_kwargs, "column_name": object_name}),
        ]
    else:
        attempts = [
            ("set_object_description", {**base_kwargs, "measure_name": object_name}),
            ("set_measure_description", {**base_kwargs, "measure_name": object_name}),
        ]

    errors = []
    for method_name, kwargs in attempts:
        method_info = LABS_WRITER_MAP.get(method_name)
        method = method_info[1] if method_info is not None else None
        if method is None:
            errors.append(f"{method_name}:missing")
            continue
        try:
            method(**kwargs)
            return True, method_name
        except Exception as ex:
            errors.append(f"{method_name}:{ex}")

    if TOM_CONNECTOR is not None:
        ok, detail = _set_object_description_via_tom(
            table_name=table_name,
            object_type=object_type,
            object_name=object_name,
            description=description,
        )
        if ok:
            return True, detail
        errors.append(detail)

    return False, " | ".join(errors)


def _discover_labs_writers():
    modules = []
    if labs is not None:
        modules.append(("labs", labs))

    # Some semantic-link-labs builds keep write helpers under submodules.
    for mod_name in [
        "sempy_labs.tom",
        "sempy_labs.tom._model",
        "sempy_labs._model",
        "sempy_labs.annotations",
    ]:
        try:
            modules.append((mod_name, import_module(mod_name)))
        except Exception:
            pass

    writer_map = {}
    for module_name, module_obj in modules:
        for attr in dir(module_obj):
            if not attr.startswith("set_"):
                continue
            fn = getattr(module_obj, attr, None)
            if callable(fn) and attr not in writer_map:
                writer_map[attr] = (module_name, fn)

    return writer_map


def _discover_tom_connector():
    candidates = []

    if labs is not None:
        fn = getattr(labs, "connect_semantic_model", None)
        if callable(fn):
            candidates.append(("labs.connect_semantic_model", fn))

    for mod_name in [
        "sempy_labs.tom",
        "sempy_labs.tom._model",
        "sempy_labs._model",
    ]:
        try:
            module_obj = import_module(mod_name)
            fn = getattr(module_obj, "connect_semantic_model", None)
            if callable(fn):
                candidates.append((f"{mod_name}.connect_semantic_model", fn))
        except Exception:
            pass

    return candidates[0] if candidates else (None, None)


def _find_collection_item_by_name(collection, name: str):
    target = name.strip().lower()

    # Try indexer first for performance and exact-name lookup.
    try:
        return collection[name]
    except Exception:
        pass

    for item in collection:
        item_name = getattr(item, "Name", None)
        if isinstance(item_name, str) and item_name.strip().lower() == target:
            return item

    return None


def _set_object_description_via_tom(table_name: str, object_type: str, object_name: str, description: str):
    if TOM_CONNECTOR is None:
        return False, "tom_connect_semantic_model:missing"

    try:
        with TOM_CONNECTOR(dataset=MODEL_NAME, readonly=False) as tom:
            table_obj = _find_collection_item_by_name(tom.model.Tables, table_name)
            if table_obj is None:
                return False, f"tom_table_missing:{table_name}"

            if object_type == "Table":
                table_obj.Description = description
                return True, "tom.model.Table.Description"

            if object_type == "Column":
                col_obj = _find_collection_item_by_name(table_obj.Columns, object_name)
                if col_obj is None:
                    return False, f"tom_column_missing:{table_name}.{object_name}"
                col_obj.Description = description
                return True, "tom.model.Column.Description"

            measure_obj = _find_collection_item_by_name(table_obj.Measures, object_name)
            if measure_obj is None:
                return False, f"tom_measure_missing:{table_name}.{object_name}"
            measure_obj.Description = description
            return True, "tom.model.Measure.Description"

    except Exception as ex:
        return False, f"tom_description_write_failed:{ex}"


LABS_WRITER_MAP = _discover_labs_writers() if labs is not None else {}
TOM_CONNECTOR_NAME, TOM_CONNECTOR = _discover_tom_connector() if labs is not None else (None, None)


def _set_ai_annotation(value: str):
    method_info = LABS_WRITER_MAP.get("set_semantic_model_annotation")
    if method_info is not None:
        _, method = method_info
        return method(
            dataset=MODEL_NAME,
            annotation_name="PBI_AI_Instructions",
            annotation_value=value,
        )

    method_info = LABS_WRITER_MAP.get("set_annotation")
    if method_info is not None:
        _, method = method_info
        return method(
            dataset=MODEL_NAME,
            annotation_name="PBI_AI_Instructions",
            annotation_value=value,
        )

    if TOM_CONNECTOR is None:
        return False

    try:
        with TOM_CONNECTOR(dataset=MODEL_NAME, readonly=False) as tom:
            annotations = getattr(tom.model, "Annotations", None)
            if annotations is None:
                return False

            existing = _find_collection_item_by_name(annotations, "PBI_AI_Instructions")
            if existing is not None:
                existing.Value = value
                return True

            # Try common add patterns used by TOM collections.
            try:
                annotations.Add("PBI_AI_Instructions", value)
                return True
            except Exception:
                pass

    except Exception:
        return False

    return False


if EFFECTIVE_DEMO_MODE:
    print("[DRY RUN] SemPy Labs writes skipped")
else:
    if labs is None:
        raise RuntimeError("DEMO_MODE=False requires sempy_labs to be installed")

    applied_descriptions = 0
    skipped_descriptions = 0
    available_setters = sorted(LABS_WRITER_MAP.keys())
    available_description_methods = [name for name in available_setters if "description" in name.lower()]
    available_annotation_methods = [name for name in available_setters if "annotation" in name.lower()]

    if not available_description_methods:
        print("[WARN] No SemPy Labs description writer methods discovered in this runtime.")
        if TOM_CONNECTOR is None:
            print("       Description writes will be skipped for this execution.")
        else:
            print(f"       Falling back to TOM writer via {TOM_CONNECTOR_NAME}.")

    for table_name, description, source in planned_table_updates:
        ok, detail = _set_object_description(table_name, "Table", table_name, description)
        if ok:
            applied_descriptions += 1
            print(f"  [APPLIED] table   {table_name:<28} source={source} via {detail}")
        else:
            skipped_descriptions += 1
            print(f"  [WARN] skipped table   {table_name:<28} source={source} | {detail}")

    for table_name, column_name, description, source_table, source_column in planned_column_updates:
        ok, detail = _set_object_description(table_name, "Column", column_name, description)
        if ok:
            applied_descriptions += 1
            print(f"  [APPLIED] column  {table_name}.{column_name:<20} source={source_table}.{source_column} via {detail}")
        else:
            skipped_descriptions += 1
            print(f"  [WARN] skipped column  {table_name}.{column_name:<20} source={source_table}.{source_column} | {detail}")

    for table_name, measure_name, description in planned_measure_updates:
        ok, detail = _set_object_description(table_name, "Measure", measure_name, description)
        if ok:
            applied_descriptions += 1
            print(f"  [APPLIED] measure {table_name}.{measure_name} via {detail}")
        else:
            skipped_descriptions += 1
            print(f"  [WARN] skipped measure {table_name}.{measure_name} | {detail}")

    print(f"  Description writes: applied={applied_descriptions}, skipped={skipped_descriptions}")
    if skipped_descriptions > 0:
        print(f"  Available SemPy Labs description methods: {available_description_methods}")
        print(f"  Available SemPy Labs annotation methods: {available_annotation_methods}")
        print(f"  All discovered set_* methods: {available_setters}")
        print(f"  TOM connector available: {TOM_CONNECTOR is not None}")
        if TOM_CONNECTOR is not None:
            print(f"  TOM connector source: {TOM_CONNECTOR_NAME}")

    if annotation_payload:
        annotation_ok = _set_ai_annotation(annotation_payload)
        if annotation_ok is False:
            print("  [WARN] skipped annotation PBI_AI_Instructions | no supported annotation writer found")
        else:
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
print(f"  Status: {'DRY RUN' if EFFECTIVE_DEMO_MODE else 'APPLIED'}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
