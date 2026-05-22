# Brookfield Enercare SQL Metadata Mirror

This repository is the maintained source-control surface for the current Enercare build:

- `sub1`: Microsoft Fabric workspace, lakehouses, notebooks, semantic model, report, and data agents
- `sub2`: Azure SQL authoritative source and Fabric mirroring input
- `sub3`: Purview governance plane

It is intentionally trimmed to the files needed to maintain the live deployment. Legacy demo mirrors,
packaging artifacts, presentation files, and obsolete walkthrough content have been removed.

## Live Architecture

```text
nb_01_setup_demo_environment
    -> lh_enercare_demo baseline tables in Fabric
    -> nb_05a_publish_synthetic_data_to_sql
    -> Azure SQL sqldemo in sub2
    -> Fabric mirrored database sqldemo-mirror in sub1
    -> nb_03_pbi_star_schema rebuilds lh_enercare_demo star schema
    -> nb_02 / nb_04a / nb_04 / nb_05 maintain metadata and semantic-model grounding
    -> Purview in sub3 is the published governance target
```

## Maintained Repo Surface

```text
/ 
|- .github/                     Copilot instructions for the maintained repo shape
|- context/                     Supporting JSON context used by notebooks and guidance
|- docs/                        Current architecture and build-status documents
|- pbi/                         Fabric Git sync source of truth
|- sql/                         Azure SQL source DDL used by the mirrored deployment
|- sql-private-dns-vnet-link.bicep
|- sql-private-dns-vnet-link.json
```

## Fabric Git Sync

- GitHub repo: `RangerXP/sql-metadata-mirror`
- Branch: `enercare`
- Fabric should sync from git into the workspace from the `pbi/` surface in this repo

## Maintained Fabric Assets

The `pbi/` folder is the only maintained Fabric content surface in git.

- `nb_01_setup_demo_environment.Notebook/`
- `nb_02_metadata_pipeline_demo.Notebook/`
- `nb_03_pbi_star_schema.Notebook/`
- `nb_04a_extend_metadata_schema.Notebook/`
- `nb_04_generate_tmdl.Notebook/`
- `nb_05a_publish_synthetic_data_to_sql.Notebook/`
- `nb_05b_test_sql_connectivity.Notebook/`
- `nb_05_push_qa_verified_answers.Notebook/`
- `BrookfieldEnercare.SemanticModel/`
- `BrookfieldEnercare.Report/`
- `lh_enercare_demo.Lakehouse/`
- `lh_metadata.Lakehouse/`
- `Enercare Data Agent.DataAgent/`
- `Enercare Governance Agent.DataAgent/`

## Recommended Run Order

1. `nb_01_setup_demo_environment`
2. `nb_05a_publish_synthetic_data_to_sql`
3. Fabric mirror sync from `sqldemo`
4. `nb_03_pbi_star_schema`
5. `nb_02_metadata_pipeline_demo`
6. `nb_04a_extend_metadata_schema`
7. `nb_04_generate_tmdl`
8. `nb_05_push_qa_verified_answers`
9. `nb_05b_test_sql_connectivity` when private SQL connectivity needs validation

## Key Documents

- `docs/design-gap-analysis.md`: current build status and remaining gaps
- `docs/sub2-sql-source-mapping.md`: authoritative seven-table mirrored-source mapping
- `sql/02_sub2_sql_source_schema.sql`: Azure SQL DDL for the mirrored source slice

## Maintenance Rules

- Keep only the current deployment assets in git.
- Treat `pbi/` as the Fabric source-of-truth surface.
- Do not reintroduce duplicate notebook mirrors outside `pbi/`.
- Do not add presentation decks, exports, or generated zip files to the maintained repo.
| TMDL description injection | Live — nb_04 pushes table/column descriptions via Fabric REST API |
| Copilot AI grounding | Live — PBI_AI_Instructions annotation set with instructions + verified Q&A |
| Governance Data Agent | Live — queries star schema + metadata lakehouses via natural language |
| Purview integration | In design — Atlas entity push not yet implemented |
| Ontology model | Not yet started |

