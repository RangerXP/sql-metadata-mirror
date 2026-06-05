# Purview Demo Data Design — Enercare (West3)

**Owner:** Sean Kelley
**Date:** 2026-06-04
**Scope:** Construct a synthetic dataset and metadata input set that exercises every Purview use case from `docs/purview-governance-brief.md`, and define where each artifact lives across SQL, Fabric-native resources, external customer files, and Sempy Labs write-back.
**Targets:** Tenant `b7e47691-9726-4f67-a302-e567815f3522`, Purview `Purview-West3`, Fabric workspace `Enercare-West3`, SQL `sqlserver-sk2wus3.database.windows.net/sqldemo`, Semantic Model `BrookfieldEnercare`.

> **North Star:** Every design choice in this document earns its place by serving the Maria scenario — see `docs/purview-maria-north-star-scenario.md`. If a glossary term, CDE, role, or policy doesn't show up there, it doesn't ship.

> The brief proved Purview can ingest this estate. What it cannot do is **invent** the inputs. Owners, glossary terms, sensitive markers, CDEs, and label-to-asset bindings have to come from somewhere — this design names that "somewhere" for every use case and constructs the data to back it up.

---

## 1. Design Philosophy — Where Things Live, and Why

A realistic Purview deployment is **not** a single-tier metadata story. Customers maintain inputs in **four** distinct places, and each place has a different change cadence and authority.

| Tier | What lives here | Change cadence | Authority for...                            | Demo store                                                          |
|------|-----------------|----------------|---------------------------------------------|---------------------------------------------------------------------|
| **T1 — Source SQL** (`sqldemo`, mirrored)  | Operational data, **PII values**, role/owner reference tables, regulatory consent records | Continuous (transactional) | **Classification** — Purview only classifies values it actually sees. PII shapes must be real enough that MIP classifiers fire. | Azure SQL → Fabric Mirror → OneLake |
| **T2 — Customer-owned external files** | Glossary, CDE catalog, role directory, label policy, domain charter, data product catalog | Quarterly / on-policy-change | **Policy** — these are governance artifacts that exist independently of the data, often pre-dating the platform. | OneDrive / SharePoint / Git → bulk-loaded into `lh_metadata` |
| **T3 — Fabric-native (lakehouse, semantic model)** | `lh_metadata` working store, gold star schema, semantic model annotations, Fabric endorsement, MIP labels applied to Fabric items | Daily / per-curation-cycle | **Runtime metadata** — what Copilot, Data Agents, and end users actually see when querying. | `lh_enercare_demo`, `lh_metadata`, `BrookfieldEnercare` semantic model |
| **T4 — Purview-native (Unified Catalog)** | Governance domains, data products, glossary publication, CDEs, classifications, scan-derived asset records, asset-to-product bindings | On-publication | **Published catalog** — the discoverability and governance system-of-record. | `Purview-West3` |

### Why not "everything in SQL"?

You **could** put policy artifacts (glossary, CDE catalog, roles) in SQL. Some customers do. But this conflates three concerns:

1. **Data ownership** (T1 belongs to the operational system owner)
2. **Policy ownership** (T2 belongs to the data governance office / CDO)
3. **Catalog ownership** (T4 belongs to the Purview administrator)

Mixing them in one schema means glossary edits require DBA gatekeeping, and label policy changes get tangled with data migrations. The hybrid pattern below is what enterprise customers actually run.

### Why not "everything in external files"?

You also could not. **Purview classifiers can only see what they scan.** PII has to be present in scan-targetable assets — that means SQL or Fabric data, not a CSV in a OneDrive folder. So the data Purview *classifies* must be in T1/T3, and the policies Purview *applies* live in T2/T4.

### The placement decision matrix

