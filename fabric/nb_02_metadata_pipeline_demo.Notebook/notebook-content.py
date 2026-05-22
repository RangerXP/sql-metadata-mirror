# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "0ee837e4-2fd3-40d9-b228-1f167b504b7d",
# META       "default_lakehouse_name": "lh_enercare_demo",
# META       "default_lakehouse_workspace_id": "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4",
# META       "known_lakehouses": [
# META         {
# META           "id": "0ee837e4-2fd3-40d9-b228-1f167b504b7d"
# META         }
# META       ]
# META     },
# META     "warehouse": {
# META       "default_warehouse": "595a4488-0f92-41b6-9cdb-f7e09337c2de",
# META       "known_warehouses": [
# META         {
# META           "id": "595a4488-0f92-41b6-9cdb-f7e09337c2de",
# META           "type": "Lakewarehouse"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

import re
import hashlib
import json
from datetime import datetime, timezone
from pyspark.sql import Row
from pyspark.sql.types import *
from pyspark.sql.functions import col, lit, current_timestamp

# ---------------------------------------------------------------------------
# Configuration — swap these for production
# ---------------------------------------------------------------------------

# TODO: replace with your actual Fabric workspace / lakehouse names
DEMO_LAKEHOUSE   = "lh_enercare_demo"   # source data (Delta tables from nb_01)
META_LAKEHOUSE   = "lh_metadata"        # metadata hub (same as README Phase 2)

# TODO: in production, set these to your Azure SQL Server connection details
# SQL_JDBC_URL  = "jdbc:sqlserver://<server>.database.windows.net:1433;database=<db>"
# SQL_USER      = dbutils.secrets.get(scope="enercare-kv", key="sql-user")
# SQL_PASSWORD  = dbutils.secrets.get(scope="enercare-kv", key="sql-password")

# TODO: in production, set these for Purview
# PURVIEW_ACCOUNT    = "enercare-purview"
# PURVIEW_TENANT_ID  = "<tenant-id>"
# PURVIEW_CLIENT_ID  = "<service-principal-client-id>"
# PURVIEW_SECRET     = dbutils.secrets.get(scope="enercare-kv", key="purview-sp-secret")

# Demo mode — no live connections
DEMO_MODE  = False   # set False when swapping in production SQL + Purview creds
SOURCE_DB  = "enercare_demo"  # used in Purview qualified names

