# Enercare Demo Preparation and Validated Artifact Catalog

## Purpose

This document is the presenter-facing build record for the Enercare metadata-governance demo. It explains what each Fabric notebook does, catalogs the artifacts it creates or changes, connects those artifacts to the Maria call-center story, and records runtime evidence from the sequential validation run.

Runtime claims are added only after the corresponding notebook and its outputs have been validated. Planned behavior is labeled `Pending validation` until that gate passes.

## Demo Architecture

The demo uses three coordinated planes:

1. **Authoritative data plane** - Azure SQL database `sqldemo` holds operational customer, service, billing, and governance records. Fabric Mirroring exposes those SQL tables through the `sqldemo` mirrored database.
2. **Analytics and AI plane** - Fabric lakehouses `lh_enercare_demo` and `lh_metadata`, the `BrookfieldEnercare` semantic model, report, and Data Agent provide governed analytics and natural-language access.
3. **Governance plane** - Microsoft Purview, the SQL governance ledger, Fabric metadata tables, and semantic-model annotations provide approval, ownership, classification, glossary, lineage, and audit evidence.

GitHub `RangerXP/sql-metadata-mirror`, branch `main`, is the deployment source of truth for Fabric item definitions. Notebook fixes are committed and pushed before Fabric synchronization and runtime validation.

## Security and Service Model

- Microsoft Entra identities authenticate Fabric, Azure SQL, Purview, and automation calls.
- Azure SQL public network access is disabled; administrative validation uses the private VPN route.
- Fabric Mirroring reaches private Azure SQL through its configured gateway and service-principal connection.
- The SQL server managed identity has the Fabric permissions required to write change-feed data to the mirror landing zone.
- Fabric notebook dependencies bind each notebook to its intended Lakehouse and, where required, managed Environment.
- Secrets and tokens are not stored in Git. Runtime credentials come from Entra, managed identity, environment configuration, or approved token flows.
- Governance mutation is separated from discovery: raw metadata and source tags are staged first, then approved changes are applied by dedicated workflow stages.

## Data, AI, and Metadata Model

The operational model starts with customer, account, equipment, contract, service-request, and billing transactions. The SQL layer adds governance-oriented demo records, including Maria Castellanos and related consent, complaint, audit, and service context.

The metadata model separates:

- discovered source metadata and `@tag` detections
- owners, stewards, glossary terms, CDEs, labels, domains, and data products
- an append-only governance request ledger with approval and application state
- KPI definitions, AI instructions, and certified verified answers
- source-to-Fabric-to-semantic lineage edges
- semantic-model annotation staging and reconciliation evidence

Only approved and certified content is intended to reach semantic-model and AI grounding surfaces. The Data Agent answers operational questions from governed semantic content; governance authorship, approval, and policy evidence remain governed catalog responsibilities.

## Maria Call-Center Story

Maria Castellanos is the customer thread used to demonstrate the architecture end to end:

1. Maria's customer, account, equipment, service, billing, consent, complaint, and audit records originate in the authoritative SQL/Fabric data path.
2. Metadata discovery identifies the meaning, ownership, sensitivity, and business use of those assets.
3. The semantic model turns the operational records into governed analytical entities and measures.
4. AI grounding exposes certified operational answers without treating draft metadata as authoritative.
5. Purview publishes the governing domains, products, glossary, CDE, labels, and lineage.
6. Approval workflows demonstrate controlled change rather than direct metadata mutation.
7. Validation proves that Maria's answer path can be traced back to approved definitions and source data.

## Sequential Runtime Rules

- Run notebooks in numeric order and stop on failed or ambiguous evidence.
- Submit exactly one Fabric `RunNotebook` job per stage. A roughly three-minute `NotStarted` period is normal Spark-session startup and is not a reason to resubmit.
- Use startup time to prepare output validation.
- Push every code change to `origin/main`, synchronize Fabric to that commit, and only then rerun.
- Record the item ID, job ID, status, duration, output counts, and downstream readback.
- A `Completed` job is necessary but not sufficient; persisted artifacts must also be read back.

## Notebook Artifact Catalog and Runtime Evidence

### NB_01 - `01_setup_source_data`

**Validation status:** Passed on 2026-08-15.

**Role in the architecture**

NB_01 establishes the operational foundation used by every later metadata, semantic, AI, and governance stage. It creates a deterministic synthetic Enercare baseline in `lh_enercare_demo`, publishes the authoritative seven-table operational model into Azure SQL `sqldemo`, and executes SQL-first extensions that support the broader governance and Maria scenarios.

**Primary services used**

- Fabric Spark and Delta Lake
- Fabric Lakehouse `lh_enercare_demo`
- Azure SQL `sqlserver-sk2wus3.database.windows.net/sqldemo`
- Microsoft Entra/managed-identity or TokenLibrary SQL authentication
- Fabric Mirroring into mirrored database `sqldemo`

**Core Lakehouse artifacts**

| Artifact | Purpose | Validated rows |
|---|---|---:|
| `lh_enercare_demo.products` | Product and plan catalog | 10 |
| `lh_enercare_demo.customers` | Residential, commercial, and multi-unit customers | 50 |
| `lh_enercare_demo.service_accounts` | Service locations and utility relationships | 56 |
| `lh_enercare_demo.equipment_registry` | Installed/rented equipment and lifecycle state | 38 |
| `lh_enercare_demo.contracts` | Product contracts, terms, and renewal state | 56 |
| `lh_enercare_demo.service_requests` | Maintenance, repair, installation, and SLA events | 30 |
| `lh_enercare_demo.billing_transactions` | Charges, taxes, payments, and invoice references | 585 |

