# Capability Showcase: Fabric + SQL + Purview + Semantic Model

## For Microsoft SEs — What This Demo Actually Proves

This document maps each capability to where it's demonstrated in the demo. Use it to prepare for technical depth questions or to scope partial demos by capability.

---

## Microsoft Fabric Capabilities

### OneLake & Lakehouse

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Delta Lake tables | Star schema in lh_enercare_demo | nb_03_pbi_star_schema |
| Parquet file ingestion | Source data seeding | nb_01_setup_demo_environment |
| Lakehouse shortcut support | sqldemo mirror references | lh_enercare_demo.Lakehouse |
| Multi-lakehouse workspace | lh_enercare_demo + lh_metadata | Workspace structure |
| Schema evolution | Mirrored tables auto-schema | sqldemo.MirroredDatabase |

### Fabric Mirroring

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Azure SQL → OneLake CDC replication | sqldemo mirrored database | Portal configuration |
| Near-real-time change propagation | Delta tables updated automatically | sqldemo.MirroredDatabase |
| No-code mirror setup | Configured via Fabric portal | — |
| Private endpoint support | Managed VNet connection | sql-private-dns-vnet-link.bicep |

### Spark Notebooks

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| PySpark data transformation | Star schema build | nb_03_pbi_star_schema |
| Delta Lake write (merge, overwrite) | All ETL notebooks | nb_01, nb_03, nb_04a |
| SemPy integration | Semantic model read/write | nb_04, nb_05 |
| SemPy Labs semantic write-back | Model description updates | nb_04_sempy_writeback |
| JDBC connectivity | SQL source publication | nb_05a_publish_synthetic_data |
| REST API calls (Purview Atlas) | Governance publication | nb_07–nb_10 |

