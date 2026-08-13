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

# G17-R6 drift tool: deliberately corrupt dim_equipment.EquipmentType's Description
# outside the approval flow, to prove nb_16 self-heals it on next run.
try:
    from sempy_labs.tom import connect_semantic_model
except ImportError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "semantic-link-labs"], check=True)
    from sempy_labs.tom import connect_semantic_model

MODEL_NAME = "BrookfieldEnercare"
DRIFT_TEXT = "DRIFTED VALUE -- manually edited outside governance, should be self-healed by nb_16."

with connect_semantic_model(dataset=MODEL_NAME, readonly=False) as tom:
    col = tom.model.Tables["dim_equipment"].Columns["EquipmentType"]
    print(f"BEFORE drift: {col.Description!r}")
    col.Description = DRIFT_TEXT

with connect_semantic_model(dataset=MODEL_NAME, readonly=True) as tom:
    col = tom.model.Tables["dim_equipment"].Columns["EquipmentType"]
    print(f"AFTER drift (should show drifted text): {col.Description!r}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
