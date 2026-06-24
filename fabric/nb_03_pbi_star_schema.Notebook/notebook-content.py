# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "e9b09e4e-b7b9-4208-b9ec-bb3433154555",
# META       "default_lakehouse_name": "lh_enercare_demo",
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99",
# META       "known_lakehouses": [
# META         {
# META           "id": "e9b09e4e-b7b9-4208-b9ec-bb3433154555"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# ===== CELL 1 START: Notebook Purpose And Run Context =====

# =============================================================================
# nb_03_pbi_star_schema.py
# Purpose : Builds a Power BI-ready star schema on top of lh_enercare_demo.
#           Reads from the 7 source tables written by nb_01 and writes
#           dimension and fact tables back to the same lakehouse.
# Run after : nb_01_setup_demo_environment.py
# Prereqs   : Attach this notebook to lh_enercare_demo (default lakehouse)
# =============================================================================
# ===== CELL 1 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 2 START: Mirror Configuration And Source Resolver =====

DEMO_LAKEHOUSE = "lh_enercare_demo"
MIRROR_WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
MIRROR_ITEM_ID = "bdf616e8-625e-4b62-8491-519509f6ffaf"  # Mirrored Azure SQL Database item ID in Enercare-West3
MIRROR_ONELAKE_DFS_HOST = "westus3-onelake.dfs.fabric.microsoft.com"
USE_DEMO_FALLBACK = False  # Use mirrored Azure SQL source tables

def mirror_table_path(table_name: str) -> str:
    return (
        f"abfss://{MIRROR_WORKSPACE_ID}@{MIRROR_ONELAKE_DFS_HOST}/"
        f"{MIRROR_ITEM_ID}/Tables/dbo/{table_name}"
    )


def mirror_table_sql(table_name: str) -> str:
    if USE_DEMO_FALLBACK:
        # Fallback: read from demo lakehouse directly (populated by nb_01)
        return f"{DEMO_LAKEHOUSE}.{table_name}"
    else:
        # Read from Fabric SQL mirror ABFSS path
        return f"delta.`{mirror_table_path(table_name)}`"


def source_has_column(table_name: str, column_name: str) -> bool:
    if USE_DEMO_FALLBACK:
        cols = spark.table(mirror_table_sql(table_name)).columns
    else:
        cols = spark.read.format("delta").load(mirror_table_path(table_name)).columns
    return column_name in cols


print(f"Source lakehouse          : {DEMO_LAKEHOUSE}")
print(f"Use fallback to demo      : {USE_DEMO_FALLBACK}")
if not USE_DEMO_FALLBACK:
    print(f"  Mirror workspace        : {MIRROR_WORKSPACE_ID}")
    print(f"  Mirror item ID          : {MIRROR_ITEM_ID}")
print(f"SparkSession              : {spark.version}")
# ===== CELL 2 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 3 START: Build And Persist dim_date =====

import pandas as pd
from pyspark.sql.types import *

date_schema = StructType([
    StructField("DateKey",       IntegerType(), False),
    StructField("FullDate",      DateType(),    False),
    StructField("Year",          IntegerType(), False),
    StructField("Quarter",       IntegerType(), False),
    StructField("Month",         IntegerType(), False),
    StructField("MonthName",     StringType(),  False),
    StructField("Day",           IntegerType(), False),
    StructField("WeekOfYear",    IntegerType(), False),
    StructField("DayOfWeek",     IntegerType(), False),
    StructField("DayName",       StringType(),  False),
    StructField("IsWeekend",     IntegerType(), False),
    StructField("IsLeapYear",    IntegerType(), False),
    StructField("FiscalYear",    IntegerType(), False),
    StructField("FiscalQuarter", IntegerType(), False),
])

dates = pd.date_range("2014-01-01", "2026-12-31", freq="D")
rows = []
for d in dates:
    dt = d.date()
    rows.append((
        int(d.strftime("%Y%m%d")),
        dt,
        d.year, d.quarter, d.month,
        d.strftime("%B"),
        d.day,
        int(d.strftime("%W")),
        d.dayofweek + 1,
        d.strftime("%A"),
        1 if d.dayofweek >= 5 else 0,
        1 if (d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)) else 0,
        d.year + (1 if d.month >= 4 else 0),
        ((d.month - 4) % 12) // 3 + 1,
    ))

