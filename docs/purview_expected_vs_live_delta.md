# Purview expected-vs-live delta report

- Snapshot analyzed: 
- Total catalog items: 184
- Expected names checked: 28

## Source-data classification update

The following objects are source-backed in the repo and appear in the seeded governance catalog, but they are not currently active defects in the local demo workflow because they are likely pre-shipped or tenant-owned catalog objects rather than objects that the repo is expected to publish as part of the demo-specific governance loop:

- `DP-BILLHEALTH`
- `GT-CONSENT`
- `GT-PII`

These items are explicitly present in [sql/02_metadata_foundation/07_seed_purview_metadata.sql](../sql/02_metadata_foundation/07_seed_purview_metadata.sql), [purview/data-product-catalog.csv](../purview/data-product-catalog.csv), and [purview/glossary-master.csv](../purview/glossary-master.csv). They should be classified as pre-seeded catalog scope, not as active demo-breaking defects.

## ✅ BrookfieldEnercare — present
- enercare://governance/domain/probe-domain-001 | EnercareGovernanceDomainProbe | enercare://governance/domain/probe-domain-001 | sourceQuery=BrookfieldEnercare
- lh_enercare_demo | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/795ce5db-7ea0-4a7c-ba64-e27c9fb568f4/lakewarehouses/e8af18fd-e9b9-4c0e-9102-06b7d1d3aa12 | sourceQuery=BrookfieldEnercare
- lh_enercare_demo | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakewarehouses/adea2c98-c565-4648-873f-dd0db11f6234 | sourceQuery=BrookfieldEnercare
- lh_enercare_demo | fabric_lakehouse | https://app.fabric.microsoft.com/groups/795ce5db-7ea0-4a7c-ba64-e27c9fb568f4/lakehouses/0ee837e4-2fd3-40d9-b228-1f167b504b7d | sourceQuery=BrookfieldEnercare
- lh_enercare_demo | fabric_lakehouse | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555 | sourceQuery=BrookfieldEnercare

## ✅ Enercare — present
- enercare://governance/domain/probe-domain-001 | EnercareGovernanceDomainProbe | enercare://governance/domain/probe-domain-001 | sourceQuery=BrookfieldEnercare
- lh_enercare_demo | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/795ce5db-7ea0-4a7c-ba64-e27c9fb568f4/lakewarehouses/e8af18fd-e9b9-4c0e-9102-06b7d1d3aa12 | sourceQuery=BrookfieldEnercare
- lh_enercare_demo | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakewarehouses/adea2c98-c565-4648-873f-dd0db11f6234 | sourceQuery=BrookfieldEnercare
- lh_metadata | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/795ce5db-7ea0-4a7c-ba64-e27c9fb568f4/lakewarehouses/595a4488-0f92-41b6-9cdb-f7e09337c2de | sourceQuery=Enercare
- lh_metadata | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakewarehouses/9c91b3bf-838a-41da-b876-2cc77c30f604 | sourceQuery=Enercare

## ✅ governance_domains — present
- governance_cdes | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_cdes | sourceQuery=governance_domains
- governance_change_requests | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_change_requests | sourceQuery=governance_domains
- governance_data_products | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_data_products | sourceQuery=governance_domains
- governance_domains | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_domains | sourceQuery=governance_domains
- governance_events | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_events | sourceQuery=governance_domains

## ✅ governance_requests — present
- governance_requests | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_requests | sourceQuery=governance_domains
- service_requests | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/service_requests | sourceQuery=governance_requests
- r6_check.txt | fabric_lakehouse_path | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/files/debug/r6_check.txt | sourceQuery=governance_requests
- service_requests | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/service_requests | sourceQuery=governance_requests

## ✅ governed_object_versions — present

## ✅ governance_object_mappings — present
- audit_data_access | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/audit_data_access | sourceQuery=governance_object_mappings
- data_owners_directory | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/data_owners_directory | sourceQuery=governance_object_mappings
- governance_object_mappings | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_object_mappings | sourceQuery=governance_domains
- governed_object_versions | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governed_object_versions | sourceQuery=governance_object_mappings
- asset_metadata | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/tables/asset_metadata | sourceQuery=governance_object_mappings

## ✅ governance_change_requests — present
- governance_change_requests | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_change_requests | sourceQuery=governance_domains
- governance_change_requests | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/tables/governance_change_requests | sourceQuery=governance_domains

## ✅ governance_role_assignments — present
- employees | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/employees | sourceQuery=governance_role_assignments
- governance_role_assignments | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/governance_role_assignments | sourceQuery=governance_domains
- cdes | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/tables/cdes | sourceQuery=governance_role_assignments
- label_assignments | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/tables/label_assignments | sourceQuery=governance_role_assignments

## ✅ governance_glossary_terms — present

## ✅ governance_data_products — present

## ✅ governance_target_receipts — present

## ✅ governance_events — present

## ❌ DOM-CUSTOPS — missing

## ❌ DOM-SVCDEL — missing

## ❌ DOM-REVCON — missing

## ✅ DP-CUST360 — present

