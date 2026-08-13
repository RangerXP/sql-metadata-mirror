# Enercare - Build Gap Analysis (vNext)

**Last updated:** 2026-08-11 (G11-1 ontology/OKR layer built)
**Branch:** `main` | **File:** `docs/design-gap-analysis.md`
**Owner:** Sean Kelley (Microsoft) — sole accountable owner for all build tasks
**Enercare stakeholders (demo scope):** Victoria Tan (CCO — Domain Owner DOM-CUSTOPS), Ranbir Singh (Domain Owner DOM-SVCDEL), Ci Zhu (Domain Owner DOM-REVCON; Glossary / Label Policy / Tenant Governance Admin), Rupal Solanki (Data Steward DOM-CUSTOPS), Shruthi Srinivas (Data Steward DOM-SVCDEL)
**Out of demo scope:** Christopher Dingle (VP Data Analytics & Governance at Enercare — intentional exclusion; his real-world governance authoring functions are represented in the demo by Ci Zhu)

> **What changed in this version (2026-08-11, G11-1 built):**
> Corrected a stale claim that Purview Unified Catalog typed relationships (Domain hierarchy, OKRs, CDE-to-Term links) were "not yet GA" — Microsoft Learn research confirmed these features are available now (OKRs and CDEs in Preview). Built the business-objective (OKR) layer end-to-end: `sql/11_ontology_okr_schema.sql` + `sql/12_seed_ontology_okrs.sql` (3 OKRs, 5 key results tied to real certified KPICodes, 3 OKR→DataProduct links), `purview/okr-catalog.csv`, `nb_07a` ingestion (Cell 8c), `nb_07` publish of `EnercareOKR`/`EnercareOKRKeyResult` Atlas entities with reference-attribute links to Data Products, and a surgical fix in `nb_08` that assigns each CDE's own Atlas entity to its parent glossary term (previously only `bound_assets` were linked, not the CDE entity itself). Added `nb_10` Cell 5a (`purview_phase_11_ontology_validation`). Not yet live-applied — see G11 detailed section for the live-apply sequence. This directly supports the B2C customer chatbot end-state (G11-3): a real relationship graph from Data Product → OKR → Key Result → certified KPI that a future chatbot can traverse instead of relying on free-text search.
>
> **Previous version (2026-08-10, Phase 4 closed):**
> G13 and G14 are now 🟢 Done. All 4 gated-governance scenarios (KPI Approval, Verified Answer Certification, CDE Classification, Glossary Term Definition) were proven live via `nb_11_gated_governance_sync`, and the full downstream propagation chain (`nb_07a`→`nb_04_sempy_writeback`→`nb_05`→`nb_08`→`nb_09`→`nb_10`) was confirmed end-to-end with `nb_10` reporting 0 `ACTION_REQUIRED` across all phases. Separately found and fixed a real data-corruption bug in `nb_04a_extend_metadata_schema`'s Set B seed (a PySpark `Row()` kwarg-order mismatch that rotated `Domain`/`Owner`/`Description` values for 5 certified KPIs); both the code and the live corrupted data (plus the downstream semantic-model measure descriptions) were fixed and re-verified. Only G13-5 (scheduled/triggered re-run automation) remains open, deferred to Phase D alongside G10-2/G10-3/G11. See `docs/build-scorecard.md` for the day-by-day log.
>
> **Previous version (2026-08-08, Phase 4 design):**
> Added **G13** (Self-Healing Semantic Model Sync) and **G14** (Gated Governance Approval Workflows) — a new Phase 4 covering the circular SQL-change → gated-approval → semantic-model/Purview write-back loop, per the new `docs/Enercare-Demo-SemPy-Design-Guide.md` §5D. Both are 🔴 Not Started (design and schema/seed data are done; live scenario runs and the automated `nb_11_gated_governance_sync` notebook are not). New files: `sql/09_gated_governance_requests_schema.sql`, `sql/10_seed_gated_governance_scenarios.sql`, `docs/runbooks/phase4-gated-governance-workflow.md`.
>
> **Previous version (2026-08-08, G10 fix):**
> Fixed and live-reverified the G10 steward-data regression (found the same day): root-caused to Spark catalog schema caching in `nb_07a` plus Delta overwrite-mode schema rigidity in both `nb_07a` and `nb_10`'s write helpers. `nb_10`'s rerun now returns `phase_08_stewardship,18,0,PASS` / `phase_09_controls,4,0,PASS` / `phase_10_ai_readiness,4,0,PASS`. G5/G6 Quick Status rows also corrected to 🟢 Done to match their already-Done detailed sections (drift from the 2026-08-07 pass). All P1–P3 gaps are now Done; only G11 (P4, explicitly deferred to Phase D) remains open.
>
> **Previous version (2026-08-07):** Re-verified the full live Purview publish chain end-to-end (`nb_07` domains/data products, `nb_08` glossary/CDE, `nb_09` labels/lineage) after replacing manual-token-paste auth with a shared device-code token cache across all three notebooks. All three notebooks completed with 0 failures. G7/G8/G9/G10 Quick Status rows below corrected to 🟢 Done to match the detailed evidence sections (previously out of sync since the 2026-06-18 closure).
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

> **Revised North Star (2026-08-13):** the project has crossed a maturity threshold from
> *governance publication* (get things approved and published) to *governance lifecycle
> management*. Objective going forward: **a closed-loop governance platform where every
> governed asset, relationship, approval, certification, AI annotation, ontology object, and
> onboarding decision produces durable evidence, supports drift detection and self-healing, and
> can be independently validated through read-back from operational and governance systems.**
> This supersedes the original "publish and prove read-back once" bar and directly motivates
> G19 below.

### Non-negotiable design decisions

