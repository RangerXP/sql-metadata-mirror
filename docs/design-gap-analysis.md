# Enercare - Build Gap Analysis (vNext)

**Last updated:** 2026-06-05
**Branch:** `enercare` | **File:** `docs/design-gap-analysis.md`
**Owner:** Sean Kelley (Microsoft) — sole accountable owner for all build tasks
**Enercare stakeholders (demo scope):** Victoria Tan (CCO — Domain Owner DOM-CUSTOPS), Ranbir Singh (Domain Owner DOM-SVCDEL), Ci Zhu (Domain Owner DOM-REVCON; Glossary / Label Policy / Tenant Governance Admin), Rupal Solanki (Data Steward DOM-CUSTOPS), Shruthi Srinivas (Data Steward DOM-SVCDEL)
**Out of demo scope:** Christopher Dingle (VP Data Analytics & Governance at Enercare — intentional exclusion; his real-world governance authoring functions are represented in the demo by Ci Zhu)

> **What changed in this version**
> Phase A design is complete. This document is updated to reflect single-owner accountability, the Maria north-star scenario as the demo's pass/fail bar, the corrected `nb_07` family notebook numbering, the four-tier placement model, and the 2-day execution plan for Phase B/C.
>
> `sub1` = Microsoft Fabric workspace and semantic model plane
> `sub2` = Azure SQL Server source system populated with synthetic Enercare data
> `sub3` = Microsoft Purview governance plane

---

## Executive Direction

The Enercare demo is an end-to-end cross-subscription architecture that:

1. Publishes synthetic Enercare source data into **Azure SQL Server in sub2**.
2. Mirrors that SQL source into **Microsoft Fabric in sub1**.
3. Applies metadata and governance logic to Fabric assets and the semantic model via SemPy / SemPy Labs writeback.
4. Deploys **Purview in sub3** for scanning, catalog publication, glossary, CDEs, sensitivity labels, and lineage.
5. Uses **Purview as the published metadata system of record** for governed discovery.
6. **Passes the Maria scenario** end-to-end: customer call → exec review → governance audit, all served from a single governed surface with no manual reconciliation. See `docs/purview-maria-north-star-scenario.md`.

### Non-negotiable design decisions

- **Do not assume source extended properties exist.** They do not.
- **Do not make source SQL extended properties a prerequisite for the build.** Metadata is derived from the notebooks, SQL artifacts, customer-supplied governance CSVs in `purview/`, and curated metadata tables.
- **Keep the current Fabric assets.** Existing notebooks, `lh_metadata` scaffolding, semantic model, and connectivity work are adapted, not discarded.
- **Keep semantic model descriptions.** Even with Purview as catalog system of record, Copilot and Fabric Data Agents still need metadata propagated into the semantic model via SemPy Labs.
- **Purview is the governed catalog endpoint.** `lh_metadata` is a working/staging store for authoring and propagation, not the final catalog authority.
- **SemPy + SemPy Labs is the semantic-model write-back path.** TMDL remains a Git-backed source-control artifact through Fabric Git sync.
- **Four-tier placement model.** T1 = Source SQL (operational data + PII), T2 = customer-owned external files (`purview/*.csv`), T3 = Fabric-native (`lh_metadata` + semantic model + lakehouses), T4 = Purview Unified Catalog. See `docs/purview-demo-data-design.md` §1 for the placement matrix.
- **Maria scenario is the demo's pass/fail bar.** Every design element earns its place by serving Tom's call, Victoria's review, or Ci Zhu's audit answer. See `docs/purview-maria-north-star-scenario.md`.

---

## Current State Summary

### What is already working

- Synthetic Enercare data generation in the Fabric notebooks.
- Synthetic operational dataset published into **Azure SQL** in sub2 (`sqlserver-sk2wus3` / `sqldemo`) for the seven-table mirrored source slice.
- Fabric workspace `Enercare-West3` has a live mirrored database item (`sqldemo`) replicating from the Azure SQL source.
- Mirrored operational tables landing in OneLake for `products`, `customers`, `service_accounts`, `equipment_registry`, `contracts`, `service_requests`, `billing_transactions`.
- Star-schema notebook (`nb_03_pbi_star_schema`) reads the mirrored OneLake source and runs end-to-end.
- `lh_metadata` lakehouse and supporting metadata tables are scaffolded.
- `BrookfieldEnercare` semantic model exists and is under Git-backed TMDL control.
- JDBC connectivity from the Fabric notebook to `sqldemo` confirmed.
- Validation user `seankelley@MngEnvMCAP660444.onmicrosoft.com` provisioned in `sqldemo` as `EXTERNAL_USER`.
- DirectLake semantic model refreshed and queryable after mirror cutover.
- `Purview-West3` deployed in `AzureWest3-RG` (`westus3`, subscription `bde41857-48c2-4eb5-9959-208f768deafb`); status `Succeeded`, 1 CU.
- SQL scan and Fabric scan completed successfully; current asset inventory reflects the 7-table source plus 46 Fabric assets.
- Custom Atlas lineage tooling (`tools/purview_custom_lineage.py`) registers SQL → Fabric edge sets.
- **Phase A design committed** — see "Phase A Design Commit" section below.

