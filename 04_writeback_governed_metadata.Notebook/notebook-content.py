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
# META       "environmentId": "7380ddbb-a87b-8113-489c-049cb1998b35",
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
    "_Measures": "Governed business measures for customer, contract, revenue, equipment, service, and contact-center performance.",
    "dim_cc_agent": "Contact-center agent dimension used to analyze queue assignment, team performance, and interaction ownership.",
    "dim_cc_billing_adj": "Billing-adjustment dimension used to classify credits, corrections, and dispute outcomes for contact-center interactions.",
    "fct_cc_interactions": "Contact-center interaction fact table used for first-contact resolution, satisfaction, handle-time, renewal, and escalation analysis.",
    "fct_cc_transcript_turns": "Contact-center transcript-turn fact table used for governed conversation analysis and interaction-level evidence.",
}

SEMANTIC_FALLBACK_MEASURE_DESCRIPTIONS = {
    "Technician Utilization Rate": "Distinct assigned technicians divided by service requests in the selected period. Use this operational coverage indicator to assess dispatch workload distribution; higher values indicate requests are spread across more technicians.",
    "Total MRR": "Posted monthly recurring revenue from customer contracts in the selected period, based on billing transactions classified as MonthlyCharge.",
    "New MRR": "Monthly recurring revenue added by contracts marked as new in the selected period.",
    "Churned MRR": "Monthly recurring revenue lost from contracts marked as churned in the selected period.",
    "Net MRR Change": "New monthly recurring revenue minus churned monthly recurring revenue in the selected period.",
    "Active Customer Count": "Count of customer records whose current status is Active.",
    "Active Contract Count": "Count of contract-month records whose contract status is Active.",
    "Avg Lifetime Value": "Average posted billing value per customer across the customer population in the selected context.",
    "Avg Tenure Months": "Average number of months from each customer's created date through the current date.",
    "SLA Breach Count": "Count of service requests that missed the governed service-level target in the selected period.",
    "SLA Compliance Rate": "Percentage of service requests that met the governed service-level target in the selected period, calculated as non-breached requests divided by total requests.",
    "Warranty Coverage Rate": "Percentage of registered equipment assets currently marked as under warranty.",
    "Avg Equipment Age Years": "Average age in years of registered equipment assets in the selected context.",
    "Escalation Rate": "Percentage of contact-center interactions marked as escalated in the selected period.",
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

meta_df = spark.sql("SELECT * FROM vw_business_metadata_current")
rows = meta_df.collect()
print(f"Cell 3 status: loaded {len(rows)} row(s) from vw_business_metadata_current")


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
        SELECT KpiName, KPICode, Description, Domain, Owner, Version,
               CertifiedBy, CertifiedDate, TargetValue, WarningThreshold,
               CriticalThreshold, UnitType
        FROM kpi_metadata
        WHERE IsCertified = 1
        """
    )

    # Build a robust lookup so semantic measures can match by KPI name or KPI code.
    kpi_descs = {}
    kpi_rows = [r for r in kpi_df.collect() if r.Description]
    certified_kpi_metadata = {
        str(r.KPICode): r.asDict(recursive=True)
        for r in kpi_rows
        if r.KPICode
    }
    for r in kpi_rows:
        if r.KpiName:
            kpi_descs[r.KpiName] = r.Description
            kpi_descs[_norm_measure_key(r.KpiName)] = r.Description
        if r.KPICode:
            kpi_descs[r.KPICode] = r.Description
            kpi_descs[_norm_measure_key(r.KPICode)] = r.Description
except Exception:
    kpi_descs = {}
    certified_kpi_metadata = {}
    print("[WARN] kpi_metadata missing IsCertified/Description")

try:
    ai_df = spark.sql(
        "SELECT ResponseText FROM ai_metadata"
        f" WHERE IsDraft = 0 AND IsCertified = 1 AND RecordType = 'ai_instruction'"
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

# Cell 4: Use the inventory verified against the live model through Power BI MCP.

semantic_tables = sorted({
    "dim_date", "dim_equipment", "dim_customer", "dim_service_account",
    "dim_product", "fct_service_request", "fct_billing", "fct_contract_month",
    "_Measures", "dim_cc_agent", "dim_cc_billing_adj",
    "fct_cc_interactions", "fct_cc_transcript_turns",
})

inventory_annotations_df = spark.table("sm_annotations")
semantic_columns = sorted({
    (str(row["table"]), str(row["object_name"]))
    for row in inventory_annotations_df.where("object_type = 'Column'")
    .select("table", "object_name")
    .distinct()
    .collect()
})

semantic_measures = sorted({
    ("_Measures", "SLA Breach Count"),
    ("fct_service_request", "Technician Utilization Rate"),
    ("_Measures", "Total MRR"),
    ("_Measures", "New MRR"),
    ("_Measures", "Churned MRR"),
    ("_Measures", "Net MRR Change"),
    ("_Measures", "Active Customer Count"),
    ("_Measures", "Active Contract Count"),
    ("_Measures", "Avg Lifetime Value"),
    ("_Measures", "Avg Tenure Months"),
    ("_Measures", "SLA Compliance Rate"),
    ("_Measures", "Warranty Coverage Rate"),
    ("_Measures", "Avg Equipment Age Years"),
    ("_Measures", "FCR Rate"),
    ("_Measures", "Avg CSAT"),
    ("_Measures", "PP Renewal Rate"),
    ("_Measures", "Avg Handle Time (sec)"),
    ("_Measures", "Escalation Rate"),
})

CERTIFIED_KPI_MEASURE_MAP = {
    "FCR": ("_Measures", "FCR Rate"),
    "CSAT": ("_Measures", "Avg CSAT"),
    "PP_RNW_RATE": ("_Measures", "PP Renewal Rate"),
    "AHT": ("_Measures", "Avg Handle Time (sec)"),
}

UNRESOLVED_CERTIFIED_KPI_MAPPINGS = {
    "SLA_BRCH_RATE": (
        "No like-for-like runtime measure exists. SLA Compliance Rate is the complement "
        "and uses fct_service_request rather than the certified field-service-visit formula."
    ),
}

print(
    "MCP-verified inventory: "
    f"{len(semantic_tables)} table(s), {len(semantic_columns)} annotation-target column(s), "
    f"{len(semantic_measures)} measure(s)"
)


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

    fallback = SEMANTIC_FALLBACK_MEASURE_DESCRIPTIONS.get(measure_name)
    if fallback:
        return fallback, "fallback", "business_use_fallback"

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

from sempy_labs.tom import connect_semantic_model

model_name = MODEL_NAME if "MODEL_NAME" in globals() else "BrookfieldEnercare"
workspace_name = None  # set to your Fabric workspace name only if needed

kwargs = {
    "dataset": model_name,
    "readonly": False,
}
if workspace_name:
    kwargs["workspace"] = workspace_name

with connect_semantic_model(**kwargs) as tom:
    print("Connected object type:", type(tom).__name__)

    # Methods on the TOM wrapper
    wrapper_writers = [
        m for m in dir(tom)
        if not m.startswith("_")
        and (
            "description" in m.lower()
            or m.startswith("set_")
            or m.startswith("update_")
            or m.startswith("add_")
        )
    ]
    print("Wrapper methods:")
    for m in sorted(wrapper_writers):
        print(" -", m)

    # Methods on the underlying model object
    model_writers = [
        m for m in dir(tom.model)
        if not m.startswith("_")
        and (
            "description" in m.lower()
            or m.startswith("set_")
            or m.startswith("update_")
            or m.startswith("add_")
        )
    ]
    print("Model methods:")
    for m in sorted(model_writers):
        print(" -", m)

    # Quick object-level proof (where Description is typically set)
    sample_table = next((t for t in tom.model.Tables if t.Name == "dim_customer"), None)
    if sample_table is not None:
        print("Sample table Description before:", sample_table.Description)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Apply SemPy Labs writes

from importlib import import_module
import pkgutil

labs = globals().get("labs")

LABS_SYMBOL_ALLOWLIST = {
    "connect_semantic_model",
    "set_semantic_model_storage_format",
}

# Set True only when actively troubleshooting sempy_labs module exports.
DEBUG_RUNTIME_SURFACE = False


def _inspect_labs_symbol_surface():
    inspected = {}
    modules = []

    if labs is not None:
        modules.append(("labs", labs))

    if labs is not None and hasattr(labs, "__path__"):
        for module_info in pkgutil.walk_packages(labs.__path__, labs.__name__ + "."):
            try:
                modules.append((module_info.name, import_module(module_info.name)))
            except Exception:
                pass

    if labs is not None:
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

    for module_name, module_obj in modules:
        callable_names = []
        for attr in dir(module_obj):
            if attr.startswith(("set_", "update_", "add_", "connect_")):
                fn = getattr(module_obj, attr, None)
                if callable(fn):
                    callable_names.append(attr)
        if callable_names:
            inspected[module_name] = sorted(set(callable_names))

    return inspected


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

    # Walk the package surface so the notebook sees the actual runtime exports,
    # not just a hand-maintained list of submodules.
    if labs is not None and hasattr(labs, "__path__"):
        for module_info in pkgutil.walk_packages(labs.__path__, labs.__name__ + "."):
            try:
                modules.append((module_info.name, import_module(module_info.name)))
            except Exception:
                pass

    if labs is not None:
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

    symbol_surface = _inspect_labs_symbol_surface()
    writer_map = {}
    for module_name, module_obj in modules:
        for attr in dir(module_obj):
            if attr not in LABS_SYMBOL_ALLOWLIST:
                continue
            fn = getattr(module_obj, attr, None)
            if callable(fn) and attr not in writer_map:
                writer_map[attr] = (module_name, fn)

    if DEBUG_RUNTIME_SURFACE:
        if symbol_surface:
            print("SemPy Labs callable surface:")
            for module_name in sorted(symbol_surface):
                print(f"  {module_name}: {', '.join(symbol_surface[module_name])}")
        else:
            print("[INFO] No sempy_labs callable surface discovered in runtime modules.")

    discovered_setters = sorted(writer_map.keys())
    if discovered_setters:
        print(f"SemPy Labs discovered module-level setters: {', '.join(discovered_setters)}")
    else:
        print("[INFO] No module-level SemPy Labs setters matched the allowlist.")

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


def _inspect_tomwrapper_writer_surface():
    if TOM_CONNECTOR is None:
        return []

    try:
        with TOM_CONNECTOR(dataset=MODEL_NAME, readonly=True) as tom:
            return sorted(
                {
                    name
                    for name in dir(tom)
                    if not name.startswith("_")
                    and (
                        "description" in name.lower()
                        or name.startswith(("set_", "update_", "add_", "sync_"))
                    )
                }
            )
    except Exception:
        return []


TOM_WRITER_METHODS = _inspect_tomwrapper_writer_surface()


def _set_ai_annotation(value: str):
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


def _apply_descriptions_via_batch_update():
    method_info = LABS_WRITER_MAP.get("update_descriptions")
    if method_info is None:
        return False, "update_descriptions:missing", 0

    method_source, method = method_info

    table_descriptions = {
        table_name: description
        for table_name, description, _ in planned_table_updates
        if isinstance(description, str) and description.strip()
    }
    column_descriptions = {
        f"{table_name}/{column_name}": description
        for table_name, column_name, description, _, _ in planned_column_updates
        if isinstance(description, str) and description.strip()
    }
    measure_descriptions = {
        f"{table_name}/{measure_name}": description
        for table_name, measure_name, description in planned_measure_updates
        if isinstance(description, str) and description.strip()
    }

    attempts = [
        {
            "dataset": MODEL_NAME,
            "table_descriptions": table_descriptions,
            "column_descriptions": column_descriptions,
            "measure_descriptions": measure_descriptions,
        },
        {
            "dataset": MODEL_NAME,
            "column_descriptions": column_descriptions,
            "measure_descriptions": measure_descriptions,
        },
        {
            "dataset": MODEL_NAME,
            "column_descriptions": column_descriptions,
        },
        {
            "dataset": MODEL_NAME,
            "measure_descriptions": measure_descriptions,
        },
    ]

    last_error = None
    for kwargs in attempts:
        kwargs = {k: v for k, v in kwargs.items() if v}
        if len(kwargs) <= 1:
            continue
        try:
            method(**kwargs)
            updated_count = 0
            if "table_descriptions" in kwargs:
                updated_count += len(kwargs["table_descriptions"])
            if "column_descriptions" in kwargs:
                updated_count += len(kwargs["column_descriptions"])
            if "measure_descriptions" in kwargs:
                updated_count += len(kwargs["measure_descriptions"])
            return True, f"{method_source}.update_descriptions(batch)", updated_count
        except Exception as ex:
            last_error = ex

    return False, f"update_descriptions:failed:{last_error}", 0


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
    used_batch_descriptions = False

    batch_ok, batch_detail, batch_applied = _apply_descriptions_via_batch_update()
    if batch_ok:
        used_batch_descriptions = True
        applied_descriptions += batch_applied
        print(f"  [APPLIED] description batch via {batch_detail} ({batch_applied} object(s))")
    elif "update_descriptions:missing" not in batch_detail:
        print(f"  [WARN] SemPy Labs batch description update failed: {batch_detail}")
        print("       Falling back to per-object writer resolution.")

    if not available_description_methods:
        print("[INFO] Description writes route through TOM (expected for this sempy_labs runtime).")
        if TOM_CONNECTOR is None:
            print("       Description writes will be skipped for this execution.")
        else:
            print(f"       Using TOM connection via {TOM_CONNECTOR_NAME} for description writes.")
            if TOM_WRITER_METHODS:
                print(f"       TOMWrapper writer-like methods detected: {', '.join(TOM_WRITER_METHODS[:12])}")

    if not used_batch_descriptions:
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
        print(f"  All discovered set_/update_* methods: {available_setters}")
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

# CELL ********************

# Cell 8: Read sm_annotations and derive description/annotation intents

sm_annotations = []
glossary_definitions = {}

try:
    sm_df = spark.table("sm_annotations")
    sm_annotations = [r.asDict(recursive=True) for r in sm_df.collect()]
    if not sm_annotations:
        raise RuntimeError("sm_annotations is empty")
    refreshed_sm_df = spark.createDataFrame(sm_annotations, schema=sm_df.schema)
    (
        refreshed_sm_df.write
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .format("delta")
        .saveAsTable("sm_annotations")
    )
    spark.catalog.refreshTable("sm_annotations")
    refreshed_count = spark.table("sm_annotations").count()
    if refreshed_count != len(sm_annotations):
        raise RuntimeError(
            f"sm_annotations refresh mismatch: expected={len(sm_annotations)}, actual={refreshed_count}"
        )
    print(f"Cell 8 status: refreshed and verified {refreshed_count} sm_annotations row(s)")
except Exception as ex:
    raise RuntimeError(f"sm_annotations refresh failed: {ex}") from ex

try:
    # explicit column-select avoids collecting schema-declared-but-not-physically-materialized
    # columns (e.g. parent_term_code) that raise IllegalStateException on a full-row collect
    glossary_rows = spark.table("glossary_terms").select("term_code", "term_name", "definition").collect()
    for row in glossary_rows:
        term_code = getattr(row, "term_code", None)
        term_name = getattr(row, "term_name", None)
        definition = getattr(row, "definition", None)
        if not definition:
            continue
        if term_code:
            glossary_definitions[_norm(str(term_code))] = definition
        if term_name:
            glossary_definitions[_norm(str(term_name))] = definition
except Exception as ex:
    raise RuntimeError(f"glossary_terms unavailable for description join: {ex}") from ex


def _parse_glossary_reference(value: str):
    if value is None:
        return []
    tokens = [p.strip() for p in str(value).split("|") if p.strip()]
    return tokens


annotation_intents = []
description_intents = {}

for row in sm_annotations:
    table_name = str(row.get("table") or "").strip()
    object_type = str(row.get("object_type") or "").strip()
    object_name = str(row.get("object_name") or "").strip()
    key = str(row.get("annotation_key") or "").strip()
    value = row.get("annotation_value")

    if not table_name or not object_name or object_type not in {"Column", "Measure"}:
        continue

    if key in {"CDE_Member_Of", "Glossary_Term_References", "Sensitivity_Label", "Data_Product_Owner"} and value:
        annotation_intents.append(
            {
                "table": table_name,
                "object_type": object_type,
                "object_name": object_name,
                "annotation_key": key,
                "annotation_value": str(value),
            }
        )

    if key == "Glossary_Term_References" and value:
        object_key = (table_name, object_type, object_name)
        if object_type == "Measure" and any(
            planned_table == table_name and planned_measure == object_name
            for planned_table, planned_measure, _ in planned_measure_updates
        ):
            continue
        for token in _parse_glossary_reference(str(value)):
            definition = glossary_definitions.get(_norm(token))
            if definition and object_key not in description_intents:
                description_intents[object_key] = definition

print(f"Cell 8 status: annotation intents={len(annotation_intents)}")
print(f"Cell 8 status: description intents={len(description_intents)}")


def _annotation_text(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


ontology_by_kpi_code = {}
try:
    okr_rows = [r.asDict(recursive=True) for r in spark.table("okrs").collect()]
    key_result_rows = [r.asDict(recursive=True) for r in spark.table("okr_key_results").collect()]
    okr_product_rows = [r.asDict(recursive=True) for r in spark.table("okr_data_products").collect()]

    okr_domain = {str(r.get("okr_id")): _annotation_text(r.get("domain_id")) for r in okr_rows}
    products_by_okr = {}
    for row in okr_product_rows:
        products_by_okr.setdefault(str(row.get("okr_id")), []).append(str(row.get("data_product_id")))

    for row in key_result_rows:
        metric_source = _annotation_text(row.get("metric_source")) or ""
        if not metric_source.lower().startswith("kpi_metadata."):
            continue
        kpi_code = metric_source.split(".", 1)[1]
        okr_id = _annotation_text(row.get("okr_id"))
        ontology_by_kpi_code[kpi_code] = {
            "Governance_Key_Result_Id": _annotation_text(row.get("key_result_id")),
            "Governance_Objective_Id": okr_id,
            "Governance_Data_Product_Id": ";".join(sorted(products_by_okr.get(okr_id, []))),
            "Governance_Domain_Id": okr_domain.get(okr_id),
        }
except Exception as ex:
    print(f"[WARN] Ontology metadata unavailable for semantic annotations: {ex}")

certification_annotation_intents = []
for kpi_code, (table_name, measure_name) in CERTIFIED_KPI_MEASURE_MAP.items():
    metadata = certified_kpi_metadata.get(kpi_code)
    if not metadata:
        raise RuntimeError(f"Certified KPI metadata missing for exact runtime mapping: {kpi_code}")

    annotation_values = {
        "Governance_KPI_Code": kpi_code,
        "Governance_Certification_Status": "Certified",
        "Governance_KPI_Owner": _annotation_text(metadata.get("Owner")),
        "Governance_Certified_By": _annotation_text(metadata.get("CertifiedBy")),
        "Governance_Certified_Date": _annotation_text(metadata.get("CertifiedDate")),
        "Governance_KPI_Domain": _annotation_text(metadata.get("Domain")),
        "Governance_KPI_Version": _annotation_text(metadata.get("Version")),
        "Governance_Target_Value": _annotation_text(metadata.get("TargetValue")),
        "Governance_Warning_Threshold": _annotation_text(metadata.get("WarningThreshold")),
        "Governance_Critical_Threshold": _annotation_text(metadata.get("CriticalThreshold")),
        "Governance_Unit_Type": _annotation_text(metadata.get("UnitType")),
        **ontology_by_kpi_code.get(kpi_code, {}),
    }
    for key, value in annotation_values.items():
        if value:
            certification_annotation_intents.append(
                {
                    "table": table_name,
                    "object_type": "Measure",
                    "object_name": measure_name,
                    "annotation_key": key,
                    "annotation_value": value,
                }
            )

print(f"Cell 8 status: certification/ontology intents={len(certification_annotation_intents)}")
for kpi_code, reason in UNRESOLVED_CERTIFIED_KPI_MAPPINGS.items():
    print(f"Cell 8 status: certified KPI mapping unresolved: {kpi_code} | {reason}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 9: Apply sm_annotations writeback via TOM (annotations + descriptions)


def _set_object_annotation_via_tom(table_name: str, object_type: str, object_name: str, key: str, value: str):
    if TOM_CONNECTOR is None:
        return False, "tom_connect_semantic_model:missing"

    try:
        with TOM_CONNECTOR(dataset=MODEL_NAME, readonly=False) as tom:
            table_obj = _find_collection_item_by_name(tom.model.Tables, table_name)
            if table_obj is None:
                return False, f"tom_table_missing:{table_name}"

            if object_type == "Column":
                target_obj = _find_collection_item_by_name(table_obj.Columns, object_name)
            elif object_type == "Measure":
                target_obj = _find_collection_item_by_name(table_obj.Measures, object_name)
            else:
                return False, f"unsupported_object_type:{object_type}"

            if target_obj is None:
                return False, f"tom_object_missing:{table_name}.{object_name}"

            # Use the TOMWrapper's own set_annotation (rather than a hand-rolled
            # Annotations.Add) since its close()/SaveChanges path is the proven one
            # that already persists Description writes in this same notebook.
            try:
                tom.set_annotation(object=target_obj, name=key, value=value)
                return True, "tom.set_annotation"
            except Exception as add_ex:
                return False, f"tom_annotation_add_failed:{add_ex}"

    except Exception as ex:
        return False, f"tom_annotation_write_failed:{ex}"


def _apply_object_annotations_via_tom(intents):
    if TOM_CONNECTOR is None:
        return [(intent, False, "tom_connect_semantic_model:missing") for intent in intents]

    results = []
    try:
        with TOM_CONNECTOR(dataset=MODEL_NAME, readonly=False) as tom:
            for intent in intents:
                table_name = intent["table"]
                object_type = intent["object_type"]
                object_name = intent["object_name"]
                table_obj = _find_collection_item_by_name(tom.model.Tables, table_name)
                if table_obj is None:
                    results.append((intent, False, f"tom_table_missing:{table_name}"))
                    continue

                if object_type == "Column":
                    target_obj = _find_collection_item_by_name(table_obj.Columns, object_name)
                elif object_type == "Measure":
                    target_obj = _find_collection_item_by_name(table_obj.Measures, object_name)
                else:
                    results.append((intent, False, f"unsupported_object_type:{object_type}"))
                    continue

                if target_obj is None:
                    results.append((intent, False, f"tom_object_missing:{table_name}.{object_name}"))
                    continue

                try:
                    tom.set_annotation(
                        object=target_obj,
                        name=intent["annotation_key"],
                        value=intent["annotation_value"],
                    )
                    results.append((intent, True, "tom.set_annotation(batch)"))
                except Exception as ex:
                    results.append((intent, False, f"tom_annotation_add_failed:{ex}"))
    except Exception as ex:
        return [(intent, False, f"tom_annotation_write_failed:{ex}") for intent in intents]

    return results


applied_ann = 0
skipped_ann = 0
applied_certification_ann = 0
skipped_certification_ann = 0
applied_desc_from_glossary = 0
skipped_desc_from_glossary = 0
_cell9_debug_lines = []

if EFFECTIVE_DEMO_MODE:
    print("[DRY RUN] sm_annotations writes skipped")
else:
    all_object_annotation_intents = annotation_intents + certification_annotation_intents
    for intent, ok, detail in _apply_object_annotations_via_tom(all_object_annotation_intents):
        _cell9_debug_lines.append(
            f"{intent['table']}.{intent['object_name']} [{intent['annotation_key']}] "
            f"ok={ok} detail={detail}"
        )
        is_certification = intent in certification_annotation_intents
        if ok and is_certification:
            applied_certification_ann += 1
        elif ok:
            applied_ann += 1
        elif is_certification:
            skipped_certification_ann += 1
        else:
            skipped_ann += 1
            print(
                f"  [WARN] skipped annotation {intent['table']}.{intent['object_name']}"
                f" [{intent['annotation_key']}] | {detail}"
            )

    for (table_name, object_type, object_name), description in description_intents.items():
        ok, detail = _set_object_description(table_name, object_type, object_name, description)
        if ok:
            applied_desc_from_glossary += 1
        else:
            skipped_desc_from_glossary += 1
            print(
                f"  [WARN] skipped glossary description {table_name}.{object_name}"
                f" ({object_type}) | {detail}"
            )

    # Job status API exposes no cell-level stdout; persist per-intent detail so a run's
    # real failure reason can be read back independent of any interactive session.
    try:
        mssparkutils.fs.mkdirs("Files/debug")
        mssparkutils.fs.put("Files/debug/nb04_cell9_last_run.txt", "\n".join(_cell9_debug_lines), True)
    except Exception as debug_ex:
        print(f"[WARN] Could not write Cell 9 debug log: {debug_ex}")

print(f"Cell 9 status: annotations applied={applied_ann}, skipped={skipped_ann}")
print(
    "Cell 9 status: certification/ontology annotations applied="
    f"{applied_certification_ann}, skipped={skipped_certification_ann}"
)
print(
    "Cell 9 status: glossary descriptions applied="
    f"{applied_desc_from_glossary}, skipped={skipped_desc_from_glossary}"
)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 10: Verify sm_annotations persistence in semantic inventory

verify_counts = {
    "annotations_requested": len(annotation_intents),
    "certification_annotations_requested": len(certification_annotation_intents),
    "description_updates_requested": len(description_intents),
    "effective_demo_mode": int(EFFECTIVE_DEMO_MODE),
    "unresolved_certified_kpi_mappings": len(UNRESOLVED_CERTIFIED_KPI_MAPPINGS),
}

verify_df = spark.createDataFrame([(k, int(v)) for k, v in verify_counts.items()], ["metric", "value"])
display(verify_df.orderBy("metric"))


def _read_annotation_value(target_obj, annotation_name):
    annotations = getattr(target_obj, "Annotations", None)
    if annotations is None:
        return None
    annotation = _find_collection_item_by_name(annotations, annotation_name)
    return None if annotation is None else str(annotation.Value)


def _description_quality_error(description):
    value = str(description or "").strip()
    lowered = value.lower()
    if not value:
        return "empty"
    if "notebook-owned governance term definition" in lowered:
        return "placeholder"
    if "<div" in lowered or "</div>" in lowered:
        return "html_markup"
    if "@enercare.ca" in lowered or "@microsoft.com" in lowered:
        return "owner_email"
    return None


readback_failures = []
if not EFFECTIVE_DEMO_MODE:
    with TOM_CONNECTOR(dataset=MODEL_NAME, readonly=True) as tom:
        for table_name, _, _ in planned_table_updates:
            table_obj = _find_collection_item_by_name(tom.model.Tables, table_name)
            error = "missing_object" if table_obj is None else _description_quality_error(table_obj.Description)
            if error:
                readback_failures.append(f"Table {table_name}: {error}")

        for table_name, measure_name, _ in planned_measure_updates:
            table_obj = _find_collection_item_by_name(tom.model.Tables, table_name)
            measure_obj = None if table_obj is None else _find_collection_item_by_name(table_obj.Measures, measure_name)
            error = "missing_object" if measure_obj is None else _description_quality_error(measure_obj.Description)
            if error:
                readback_failures.append(f"Measure {table_name}.{measure_name}: {error}")

        for intent in annotation_intents + certification_annotation_intents:
            table_obj = _find_collection_item_by_name(tom.model.Tables, intent["table"])
            collection = None
            if table_obj is not None and intent["object_type"] == "Column":
                collection = table_obj.Columns
            elif table_obj is not None and intent["object_type"] == "Measure":
                collection = table_obj.Measures
            target_obj = None if collection is None else _find_collection_item_by_name(collection, intent["object_name"])
            actual = None if target_obj is None else _read_annotation_value(target_obj, intent["annotation_key"])
            if actual != intent["annotation_value"]:
                readback_failures.append(
                    f"Annotation {intent['table']}.{intent['object_name']}[{intent['annotation_key']}]: "
                    f"expected={intent['annotation_value']!r}, actual={actual!r}"
                )

if readback_failures:
    raise RuntimeError("Notebook 4 TOM readback validation failed:\n" + "\n".join(readback_failures))

print(
    "Cell 10 status: TOM readback passed for "
    f"{len(planned_table_updates)} table descriptions, "
    f"{len(planned_measure_updates)} measure descriptions, and "
    f"{len(annotation_intents) + len(certification_annotation_intents)} object annotations"
)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Fabric Notebook: nb_05_push_qa_verified_answers
# Purpose: Read ai_instruction + verified_answer rows from lh_metadata.ai_metadata
#          and write them to the semantic model as two distinct annotations using
#          SemPy Labs (primary write-back path):
#            PBI_AI_Instructions    <- RecordType='ai_instruction' rows only
#            PBI_AI_VerifiedAnswers <- RecordType='verified_answer' rows only
#          Verified answers are a distinct governed construct from ai_metadata and
#          are kept on their own annotation so they can be regenerated/audited
#          independently of the source/model/agent instruction content.
#
# DEMO_MODE = True  -> dry-run (prints both annotation previews, no write)
# DEMO_MODE = False -> live (writes both annotations to semantic model)

# Standalone Copilot grounding reads semantic model annotation surfaces.
# Keep this enabled so write path stays on SemPy Labs-only and avoids TOM drift.
USE_SEMPY_ONLY      = True

DEMO_MODE            = False
MODEL_NAME           = "BrookfieldEnercare"
MODEL_WORKSPACE_ID   = "b976cac2-7754-4061-88c2-61c0ac016a99"
METADATA_LH          = "lh_metadata"
# Keep this high enough to include all valid instructions + verified Q&A.
# If your environment enforces a lower annotation limit, the notebook now reports
# that explicitly instead of silently dropping content.
MAX_ANNOTATION_CHARS = 12000

print(f"nb_05_push_qa_verified_answers | DEMO_MODE={DEMO_MODE}")
print(f"Target model: {MODEL_NAME}")
print(f"Max annotation chars: {MAX_ANNOTATION_CHARS}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read ai_metadata
# Gate matches nb_04_sempy_writeback's KPI pattern exactly (WHERE IsCertified = 1): only
# certified content reaches the Data Agent's live grounding surface. Previously this filtered
# only IsDraft = 0, which let content with no certification decision at all (IsCertified NULL)
# through -- found during the 2026-08-13 notebook governance review (docs/01_Notebook_Description.md).

ai_df = spark.sql(f"""
    SELECT RecordType, TriggerText, ResponseText, LinkedKPICode
    FROM ai_metadata
    WHERE IsDraft = 0 AND IsCertified = 1
    ORDER BY RecordType, RecordID
""")
ai_rows = ai_df.collect()

ai_instructions = list(
    dict.fromkeys(
        r.ResponseText
        for r in ai_rows
        if r.RecordType == "ai_instruction" and r.ResponseText
    )
)

_seen_qa = set()
verified_answers = []
for r in ai_rows:
    if r.RecordType == "verified_answer" and r.TriggerText and r.ResponseText:
        key = (r.TriggerText, r.ResponseText)
        if key not in _seen_qa:
            _seen_qa.add(key)
            verified_answers.append(r)

# Exact service request IDs should rank first in grounding payload assembly.
verified_answers.sort(
    key=lambda r: (
        0 if any(ch.isdigit() for ch in (r.TriggerText or "")) else 1,
        (r.TriggerText or "").lower(),
    )
)

print(f"Loaded: {len(ai_instructions)} instruction(s), {len(verified_answers)} verified answer(s)")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build annotation payload


def _safe(text: str) -> str:
    return text.replace('"', "'").strip()


def _truncate(payload: str, label: str) -> str:
    if len(payload) <= MAX_ANNOTATION_CHARS:
        return payload
    raise RuntimeError(
        f"{label} is {len(payload)} chars and exceeds MAX_ANNOTATION_CHARS={MAX_ANNOTATION_CHARS}; "
        "refusing to truncate governed runtime content"
    )


instr_block = " | ".join(_safe(t) for t in ai_instructions)
qa_parts = [
    f"Q: {_safe(r.TriggerText)} -> {_safe(r.ResponseText)}"
    for r in verified_answers
]
qa_block = " | ".join(qa_parts)

# Verified answers are their own governed construct (ai_metadata.RecordType=
# 'verified_answer') and are written to their own annotation so they stay
# independently addressable/regenerable instead of flattened into one
# instruction blob alongside source/model/agent instruction content.
instructions_payload = _truncate(instr_block, "PBI_AI_Instructions")
verified_answers_payload = _truncate(qa_block, "PBI_AI_VerifiedAnswers")

print(f"PBI_AI_Instructions length: {len(instructions_payload)}")
print("--- Preview (first 500 chars) ---")
print(instructions_payload[:500])
print("..." if len(instructions_payload) > 500 else "")

print(f"\nPBI_AI_VerifiedAnswers length: {len(verified_answers_payload)}")
print("--- Preview (first 500 chars) ---")
print(verified_answers_payload[:500])
print("..." if len(verified_answers_payload) > 500 else "")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Write annotation with SemPy Labs


def _find_collection_item_by_name(collection, name: str):
    target = name.strip().lower()

    try:
        return collection[name]
    except Exception:
        pass

    for item in collection:
        item_name = getattr(item, "Name", None)
        if isinstance(item_name, str) and item_name.strip().lower() == target:
            return item

    return None


def _resolve_model_workspace_id() -> str:
    return globals().get("MODEL_WORKSPACE_ID", "b976cac2-7754-4061-88c2-61c0ac016a99")


def _discover_tom_connector(labs_module):
    candidates = []

    if labs_module is not None:
        fn = getattr(labs_module, "connect_semantic_model", None)
        if callable(fn):
            candidates.append(("labs.connect_semantic_model", fn))

    for mod_name in [
        "sempy_labs.tom",
        "sempy_labs.tom._model",
        "sempy_labs._model",
    ]:
        try:
            module_obj = __import__(mod_name, fromlist=["connect_semantic_model"])
            fn = getattr(module_obj, "connect_semantic_model", None)
            if callable(fn):
                candidates.append((f"{mod_name}.connect_semantic_model", fn))
        except Exception:
            pass

    return candidates[0] if candidates else (None, None)


def _set_annotation_via_labs(labs_module, name: str, value: str):
    if labs_module is None:
        return False, "sempy_labs unavailable"

    candidate_modules = [labs_module]
    for mod_name in ["sempy_labs.annotations", "sempy_labs"]:
        try:
            candidate_modules.append(__import__(mod_name, fromlist=["*"]))
        except Exception:
            pass

    candidate_methods = [
        "set_annotation",
        "update_annotation",
        "add_annotation",
        "set_model_annotation",
    ]

    workspace_id = _resolve_model_workspace_id()

    errors = []
    for module_obj in candidate_modules:
        module_name = getattr(module_obj, "__name__", "labs")
        for method_name in candidate_methods:
            method = getattr(module_obj, method_name, None)
            if not callable(method):
                continue

            call_variants = [
                {
                    "dataset": MODEL_NAME,
                    "workspace": workspace_id,
                    "annotation_name": name,
                    "annotation_value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "workspace_id": workspace_id,
                    "annotation_name": name,
                    "annotation_value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "annotation_name": name,
                    "annotation_value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "workspace": workspace_id,
                    "name": name,
                    "value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "name": name,
                    "value": value,
                },
            ]

            for kwargs in call_variants:
                try:
                    method(**kwargs)
                    return True, f"{module_name}.{method_name}"
                except Exception as ex:
                    errors.append(f"{module_name}.{method_name}: {ex}")

    # SemPy Labs v2 commonly exposes connect_semantic_model/TOM wrapper
    # rather than direct set_annotation helpers. Treat this as SemPy path.
    connector_name, connector = _discover_tom_connector(labs_module)
    ok_tom, detail_tom = _set_annotation_via_tom(connector, connector_name, name=name, value=value)
    if ok_tom:
        return True, f"{detail_tom} (SemPy Labs v2 TOM wrapper)"

    if errors:
        errors.append(f"tom_wrapper: {detail_tom}")
        return False, " | ".join(errors[:3])

    return False, f"no compatible sempy_labs annotation writer found | tom_wrapper: {detail_tom}"


def _set_annotation_via_tom(connector, connector_name, name: str, value: str):
    if connector is None:
        return False, "no supported TOM connector found"

    workspace_id = _resolve_model_workspace_id()

    connect_variants = [
        {"dataset": MODEL_NAME, "workspace": workspace_id, "readonly": False},
        {"dataset": MODEL_NAME, "workspace_id": workspace_id, "readonly": False},
        {"dataset": MODEL_NAME, "readonly": False},
    ]

    last_ex = None
    for connect_kwargs in connect_variants:
        try:
            with connector(**connect_kwargs) as tom:
                annotations = getattr(tom.model, "Annotations", None)
                if annotations is None:
                    return False, "model annotations collection unavailable"

                existing = _find_collection_item_by_name(annotations, name)
                if existing is not None:
                    existing.Value = value
                    return True, f"updated via {connector_name or 'unknown_connector'}"

                # New annotation: TOM's Annotations.Add() requires an Annotation
                # object (Add(str, str) has no matching .NET overload), so build
                # one via the Microsoft.AnalysisServices.Tabular namespace before
                # adding it to the collection.
                try:
                    from Microsoft.AnalysisServices.Tabular import Annotation as TomAnnotation

                    new_annotation = TomAnnotation()
                    new_annotation.Name = name
                    new_annotation.Value = value
                    annotations.Add(new_annotation)
                    return True, f"added via {connector_name or 'unknown_connector'}"
                except Exception as ex:
                    return False, f"annotation add failed: {ex}"
        except Exception as ex:
            last_ex = ex

    return False, f"annotation write failed: {last_ex}"


def _publish_annotation_semantic_surface(name: str, value: str, labs_module):
    ok, detail = _set_annotation_via_labs(labs_module, name=name, value=value)
    if ok:
        return True, detail

    sempy_only_mode = globals().get("USE_SEMPY_ONLY", True)
    if sempy_only_mode:
        return False, f"SemPy-only mode enabled; annotation publish failed via SemPy Labs: {detail}"

    connector_name, connector = _discover_tom_connector(labs_module)
    return _set_annotation_via_tom(connector, connector_name, name=name, value=value)

LABS_SETUP_MESSAGE = (
    "semantic-link-labs is not installed in this Fabric environment. "
    "Install it in the environment configuration (not at notebook runtime), "
    "restart the session, and rerun this notebook."
)

try:
    import sempy_labs as labs
except ModuleNotFoundError:
    labs = None
    print(f"[WARN] {LABS_SETUP_MESSAGE}")
except Exception as ex:
    labs = None
    print("[WARN] sempy_labs import failed.")
    print("       Verify semantic-link-labs is installed in the environment configuration,")
    print("       then restart the session and rerun this notebook.")
    print(f"       Detail: {ex}")


# Publish each governed construct to its own annotation surface that standalone
# Copilot reads — keeps verified Q&A independently regenerable from instructions.
annotations_to_publish = {
    "PBI_AI_Instructions": instructions_payload,
    "PBI_AI_VerifiedAnswers": verified_answers_payload,
}
annotation_results = {}

if DEMO_MODE:
    print("[DRY RUN] Annotation write skipped")
else:
    if labs is None:
        raise RuntimeError(f"DEMO_MODE=False requires sempy_labs. {LABS_SETUP_MESSAGE}")

    for annotation_name, annotation_value in annotations_to_publish.items():
        applied, detail = _publish_annotation_semantic_surface(
            name=annotation_name,
            value=annotation_value,
            labs_module=labs,
        )
        annotation_results[annotation_name] = (applied, detail)

        if applied:
            print(f"[APPLIED] Annotation {annotation_name} ({len(annotation_value)} chars) | {detail}")
        else:
            print(f"[WARN] Annotation write was not applied for {annotation_name}.")
            print(f"       Detail: {detail}")
            print("       Annotation preview (first 500 chars):")
            print(annotation_value[:500])

    failed_annotations = [
        name for name, (applied, _) in annotation_results.items() if not applied
    ]
    if failed_annotations:
        raise RuntimeError(
            "Governed model annotation writes failed: " + ", ".join(failed_annotations)
        )

    connector_name, connector = _discover_tom_connector(labs)
    if connector is None:
        raise RuntimeError("SemPy Labs TOM connector unavailable for model annotation readback")

    model_annotation_readback = {}
    with connector(dataset=MODEL_NAME, workspace=_resolve_model_workspace_id(), readonly=True) as tom:
        model_annotations = getattr(tom.model, "Annotations", None)
        for annotation_name in annotations_to_publish:
            annotation = _find_collection_item_by_name(model_annotations, annotation_name)
            model_annotation_readback[annotation_name] = None if annotation is None else str(annotation.Value)

    readback_mismatches = [
        name
        for name, expected in annotations_to_publish.items()
        if model_annotation_readback.get(name) != expected
    ]
    if readback_mismatches:
        raise RuntimeError(
            "Governed model annotation readback mismatch: " + ", ".join(readback_mismatches)
        )
    if model_annotation_readback["PBI_AI_Instructions"] == model_annotation_readback["PBI_AI_VerifiedAnswers"]:
        raise RuntimeError("AI instructions and verified answers must remain distinct model annotations")

    print(
        "Model annotation readback passed: "
        f"PBI_AI_Instructions={len(model_annotation_readback['PBI_AI_Instructions'])} chars, "
        f"PBI_AI_VerifiedAnswers={len(model_annotation_readback['PBI_AI_VerifiedAnswers'])} chars"
    )

    # Operational debug log: records applied/failed status + detail per annotation
    # so a live run's outcome can be inspected without a separate readback notebook.
    try:
        mssparkutils.fs.mkdirs("Files/debug")
        debug_lines = [
            f"{name}: applied={annotation_results.get(name, (False, 'not attempted'))[0]} "
            f"detail={annotation_results.get(name, (False, 'not attempted'))[1]}"
            for name in annotations_to_publish
        ]
        mssparkutils.fs.put("Files/debug/nb05_last_run.txt", "\n".join(debug_lines), True)
    except Exception as debug_ex:
        print(f"[WARN] Could not write nb05 debug log: {debug_ex}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Summary

print("\n=== nb_05 Summary ===")
print(f"  Model:                        {MODEL_NAME}")
print(f"  AI instructions:              {len(ai_instructions)}")
print(f"  Verified Q&A pairs:           {len(qa_parts)}")
print(f"  PBI_AI_Instructions chars:    {len(instructions_payload)} / {MAX_ANNOTATION_CHARS}")
print(f"  PBI_AI_VerifiedAnswers chars: {len(verified_answers_payload)} / {MAX_ANNOTATION_CHARS}")
if DEMO_MODE:
    print("  Status: DRY RUN")
else:
    for annotation_name in annotations_to_publish:
        applied, detail = annotation_results.get(annotation_name, (False, "not attempted"))
        print(f"  {annotation_name}: {'APPLIED' if applied else 'FAILED'} | {detail}")
print("\nTo verify: ask Copilot 'what is our FCR?' or 'what is our CSAT score?'")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
