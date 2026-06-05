# ============================================================================
# Phase B Cell Additions for nb_05a_publish_synthetic_data_to_sql.Notebook
# ============================================================================
#
# Purpose: Execute Phase A Purview demo SQL artifacts from inside the notebook,
# using the same private-path pyodbc connection nb_05a already establishes.
# Solves the SSMS public-access denial — nb_05a runs from Fabric and has a
# working managed private endpoint to sqldemo.
#
# Pattern: mirrors nb_06_purview_sql_grants.Notebook which wraps sql/03 the
# same way. SQL files remain canonical text under sql/; orchestration lives
# in the notebook.
#
# Run order: insert these cells AFTER the existing nb_05a cells that publish
# the synthetic operational dataset to sqldemo (so the 7 base tables already
# exist before we add columns and FKs to them).
#
# Cells covered:
#   B1 — Execute sql/04_purview_demo_extensions.sql (DDL extensions)
#   B2 — Verify DDL applied
#   B3 — Execute sql/05_seed_purview_demo_data.sql (seed data)
#   B4 — Verify seed counts
#   B5 — Backfill Luhn-valid SINs via tools/sin_luhn_generator.py
#   B6 — Spot-check SIN validity
#
# Each cell below is annotated with "# === CELL Bx ===" — paste each as a
# new code cell in nb_05a, in order.
# ============================================================================


# === CELL B1 — Execute sql/04_purview_demo_extensions.sql (DDL) ===
#
# Assumes nb_05a has already established a pyodbc connection 'conn' to
# sqldemo. If your nb_05a uses a different connection variable name,
# rename below to match.

import os

SQL_REPO_ROOT = "/lakehouse/default/Files/sql"  # adjust if your repo mount differs
DDL_FILE      = os.path.join(SQL_REPO_ROOT, "04_purview_demo_extensions.sql")

with open(DDL_FILE, "r", encoding="utf-8") as f:
    ddl_script = f.read()

# Azure SQL pyodbc cannot execute a multi-batch script in one cursor.execute() call
# because it doesn't understand the "GO" batch separator. Split on GO and run each
# batch individually. This matches the pattern in nb_06_purview_sql_grants.

def split_sql_batches(script: str) -> list[str]:
    """Split T-SQL script on GO batch separators (case-insensitive, line-anchored)."""
    batches = []
    current = []
    for line in script.splitlines():
        if line.strip().upper() == "GO":
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    tail = "\n".join(current).strip()
    if tail:
        batches.append(tail)
    return batches

batches = split_sql_batches(ddl_script)
print(f"DDL script: {len(batches)} batches to execute")

cur = conn.cursor()
for i, batch in enumerate(batches, 1):
    try:
        cur.execute(batch)
        conn.commit()
    except Exception as e:
        # IF NOT EXISTS guards in 04_*.sql make most batches idempotent;
        # log unexpected failures but continue.
        print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")

print(f"DDL applied: 04_purview_demo_extensions.sql")


# === CELL B2 — Verify DDL applied ===

verify_ddl_sql = """
SELECT 'new tables present'                    AS check_name,
       COUNT(*)                                AS count_actual,
       6                                       AS count_expected
  FROM sys.tables
 WHERE name IN ('employees','service_zones','customer_consents',
                'customer_complaints','data_owners_directory','audit_data_access')
UNION ALL
SELECT 'customers PII columns added',
       CASE WHEN COL_LENGTH('dbo.customers','date_of_birth')   IS NOT NULL
              AND COL_LENGTH('dbo.customers','sin_last_4')     IS NOT NULL
              AND COL_LENGTH('dbo.customers','owner_email')    IS NOT NULL
              AND COL_LENGTH('dbo.customers','marketing_consent') IS NOT NULL
            THEN 4 ELSE 0 END,
       4
UNION ALL
SELECT 'service_accounts GPS columns added',
       CASE WHEN COL_LENGTH('dbo.service_accounts','latitude')          IS NOT NULL
              AND COL_LENGTH('dbo.service_accounts','longitude')         IS NOT NULL
              AND COL_LENGTH('dbo.service_accounts','service_zone_code') IS NOT NULL
            THEN 3 ELSE 0 END,
       3
UNION ALL
SELECT 'billing_transactions payment partials added',
       CASE WHEN COL_LENGTH('dbo.billing_transactions','bank_routing_last_4') IS NOT NULL
              AND COL_LENGTH('dbo.billing_transactions','card_pan_last_4')    IS NOT NULL
            THEN 2 ELSE 0 END,
       2;
"""

cur.execute(verify_ddl_sql)
rows = cur.fetchall()
print(f"\n{'check_name':45s} {'actual':>8s} {'expected':>10s}  status")
print("-" * 80)
for r in rows:
    status = "GREEN" if r[1] == r[2] else "RED"
    print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# === CELL B3 — Execute sql/05_seed_purview_demo_data.sql (seed data) ===

SEED_FILE = os.path.join(SQL_REPO_ROOT, "05_seed_purview_demo_data.sql")

with open(SEED_FILE, "r", encoding="utf-8") as f:
    seed_script = f.read()

