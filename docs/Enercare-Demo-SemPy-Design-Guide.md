# Enercare Demo — SemPy / SemPy Labs Design Guide

**Purpose:** Capture Alison Pouw's recommended metadata pipeline pattern and translate it into a step-by-step implementation guide for the Enercare demo.

**Source:** Teams thread with Alison Pouw, April–May 2026.

---

## 1. What Alison Is Actually Asking For

Across the thread, Alison is consistently pointing at a **simpler pattern than the one currently scoped in the demo**. Two of her statements are load-bearing:

> "From my understanding they would just need to read the current report metadata using SemPy and then write it using SemPy Labs. To get it to Purview they can just scan the semantic models and get the data to Fabric." — *Alison, 2026-05-18*

> "Not the latter — to scan the SM in Fabric." — *Alison, 2026-05-18 (clarifying that Purview scans the Fabric semantic models, not the SQL-side models)*

In other words: **drop the JDBC-to-SQL / `sys.extended_properties` step from the original design.** Enercare isn't populating `sys.extended_properties` today, so there's nothing to read on that side. The metadata authority becomes the **Fabric semantic model itself**, and Purview is the downstream governance catalog.

This is a meaningful simplification of the earlier flow that included the JDBC bridge.

---

## 2. The Pattern in One Sentence

**SemPy reads current report/model metadata → enrich it in a notebook → SemPy Labs writes it back into the Fabric semantic model → Purview scans the Fabric semantic model → gold-layer data products feed the ontologies that Data Agents sit on top of.**

---

## 3. ASCII Flow

```
                                         ┌──────────────────────────────┐
                                         │  Fabric Lakehouse (Gold)     │
                                         │  - curated tables            │
                                         │  - business metadata staged  │
                                         │    in lh_metadata            │
                                         └──────────────┬───────────────┘
                                                        │ bulk load: table + column defs
                                                        ▼
   ┌──────────────────────────┐    read     ┌──────────────────────────────┐
   │  Existing Power BI       │ ──────────▶ │   Fabric Notebook            │
   │  Semantic Model(s)       │   SemPy     │   - SemPy: read report &     │
   │  (in Fabric workspace)   │             │     model metadata           │
   └──────────────────────────┘             │   - merge with curated       │
              ▲                             │     business metadata        │
              │                             │   - apply descriptions,      │
              │  write back                 │     synonyms, AI instr.,     │
              │  SemPy Labs                 │     verified answers         │
              └─────────────────────────────┤                              │
                                            └──────────────┬───────────────┘
                                                           │ Purview scan
                                                           ▼
                                            ┌──────────────────────────────┐
                                            │  Microsoft Purview           │
                                            │  - catalog & glossary        │
                                            │  - lineage                   │
                                            │  - classification / labels   │
                                            └──────────────┬───────────────┘
                                                           │ published metadata
                                                           ▼
                                            ┌──────────────────────────────┐
                                            │  Gold Data Products          │
                                            │  → Ontologies                │
                                            │  → Data Agents / Copilot     │
                                            └──────────────────────────────┘
```

---

## 4. What Changed From The Original Design

| Original demo step | Status | Reason (per Alison) |
|---|---|---|
| JDBC connection from notebook to mirrored SQL DB | **Remove** | Enercare isn't using `sys.extended_properties`, so there's nothing meaningful to pull. |
| Read `sys.extended_properties` for source metadata | **Remove** | Same — no data there today. |
| SQL Mirror as the metadata source of record | **De-emphasize** | The Fabric semantic model is the runtime metadata surface. SQL Mirror remains for *data*, not metadata. |
| SemPy reads existing Power BI report/model metadata | **Keep — make central** | This is the starting point of Alison's pattern. |
| SemPy Labs writes enriched metadata back to the model | **Keep — make central** | This is the write-back loop she's calling for. |
| Purview scan against **SQL** | **Replace** | Purview scans the **Fabric semantic models**, not SQL. |
| Purview scan against **Fabric semantic models** | **Add** | Confirmed by Alison's "not the latter — to scan the SM in Fabric." |
| Gold layer feeds ontologies → data agents | **Add / make explicit** | From her AI-readiness comments on 2026-05-13. |

---

## 5. Implementation Steps for the Demo