df_dim_date = spark.createDataFrame(rows, schema=date_schema)
df_dim_date.write.format("delta").mode("overwrite").saveAsTable(f"{DEMO_LAKEHOUSE}.dim_date")
print(f"  dim_date: {df_dim_date.count()} rows written")
# ===== CELL 3 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 4 START: Build Core Dimensions =====

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.dim_customer USING DELTA AS
SELECT
    customer_id          AS CustomerKey,
    account_number       AS AccountNumber,
    first_name           AS FirstName,
    last_name            AS LastName,
    email                AS Email,
    phone                AS Phone,
    customer_type        AS CustomerType,
    status               AS Status,
    city                 AS City,
    province             AS Province,
    postal_code          AS PostalCode,
    LEFT(postal_code, 3) AS FSA,
    created_date         AS CreatedDate
FROM {mirror_table_sql('customers')}
""")
print(f"  dim_customer: {spark.table(f'{DEMO_LAKEHOUSE}.dim_customer').count()} rows")

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.dim_product USING DELTA AS
SELECT
    product_id        AS ProductKey,
    product_code      AS ProductCode,
    product_name      AS ProductName,
    product_category  AS ProductCategory,
    billing_frequency AS BillingFrequency,
    base_price        AS BasePrice,
    is_active         AS IsActive,
    effective_date    AS EffectiveDate
FROM {mirror_table_sql('products')}
""")
print(f"  dim_product: {spark.table(f'{DEMO_LAKEHOUSE}.dim_product').count()} rows")

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.dim_service_account USING DELTA AS
SELECT
    sa.service_account_id   AS ServiceAccountKey,
    sa.customer_id          AS CustomerKey,
    sa.account_number       AS AccountNumber,
    sa.utility_type         AS UtilityType,
    sa.rate_class           AS RateClass,
    sa.distributor          AS Distributor,
    sa.status               AS Status,
    sa.service_address      AS ServiceAddress,
    sa.city                 AS City,
    sa.postal_code          AS PostalCode,
    LEFT(sa.postal_code, 3) AS FSA,
    sa.opened_date          AS OpenedDate
FROM {mirror_table_sql('service_accounts')} sa
""")
print(f"  dim_service_account: {spark.table(f'{DEMO_LAKEHOUSE}.dim_service_account').count()} rows")
# ===== CELL 4 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 5 START: Build dim_equipment =====

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.dim_equipment USING DELTA AS
SELECT
    e.equipment_id                                               AS EquipmentKey,
    e.service_account_id                                         AS ServiceAccountKey,
    e.equipment_type                                             AS EquipmentType,
    e.make                                                       AS Make,
    e.model                                                      AS Model,
    e.serial_number                                              AS SerialNumber,
    e.ownership_type                                             AS OwnershipType,
    e.fuel_type                                                  AS FuelType,
    e.install_date                                               AS InstallDate,
    e.warranty_expiry                                            AS WarrantyExpiry,
    e.status                                                     AS Status,
    CAST(DATE_FORMAT(e.install_date,    'yyyyMMdd') AS INT)      AS InstallDateKey,
    CAST(DATE_FORMAT(e.warranty_expiry, 'yyyyMMdd') AS INT)      AS WarrantyExpiryDateKey,
    ROUND(DATEDIFF(CURRENT_DATE(), e.install_date) / 365.25, 1) AS AgeYears,
    CASE WHEN e.warranty_expiry >= CURRENT_DATE() THEN 1 ELSE 0 END AS IsUnderWarranty
FROM {mirror_table_sql('equipment_registry')} e
""")
print(f"  dim_equipment: {spark.table(f'{DEMO_LAKEHOUSE}.dim_equipment').count()} rows")
# ===== CELL 5 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 6 START: Build fct_billing =====

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.fct_billing USING DELTA AS
SELECT
    bt.transaction_id                                          AS TransactionKey,
    bt.contract_id                                             AS ContractKey,
    bt.service_account_id                                      AS ServiceAccountKey,
    sa.customer_id                                             AS CustomerKey,
    c.product_id                                               AS ProductKey,
    CAST(DATE_FORMAT(bt.transaction_date, 'yyyyMMdd') AS INT)  AS TransactionDateKey,
    CAST(DATE_FORMAT(bt.due_date,         'yyyyMMdd') AS INT)  AS DueDateKey,
    bt.transaction_type                                        AS TransactionType,
    bt.amount                                                  AS Amount,
    bt.tax_amount                                              AS TaxAmount,
    bt.amount + bt.tax_amount                                  AS TotalAmount,
    bt.payment_method                                          AS PaymentMethod,
    bt.status                                                  AS Status,
    bt.invoice_number                                          AS InvoiceNumber