batches = split_sql_batches(seed_script)
print(f"Seed script: {len(batches)} batches to execute")

cur = conn.cursor()
for i, batch in enumerate(batches, 1):
    try:
        cur.execute(batch)
        conn.commit()
    except Exception as e:
        print(f"  Batch {i}/{len(batches)} note: {type(e).__name__}: {e}")

print(f"Seed applied: 05_seed_purview_demo_data.sql")


# === CELL B4 — Verify seed counts ===

verify_seed_sql = """
SELECT 'employees'             AS table_name, COUNT(*) AS row_count, 11  AS expected FROM dbo.employees
UNION ALL
SELECT 'service_zones',                       COUNT(*),               8       FROM dbo.service_zones
UNION ALL
SELECT 'customer_consents',                   COUNT(*),             120       FROM dbo.customer_consents
UNION ALL
SELECT 'customer_complaints',                 COUNT(*),              18       FROM dbo.customer_complaints
UNION ALL
SELECT 'data_owners_directory',               COUNT(*),              13       FROM dbo.data_owners_directory
UNION ALL
SELECT 'audit_data_access',                   COUNT(*),             200       FROM dbo.audit_data_access
UNION ALL
SELECT 'customers with DOB backfilled',       COUNT(*),              50       FROM dbo.customers
 WHERE date_of_birth IS NOT NULL
UNION ALL
SELECT 'service_accounts with GPS backfilled', COUNT(*),              56      FROM dbo.service_accounts
 WHERE latitude IS NOT NULL;
"""

cur.execute(verify_seed_sql)
rows = cur.fetchall()
print(f"\n{'table_name':45s} {'rows':>8s} {'expected':>10s}  status")
print("-" * 80)
for r in rows:
    status = "GREEN" if r[1] == r[2] else "YELLOW"  # consents/audit have slight variance
    print(f"{r[0]:45s} {r[1]:>8d} {r[2]:>10d}  {status}")


# === CELL B5 — Backfill Luhn-valid SINs via tools/sin_luhn_generator.py ===
#
# Layer 1 of the SIN classifier backstop strategy. Generates Luhn-valid
# 9-digit Canadian SINs (first digit 9 = Temporary Resident range for
# unambiguous synthetic data) and writes them in place. See
# docs/purview-sin-classifier-backstop.md for the full three-layer strategy.

import sys
TOOLS_PATH = "/lakehouse/default/Files/tools"  # adjust if your repo mount differs
if TOOLS_PATH not in sys.path:
    sys.path.insert(0, TOOLS_PATH)

from sin_luhn_generator import generate_synthetic_sin, hyphenated  # noqa: E402

import random
rng = random.Random(20260605)  # reproducible across runs

# Populate dbo.employees.sin_full with hyphenated Luhn-valid SINs
cur.execute("SELECT employee_id FROM dbo.employees WHERE sin_full IS NULL")
emp_ids = [row[0] for row in cur.fetchall()]
print(f"Backfilling sin_full for {len(emp_ids)} employees...")

for emp_id in emp_ids:
    sin9 = generate_synthetic_sin(first_digit="9", rng=rng)
    cur.execute(
        "UPDATE dbo.employees SET sin_full = ? WHERE employee_id = ?",
        hyphenated(sin9), emp_id,
    )
conn.commit()
print(f"  employees.sin_full populated: {len(emp_ids)} rows")

# Populate dbo.customers.sin_last_4 with the last 4 digits of Luhn-valid SINs
cur.execute("SELECT customer_id FROM dbo.customers WHERE sin_last_4 IS NULL")
cust_ids = [row[0] for row in cur.fetchall()]
print(f"Backfilling sin_last_4 for {len(cust_ids)} customers...")

for cust_id in cust_ids:
    sin9 = generate_synthetic_sin(first_digit="9", rng=rng)
    cur.execute(
        "UPDATE dbo.customers SET sin_last_4 = ? WHERE customer_id = ?",
        sin9[-4:], cust_id,
    )
conn.commit()
print(f"  customers.sin_last_4 populated: {len(cust_ids)} rows")


# === CELL B6 — Spot-check SIN validity ===
#
# Pull 5 random SINs from employees, verify each passes the Luhn check.
# Layer 1 backstop succeeds if all 5 pass.

from sin_luhn_generator import is_luhn_valid  # noqa: E402

cur.execute("SELECT TOP 5 employee_id, sin_full FROM dbo.employees ORDER BY NEWID()")
samples = cur.fetchall()

print(f"\nSIN Luhn validation spot-check (Layer 1 backstop):")
print(f"{'employee_id':>12s}  {'sin_full':>15s}  result")
print("-" * 45)
all_valid = True
for emp_id, sin_full in samples:
    valid = is_luhn_valid(sin_full)
    all_valid = all_valid and valid
    print(f"{emp_id:>12d}  {sin_full:>15s}  {'GREEN' if valid else 'RED'}")

print(f"\nOverall: {'ALL GREEN — Layer 1 backstop ready' if all_valid else 'RED — investigate generator'}")