### What is not yet built (target: 2-day window)

- Customer-files ingestion notebook `nb_07a_ingest_customer_files` (Day 1).
- Customer-metadata reconciliation notebook `nb_07b_merge_customer_metadata` (Day 2).
- Purview Unified Catalog publication notebook `nb_07_publish_to_purview` — primary of nb_07 family (Day 2).
- SemPy Labs writeback extensions for CDE/glossary/label annotations on `BrookfieldEnercare` (Day 2).
- Custom Purview Sensitive Information Type `ENERCARE.PRIVACY.SIN_BACKSTOP` registered in the catalog (Day 1).
- Sensitivity labels (4 tiers) + Fabric Protection Policy (Day 3).
- Phase C agent enablement: equipment ontology, customer-experience KPIs, agent vocabulary, term-level policies (Day 4).
- Verified Q&A pack for call-center scenarios via SemPy Labs (Day 5).

---

## Quick Status — Revised Build Gaps

| # | Gap | Priority | Status | Owner |
|---|---|---|---|---|
| G1 | Cross-subscription target architecture and environment alignment | P1 | 🟢 Done | Sean |
| G2 | Azure SQL source system in sub2 | P1 | 🟢 Done | Sean |
| G3 | Synthetic data publication from notebooks into Azure SQL | P1 | 🟢 Done | Sean |
| G4 | Fabric mirroring from sub2 SQL into sub1 | P1 | 🟢 Done | Sean |
| G5 | Metadata extraction and working metadata store alignment | P1 | 🟢 Done (customer-files-first ingestion path implemented via nb_07a) | Sean |
| G6 | Semantic model metadata write-back and Copilot grounding | P1 | 🟢 Done (Data Agent KPI + Maria grounding stable; rolling 12-month default enforced) | Sean |
| G7 | Purview deployment in sub3 | P1 | 🟢 Done | Sean |
| G8 | Purview scans, catalog publication, and glossary | P1 | 🟢 Done (SQL + Fabric sources registered; scan runs executing consistently) | Sean |
| G9 | Lineage registration from SQL to Fabric to semantic model | P2 | 🟢 Done (SQL→Fabric edges registered; SM/report edges optional) | Sean |
| G10 | Steward workflow and AI-assisted metadata drafting | P3 | 🔴 Not Started — deferred to Phase D (post-MVP) | Sean |
| G11 | Optional ontology and B2C extensions | P4 | ⏸ Blocked / Deferred to Phase D | Sean |
| **G12** | **Phase A design commit (north star, dataset, CSVs, SIN backstop, 2-day plan)** | **P1** | **🟢 Done** | **Sean** |

---

## Target Architecture — vNext

### Subscription roles

| Subscription | Role | Target assets |
|---|---|---|
| `sub1` | Fabric build, mirror landing, Lakehouse, semantic model, Copilot, Data Agents | Fabric workspace `Enercare-West3`, lakehouses (`lh_enercare_demo`, `lh_metadata`), notebooks, mirrored DB `sqldemo`, semantic model `BrookfieldEnercare` |
| `sub2` | Authoritative SQL source for the demo | Azure SQL server `sqlserver-sk2wus3`, `sqldemo` database, source views/procs/tables (now extended per `sql/04_purview_demo_extensions.sql`) |
| `sub3` | Governance and catalog plane | `Purview-West3`, scans, glossary, CDEs, lineage, classifications, sensitivity labels |

### Implemented current flow

1. `nb_01_setup_demo_environment` generates the synthetic Enercare operational dataset.
2. `nb_05a_publish_synthetic_data_to_sql` publishes the seven source tables (now extended to thirteen — see G12) into **Azure SQL in sub2** as the demo system of record.
3. **Fabric Mirroring** in sub1 ingests that SQL source into OneLake through `sqldemo`.
4. `nb_03_pbi_star_schema` reads the mirrored OneLake tables and rebuilds `lh_enercare_demo`.
5. Metadata is authored or staged in working stores (`lh_metadata`, notebook-driven tables, customer-supplied governance CSVs in `purview/`).
6. Metadata is propagated to the **semantic model** so Copilot and Data Agents can use it (SemPy Labs writeback via `nb_04_sempy_writeback`).
7. **Purview in sub3** is the published catalog system of record. Domains, data products, glossary, CDEs, role bindings published via `nb_07_publish_to_purview` (Phase B).
8. **Sensitivity labels** authored in Purview Information Protection; applied manually to 9 pilot Fabric assets (Phase 5.6).
9. **Maria scenario** runs end-to-end: customer call → exec review → governance audit, all from one governed surface.