The notebook also creates call-center extension tables in the Lakehouse, including agent, billing-adjustment reference, interaction, transcript-turn, and renewal-analysis artifacts used by later analytical and AI experiences.

**Authoritative Azure SQL and mirrored artifacts**

| Artifact | Validated SQL rows | Validated mirror rows | Difference from baseline |
|---|---:|---:|---|
| `dbo.products` | 10 | 10 | None |
| `dbo.customers` | 51 | 51 | Maria/customer extension |
| `dbo.service_accounts` | 57 | 57 | Maria service account |
| `dbo.equipment_registry` | 39 | 39 | Maria equipment |
| `dbo.contracts` | 57 | 57 | SQL-first extension |
| `dbo.service_requests` | 31 | 31 | Maria service request |
| `dbo.billing_transactions` | 587 | 587 | Maria billing rows |

Additional SQL-first artifacts include governance domains, data products, glossary terms, CDEs, role assignments, sensitivity-label assignments, governance requests, OKRs, consent, complaint, employee, service-zone, and audit data defined by the notebook's embedded idempotent SQL phases.

**Security and governance posture**

- `DEMO_MODE=False` enables the real SQL publication path.
- Base-table publication uses primary-key-aware `skip_existing`, preventing duplicate inserts on repeat runs.
- SQL authentication prefers managed identity and falls back to TokenLibrary when required.
- Azure SQL remains private; validation succeeded after reconnecting the approved VPN path.
- SQL is authoritative for enriched operational/governance rows; the Fabric mirror is validated as a downstream replica rather than treated as a second source of truth.

**Maria and demo contribution**

NB_01 makes Maria a real governed operational record rather than a presentation-only persona. Her customer, service account, equipment, service request, billing, consent, complaint, and audit context becomes available to the mirror, semantic model, Data Agent, and governance evidence chain used in later stages.

**Runtime evidence**

| Evidence | Value |
|---|---|
| Fabric item ID | `72fcdfdf-cf7d-40b6-be03-fe76c877f2d9` |
| Fabric job ID | `3e10bd4a-d55c-449c-9784-9152e7ef5695` |
| Status | `Completed` |
| Start | `2026-08-16T00:06:19Z` |
| End | `2026-08-16T00:13:46Z` |
| Source-control commit | `00e89159e72e12ee11ae8921d3f868d6466307db` |
| Fabric/Git pending changes | `0` |
| Mirror status | `Running`; all seven base tables `Replicating`; no per-table errors |

**Gate result:** PASS. The job completed, Lakehouse baseline counts matched the notebook definitions, Azure SQL contained the expected enriched counts, and the mirrored SQL endpoint matched Azure SQL after propagation.

### NB_02 - `02_build_metadata_foundation`

**Validation status:** Pending validation.

**Planned role:** discover SQL `@tag` metadata, stage governed working tables in `lh_metadata`, reconcile SQL-mirrored and customer metadata, seed KPI/AI metadata, and build semantic annotation candidates without directly applying unapproved changes.

**Expected artifact families:** source-tag detections, `ai_metadata`, `data_owners`, `lineage_edges`, `kpi_metadata`, current business-metadata views, domains, data products, glossary terms, CDEs, role and label assignments, governance request working copies, OKRs/key results/product links, and `sm_annotations`.

### NB_03 - `03_build_semantic_model`

**Validation status:** Pending validation.

**Planned role:** build or refresh the DirectLake star schema and source-to-semantic mappings from the mirrored operational model.

### NB_04 - `04_writeback_governed_metadata`

**Validation status:** Pending validation.

**Planned role:** apply approved descriptions, certifications, KPI metadata, and AI instructions to the semantic model through SemPy and SemPy Labs.

### NB_05 - `05_publish_governance_domains`

**Validation status:** Pending validation.

**Planned role:** publish approved governance domains, data products, ownership, and stewardship state to Purview.

### NB_06 - `06_publish_glossary_and_lineage`

**Validation status:** Pending validation.

**Planned role:** publish glossary terms, CDEs, classifications, normalized sensitivity labels, asset associations, and cross-system lineage.

### NB_07 - `07_apply_approved_changes`

**Validation status:** Pending validation.

**Planned role:** apply only approved, unapplied governance requests and record downstream mutation evidence.

### NB_08 - `08_validate_governance_evidence`

**Validation status:** Pending validation.

**Planned role:** validate stewardship, approvals, publication, sensitivity, lineage, semantic state, and the Maria end-to-end evidence chain.

### NB_09 - `09_reconcile_semantic_model`

**Validation status:** Pending validation.

**Planned role:** detect and correct semantic-governance drift against approved catalog state without creating implicit approvals.

### NB_10 - `10_reset_demo`

**Validation status:** Pending validation.

**Planned role:** restore the repeatable demonstration baseline without deleting governed production objects or tenant-wide governance state.

## Related Detailed References

- `docs/Enercare-Demo-SemPy-Design-Guide.md`
- `docs/design-gap-analysis.md`
- `docs/closed-loop-governance-reference-model.md`
- `docs/purview-maria-north-star-scenario.md`
- `docs/maria-northstar-validation-plan.md`
- `docs/runbooks/ten-notebook-consolidated-validation.md`
- `docs/sql-metadata-governance-standard.md`