FROM {mirror_table_sql('billing_transactions')} bt
JOIN {mirror_table_sql('service_accounts')} sa ON sa.service_account_id = bt.service_account_id
JOIN {mirror_table_sql('contracts')} c         ON c.contract_id         = bt.contract_id
""")
print(f"  fct_billing: {spark.table(f'{DEMO_LAKEHOUSE}.fct_billing').count()} rows")
# ===== CELL 6 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 7 START: Build fct_service_request =====

has_no_show_reason_code = source_has_column("service_requests", "no_show_reason_code")
no_show_reason_expr = "sr.no_show_reason_code" if has_no_show_reason_code else "CAST(NULL AS STRING)"
print(f"  service_requests.no_show_reason_code available: {has_no_show_reason_code}")

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.fct_service_request USING DELTA AS
SELECT
    sr.request_id                                               AS RequestKey,
    sr.service_account_id                                       AS ServiceAccountKey,
    sa.customer_id                                              AS CustomerKey,
    sr.equipment_id                                             AS EquipmentKey,
    CAST(DATE_FORMAT(sr.created_date,   'yyyyMMdd') AS INT)     AS CreatedDateKey,
    CAST(DATE_FORMAT(sr.scheduled_date, 'yyyyMMdd') AS INT)     AS ScheduledDateKey,
    CAST(DATE_FORMAT(sr.completed_date, 'yyyyMMdd') AS INT)     AS CompletedDateKey,
    sr.request_type                                             AS RequestType,
    sr.priority                                                 AS Priority,
    sr.status                                                   AS Status,
    sr.description                                              AS Description,
    sr.technician_id                                            AS TechnicianId,
    {no_show_reason_expr}                                       AS NoShowReasonCode,
    sr.resolution_notes                                         AS ResolutionNotes,
    CASE
        WHEN sr.status = 'Completed' AND sr.priority IN ('High','Emergency')
             AND sr.completed_date > sr.scheduled_date         THEN 1
        WHEN sr.status IN ('Open','InProgress') AND sr.priority IN ('High','Emergency')
             AND (sr.scheduled_date IS NULL OR sr.scheduled_date < CURRENT_DATE()) THEN 1
        ELSE 0
    END                                                         AS IsSlaBreachFlag,
    CASE WHEN sr.completed_date IS NOT NULL
         THEN DATEDIFF(sr.completed_date, sr.created_date)
         ELSE NULL
    END                                                         AS DaysToComplete
FROM {mirror_table_sql('service_requests')} sr
JOIN {mirror_table_sql('service_accounts')} sa ON sa.service_account_id = sr.service_account_id
""")
print(f"  fct_service_request: {spark.table(f'{DEMO_LAKEHOUSE}.fct_service_request').count()} rows")
# ===== CELL 7 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 8 START: Build fct_contract_month =====

spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.fct_contract_month USING DELTA AS
WITH months AS (
    SELECT EXPLODE(SEQUENCE(
        DATE '2023-01-01',
        DATE '2024-12-01',
        INTERVAL 1 MONTH
    )) AS BillingMonth
),
active_spine AS (
    SELECT
        c.contract_id,
        c.service_account_id,
        sa.customer_id,
        c.product_id,
        p.billing_frequency,
        c.monthly_amount     AS MonthlyAmount,
        c.contract_status    AS ContractStatus,
        c.start_date         AS ContractStartDate,
        c.cancellation_date  AS CancellationDate,
        m.BillingMonth
    FROM {mirror_table_sql('contracts')} c
    JOIN {mirror_table_sql('service_accounts')} sa ON sa.service_account_id = c.service_account_id
    JOIN {mirror_table_sql('products')} p          ON p.product_id          = c.product_id
    CROSS JOIN months m
    WHERE p.billing_frequency = 'Monthly'
      AND m.BillingMonth >= DATE_TRUNC('MONTH', c.start_date)
      AND (c.cancellation_date IS NULL OR m.BillingMonth <= DATE_TRUNC('MONTH', c.cancellation_date))
)
SELECT
    contract_id                                                   AS ContractKey,
    service_account_id                                            AS ServiceAccountKey,
    customer_id                                                   AS CustomerKey,
    product_id                                                    AS ProductKey,
    BillingMonth,
    CAST(DATE_FORMAT(BillingMonth,      'yyyyMMdd') AS INT)       AS BillingMonthDateKey,
    CAST(DATE_FORMAT(ContractStartDate, 'yyyyMMdd') AS INT)       AS ContractStartDateKey,
    MonthlyAmount,
    ContractStatus,
    CASE WHEN DATE_TRUNC('MONTH', ContractStartDate) = BillingMonth THEN 1 ELSE 0 END AS IsNew,
    CASE WHEN CancellationDate IS NOT NULL
              AND DATE_TRUNC('MONTH', CancellationDate) = BillingMonth THEN 1 ELSE 0 END AS IsChurn
FROM active_spine
""")
print(f"  fct_contract_month: {spark.table(f'{DEMO_LAKEHOUSE}.fct_contract_month').count()} rows")
# ===== CELL 8 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 9 START: Validate Star Schema Row Counts =====

print("\n=== Star schema row counts ===")
dims  = ["dim_date", "dim_customer", "dim_product", "dim_equipment", "dim_service_account"]
facts = ["fct_billing", "fct_service_request", "fct_contract_month"]

print("  Dimensions:")
for t in dims:
    print(f"    {t:<30} {spark.table(f'{DEMO_LAKEHOUSE}.{t}').count():>6} rows")

print("  Facts:")
for t in facts:
    print(f"    {t:<30} {spark.table(f'{DEMO_LAKEHOUSE}.{t}').count():>6} rows")

print("\nStar schema ready.")
# ===== CELL 9 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 10 START: Build dim_cc_agent =====

# Call center dimensions — CC extension
# dim_cc_agent: agent registry for call center agents
spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.dim_cc_agent AS
SELECT
    agent_id,
    agent_name,
    team,
    hire_date
FROM {DEMO_LAKEHOUSE}.cc_agents
""")
print(f"dim_cc_agent:          {spark.table(f'{DEMO_LAKEHOUSE}.dim_cc_agent').count()} rows")
# ===== CELL 10 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 11 START: Build dim_cc_billing_adj =====

# dim_cc_billing_adj: billing adjustment category reference
spark.sql(f"""
CREATE OR REPLACE TABLE {DEMO_LAKEHOUSE}.dim_cc_billing_adj AS
SELECT
    category_code,
    category_desc,
    adj_type
FROM {DEMO_LAKEHOUSE}.ref_cc_billing_adj_category
""")
print(f"dim_cc_billing_adj:    {spark.table(f'{DEMO_LAKEHOUSE}.dim_cc_billing_adj').count()} rows")
# ===== CELL 11 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 12 START: Validate Call Center Layer =====

print("\n=== Call center layer row counts ===")
cc_dims  = ["dim_cc_agent", "dim_cc_billing_adj"]
cc_facts = ["fct_cc_interactions", "fct_cc_transcript_turns"]

print("  CC Dimensions:")
for t in cc_dims:
    print(f"    {t:<30} {spark.table(f'{DEMO_LAKEHOUSE}.{t}').count():>6} rows")

print("  CC Facts:")
for t in cc_facts:
    print(f"    {t:<30} {spark.table(f'{DEMO_LAKEHOUSE}.{t}').count():>6} rows")

print("\nCall center extension ready.")
# ===== CELL 12 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ===== CELL 13 START: Session Cleanup =====

spark.catalog.clearCache()
print("Session cache cleared.")
# ===== CELL 13 END =====


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