---

## Repository Structure

```
/
├── demo/                              Dev copies + SQL seed data
│   ├── sql/
│   │   ├── 00_demo_schema_and_headers.sql     T-SQL schema + views with header convention
│   │   └── 01_demo_seed_data.sql              Seed data INSERT statements
│   └── README.md                     Demo-specific run instructions
│
├── pbi/                               Fabric workspace sync (branch: enercare, folder: /pbi)
│   ├── nb_01_setup_demo_environment.Notebook/   Source table loader
│   ├── nb_02_metadata_pipeline_demo.Notebook/   Governance metadata extractor
│   ├── nb_03_pbi_star_schema.Notebook/          Star schema builder
│   ├── nb_04a_extend_metadata_schema.Notebook/  Schema extension + AI metadata seeder
│   ├── nb_04_generate_tmdl.Notebook/            TMDL description injector (Fabric REST API)
│   ├── nb_05_push_qa_verified_answers.Notebook/ Copilot verified Q&A annotation pusher
│   ├── BrookfieldEnercare.SemanticModel/        Direct Lake semantic model (TMDL)
│   ├── BrookfieldEnercare.Report/               Power BI report
│   ├── lh_enercare_demo.Lakehouse/              Demo data lakehouse
│   ├── lh_metadata.Lakehouse/                   Governance metadata lakehouse
│   ├── Enercare Data Agent.DataAgent/           AI agent (NL queries over semantic model)
│   └── nb_05_push_qa_verified_answers.Notebook/ Pushes verified Q&A to PBI_AI_Instructions
│
└── sql/
    └── 02_extract_from_modules.sql    T-SQL metadata extractor (SQL Server path)
```

> **Git integration:** The Fabric workspace syncs to the `enercare` branch.
> Push changes here → sync in Fabric via **Source control → Update all**.
> Commit workspace changes back via **Source control → Commit**.

---

## Demo Data Model

Modelled on an Ontario residential/commercial energy services company.

### Source Tables (`lh_enercare_demo`)

| Table | Rows | Description |
|---|---|---|
| `customers` | 50 | Residential (40), Commercial (5), MUR (5) — Ontario cities |
| `service_accounts` | 56 | Natural Gas, HVAC, Water Heater, Electricity |
| `products` | 10 | Rentals, protection plans, smart home |
| `contracts` | 68 | Active, Cancelled, Expired |
| `equipment_registry` | 38 | Water heaters, furnaces, AC, heat pumps, thermostats |
| `service_requests` | 30 | Completed, InProgress, Open — with SLA breach flags |
| `billing_transactions` | ~300 | Jan–Jun 2024 monthly charges + payments |

### Star Schema (`lh_enercare_demo`)

| Layer | Tables |
|---|---|
| Dimensions | `dim_date`, `dim_customer`, `dim_product`, `dim_equipment`, `dim_service_account` |
| Facts | `fct_billing`, `fct_service_request`, `fct_contract_month` |

Key computed columns: `IsSlaBreachFlag`, `DaysToComplete`, `IsNew`, `IsChurn`,
`IsUnderWarranty`, `AgeYears`, `FSA`.

### Metadata Tables (`lh_metadata`)

| Table | Description |
|---|---|
| `asset_metadata` | Table/view descriptions, owner, steward, domain, sensitivity, DefinitionHash |
| `column_metadata` | Column descriptions per asset |
| `kpi_metadata` | KPI definitions with `IsCertified` gate, `LinkedMeasureName`, `BusinessDefinition` |
| `ai_metadata` | AI grounding instructions (`ai_instruction`) and verified Q&A pairs (`verified_answer`) |
| `sensitivity_classification` | Column-level sensitivity tags |
| `data_owners` | Owner and steward assignments per asset |
| `data_lineage` | Upstream dependency graph |
| `vw_business_metadata_current` | Unified view across all tables — single query surface for nb_04/nb_05 |

