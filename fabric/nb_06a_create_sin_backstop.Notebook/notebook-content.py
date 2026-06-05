# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# # nb_06a — Create ENERCARE.PRIVACY.SIN_BACKSTOP Custom Purview SIT
#
# **Family:** Purview admin operations (extends `nb_06_purview_sql_grants`)
# **Role:** Phase B Layer-2 SIN classifier backstop registration
# **Run:** Day 1 Step 1.6 — once per tenant. Idempotent (safe to re-run).
#
# This notebook wraps `tools/purview_create_sin_backstop.py` so the SIN SIT
# registration runs in-notebook and stays in the project build pattern.
#
# **What it does:**
# 1. Imports the helper functions from `tools/purview_create_sin_backstop.py`
# 2. Acquires a Purview data-plane token (DefaultAzureCredential → user identity in Fabric)
# 3. Creates the `ENERCARE.PRIVACY.SIN_BACKSTOP` classification (Layer 2 — column-name + regex, no Luhn requirement)
# 4. Creates the classification rule (regex `\b[1-79]\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b` + column-name `^(sin|sin_full|sin_last_4|social_insurance_number|nas)$`)
# 5. Verifies the rule is enabled
#
# **Why it matters:** the built-in `MICROSOFT.CANADIAN.SIN` classifier requires Luhn-valid 9-digit values to fire confidently.
# Layer 1 (Luhn generation in nb_05a) guarantees that. Layer 2 (this notebook) is the column-name + regex backstop
# that fires even on partial SIN columns (`sin_last_4`) and on synthetic data that doesn't pass Luhn.
# See `docs/purview-sin-classifier-backstop.md` for the full strategy.
#
# **Prerequisites:**
# - `Purview-West3` deployed (G7-1 🟢 Done)
# - User has Purview Data Source Administrator or Data Curator role
# - `tools/purview_create_sin_backstop.py` mounted at the path below

# CELL ********************

# === Cell 1: Imports and configuration ===

import sys
import os

TOOLS_PATH = "/lakehouse/default/Files/tools"  # adjust if your repo mount differs
if TOOLS_PATH not in sys.path:
    sys.path.insert(0, TOOLS_PATH)

# Import helper functions from the canonical Python module
from purview_create_sin_backstop import (  # noqa: E402
    get_token,
    create_classification,
    create_classification_rule,
    verify,
    PURVIEW_ACCOUNT,
    CLASSIFICATION_NAME,
)

print(f"Target Purview account: {PURVIEW_ACCOUNT}")
print(f"Classification to register: {CLASSIFICATION_NAME}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# === Cell 2: Acquire Purview data-plane token ===
#
# Uses azure.identity.DefaultAzureCredential which in a Fabric notebook
# resolves through the user's interactive identity. Sean's account has
# Purview Data Source Administrator role per G1-4.

token = get_token()
print(f"Token acquired (length: {len(token)} chars)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# === Cell 3: Create the custom classification ===
#
# Idempotent — Purview returns 409 Conflict if it already exists; helper
# treats that as success.

create_classification(token)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# === Cell 4: Create the classification rule ===
#
# Defines:
#   - regex pattern (3 SIN formats: hyphenated, spaced, raw; first-digit 1-7 or 9)
#   - column-name pattern (^(sin|sin_full|sin_last_4|social_insurance_number|nas)$)
#   - minimum match threshold = 50% (loosened from default 60% so partial SIN columns fire)

create_classification_rule(token)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# === Cell 5: Verify and summarize ===
#
# Reads the rule back to confirm it landed and is enabled. Output should
# show:
#   name: ENERCARE.PRIVACY.SIN_BACKSTOP
#   status: Enabled
#   min match %: 50

verify(token)

print()
print("=" * 70)
print("Next step: enable this classification in the scan rule set used by")
print("the Enercare scans (sqldemo + Fabric workspace), then re-run scans.")
print("Day 3 Step 3.10 in docs/purview-5-day-execution-plan.md covers this.")
print("=" * 70)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
