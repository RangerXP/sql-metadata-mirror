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

# READ-ONLY safety check: has nb_02_metadata_pipeline_demo's unconditional overwrite already
# damaged the real, governance-managed lh_metadata.kpi_metadata table? This cell performs NO
# writes of any kind.
import json

report_lines = []
try:
    df = spark.table("lh_metadata.kpi_metadata")
    count = df.count()
    report_lines.append(f"kpi_metadata row count: {count}")
    rows = df.select("KpiName", "KPICode", "IsCertified").collect()
    for r in rows:
        report_lines.append(f"  KpiName={r['KpiName']!r} KPICode={r['KPICode']!r} IsCertified={r['IsCertified']!r}")
except Exception as exc:
    report_lines.append(f"ERROR reading kpi_metadata: {exc}")

report_text = "\n".join(report_lines)
print(report_text)
mssparkutils.fs.put("Files/debug/g18a_kpi_metadata_safety_check.txt", report_text, True)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
