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

# G18-A safety check: confirm lh_metadata.kpi_metadata still holds the REAL
# certified KPIs, not nb_02's demo-prototype overwrite. Read-only, no writes.
result_lines = []
try:
    df = spark.sql("SELECT KPICode, KpiName, IsCertified FROM lh_metadata.kpi_metadata ORDER BY KPICode")
    rows = df.collect()
    result_lines.append(f"row_count={len(rows)}")
    for r in rows:
        result_lines.append(f"{r['KPICode']} | {r['KpiName']} | IsCertified={r['IsCertified']}")
except Exception as exc:
    result_lines.append(f"ERROR: {exc}")

output = "\n".join(result_lines)
print(output)
mssparkutils.fs.put("Files/debug/g18a_kpi_check.txt", output, True)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