### Step 1 — Stage curated metadata in the Lakehouse (`lh_metadata`)
Keep the existing `lh_metadata` working store. This is the workshop where you assemble:
- Technical metadata (extracted from model + lakehouse)
- Business metadata (KPI definitions, descriptions, glossary terms)
- Stewardship metadata (`owner`, `steward`, `IsDraft`, `IsCertified`)
- AI-facing metadata (AI instructions, verified Q&A)

Bulk-load initial table and column definitions from the lakehouse — this is what Alison meant by *"those definitions can be a bulk load from a lh in fabric like you have."*

### Step 2 — Read current semantic model metadata with SemPy
In a Fabric notebook, use `semantic-link` (SemPy) to read what's already in the Power BI semantic model:

```python
import sempy.fabric as fabric

# Inventory existing model objects
tables   = fabric.list_tables(dataset="EnercareModel")
columns  = fabric.list_columns(dataset="EnercareModel")
measures = fabric.list_measures(dataset="EnercareModel")

# Read existing descriptions/annotations so we don't overwrite curated content
existing = fabric.evaluate_dax(
    dataset="EnercareModel",
    dax_string="EVALUATE INFO.MEASURES()"
)
```

This is the "current report metadata" Alison referenced.

### Step 3 — Merge curated `lh_metadata` with what SemPy read
In the same notebook, join the SemPy-read inventory against your `lh_metadata` tables. Output is a single enriched DataFrame containing, per object:
- Object identity (table / column / measure name)
- Curated business description
- Synonyms
- Owner / steward
- Certification state
- AI instructions and verified-answer references

### Step 4 — Write back to the semantic model with SemPy Labs
Use `sempy-labs` (the extended labs package — `pip install semantic-link-labs`) for the operations SemPy core doesn't cover:

```python
import sempy_labs as labs

# Push descriptions, synonyms, and Prep for AI configurations
labs.set_object_description(dataset="EnercareModel",
                            object_type="Measure",
                            object_name="Net Revenue",
                            description="Revenue after returns and credits...")

labs.set_synonyms(dataset="EnercareModel",
                  object_name="Net Revenue",
                  synonyms=["net sales", "revenue net"])

# Verified answers + AI instructions land via TMDL/Prep-for-AI surfaces
labs.update_tmdl(...)
```

Key point Alison made: this write-back is what makes the metadata real. Curated metadata in `lh_metadata` is useful, but **Copilot and Data Agents read from the semantic model, not from the lakehouse**. The SemPy Labs write step is what gets the work onto the runtime surface.

### Step 5 — Promote and label the model in Fabric
Before scanning, set the Fabric-side governance bits Alison called out as part of "AI-ready":
- Apply **sensitivity labels** to the semantic model
- Mark the model as **Promoted** or **Certified** (endorsement)
- Confirm **DQ rules** are running against the gold tables
- Confirm **medallion** flow: bronze → silver → **gold** (gold is what the model and ontologies should read from)

### Step 6 — Scan the Fabric semantic model with Purview
Register the Fabric tenant in Purview and run a scan against the **semantic models in Fabric** (not against SQL — this was the explicit correction). Purview then becomes:
- The catalog (discoverability across systems)
- The glossary publication target
- The lineage view (model → lakehouse → source)
- The published governance system of record

### Step 7 — Surface gold data products as ontologies for Data Agents
The last leg of Alison's "AI-ready" definition:

> *"leveraging medallion architecture and using the gold layer to feed ontologies which data agents sit on, making sure you have proper sensitivity labels and promoted items in fabric and proper governance and you're running DQ rules."*

In the demo, this means:
- Define one or more **gold data products** built on the curated gold tables
- Treat those as the ontology layer
- Point the **Fabric Data Agent** at the semantic model that sits over them
- The AI Data Schema + AI Instructions + Verified Answers from Step 4 are what give the agent its business context

---

## 5A. Current Notebook Construct (June 2026)

This is the active notebook construct in the repo today.

### Build and source stages

1. `nb_01_setup_demo_environment`
- Seeds the baseline demo tables in `lh_enercare_demo`.

2. `nb_05a_publish_synthetic_data_to_sql`
- Publishes the seven source tables to Azure SQL (`sqldemo`) and then executes SQL scripts `04`-`07` to extend/seed governance metadata in SQL.

3. Fabric mirror sync (operational step)
- Mirrors SQL objects into Fabric mirrored database surfaces (`sqldemo` / `sqldemo-mirror`).

