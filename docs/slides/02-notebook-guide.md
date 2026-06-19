# Notebook Reference Guide

## Overview

This demo runs through **13 notebooks** organized into five functional phases. Each notebook is designed to be re-runnable and serves a specific role in the data-to-governance pipeline.

---

## Phase 1: Data Foundation

### nb_01_setup_demo_environment

**What It Does**

Seeds synthetic Enercare operational data — customers, products, equipment, contracts, service requests, and billing transactions — into the Fabric lakehouse as source-style tables.

**Why It Matters**

This creates the realistic operational dataset that powers the Maria scenario. Every downstream analysis traces back to data seeded here — including the furnace that broke on Saturday.

**Technical Details**

- Seeds ~50 customers, ~60 service accounts, ~40 equipment records
- Generates 12 months of billing transactions and service requests
- Creates synthetic Canadian SINs using Luhn-valid generation
- Populates call-center interaction transcripts for agent scenarios
- Output: `lh_enercare_demo` source tables ready for SQL publication

---

### nb_05a_publish_synthetic_data_to_sql

**What It Does**

Publishes the synthetic operational dataset from Fabric into **Azure SQL Database** as the authoritative source system — the canonical "system of record" that enterprise data pipelines would connect to.

**Why It Matters**

This establishes the **sub2 → sub1 mirroring pattern**: SQL is the source of truth, Fabric mirrors it. This is the architecture pattern enterprise customers actually deploy.

**Technical Details**

- JDBC connection from Fabric to Azure SQL via managed private endpoint
- Publishes 7+ tables: customers, contracts, service_requests, billing_transactions, equipment_registry, customer_consents, customer_complaints
- Includes SIN columns for classifier testing
- Uses incremental MERGE logic for re-runs
- Output: `sqlserver-sk2wus3.database.windows.net/sqldemo` populated and ready for mirroring

---

## Phase 2: Mirroring & Star Schema

### Fabric Mirroring (sqldemo)

**What It Does**

Replicates Azure SQL tables into OneLake in near real-time using Fabric's built-in CDC-based mirroring.

**Why It Matters**

Demonstrates the **lakehouse pattern** for financial services: keep transactional systems in SQL, replicate to Fabric for analytics, avoid dual-write complexity.

**Technical Details**

- Mirrored database item: `sqldemo.MirroredDatabase`
- CDC-based change propagation
- Tables land as Delta Lake in OneLake
- Automatic schema evolution support
- No notebook required — configured via Fabric portal

---

### nb_03_pbi_star_schema

**What It Does**

Transforms the mirrored operational tables into an analytics-ready **star schema** with dimensions and facts — the shape that Power BI and the semantic model consume.

**Why It Matters**

This is where raw operational data becomes analytics-ready. The star schema enables the KPI calculations (FCR, AHT, Net Revenue, Churn) that Tom, Victoria, and Ci Zhu all rely on.

**Technical Details**

- Reads mirrored tables from OneLake
- Builds dimension tables: `dim_customer`, `dim_product`, `dim_equipment`, `dim_service_account`, `dim_date`
- Builds fact tables: `fct_billing`, `fct_service_request`, `fct_contract_month`, `fct_cc_interactions`
- Applies surrogate key generation and SCD Type 1 handling
- Output: `lh_enercare_demo` star schema tables ready for semantic model consumption

---

## Phase 3: Metadata Engineering

### nb_02_metadata_pipeline_demo

**What It Does**

Extracts and stages technical metadata from the semantic model and lakehouse tables into `lh_metadata` — the working metadata hub where governance assets are prepared.

**Why It Matters**

Creates the inventory of tables, columns, and measures that governance teams annotate with business definitions, ownership, and classification.

**Technical Details**

- Uses SemPy to read semantic model structure
- Catalogs table/column inventory with data types
- Stages measure definitions with DAX formulas
- Prepares join keys for glossary/CDE binding
- Output: `lh_metadata.asset_metadata`, `lh_metadata.measure_inventory`

---

### nb_04a_extend_metadata_schema

**What It Does**

