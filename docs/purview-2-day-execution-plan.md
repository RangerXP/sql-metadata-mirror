# Enercare Purview Demo — 2-Day Execution Plan

**Target:** Complete Phase C (agent enablement) within 2 development days.
**Constraint:** Compressed timeline; Phase D (ontology, certified-KPI endorsement workflow) explicitly out of scope.
**North Star:** `docs/purview-maria-north-star-scenario.md` — every day's deliverables either move the Maria scenario closer to passing or are out of scope.
**Owner:** Sean Kelley
**Date authored:** 2026-06-04

## Deferred Backlog (Future Cycle)

1. Governance Agent lifecycle reset is deferred by design.
2. If `Enercare Governance Agent` is deleted for troubleshooting, rebuild it in a future cycle only after standalone operational routing is stable on `Enercare Data Agent West3`.
3. Rebuild scope when resumed: governance-only behavior (glossary, CDEs, labels, policies, lineage) and explicit exclusion of operational request/ticket lookup.

## 2-Day Cadence Map (Locked)

1. Day 0 pre-flight steps run as same-day prep immediately before execution start.
2. Day 1 covers prior Day 1 and Day 2 workstreams.
3. Day 2 covers prior Day 3 through Day 5 workstreams, including Maria scenario E2E and rehearsal.
4. File path remains `docs/purview-2-day-execution-plan.md` for backward compatibility, but operational cadence is 2-day.

## Day 0 — Phase A commit (you, today)

Estimated time: **2 hours**

### Source Control Pattern (Locked)

1. Keep exactly one primary Data Agent folder in git:
`fabric/Enercare Data Agent.DataAgent/`.
2. After any commit that modifies `fabric/*.DataAgent/` or `fabric/*.Notebook/`, run Fabric Source Control update immediately before additional workspace edits.
3. Do not continue notebook execution or live item patching while Source Control shows unresolved conflicts.
4. If a duplicate-name Data Agent conflict occurs, resolve by keeping the git-backed canonical item and removing unbound workspace duplicates before retrying update.

| # | Step | Evidence |
|---|---|---|
| 0.1 | Copy staging tree → demo repo `Documents/Demos/sql-metadata-mirror/` | Git status shows new untracked files in `purview/`, `docs/`, `sql/`, `tools/`, `fabric/nb_05a_*/`, `fabric/nb_06a_*/` |
| 0.2 | Local review of all staged files | One commit on `enercare` branch with message "Phase A — Purview design assets + notebook-based Phase B scaffolding" |
| 0.3 | Confirm M365 E3/E5 SKU on demo tenant `MngEnvMCAP660444.onmicrosoft.com` (gates Phase 5.4 Protection Policies) | Screenshot of admin center license summary |
| 0.4 | Confirm Fabric tenant settings allow sensitivity labels (gates Phase 5.6) | Tenant admin screenshot |
| 0.5 | Confirm asset curation has not yet been enabled (irreversible) | Banner state captured for Day 2 plan |
| 0.6 | Confirm SQL public network access posture matches design (Selected networks + AllowAzureServices + your laptop) — see `design-gap-analysis.md` G7-2 | SSMS connects to `sqldemo` from your laptop |
| 0.7 | Confirm `nb_05a` contains notebook-owned Phase B SQL and optionally upload `tools/` for the SIN helper override | No `/lakehouse/default/Files/sql` upload required; `/lakehouse/default/Files/tools/` is optional because the notebook has a local SIN fallback |

---

## Day 1 — SQL extensions live + customer files ingested (NOTEBOOK-BASED BUILD)

Estimated time: **6–8 hours**

> **Build pattern (locked):** All build steps run from inside Fabric notebooks. SSMS is the **validation surface** only — use it to spot-check row counts, inspect classifications, or run ad-hoc SELECTs. SSMS never executes DDL or DML against the source.
>
> **SQL files** (`sql/04_*.sql`, `sql/05_*.sql`, `sql/06_*.sql`, `sql/07_*.sql`) remain canonical text references. Runtime execution is notebook-owned: `nb_05a` supplies the executable SQL inline and does not read from Lakehouse `Files/sql`.
>
> **Source-control checkpoint (locked):** After any git push that touches Fabric items, immediately run Fabric Source Control update before further workspace edits. This prevents branch/workspace divergence and Data Agent name-collision conflicts.