| Use case from brief                              | T1 SQL   | T2 Customer File | T3 Fabric native | T4 Purview native | Sempy Labs writeback |
|--------------------------------------------------|----------|------------------|------------------|--------------------|----------------------|
| Governance domains (3)                           | —        | charter source-of-truth | mirrored to `lh_metadata` | **authored here** | — |
| Data products (3)                                | —        | catalog source-of-truth | staged in `lh_metadata` | **authored here** | — |
| Asset-to-data-product bindings                   | —        | catalog references | — | **authored here** | — |
| Glossary terms (industry / domain-specific)      | —        | **source-of-truth** | staged in `lh_metadata` | **published here** | term references annotated on semantic model |
| Critical Data Elements (CDEs)                    | —        | **source-of-truth** | staged in `lh_metadata` | **published here** (preview) | CDE-member annotations on columns |
| Sensitivity labels (MIP)                         | —        | label taxonomy / rules | applied to Fabric items | classifications surface here | label annotations on semantic model |
| Roles / owners / stewards                        | reference table | **source-of-truth** | staged | role assignments | annotation on objects |
| **Classified PII** (names, SIN, payment, address) | **must live here** for classifiers to fire | — | mirrored | classification labels surface here | — |
| Lineage edges (SQL → mirror → SM → report)       | — | edges CSV (already exists) | edge tracking | **registered here** via custom Atlas | — |
| Table / column / measure **descriptions**        | — | inputs feed metadata curation | curated in `lh_metadata` | scanned from semantic model | **primary write target** |
| AI instructions, verified Q&A                    | — | curation inputs | curated in `lh_metadata` | scanned via SM scan | **primary write target** |

**Rule of thumb:**
- If Purview must **classify it**, it lives in **T1** with realistic values.
- If a **steward must edit it without touching prod data**, it lives in **T2**.
- If **Copilot or a Data Agent must read it**, it gets onto the semantic model via **Sempy Labs (T3 → T4 write-back)**.
- If it's the **published catalog state**, it lives in **T4**.

---

## 2. Industry Context — Enercare (Brookfield)

Anchoring the synthetic data on Enercare's real business profile is what makes the demo land. Key facts:

- **Industry:** Home services / utility — HVAC rental, water heaters, protection plans, sub-metering
- **Geography:** Primarily Ontario, Canada (extending nationally)
- **Regulator(s):**
  - **OEB** (Ontario Energy Board) — sub-metering & utility distribution
  - **PIPEDA** — federal privacy law (consent, breach reporting)
  - **CASL** — anti-spam (email/SMS consent required)
  - **Ontario Consumer Protection Act** — auto-renewal disclosure
- **Identifiers to expect in source data:** SIN (Canadian Social Insurance Number, 9-digit XXX-XXX-XXX), FSA postal codes (first 3 chars), bank routing numbers, account numbers
- **Sensitive categories:**
  - Confidential — customer PII, contracts, service-call notes
  - Highly Confidential — SIN, payment method PANs (last 4), banking info, residential GPS

These regulatory anchors are what make the **glossary** and **CDE catalog** below feel like a real customer's, not a generic demo.

---

## 3. Dataset Construction — What to Build, Where

### 3.1 SQL Source Extensions (T1)

The existing 7 tables (`products`, `customers`, `service_accounts`, `equipment_registry`, `contracts`, `service_requests`, `billing_transactions`) cover the core operational story but **lack the data Purview classifiers care about**. The current `customers` table has only `first_name`, `last_name`, `email`, `phone` — none of which exercise the classifiers that produce sensitivity-label evidence.

**Add these columns to existing tables** (DDL in `output/sql-additions/04_purview_demo_extensions.sql`):

| Table | New column | Type | Why it earns a Purview use case |
|-------|------------|------|---------------------------------|
| `customers` | `date_of_birth` | DATE | DOB classifier → Confidential |
| `customers` | `sin_last_4` | CHAR(4) | Canadian SIN partial → Highly Confidential, exercises Canada SIN classifier when full version used in audit table |
| `customers` | `owner_email` | VARCHAR(255) | Steward / Data Owner mapping for downstream Purview role assignment |
| `service_accounts` | `latitude` | DECIMAL(9,6) | GPS coordinates → Confidential, exercises location classifier |
| `service_accounts` | `longitude` | DECIMAL(9,6) | GPS coordinates → Confidential |
| `billing_transactions` | `bank_routing_last_4` | CHAR(4) | Bank routing → Highly Confidential, exercises financial classifier |
| `billing_transactions` | `card_pan_last_4` | CHAR(4) | PAN partial → PCI scope, exercises credit card classifier |