Extends the metadata schema with governance-specific tables and seeds certified KPI definitions, AI instructions, and data ownership records.

**Why It Matters**

This is where business meaning is added to technical assets. The KPI definitions seeded here become the glossary terms published to Purview.

**Technical Details**

- Creates `kpi_metadata` with certified KPI definitions (FCR, AHT, Net Revenue, etc.)
- Creates `ai_metadata` with Copilot instruction annotations
- Creates `data_owners` linking assets to accountable owners
- Creates `lineage_edges` documenting SQL→Fabric→SM data flow
- Seeds sample verified Q&A pairs for Data Agent grounding
- Output: `lh_metadata` governance tables populated and ready for writeback

---

### nb_04_sempy_writeback

**What It Does**

Writes curated metadata from `lh_metadata` into the semantic model using **SemPy Labs** — pushing table descriptions, column descriptions, and measure documentation directly into the model's metadata layer.

**Why It Matters**

This is the critical bridge between governance curation and runtime consumption. After this notebook runs, Copilot, Data Agents, and Power BI all see the business definitions — not just the technical names.

**Technical Details**

- Uses `sempy.fabric.connect_semantic_model()` for TOM-backed model access
- Writes `Table.Description` for each dimension/fact
- Writes `Column.Description` with CDE annotations
- Writes `Measure.Description` with business definitions
- Applies AI instruction annotations for Copilot grounding
- Output: `BrookfieldEnercare` semantic model enriched with governed metadata

---

### nb_05_push_qa_verified_answers

**What It Does**

Pushes **verified Q&A pairs** into the semantic model's AI instruction annotations — pre-approved answers to common business questions that Copilot and Data Agents should use verbatim.

**Why It Matters**

When Tom asks "What's the SLA for a no-heat call?", the answer should come from the verified Q&A, not be hallucinated. This ensures AI responses are governed.

**Technical Details**

- Reads verified Q&A from `lh_metadata.verified_qa` or curated JSON
- Formats as PBI_AI_Instructions JSON payload
- Writes via SemPy Labs `set_annotation()` method
- Includes example questions and canonical answers
- Output: Semantic model carries verified Q&A for Data Agent consumption

---

## Phase 4: Governance Publication

### nb_07a_ingest_customer_files

**What It Does**

Ingests the **customer-supplied governance CSVs** (`purview/*.csv`) into `lh_metadata` — the domain charters, data product definitions, glossary terms, CDEs, role assignments, and label policies.

**Why It Matters**

Governance definitions come from business stakeholders, not data engineers. This notebook operationalizes the handoff from business governance (CSV files) to technical implementation.

**Technical Details**

- Reads 6 CSVs: domain-charter, data-product-catalog, glossary-master, cde-catalog, role-directory, label-policy
- Validates required schema fields
- Loads into `lh_metadata.metadata.*` tables
- Applies status filtering (Published/Certified only)
- Output: Governance definitions staged for Purview publication

---

### nb_07b_merge_customer_metadata

**What It Does**

Reconciles customer-supplied governance definitions with scan-derived inventory — ensuring every glossary term binds to an actual asset, and every CDE maps to a real column.

**Why It Matters**

Catches mismatches between business governance intent and technical reality. If a glossary term references a table that doesn't exist, this notebook surfaces it.

**Technical Details**

- Left-joins glossary terms to asset inventory
- Left-joins CDEs to column inventory
- Flags unbound terms as `WARN`
- Creates reconciliation report
- Output: `lh_metadata.governance_reconciliation` with binding status

---

### nb_07_publish_to_purview

**What It Does**

Publishes governance definitions from `lh_metadata` to **Microsoft Purview** — creating domains, data products, and attaching assets to the governed catalog.

**Why It Matters**

This is where governance goes live. After this notebook runs, Ci Zhu can open Purview and show the auditor the published domains, data products, and asset bindings.

**Technical Details**

- Uses Purview REST APIs for domain/product creation
- Creates governance domains with dual ownership (per Purview Phase 2.2)
- Creates data products with Type, audience, and access policies
- Attaches scanned assets (SQL tables, Fabric tables, semantic model) to products
- Output: Purview Unified Catalog populated with governance structure