### Morning — Notebook 1: Extended `nb_05a` (SQL bring-up + Luhn SIN backfill)

Open `fabric/nb_05a_publish_synthetic_data_to_sql.Notebook/`; the Phase B cells are already integrated in the notebook.

| # | Cell | Action | Evidence |
|---|---|---|---|
| 1.1 | nb_05a Cell B1 | Execute notebook-owned Purview extension DDL via the existing pyodbc `conn`; `GO` batches split in-notebook | Output: `DDL applied: notebook-owned Purview demo extensions` |
| 1.1v | nb_05a Cell B2 | Verify: 6 new tables + 9 PII columns | 4 rows, all GREEN |
| 1.2 | nb_05a Cell B3 | Execute notebook-owned Purview seed data | Output: `Seed applied: notebook-owned Purview demo seed data` |
| 1.2v | nb_05a Cell B4 | Verify seed counts | 8 rows: employees=11, zones=8, consents=~120, complaints=18, owner_dir=13, audit=200, customers DOB-backfilled=50, service_accounts GPS-backfilled=56 |
| 1.3 | nb_05a Cell B5 | Backfill Luhn-valid SINs via `tools/sin_luhn_generator.py` (Layer 1 backstop) | `employees.sin_full populated: 11 rows`; `customers.sin_last_4 populated: 50 rows` |
| 1.3v | nb_05a Cell B6 | Spot-check 5 random SINs via `is_luhn_valid()` | `ALL GREEN — Layer 1 backstop ready` |

### Morning — Wait window + Notebook 2: Re-run `nb_03_pbi_star_schema`

| # | Action | Evidence |
|---|---|---|
| 1.4 | Wait for Fabric mirror to pick up new columns and tables (5–15 min). Confirm via OneLake explorer — all 13 source tables visible under `sqldemo` | All 13 tables reflected in OneLake |
| 1.5 | Open `fabric/nb_03_pbi_star_schema.Notebook/` and run end-to-end | Star schema rebuilds without error; row counts include new dimensions |

### Morning — Notebook 3: `nb_06a_create_sin_backstop` (custom Purview SIT)

| # | Cell | Action | Evidence |
|---|---|---|---|
| 1.6 | nb_06a — all cells | Wraps `tools/purview_create_sin_backstop.py`; registers Layer-2 SIT `ENERCARE.PRIVACY.SIN_BACKSTOP` in Purview-West3 via REST API | Verification cell shows: `name: ENERCARE.PRIVACY.SIN_BACKSTOP, status: Enabled, min match %: 50` |

### Afternoon — Notebook 4: Author `nb_07a_ingest_customer_files`

> **Notebook family convention:** `nb_07` is the Purview catalog publication family (distinct from `nb_06` which is Purview admin operations — scan grants, SIT registration). The integer holds the primary goal; lowercase letters hold supporting sub-steps that run before the primary. Mirrors `nb_04a → nb_04`.

| # | Cell | Action | Outcome |
|---|---|---|---|
| 1.7 | nb_07a build | Author `fabric/nb_07a_ingest_customer_files.Notebook/notebook-content.py` with cells: load each CSV from the lakehouse `Files/purview/` mount → validate schema against brief field list → write to `lh_metadata.metadata.*` Delta tables | Notebook stages cleanly |
| 1.8 | nb_07a schema-validation cell | Per-CSV: assert required columns present; assert enum values valid (`domain_type` ∈ {Data domain, Functional unit, Line of business, Regulatory, Project}; `product_type` ∈ {Dataset, Dashboards/Reports, Master and reference data}; `expected_data_type` ∈ {number, text, date, Boolean}) | Validation errors loudly if a column or enum drift detected |
| 1.9 | nb_07a run end-to-end | All 6 `lh_metadata.metadata.*` tables populate | `domains=3, data_products=3, glossary_terms=35, cdes=12, role_assignments=48, label_assignments=9` |