### DirectLake Semantic Model

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| DirectLake mode (no import) | BrookfieldEnercare model | BrookfieldEnercare.SemanticModel |
| DAX measures | KPI calculations | definition/tables/*.tmdl |
| Table/column descriptions | Governed metadata surface | Written by nb_04 |
| AI instruction annotations | Copilot grounding | Written by nb_05 |
| Verified Q&A | Data Agent answers | Written by nb_05 |

### Copilot & Data Agents

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Natural language queries | Tom's agent queries | Data Agent UI |
| Semantic model binding | Agent reads from SM | ee82668f...DataAgent |
| Verified Q&A grounding | Guardrailed answers | nb_05_push_qa_verified_answers |
| AI instruction compliance | Copilot behavior | Model annotations |

---

## Azure SQL Database Capabilities

### Core SQL

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Source system role | Authoritative operational data | sqldemo database |
| 7-table schema | Full Enercare operational model | 02_sub2_sql_source_schema.sql |
| Private endpoint access | Fabric → SQL connectivity | nb_05b_test_sql_connectivity |
| JDBC from Spark | Notebook writes to SQL | nb_05a_publish_synthetic_data |

### Purview Integration

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Purview scan source | AzureSqlDatabase-Sub2 registered | Purview portal |
| Lineage source node | SQL tables as lineage inputs | nb_09_purview_labels_lineage |
| Schema discovery | Scanned table/column inventory | Purview data map |

---

## Microsoft Purview Capabilities

### Unified Catalog (Phase 2.2)

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Governance Domains | 3 domains created | nb_07_publish_to_purview |
| Data Products | 3 products with ownership | nb_07_publish_to_purview |
| Asset → Product binding | Semantic model tables bound | nb_07_publish_to_purview |
| Dual ownership model | Domain + Product owners | purview/domain-charter.csv |

### Business Glossary

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Glossary terms | 35+ terms with definitions | nb_08_purview_glossary_cde |
| Term → Asset binding | Glossary linked to measures | nb_08_purview_glossary_cde |
| Related terms | Term hierarchy/relationships | purview/glossary-master.csv |
| Term ownership | Accountable owners assigned | purview/glossary-master.csv |

### Critical Data Elements (CDEs)

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| CDE catalog | 12 CDEs defined | nb_08_purview_glossary_cde |
| CDE → Column binding | CDEs linked to source columns | nb_08_purview_glossary_cde |
| Expected data types | CDE schema validation | purview/cde-catalog.csv |
| CDE ownership | Stewards assigned | purview/cde-catalog.csv |

### Sensitivity Labels & Classification

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Label taxonomy | 4 sensitivity levels | purview/label-policy.csv |
| Custom classifiers | Enercare-specific patterns | nb_09_purview_labels_lineage |
| Classification typedef | Atlas API registration | nb_09_purview_labels_lineage |
| Label → Column mapping | Sensitive columns tagged | Manual or scan-derived |

### Lineage

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Atlas lineage API | Process entity creation | nb_09_purview_labels_lineage |
| SQL → Fabric edges | 8 lineage edges published | nb_09_purview_labels_lineage |
| Visual lineage graph | Purview UI lineage view | Purview portal |
| GUID resolution | Asset lookup via search API | nb_09_purview_labels_lineage |

### Governance Validation

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Stewardship scoring | 18 objects validated | nb_10_purview_stewardship_ai |
| Controls validation | 4 control checks | nb_10_purview_stewardship_ai |
| AI readiness scoring | Semantic annotation coverage | nb_10_purview_stewardship_ai |
| Closeout manifest | Audit-ready report | nb_10_purview_stewardship_ai |

---

## Semantic Model Metadata Engineering

### SemPy (Read)

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| List tables | Inventory extraction | nb_02_metadata_pipeline_demo |
| List columns | Column inventory | nb_02_metadata_pipeline_demo |
| List measures | Measure inventory | nb_02_metadata_pipeline_demo |
| Read descriptions | Current metadata state | nb_04_sempy_writeback |

### SemPy Labs (Write)

| Capability | Where Demonstrated | Notebook/Artifact |
|------------|-------------------|-------------------|
| Write table descriptions | Business definitions | nb_04_sempy_writeback |
| Write column descriptions | CDE annotations | nb_04_sempy_writeback |
| Write measure descriptions | KPI definitions | nb_04_sempy_writeback |
| Set AI annotations | Copilot instructions | nb_05_push_qa_verified_answers |
| Set verified Q&A | Guardrailed answers | nb_05_push_qa_verified_answers |

---

## Integration Patterns

### Pattern 1: SQL → Fabric Mirroring

```
Azure SQL (sub2, authoritative)
    │ CDC replication
    ▼
Fabric Mirroring (sqldemo)
    │ Delta Lake
    ▼
Lakehouse (lh_enercare_demo)
    │ Star schema transform
    ▼
Semantic Model (BrookfieldEnercare)
```

**Demonstrated in**: nb_05a → Mirroring → nb_03

### Pattern 2: Metadata Engineering Pipeline

```
lh_metadata (working hub)
    │ SemPy inventory
    ▼
Curated metadata (KPIs, AI instructions)
    │ SemPy Labs writeback
    ▼
Semantic Model (descriptions, annotations)
    │ Purview scan
    ▼
Purview Catalog (governance surface)
```

**Demonstrated in**: nb_02 → nb_04a → nb_04 → nb_05 → Purview scan

### Pattern 3: Governance Publication Pipeline

```
CSV governance definitions (purview/*.csv)
    │ Ingest
    ▼
lh_metadata.metadata.* tables
    │ Reconciliation
    ▼
Purview REST APIs
    │ Publication
    ▼
Domains, Products, Glossary, CDEs, Lineage
```

**Demonstrated in**: nb_07a → nb_07b → nb_07 → nb_08 → nb_09 → nb_10

---

## Capability Matrix for Partial Demos

| If You Want to Show... | Run These Notebooks | Skip These |
|------------------------|--------------------|-----------| 
| Just the semantic model | nb_01, nb_05a, nb_03, nb_04, nb_05 | nb_07–nb_10 |
| Just the Purview governance | nb_07a, nb_07b, nb_07, nb_08, nb_09, nb_10 | nb_01–nb_05 (use existing data) |
| Just the Data Agent | All (need full pipeline) | — |
| Just the lineage | nb_09 only (if data exists) | nb_01–nb_08 |
| Just the mirroring | nb_05a + portal config | All others |

---

## Technical Depth Questions

### "How does SemPy Labs write to the model?"

> SemPy Labs provides Python bindings to the TOM (Tabular Object Model). When you call `table.set_description()`, it's making a direct TOM mutation that persists to the model definition. No REST API, no TMDL parsing — direct object model access.

### "Why not use Purview for everything?"

> Purview is the published governance authority — it's the system of record for definitions. But the runtime consumption surface is the semantic model. Copilot and Data Agents consume semantic model metadata, not Purview metadata directly. So we engineer metadata in Fabric, then publish to Purview for governance.

### "Can this scale to 1000 tables?"

> The metadata pipeline is batch-oriented. For 1000 tables, you'd parallelize the SemPy writeback and paginate the Purview publication. The pattern holds — just the batch sizes change.

### "What about real-time lineage?"

> This demo publishes batch lineage via Atlas API. For real-time data flow lineage (e.g., streaming events), you'd integrate with Fabric's built-in lineage capture or use Purview's automated lineage from scans.

---

## Demo Artifacts Summary

| Artifact Type | Count | Location |
|---------------|-------|----------|
| Notebooks | 13 | fabric/nb_*.Notebook/ |
| Lakehouses | 2 | fabric/lh_*.Lakehouse/ |
| Semantic Model | 1 | fabric/BrookfieldEnercare.SemanticModel/ |
| Power BI Report | 1 | fabric/BrookfieldEnercare.Report/ |
| Data Agent | 1 | fabric/ee82668f...DataAgent/ |
| SQL Scripts | 5 | sql/*.sql |
| Governance CSVs | 6 | purview/*.csv |
| Context JSONs | 5 | context/*.json |
| Documentation | 7+ | docs/*.md |