---

## Metadata Header Convention

Source SQL objects carry structured comments that nb_02 parses:

```sql
-- @asset_type    : view
-- @description   : Customer 360 — lifetime value, tenure, SLA exposure
-- @owner         : analytics@enercare.ca
-- @sensitivity   : Internal
-- @kpi           : ActiveCustomerCount | count(customer_id) WHERE status='Active'
-- @column        : CustomerKey | Surrogate key | Internal
-- @upstream      : customers, service_accounts, contracts
```

Supported tags: `@asset_type`, `@description`, `@owner`, `@steward`, `@domain`,
`@grain`, `@refresh`, `@sensitivity`, `@glossary`, `@upstream`, `@column`, `@kpi`, `@notes`

---

## DEMO_MODE Convention

All notebooks except nb_01 respect a `DEMO_MODE` flag at the top of Cell 1:

| Value | Behaviour |
|---|---|
| `True` (default) | Dry-run — prints SQL statements, annotation previews, or injection plans. No Delta writes, no REST API calls. Safe to run at any time. |
| `False` | Live — executes all operations: writes Delta tables, alters schemas, calls Fabric REST API to push TMDL changes. |

Change `DEMO_MODE = True` to `DEMO_MODE = False` and re-run when ready to apply.

---

## Getting Started (New Collaborator)

### Prerequisites
- Access to the Fabric workspace `Enercare` (workspace ID: `795ce5db-7ea0-4a7c-ba64-e27c9fb568f4`)
- Git access to this repository (branch: `enercare`)
- Power BI Desktop (July 2023+) to view the semantic model locally via `pbi/BrookfieldEnercare.pbip`

### Sync workspace from git
In the Fabric workspace: **Source control → Update all**

### Full pipeline run (fresh start)
1. `nb_01` — loads all 7 source tables into `lh_enercare_demo`
2. `nb_02` — extracts governance metadata into `lh_metadata` (set `DEMO_MODE = False`)
3. `nb_03` — builds star schema in `lh_enercare_demo`
4. `nb_04a` — extends `lh_metadata` schema and seeds AI metadata (set `DEMO_MODE = False`)
5. `nb_04` — injects TMDL descriptions into semantic model (set `DEMO_MODE = False`)
6. `nb_05` — pushes verified Q&A annotation to semantic model (set `DEMO_MODE = False`)

The semantic model and Data Agent are live after step 3. Steps 4–6 add AI grounding.

### Verifying Copilot grounding (after nb_05)
Ask Copilot in the Power BI report or Data Agent:
- *"What is our FCR?"* → should return First Contact Resolution definition
- *"What is our CSAT score?"* → should return CSAT definition and context
- *"What is our PP renewal rate?"* → should return Protection Plan renewal definition

---

## Planned: Purview & Ontology

The next development phase uses the populated `lh_metadata` tables as the source of truth
for Purview registration and ontology generation.

**Purview targets:**
- Register lakehouse tables as Atlas `DataSet` entities with business descriptions
- Push column-level sensitivity classifications from `sensitivity_classification`
- Create lineage edges: source SQL objects → OneLake Delta tables → semantic model
- Populate business glossary terms from `kpi_metadata` and `column_metadata`

**Ontology targets:**
- Define entity types for the Enercare domain (Customer, ServiceAccount, Equipment,
  Contract, ServiceEvent, BillingEvent)
- Map star schema tables to ontology classes
- Export ontology compatible with Purview custom type definitions

**Notebooks to build:**
- `nb_06_purview_register_assets` — Atlas entity push from `lh_metadata`
- `nb_07_purview_lineage` — lineage registration
- `nb_08_ontology_export` — ontology artifact generation

---

## Key Contacts

| Role | Name |
|---|---|
| Project lead | Sean Kelley (Microsoft) |
| Original scaffold | Ajay (Microsoft PG) |