### Optional — SSMS validation (parallel, your call)

These are not build steps. They're spot-checks you can run from SSMS at any point to confirm what the notebooks did.

```sql
-- After 1.1/1.2: confirm shape
SELECT name FROM sys.tables
 WHERE name IN ('employees','service_zones','customer_consents',
                'customer_complaints','data_owners_directory','audit_data_access')
 ORDER BY name;
-- Expect 6 rows.

-- After 1.3: confirm SINs landed
SELECT TOP 5 employee_id, sin_full FROM dbo.employees;
SELECT TOP 5 customer_id, sin_last_4 FROM dbo.customers WHERE sin_last_4 IS NOT NULL;
```

### End-of-day exit criteria

- [ ] All 6 Phase B cells in `nb_05a` ran green (B1→B6)
- [ ] `nb_03_pbi_star_schema` re-ran without error post-mirror
- [ ] `nb_06a_create_sin_backstop` verification cell shows `ENERCARE.PRIVACY.SIN_BACKSTOP` enabled in Purview
- [ ] `nb_07a_ingest_customer_files` runs end-to-end with 6 `lh_metadata` tables populated
- [ ] Phase A + Day 1 notebook commits on `enercare` branch

---

## Day 2 — Sempy writeback + scan + Purview push

Estimated time: **8 hours**

### Morning — Build `nb_07b` (reconcile) and update `nb_04` (SemPy writeback)

| # | Step | Outcome |
|---|---|---|
| 2.1 | Author `fabric/nb_07b_merge_customer_metadata.Notebook/notebook-content.py` (support — runs second in Phase B) | Joins `metadata.glossary_terms` + `metadata.cdes` against the SemPy-read inventory of `BrookfieldEnercare` model; outputs a single enriched DataFrame |
| 2.2 | Extend `nb_04_sempy_writeback` with the merged DataFrame | Per-table, per-column, per-measure descriptions written via SemPy Labs; new annotations `CDE_Member_Of`, `Glossary_Term_References`, `Sensitivity_Label`, `Data_Product_Owner` |
| 2.3 | Run `nb_04` end-to-end | Semantic model `BrookfieldEnercare` shows descriptions on `dim_customer`, `dim_service_account`, the 4 measures; verify via SemPy `list_columns` |

### Afternoon — Phase 0–3 in Purview (domains + data products via SDK)

| # | Step | Outcome |
|---|---|---|
| 2.4 | Phase 0.4 — Asset curation enablement (irreversible) with Ci Zhu / Alison approval | Banner shows curation enabled |
| 2.5 | Author `fabric/nb_07_publish_to_purview.Notebook/notebook-content.py` (**primary** — runs third in Phase B) | Reads `lh_metadata` staged tables; uses Purview SDK to POST domains, data products with asset attachments, glossary terms (Phase 4.1), CDEs (Phase 4.5) |
| 2.6 | Run `nb_07` Phase 1 (assign roles) | Tenant-level Data Governance Admin + Governance Domain Creator assigned per `role-directory.csv` (Ci Zhu, Alison cover) |
| 2.7 | Run `nb_07` Phase 2 (create 3 domains) | Domains exist with two Governance Domain Owners each, status Published |
| 2.8 | Run `nb_07` Phase 3 (3 data products) | Products exist with Type, business_use_case, audience, owners, attached SQL + Fabric + SM assets, access policies, status Published |

### End-of-day exit criteria

- [ ] `BrookfieldEnercare` semantic model has glossary descriptions and CDE annotations visible
- [ ] 3 governance domains and 3 data products visible in Purview Unified Catalog
- [ ] Each data product shows 3+ attached assets

---

## Day 3 — Glossary, CDE, labels, scan, and validation

Estimated time: **8 hours**

### Morning — Phase 4 publication (glossary + CDE)