**Add these net-new tables**:

| Table | Purpose | Purview use case it unlocks |
|-------|---------|----------------------------|
| `dbo.employees` | Resolves `service_requests.technician_id`; carries SIN for HR scenario | Highly Confidential classification on `sin_full` column — proves the classifier difference between partial and full PII |
| `dbo.customer_consents` | PIPEDA consent records (marketing, data sharing, retention) | Demonstrates regulatory CDE; needed for **Ontario PIPEDA compliance** glossary terms |
| `dbo.customer_complaints` | Complaint workflow with regulator-reportable severity | Domain ownership story for **Customer Operations** governance domain |
| `dbo.service_zones` | Geographic territory hierarchy | Territorial role assignment story; demonstrates **Service Delivery** domain hierarchy |
| `dbo.data_owners_directory` | UPN ↔ table mapping for object ownership at the SQL layer | Bridges T1 to T2 role directory; proves the "owner exists in source" reverse-lookup |
| `dbo.audit_data_access` | Recently accessed sensitive rows (per row purpose-of-use) | Exercises **data observability** preview features and ties to **purpose-of-use** governance pattern |

**Net effect:** 7 tables → 13 tables, with **10 columns of net-new classifiable PII**. This is enough to make a real Purview classification dashboard look populated.

### 3.2 Customer-Owned External Files (T2)

