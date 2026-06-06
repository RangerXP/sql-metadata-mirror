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
- Prepares Purview payloads and is guarded for SQL-mirror-only runs unless explicitly overridden.

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