4. `nb_03_pbi_star_schema`
- Rebuilds star schema from mirrored SQL source (or fallback to demo tables if explicitly enabled).

### Metadata and semantic-model stages

5. `nb_02_metadata_pipeline_demo`
- Builds `lh_metadata` metadata tables/views (`asset_metadata`, `column_metadata`, `kpi_metadata`, `vw_business_metadata_current`).

6. `nb_04a_extend_metadata_schema`
- Extends metadata schema (`ai_metadata`, `data_owners`, `lineage_edges`) and seeds curated KPI/AI metadata.

7. `nb_07a_ingest_customer_files`
- SQL-mirror-first ingestion of governance metadata into `lh_metadata.metadata.*`.

8. `nb_07b_merge_customer_metadata`
- Builds `lh_metadata.metadata.sm_annotations` from glossary/CDE/label/data-product mappings.

9. `nb_04_sempy_writeback` and `nb_05_push_qa_verified_answers`
- Writes curated descriptions/annotations/instructions into the semantic model via SemPy/SemPy Labs.

10. `nb_07_publish_to_purview`
- Prepares Purview domain and data-product payloads and is guarded for SQL-mirror-only runs unless explicitly overridden.

11. `nb_08_purview_glossary_cde`
- Publishes Phase 4/5 glossary and CDE payloads from `lh_metadata.metadata.glossary_terms` and `lh_metadata.metadata.cdes`.
- Writes dry-run artifacts to `/lakehouse/default/Files/purview_publish/phase_04_05_glossary_cde` and records validation in `metadata.purview_phase_04_05_validation`.

12. `nb_09_purview_labels_lineage`
- Builds Phase 6/7 sensitivity-classification type definitions, classification manifests, and SQL-to-Fabric lineage edge manifests.
- Writes dry-run artifacts to `/lakehouse/default/Files/purview_publish/phase_06_07_labels_lineage` and records validation in `metadata.purview_phase_06_07_validation`.

13. `nb_10_purview_stewardship_ai`
- Validates Phase 8-10 stewardship, certification, DLP readiness, and governed AI readiness.
- Writes closeout state to `metadata.purview_phase_08_stewardship_scorecard`, `metadata.purview_phase_09_controls_validation`, `metadata.purview_phase_10_ai_readiness_validation`, and `metadata.purview_phase_08_10_closeout`.

### Purview admin-ops family (`nb_06`)

- `nb_06a_create_sin_backstop` is active and intentional.
    - It registers the custom Purview SIT `ENERCARE.PRIVACY.SIN_BACKSTOP` and is part of Day 1 admin setup.

- `nb_06_purview_sql_grants` is not part of the current branch construct.
    - It existed in historical snapshots as a lineage/grants notebook (`CONTROL DATABASE`, `VIEW DATABASE STATE`, fallback principal grants), but was removed in the current design path.
    - This was not migrated as a first-class notebook in current branches.
    - The minimal surviving guidance is now in `nb_05b_test_sql_connectivity` (manual `CREATE USER ... FROM EXTERNAL PROVIDER` and `ALTER ROLE db_datareader ...` hints) plus runbook guidance.

### Why `nb_06_purview_sql_grants` was de-emphasized

- The demo moved to private-safe metadata scanning and custom lineage publication workflows rather than relying on the earlier SQL lineage-grant path as a mandatory runtime step.
- The semantic-model-first writeback and Fabric scan flow remains the primary implementation pattern.

For run-by-run validation of this construct, use `docs/build-evaluation-matrix.md`.

---

## 5B. Azure Purview Delivery Milestones

The open **Enercare Purview Governance Implementation Guide** is treated as the instruction set for the delivery model. The implementation is staged so every milestone has three outputs: a governance decision, a code artifact where applicable, and a validation gate before continuing.

### Milestone 1 — Platform registration and scans

**Governance outcome:** SQL and Fabric are registered in Purview with repeatable scans.

**Code and configuration artifacts:**
- Purview portal/MCP registration for Azure SQL and Fabric tenant/workspace scope.
- Existing SQL/Fabric validation notebooks: `nb_05b_test_sql_connectivity`, `nb_07a_ingest_customer_files`.

**Validation gate:** SQL assets and Fabric workspace assets are searchable in Data Map / Unified Catalog; scan history has no credential or connectivity failures.

### Milestone 2 — Governance foundation and data products