These files live in `customer-files/` under the demo repo (and in the real customer's case, in SharePoint or Git). The MVP set is **six CSVs**:

| File | Rows | Purpose |
|------|------|---------|
| `domain-charter.csv`         | 3 | Governance domain definitions, types, owners |
| `data-product-catalog.csv`   | 3 | Data product specs, owners, asset-binding intent |
| `role-directory.csv`         | ~25 | Person ↔ role ↔ domain/product matrix |
| `glossary-master.csv`        | ~35 | Industry/regulatory/business terms with acronyms, definitions, parents |
| `cde-catalog.csv`            | ~12 | Critical Data Elements with regulatory references |
| `label-policy.csv`           | 4 + rules | Sensitivity label taxonomy + assignment rules |

These are **deliberately small** — MVP scope. The brief proved the platform supports much more, but a working pilot needs ~30 glossary terms, not 300.

### 3.3 Fabric Native Resources (T3)

Use existing `lh_metadata` + `lh_enercare_demo` lakehouses. Add these tables in `lh_metadata` (populated by a new notebook that bulk-loads from the T2 CSVs):

| Lakehouse table | Source | Purpose |
|-----------------|--------|---------|
| `metadata.glossary_terms` | `glossary-master.csv` | Staged glossary for Purview push |
| `metadata.cdes` | `cde-catalog.csv` | Staged CDEs for Purview push |
| `metadata.data_products` | `data-product-catalog.csv` + scan results | Joined view: data product → actual scanned asset GUID |
| `metadata.domains` | `domain-charter.csv` | Staged domains for Purview push |
| `metadata.role_assignments` | `role-directory.csv` + `dbo.data_owners_directory` (T1) | Reconciled role view |
| `metadata.label_assignments` | `label-policy.csv` + classification scan output | What gets MIP-labeled and why |

### 3.4 Semantic Model — Sempy Labs Write-Back Targets (T3 → T4)

Per Alison's pattern, the semantic model is the **runtime metadata surface** Copilot and Data Agents read. Sempy Labs writes these properties from `lh_metadata`:

| Sempy Labs write | Source | Visible to |
|------------------|--------|------------|
| `Table.Description` | `metadata.glossary_terms` joined on `table_business_term` | Copilot, Purview scan |
| `Column.Description` | `metadata.glossary_terms` joined on `column_business_term` | Copilot, Purview scan |
| `Column` annotation `CDE_Member_Of` | `metadata.cdes` joined on column | Purview CDE binding (via SM scan) |
| `Measure.Description` | `metadata.glossary_terms` for measure-level KPIs | Copilot, Power BI Q&A |
| `Model` annotation `Sensitivity_Label` | `metadata.label_assignments` table-level | Fabric MIP label application |
| `Model` annotation `Data_Product_Owner` | `metadata.role_assignments` | Discoverability, audit |
| `Model` annotation `PBI_AI_Instructions` | curated content | Power BI Copilot grounding |
| Verified Q&A entries | curated content | Power BI Copilot (preview) |

### 3.5 Purview-Native Authoring (T4)

After scans complete, the Purview admin (Alison) authors directly in Unified Catalog:

1. **Governance domains** — push from `metadata.domains` via Purview SDK (or manually)
2. **Data products** — push from `metadata.data_products`, bind to scanned asset GUIDs (the join is on table-qualified name)
3. **Glossary terms** — push from `metadata.glossary_terms` (use the Purview bulk-import preview if you want repeatable flow; cap at 1,000 rows)
4. **CDEs** — push from `metadata.cdes` (preview; manual UI for MVP unless API stable)
5. **Role assignments** — Domain Owner, Data Product Owner, Data Steward per `metadata.role_assignments`
6. **Label policies** — configured via Microsoft Purview Information Protection portal, then enforced as Fabric Protection Policies (E3/E5 required; brief flagged the 50-policy / 100-user cap)

---

## 4. Run Order — How the Pieces Get Loaded

```
                    Day 1 (one-time)
                    ─────────────────
Customer files
(T2 CSVs)  ──────► purview/ in repo ──────► nb_07a_ingest_customer_files
                                                       │
                                                       ▼
                                              lh_metadata staged tables (T3)

                    Day 1 → ongoing
                    ───────────────
nb_01_setup_demo_environment
        │
        ▼
nb_05a_publish_synthetic_data_to_sql ──► sqldemo (T1, with new tables/columns)
        │
        ▼
Fabric Mirror ──► OneLake mirrored tables
        │
        ▼
nb_03_pbi_star_schema ──► lh_enercare_demo gold tables
        │
        ▼
nb_02 + nb_04a ──► lh_metadata curation tables populated
        │
        ▼
nb_07b_merge_customer_metadata
   (joins T2 → T3 → semantic model objects)
        │
        ▼
nb_04_sempy_writeback ──► BrookfieldEnercare semantic model annotations (T3 → SM)
        │
        ▼
nb_05_push_qa_verified_answers ──► verified Q&A on SM (preview)
        │
        ▼
Purview scans (SQL + Fabric) ──► T4 asset records
        │
        ▼
nb_07_publish_to_purview (NEW — primary of nb_07 family)
   – domains, data products, glossary, CDEs, role bindings
   – uses Purview SDK + Atlas APIs
        │
        ▼
Manual: Apply Fabric Protection Policies (MIP labels)
        │
        ▼
tools/purview_custom_lineage.py ──► lineage edges already in place
```

### New notebooks/scripts to add

The nb_07 family follows the established `nb_04a → nb_04` convention: integer holds the primary goal; lowercase letters hold supporting sub-steps that run before the primary. Distinct from `nb_06_purview_sql_grants` which lives in the Purview scan-grants family.

| Name | Role | Run order | Lives in |
|------|------|-----------|----------|
| `nb_07a_ingest_customer_files` | support — bulk-load T2 CSVs → `lh_metadata` staging | Phase B step 1 | `fabric/` |
| `nb_07b_merge_customer_metadata` | support — join staged metadata with scanned asset inventory; reconcile | Phase B step 2 | `fabric/` |
| `nb_07_publish_to_purview` | **primary** — push domains, products, glossary, CDEs to Purview via SDK | Phase B step 3 | `fabric/` |
| `tools/sempy_label_writer.py` | helper — write MIP label annotations via Sempy Labs | called from nb_04 | `tools/` |

---

## 5. Coverage Map — Use Case → Source → Demo Evidence

For your demo walkthrough, this is the "every Purview feature has a story" matrix.

| Purview feature                              | Demo evidence shown                                                                                       | Backing data location |
|----------------------------------------------|----------------------------------------------------------------------------------------------------------|----------------------|
| Governance domain hierarchy                  | 3 domains: Customer Ops, Service Delivery, Revenue & Contracts                                            | `domain-charter.csv` → Purview |
| Data products with binding                   | 3 products, each binding ≥1 SQL + ≥1 Fabric + 1 SM asset                                                  | `data-product-catalog.csv` |
| Asset curation                               | Show before/after on `dim_customer` — description and CDE binding                                          | Sempy Labs write |
| Classification fires                         | Scan results show `Person Name`, `Email`, `Canadian SIN`, `Credit Card` classifiers                       | T1 SQL columns |
| Glossary publication                         | ~35 terms with industry vocabulary + acronyms (OEB, CASL, FCR, MRR)                                       | `glossary-master.csv` |
| CDE catalog                                  | ~12 CDEs tied to regulators (PIPEDA, OEB)                                                                  | `cde-catalog.csv` |
| Sensitivity labels                           | Confidential / Highly Confidential labels visible in Fabric on semantic model and lakehouse               | MIP portal → Fabric |
| Steward / owner roles                        | Each domain has named owner, each data product has owner + steward                                         | `role-directory.csv` |
| Lineage                                      | SQL → mirror → semantic model edges already in place via `tools/purview_custom_lineage.py`                | existing |
| Conflict resolution                          | Demo a "scan said X / steward says Y" reconciliation                                                       | `nb_07b_merge_customer_metadata` |
| Industry vocabulary                          | Glossary contains FCR (First Call Resolution), MRR, OEB, PIPEDA, CASL, FSA, etc.                          | `glossary-master.csv` |
| Sensitive PII demonstration                  | DOB, SIN partial, GPS, payment partial — classifiers fire on the synthetic values                         | T1 SQL extensions |
| Regulatory consent (PIPEDA)                  | `customer_consents` table shows opt-in / opt-out per channel                                              | T1 new table |
| Steward workflow                             | Owner directory in SQL + role directory in CSV reconcile on Purview push                                   | T1 + T2 |
| Audit / observability                        | `audit_data_access` table shows who-touched-what-when on sensitive columns                                 | T1 new table |

---

## 6. What's NOT in This Design (Out of Scope for MVP)

Per the brief's "MVP not enterprise" constraint:

- **Bulk CDE import via API** — preview; we'll do up to 12 manually if the API isn't stable
- **>3 domains or >3 products** — proven model can support 200; MVP doesn't need it
- **Custom classifiers** — defer until built-in Microsoft classifiers are proven to fire on the synthetic data
- **Cross-tenant scan** — same-tenant only (brief flagged cross-tenant degrades classification/labeling/policy)
- **Data observability dashboards** — preview, defer
- **Asset curation enablement** — one-way decision per brief; defer until customer asks
- **Full PCI-scope data** — partial only (last 4 digits); never put full PANs in a demo
- **Production-grade synthetic PII generation** — the dataset is realistic enough to fire classifiers, but should not be confused with a privacy-sanitized real dataset

---

## 7. Demo Personnel — Enercare Lineup

The demo's Enercare-side leadership was derived from Brian Lung's correspondence and the 2026-05-20 *Deeper Dive — MSFT <> Enercare — Data Mirroring and Governance* meeting. The current org model (as of 2026-06-04):

| Person | Title | Demo role |
|---|---|---|
| **Victoria Tan** | Chief Customer Officer | Domain Owner DOM-CUSTOPS; Data Product Owner DP-CUST360; Privacy Officer; stakeholder on the other two products |
| **Ranbir Singh** | Enercare Leadership — Data Plane | Domain Owner DOM-SVCDEL; Data Product Owner DP-SVCPERF |
| **Ci Zhu** | Senior Manager, Data Strategy & Analytics | Domain Owner DOM-REVCON; Data Product Owner DP-BILLHEALTH; all tenant-level governance authoring (Governance Domain Creator, Data Governance Admin, Glossary Owner, Label Policy Owner, CDE Catalog Owner) |
| **Rupal Solanki** | Enercare Data & Analytics | Steward DOM-CUSTOPS; Steward DP-CUST360; backup steward DOM-REVCON |
| **Shruthi Srinivas** | Enercare Data & Analytics | Steward DOM-SVCDEL; Steward DP-SVCPERF |

Microsoft delivery team (Alison Pouw, Sean Kelley, Ajay Jagannathan, Brian Lung, Naunihal Singh Sidhu) covers tenant-level Purview operator roles **during build only**. All Microsoft-held governance roles transfer to Ci Zhu (or his nominee) post-handoff; the Data Source Administrator on `Purview-West3` transfers to Enercare ops. These transitions are noted explicitly in the assignment_note column of `role-directory.csv`.

Out of demo scope: Christopher Dingle (VP Data Analytics & Governance at Enercare). His governance authoring duties (glossary, CDEs, label policy, tenant Purview admin) are represented in this demo by Ci Zhu. This is a deliberate scoping choice — not a reflection of his real-world status.

---

## 8. Open Decisions for You

Before generating data:

1. **Tenant boundary for MIP labels** — the brief noted Protection Policies require M365 E3/E5; confirm the demo tenant has the right SKU on `seankelley@MngEnvMCAP660444.onmicrosoft.com`. If not, demo labels via annotation only (won't enforce, but will display).
2. **Glossary parent/child depth** — Purview supports 5 levels; this design uses 2 (domain → term). If you want hierarchy demoed, decide which terms get children.
3. **Custom classifier scope** — for the SIN backstop, the strategy is already in place (see `purview-sin-classifier-backstop.md`). For other custom classifiers (e.g. "Enercare Account Number" pattern `^EC\d{8}$`), skip for MVP unless customer asks.
4. **Verified Q&A scope** — Sempy Labs writes them, but they are Power BI Copilot preview; pick 5 high-confidence question/answer pairs only.

> ✅ **Resolved (2026-06-04):** Synthetic SIN generation — previously open. The three-layer backstop strategy in `purview-sin-classifier-backstop.md` guarantees SIN classification appears in Purview regardless of whether the built-in `MICROSOFT.CANADIAN.SIN` classifier fires on the seed values: Luhn-valid generation (Layer 1) + custom Purview SIT with regex + column-name match (Layer 2) + direct asset annotation as last-resort (Layer 3).

---

## 9. Files Produced With This Design

### Design and strategy docs
| File | Purpose |
|------|---------|
| `output/purview-demo-data-design.md` | This document — placement model and dataset spec |
| `output/purview-sin-classifier-backstop.md` | Three-layer SIN classifier guarantee strategy |
| `output/purview-governance-brief.md` | MS Learn research brief (Tier 4 — Unified Catalog) |

### SQL additions
| File | Purpose |
|------|---------|
| `output/sql-additions/04_purview_demo_extensions.sql` | DDL for the new tables + column additions on the 7 existing source tables |
| `output/sql-additions/05_seed_purview_demo_data.sql` | INSERT statements with synthetic values (SIN columns left NULL — populated by nb_05a via the Luhn generator) |

### Customer-owned external files (T2)
| File | Purpose |
|------|---------|
| `output/customer-files/domain-charter.csv` | 3 governance domains owned by Victoria / Ranbir / Ci Zhu |
| `output/customer-files/data-product-catalog.csv` | 3 data products with asset bindings |
| `output/customer-files/role-directory.csv` | Person ↔ role ↔ domain matrix; the canonical source for who-does-what in the demo |
| `output/customer-files/glossary-master.csv` | ~35 industry/regulatory/business terms; authored by Ci Zhu |
| `output/customer-files/cde-catalog.csv` | ~12 CDEs with regulatory mapping; authored by Ci Zhu |
| `output/customer-files/label-policy.csv` | MIP label taxonomy + assignment rules; authored by Ci Zhu, Privacy escalation through Victoria |

### Tools
| File | Purpose |
|------|---------|
| `output/tools/sin_luhn_generator.py` | Layer 1 — Luhn-valid Canadian SIN generation (self-test passes) |
| `output/tools/purview_create_sin_backstop.py` | Layer 2 — creates the `ENERCARE.PRIVACY.SIN_BACKSTOP` custom SIT via Purview API |

These are sized for an MVP pilot. Scaling them is a copy-paste exercise once the pattern is proven.
