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

# G17-R6 read-only check: report the current live description, writes result to a debug file
# since RunNotebook's job-status API does not expose stdout.
try:
    from sempy_labs.tom import connect_semantic_model
except ImportError:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "semantic-link-labs"], check=True)
    from sempy_labs.tom import connect_semantic_model

MODEL_NAME = "BrookfieldEnercare"

with connect_semantic_model(dataset=MODEL_NAME, readonly=True) as tom:
    col = tom.model.Tables["dim_equipment"].Columns["EquipmentType"]
    current_description = str(col.Description or "")

print(f"CURRENT dim_equipment.EquipmentType.Description = {current_description!r}")
mssparkutils.fs.put("Files/debug/r6_check.txt", current_description, True)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