**Governance outcome:** Domains, data products, owners, stewards, and initial product descriptions exist.

**Code artifacts:**
- `sql/06_purview_metadata_schema.sql` creates the SQL-first governance metadata model.
- `sql/07_seed_purview_metadata.sql` seeds baseline domain/product/glossary/CDE/role/label data.
- `nb_07_publish_to_purview` prepares and optionally publishes Purview Atlas entities for domains and data products.

**Validation gate:** `nb_07_publish_to_purview` produces domain/data-product payloads and summary counts; at least three data products are attached to real scanned assets.

### Milestone 3 — Glossary and critical data elements

**Governance outcome:** Business glossary terms and CDEs are created, linked to domains, and bound to SQL/Fabric/Semantic assets where supported.

**Code artifacts:**
- `purview/glossary-master.csv` and `purview/cde-catalog.csv` remain the customer-facing governance seed files.
- `nb_08_purview_glossary_cde` validates staged metadata, generates Atlas typedefs, creates CDE entities, and prepares glossary term payloads.

**Validation gate:** `metadata.purview_phase_04_05_validation` shows PASS for source rows, glossary payloads, and CDE entities. Dry-run JSON artifacts exist under `Files/purview_publish/phase_04_05_glossary_cde`.

### Milestone 4 — Classification, sensitivity, and lineage

**Governance outcome:** Sensitive assets have a consistent label/classification model, and the SQL to Fabric to semantic lineage story has a native-or-custom path.

**Code artifacts:**
- `purview/label-policy.csv` defines the sensitivity hierarchy and assignment rules.
- `nb_09_purview_labels_lineage` emits Atlas classification typedefs, classification manifests, and deterministic SQL-to-Fabric lineage edge manifests.

**Validation gate:** `metadata.purview_phase_06_07_validation` shows PASS for classification definitions and assignment manifests. Lineage rows may be WARN until asset GUID resolution or native Purview lineage is available.

### Milestone 5 — Stewardship, certification, controls, and AI readiness

**Governance outcome:** Products and critical assets have trust indicators, DLP/control decisions, and AI-facing metadata completeness checks.

**Code artifacts:**
- `nb_07b_merge_customer_metadata` creates the semantic annotation plan from glossary/CDE/label/product mappings.
- `nb_04_sempy_writeback` and `nb_05_push_qa_verified_answers` push governed metadata into the semantic model.
- `nb_10_purview_stewardship_ai` validates owner/steward/certification status, DLP readiness, and AI-readiness prerequisites.

**Validation gate:** `metadata.purview_phase_08_10_closeout` has zero `ACTION_REQUIRED` rows before the governance demo is marked ready. Any DLP mode must be explicitly selected as alert-only, policy tip, or block before a live run.

### Operating rule for live Purview writes

All Purview notebooks are dry-run first. Live API calls require `APPLY_CHANGES=True` and, where the SQL-mirror-only guard is active, `PURVIEW_PUBLISH_OVERRIDE=True`. This protects the current deployment path while still producing reviewable payloads after every stage.

---

## 5C. Phase 3 — AI Enrichment Design Pattern (Call Center North Star)

### Phase framing

- **Phase 1 (completed):** Infrastructure and architecture.
- **Phase 2 (completed):** Semantic modeling and baseline metadata surfaces.
- **Phase 3 (new):** AI enrichment for call-center outcomes, using Maria Castellanos as the northstar business case.

The objective of Phase 3 is to move from generic annotation coverage to **use-case-valid annotation quality**: KPIs, Verified Answers, and AI Instructions that are explicitly ordered and authored for Tom-style in-call decisions.

### North-star business contract (Maria)

The runtime behavior for this phase is anchored to this minimum scenario:

1. Agent can profile customer state quickly: identity, account, consent, equipment, active service request, contract, billing, and complaint history.
2. Agent can detect and explain SLA breach context for no-heat and missed dispatch.
3. Agent can apply business-rule recommendations in order: immediate operational recovery first, then financial remediation.
4. Agent can issue recommendation for credit where rules are satisfied (for example, SLA breach + active billing during no-heat + not a repeat complainer).
5. Copilot/Data Agent responses remain deterministic by priority ordering and certified metadata state.

### Phase 3 milestones and closure proofs

#### Milestone P3-1 — Source-readiness and coverage review

**Goal:** verify each source domain has enough row-level evidence to support the intended AI annotations.