| # | Step | Outcome |
|---|---|---|
| 3.1 | Run `nb_07` Phase 4.1 (glossary terms) | All 35 terms published with owners, parent, acronyms, resources |
| 3.2 | Run `nb_07` Phase 4.4 (term-related links) | Term → data product / asset / column / CDE links populated where `bound_assets` and `is_cde=1` flags indicate |
| 3.3 | Run `nb_07` Phase 4.5 (CDE creation) | All 12 CDEs published with expected_data_type, owner, status; Add column → bound_columns from CSV |
| 3.4 | Verify Phase 4.6 auto-association | CDE detail page shows associated data products derived from column bindings |

### Afternoon — Phase 5 (sensitivity labels) + Scan re-run

| # | Step | Outcome |
|---|---|---|
| 3.5 | Phase 5.1 — Verify Fabric tenant setting "Allow users to apply sensitivity labels" | Already confirmed Day 0.4 |
| 3.6 | Phase 5.2 — Create 4 sensitivity labels (General / Internal / Confidential / Highly Confidential) | Labels visible in Information Protection portal |
| 3.7 | Phase 5.3 — Publish label policy to pilot users | Label policy shows in admin |
| 3.8 | Phase 5.4 — Configure Protection Policy on Highly Confidential (requires E3/E5; see Day 0.3) | Protection policy visible; covers the 50-policy / 100-user caps |
| 3.9 | Phase 5.6 — Manually apply labels to 9 pilot Fabric assets (3 per data product) | Each item shows label badge |
| 3.10 | Re-run SQL + Fabric scans with custom SIN SIT in rule set | Scan run completed; new classifications surface on `employees.sin_full` and `customers.sin_last_4` |

### End-of-day exit criteria

- [ ] 35 glossary terms visible, with linked data products, assets, columns, CDEs
- [ ] 12 CDEs visible, each auto-associated to its data product
- [ ] 4 labels visible; Highly Confidential carries a Protection Policy (if E3/E5)
- [ ] Classification dashboard shows SIN, PII, financial classifications on the 9 pilot assets
- [ ] Phase A + B commit on `enercare` branch

---

## Day 4 — Phase C: agent enablement (glossary expansion)

Estimated time: **8 hours**

### Morning — Expand glossary with the agent vocabulary

| # | Step | Outcome |
|---|---|---|
| 4.1 | Add equipment ontology terms to `glossary-master.csv`: GT-EQUIP-FURNACE, GT-EQUIP-AC, GT-EQUIP-WATERHEATER, GT-EQUIP-HEATPUMP, GT-EQUIP-HRV, GT-EQUIP-TANKLESS — each with industry acronym, parent GT-EQUIP, definition tied to `equipment_type` enum values | 6 new terms |
| 4.2 | Add agent vocabulary acronyms (HVAC, HRV, AC, WH, HP, Tankless) as either standalone terms or `acronyms` on the equipment terms | Acronyms in CSV |
| 4.3 | Add customer-experience KPI terms: GT-NPS, GT-CSAT, GT-AHT, GT-QASCORE, GT-REPEATCOMPLAINT — bound to `BrookfieldEnercare/_Measures/X` (define the 5 measures in `nb_04` first) | 5 new KPI terms; 5 new SM measures |
| 4.4 | Re-run `nb_07a` (ingest) → `nb_07b` (merge) → `nb_07` Phase 4.1 (republish) | Glossary now ~46 terms; agent vocabulary complete |

### Afternoon — Term-level policies + verified Q&A foundation

| # | Step | Outcome |
|---|---|---|
| 4.5 | Phase 4.2 — Attach term-level access policies to GT-CONSENT, GT-PII, GT-SIN, GT-GEOPII, GT-PCISCOPE | Policies auto-propagate to any asset the term attaches to |
| 4.6 | Update `nb_04` to add 5 customer-experience measures to `BrookfieldEnercare` (NPS, CSAT, AHT, Quality Score, Repeat Complaint Rate) | Measures show in SM; bound to fct_cc_interactions and call-center fact tables |
| 4.7 | Stub 5 verified Q&A entries in `lh_metadata.qa_verified` for the call-center scenarios | Q&A entries ready for SemPy push |