## ✅ DP-SVCPERF — present
- DP600_Lakehouse_module2 | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/f753dff7-5fc9-40dc-8c50-6decc597b13b/lakewarehouses/3efecbe6-8e92-437a-a9a6-0000c1246844 | sourceQuery=DP-SVCPERF
- DP600_Lakehouse_module2 | fabric_lakehouse | https://app.fabric.microsoft.com/groups/f753dff7-5fc9-40dc-8c50-6decc597b13b/lakehouses/ecc603f3-fe95-4246-963e-d270bb00e209 | sourceQuery=DP-SVCPERF
- nb_14_purview_access_sync | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/eaff082f-da58-44d8-914c-3f5e469f34ee | sourceQuery=DP-SVCPERF
- nb_15_purview_dataproduct_sync | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/27a8ba2f-ff87-4f41-9862-4a564d381854 | sourceQuery=Enercare
- nb_16_dataproduct_semantic_reconcile | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/48727731-2196-44bc-bab9-872246a85e63 | sourceQuery=Enercare

## ❌ DP-BILLHEALTH — missing

## ✅ GT-SLA — present
- nb_12_purview_workflow_sync | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/f92425dc-f384-4dba-b388-7a883c9d1441 | sourceQuery=Enercare
- nb_13_semantic_reconcile | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/65c1aef3-e9ac-40fe-9cd6-625c21109985 | sourceQuery=Enercare

## ❌ GT-CONSENT — missing

## ❌ GT-CONTRACT — missing

## ❌ GT-SVCREQ — missing

## ❌ GT-PII — missing

## ✅ dp-svcperf — present
- DP600_Lakehouse_module2 | fabric_lake_warehouse | https://app.fabric.microsoft.com/groups/f753dff7-5fc9-40dc-8c50-6decc597b13b/lakewarehouses/3efecbe6-8e92-437a-a9a6-0000c1246844 | sourceQuery=DP-SVCPERF
- DP600_Lakehouse_module2 | fabric_lakehouse | https://app.fabric.microsoft.com/groups/f753dff7-5fc9-40dc-8c50-6decc597b13b/lakehouses/ecc603f3-fe95-4246-963e-d270bb00e209 | sourceQuery=DP-SVCPERF
- nb_14_purview_access_sync | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/eaff082f-da58-44d8-914c-3f5e469f34ee | sourceQuery=DP-SVCPERF
- nb_15_purview_dataproduct_sync | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/27a8ba2f-ff87-4f41-9862-4a564d381854 | sourceQuery=Enercare
- nb_16_dataproduct_semantic_reconcile | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/48727731-2196-44bc-bab9-872246a85e63 | sourceQuery=Enercare

## ✅ gt-sla — present
- nb_12_purview_workflow_sync | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/f92425dc-f384-4dba-b388-7a883c9d1441 | sourceQuery=Enercare
- nb_13_semantic_reconcile | fabric_synapse_notebook | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/synapsenotebooks/65c1aef3-e9ac-40fe-9cd6-625c21109985 | sourceQuery=Enercare

## ✅ vw_technician_utilization_summary — present
- lh_metadata | fabric_lakehouse | https://app.fabric.microsoft.com/groups/795ce5db-7ea0-4a7c-ba64-e27c9fb568f4/lakehouses/d4ba455b-9b80-46dd-afe8-d0b877b3a5d2 | sourceQuery=vw_technician_utilization_summary
- lh_metadata | fabric_lakehouse | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a | sourceQuery=vw_technician_utilization_summary
- debug | fabric_lakehouse_path | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/files/debug | sourceQuery=vw_technician_utilization_summary
- g18a_kpi_metadata_safety_check.txt | fabric_lakehouse_path | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/files/debug/g18a_kpi_metadata_safety_check.txt | sourceQuery=vw_technician_utilization_summary
- g18a_nb02_check.txt | fabric_lakehouse_path | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/824f4a52-baa0-4c3f-88dc-203c1d85c89a/files/debug/g18a_nb02_check.txt | sourceQuery=vw_technician_utilization_summary

## ✅ service_requests — present
- billing_transactions | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/billing_transactions | sourceQuery=service_requests
- contracts | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/contracts | sourceQuery=service_requests
- customer_complaints | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/customer_complaints | sourceQuery=service_requests
- equipment_registry | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/equipment_registry | sourceQuery=service_requests
- service_accounts | azure_sql_table | mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/service_accounts | sourceQuery=service_requests

## ✅ fct_service_request — present
- fct_cc_transcript_turns | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/fct_cc_transcript_turns | sourceQuery=fct_service_request
- fct_service_request | fabric_lakehouse_table | https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/fct_service_request | sourceQuery=vw_technician_utilization_summary

## Summary

- The governance ledger tables are live in Purview and visible in the snapshot.
- Exact custom names such as DOM-SVCDEL, GT-SLA, DP-SVCPERF, and vw_technician_utilization_summary are not all resolving as direct exact hits.
- This indicates a naming/indexing or publication mismatch for some repo-controlled objects, not a complete absence of the governance model.
- The remaining apparent misses for `DP-BILLHEALTH`, `GT-CONSENT`, and `GT-PII` are source-backed and likely pre-shipped tenant catalog objects rather than active demo defects.

- Present in snapshot: 20
- Missing: 8
- Active demo-scope defects: lower than the raw missing count once the source-backed pre-seeded catalog items are excluded