---

### nb_08_purview_glossary_cde

**What It Does**

Publishes **glossary terms** and **Critical Data Elements (CDEs)** to Purview — the certified business definitions that all consumers must use.

**Why It Matters**

This is where "Net Revenue" gets its official definition. After this notebook runs, there's only one definition of Net Revenue — and it's the one Tom, Victoria, and the auditor all see.

**Technical Details**

- Creates glossary terms with owners, definitions, and related terms
- Binds terms to semantic model measures (`GT-NETREV → _Measures/Net Revenue`)
- Creates CDE records with expected data types
- Links CDEs to source columns (`CDE-CONTRACTAMT → dbo.contracts.monthly_amount`)
- Output: Purview glossary and CDE catalog populated

---

### nb_09_purview_labels_lineage

**What It Does**

Publishes **sensitivity labels** and **lineage edges** to Purview — the classification schema and the data flow graph.

**Why It Matters**

This enables the "click any number, trace to source" experience. When Victoria drills into Net Revenue, she can click View Lineage and see the chain from dashboard to source SQL.

**Technical Details**

- Creates classification typedefs for custom Enercare classifiers
- Publishes 8 lineage process entities (SQL table → Fabric semantic model)
- Uses Atlas API for lineage edge creation
- Resolves asset GUIDs via Purview search (with singular/plural fallback)
- Output: Purview lineage graph populated, sensitivity classifications registered

---

### nb_10_purview_stewardship_ai

**What It Does**

Validates **stewardship**, **controls**, and **AI readiness** across all governance objects — producing a scorecard that confirms the demo is complete and audit-ready.

**Why It Matters**

This is the final validation gate. If this notebook produces `0 ACTION_REQUIRED`, the demo is ready to ship.

**Technical Details**

- Phase 08: Scores 18 governance objects (domains, products, CDEs) on stewardship status
- Phase 09: Validates controls (sensitive CDEs identified, label policies configured, DLP mode selected)
- Phase 10: Validates AI readiness (semantic annotations available, glossary terms bound, verified Q&A present)
- Produces closeout manifest with pass/fail status
- Output: `lh_metadata.purview_phase_08_10_closeout` with 0 ACTION_REQUIRED = demo ready

---

## Execution Order

For a full demo rebuild:

```
1. nb_01_setup_demo_environment     → Seed synthetic data
2. nb_05a_publish_synthetic_data_to_sql → Publish to SQL
3. [Portal] Fabric Mirroring sync   → Replicate to OneLake
4. nb_03_pbi_star_schema            → Build star schema
5. nb_02_metadata_pipeline_demo     → Extract metadata inventory
6. nb_04a_extend_metadata_schema    → Seed KPI/AI metadata
7. nb_04_sempy_writeback            → Write to semantic model
8. nb_05_push_qa_verified_answers   → Push verified Q&A
9. nb_07a_ingest_customer_files     → Ingest governance CSVs
10. nb_07b_merge_customer_metadata  → Reconcile bindings
11. nb_07_publish_to_purview        → Publish domains/products
12. nb_08_purview_glossary_cde      → Publish glossary/CDEs
13. nb_09_purview_labels_lineage    → Publish labels/lineage
14. nb_10_purview_stewardship_ai    → Validate completion
```

---

## Quick Reference

| Notebook | Phase | Primary Output |
|----------|-------|----------------|
| nb_01 | Foundation | Synthetic data in lakehouse |
| nb_05a | Foundation | SQL source populated |
| nb_03 | Transform | Star schema built |
| nb_02 | Metadata | Asset inventory extracted |
| nb_04a | Metadata | KPI/AI definitions seeded |
| nb_04 | Metadata | Semantic model enriched |
| nb_05 | Metadata | Verified Q&A published |
| nb_07a | Governance | CSVs ingested |
| nb_07b | Governance | Bindings reconciled |
| nb_07 | Governance | Domains/products published |
| nb_08 | Governance | Glossary/CDEs published |
| nb_09 | Governance | Labels/lineage published |
| nb_10 | Validation | Audit-ready scorecard |