**Required review scope:**
- Fact tables, dimensions, and production measures in the `BrookfieldEnercare` model.
- Core scenario slices: Customer, Financials (billing/contracts/revenue), Service Records, Equipment, Call History.

**Execution pattern:**
1. Read each row cohort relevant to Maria and adjacent cohorts (non-Maria controls).
2. Map each candidate KPI/VA/AI Instruction to its source columns and measure lineage.
3. Flag unsupported annotation intents as `BACKFIT_REQUIRED`.

**Approval proof to close P3-1:**
- A traceability matrix exists with one row per annotation intent and columns for source support, gaps, and backfit owner.
- No high-priority call-center intent remains unclassified (`SUPPORTED` or `BACKFIT_REQUIRED`).

#### Milestone P3-2 — Industry-lexicon KPI design

**Goal:** define KPI semantics in call-center and home-service industry language.

**Design rules:**
1. KPI names and descriptions must be conversant for call-center users (not only technical model terms).
2. KPI definitions must resolve to a single semantic-model measure path.
3. KPI business language must align to glossary terms used in the Maria scenario.

**Approval proof to close P3-2:**
- KPI set is reviewed with domain owner/steward and tagged as `CERTIFIED_FOR_AGENT_USE` in the curation workflow.
- Every KPI used by AI Instructions has a bound measure and glossary linkage.

#### Milestone P3-3 — Verified Answers pack for call-agent prompts

**Goal:** produce verified answers from actual data states that match high-frequency support intents.

**Priority intents baseline:**
1. `no-heat`
2. `missed appointment` / `no-show`
3. `billing while unresolved outage`
4. `credit eligibility`
5. `repeat complaint risk`

**Design rules:**
1. Verified answers must be derived from data, not only template prose.
2. Each answer must contain explicit condition logic and recommended action path.
3. Sort order must support in-call triage: current customer state before generalized policy text.

**Approval proof to close P3-3:**
- Verified-answer payload is generated and versioned from current metadata tables.
- Smoke prompts in notebook/test harness return expected answer class for all baseline intents.

#### Milestone P3-4 — AI Instructions ordering and recommendation policy

**Goal:** enforce deterministic instruction order for call-agent screen needs and recommendation logic.

**Ordering policy (top to bottom):**
1. Identity and customer state snapshot
2. Service urgency and SLA condition
3. Financial exposure (billing/contracts/revenue context)
4. Complaint history and repeat-risk status
5. Recommendation block (actions, credits, escalation)

**Maria decision rule baseline:**
- If active `no-heat` + SLA breach + billing is active during unresolved service window + no repeat-complaint pattern, recommend credit and dispatch escalation.

**Approval proof to close P3-4:**
- Annotation ordering is validated in both draft and published Data Agent surfaces.
- Manual test run for Maria returns policy-aligned recommendation in expected order.

#### Milestone P3-5 — Backfit sprint for annotation-data gaps

**Goal:** close data gaps discovered in P3-1 so AI annotations are fully evidence-backed.

**Backfit scope examples:**
- Missing service-call attributes needed to determine no-show causality.
- Missing complaint recurrence markers for repeat-complaint logic.
- Missing billing-state attributes tied to unresolved outage intervals.

**Approval proof to close P3-5:**
- All `BACKFIT_REQUIRED` items are either implemented or explicitly deferred with owner/date/risk.
- No high-severity annotation remains without data support.

#### Milestone P3-6 — Phase 3 closeout gate

**Goal:** certify that the call-center AI enrichment pattern is demo-ready and governance-ready.

**Closure checks:**
1. Maria northstar run passes end-to-end for customer profile, service state, financial context, and recommendation output.
2. KPI, Verified Answers, and AI Instructions are traceable to source data and semantic measures.
3. Annotation sort order is stable and deterministic in runtime surfaces.
4. Outstanding gap log contains no unresolved blocking item.

**Approval proof to close P3-6:**
- A short sign-off record is captured with Domain Owner + Data Steward + Demo Owner approval.
- Phase status marked `CLOSED` and promoted as the operating pattern for subsequent scenarios.

### Delivery cadence for fast execution

Use short cycles with explicit go/no-go gates:

1. **Cycle 1:** P3-1 and P3-2
2. **Cycle 2:** P3-3 and P3-4
3. **Cycle 3:** P3-5 and P3-6

