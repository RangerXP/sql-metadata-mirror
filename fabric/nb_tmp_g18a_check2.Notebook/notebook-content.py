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

# READ-ONLY: verify nb_02's thin reader wrote exactly the pending SOURCE_TAG_DETECTED rows.
lines = []
try:
    df = spark.table("lh_metadata.source_tag_detections")
    lines.append(f"row count: {df.count()}")
    for r in df.collect():
        lines.append(f"  RequestId={r['RequestId']} TargetObjectId={r['TargetObjectId']} CurrentStatus={r['CurrentStatus']}")
except Exception as exc:
    lines.append(f"ERROR: {exc}")

text = "\n".join(lines)
print(text)
mssparkutils.fs.put("Files/debug/g18a_nb02_check.txt", text, True)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