print(f"DEMO_MODE          : {DEMO_MODE}")
print(f"Source DB (demo)   : {SOURCE_DB}")
print(f"Data lakehouse     : {DEMO_LAKEHOUSE}")
print(f"Metadata lakehouse : {META_LAKEHOUSE}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#
# In production this dict is replaced by a JDBC read:
#   SELECT o.name, o.type_desc, m.definition
#   FROM   sys.sql_modules m
#   JOIN   sys.objects     o ON o.object_id = m.object_id
#   WHERE  o.type IN ('V','P','IF','TF')
#   AND    o.is_ms_shipped = 0
#
# The Python extractor in Phase 1 is identical whether the definition comes
# from this dict or from a live JDBC read — only the data source changes.
# ===========================================================================

# TODO: replace SQL_MODULES with JDBC read from sys.sql_modules (see comment above)
SQL_MODULES = {
    "vw_customer_360": {
        "type": "VIEW",
        "definition": """\
/*
  @asset_type:    view
  @business_name: Customer 360
  @description:   Unified customer profile combining account details, active
                  contracts, equipment count, and lifetime billing value.
                  Primary analytical surface for customer success and
                  retention teams.  One row per customer.
  @owner:         Data & Analytics
  @steward:       analytics@enercare.ca
  @domain:        Customer
  @grain:         One row per customer (customer_id)
  @refresh:       real-time (Direct Lake)
  @sensitivity:   Confidential – PII
  @glossary:      Customer; Contract; LifetimeValue; ChurnRisk
  @upstream:      demo.customers | demo.service_accounts | demo.contracts | demo.billing_transactions

  @column customer_id:           Surrogate key for the customer record
  @column account_number:        External-facing identifier used in all customer communications
  @column full_name:             Concatenated first + last name; use display-only, not as a join key
  @column customer_type:         Segmentation bucket: Residential | Commercial | MUR
  @column status:                Current lifecycle state of the account
  @column city:                  City of the customer's primary service address
  @column postal_code:           First 3 chars = FSA (Forward Sortation Area) used for geo-clustering
  @column active_contract_count: Count of non-cancelled, non-expired contracts as of query date
  @column total_active_equipment: Active equipment items registered across all service accounts
  @column lifetime_value:        Sum of MonthlyCharge + OneTimeCharge (status=Posted) since account open; CAD
  @column avg_monthly_spend:     Mean of monthly charges over the trailing 12 months; NULL if tenure < 12 months
  @column first_contract_date:   Date of earliest contract; used as a proxy for customer tenure
  @column last_service_date:     Most recent completed service request; NULL if no service history
  @column tenure_months:         Months between created_date and today; used for cohort analysis

  @kpi active_contract_count:    metric | COUNT(contracts WHERE status = Active) | non-negative integer
  @kpi lifetime_value:           metric | SUM(billing WHERE type IN (MonthlyCharge,OneTimeCharge) AND status=Posted) | CAD, 2 dp
  @kpi avg_monthly_spend:        metric | lifetime_value / NULLIF(tenure_months,0) | CAD, 2 dp
  @kpi tenure_months:            metric | DATEDIFF(MONTH, created_date, GETDATE()) | integer months

  @notes: Excludes test/internal accounts (customer_type <> 'Internal').
          Lifetime value uses posted transactions only.
*/
CREATE OR ALTER VIEW demo.vw_customer_360 AS
SELECT c.customer_id, ...
FROM demo.customers c
LEFT JOIN demo.service_accounts sa ON sa.customer_id = c.customer_id
...
"""
    },
    "vw_monthly_revenue": {
        "type": "VIEW",
        "definition": """\
/*
  @asset_type:    view
  @business_name: Monthly Recurring Revenue by Product
  @description:   Calculates MRR contribution per contract for each calendar
                  month.  Supports Finance and Strategy reporting on revenue
                  growth, churn, and product mix.
  @owner:         Finance Analytics
  @steward:       finance.analytics@enercare.ca
  @domain:        Revenue
  @grain:         One row per (contract_id, billing_month)
  @refresh:       daily (scheduled Lakehouse refresh)
  @sensitivity:   Internal
  @glossary:      MRR; Contract; Churn; Expansion; ARR
  @upstream:      demo.contracts | demo.products | demo.billing_transactions | demo.service_accounts

  @column contract_id:      Unique contract identifier; join key to demo.contracts
  @column service_account_id: Owning service account; join key to demo.service_accounts
  @column product_name:     Friendly product name from the product master
  @column product_category: High-level revenue category: Rental | Protection | SmartHome | Cooling | Heating
  @column billing_month:    First day of the reporting month (YYYY-MM-01)
  @column contract_status:  Contract state at query time
  @column monthly_amount:   MRR contribution of this contract in CAD
  @column is_new:           1 if this is the first billing month for this contract (acquisition)
  @column is_churn:         1 if this contract was cancelled in this billing month

  @kpi monthly_amount:      metric | SUM(contracts.monthly_amount WHERE is_active_in_month) | CAD MRR
  @kpi is_churn:            metric | COUNT(contracts WHERE cancellation_date IN billing_month) | integer
  @kpi is_new:              metric | COUNT(contracts WHERE start_date IN billing_month) | integer

  @notes: MRR spine covers Jan 2023 – Dec 2024.
*/
CREATE OR ALTER VIEW demo.vw_monthly_revenue AS ...
"""
    },
    "vw_equipment_health": {
        "type": "VIEW",
        "definition": """\
/*
  @asset_type:    view
  @business_name: Equipment Health Dashboard
  @description:   Active equipment inventory enriched with age, warranty
                  status, and service history.  Supports proactive maintenance
                  planning and field operations scheduling.
  @owner:         Field Operations
  @steward:       operations.data@enercare.ca
  @domain:        Operations
  @grain:         One row per active equipment_id
  @refresh:       daily
  @sensitivity:   Internal
  @glossary:      Equipment; Warranty; ServiceHistory; MTBF; Rental
  @upstream:      demo.equipment_registry | demo.service_accounts | demo.customers | demo.service_requests

  @column equipment_id:              Surrogate key for the equipment record
  @column equipment_type:            Category: Water Heater | Furnace | Central AC | Heat Pump | Smart Thermostat
  @column make:                      Manufacturer name
  @column model:                     Manufacturer model number or name
  @column serial_number:             Factory serial; used for warranty claims
  @column ownership_type:            Rental = Enercare owns; Customer-Owned = Enercare services only
  @column fuel_type:                 Energy source: Natural Gas | Electric | Propane
  @column install_date:              Date equipment was installed at the service address
  @column age_years:                 Decimal years since install_date
  @column is_under_warranty:         1 if warranty_expiry >= today; 0 if expired or NULL
  @column days_to_warranty_expiry:   Positive = remaining days; negative = past expiry
  @column service_request_count:     Total lifetime service requests against this equipment
  @column last_service_type:         Most recent completed service request type
  @column last_service_date:         Date of most recent completed service visit
  @column customer_account_number:   Customer account number for CS lookup
  @column city:                      City of service address

  @kpi age_years:              metric | DATEDIFF(day,install_date,GETDATE()) / 365.25 | decimal years
  @kpi service_request_count:  metric | COUNT(service_requests WHERE equipment_id = X) | integer
  @kpi is_under_warranty:      metric | SUM(is_under_warranty) / COUNT(*) | coverage rate 0-1

  @notes: Filters to eq.status = 'Active' only.
*/
CREATE OR ALTER VIEW demo.vw_equipment_health AS ...
"""
    },
    "vw_service_backlog": {
        "type": "VIEW",
        "definition": """\
/*
  @asset_type:    view
  @business_name: Open Service Backlog
  @description:   All open and in-progress service requests enriched with
                  SLA status, customer context, and equipment type.  Primary
                  operational dashboard for dispatch and service coordination.
  @owner:         Field Operations
  @steward:       operations.data@enercare.ca
  @domain:        Operations
  @grain:         One row per open or in-progress service request (request_id)
  @refresh:       real-time (Direct Lake)
  @sensitivity:   Internal
  @glossary:      ServiceRequest; SLA; Priority; Dispatch; FieldOps
  @upstream:      demo.service_requests | demo.service_accounts | demo.customers | demo.equipment_registry

  @column request_id:         Unique service request identifier
  @column request_type:       Work category: Installation | Emergency Repair | Maintenance | Inspection | Upgrade
  @column priority:           Urgency tier: Low | Medium | High | Emergency
  @column status:             Current workflow state: Open | InProgress
  @column description:        Free-text description of the reported issue
  @column created_date:       UTC timestamp when the request was logged
  @column scheduled_date:     Planned service visit date; NULL if not yet scheduled
  @column age_hours:          Elapsed hours from created_date to now
  @column sla_target_hours:   SLA commitment by priority: Emergency=4, High=24, Medium=72, Low=168
  @column is_sla_breach:      1 if age_hours > sla_target_hours and request not yet completed
  @column customer_account:   Customer account number for CS lookup
  @column city:               City of service address
  @column equipment_type:     Equipment associated (NULL if not equipment-related)
  @column technician_id:      Assigned technician; NULL if unassigned

  @kpi is_sla_breach:         metric | COUNT(requests WHERE is_sla_breach=1) | integer; alert > 5
  @kpi age_hours:             metric | AVG(age_hours WHERE status=Open) | hours

  @notes: Filters to status IN ('Open','InProgress') only.
          SLA: Emergency 4h, High 24h, Medium 72h, Low 168h.
*/
CREATE OR ALTER VIEW demo.vw_service_backlog AS ...
"""
    },
}

print(f"Loaded {len(SQL_MODULES)} SQL module definitions")
for name, mod in SQL_MODULES.items():
    print(f"  {mod['type']:<12}  demo.{name}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************


# ===========================================================================
# CELL 3 — Phase 1: Extract metadata from SQL module headers
# ===========================================================================
#
# Python re-implementation of sql/02_extract_from_modules.sql
# Logic is identical — only the execution engine changes (Python vs T-SQL).
# In production the module definitions come from a JDBC read (see Cell 2 TODO).
# ===========================================================================

HEADER_RE = re.compile(r'/\*\s*(.*?)\s*\*/', re.DOTALL)

# Matches "@word:" (simple) or "@word subname:" (column/kpi compound tags)
_TAG_LINE_RE = re.compile(r'^@(\w+)(?:\s+([\w_]+))?:\s*(.*)')


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_module_header(name: str, mod: dict) -> dict:
    definition = mod["definition"]
    header_match = HEADER_RE.search(definition)
    if not header_match:
        return {"_name": name, "_type": mod["type"], "_raw_found": False}

    result = {
        "_name":      name,
        "_type":      mod["type"],
        "_hash":      _compute_hash(definition),
        "_raw_found": True,
        "columns":    {},
        "kpis":       [],
        "upstream":   [],
    }

    cur_tag, cur_sub, cur_lines = None, None, []

    def _flush():
        if cur_tag is None:
            return
        val = re.sub(r'\s+', ' ', ' '.join(cur_lines)).strip()
        if cur_tag == "column" and cur_sub:
            result["columns"][cur_sub] = val
        elif cur_tag == "kpi" and cur_sub:
            parts = [p.strip() for p in val.split("|")]
            result["kpis"].append({
                "name":     cur_sub,
                "kpi_type": parts[0] if parts else None,
                "formula":  parts[1] if len(parts) > 1 else None,
                "unit":     parts[2] if len(parts) > 2 else None,
            })
        elif cur_tag == "upstream":
            result["upstream"] = [u.strip() for u in val.split("|")]
        elif cur_sub is None:
            result[cur_tag] = val

    for line in header_match.group(1).splitlines():
        m = _TAG_LINE_RE.match(line.strip())
        if m:
            _flush()
            cur_tag  = m.group(1)
            cur_sub  = m.group(2)
            cur_lines = [m.group(3)] if m.group(3).strip() else []
        elif cur_tag is not None:
            cur_lines.append(line.strip())
    _flush()

    return result


print("Parsing module headers ...")
parsed = {name: parse_module_header(name, mod) for name, mod in SQL_MODULES.items()}

for name, p in parsed.items():
    n_cols = len(p.get("columns", {}))
    n_kpis = len(p.get("kpis", []))
    print(f"  {name:<30}  domain={p.get('domain','?'):<12}  "
          f"cols={n_cols}  kpis={n_kpis}  hash={p['_hash'][:8]}...")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#          (maps to sql/01_create_metadata_tables.sql populated by 02_extract)
#
# In production these Delta tables in lh_metadata are the OneLake hub that
# the replication step (Phase 2, 03_replicate_meta_to_onelake.py) would
# MERGE into.  In this demo they ARE the hub — one less hop.
# ===========================================================================

# ── 4a: meta.AssetMetadata ──────────────────────────────────────────────────
asset_schema = StructType([
    StructField("AssetId",           IntegerType(), False),
    StructField("SchemaName",        StringType(),  False),
    StructField("ObjectName",        StringType(),  False),
    StructField("ObjectType",        StringType(),  False),
    StructField("BusinessName",      StringType(),  True),
    StructField("Description",       StringType(),  True),
    StructField("Owner",             StringType(),  True),
    StructField("Steward",           StringType(),  True),
    StructField("Domain",            StringType(),  True),
    StructField("Grain",             StringType(),  True),
    StructField("RefreshFrequency",  StringType(),  True),
    StructField("Sensitivity",       StringType(),  True),
    StructField("GlossaryTerms",     StringType(),  True),
    StructField("UpstreamAssets",    StringType(),  True),
    StructField("Notes",             StringType(),  True),
    StructField("DefinitionHash",    StringType(),  True),
    StructField("IsDraft",           IntegerType(), False),
    StructField("LastExtractedUtc",  StringType(),  False),
])

asset_rows = []
for i, (name, p) in enumerate(parsed.items(), start=1):
    asset_rows.append((
        i,
        "demo",
        name,
        p["_type"],
        p.get("business_name"),
        p.get("description"),
        p.get("owner"),
        p.get("steward"),
        p.get("domain"),
        p.get("grain"),
        p.get("refresh"),
        p.get("sensitivity"),
        p.get("glossary"),
        " | ".join(p.get("upstream", [])),
        p.get("notes"),
        p.get("_hash"),
        0,
        datetime.now(timezone.utc).isoformat(),
    ))

df_assets = spark.createDataFrame(asset_rows, schema=asset_schema)
df_assets.write.format("delta").mode("overwrite").saveAsTable(f"{META_LAKEHOUSE}.asset_metadata")
print(f"  meta.asset_metadata: {df_assets.count()} rows written")


# ── 4b: meta.ColumnMetadata ─────────────────────────────────────────────────
col_schema = StructType([
    StructField("ColumnId",          IntegerType(), False),
    StructField("AssetId",           IntegerType(), False),
    StructField("ColumnName",        StringType(),  False),
    StructField("Description",       StringType(),  True),
    StructField("IsDraft",           IntegerType(), False),
    StructField("LastExtractedUtc",  StringType(),  False),
])

col_rows = []
col_id   = 1
asset_id_map = {name: i+1 for i, name in enumerate(parsed.keys())}

for name, p in parsed.items():
    aid = asset_id_map[name]
    for col_name, col_desc in p.get("columns", {}).items():
        col_rows.append((
            col_id,
            aid,
            col_name,
            col_desc,
            0,
            datetime.now(timezone.utc).isoformat(),
        ))
        col_id += 1

df_cols = spark.createDataFrame(col_rows, schema=col_schema)
df_cols.write.format("delta").mode("overwrite").saveAsTable(f"{META_LAKEHOUSE}.column_metadata")
print(f"  meta.column_metadata: {df_cols.count()} rows written")


# ── 4c: meta.KpiMetadata ────────────────────────────────────────────────────
kpi_schema = StructType([
    StructField("KpiId",             IntegerType(), False),
    StructField("AssetId",           IntegerType(), False),
    StructField("KpiName",           StringType(),  False),
    StructField("KpiType",           StringType(),  True),
    StructField("Formula",           StringType(),  True),
    StructField("Unit",              StringType(),  True),
    StructField("IsDraft",           IntegerType(), False),
    StructField("LastExtractedUtc",  StringType(),  False),
])

kpi_rows = []
kpi_id   = 1
for name, p in parsed.items():
    aid = asset_id_map[name]
    for kpi in p.get("kpis", []):
        kpi_rows.append((
            kpi_id,
            aid,
            kpi["name"],
            kpi["kpi_type"],
            kpi["formula"],
            kpi["unit"],
            0,
            datetime.now(timezone.utc).isoformat(),
        ))
        kpi_id += 1

df_kpis = spark.createDataFrame(kpi_rows, schema=kpi_schema)
df_kpis.write.format("delta").mode("overwrite").saveAsTable(f"{META_LAKEHOUSE}.kpi_metadata")
print(f"  meta.kpi_metadata: {df_kpis.count()} rows written")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#
# Equivalent to the filtered view created in 03_replicate_meta_to_onelake.py.
# One wide row per (asset, column) — the downstream "single source of truth"
# consumed by Phase 4 (apply to Fabric) and Phase 5 (Purview push).
# ===========================================================================

spark.sql(f"""
CREATE OR REPLACE VIEW {META_LAKEHOUSE}.vw_business_metadata_current AS
SELECT
    a.SchemaName,
    a.ObjectName,
    a.ObjectType,
    a.BusinessName,
    a.Description                           AS AssetDescription,
    a.Owner,
    a.Steward,
    a.Domain,
    a.Sensitivity,
    a.GlossaryTerms,
    a.UpstreamAssets,
    c.ColumnName,
    c.Description                           AS ColumnDescription,
    k.KpiName,
    k.KpiType,
    k.Formula                               AS KpiFormula,
    k.Unit                                  AS KpiUnit,
    -- Purview-style qualified names
    CONCAT('mssql://{SOURCE_DB}/demo/', a.ObjectName)       AS SourceQualifiedName,
    CONCAT('fabric://', a.SchemaName, '/', a.ObjectName)    AS FabricQualifiedName
FROM       {META_LAKEHOUSE}.asset_metadata  a
LEFT JOIN  {META_LAKEHOUSE}.column_metadata c ON c.AssetId = a.AssetId
LEFT JOIN  {META_LAKEHOUSE}.kpi_metadata    k ON k.AssetId = a.AssetId
                                              AND k.KpiName = c.ColumnName
WHERE a.IsDraft = 0
""")

row_count = spark.table(f"{META_LAKEHOUSE}.vw_business_metadata_current").count()
print(f"  vw_business_metadata_current: {row_count} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#
# In production, data arrives via Fabric Mirroring from Azure SQL DB.
# In this demo the Delta tables were created directly in nb_01.
# This cell just confirms the data is present and queryable.
# ===========================================================================

print("Phase 3 — Data availability check")
for tbl in ["customers", "service_accounts", "products", "equipment_registry"]:
    n = spark.table(f"{DEMO_LAKEHOUSE}.{tbl}").count()
    print(f"  {DEMO_LAKEHOUSE}.{tbl:<25} {n:>5} rows  ✓")

# Run the Customer 360 view query directly in Spark (mimics Direct Lake)
df_c360 = spark.sql(f"""
SELECT
    c.customer_id,
    CONCAT(c.first_name, ' ', c.last_name)  AS full_name,
    c.customer_type,
    c.status,
    c.city,
    c.postal_code,
    DATEDIFF(c.created_date, current_date()) * -1   AS tenure_months,
    COUNT(DISTINCT sa.service_account_id)            AS service_account_count
FROM {DEMO_LAKEHOUSE}.customers c
LEFT JOIN {DEMO_LAKEHOUSE}.service_accounts sa ON sa.customer_id = c.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.customer_type,
         c.status, c.city, c.postal_code, c.created_date
ORDER BY c.customer_id
""")

print(f"\n  Customer 360 sample ({df_c360.count()} rows):")
df_c360.show(5, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#
# Equivalent to the first section of 05_apply_metadata_to_fabric.py.
# Reads from vw_business_metadata_current and issues ALTER TABLE ... ALTER
# COLUMN ... COMMENT statements for each Lakehouse Delta table.
#
# In production this runs against the Mirrored / Silver Lakehouse tables.
# In demo mode it targets lh_enercare_demo tables.
# ===========================================================================

print("Phase 4 — Applying Delta column comments")
print("-" * 60)

# Load metadata index: {table_name: {col_name: description}}
meta_df = spark.table(f"{META_LAKEHOUSE}.vw_business_metadata_current") \
               .filter(col("ColumnName").isNotNull()) \
               .select("ObjectName", "ColumnName", "ColumnDescription") \
               .distinct()

meta_index = {}
for row in meta_df.collect():
    tbl = row["ObjectName"]
    if tbl not in meta_index:
        meta_index[tbl] = {}
    if row["ColumnDescription"]:
        meta_index[tbl][row["ColumnName"]] = row["ColumnDescription"]

# Apply comments to each view's underlying base table where columns match
base_table_map = {
    "vw_customer_360":    "customers",
    "vw_monthly_revenue": None,                # no direct base table in demo
    "vw_equipment_health":"equipment_registry",
    "vw_service_backlog": None,
}

applied = 0
skipped = 0

for view_name, base_table in base_table_map.items():
    if base_table is None:
        print(f"  SKIP  {view_name:<30} (no base table mapping in demo)")
        skipped += 1
        continue

    col_descs = meta_index.get(view_name, {})
    if not col_descs:
        print(f"  SKIP  {view_name:<30} (no column metadata found)")
        skipped += 1
        continue

    # Get actual columns on the Delta table
    try:
        actual_cols = {f.name for f in spark.table(f"{DEMO_LAKEHOUSE}.{base_table}").schema.fields}
    except Exception as e:
        print(f"  WARN  {base_table:<30} not found — {e}")
        skipped += 1
        continue

    for col_name, col_desc in col_descs.items():
        if col_name in actual_cols:
            safe_desc = col_desc.replace("'", "\\'")
            ddl = (f"ALTER TABLE {DEMO_LAKEHOUSE}.{base_table} "
                   f"ALTER COLUMN `{col_name}` COMMENT '{safe_desc}'")
            if DEMO_MODE:
                # In demo mode print the DDL rather than executing
                print(f"  [DRY] {ddl[:100]}...")
            else:
                spark.sql(ddl)
            applied += 1

print(f"\n  Result: {applied} comments applied, {skipped} views skipped")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#
# In production this calls sp_addextendedproperty on the Fabric Warehouse
# (NOT the source OLTP DB — per the README's core principle).
# In demo mode we print the TSQL that would be executed.
# ===========================================================================

print("\nPhase 4 — Warehouse extended properties (dry run)")
print("-" * 60)

asset_df = spark.table(f"{META_LAKEHOUSE}.asset_metadata").collect()
for row in asset_df:
    if row["Description"]:
        tsql = (f"EXEC sp_addextendedproperty "
                f"@name=N'MS_Description', @value=N'{row['Description'][:80]}...', "
                f"@level0type=N'SCHEMA', @level0name=N'demo', "
                f"@level1type=N'VIEW',   @level1name=N'{row['ObjectName']}'")
        print(f"  [DRY-WAREHOUSE] {tsql[:110]}...")

print("\n  → To execute: set DEMO_MODE=False and ensure Warehouse endpoint is configured")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

#
# Equivalent to purview/06_purview_push_descriptions.py (Atlas REST push).
# In demo mode we print the Atlas entity payloads instead of calling the API.
#
# TODO: set DEMO_MODE=False and provide PURVIEW_* credentials above to
#       switch from dry-run to live Atlas API push.
# ===========================================================================

print("\nPhase 5 — Purview Atlas entity preview (dry run)")
print("=" * 60)

meta_rows = (
    spark.table(f"{META_LAKEHOUSE}.vw_business_metadata_current")
    .select("ObjectName", "AssetDescription", "ColumnName",
            "ColumnDescription", "GlossaryTerms", "SourceQualifiedName")
    .distinct()
    .collect()
)

# Build one preview per asset
asset_previews = {}
for row in meta_rows:
    obj = row["ObjectName"]
    if obj not in asset_previews:
        asset_previews[obj] = {
            "typeName":  "mssql_view",
            "attributes": {
                "qualifiedName": row["SourceQualifiedName"],
                "userDescription": row["AssetDescription"],
            },
            "relationshipAttributes": {},
            "column_updates": [],
        }
    if row["ColumnName"] and row["ColumnDescription"]:
        asset_previews[obj]["column_updates"].append({
            "typeName": "mssql_column",
            "attributes": {
                "qualifiedName": f"{row['SourceQualifiedName']}#{row['ColumnName']}",
                "userDescription": row["ColumnDescription"],
            }
        })

for obj, payload in asset_previews.items():
    n_cols = len(payload["column_updates"])
    print(f"\n  Asset : {obj}")
    print(f"    qualifiedName  : {payload['attributes']['qualifiedName']}")
    print(f"    description    : {str(payload['attributes']['userDescription'])[:80]}...")
    print(f"    column updates : {n_cols} column descriptions ready to push")

print(f"\n  Total assets ready : {len(asset_previews)}")
print(f"  Total column updates: {sum(len(v['column_updates']) for v in asset_previews.values())}")

if DEMO_MODE:
    print("\n  [DEMO MODE] Atlas API not called.  To activate:")
    print("    1. Set DEMO_MODE = False in Cell 1")
    print("    2. Provide PURVIEW_ACCOUNT, PURVIEW_TENANT_ID, PURVIEW_CLIENT_ID, PURVIEW_SECRET")
    print("    3. pip install pyapacheatlas (or use purview/06_purview_push_descriptions.py)")
else:
    # TODO: activate live push
    # from pyapacheatlas.auth import ServicePrincipalAuthentication
    # from pyapacheatlas.core import PurviewClient
    # auth   = ServicePrincipalAuthentication(PURVIEW_TENANT_ID, PURVIEW_CLIENT_ID, PURVIEW_SECRET)
    # client = PurviewClient(account_name=PURVIEW_ACCOUNT, authentication=auth)
    # for obj, payload in asset_previews.items():
    #     client.upload_entities([payload, *payload["column_updates"]])
    print("  Live Purview push would execute here")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("\n" + "=" * 60)
print("METADATA PIPELINE DEMO — RUN SUMMARY")
print("=" * 60)

summary = spark.sql(f"""
SELECT
    (SELECT COUNT(*) FROM {META_LAKEHOUSE}.asset_metadata)  AS assets_extracted,
    (SELECT COUNT(*) FROM {META_LAKEHOUSE}.column_metadata) AS columns_extracted,
    (SELECT COUNT(*) FROM {META_LAKEHOUSE}.kpi_metadata)    AS kpis_extracted
""")
summary.show()

print("Phases completed:")
print("  [✓] Phase 0  Header convention applied to 4 demo views")
print("  [✓] Phase 1  Metadata extracted from SQL module definitions")
print("  [✓] Phase 2  Metadata hub Delta tables written (lh_metadata)")
print("  [✓] Phase 3  Demo data confirmed in Fabric Delta tables")
print("  [~] Phase 4  Delta comments and Warehouse XPs (dry run — DEMO_MODE=True)")
print("  [~] Phase 5  Purview Atlas payload preview (dry run — DEMO_MODE=True)")
print()
print("Next steps:")
print("  1. Add real SQL views/procs to SQL_MODULES (Cell 2)")
print("     OR swap SQL_MODULES for a JDBC read from sys.sql_modules")
print("  2. Set DEMO_MODE = False")
print("  3. Provide SQL Server JDBC credentials (Cell 1)")
print("  4. Provide Purview service principal credentials (Cell 1)")
print("  5. Schedule this notebook on 15-min trigger (matches README Phase 2)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