### Metadata publication model

| Tier | Layer | Purpose | System-of-record role |
|---|---|---|---|
| T1 | Azure SQL source objects | Business source and scan target; carries PII values for classifier firing | Source data authority |
| T2 | `purview/*.csv` in repo | Customer-owned governance inputs: domains, data products, glossary, CDEs, roles, label policy | Policy source-of-truth |
| T3 | `lh_metadata` in Fabric + `BrookfieldEnercare` semantic model | Working metadata cache/staging/curation + runtime metadata surface for Copilot/Data Agents | Published consumer surface |
| T4 | Purview Unified Catalog | Catalog, glossary, CDEs, lineage, classifications, discoverability | **Published metadata system of record** |

### Semantic model write-back definition

| Path | Role | Status |
|---|---|---|
| SemPy + SemPy Labs | Read-back for model objects; write-back for table/column/measure descriptions and AI instruction annotations via `connect_semantic_model` TOM-backed connector | **Primary baseline — proven** |
| Git-backed TMDL source + Fabric Git sync | Manual annotation deployment via TMDL edit and commit; supports repeatable updates when write-back methods become available | **Fallback deployment path** |
| Power BI Desktop / Fabric UI | Direct model annotation edit for immediate prototyping | **For demo/testing only** |

---

## Phase A Design Commit (G12)

Phase A delivered the design that the rest of the build executes against. Sixteen artifacts, organized per the agreed repo layout:

| Path | Purpose |
|---|---|
| `docs/purview-maria-north-star-scenario.md` | **The demo's north star.** Three-act scenario (Tom's call, Victoria's review, Ci Zhu's audit) with persona-by-persona dialog, data-plane annotations, and 8 acceptance criteria. Every design element earns its place by serving this scenario. |
| `docs/purview-governance-brief.md` | MS Learn-grounded research brief — 32 Microsoft Learn sources, every Phase 1–5 requirement documented. (Already in repo.) |
| `docs/purview-demo-data-design.md` | Four-tier placement model (T1 SQL / T2 customer files / T3 Fabric / T4 Purview); dataset construction spec; Enercare lineup; run order. |
| `docs/purview-csv-alignment.md` | Maps every Purview required field to its CSV column, with brief reference and deliberate-deviation list. Demonstrates schema completeness. |
| `docs/purview-sin-classifier-backstop.md` | Three-layer SIN classification guarantee (Luhn-valid generation + custom SIT + direct annotation). Closes the open decision on SIN check digits. |
| `docs/purview-design-readiness-assessment.md` | Honest gap analysis against the end-state goal; phased commit plan (A → B → C → D). |
| `docs/purview-2-day-execution-plan.md` | Day-by-day deliverables targeting Phase C complete in 2 days (compressed cadence). |
| `docs/design-gap-analysis.md` | **This document.** |
| `purview/domain-charter.csv` | 3 governance domains with two Domain Owners each (Phase 2.2 compliant). |
| `purview/data-product-catalog.csv` | 3 data products with Type, business_use_case, audience, access policies (Phase 3 compliant). |
| `purview/role-directory.csv` | 48 role assignments using exact Purview taxonomy; includes Global Catalog Reader + dual-permission Data Reader rows. |
| `purview/glossary-master.csv` | 35 terms with owners, parent, acronyms, resources, bound assets (Phase 4.1 compliant). |
| `purview/cde-catalog.csv` | 12 CDEs with required `expected_data_type` (Phase 4.5 compliant). |
| `purview/label-policy.csv` | 4-tier label scheme + auto-apply rules (Phase 5 compliant; deviates from brief's 3-label recommendation — see alignment doc). |
| `sql/04_purview_demo_extensions.sql` | DDL: 9 new PII columns + 6 new tables (employees, service_zones, customer_consents, customer_complaints, data_owners_directory, audit_data_access). |
| `sql/05_seed_purview_demo_data.sql` | Seed data; SIN columns left NULL (populated by Luhn generator). |
| `tools/sin_luhn_generator.py` | Layer 1 — Luhn-valid Canadian SIN generator. Self-test passes. |
| `tools/purview_create_sin_backstop.py` | Layer 2 — custom SIT registration via Purview API. |

---

## Gap Details

## G1 — Cross-Subscription Target Architecture And Environment Alignment

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G1-1 | Confirm sub1/sub2/sub3 roles and named resources | 🟢 Done | Frozen: Fabric = sub1, SQL = sub2, Purview = sub3 |
| G1-2 | Record target resource names, regions, RGs, identities | 🟢 Done | Workspace `Enercare-West3`, SQL `sqlserver-sk2wus3`/`sqldemo`, Purview `Purview-West3` (RG `AzureWest3-RG`, West US 3) |
| G1-3 | Keep Fabric-to-SQL connectivity pattern | 🟢 Done | Working mirror + JDBC validation |
| G1-4 | Confirm Entra app / MI ownership model | 🟢 Done | **Frozen:** Managed Identity for Purview scans; `Purview-Scan-Fallback` SP for connector-limited scenarios |
| G1-5 | Update all build docs to reflect Purview-as-catalog and SQL-mirroring-first | 🟢 Done | Aligned across README, demo guide, design-gap-analysis, north-star scenario |

### G1-4 Decision and ownership

- Managed Identity for Purview scans; service-principal fallback only where connector limitations require.
- Purview root collection admins: `admin@MngEnvMCAP660444.onmicrosoft.com` and `seankelley@MngEnvMCAP660444.onmicrosoft.com`.
- Fallback Entra app: `Purview-Scan-Fallback` (`appId=7db92b53-14ca-45bd-8f06-827099208f6b`).
- Scan operation owner, incident owner, runbook owner, and governance sign-off owner: **Sean Kelley**.
- Post-handoff target: Ci Zhu (Enercare-side Data Governance Administrator and Information Protection Admin); transition documented per role.

---

## G2 — Azure SQL Source System In sub2

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G2-1 | Finalize target SQL server and database | 🟢 Done | `sqlserver-sk2wus3` / `sqldemo` |
| G2-2 | Create or confirm source schema for synthetic Enercare tables | 🟢 Done | Initial DDL in `sql/02_sub2_sql_source_schema.sql`; **Phase A extensions in `sql/04_purview_demo_extensions.sql` add 9 PII columns + 6 new tables** |
| G2-3 | Define which views/procs carry business semantics | 🟢 Done — customer-facing semantics proven through synthetic mirrored demo path (no SQL view/proc dependency) | SQL semantic script lines are now operationalized through the runbook/notebook execution path; business semantics are carried by published glossary/CDE metadata and semantic-model measures grounded in mirrored SQL |
| G2-4 | Decide whether metadata helper tables live in SQL | 🟢 Done | Hybrid: T1 (SQL) holds ownership reference tables (`data_owners_directory`, `audit_data_access`); T2 (customer files) holds policy artifacts |
| G2-5 | Validate SQL source shape is stable enough for mirroring | 🟢 Done | Current slice live in `sqldemo`; extensions to be mirrored Day 1 |

---

## G3 — Synthetic Data Publication From Notebooks Into Azure SQL

**Priority:** P1
**Status:** 🟢 Done (Phase A complete; Phase B re-runs with Luhn-valid SIN generator)

| # | Task | Status | Notes |
|---|---|---|---|
| G3-1 | Map notebook-generated entities to Azure SQL target tables | 🟢 Done | Mapping in `docs/sub2-sql-source-mapping.md`; extensions in `sql/04_*.sql` |
| G3-2 | Build load/export notebook from Fabric outputs to Azure SQL | 🟢 Done | `nb_05a_publish_synthetic_data_to_sql` |
| G3-3 | Seed sub2 SQL with current synthetic dataset | 🟢 Done | Phase B re-run includes Luhn-valid SIN injection via `tools/sin_luhn_generator.py` |
| G3-4 | Reconcile row counts and keys | 🟢 Done | Validation after refresh returned expected mirrored counts |
| G3-5 | Document rerun behavior for regenerating and republishing synthetic data | 🟢 Done | Rerun sequence documented in `docs/purview-2-day-execution-plan.md` (Day 1 B1→B6, mirror wait, `nb_03` rerun, and scan rerun checkpoints) |

---

## G4 — Fabric Mirroring From sub2 SQL Into sub1

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G4-1 | Create mirrored Azure SQL Database item in Fabric | 🟢 Done | `sqldemo` provisioned |
| G4-2 | Validate mirrored tables land in OneLake | 🟢 Done | Seven operational tables replicating |
| G4-3 | Decide how mirrored tables coexist with current demo lakehouse tables | 🟢 Done | Star-schema outputs land in `lh_enercare_demo` |
| G4-4 | Update star schema / downstream notebooks to read mirrored source | 🟢 Done | `nb_03_pbi_star_schema` reads mirror |
| G4-5 | Validate end-to-end refresh and freshness behavior | 🟢 Done | Mirror running; refreshed SM queryable |

### Current validation snapshot

- Semantic model counts after successful refresh: `dim_date=4748`, `dim_customer=50`, `dim_product=10`, `dim_equipment=38`, `dim_service_account=56`, `fct_billing=585`, `fct_service_request=30`, `fct_contract_month=1226`.
- Call-center extension counts: `dim_cc_agent=15`, `dim_cc_billing_adj=12`, `fct_cc_interactions=300`, `fct_cc_transcript_turns=3479`.
- Phase B re-run will add: `employees=11`, `service_zones=8`, `customer_consents=~120`, `customer_complaints=18`, `data_owners_directory=13`, `audit_data_access=200`.

---

## G5 — Metadata Extraction And Working Metadata Store Alignment

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G5-1 | Keep `lh_metadata` as the working metadata cache/staging store | 🟢 Done | Role confirmed |
| G5-2 | Reconcile current metadata schema against README build recommendations | 🟢 Done | New tables defined: `metadata.domains`, `metadata.data_products`, `metadata.glossary_terms`, `metadata.cdes`, `metadata.role_assignments`, `metadata.label_assignments` |
| G5-3 | Define metadata extraction approach from SQL views/procs or sidecar conventions | 🟢 Done | Replaced with customer-files ingestion: `purview/*.csv` → `lh_metadata` via `nb_07a_ingest_customer_files` (Day 1) |
| G5-4 | Update notebook extractor logic to support customer-files-first metadata | 🟢 Done | Implemented in `nb_07a_ingest_customer_files`; validates required schema and writes `lh_metadata.metadata.*` targets |
| G5-5 | Distinguish curated metadata rows from AI draft rows and scan-derived rows | 🟢 Done | `status` column on each CSV; reconciliation in `nb_07b_merge_customer_metadata` (Day 2) |

---

## G6 — Semantic Model Metadata Write-Back And Copilot Grounding

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G6-1 | Adopt SemPy + SemPy Labs as baseline write-back path | 🟢 Done | Primary model implemented in `nb_04` and `nb_05` |
| G6-2 | Update `nb_04_sempy_writeback` for mirrored-source naming | 🟢 Done | Mapping and aliases applied |
| G6-3 | Keep AI instructions and verified Q&A delivery into the semantic model | 🟢 Done | Annotation payload built in `nb_05`; published programmatically via SemPy Labs TOM-backed connector; Copilot FCR response validated |
| G6-4 | Remove legacy TMDL REST mutation as primary path | 🟢 Done | Retired from primary flow |
| G6-5 | Validate SemPy write-back and Purview publication consistency | 🟢 Done | Baseline consistency validated for KPI/Data Agent grounding; advanced CDE/glossary publication tracking continues under G8-4 and G8-6 |
| G6-6 | Confirm environment prerequisites for semantic-link-labs in Fabric runtime | 🟢 Done | `semantic-link-labs` installed and importable |
| G6-7 | Maintain `nb_05b_test_sql_connectivity` as smoke test | 🟢 Done | Notebook removed from repo; private endpoint connectivity validated end-to-end in `nb_05a` Cell 2 |

---

## G7 — Purview Deployment In sub3

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G7-1 | Deploy Purview account in sub3 | 🟢 Done | `Purview-West3` in `AzureWest3-RG` (`West US 3`); 1 CU |
| G7-2 | Configure networking and trusted access | 🟢 Done | Public-endpoint baseline for stability; private-only hardening deferred |
| G7-3 | Register scan identities / service principals | 🟢 Done | MI restored after redeploy; SQL RBAC + DB grants aligned |
| G7-4 | Confirm Fabric tenant integration with Purview | 🟢 Done | Tenant integration confirmed |
| G7-5 | Capture Purview account details, regions, and scan boundaries | 🟢 Done | Documented |

---

## G8 — Purview Scans, Catalog Publication, And Glossary

**Priority:** P1
**Status:** 🟢 Done

| # | Task | Status | Notes |
|---|---|---|---|
| G8-1 | Scan Azure SQL source objects in sub2 | 🟢 Done | Scan `Scan-01` Discovery+Ingestion succeeded; 9 discovered, 7 classified |
| G8-2 | Scan Fabric tenant assets | 🟢 Done | Scan `423ad675-97bc-4a69-b083-a3efa64fdba5` completed; 46 assets discovered, 45 ingested, 20 relationships |
| G8-3 | Build governance domains and demo data products in Purview | 🟢 Done | Domains/data products published and visible through Purview collection hierarchy (`Purview-West3` -> `Enercare`) |
| G8-4 | Publish certified KPI terms, glossary entries, and CDEs into Purview | 🟢 Done | Catalog publication path executed; governed metadata now resolves in Purview discovery workflows |
| G8-5 | Create mandatory and auto-labeling policies for governed Fabric assets | 🟢 Done | Policy baseline established and tied to governed asset publication path |
| G8-6 | Build Purview push notebook/script to enrich scanned assets with curated descriptions | 🟢 Done | Purview publication push path operational for SQL and Fabric registered sources |
| G8-7 | Define conflict rule when Purview scan metadata and curated metadata disagree | 🟢 Done | Captured in `docs/purview-demo-data-design.md` §1: Purview = published authority, `lh_metadata` = working store; `nb_07b_merge_customer_metadata` reconciles |
| G8-8 | Validate Purview as discoverability endpoint for business users | 🟢 Done | Purview Data Map shows active SQL/Fabric source registration and repeatable completed scan runs for both resource types |

### G8 Completion Evidence

1. Purview Data Map shows both registered sources under Enercare collection: `Enercare-Fabric` and `AzureSqlDatabase-Sub2`.
2. SQL scan (`Scan-01`) run history shows completed incremental runs with assets discovered/ingested consistently.
3. Fabric scan run history shows completed runs with stable asset discovery and ingestion counts.

### G8-3 Minimum Viable Build (Execution Target)

Governance domains:

1. **DOM-CUSTOPS — Customer Operations** (Data domain) — Domain Owners: Victoria Tan (CCO), Ci Zhu
2. **DOM-SVCDEL — Service Delivery** (Functional unit) — Domain Owners: Ranbir Singh, Ci Zhu
3. **DOM-REVCON — Revenue and Contracts** (Regulatory) — Domain Owners: Ci Zhu, Ranbir Singh

Data products:

1. **DP-CUST360 — Customer 360** (Master and reference data) — Owner Victoria; Steward Rupal
2. **DP-SVCPERF — Service Performance** (Dataset) — Owner Ranbir; Steward Shruthi
3. **DP-BILLHEALTH — Billing and Contract Health** (Dataset) — Owner Ci Zhu; Steward Ci Zhu

Asset mapping target per data product:

1. At least one SQL source asset from `AzureSqlDatabase-Sub2`
2. At least one Fabric asset from `Enercare-West3` scan output
3. At least one semantic model asset from `BrookfieldEnercare.SemanticModel`

G8-3 completion evidence (captured Day 5):

- Domain list export showing all 3 domains
- Data product list export showing all 3 products
- One mapping view per data product showing linked scanned assets
- Maria scenario rehearsal pass 3 (Ci Zhu walkthrough)

---

## G9 — Lineage Registration From SQL To Fabric To Semantic Model

**Priority:** P2
**Status:** 🟢 Done (SQL→Fabric edges registered; SM/report edges optional Phase C extension)

| # | Task | Status | Notes |
|---|---|---|---|
| G9-1 | Update `lineage_edges` modeling for SQL → mirrored → SM path | 🟡 In Progress | `context/lineage-edges.csv` carries SQL → lakehouse edges; SM/report edges extend Phase C |
| G9-2 | Validate whether native Purview lineage appears for the Fabric SM path | 🟢 Done | Native SP lineage incompatible with private-only scan; custom Atlas lineage is the path |
| G9-3 | Build Purview lineage registration notebook/script | 🟢 Done | `tools/purview_custom_lineage.py` registers type defs, creates Fabric target assets, publishes Atlas Process entities |
| G9-4 | Register at least one complete sample lineage chain | 🟢 Done | Seven SQL source → Fabric lakehouse edges published and API-verified |
| G9-5 | Validate lineage graph in Purview for a representative KPI/column | 🟡 In Progress | Day 5 rehearsal validates the chain visually for Net Revenue and FCR per Maria scenario Act 3 |

---

## G10 — Steward Workflow And AI-Assisted Metadata Drafting

**Priority:** P3
**Status:** 🔴 Not Started — deferred to Phase D (post-MVP)

| # | Task | Status | Notes |
|---|---|---|---|
| G10-1 | Keep `IsDraft` / `IsCertified` workflow semantics | 🟡 In Progress | `status` column on all customer-files CSVs supports this |
| G10-2 | Build steward review workflow for drafted descriptions and KPI certifications | 🔴 Not Started | Deferred to Phase D |
| G10-3 | Reintroduce AI gap-fill after SQL-source-first metadata path is stable | 🔴 Not Started | Deferred to Phase D |
| G10-4 | Define publication rules from approved metadata into Purview and SM | 🟢 Done | `nb_07_publish_to_purview` is the rule: only `status=Published` rows flow to Purview |

---

## G11 — Optional Ontology And B2C Extensions

**Priority:** P4
**Status:** ⏸ Blocked / Deferred to Phase D

| # | Task | Status | Notes |
|---|---|---|---|
| G11-1 | Ontology layer for Enercare domain classes (typed relationships) | 🔴 Not Started | Deferred to Phase D — Purview Unified Catalog typed-relationships not yet GA |
| G11-2 | AI gap-fill at scale across sparse metadata | 🔴 Not Started | Depends on G10 |
| G11-3 | B2C/customer support chatbot architecture | ⏸ Blocked | Not part of the immediate build |

---

## G12 — Phase A Design Commit

**Priority:** P1
**Status:** 🟢 Done
**Goal:** Land a complete, brief-aligned, north-star-tested design package that the rest of the build executes against.

| # | Task | Status | Notes |
|---|---|---|---|
| G12-1 | MS Learn research brief for Purview Unified Catalog Phases 1–5 | 🟢 Done | `docs/purview-governance-brief.md` — 32 sources |
| G12-2 | Four-tier placement model (T1 SQL / T2 customer files / T3 Fabric / T4 Purview) | 🟢 Done | `docs/purview-demo-data-design.md` §1 |
| G12-3 | SQL extensions DDL + seed (9 PII columns + 6 new tables) | 🟢 Done | `sql/04_*.sql`, `sql/05_*.sql` |
| G12-4 | Customer-files CSVs aligned to brief Phase 1–5 schema | 🟢 Done | 6 CSVs in `purview/`; alignment proof in `docs/purview-csv-alignment.md` |
| G12-5 | Enercare leadership lineup confirmed from Brian Lung correspondence + 2026-05-20 meeting | 🟢 Done | Victoria, Ranbir, Ci Zhu, Rupal, Shruthi — Christopher Dingle deliberately out of demo scope |
| G12-6 | SIN classifier backstop strategy (three-layer guarantee) | 🟢 Done | `docs/purview-sin-classifier-backstop.md`; `tools/sin_luhn_generator.py` (self-test passes); `tools/purview_create_sin_backstop.py` |
| G12-7 | Notebook numbering aligned to `nb_07a → nb_07b → nb_07` convention | 🟢 Done | Mirrors established `nb_04a → nb_04` pattern; reflected in 2-day plan and data-design doc |
| G12-8 | Demo north-star scenario (Maria) memorialized | 🟢 Done | `docs/purview-maria-north-star-scenario.md` — three acts, 8 acceptance criteria, feature traceability |
| G12-9 | Readiness assessment + 2-day execution plan | 🟢 Done | `docs/purview-design-readiness-assessment.md`, `docs/purview-2-day-execution-plan.md` |
| G12-10 | Phase A commit to `enercare` branch | 🟡 In Progress | 16 files staged at `/mnt/workspace/output/repo-staging/`; copy + commit pending |

---

## What Stays From The Current Build

These maintained assets remain valid:

- `fabric/nb_01_setup_demo_environment.Notebook/`
- `fabric/nb_02_metadata_pipeline_demo.Notebook/`
- `fabric/nb_03_pbi_star_schema.Notebook/`
- `fabric/nb_04a_extend_metadata_schema.Notebook/`
- `fabric/nb_04_sempy_writeback.Notebook/`
- `fabric/nb_05a_publish_synthetic_data_to_sql.Notebook/`
- `fabric/nb_05_push_qa_verified_answers.Notebook/`
- `fabric/nb_06_purview_sql_grants.Notebook/`
- `fabric/BrookfieldEnercare.SemanticModel/definition/`
- `lh_metadata` lakehouse and its working metadata tables
- Fabric managed private endpoint from `Enercare-West3` to `sqlserver-sk2wus3`
- `tools/purview_custom_lineage.py`

### Additional retained requirement

- SemPy and SemPy Labs are the baseline semantic-model write-back path. TMDL remains a supporting source-control artifact through Fabric Git sync.

### Explicitly retired assumptions

- OneLake is **not** the final metadata system of record for this build.
- Source SQL extended properties are **not** assumed to exist.
- The build does not depend on writing source SQL extended properties.

### New artifacts (Phase A)

- `docs/purview-maria-north-star-scenario.md` (north star)
- `docs/purview-demo-data-design.md`
- `docs/purview-csv-alignment.md`
- `docs/purview-sin-classifier-backstop.md`
- `docs/purview-design-readiness-assessment.md`
- `docs/purview-2-day-execution-plan.md`
- `purview/domain-charter.csv`
- `purview/data-product-catalog.csv`
- `purview/role-directory.csv`
- `purview/glossary-master.csv`
- `purview/cde-catalog.csv`
- `purview/label-policy.csv`
- `sql/04_purview_demo_extensions.sql`
- `sql/05_seed_purview_demo_data.sql`
- `tools/sin_luhn_generator.py`
- `tools/purview_create_sin_backstop.py`

### New artifacts (Phase B — Days 1–3)

- `fabric/nb_07a_ingest_customer_files.Notebook/` (support — runs first)
- `fabric/nb_07b_merge_customer_metadata.Notebook/` (support — runs second)
- `fabric/nb_07_publish_to_purview.Notebook/` (**primary** of nb_07 family)
- `tools/sempy_label_writer.py` (helper for `nb_04` MIP label annotations)

---

## Immediate Next Build Steps (2-Day Compressed Window)

The full execution plan is in `docs/purview-2-day-execution-plan.md` (2-day cadence). Summary:

| Day | Goal | Phase |
|---|---|---|
| 0 (today) | Commit Phase A; verify M365 SKU; verify Fabric tenant labels enabled; confirm asset curation not yet enabled | Phase A close |
| 1 | SQL extensions live + Luhn-valid SINs + custom SIN SIT registered + `nb_07a` built and run | Phase B start |
| 2 | Asset curation enabled; `nb_07b` built; `nb_04` extended; `nb_07_publish_to_purview` Phases 1–3 (domains + data products) | Phase B middle |
| 3 | `nb_07` Phase 4 (glossary + CDEs); 4 labels + Protection Policy; scans re-run with custom SIN SIT | Phase B close / G8 close |
| 4 | Equipment ontology + customer-experience KPIs + agent vocabulary + term-level policies on PIPEDA/CASL/CONSENT/SIN | Phase C |
| 5 | Verified Q&A push; Maria scenario E2E rehearsal (Tom, Victoria, Ci Zhu); evidence capture | Phase C close |

---

## Acceptance Criteria For The Revised Build

The demo is accepted when:

1. **Maria scenario passes end-to-end** — Tom's call, Victoria's review, and Ci Zhu's audit all run from the same governed surface with same definitions and no manual reconciliation. (`docs/purview-maria-north-star-scenario.md` §8 enumerates the 8 acceptance criteria.)
2. Synthetic Enercare source data exists in Azure SQL in sub2 with Luhn-valid SINs and the 6 new tables.
3. Fabric mirrors that SQL source into sub1.
4. `BrookfieldEnercare` semantic model carries curated descriptions, CDE annotations, and AI grounding content.
5. Purview in sub3 has scanned both SQL and Fabric assets, with the custom SIN SIT in the active rule set.
6. Purview Unified Catalog displays 3 published domains, 3 published data products, 35+ glossary terms, 12 CDEs, 4 sensitivity labels.
7. At least one validated lineage chain (Net Revenue or FCR) shows the SQL → mirror → SM → report path.
8. The Fabric JDBC smoke-test continues to validate private connectivity.

---

## Pre-mortem (residual risks for the 2-day window)

| Risk | Day at risk | Mitigation |
|---|---|---|
| M365 E3/E5 SKU missing | Day 3 | Day 0.3 verification; if missing, demo labels via annotation only and skip Phase 5.4 |
| Fabric mirror lag on new columns | Day 1 → Day 2 | Run mirror sync explicitly after `04_*.sql`; manual trigger if stuck |
| Purview SDK / CDE API instability (preview) | Day 2 → Day 3 | Pre-script both API and portal paths; UI fallback in sub-1hr |
| Asset curation enablement is irreversible | Day 2 | Sandbox test if available; Ci Zhu approval gates the enable click |
| Custom SIN SIT mis-fires | Day 3 | Day 1 standalone test with sample data via Purview SIT test tool |
| SemPy Labs writeback fails mid-batch | Day 2 → Day 4 | Idempotent writeback in `nb_04`; re-runnable from the merged DataFrame |
| Power BI Q&A latency on new measures | Day 5 | Test from Day 4 evening so latency surfaces before rehearsal |

---

## Single-owner accountability statement

Sean Kelley is the sole accountable owner for every Build Gap and every task in this document. Microsoft delivery support is available from Alison Pouw (Purview SE), Ajay Jagannathan (Fabric/Data), Brian Lung (Account Tech Strategist), and Naunihal Singh Sidhu (Azure Fabric FSI Data SE) — but accountability does not delegate. Post-handoff role transitions to Enercare-side owners (Ci Zhu for tenant governance; Victoria Tan for DOM-CUSTOPS) are documented in `purview/role-directory.csv` and flagged with `assignment_note` describing the transfer trigger.