### End-of-day exit criteria

- [ ] Glossary expanded by 11 terms (6 equipment + 5 CX KPIs); republished
- [ ] 5 term-level policies live on regulated terms
- [ ] 5 new SM measures with descriptions
- [ ] 5 verified Q&A entries staged

---

## Day 5 — Maria scenario E2E + demo rehearsal

Estimated time: **8 hours**

### Morning — Verified Q&A push + Maria scenario dry-run

| # | Step | Outcome |
|---|---|---|
| 5.1 | Run `nb_05_push_qa_verified_answers` to push the 5 Q&A entries to `BrookfieldEnercare` | Q&A annotations visible in SM |
| 5.2 | Dry-run the Maria scenario in the Data Agent ("Why hasn't anyone fixed Maria's furnace?") | Agent resolves "furnace" via equipment ontology, surfaces service request status, technician note, contract SLA, billing line items |
| 5.3 | Validate the exec view (Power BI report on `BrookfieldEnercare`) shows the 5 CX KPIs | Dashboard renders; KPIs match SM measures (no drift) |

### Afternoon — Evidence capture + rehearsal

| # | Step | Outcome |
|---|---|---|
| 5.4 | Capture demo evidence: domain list, data product list, glossary term + CDE detail page, lineage view, classification dashboard, label-applied Fabric item, Data Agent answer | Screenshots in `docs/evidence/` |
| 5.5 | Rehearsal pass 1 — Maria call from agent perspective | End-to-end story works |
| 5.6 | Rehearsal pass 2 — Victoria exec review from CCO perspective | KPIs read cleanly |
| 5.7 | Rehearsal pass 3 — Ci Zhu governance walkthrough | Glossary, CDE, term policies, lineage all tell a coherent governance story |

### End-of-day exit criteria

- [ ] Maria scenario answerable by Data Agent end-to-end
- [ ] Exec view (Power BI) renders all 5 CX KPIs from single SM source
- [ ] All evidence captured
- [ ] Final commit: Phase A + B + C complete

---

## Schedule risk register

| Risk | Day at risk | Mitigation |
|---|---|---|
| M365 E3/E5 SKU missing | Day 3 | Day 0.3 verification; if missing, demo labels via annotation only and skip Phase 5.4 |
| Fabric mirror lag on new columns | Day 1 → Day 2 | Run mirror sync explicitly after `04_purview_demo_extensions.sql`; if stuck, manually trigger refresh |
| Purview SDK / CDE API instability | Day 2 → Day 3 | Pre-script both API and portal paths; if API fails, do the 12 CDEs in UI (sub-1hr) |
| Asset curation enablement breaks something | Day 2 | Test in a sandbox catalog if available; Ci Zhu approves on Day 2 only after Day 1 smoke test |
| Custom SIN SIT mis-fires | Day 3 | Day 1 standalone test with sample data via Purview SIT test tool |
| SemPy Labs writeback fails mid-batch | Day 2 → Day 4 | Idempotent writeback; nb_04 re-runs from the merged DataFrame on every cell run |
| Power BI Q&A latency on new measures | Day 5 | Test from Day 4 evening so latency surfaces before rehearsal |

---

## Definition of done

The demo is ready when **all three personas** can be served from the same governed surface, with the same definitions, by the same data products, with no manual reconciliation step:

1. **Tom (agent)** — Asks "what's the status of Maria's furnace?" via Data Agent → gets equipment + service request + technician + SLA + credit eligibility, in business terms
2. **Victoria (CCO)** — Sees a Power BI dashboard with FCR, MTTR, NPS, CSAT, AHT, Quality Score, Repeat Complaint Rate, Churn — same definitions as Tom uses
3. **Ci Zhu (governance)** — Walks the Purview catalog showing domain → data product → glossary term → CDE → label → lineage → certified KPI bound to SM measure — every claim provable

If any persona's view diverges from the others, KPI drift has won and the demo fails on the central thesis.