Each cycle ends with:
- A file gate (only expected assets changed).
- A behavior gate (northstar scenario assertions pass).
- A publish gate (draft/published surfaces synchronized).

This keeps Phase 3 fast while preserving proof-based governance closure.

---

## 6. Layer Responsibilities (Mental Model)

| Layer | Role | Tool |
|---|---|---|
| Source data | Operational data, gold tables | Fabric Lakehouse (medallion) |
| Working metadata store | Curate / extend / certify metadata | `lh_metadata` lakehouse |
| Runtime metadata surface | Where Copilot / Data Agents read from | Fabric semantic model (via SemPy Labs write-back) |
| Governance / publication | Catalog, glossary, lineage, classification | Microsoft Purview (scanning the Fabric SM) |
| AI consumption | Question answering, narrative, action | Fabric Data Agent on top of gold + ontologies |

---

## 7. Things to Validate Before Building

A few items Alison left open or implied that are worth confirming before you start coding:

1. **Which existing Enercare semantic model is the demo target?** SemPy reads from a real model — you'll need either an existing Enercare model or a representative stand-in.
2. **Purview tenant choice** — Alison flagged the 3-subscription setup ("is there a reason you have 3 subscriptions?"). Consolidate or document why before the Purview scan step.
3. **AI Data Schema scope** — decide which subset of the model the Data Agent should answer over before configuring Prep for AI.
4. **Ontology shape** — Alison referenced ontologies generically. For the demo, pick a single, concrete gold data product (e.g., *Customer 360* or *Service Calls*) and build the agent around that.
5. **Promotion/certification authority** — who in the demo flow marks the model as Certified? This is the human-in-the-loop step that makes the governance story real.

---

## 8. References Alison's Pattern Maps To

- *Semantic model best practices for Data Agent* — `learn.microsoft.com/en-us/fabric/data-science/semantic-model-best-practices`
- *Prepare your data for AI in Power BI* — `learn.microsoft.com/en-us/power-bi/create-reports/copilot-prepare-data`
- *Use Microsoft Purview to govern Microsoft Fabric* — `learn.microsoft.com/en-us/purview/microsoft-purview-fabric`
- *Metadata and lineage from Fabric into Microsoft Purview* — `learn.microsoft.com/en-us/purview/how-to-lineage-fabric`
- `semantic-link` (SemPy) — `pypi.org/project/semantic-link/`
- `semantic-link-labs` (SemPy Labs) — `pypi.org/project/semantic-link-labs/`

---

## Appendix — Alison's Comments, Verbatim

**2026-04-15** — Background: Enercare wants SQL → Fabric mirroring with governance parity; Sean expects the conversation to turn to RLS/OLS. (Sean's framing, not Alison's, but sets the stage.)

**2026-05-07 21:10:32** — *"You have a mirror db set up and reading from it with jdbc connection via notebook and adding that to current metadata from reports gotten by sempy and then writing to reports with sempylabs and writing to purview via purview api?"* — initial framing of the pattern.

**2026-05-07 21:12:50** — *"Yeah ideally they have purview as a source but seems like for their UC they need fabric."*

**2026-05-07 21:13:11** — *"Future state would like to have purview cause it's a governance tool."*

**2026-05-13 13:52:45** — *"You can add whatever to the sql db and then scan it. From the last email it seems we can just have table and column definitions to start for the semantic models. Those definitions can be a bulk load from a lh in fabric like you have. Once those are defined then we scan in the fabric semantic models with the appropriate metadata. They can make gold data products and add context to this metadata… AI ready means making sure your data has the most context and good quality so one copy of data, leveraging medallion architecture and using the gold layer to feed ontologies which data agents sit on, making sure you have proper sensitivity labels and promoted items in fabric and proper governance and you're running DQ rules."*

**2026-05-18 17:13:58** — *"But they're not using sys.extended properties rn so what's the point of bringing in that data? From my understanding they would just need to read the current report metadata using SemPy and then write it using SemPy Labs. To get it to Purview they can just scan the semantic models and get the data to Fabric. Does that make sense? The jdbc connection was if they needed the sys extended properties which sounds like they don't and that was my misunderstanding."* — **the simplification.**

**2026-05-18 18:56:07** — *"Not the latter — to scan the SM in Fabric."* — confirming Purview scans the Fabric semantic models, not SQL.