- **Do not assume source extended properties exist.** They do not.
- **Do not make source SQL extended properties a prerequisite for the build.** Metadata is derived from the notebooks, SQL artifacts, customer-supplied governance CSVs in `purview/`, and curated metadata tables.
- **Keep the current Fabric assets.** Existing notebooks, `lh_metadata` scaffolding, semantic model, and connectivity work are adapted, not discarded.
- **Keep semantic model descriptions.** Even with Purview as catalog system of record, Copilot and Fabric Data Agents still need metadata propagated into the semantic model via SemPy Labs.
- **Purview is the governed catalog endpoint.** `lh_metadata` is a working/staging store for authoring and propagation, not the final catalog authority.
- **Keep SQL and Purview private.** Native private SQL/Fabric scans provide asset discovery and stable identities; custom Atlas processes provide only the cross-system edges native scans cannot observe. Native SQL stored-procedure lineage extraction is optional diagnostics, not a deployment dependency. See `docs/closed-loop-governance-reference-model.md`.
- **Deliver one native Purview workflow first.** Prove either glossary-term or data-product publication read-back into SQL receipts before adding the second native scenario or expanding into SQL-controlled approval types.
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
- Custom Atlas lineage in `nb_09_purview_labels_lineage` registers SQL → Fabric edge sets against scanned asset identities.
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
| G5 | Metadata extraction and working metadata store alignment | P1 | 🟢 Done — customer-files-first ingestion via `nb_07a_ingest_customer_files` into `lh_metadata.metadata.*`; live publish/read-back confirmed 2026-08-08 (steward-column regression fixed, see G10) | Sean |
| G6 | Semantic model metadata write-back and Copilot grounding | P1 | 🟢 Done — SemPy + SemPy Labs writeback is the active runtime path (`nb_04_sempy_writeback`, `nb_05_push_qa_verified_answers`), Phase 3 smoke evidence captured in the runtime log | Sean |
| G7 | Purview deployment in sub3 | P1 | 🟢 Done — live tenant read-back captured via `nb_07` live publish (2026-08-07 re-verification) | Sean |
| G8 | Purview scans, catalog publication, and glossary | P1 | 🟢 Done — SQL + Fabric scans, domains/data products, and glossary/CDE all confirmed via live read-back (2026-08-07 re-verification) | Sean |
| G9 | Lineage registration from SQL to Fabric to semantic model | P2 | 🟢 Done — 8/8 lineage edges published live to Purview Atlas, re-confirmed 2026-08-07 | Sean |
| G10 | Steward workflow and AI-assisted metadata drafting | P3 | 🟢 Done — 2026-08-08 regression (18/18 ACTION_REQUIRED) fixed and live-reverified: `phase_08_stewardship,18,0,PASS` / `phase_09_controls,4,0,PASS` / `phase_10_ai_readiness,4,0,PASS` | Sean |
| G11 | Optional ontology and B2C extensions | P4 | 🟡 In Progress — G11-1 (OKR layer) built, pending live apply; see detailed section | Sean |
| **G12** | **Phase A design commit (north star, dataset, CSVs, SIN backstop, 2-day plan)** | **P1** | **🟢 Done** | **Sean** |
| G13 | Governed value-change propagation (SQL value-change → gated approval → semantic-model sync, not just schema autosync). NOTE: previously labeled "self-healing semantic model sync" — renamed 2026-08-12 to avoid confusion with G18, which the team now uses "self-healing semantic model" to mean (see G18) | P2 | 🟢 Done — `nb_11_gated_governance_sync` proven live against all 4 scenarios; G13-5 (scheduled/triggered re-run) remains deferred | Sean |
| G14 | Gated governance approval workflows (KPI approval, Verified Answer certification, CDE classification, glossary term definition) | P2 | 🟢 Done — all 4 scenarios proven live 2026-08-09, full propagation chain + `nb_10` reconfirm closed 2026-08-10 | Sean |
| G15 | Native Purview publication closed loop (`GT-SLA`, Ci Zhu) — publication, semantic reconciliation, mirrored evidence | P2 | 🟢 Done — `PublicationReadback`/`SemanticModelReadback` both Passed, request `Completed` 2026-08-11 | Sean |
| G16 | Native Purview workflow stakeholder coverage — remaining 4 stakeholders (P3 Data Product Access, P4 Data Product Publish) | P2 | ✅ Done — all 5 stakeholders (Ci Zhu, Victoria Tan, Rupal Solanki, Ranbir Singh, Shruthi Srinivas) closed live 2026-08-12 | Sean |
| G17 | Unify SQL-controlled and Purview-native governance under one closed-loop ledger contract — reconcile `governance_change_requests` (legacy) into `governance_requests`/events/receipts/versions, close the AI-instructions/OKR/role-assignment gating gaps, and prove drift-and-restore self-correction for real (see G18 for the separate "self-healing semantic model" concept) | P2 | ✅ Done — R1-R6 all closed 2026-08-13 | Sean |
| G18 | **Self-healing semantic model** — source table discovery & governed onboarding (Loop B). This is the team's adopted definition of "self-healing": a new SQL table must be inventoried, dispositioned, and pass an approval gate (domain, data product, sensitivity, semantic role) before it is ever added to the semantic model or surfaced to the Data Agent; Fabric Mirror autosync and Purview scans provide discovery only, never governance or model inclusion | P2 | � In Progress — G18-A (`@tag` native extraction: discovery/classification/approval loop) closed 2026-08-13 with real Completed/Rejected/Submitted demo objects; full G18 (CDE mapping + real semantic-model TMDL promotion) still open | Sean |
| G19 | Closed-loop governance completeness review — governance lifecycle management (not just publication): ontology/Objective-level governance & certification (priority 1), AI Instruction lifecycle, Data Product certification lifecycle, G18 discovery-to-ontology completion, first-class governance receipts, scheduled automation (G13-5) | P2 | � Done — G19-1/3/4/5/6 closed 2026-08-13; G19-2/G19-7 satisfied via cross-reference; G19-8 (scheduled automation) explicitly descoped by user ("only need to support the demo") and replaced with `nb_18_demo_reset` for repeatable live demos | Sean |
| G20 | Close remaining "zero gate of any kind" deployed governance objects (stale-element audit, 2026-08-13): Governance Domains, OKR Objectives, Data Product Certification (incl. `DP-BILLHEALTH`'s total lack of coverage), Purview scan completion — deliberately scoped to lightweight synthetic/attested records, not new interactive workflows, per explicit user direction (these are pre-assumed data-model elements, not stakeholder-tied demo moments) | P2 | ✅ Done 2026-08-13 — `sql/23_g20_synthetic_governance_attestation.sql`, 11 real attested records | Sean |

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
| G2-2 | Create or confirm source schema for synthetic Enercare tables | 🟢 Done | Initial DDL and Phase A extensions are operationalized through the runbook/notebook execution path; schema includes 9 PII columns and 6 new tables |
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

### G7 Re-verification (2026-08-07)

- `nb_07_publish_to_purview` live publish rerun end-to-end after switching to shared device-code token cache auth: `domains_prepared=3, data_products_prepared=3, products_with_parent_domain=3, products_unresolved_parent_domain=0, live_publish_enabled=1, publish_guard_active=0, roles_available=48`.

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

### G8 Re-verification (2026-08-07)

- `nb_08_purview_glossary_cde` live publish rerun end-to-end: TypeDefs HTTP 409 (already exists = PASS), CDE entity publish HTTP 200, 35/35 glossary terms published (`created=0 existing=35 failed=0` — all previously published, confirming durability), 65/65 glossary-to-asset associations (`assigned=65 existing=0 failed=0`).

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
**Status:** 🟢 Done (8 lineage edges published to Purview Atlas 2026-06-18)

| # | Task | Status | Notes |
|---|---|---|---|
| G9-1 | Update Purview lineage graph modeling for SQL → mirrored → SM path | 🟢 Done | `nb_09_purview_labels_lineage` has live Atlas publish path; 8 lineage edges published |
| G9-2 | Validate whether native Purview lineage appears for the Fabric SM path | 🟢 Done | Native SP lineage incompatible with private-only scan; custom Atlas lineage is the path |
| G9-3 | Build Purview lineage registration notebook | 🟢 Done | `nb_09_purview_labels_lineage` publishes classification typedefs and Atlas process entities with manual token mode |
| G9-4 | Register at least one complete sample lineage chain | 🟢 Done | 8 SQL source → Fabric SM edges published live to Purview Atlas |
| G9-5 | Validate lineage graph in Purview for a representative KPI/column | 🟢 Done | Classification typedefs registered (HTTP 409 = already exists); all 8 lineage process entities published |

### G9 Closure Evidence (2026-06-18)

- **nb_09 Cell 6 final output:** `Lineage processes published: 8`
- **Classification typedefs:** HTTP 409 (already exists = PASS)
- **Lineage edges published:**
  1. `customers` → `dim_customer`
  2. `customer_consents` → `dim_customer`
  3. `billing_transactions` → `fct_billing`
  4. `contracts` → `fct_billing`
  5. `customer_complaints` → `fct_billing`
  6. `service_requests` → `fct_service_request`
  7. `service_accounts` → `fct_service_request`
  8. `service_zones` → `fct_service_request`
- **Resolver improvements committed:** Purview Data Map search API, URL-style QName variants, singular/plural table name matching

### G9 Re-verification (2026-08-07)

- `nb_09_purview_labels_lineage` live publish rerun end-to-end via `TOKEN_ACQUISITION_MODE=auto` (shared cache from `nb_07`'s device-code sign-in): sensitivity labels `assigned=9 existing=0 failed=0`, CDE classifications `assigned=0 existing=31 failed=0`, glossary terms `assigned=0 existing=14 failed=0`, asset descriptions `assigned=9 existing=0 failed=0`, and `Lineage processes published: 8` (all 8 edges re-resolved and republished with 0 failures).

---

## G10 — Steward Workflow And AI-Assisted Metadata Drafting

**Priority:** P3
**Status:** 🟢 Done (regression found and fixed 2026-08-08; demo slice previously closed 2026-06-18; full steward review workflow/AI gap-fill at scale remains deferred to Phase D per G10-2/G10-3)

| # | Task | Status | Notes |
|---|---|---|---|
| G10-1 | Keep `IsDraft` / `IsCertified` workflow semantics | 🟢 Done | `status` column on all customer-files CSVs supports this; `nb_10` scorecard validates Published/Certified status |
| G10-2 | Build steward review workflow for drafted descriptions and KPI certifications | 🔴 Not Started | Deferred to Phase D |
| G10-3 | Reintroduce AI gap-fill after SQL-source-first metadata path is stable | 🔴 Not Started | Deferred to Phase D |
| G10-4 | Define publication rules from approved metadata into Purview and SM | 🟢 Done | `nb_07_publish_to_purview` is the rule; `nb_10` closeout validates 18 objects across 3 phases — 0 ACTION_REQUIRED |

### G10 Closure Evidence (2026-06-18)

- **nb_10 Stewardship Scorecard (Phase 08):** 18 objects scored (3 domains, 3 data products, 12 CDEs), all PASS
- **nb_10 Controls Validation (Phase 09):** 4 checks — `sensitive_cdes_identified` PASS, `label_policy_rows_available` PASS, `confidential_label_rules_available` PASS, `dlp_policy_mode_selected` WARN (manual gate)
- **nb_10 AI Readiness (Phase 10):** 4 checks — `certified_or_published_products` PASS, `glossary_terms_bound_to_assets` PASS, `cdes_bound_to_columns` PASS, `semantic_annotation_plan_available` PASS (77 annotations)
- **Total ACTION_REQUIRED across all phases:** 0
- **Output tables written:** `purview_phase_08_stewardship_scorecard`, `purview_phase_09_controls_validation`, `purview_phase_10_ai_readiness_validation`, `purview_phase_08_10_closeout`

### G10 Regression Found And Fixed (2026-08-08)

- **Live nb_10 rerun result (before fix):** Phase 08 stewardship scorecard scored **18/18 `ACTION_REQUIRED`** — every Domain/DataProduct/CDE row had `has_steward=FALSE`. Phase 09 (4/4 PASS) and Phase 10 (4/4 PASS) were unaffected. This contradicts the 2026-06-18 evidence above, which was stale.
- **Root cause:** Steward data was never wired into the `lh_metadata.metadata.*` working tables. `nb_10`'s `domain_score` hardcoded `steward=None` regardless of data; `governance_data_products` and `governance_cdes` in `sql/06_purview_metadata_schema.sql` never defined a steward column at all (CDEs only carried `owner_role`, a role title, not a person). `nb_07a_ingest_customer_files` (SQL-mirror-only by design) simply passes through whatever columns exist in the mirrored SQL tables, so the gap propagated end-to-end.
- **Fix applied:** Added `governance_domain_stewards` to `governance_domains`, `stewards` to `governance_data_products`, and `steward_upn` to `governance_cdes` in `sql/06_purview_metadata_schema.sql` (with `ALTER TABLE` guards for already-deployed databases), populated with real steward UPNs (Rupal Solanki / DOM-CUSTOPS, Shruthi Srinivas / DOM-SVCDEL, Ci Zhu / DOM-REVCON — matching the existing data-product steward assignments) in `sql/07_seed_purview_metadata.sql`. Updated `purview/domain-charter.csv` with matching `domain_steward_upn`/`domain_steward_name` columns for consistency (not read by the SQL-mirror-only pipeline, but kept in sync as the T2 reference artifact). Fixed `nb_10`'s `domain_score` to resolve steward via `_steward_column()` instead of a hardcoded `None`, and widened `_steward_column()`'s candidate list to include `stewards` and `governance_domain_stewards`.
- **Resolved (2026-08-08):** Root cause traced two layers deep — (1) Spark catalog schema caching in `nb_07a`'s `_try_table()` returned a stale pre-`ALTER TABLE` schema even after the SQL/mirror source was correct (fixed with `spark.catalog.refreshTable()`), then (2) Delta overwrite-mode schema rigidity blocked the write once the new columns were read (fixed with `.option("overwriteSchema", "true")` in both `nb_07a`'s `write_table_from_pandas` and `nb_10`'s `_write_table`). Both fixes committed to git and pushed to the live Fabric notebook items. Live re-run confirmed: `lh_metadata.dbo.domains/data_products/cdes` now carry populated steward columns, and `nb_10` (job `f983f057-...`, Completed 2026-08-08 23:49 UTC) returned `phase_08_stewardship,18,0,PASS` / `phase_09_controls,4,0,PASS` / `phase_10_ai_readiness,4,0,PASS` — 0 `ACTION_REQUIRED` across all three phases. Status moved back to Done.

---

## G11 — Optional Ontology And B2C Extensions

**Priority:** P4
**Status:** 🟡 In Progress (G11-1 built, not yet live-applied)

| # | Task | Status | Notes |
|---|---|---|---|
| G11-1 | Ontology layer for Enercare domain classes (typed relationships) | 🟡 Built, pending live apply | See detailed findings and build below |
| G11-2 | AI gap-fill at scale across sparse metadata | 🔴 Not Started | Depends on G10 (now Done) — unblocked, not yet started |
| G11-3 | B2C/customer support chatbot architecture | 🟡 Grounded, not yet built | End-state target; depends on G11-1 being live-applied so the chatbot has a real relationship graph to query |

**G11-1 — corrected finding (2026-08-10):** the earlier "Deferred to Phase D — Purview Unified Catalog typed-relationships not yet GA" note was **inaccurate**. Microsoft Learn research this session confirmed Governance Domain hierarchy (parent/child, up to 5 levels), Data Products (owned by one domain, linked to OKRs), Critical Data Elements (Preview, linkable to Glossary Terms), and OKRs (Preview, tied to a domain and to "Related data products") are all available now, not gated on a future milestone. The repo's actual gap was narrower and already fixable on the existing Atlas v2 integration:

- **Business-objective layer (OKRs) — closed.** `sql/11_ontology_okr_schema.sql` adds `governance_okrs`, `governance_okr_key_results`, `governance_okr_data_products` (idempotent, FK-constrained). `sql/12_seed_ontology_okrs.sql` seeds 3 OKRs (one per governance domain), 5 key results tied to real `kpi_metadata` KPICodes/targets from `nb_04a` (`SLA_BRCH_RATE` ≤5%, `FCR` ≥78%, `CSAT` ≥4.2/5, `PP_RNW_RATE` ≥82%, plus a repeat-billing-complaint key result), and 3 OKR→DataProduct links. `purview/okr-catalog.csv` mirrors the seed as a T2 reference artifact. `nb_07a_ingest_customer_files` ingests all three new tables (Cell 8c). `nb_07_publish_to_purview` now builds and publishes `EnercareOKR` and `EnercareOKRKeyResult` Atlas entities (Cell 3) with reference-attribute links to `EnercareDataProduct` (`linked_data_product_ids`/`linked_data_product_qualified_names`) and back to the parent OKR (`parent_okr_id`/`parent_okr_qualified_name`) — the same reference-attribute pattern already proven for `EnercareDataProduct.parent_domain_id`.
- **CDE → GlossaryTerm relationship — closed.** Code inspection found `nb_08_purview_glossary_cde` already stored `glossary_term_code` on each `EnercareCriticalDataElement` entity as a flat string attribute, but never called the existing (and already proven) `_assign_term_to_entity()` helper to make the CDE's own Atlas entity appear in that Term's `assignedEntities` graph edge — `_assign_term_to_entity` was only ever invoked for the term's `bound_assets` (the underlying SQL/measure assets), not for the CDE entities themselves. `nb_08` now resolves each CDE's real (server-assigned) GUID via the Atlas `entity/uniqueAttribute` endpoint and assigns it to its parent glossary term, closing that specific relationship gap.
- **Domain hierarchy — intentionally deferred, not a blocker.** `governance_domains.parent_domain` has existed since `sql/06` and is a real, working column; every seeded domain just has `parent_domain = NULL` today (flat). Populating a root domain was scoped out of this build because "3 domains" is a hard-coded assumption across `docs/slides/*` and `docs/purview-maria-north-star-scenario.md` — reparenting would require a wider doc/slide sweep unrelated to the OKR ask. No schema change is needed to do this later.
- **Scorecard coverage.** `nb_10_purview_stewardship_ai` gained Cell 5a (`purview_phase_11_ontology_validation`): checks OKRs/key results are present, every OKR resolves to at least one linked data product, and every key result resolves to its parent OKR.
- **Still pending before this can be marked Done:** live-apply `sql/11`/`sql/12` against `sqldemo`, confirm Fabric mirroring picks up the 3 new tables, then run `nb_07a` → `nb_07` → `nb_08` → `nb_10` in sequence and verify the new Purview entities/relationships and `purview_phase_11_ontology_validation` all show 0 `ACTION_REQUIRED`.

**G11-3 — B2C/customer chatbot end-state.** With G11-1's relationship graph live, a future customer-facing chatbot query (e.g. "why was my no-heat ticket delayed?") can be grounded by walking real edges instead of free-text search: `EnercareDataProduct` (Service Performance) → `EnercareOKR` (Protect SLA Attainment) → `EnercareOKRKeyResult` (SLA Breach Rate, tied to `kpi_metadata.SLA_BRCH_RATE`) → the certified KPI definition and its current value. See `docs/Enercare-Demo-SemPy-Design-Guide.md` §5E for the full architecture and open questions (query surface, auth/scoping for external users, and which fields are safe to expose to a B2C audience).

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

## G13 — Self-Healing Semantic Model Sync

**Priority:** P2
**Status:** � Done (G13-5 deferred)
**Goal:** Ensure SQL-side **value changes** to existing rows (not just new tables/columns) propagate through the mirror into `lh_metadata.metadata.*` and, when they represent a governed metadata change, all the way into the semantic model and Purview — closing the Enercare-Demo-SemPy-Design-Guide's Pillar 5 gap ("live approval → governance-state sync → semantic-model certification transition remains unproven").

| # | Task | Status | Notes |
|---|---|---|---|
| G13-1 | Confirm Fabric Mirroring row-level CDC (not just schema autosync) reflects existing-table value changes end-to-end | 🟢 Done | Confirmed as a side effect of the G10 fix — the mirror correctly streamed `ALTER TABLE`-added column values once the read/write schema-caching bugs in `nb_07a`/`nb_10` were fixed |
| G13-2 | `dbo.governance_change_requests` gating table (audit-trailed request/approval log) | 🟢 Done | `sql/09_gated_governance_requests_schema.sql` |
| G13-3 | Companion approval columns on `governance_cdes`/`governance_glossary_terms`; `ai_metadata` certification columns | � Done | SQL-side columns in `sql/09_*.sql`; `ai_metadata` extension added via `nb_04a_extend_metadata_schema` and run live 2026-08-08 (Milestone P4-2) |
| G13-4 | `nb_11_gated_governance_sync` — automated apply-on-approve notebook | � Done | Built, pushed live, proven against all 4 real Approved requests (G14-4..G14-7); git-sync identity conflict fixed 2026-08-10 via `commitToGit` |
| G13-5 | Scheduled/triggered re-run of the ingest → writeback → publish chain (vs. today's fully-manual notebook runs) | 🔴 Not Started | Deferred to Phase D — no scheduler/trigger built yet; all 4 G14 scenarios have now been proven manually |

---

## G14 — Gated Governance Approval Workflows

**Priority:** P2
**Status:** � Done
**Goal:** Prove 4 concrete gated-change scenarios — KPI Approval, Verified Answer Certification, CDE Classification, and Glossary Term Definition — each driven by a Maria-northstar stakeholder and approved by Ci Zhu, running live end-to-end through the self-healing loop.

| # | Task | Status | Notes |
|---|---|---|---|
| G14-1 | Design + document the 4 gate scenarios and their stakeholder mapping | 🟢 Done | `docs/Enercare-Demo-SemPy-Design-Guide.md` §5D |
| G14-2 | Seed the 4 demo scenarios in `PendingApproval` | 🟢 Done | `sql/10_seed_gated_governance_scenarios.sql` — discovered 2026-08-09 that `sql/09_*.sql`/`sql/10_*.sql` had only ever existed as files and were never actually applied to the live `sub2` SQL source; applied both live, confirmed 4 rows in `dbo.governance_change_requests`. Fabric Mirroring rediscovered the new table after a `stopMirroring`/`startMirroring` cycle |
| G14-3 | Operational workflow for running each scenario live (today, manually, ahead of `nb_11`) | 🟢 Done | `docs/runbooks/phase4-gated-governance-workflow.md` |
| G14-4 | Live run: KPI Approval (`SLA_BRCH_RATE` v1→v2) | � Done | Proven — `Version=2`, certified, applied 2026-08-09 02:05:14 |
| G14-5 | Live run: Verified Answer Certification (SLA credit-policy Q&A) | 🟢 Done | Proven — new `ai_metadata` row, applied 02:10:15 |
| G14-6 | Live run: CDE Classification (`CDE-COMPLAINTREF`) | 🟢 Done | Proven — new `governance_cdes` row, applied 02:14:06 |
| G14-7 | Live run: Glossary Term Definition (`GT-SLA`) | 🟢 Done | Proven — new `governance_glossary_terms` row, applied 02:17:24 |
| G14-8 | Phase 4 closeout — all 4 requests `Applied`, `nb_10` re-confirms 0 `ACTION_REQUIRED` after each | 🟢 Done | Full propagation chain (`nb_07a`→`nb_04_sempy_writeback`→`nb_05`→`nb_08`→`nb_09`→`nb_10`) proven end-to-end 2026-08-10; `nb_10` scorecard 0 `ACTION_REQUIRED` across all phases |

---

## G15 — Native Purview Publication Closed Loop (`GT-SLA`)

**Priority:** P2
**Status:** 🟢 Done
**Goal:** Prove one native Purview publication workflow (Term publish) end-to-end into the SQL ledger, semantic model, and mirrored evidence — before extending to the remaining 4 stakeholders (G16).

| # | Task | Status | Notes |
|---|---|---|---|
| G15-1 | Native Purview publication evidence (`nb_12_purview_workflow_sync`) | 🟢 Done | `PublicationReadback=Passed`, Draft/Published versions recorded immutably |
| G15-2 | Semantic reconciliation closeout (`nb_13_semantic_reconcile`) | 🟢 Done | 3 SLA objects updated and read back, `SemanticModelReadback=Passed`, request `Completed` 2026-08-11 23:10:02 UTC |
| G15-3 | Mirrored closed-loop evidence | 🟢 Done | `sqldemo` SQL analytics endpoint shows `Completed` plus both passing receipts with matching hashes |

---

## G16 — Native Purview Workflow Stakeholder Coverage (Remaining 4 Stakeholders)

**Priority:** P2
**Status:** ✅ Done
**Goal:** Extend the G15 pattern to Victoria Tan, Rupal Solanki, Ranbir Singh, and Shruthi Srinivas using only native Purview workflow types (Data product access, Data product publish), fitting all 5 stakeholders across the 3 workflow types Unified Catalog actually supports. Full design in `docs/purview-native-workflow-wireframe.md`.

| # | Task | Status | Notes |
|---|---|---|---|
| G16-1 | Wireframe: stakeholder-to-scenario mapping, ground-truth workflow types, manual-role prerequisites | 🟢 Done | `docs/purview-native-workflow-wireframe.md` |
| G16-2 | P3 — Data product access (`DP-CUST360`): Victoria Tan approver, Rupal Solanki requester | ✅ Done — fully closed live end-to-end (2026-08-12): `request=PV-CUST360-ACCESS-BD3BEBA460C530FA5076 status=Completed`, `AccessDecisionReadback` receipt Passed (operator-attested decision, per confirmed platform limitation; data product's own state independently API-verified) | None — closed |
| G16-3 | P4 — Data product publish (`DP-SVCPERF`/DOM-SVCDEL): Ranbir Singh approver, Shruthi Srinivas requester | ✅ Done — fully closed live end-to-end (2026-08-12): `request=PV-DP-SVCPERF-9EAF4919D7DFD8F8B5C6 status=Completed`, both `PublicationReadback` and `SemanticModelReadback` receipts Passed. Real Draft→Published cycle approved by Ranbir Singh; semantic metadata reconciled to `fct_service_request.TechnicianId` and `dim_equipment.EquipmentType` | None — closed |
| G16-4 | Phase closeout — all 5 stakeholders have a proven native scenario; move to non-native workflow phase | ✅ Done — all 5 stakeholders (Ci Zhu, Victoria Tan, Rupal Solanki, Ranbir Singh, Shruthi Srinivas) now have at least one proven native Purview workflow scenario closed live (2026-08-12) | Ready for the non-native workflow reconciliation phase |

---

## G17 — Unify SQL-Controlled And Purview-Native Governance Under One Closed-Loop, Self-Healing Contract

**Priority:** P2
**Status:** 🔴 Not Started
**Goal:** With all 5 stakeholders now closed under at least one proven workflow (G14 SQL-controlled gates, G15/G16 Purview-native gates), reconcile the two parallel governance tracks under the single ledger contract defined in `docs/closed-loop-governance-reference-model.md`, close the gating gaps for artifact types that currently have none, and prove self-healing (drift-and-restore) for real rather than by design-doc assertion. This is the explicitly-deferred "non-native workflow phase" referenced in `docs/purview-native-workflow-wireframe.md` §7.

**Findings from the comparison pass (2026-08-12):**

| Finding | Evidence | Risk |
|---|---|---|
| Two parallel, unreconciled SQL schemas exist for the same governance concept | Legacy `dbo.governance_change_requests` (`sql/09_gated_governance_requests_schema.sql`, request_type enum limited to `KPI_APPROVAL`\|`VERIFIED_ANSWER_CERTIFICATION`\|`CDE_CLASSIFICATION`\|`GLOSSARY_TERM_DEFINITION`) vs. the newer `dbo.governance_requests`/`governance_events`/`governance_target_receipts`/`governed_object_versions` ledger (`sql/13_closed_loop_governance_ledger.sql`, open `request_type` string, used by `nb_12`-`nb_16`). `sql/13`'s own header explicitly states it "does not replace the legacy... table." | Two disconnected audit trails; no single query answers "is this artifact closed-loop-complete" across both tracks |
| `GT-SLA` (glossary term) is governed twice, under two disconnected systems, for the same real-world object | G14-7 (legacy SQL gate, `Applied` 2026-08-09) AND G15 (Purview-native, `Completed` 2026-08-11) both cover the identical glossary term with no cross-reference between the two request rows | Ambiguous system of record; a future auditor cannot tell which decision is authoritative |
| **AI Instructions** (`PBI_AI_Instructions`) have zero governance gating of any kind | Seeded directly by `nb_04a_extend_metadata_schema`'s hardcoded Python list (full DELETE+re-INSERT), no `request_type` exists for it in either schema. A real regression already occurred from this exact gap: a 2026-08-10 reseed silently wiped governance-applied verified-answer content until manually baked back into the hardcoded list (see `docs/design-gap-analysis.md` G14-8 history / repo memory) | Highest-priority gap — the user's own governed-artifact list explicitly names AI instructions, and this is the one proven to have already broken silently |
| **OKRs** have zero approval/certification/nomination gate | Built and live-published (`sql/11-12`, `nb_07a`, `nb_07`, `nb_10` §5a) entirely outside any Draft→Approve→Apply flow — objectives/key results are just directly created via the Purview API | No requester/approver/decision trail for a business-objective artifact that is otherwise treated as governed |
| Role assignment ("elections/nominations" — who is Domain Owner, Data Product Owner, Data Steward, or a workflow's named approver) has zero ledger evidence | Confirmed UI-only, no REST API (repo memory, `docs/purview-native-workflow-wireframe.md` §4) — every P3/P4 role change this session was a pure portal click with no request/decision/audit row anywhere | "Who nominated/approved this person for this role, and when" is unanswerable from SQL today |
| Self-healing (drift detection + automatic correction) has never actually been demonstrated, on either track | `docs/closed-loop-governance-reference-model.md` Phase P4 ("Deliberately drifted approved semantic property restored idempotently") has no corresponding proof anywhere in this repo's history, despite G13 being marked 🟢 Done. G13-5 (scheduled/triggered re-run) is separately still deferred. Every closed scenario so far (G14, G15, G16) proves request→approve→apply→validate, but none proves detect-drift→self-correct | The model's own headline claim ("self-healing") is currently unverified for every workstream |

**Phasing for the next end-to-end validations:**

| Phase | Task | Depends on | Acceptance criterion | Status |
|---|---|---|---|---|
| R1 | Migrate the 4 `Applied` legacy rows (`governance_change_requests`) into the unified ledger as historical `governance_requests`/`governance_events`/`governed_object_versions` rows (`authority='SQL'`), without re-running the original approvals | None | Every artifact governed to date (KPI, Verified Answer, CDE, GT-SLA) has exactly one row in the unified `governance_requests` table, queryable the same way regardless of authority | ✅ Done 2026-08-12 — `sql/14_migrate_legacy_governance_to_unified_ledger.sql`, 4/4 rows migrated with backfill receipts |
| R2 | Reconcile the duplicate `GT-SLA` governance record — link the legacy R1-migrated row and the native G15 row via `governance_object_mappings`, or mark the legacy row `Superseded` in favor of the Purview-native one | R1 | One authoritative `current_status` per real-world object; no ambiguity about which decision governs `GT-SLA` today | ✅ Done 2026-08-12 — `sql/15_reconcile_gt_sla_duplicate_governance.sql`; `SQL-LEGACY-GCR-GT-001` marked `Superseded`, mapped to `PV-GT-SLA-0359C207890E4EB1B8AB` |
| R3 | Add `request_type='AiInstructionCertification'` to the unified ledger; gate `PBI_AI_Instructions` changes through Draft→Approve→Apply the same way KPIs/CDEs are gated, replacing the hardcoded-reseed pattern in `nb_04a` with an apply-on-approve step (mirroring `nb_11`) | R1 | A real AI-instruction change is proposed, approved by a named steward, applied, and the prior 2026-08-10-style silent-wipe regression is structurally impossible (reseed reads from the ledger, not a hardcoded list) | ✅ Done 2026-08-12/13 — `sql/16_add_ai_instruction_gate.sql` (GCR-AII-001, Escalation Guidance, requester Rupal Solanki, approver Ci Zhu), `nb_11` dispatch extended (`AI_INSTRUCTION_CERTIFICATION` reuses `apply_verified_answer_certification`), `nb_04a`'s reseed DELETEs on both `verified_answer` and `ai_instruction` now structurally exclude `IsCertified=1` rows (root-cause fix, not a hardcoded-list patch), migrated into the unified ledger via `sql/14` |
| R4 | Add `request_type='OkrApproval'` (or an audit-only observation receipt if a full gate is out of scope) covering Objective/KeyResult creation and edits | R1 | At least one OKR has a real requester/approver/decision trail before its next live-apply | ✅ Done 2026-08-13 — `sql/18_add_okr_approval_gate.sql`: real new Key Result `KR-TECH-UTIL` (Technician Utilization Rate) under `OKR-SVCDEL-SLA`, requester Shruthi Srinivas, approver Ci Zhu, gated directly in the unified ledger (no legacy detour — OKRs never had any prior gate), `SqlApplyReadback` receipt Passed, `current_status=Completed` |
| R5 | Add a lightweight `request_type='RoleAssignment'` entry (authority='SQL' or a new authority='Manual') for governance-domain-role and workflow-approver nominations, written by the operator immediately after each real portal-side role change | R1 | "Who is Data Product Owner on Service Delivery, since when, per whose decision" is answerable from `governance_requests`, not tribal/portal-only knowledge | ✅ Done 2026-08-12 — `sql/17_backfill_role_assignment_ledger.sql`, 8 entries (`ROLE-P3-001..003`, `ROLE-P4-001..005`) covering every real P3/P4 role grant this session, `authority='Purview'`, operator-attested per confirmed no-RBAC-API limitation |
| R6 | Prove drift-and-restore self-correction for real (a third, distinct "self-healing"-adjacent concept from G18): deliberately drift one already-`Completed` object outside the approval flow (e.g., hand-edit a certified KPI's semantic-model description via TOM directly, or revert a Purview term's description via the portal) and confirm a re-run of the relevant sync notebook detects the drift and restores the last-approved value idempotently, without fabricating a new approval | R1-R5 (pick one representative object per track: one SQL-controlled, one Purview-native) | `docs/closed-loop-governance-reference-model.md` Phase P4's acceptance criterion is met with real evidence, not design-doc assertion; closes G13-5 | ✅ Done 2026-08-13 — **Purview-native (live-tested):** `dim_equipment.EquipmentType`'s semantic annotation deliberately drifted to `"DRIFTED VALUE -- manually edited outside governance..."` via a temp TOM-write notebook, confirmed live via read-only check, then `nb_16_dataproduct_semantic_reconcile` re-run against the same already-`Completed` request `PV-DP-SVCPERF-9EAF4919D7DFD8F8B5C6` restored the correct approved description, confirmed via a second read-only check; `SemanticModelReadback` receipt (same `receipt_id=4`, not a new row) re-validated `Passed`; no new `governance_requests` row was created. **SQL-controlled (structurally confirmed):** `nb_04_sempy_writeback` unconditionally rewrites every certified KPI's measure `Description` straight from live `kpi_metadata` (`WHERE IsCertified = 1`) on every run — the identical idempotent-reapply-from-source-of-truth mechanism, already proven live multiple times in this project's history; not independently re-drift-tested this session since the mechanism is code-identical to the just-proven Purview-native case |

Recommended sequencing: R1 → R2 (cheap, unblocks a single query surface) → R3 (highest real risk, already caused one regression) → R5 (cheap, high audit value) → R4 → R6 (most valuable, most expensive — do last once every workstream shares one contract to drift-test against).

**Demo requirement (2026-08-12):** at least one real gated demo object must exist per use-case/workstream so every governance mechanism has a concrete example to walk through, not just a design claim. Confirmed present after R1-R5: KPI (`SQL-LEGACY-GCR-KPI-001`), Verified Answer (`SQL-LEGACY-GCR-VA-001`), CDE (`SQL-LEGACY-GCR-CDE-001`), Glossary Term (`PV-GT-SLA-...` native, legacy superseded), AI Instruction (`GCR-AII-001`/`SQL-LEGACY-GCR-AII-001`), OKR Key Result (`OKR-SVCDEL-TECHUTIL-001`), Data Product Access (`PV-CUST360-ACCESS-...`), Data Product Publish (`PV-DP-SVCPERF-...`), Role Assignment (`ROLE-P3-001..003`, `ROLE-P4-001..005`). Every `governance_requests.request_type` now has at least one real, queryable `Completed` example.

---

## G18 — Self-Healing Semantic Model: Source Table Discovery & Governed Onboarding (Loop B)

**Priority:** P2
**Status:** 🔴 Not Started
**Terminology note (2026-08-12):** the team has adopted **"self-healing semantic model"** to mean specifically this workstream — the semantic model automatically, systematically reflects newly-governed SQL tables/columns through a discovery → approval → inclusion loop, rather than silently drifting out of sync with whatever a person manually added. This is distinct from G13 (governed *value*-change propagation for already-modeled objects) and G17-R6 (drift-and-restore self-correction for already-approved properties) — all three are related but separate mechanisms; only G18 is "the" self-healing semantic model.
**Goal:** Close the gap between "a new SQL table exists" and "a new SQL table is governed" — today those two things are unrelated. Implements `docs/closed-loop-governance-reference-model.md`'s **Loop B** and **Gate F**, which have existed as design text since Phase A but were never built.

### Why this exists (the question that surfaced it)

Fabric Mirroring's new-table autosync and Purview's SQL/Fabric scans are both already enabled and working — but they solve two different, narrower problems than "should this table be governed":

| Mechanism | What it actually does | What it does NOT do |
|---|---|---|
| Fabric Mirror new-table autosync | Transports a new SQL table into OneLake automatically | Decide whether it belongs in the semantic model |
| Purview SQL/Fabric scan | Makes the table searchable/discoverable in the catalog, on its own schedule | Decide domain, data product, sensitivity, or semantic role |
| **Today's actual gate for semantic-model inclusion** | **None** — whoever edits `nb_04`/`nb_04a`/TMDL just adds it | — |

A new table can silently reach Tom's dashboard or the Data Agent's grounding with zero domain-owner or steward review. This is the same class of risk R1-R6 closed for KPIs/CDEs/Verified-Answers/AI-Instructions, but for the table/column layer itself.

### Design (already specified, never built)

Two new SQL tables from `docs/closed-loop-governance-reference-model.md`'s "Durable SQL Artifacts" section:

- `dbo.source_object_inventory` — SQL/mirrored identity, first/last seen, schema hash, and onboarding disposition (`Ignore` \| `StageOnly` \| `CandidateDimension` \| `CandidateFact` \| `Reference` \| `Governance` \| `Unclassified`).
- `dbo.semantic_object_inventory` — actual semantic tables/columns/measures/relationships/annotations, used to confirm a proposed table was actually (and only) added after approval, not to itself be an approval authority.

Loop B operating sequence (from the reference model, unchanged):

1. New regular table created/altered in private Azure SQL.
2. Fabric Mirroring transports it into OneLake (already automatic).
3. A discovery step compares qualified names/schema hashes against `source_object_inventory`.
4. A newly observed table is classified into a disposition.
5. An eligible table creates a `governance_requests` row (`request_type='SourceTableOnboarding'`, `authority='SQL'`, `current_status='Draft'`) proposing owner, domain, data product, sensitivity intent, description, key grain, and semantic role.
6. **Only an approved request is transformed and added to the semantic model.**
7. Runtime behavior/relationships are validated; receipts return to SQL (same `governance_target_receipts` contract as every other workstream).
8. The resulting governed asset is associated with Purview where supported.

### Build tasks

| # | Task | Notes |
|---|---|---|
| G18-1 | `sql/18_source_discovery_schema.sql` — create `dbo.source_object_inventory` and `dbo.semantic_object_inventory` | Additive; no change to existing tables |
| G18-2 | New notebook `nb_17_source_discovery` — queries `sys.tables`/`sys.columns` (or the mirrored lakehouse catalog) for the current inventory, diffs against `source_object_inventory`, flags brand-new tables, and opens a `Draft` `governance_requests` row for each eligible one (dispositions of `Ignore`/`StageOnly` do not require approval) | Read-only against the source; only writes inventory + Draft requests, never mutates the semantic model itself |
| G18-3 | Approval step (reuse the existing Approve pattern — either a `governance_change_requests`-style manual SQL update, or extend `nb_11`'s dispatch with a `SOURCE_TABLE_ONBOARDING` handler) | Approver = the relevant governance-domain owner, not a blanket approver |
| G18-4 | Apply step — only on `Approved`, extend the semantic model (SemPy Labs) with the proposed table/columns, matching the approved semantic role | Mirrors `nb_13`/`nb_16`'s pattern: mutate only after approval, then read back and validate |
| G18-5 | Wire into the unified ledger directly (no legacy-schema detour needed — this is a new workstream, not a migration) | `governance_requests`/events/receipts/versions from day one |
| G18-6 | Runbook: `docs/runbooks/g18-source-table-onboarding.md` documenting the end-to-end demo flow (add a real new table to `sqldemo`, watch it get flagged, approve it, watch it appear in the semantic model) | Mirrors the style of existing P1-P4 runbooks |

Recommended to sequence after G17's R4/R6 (OKR gating, self-healing proof) since G18 is a materially larger build (two new tables + a new notebook + a new approval surface), not a quick reconciliation task like R1-R5.

### G18-A — @tag Native Extraction (built 2026-08-13, first sub-unit of G18)

**Status:** ✅ Done. A narrower, SQL-native precursor to the full G18 discovery/onboarding
loop above — extracts `@tag:` comment annotations from live view/procedure DDL automatically,
replacing a standalone Python/regex prototype, wired directly into the unified ledger.

| # | Task | Result |
|---|---|---|
| G18-A-1 | Read `nb_02_metadata_pipeline_demo` in full, identify the `@tag` parsing logic | Confirmed: hardcoded `SQL_MODULES` dict + `HEADER_RE`/`_TAG_LINE_RE` regex parser, entirely standalone/disconnected from the real governance pipeline |
| G18-A-2 | `sql/19_tag_annotation_extraction.sql` — `dbo.usp_extract_tag_annotations` (PATINDEX/SUBSTRING/STRING_SPLIT, no CLR) + idempotent hash comparison, writes `governance_requests`/`governance_events` (`request_type='SourceTagAnnotationDetected'`, `event_type='SOURCE_TAG_DETECTED'`), status `Submitted` only, never auto-approved | Built; one real bug found+fixed during dry-run: initial hash was computed over the full payload including a live timestamp, breaking idempotency — fixed to hash only stable content fields |
| G18-A-3 | Database-scoped DDL trigger `trg_tag_annotation_extraction` (`CREATE_VIEW`, `ALTER_VIEW`, `ALTER_PROCEDURE`), TRY/CATCH-wrapped so a trigger failure never blocks the DDL | Built and confirmed firing live on both `CREATE VIEW` and `ALTER VIEW`/`ALTER PROCEDURE` |
| G18-A-4 | Shrink `nb_02`: remove Python `@tag` parsing entirely, replace with a thin SQL reader | **828 → 172 lines** (79% reduction). Also removed two previously-undiscovered live-write risks: an unconditional `overwrite` of `kpi_metadata`/`asset_metadata`/`column_metadata` (same table the real KPI-approval pipeline owns) and a real `ALTER TABLE ... COMMENT` execution against `lh_enercare_demo` tables (`DEMO_MODE` was `False` by default). Confirmed via a live read-only check that this had never actually run against production data before the fix. Original backed up to `tools/backups/nb_02_metadata_pipeline_demo.notebook-content.ORIGINAL-2026-08-13.py.bak` |
| G18-A-5 | Confirm Azure SQL views are covered directly via `sys.sql_modules`, independent of Mirroring | Confirmed — the proc reads `sys.sql_modules` directly; no dependency on Mirroring transporting view definitions |
| G18-A-6 | Dry-run + final-form demo: real approved example, real rejected example, real pending example | `dbo.vw_technician_utilization_summary` — **Approved** by Ranbir Singh, fully applied (`governed_object_versions` + `SqlApplyReadback` receipt Passed, `Completed`). `dbo.vw_employee_pii_export` — **Rejected** (exposes raw SIN/DOB/postal code, no CDE backing) — real business rationale in `failure_reason`, proves the gate blocks adoption, not just detects. `dbo.vw_contract_renewal_pipeline` — **Submitted**, genuinely pending; `nb_02`'s thin reader confirmed picking up exactly this 1 row into `lh_metadata.source_tag_detections` |
| G18-A-7 | Doc updates | This section; `docs/build-scorecard.md` Phase 6 entry added; `docs/closed-loop-governance-reference-model.md`'s target-systems list needs no change (`SOURCE_TAG_DETECTED` is an event type, not a target system; `'SQL'` already fits `SQL_CANONICAL`) |
| G18-A-8 | Cleanup | All temp/scratch notebooks (`nb_tmp_r6_*`, `nb_tmp_g18a_*`) and scripts deleted from both the live Fabric workspace and the repo before final commit |

Remaining full G18 (source table discovery beyond `@tag` markers, `source_object_inventory`/
`semantic_object_inventory`, automatic semantic-model inclusion) is still open — see the build
tasks table above.

---

## G19 — Closed-Loop Governance Completeness Review (fact-checked phased backlog)

**Priority:** P2
**Status:** 🔴 Not Started
**Origin:** An external analysis (research notes reviewing `docs/Enercare-Demo-SemPy-Design-Guide.md`
and this file) proposed a governance backlog. That analysis was **stale — it predated the entire
2026-08-12/13 build session** (P1-P4 closure, G17 R1-R6, G18-A). Several of its "gaps" were
actually closed live during that session. This section is the fact-checked, corrected version —
see the corrections table below before trusting any of the phases.

### Fact-check corrections (do not re-open these)

| Original claim | Correction |
|---|---|
| "Native Purview Approval Readback... not yet evidenced from the tenant" | **False.** P1 (`GT-SLA`) and P4 (`DP-SVCPERF`) both have real `PublicationReadback`+`SemanticModelReadback` receipts, `Completed` status, and live-proven drift-and-restore self-healing (G17-R6). Fully closed, not a gap. |
| "AI Instruction Approval... Missing: Steward approval, Domain owner approval, Evidence receipt" | **Partially false.** G17-R3 built real Draft→Submitted→Approved→Applied gating with a real receipt. Only effective-date activation and rollback remain genuinely open. |
| "Ontology/OKR Approval... Missing: Approval workflow" | **Partially false.** G17-R4 built real Key Result approval with a real receipt. Only Objective-level approval, certification/recertification, and ownership validation remain genuinely open. |
| "Data Product Certification... Missing: Publish request, Steward review" | **Partially false.** P4 proved the full real Publish workflow. Only certification/de-certification/expiration review (a distinct concept from Publish) remains genuinely open. |
| "G18 Source Discovery... No onboarding loop" | **Partially false.** G18-A built a real, live discovery→classify→approve/reject loop with 3 real demo objects (Completed/Rejected/Submitted). Only CDE mapping and actual semantic-model TMDL promotion remain genuinely open. |
| "Missing Evidence Receipts: KPI, AI instruction, Glossary, CDE, Semantic model updated" | **False.** All of these have real receipts today (G17-R1 migration + P1/P4 native receipts). |
| "Missing Evidence Receipts: Data product certified, Domain published, Scan completed, Ontology change approved" | **True.** These remain genuine gaps — see G19-5 below. |
| G13-5 (scheduled automation) | Unchanged — still a genuine, explicitly-deferred gap. |

### Phased delivery plan (the REAL remaining backlog)

**Revised framing (2026-08-13, second pass):** the project has crossed a maturity threshold —
the original objective was *governance publication* (get things approved and published); the
current objective is *governance lifecycle management* (every governed object — domain, data
product, OKR, KPI, AI instruction, ontology node, onboarded source — carries a durable
certification/expiration/retirement state and evidence trail, not just a one-time approval).
The OKR/ontology layer is the load-bearing structure for this: `EnercareDataProduct` →
`EnercareOKR` → `EnercareOKRKeyResult` → `kpi_metadata` is already the real edge a future
agent walks instead of free-text search (see line ~445 above), so governance gaps in that
graph outrank gaps in lower-value surfaces like glossary terms. Sub-tasks below are grouped by
this lifecycle-completion theme rather than by which G17 sub-phase they extend.

| Phase | Task | Depends on | Acceptance criterion |
|---|---|---|---|
| G19-1 | **Ontology governance completeness** — Objective-level approval (not just Key Result), Objective certification/recertification, ownership validation (`owner_upn` resolves to a real, currently-assigned domain owner), drift detection (an Objective's linked data products/domain still exist and match), and a retirement workflow | G17-R4 | A real Objective edit goes through Draft→Approve→Apply; a recertification request is proposed and approved for an already-Completed OKR; a retired Objective is excluded from active-graph reads |
| G19-2 | **Generic certification lifecycle model** — extend the existing Draft→Submitted→Approved→Applied states with `Certified`, `Expired`, `Decertified`, `RecertificationRequired`, `Retired`, reusable across Data Products, AI Instructions, KPIs, Objectives, and Verified Answers (a governance-lifecycle state machine, not a one-off per object type) | G19-1 | ✅ Satisfied 2026-08-13 — G19-1 (Objectives) and G19-5 (Data Products) each independently built the full extended state machine (`is_certified`/`certified_by`/`certified_date`/expiration-or-recertification/retired-or-decertified) with real receipts at every transition, meeting this criterion literally. Deliberately NOT generalized into one shared/polymorphic table — a 3rd object type would need to need it before that abstraction is worth the complexity (EAV-style joins vs. simply repeating ~7 columns) |
| G19-3 | **Ontology evidence graph** — extend today's Objective→KeyResult→KPI chain with linked receipts at every hop (Approval Receipt, Certification Receipt, Semantic Model Receipt) so a business objective can be explained end-to-end by evidence, not just by data | G19-1, G19-2 | A single query/read-back walks Objective → Key Result → KPI → Data Product → Domain and returns a real receipt at every edge |
| G19-4 | **AI Instruction lifecycle completeness** — effective-date activation (`EffectiveDate` column + gating so an approved instruction doesn't take effect until its date) and a rollback workflow (revert to the prior certified version, itself going through the same approval gate) | G17-R3 | ✅ Done 2026-08-13 — A real AI instruction is approved with a future effective date, confirmed NOT active until that date; a real rollback request is approved and restores the prior certified text; see results below |
| G19-5 | **Data Product certification lifecycle** — certify/de-certify/expiration-review, distinct from Publish (already proven) | G16 (P4), G19-2 | ✅ Done 2026-08-13 — A published data product is separately certified (new `request_type`, `DataProductCertification`), with a real expiration date and a real de-certification example; see results below |
| G19-6 | **Discovery-to-ontology loop (G18 completion)** — extend G18-A's discovery→classify→approve chain with a CDE mapping step and an ontology mapping step (link the approved table/column to a real ontology node — Domain/Data Product/OKR — not just a domain tag) before actual semantic-model promotion (real SemPy Labs TOM mutation, not just a SQL-side receipt) | G18-A | ✅ Done 2026-08-13 — An approved G18-A object (`vw_technician_utilization_summary`) resolves to a real ontology node, is actually added to the semantic model, and is read back — matching the `nb_13`/`nb_16` apply+validate pattern; see results below |
| G19-7 | **First-class governance receipts** — promote domain-publish and Purview-scan-completion events from "missing" to typed receipts: Domain Publish Receipt (Published→Read Back→Validated), Purview Scan Receipt (Started→Completed→Assets Discovered→Read Back), Objective Approval Receipt (Approved→Ontology Updated→Relationships Validated) | G19-1, G17 ledger | ✅ Satisfied 2026-08-13 — G20's `DomainPublication` (x3) and `ScanCompletion` (x2) receipts already give every domain and every real scan run a queryable, typed receipt in the unified ledger, meeting this criterion literally. The richer multi-stage breakdown (separate Started/Completed/AssetsDiscovered/ReadBack events) is deliberately NOT built — Domains and Scans are pre-assumed data-model elements, not stakeholder-tied demo moments (same 2026-08-13 scope decision as G20) |
| G19-8 | **Autonomous governance (G13-5)** — scheduled/triggered automation of the full chain (proposal → approval → propagation → validation → receipt → reconciliation) without a human manually triggering each notebook run | All of the above | ⛔ Descoped 2026-08-13 by explicit user direction — "the trigger is not needed now, we only need to support the demo." Replaced with `nb_18_demo_reset` (see below): a reusable notebook that resets G19's demo requests back to pre-decision status so the live approval narrative can be re-demoed indefinitely, instead of automating a production-style schedule nobody asked for |

**Recommended priority (executive-demo framing, supersedes the original cheapest-first
sequencing):**

1. **G19-1 + G19-3** — Objective-level ontology governance, certification, and approval
   receipts. This is the highest-value change: it turns the OKR/ontology layer from "just
   linked data" into a governed business-reasoning graph, which is the strongest differentiator
   for Enercare/Brookfield and future agent experiences.
2. **G19-4** — AI Instruction lifecycle (effective dates, rollback).
3. **G19-5** — Data Product certification lifecycle.
4. **G19-6** — G18 semantic-model promotion (larger; real TMDL mutation).
5. **G19-2 + G19-7** — generalize the certification state machine and receipt types once at
   least two real object types have proven the pattern in 1-3 above (avoids over-building an
   abstraction before it has real usages).
6. **G19-8** — scheduled automation, last, matching G17's own R6-last precedent (self-healing
   was proven manually before it was worth automating).

---

## G20 — Close Remaining Ungated Deployed Governance Objects (stale-element audit)

**Priority:** P2
**Status:** ✅ Done 2026-08-13
**Origin:** Before starting G19's deeper lifecycle-maturity work, the user asked for an
inventory of every currently-deployed governance object to confirm none were "stale" —
deployed with no workflow or approval gate defined and tested at all.

**Explicit scope decision (user direction, 2026-08-13):** not every governed object needs a
full interactive approval workflow. Only the core demo functions tied to a specific
stakeholder moment (P1-P4, G13, G14, G17-R3/R4, G18-A) warrant that investment. Objects that
are pre-assumed/foundational parts of the data model are satisfied with a lightweight,
honestly-labeled **synthetic/attested** governance record — same pattern as G17-R5's
`RoleAssignment` backfill — not a new interactive workflow, notebook, or UI.

### Audit method

Queried `dbo.governance_requests` live against every deployed governance object table
(`governance_domains`, `governance_data_products`, `governance_okrs`,
`governance_okr_key_results`, `governance_cdes`, `governance_glossary_terms`,
`governance_role_assignments`) to find any category with **zero** gated instance of any kind
(not just "fewer than ideal" — genuinely never gated once).

| Category | Live count | Gated instances (before G20) | Verdict |
|---|---|---|---|
| Governance Domains | 3 | 0 | 🔴 Stale — no domain-level gate existed |
| OKR Objectives | 3 | 0 | 🔴 Stale — only child Key Results could be gated (1/6 KRs was, via G17-R4) |
| Data Product Certification (concept) | 3 products | 0 | 🔴 Stale — no `request_type` for certification existed for any product |
| `DP-BILLHEALTH` specifically | 1 product | 0 | 🔴 Stale — the only data product with zero governance trail of any kind |
| Purview Scan completion | n/a | 0 | 🔴 Stale — no receipt/gate concept existed |
| Glossary Terms, CDEs, AI Instructions, Verified Answers, KPIs, Role Assignments, G18-A source objects | various | ≥1 each | 🟢 Already meets the G17-R4 "at least one real gated demo object" bar — not stale |

### Resolution

`sql/23_g20_synthetic_governance_attestation.sql` (idempotent, same 3-table insert shape as
`sql/17`) added 11 real attested records, all grounded in already-true live facts (real
domain/OKR/data-product owners queried directly from `dbo.governance_domains`/
`governance_okrs`/`governance_data_products`; real Purview scan run outcomes from repo
memory) — nothing fabricated:

| request_type | Rows | Coverage |
|---|---|---|
| `DomainPublication` | 3 | All 3 domains (DOM-CUSTOPS, DOM-SVCDEL, DOM-REVCON) |
| `ObjectiveApproval` | 3 | All 3 OKR Objectives (distinct from the existing Key Result gate) |
| `DataProductCertification` | 3 | All 3 data products, including `DP-BILLHEALTH` (closes its total-zero-coverage gap) |
| `ScanCompletion` | 2 | `enercareFabricScan` (real run `0164ff32-3a06-4db7-b97c-410bb09aa690`) and `enercareSqlScan` |

Each record has a full `governance_requests` → `governance_events` → `governance_target_receipts`
chain, `current_status='Completed'`, receipt type `OperatorAttested<RequestType>`,
`validation_status='Passed'`, and an evidence payload explicitly labeled as a 2026-08-13
scope-decision synthetic attestation (not a live interactive workflow decision) — same honesty
convention as every other attested (vs. machine-verified) receipt in this repo. Live-verified via
`SELECT request_type, COUNT(*) FROM dbo.governance_requests GROUP BY request_type` showing all
4 new types present with the expected row counts (15 total distinct request types now covered,
up from 11).

This closes the stale-element audit. **G19's deeper lifecycle-maturity work (Objective
certification/recertification/ownership validation/drift detection, full certification state
machine, evidence graphs, etc.) is unaffected and remains the next real build** — G20 only
guarantees every deployed object category has at least one real gate to build on top of.

### G19-1 + G19-3 results (closed 2026-08-13)

`sql/24_g19_ontology_governance_completeness.sql` (idempotent, same battle-tested pattern as
`sql/18`/`sql/21`) built the full Objective-level governance lifecycle for real, distinct from
G20's synthetic attestation:

| Item | Result |
|---|---|
| Schema | `dbo.governance_okrs` extended with `is_certified`, `certified_by`, `certified_date`, `recertification_due`, `retired_at`, `retired_by`, `retirement_reason` — kept as direct columns (not a generic reusable table; that generalization is G19-2, deliberately deferred until proven on a 2nd object type) |
| Real edit-approval cycle | `OBJEDIT-SVCDEL-SLA-001` — `OKR-SVCDEL-SLA`'s `target_date` extended 2026-12-31 → 2027-06-30 via a real Draft→Submitted→Approved→Applied cycle (requester Ranbir Singh, approver Ci Zhu), `governed_object_versions` snapshot + `SqlApplyReadback` receipt Passed — distinct from G20's attestation and from the Key Result gate (G17-R4) |
| Certification | `OBJCERT-SVCDEL-SLA-001` — `OKR-SVCDEL-SLA` certified (requester Shruthi Srinivas, approver Ci Zhu), `recertification_due` deliberately backdated 30 days to prove the recert path for real |
| Recertification | `OBJRECERT-SVCDEL-SLA-001` — only proceeds if genuinely past-due (guarded check); recertified with `recertification_due` extended to 2027-02-09, `ObjectiveRecertificationReadback` receipt Passed |
| Ownership validation | 3 real, **machine-verified** (not attested) checks — `owner_upn` confirmed against `dbo.governance_domains.governance_domain_owners` via `STRING_SPLIT` for all 3 real Objectives, all `Passed` |
| Drift detection | 3 real, **machine-verified** checks — each Objective's linked Data Product confirmed to still exist and still belong to the Objective's own domain, all `Passed` |
| Retirement workflow | New demo Objective `OKR-CUSTOPS-LEGACY-NPS` (a Net Promoter Score objective superseded by `OKR-CUSTOPS-CX`'s CSAT/FCR measures) created via a real gate (`OBJAPPR-CUSTOPS-LEGACY-NPS-001`) then retired via a real gate (`OBJRETIRE-CUSTOPS-LEGACY-NPS-001`) — proves the full lifecycle without touching any of the 3 real production Objectives |
| Ontology evidence graph (G19-3) | `dbo.vw_ontology_evidence_graph` walks Objective → Key Result → Data Product → Domain, surfacing the real receipt/status at every edge (KPI-level evidence already exists separately via `KpiApproval` receipts in the Lakehouse tier, out of scope for a SQL-native view) |

All live-verified via direct SQL read-back: `OKR-SVCDEL-SLA` shows `target_date=2027-06-30,
is_certified=1, certified_by=Ci.Zhu@enercare.ca, recertification_due=2027-02-09`;
`OKR-CUSTOPS-LEGACY-NPS` shows `status=Retired, retired_at=<timestamp>`; the other 2 real
Objectives (`OKR-CUSTOPS-CX`, `OKR-REVCON-RETAIN`) are untouched; all 14 new receipts
(`SqlApplyReadback` x2, `ObjectiveCertificationReadback`, `ObjectiveRecertificationReadback`,
`ObjectiveRetirementReadback`, `OwnershipValidationReadback` x3, `DriftDetectionReadback` x3,
plus the pre-existing `OperatorAttestedObjectiveApproval` x3 from G20) show `validation_status='Passed'`.

### G19-4 results (closed 2026-08-13)

Extended `nb_11_gated_governance_sync` (same existing AI Instruction gate GCR-AII-001 already
proved, not a new/parallel workflow) with effective-date activation and a rollback handler:

| Item | Result |
|---|---|
| Schema | `lh_metadata.ai_metadata` extended with `EffectiveDate`, `IsRolledBack`, `RolledBackFromRecordID`, `RollbackReason` (idempotent `ALTER TABLE ADD COLUMNS`, guarded by column-existence check) |
| Effective-date activation | `GCR-AII-002` — new "Winter Weather Delay Communication" instruction certified with `EffectiveDate` 14 days out (2026-08-27); confirmed live it is NOT active yet (real future date stored, not backdated) |
| Rollback | `GCR-AII-003` — a flawed edit to the existing "escalation" instruction (Shruthi Srinivas requester, Ci Zhu approver) that unintentionally dropped the safety/emergency escalation clause, a real governance risk; `GCR-AII-004` — Ranbir Singh catches it and requests rollback, approved by Ci Zhu. `apply_ai_instruction_rollback` dynamically resolves the currently-active certified row and the version immediately before it (no hardcoded RecordID) |
| Live result | The flawed row is superseded (`IsCertified=0`) and a new row reverts to the original safety-clause-inclusive text, `IsRolledBack=1`, `RolledBackFromRecordID` pointing at the superseded row |

**Real incident hit and fixed during this build:** the first `nb_11` run executed before the git
sync had actually landed (`updateFromGit` failed with `MissingWorkspaceConflictResolution` — the
fix was adding `conflictResolution: {conflictResolutionType: "Workspace", conflictResolutionPolicy:
"PreferRemote"}` to the request body, a new gotcha beyond the previously-documented
`allowOverrideItems` fix). That first run silently executed the OLD pre-G19-4 code, which
appended 2 orphan duplicate rows (RecordID 41 `weather_delay`, RecordID 42 `escalation`, both
missing the new lifecycle columns) before failing on the unknown `AI_INSTRUCTION_ROLLBACK`
request_type and rolling back only the SQL-side `applied_at` stamps (Delta appends are
independent commits, not part of that transaction). After fixing the sync and re-running
cleanly, the rollback's "prior version" lookup was contaminated by orphan RecordID 42 (picked
as "immediately prior" instead of the true original RecordID 40), reverting to the wrong
(still-flawed) text. Fixed via a disposable temp notebook (created, run, deleted per standard
hygiene) that deleted the 2 orphan rows and corrected the rollback row's text to the true
original. Final state independently re-verified via OneLake debug-file fetch: 4 clean rows
(`RecordID 40` original, `44` superseded flawed edit, `45` correct rollback with the full
safety-clause text restored, `43` the future-dated weather instruction) — no orphans remain.

### G19-5 results (closed 2026-08-13)

`sql/26_g19_data_product_certification_lifecycle.sql` (idempotent, same pattern as `sql/24`)
built the REAL Data Product certification lifecycle, distinct from G20's synthetic attestation
and from Publish/Access (already proven in P4/P3):

| Item | Result |
|---|---|
| Schema | `dbo.governance_data_products` extended with `is_certified`, `certified_by`, `certified_date`, `expiration_date`, `decertified_at`, `decertified_by`, `decertification_reason` (direct columns, same deliberate non-generalization as G19-1) |
| Real certification | `DPCERT-SVCPERF-002` — `DP-SVCPERF` certified (Shruthi Srinivas requester, Ci Zhu approver), `expiration_date` deliberately backdated 30 days to prove the expiration-review path for real |
| Expiration review | `DPCERTREVIEW-SVCPERF-001` — only proceeds if genuinely past-due (guarded check); renewed `expiration_date` to 2027-08-13 (+365 days) |
| De-certification | New demo data product `DP-LEGACY-CALLCENTER-IVR` (legacy IVR analytics, superseded by `DP-CUST360`) created via a real gate (`DPAPPR-LEGACY-IVR-001`), certified (`DPCERT-LEGACY-IVR-001`), then de-certified for a real reason (`DPDECERT-LEGACY-IVR-001`, `status='Retired'`) — proves the full lifecycle without touching any of the 3 real production data products |

Live-verified: `DP-SVCPERF` shows `is_certified=1, certified_by=Ci.Zhu@enercare.ca,
expiration_date=2027-08-13`; `DP-LEGACY-CALLCENTER-IVR` shows `is_certified=0, status=Retired,
decertified_at=<timestamp>`; `DP-CUST360`/`DP-BILLHEALTH` untouched; all 5 new receipts
(`SqlApplyReadback`, `DataProductCertificationReadback` x2, `DataProductExpirationReviewReadback`,
`DataProductDecertificationReadback`) plus the pre-existing 3 `OperatorAttestedDataProductCertification`
receipts from G20 show `validation_status='Passed'`.

---

### G19-6 results (closed 2026-08-13)

Completed G18's discovery→classify→approve→CDE/ontology-map→promote chain via `sql/27`, `sql/28`,
and a new `nb_17_g18_semantic_promotion` notebook:

| Item | Result |
|---|---|
| CDE mapping | `CDEMAP-CONTRACT-RENEWAL-001` — `vw_contract_renewal_pipeline` (G18-A's genuinely-pending 3rd demo object) mapped to `CDE-CONTRACT-ID` (a real fit — the view selects `contract_id`). This CDE backing then justified finally deciding the pending object: `TAG-D0BF6E496681E6B0` **Approved** (Ci Zhu), giving all 3 original G18-A demo objects a real terminal state |
| Ontology mapping | `ONTOMAP-TECHUTIL-001` — `vw_technician_utilization_summary` (already Approved/Completed via G18-A) mapped to the real Key Result `KR-TECH-UTIL`, which it was literally built to serve (not a contrived link) |
| Semantic model promotion | `nb_17_g18_semantic_promotion` added a REAL new measure `fct_service_request[Technician Utilization Rate]` (DAX: `DIVIDE(DISTINCTCOUNT(fct_service_request[TechnicianId]), COUNTROWS(fct_service_request))`) to the live `BrookfieldEnercare` semantic model via SemPy Labs TOM — an actual TMDL mutation, not just a SQL-side receipt — with annotations (`SourceObject_References`, `KeyResult_Id`, `Governance_Request_Id`), then read back read-only and receipted (`SemanticModelReadback`, Passed) |

**Real bug found and fixed during this build:** `nb_17` failed repeatedly with a generic
`System_Cancelled_Session_Statements_Failed` error across three different notebook shapes
(multi-cell, single flattened cell, single flattened cell with a pip-install fallback) before a
targeted debug-wrapped diagnostic surfaced the real Python traceback:
`ModuleNotFoundError: No module named 'Microsoft'`. Root cause: `Microsoft.AnalysisServices.Tabular`
(the .NET/CLR interop module SemPy Labs TOM exposes) is only importable **after**
`connect_semantic_model` has been entered at least once in that session — it bootstraps the CLR
bridge on first use. The `from Microsoft.AnalysisServices.Tabular import Measure as TomMeasure`
import was written BEFORE the `with connect_semantic_model(...)` block instead of inside it
(nb_16's equivalent `Annotation` import is correctly nested inside `upsert_annotation`, which is
only ever called from within an already-active session — that's why nb_16 never hit this).
Fix: move the import inside the active `with` block. General lesson for any future SemPy Labs
TOM code: never import `Microsoft.AnalysisServices.Tabular.*` types at module/cell top level or
before any `connect_semantic_model` call in that session — always import them from inside an
active session context.

Live-verified: `SEMPROMO-TECHUTIL-001` shows `current_status=Completed`; the
`SemanticModelReadback` receipt on `fct_service_request.Technician Utilization Rate` shows
`validation_status=Passed`; the new measure is confirmed present in the git-committed TMDL
(`fabric/BrookfieldEnercare.SemanticModel/definition/tables/fct_service_request.tmdl`) after a
`commitToGit` sync back from the live workspace.

### Demo repeatability — `nb_18_demo_reset` (added 2026-08-13)

G19-8 (scheduled automation) was explicitly descoped by the user — "the trigger is not needed
now, we only need to support the demo." In its place: a reusable reset notebook so the entire
G19 approval narrative can be re-demoed live, indefinitely, without re-running any SQL setup
scripts.

**Scope decisions (explicit user direction):** this is about request STATUS, not deleting
anything — no governed object row is ever deleted. The two disposable demo objects
(`OKR-CUSTOPS-LEGACY-NPS`, `DP-LEGACY-CALLCENTER-IVR`) keep their CREATE decision applied (the
object keeps existing); only their later decisions (Certify, Retire/Decertify) reset, so a
presenter can re-demo "certify it, then retire it" repeatedly without recreating the object each
time. The 2 real production objects touched this session (`OKR-SVCDEL-SLA`, `DP-SVCPERF`) reset
fully to their true pre-G19 baseline.

`fabric/nb_18_demo_reset.Notebook` (DEMO_MODE=True by default, matching every other notebook's
safe-default convention) resets, in one run:

| Scope | Action |
|---|---|
| G19-1 (`OBJEDIT`/`OBJCERT`/`OBJRECERT`-SVCDEL-SLA, `OBJRETIRE`-CUSTOPS-LEGACY-NPS) | `governance_requests.current_status` back to `Submitted`; `governance_okrs` fields (`target_date`, `is_certified`, `certified_by`, `certified_date`, `recertification_due`, retirement fields) reverted |
| G19-5 (`DPCERT`/`DPCERTREVIEW`-SVCPERF, `DPCERT`/`DPDECERT`-LEGACY-IVR) | Same pattern on `governance_data_products` |
| G18-A / G19-6 (`TAG-D0BF6E496681E6B0`, `CDEMAP-CONTRACT-RENEWAL-001`, `ONTOMAP-TECHUTIL-001`) | Reset to `Submitted`; `SEMPROMO-TECHUTIL-001` reset to `Approved` (it's a system gate, not a steward-click moment) |
| Semantic model | Removes the `Technician Utilization Rate` measure entirely so `nb_17` can recreate it fresh |
| G19-4 (`GCR-AII-002/003/004`, legacy table) | Reset to `PendingApproval`; `ai_metadata` demo rows deleted, keeping only the original baseline row (`RecordID 40`) |

Every reset also deletes the `Decided`/`Applied` `governance_events`, `governed_object_versions`,
and `governance_target_receipts` rows tied to that request, so the ledger looks freshly
pre-decision, not just status-flipped. Live-tested in `DEMO_MODE=True` (preview, no writes) —
confirmed the notebook runs cleanly end-to-end. Re-demoing after a live reset requires flipping
each request back to `Approved` (a small SQL `UPDATE`, or the live Purview/portal workflow where
one exists) and re-running the matching apply step (`nb_11` for AI Instructions, `nb_17` for the
semantic promotion); the original `sql/24`/`sql/26`/`sql/27` build scripts will NOT reapply a
reset request since they're guarded by request_id existence, not status.

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
- `fabric/nb_09_purview_labels_lineage.Notebook/`

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

1. ✅ **Maria scenario passes end-to-end** — Tom's call, Victoria's review, and Ci Zhu's audit all run from the same governed surface with same definitions and no manual reconciliation. (`docs/purview-maria-north-star-scenario.md` §8 enumerates the 8 acceptance criteria.)
2. ✅ Synthetic Enercare source data exists in Azure SQL in sub2 with Luhn-valid SINs and the 6 new tables.
3. ✅ Fabric mirrors that SQL source into sub1.
4. ✅ `BrookfieldEnercare` semantic model carries curated descriptions, CDE annotations, and AI grounding content.
5. ✅ Purview in sub3 has scanned both SQL and Fabric assets, with the custom SIN SIT in the active rule set.
6. ✅ Purview Unified Catalog displays 3 published domains, 3 published data products, 35+ glossary terms, 12 CDEs, 4 sensitivity labels.
7. ✅ At least one validated lineage chain (Net Revenue or FCR) shows the SQL → mirror → SM → report path. **8 lineage edges published 2026-06-18.**
8. ✅ The Fabric JDBC smoke-test continues to validate private connectivity.

**Demo Closure Status (2026-06-18):** All acceptance criteria met. Demo ready to publish.

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


