[](https://example.com)# Purview Demo — 5-Day Build Runbook

**Audience:** VS Code Copilot / Claude Code agent executing the Phase B + C build, with Sean Kelley (`seankelley@microsoft.com`) as the human-in-the-loop for portal actions.
**Tenant:** `MngEnvMCAP660444.onmicrosoft.com` (demo)
**Subscription:** `bde41857-48c2-4eb5-9959-208f768deafb` (Azure West 3)
**Fabric workspace:** `Purview-West3`
**Source SQL:** `sqlserver-sk2wus3.database.windows.net`, DB `sqldemo`
**Purview account:** `Purview-West3`
**Semantic model:** `BrookfieldEnercare`
**Lakehouse:** `lh_metadata` (default for ingestion + agent build), `lh_demo` (synthetic data primary)
**Repo:** `Documents/Demos/sql-metadata-mirror`, branch `enercare`

---

## How the agent should use this doc

1. **Source of truth:** This runbook supersedes prior plans for execution sequencing. Cross-reference design intent against `docs/purview-demo-data-design.md`, `docs/purview-csv-alignment.md`, `docs/design-gap-analysis.md`, `docs/purview-sin-classifier-backstop.md`, and `docs/purview-maria-north-star-scenario.md`.
2. **Step ownership tags:**
   - `[AGENT]` — VS Code can do this directly (edit a file, run a shell command, commit to git, author notebook content)
   - `[HUMAN]` — Sean does this (Fabric portal click, Purview portal action, screenshot, MFA-gated operation)
   - `[BOTH]` — Agent prepares the artifact; Sean executes it in Fabric / Purview
3. **Verification gates:** Every step has a `Verify` block. Do not advance until the verification passes. If a `[HUMAN]` verification step is pending, surface it and wait.
4. **Task tracking:** Use your task tool to mirror each numbered step. Mark `in_progress` before starting; `completed` after verification passes.
5. **Commits:** Each day has an explicit evening commit. Do not commit mid-day unless a step says to.
6. **Failure recovery:** Every step has a `If it errors` block. Apply the recovery first; escalate only if the recovery fails.
7. **Never improvise scope:** If a step's verification gate cannot be satisfied with the inputs as defined, stop and ask. Do not add features, retries, or "while I'm here" cleanups.

---

## Repository conventions

### File layout (after Day 0)

```
docs/
  purview-demo-data-design.md
  purview-csv-alignment.md
  purview-sin-classifier-backstop.md
  purview-maria-north-star-scenario.md
  purview-design-readiness-assessment.md
  design-gap-analysis.md
  purview-5-day-execution-plan.md
  purview-5-day-runbook.md        ← THIS FILE
purview/
  domain-charter.csv              (3 rows)
  data-product-catalog.csv        (3 rows)
  glossary-master.csv             (35 rows → 46 after Day 4)
  cde-catalog.csv                 (12 rows)
  role-directory.csv              (48 rows)
  label-policy.csv                (9 rows)
sql/
  01_create_tables.sql            (existing)
  02_create_views.sql             (existing)
  03_purview_scan_grants.sql      (existing)
  04_purview_demo_extensions.sql  (NEW Phase A)
  05_seed_purview_demo_data.sql   (NEW Phase A)
tools/
  sin_luhn_generator.py           (NEW Phase A)
  purview_create_sin_backstop.py  (NEW Phase A)
fabric/
  nb_01_*..nb_06_*.Notebook/      (existing)
  nb_05a_publish_synthetic_data_to_sql.Notebook/
    notebook-content.py           (existing, Phase B cells appended Day 1)
    phase_b_cell_additions.py     (NEW Phase A — to be appended to notebook-content.py on Day 1)
  nb_06a_create_sin_backstop.Notebook/
    notebook-content.py           (NEW Phase A)
  nb_07a_ingest_customer_files.Notebook/   (BUILT Day 1 afternoon)
  nb_07b_merge_customer_metadata.Notebook/ (BUILT Day 2 morning)
  nb_07_publish_to_purview.Notebook/       (BUILT Day 2 afternoon)
```

### Notebook family convention

- `nb_NN` = primary notebook for a family
- `nb_NNa`, `nb_NNb` = support notebooks that run **before** the primary
- Example: `nb_07a` (ingest CSVs) → `nb_07b` (merge with SM inventory) → `nb_07` (publish to Purview)
- This mirrors the existing `nb_04a → nb_04` pattern

### SQL build pattern (locked)

- SQL DDL/seed lives in `sql/*.sql` as canonical text
- Execution always runs from a Fabric notebook cell using `pyodbc`
- SSMS is for **validation only** (spot-checks, classification inspection, ad-hoc SELECT)
- Never execute DDL from SSMS — it would diverge from the notebook-replayable record

### Lakehouse file paths (referenced by notebooks)

| Mount path | Contents |
|---|---|
| `/lakehouse/default/Files/sql/` | `04_purview_demo_extensions.sql`, `05_seed_purview_demo_data.sql` |
| `/lakehouse/default/Files/tools/` | `sin_luhn_generator.py` |
| `/lakehouse/default/Files/purview/` | 6 CSVs |

---

## Pre-flight — Day 0 (you, before Day 1 starts)

### Objective
Phase A staging is committed to the demo repo; lakehouse Files mount has SQL/tools/CSVs ready; SQL public network access confirmed working from your laptop and from Fabric workspace identity.

### Inputs
- Staging tree at `/mnt/workspace/output/repo-staging/` (19 files)
- Demo repo cloned locally at `~/Documents/Demos/sql-metadata-mirror`, branch `enercare`

### Steps

**0.1 [AGENT]** Copy staging tree into the demo repo.
```bash
cd ~/Documents/Demos/sql-metadata-mirror
git checkout enercare
git status   # must be clean
# Copy staging tree (path adjusted to where the staging tree is delivered)
rsync -av /path/to/repo-staging/ ./
git status   # expect 19 new files
```
**Verify:** `git status` shows new untracked files under `docs/`, `purview/`, `sql/`, `tools/`, `fabric/nb_05a_*/`, `fabric/nb_06a_*/`.

**0.2 [AGENT]** Commit Phase A.
```bash
git add docs/ purview/ sql/ tools/ \
        fabric/nb_05a_publish_synthetic_data_to_sql.Notebook/phase_b_cell_additions.py \
        fabric/nb_06a_create_sin_backstop.Notebook/
git commit -m "Phase A — Purview design assets + notebook-based Phase B scaffolding"
```
**Verify:** `git log -1 --stat` shows ~19 files in the commit.

**0.3 [HUMAN]** Confirm M365 E3/E5 SKU on `MngEnvMCAP660444.onmicrosoft.com`.
**Verify:** Screenshot of admin center license summary saved to `docs/evidence/day0-licenses.png`. If E3/E5 missing, flag for Day 3 step 3.8 (skip Protection Policy).

**0.4 [HUMAN]** Confirm Fabric tenant setting "Allow users to apply sensitivity labels" is enabled.
**Verify:** Screenshot saved to `docs/evidence/day0-fabric-labels-setting.png`. If disabled, request tenant admin enable before Day 3.

**0.5 [HUMAN]** Confirm asset curation is **not** yet enabled in Purview-West3 (it's irreversible — Day 2 step 2.4 turns it on).
**Verify:** Screenshot of Purview banner state saved to `docs/evidence/day0-curation-banner.png`.

**0.6 [HUMAN]** Confirm SQL public network access matches `docs/design-gap-analysis.md` §G7-2 posture: *Selected networks ON + AllowAzureServices exception ON*. SSMS connects from your laptop (already verified).
**Verify:** SSMS successful connection to `sqldemo` from MSFT VPN.

**0.7 [HUMAN + AGENT]** Upload `sql/` and `tools/` to lakehouse Files mount.
- Fabric portal → `Purview-West3` → `lh_metadata` → `Files` → Upload `sql/04_purview_demo_extensions.sql`, `sql/05_seed_purview_demo_data.sql` into `Files/sql/`
- Upload `tools/sin_luhn_generator.py` into `Files/tools/`

**Verify:** From any Fabric notebook cell, run:
```python
import os
assert "04_purview_demo_extensions.sql" in os.listdir("/lakehouse/default/Files/sql")
assert "05_seed_purview_demo_data.sql" in os.listdir("/lakehouse/default/Files/sql")
assert "sin_luhn_generator.py" in os.listdir("/lakehouse/default/Files/tools")
print("Files mount verified")
```

### Exit criteria
- [ ] 0.1–0.7 all verified
- [ ] Phase A commit on `enercare` branch
- [ ] Lakehouse Files mount has SQL + tools

---

## Day 1 — SQL extensions live + customer files ingested

### Objective
Phase B SQL extensions deployed; SINs populated (Luhn-valid); Fabric mirror reflects 13 tables; custom Purview SIT registered; `lh_metadata.metadata.*` tables populated from the 6 CSVs.

### Inputs
- Day 0 exit criteria met
- `nb_05a_publish_synthetic_data_to_sql` exists in `Purview-West3` workspace from prior work

### Outputs
- `dbo.employees`, `dbo.service_zones`, `dbo.customer_consents`, `dbo.customer_complaints`, `dbo.data_owners_directory`, `dbo.audit_data_access` populated in SQL
- `dbo.customers.sin_last_4`, `dbo.employees.sin_full`, `dbo.customers.date_of_birth`, `dbo.service_accounts.installation_address_lat/lon` populated
- OneLake mirror reflects 13 SQL tables
- Custom SIT `ENERCARE.PRIVACY.SIN_BACKSTOP` registered in Purview
- `lh_metadata.metadata.domains|data_products|glossary_terms|cdes|role_assignments|label_assignments` populated

### Steps

**1.1a [HUMAN]** Open `nb_05a_publish_synthetic_data_to_sql` in Fabric. Confirm the existing `conn = pyodbc.connect(...)` cell at the top runs cleanly (verifies SQL connectivity from Fabric workspace identity).

**1.1b [HUMAN]** Append the six Phase B cells from `fabric/nb_05a_publish_synthetic_data_to_sql.Notebook/phase_b_cell_additions.py` into `nb_05a`. The file is divided by `# CELL B1` … `# CELL B6` markers — paste each block as a new Fabric cell at the bottom of the notebook, in order.
**Verify:** Six new cells (B1–B6) visible at the bottom of `nb_05a`.

**1.1c [HUMAN]** Run Cell B1 (execute `sql/04_purview_demo_extensions.sql` DDL).
**Expected output:** `DDL applied: 04_purview_demo_extensions.sql`
**Verify (Cell B2):** 4 rows, all GREEN.
**If B1 errors:**
- `Invalid object name 'dbo.customers'` → re-run notebook from top so existing schema lands first.
- `There is already an object named '<table>'` → DDL ran already; skip B1, advance to B2.

**1.2 [HUMAN]** Run Cell B3 (execute `sql/05_seed_purview_demo_data.sql`).
**Expected output:** `Seed applied: 05_seed_purview_demo_data.sql`
**Verify (Cell B4):** 8 rows with counts:
```
employees                       11
service_zones                    8
customer_consents              ~120
customer_complaints             18
data_owners_directory           13
audit_data_access              200
customers DOB-backfilled        50
service_accounts GPS-backfilled 56
```
**If B3 errors on duplicate key:** seed already ran; the seed uses `MERGE` so this should be safe — re-running is idempotent. Advance to B4.

**1.3 [HUMAN]** Run Cell B5 (Layer-1 Luhn SIN backfill).
**Expected output:** `employees.sin_full populated: 11 rows` and `customers.sin_last_4 populated: 50 rows`
**Verify (Cell B6):** `ALL GREEN — Layer 1 backstop ready` and `5/5 SINs Luhn-valid`.
**If B5 errors `ModuleNotFoundError: sin_luhn_generator`:** Step 0.7 upload of `tools/sin_luhn_generator.py` did not complete. Re-upload and re-run B5.

**1.3v [HUMAN]** Save `nb_05a` (top-right floppy icon).

**1.4 [HUMAN]** Wait for Fabric mirror to pick up new tables/columns (5–15 min). Open `sqldemo` in Purview-West3 → check last sync time advances → confirm 13 tables visible in OneLake explorer under the mirror.
**Verify:** OneLake shows 13 tables under `sqldemo` (7 original + 6 new).
**If mirror lag exceeds 30 min:** in mirror status page, click "Stop replication" then "Start replication" to force a re-sync.

**1.5 [HUMAN]** Open `nb_03_pbi_star_schema` in Fabric → Run all.
**Verify:** No errors. Final summary cell shows row counts that include the new dims/facts.
**If it errors on missing columns:** mirror hasn't synced yet — re-check 1.4, wait 5 min, re-run.

**1.6a [HUMAN]** Stage `nb_06a_create_sin_backstop` in Fabric.
- Fabric portal → `Purview-West3` → New → Notebook → name it `nb_06a_create_sin_backstop`
- Set default lakehouse to `lh_metadata`
- Open `fabric/nb_06a_create_sin_backstop.Notebook/notebook-content.py` from the staging tree
- Paste each cell (5 total) into the new Fabric notebook in order
- Save

**1.6b [HUMAN]** Run `nb_06a` end-to-end.
**Expected output (final cell):**
```
✓ Classification: ENERCARE.PRIVACY.SIN_BACKSTOP
  status: Enabled
  min match %: 50
  description: Luhn-valid 9-digit Canadian SIN backstop
```
**Verify:** Purview portal → Data Map → Classifications → Custom → `ENERCARE.PRIVACY.SIN_BACKSTOP` is listed and Enabled. Screenshot to `docs/evidence/day1-sin-sit-registered.png`.
**If 401/403:** the authenticating identity needs Purview Data Curator or Data Source Administrator. You and Alison already have this — confirm the auth cell picked up your interactive identity, not the workspace MSI. If running as MSI, grant `Microsoft.Purview/account/scan/datasources/...` permissions to the workspace identity in Purview.
**If 409 (already exists):** SIT was already registered. Re-run the verify cell only; advance.

**1.7 [HUMAN]** Upload the 6 CSVs from `purview/` to `lh_metadata/Files/purview/`.
- Fabric portal → `lh_metadata` → Files → Upload all 6 CSVs into a `Files/purview/` folder.
**Verify:** From a notebook cell:
```python
import os
expected = {"domain-charter.csv","data-product-catalog.csv","glossary-master.csv",
            "cde-catalog.csv","role-directory.csv","label-policy.csv"}
assert expected.issubset(set(os.listdir("/lakehouse/default/Files/purview")))
```

**1.8 [AGENT]** Author `fabric/nb_07a_ingest_customer_files.Notebook/notebook-content.py` and its `.platform` metadata file in the staging tree (and commit). The notebook reads each CSV from `/lakehouse/default/Files/purview/`, validates schema against `docs/purview-csv-alignment.md`, and writes Delta tables to `lh_metadata.metadata.*`.

Required cells (in order):
1. **Config + imports:** `CSV_ROOT = "/lakehouse/default/Files/purview"`; `SCHEMA = "metadata"`; `import pandas as pd`, `from pyspark.sql import SparkSession`.
2. **Helper `validate_csv(df, required_cols, enum_cols)`** — asserts required columns present; asserts enum values are within allowed sets. Raises `ValueError` with a clear message on any drift.
3. **`domain-charter.csv`** — required cols: `domain_id, domain_name, domain_type, description, parent_domain, status, governance_domain_owners, governance_domain_creators`. Enum: `domain_type ∈ {Data domain, Functional unit, Line of business, Regulatory, Project}`. Write to `lh_metadata.metadata.domains`.
4. **`data-product-catalog.csv`** — required cols: `data_product_id, data_product_name, product_type, business_use_case, audience, owners, attached_assets, access_policy, status, parent_domain_id`. Enum: `product_type ∈ {Dataset, Dashboards/Reports, Master and reference data}`. Write to `lh_metadata.metadata.data_products`.
5. **`glossary-master.csv`** — required cols per design doc §Glossary master: 18 columns. Write to `lh_metadata.metadata.glossary_terms`.
6. **`cde-catalog.csv`** — required cols: `cde_id, cde_name, expected_data_type, business_definition, owner_role, status, parent_glossary_term, bound_columns`. Enum: `expected_data_type ∈ {number, text, date, Boolean}`. Write to `lh_metadata.metadata.cdes`.
7. **`role-directory.csv`** — required cols: `role_id, principal_email, principal_display_name, role_type, scope_target, scope_target_type, governance_layer`. Write to `lh_metadata.metadata.role_assignments`.
8. **`label-policy.csv`** — required cols: `label_id, label_name, sensitivity_tier, protection_policy, applies_to_asset_ids, scope`. Write to `lh_metadata.metadata.label_assignments`.
9. **Summary:** `SELECT 'domains' AS t, COUNT(*) FROM lh_metadata.metadata.domains UNION ALL ... ORDER BY t` — print expected vs actual counts.

Commit:
```bash
git add fabric/nb_07a_ingest_customer_files.Notebook/
git commit -m "Day 1 — nb_07a_ingest_customer_files (schema-validated CSV → lh_metadata)"
```

**1.9 [HUMAN]** Stage `nb_07a` in Fabric (copy cells from staged `notebook-content.py` into a new Fabric notebook) and run end-to-end.
**Verify:** Summary cell shows:
```
domains              3
data_products        3
glossary_terms      35
cdes                12
role_assignments    48
label_assignments    9
```
**If schema validation fires:** Stop. The CSV drifted from the alignment doc. Restore the failing CSV from the staging tree and re-run.

### Day 1 evening commit
```bash
# AGENT
git add fabric/nb_07a_ingest_customer_files.Notebook/
git commit -m "Day 1 — Phase B notebooks live; SQL extensions + SIN SIT + lh_metadata populated"
```

### Day 1 exit criteria
- [ ] `nb_05a` Phase B cells B1–B6 all green
- [ ] OneLake mirror reflects 13 tables
- [ ] `nb_03_pbi_star_schema` re-ran without error
- [ ] `ENERCARE.PRIVACY.SIN_BACKSTOP` registered + enabled in Purview
- [ ] `nb_07a` populated 6 `lh_metadata.metadata.*` tables to expected counts
- [ ] Day 1 commit on `enercare` branch

---

## Day 2 — Sempy writeback + Purview Phase 0–3 (roles, domains, data products)

### Objective
Semantic model `BrookfieldEnercare` carries glossary descriptions and CDE annotations on the columns and measures that bind to them; asset curation is enabled (irreversible); Purview catalog has 3 domains and 3 data products published, each with attached assets.

### Inputs
- Day 1 exit criteria met
- SemPy Labs available in Fabric Python notebook environment

### Outputs
- `BrookfieldEnercare` semantic model has descriptions on key columns and the 4 existing measures
- New annotations on the SM: `CDE_Member_Of`, `Glossary_Term_References`, `Sensitivity_Label`, `Data_Product_Owner`
- Asset curation enabled in Purview-West3 (irreversible)
- Phase 0 roles assigned (Tenant DG Admin + Governance Domain Creator)
- Phase 2: 3 governance domains published
- Phase 3: 3 data products published with assets, owners, policies

### Steps

**2.1 [AGENT]** Author `fabric/nb_07b_merge_customer_metadata.Notebook/notebook-content.py`. The notebook reads `lh_metadata.metadata.glossary_terms` + `metadata.cdes`, reads the SemPy inventory of `BrookfieldEnercare` (`list_tables`, `list_columns`, `list_measures`), joins them on column and measure paths from `glossary-master.csv.bound_assets` and `cde-catalog.csv.bound_columns`, and writes a single Delta table `lh_metadata.metadata.sm_annotations` with one row per (table, column-or-measure, annotation_key, annotation_value).

Required cells:
1. Imports + config (`SEMANTIC_MODEL = "BrookfieldEnercare"`)
2. Read `lh_metadata.metadata.glossary_terms`, `metadata.cdes`, `metadata.data_products` as Spark DataFrames
3. Use `import sempy.fabric as fabric` → `list_tables`, `list_columns`, `list_measures` on `SEMANTIC_MODEL` → assemble inventory
4. Parse `bound_assets` (glossary) and `bound_columns` (CDE) — formats per `docs/purview-csv-alignment.md` §"Bound assets format"
5. Build the annotation DataFrame: one row per binding, with columns `model, table, object_type ∈ {Column, Measure}, object_name, annotation_key ∈ {CDE_Member_Of, Glossary_Term_References, Sensitivity_Label, Data_Product_Owner}, annotation_value`
6. Write to `lh_metadata.metadata.sm_annotations` (overwrite)
7. Summary: count of annotations per `annotation_key`

Commit:
```bash
git add fabric/nb_07b_merge_customer_metadata.Notebook/
git commit -m "Day 2 — nb_07b: merge glossary + CDE with BrookfieldEnercare inventory"
```

**2.2 [HUMAN]** Stage `nb_07b` in Fabric and run end-to-end.
**Verify:** Summary shows ≥1 annotation per key, with expected counts:
- `CDE_Member_Of` ≥ 12
- `Glossary_Term_References` ≥ 20
- `Sensitivity_Label` ≥ 9 (from `label-policy.csv.applies_to_asset_ids`)
- `Data_Product_Owner` ≥ 3

**2.3 [AGENT]** Extend existing `nb_04_sempy_writeback` with a new cell block that reads `lh_metadata.metadata.sm_annotations` and uses SemPy Labs writeback to apply descriptions and annotations to `BrookfieldEnercare`.

Add cells (append to `nb_04`):
1. Read `lh_metadata.metadata.sm_annotations`
2. For each row, call the appropriate SemPy Labs function:
   - `Description` (the column or measure description text from `glossary-master.csv.definition` joined via `Glossary_Term_References`) → `update_column(...)`, `update_measure(...)`
   - `CDE_Member_Of`, `Glossary_Term_References`, `Sensitivity_Label`, `Data_Product_Owner` → `set_annotation(...)`
3. Confirmation cell: re-read `list_columns` + annotations and verify the writes persisted

Commit:
```bash
git add fabric/nb_04_sempy_writeback.Notebook/notebook-content.py
git commit -m "Day 2 — nb_04 extended with annotation writeback from sm_annotations"
```

**2.4 [HUMAN]** Run `nb_04` end-to-end.
**Verify:**
- Power BI service → `BrookfieldEnercare` → Data hub → confirm descriptions on `dim_customer`, `dim_service_account`, the 4 measures
- SemPy spot-check from a notebook cell:
```python
import sempy.fabric as fabric
cols = fabric.list_columns("BrookfieldEnercare")
print(cols[cols["Description"].notna()].head(20))
```
**If writeback fails on auth:** SemPy uses the running user's identity. Confirm Sean has Member or Admin on the workspace.

**2.5 [HUMAN — APPROVAL GATE]** Phase 0.4 — Asset curation enablement.
This is **irreversible**. Before clicking enable:
- Confirm Day 0.5 baseline screenshot exists
- Confirm Day 1 smoke test (1.6 SIT registration) succeeded — proves Purview API path works
- Coordinate with Ci Zhu / Alison per `docs/purview-design-readiness-assessment.md` §Phase 0.4

Once approved: Purview portal → Data Map → Settings → Asset curation → Enable.
**Verify:** Banner change captured in `docs/evidence/day2-curation-enabled.png`.

**2.6 [AGENT]** Author `fabric/nb_07_publish_to_purview.Notebook/notebook-content.py` — the primary Phase B publication notebook.

Required cells (in order — each Phase is one logical cell or a small block):

**Cell 1 — Config + auth:**
```python
PURVIEW_ACCOUNT = "Purview-West3"
PURVIEW_REGION  = "westus3"
from azure.identity import DefaultAzureCredential
from azure.purview.catalog import PurviewCatalogClient
cred = DefaultAzureCredential()
client = PurviewCatalogClient(f"https://{PURVIEW_ACCOUNT}.purview.azure.com", credential=cred)
```

**Cell 2 — Phase 1: Assign tenant-level roles** (read `lh_metadata.metadata.role_assignments` filtered to `governance_layer = 'Tenant'`):
- POST roles per `role-directory.csv` §Tenant scope rows (Ci Zhu = Data Governance Admin; Alison = Governance Domain Creator)
- Use Purview RBAC API or surface a list of required Entra group assignments if API path is gated

**Cell 3 — Phase 2: Create 3 governance domains** (read `lh_metadata.metadata.domains`):
- For each row: POST domain with name, description, type, status=Draft, then PATCH owners (two Governance Domain Owners per domain), then PUBLISH

**Cell 4 — Phase 3: Create 3 data products** (read `lh_metadata.metadata.data_products`):
- For each row: POST data product with type, business_use_case, audience, parent_domain_id, status=Draft
- PATCH owners
- For each entry in `attached_assets`: resolve asset by qualified name (SQL table FQN, Fabric item ID, or SM measure path), POST asset link
- PATCH access_policy
- PUBLISH

**Cell 5 — Summary:** GET each domain + product, print published status + counts of attached assets.

Commit:
```bash
git add fabric/nb_07_publish_to_purview.Notebook/
git commit -m "Day 2 — nb_07_publish_to_purview Phases 1-3 (roles, domains, data products)"
```

**2.7 [HUMAN]** Stage `nb_07` in Fabric. Run Cell 1 + Cell 2 (Phase 1 roles).
**Verify:** Purview → Data Map → Collections → Role assignments → Ci Zhu shown as Data Governance Admin; Alison as Governance Domain Creator. Screenshot to `docs/evidence/day2-phase1-roles.png`.

**2.8 [HUMAN]** Run Cell 3 (Phase 2 domains).
**Verify:** Purview → Unified Catalog → Governance domains → 3 domains visible, each Published, each with 2 owners. Screenshot to `docs/evidence/day2-phase2-domains.png`.

**2.9 [HUMAN]** Run Cell 4 (Phase 3 data products).
**Verify:** Purview → Unified Catalog → Each data product page shows: Type, Business use case, Audience, Owners (≥1), Attached assets (≥3 per product), Access policy, status Published. Screenshot to `docs/evidence/day2-phase3-products.png`.
**If asset attachment fails (asset not found):** the asset's qualified name needs to be confirmed. Print the asset's expected qualified name vs what Purview shows in the Data Map for that asset, fix the mapping in the publication cell, re-run.

### Day 2 evening commit
```bash
# AGENT
git add docs/evidence/
git commit -m "Day 2 — SemPy writeback live; asset curation enabled; Purview Phases 1-3 published"
```

### Day 2 exit criteria
- [ ] `BrookfieldEnercare` shows glossary descriptions + CDE annotations
- [ ] Asset curation enabled in Purview-West3
- [ ] 3 governance domains visible, Published, 2 owners each
- [ ] 3 data products visible, Published, ≥3 attached assets each
- [ ] Day 2 commit on `enercare` branch

---

## Day 3 — Glossary, CDE, sensitivity labels, scan re-run

### Objective
All 35 glossary terms and 12 CDEs published in Purview with relationships; 4 sensitivity labels created and policy published; pilot Fabric assets labeled; SQL + Fabric scans re-run with custom SIN SIT and classifications visible.

### Inputs
- Day 2 exit criteria met
- `nb_07_publish_to_purview` has Phase 4 cells (to be added in this day's morning)

### Outputs
- 35 glossary terms in Purview with owners, parent, acronyms, resources, related-asset/term links
- 12 CDEs in Purview, each with expected_data_type, owner, bound columns, auto-associated data product
- 4 sensitivity labels in M365 Information Protection
- Highly Confidential carries a Protection Policy (if E3/E5 available)
- 9 pilot Fabric assets labeled (3 per data product)
- Scan re-run completed; SIN classifications visible on `employees.sin_full` and `customers.sin_last_4`

### Steps

**3.1 [AGENT]** Extend `nb_07_publish_to_purview` with Phase 4.1, 4.4, 4.5, 4.6 cells.

Add cells (append):

**Cell 6 — Phase 4.1: Publish glossary terms** (read `lh_metadata.metadata.glossary_terms`):
- For each row: POST term with name, definition, parent_term (resolve parent_id from prior creates), acronyms, resources, owners, status, attached data products from `bound_assets` (data-product references only — column/asset links happen in 4.4)

**Cell 7 — Phase 4.4: Term-related links** (re-read glossary, this time process `bound_assets` entries that point at columns, assets, CDEs):
- For each term: parse `bound_assets`; POST relationship `term → asset/column/CDE` per type

**Cell 8 — Phase 4.5: Publish CDEs** (read `lh_metadata.metadata.cdes`):
- For each row: POST CDE with name, expected_data_type, business_definition, owner_role, status, parent_glossary_term, then for each entry in `bound_columns`: POST Add column relationship

**Cell 9 — Phase 4.6 verification: Auto-association check:**
- For each CDE, GET its detail; assert `associated_data_products` is non-empty (auto-derived from column bindings)

Commit:
```bash
git add fabric/nb_07_publish_to_purview.Notebook/notebook-content.py
git commit -m "Day 3 — nb_07 Phase 4 (glossary, term links, CDE) cells"
```

**3.2 [HUMAN]** Run Cell 6 (Phase 4.1).
**Verify:** Purview → Glossary → 35 terms listed. Spot-check 3 terms (`GT-PII`, `GT-CONSENT`, `GT-FCR`): each has definition, parent, owner, resources. Screenshot to `docs/evidence/day3-phase4.1-glossary.png`.
**If 429:** wait 60 sec, re-run cell — Purview rate-limits batch POST.

**3.3 [HUMAN]** Run Cell 7 (Phase 4.4).
**Verify:** Spot-check `GT-PII`: detail page shows related assets and CDEs. Screenshot to `docs/evidence/day3-phase4.4-term-links.png`.

**3.4 [HUMAN]** Run Cell 8 (Phase 4.5).
**Verify:** Purview → CDEs → 12 CDEs listed. Spot-check `CDE-CUST-ID`: detail shows bound columns (`customers.customer_id`, `service_accounts.customer_id`, etc.). Screenshot to `docs/evidence/day3-phase4.5-cdes.png`.

**3.5 [HUMAN]** Run Cell 9 (Phase 4.6 verification).
**Verify:** Output shows each CDE has ≥1 associated data product (auto-derived). Screenshot to `docs/evidence/day3-phase4.6-cde-auto-assoc.png`.

**3.6 [HUMAN]** Phase 5.2 — Create 4 sensitivity labels in M365 Information Protection portal.
Labels per `label-policy.csv` §Tier rows:
- `General` (Public-equivalent)
- `Internal` (default)
- `Confidential`
- `Highly Confidential`
**Verify:** Compliance portal → Information protection → Labels → all 4 visible. Screenshot to `docs/evidence/day3-phase5.2-labels.png`.

**3.7 [HUMAN]** Phase 5.3 — Publish label policy to pilot users (you, Alison, Ci Zhu).
**Verify:** Compliance portal → Label policies → pilot policy active, scoped to pilot users.

**3.8 [HUMAN — CONDITIONAL]** Phase 5.4 — Configure Protection Policy on `Highly Confidential`. **Requires M365 E3/E5** (verified Day 0.3). If E3/E5 not available, skip and annotate the gap in `docs/evidence/day3-phase5.4-skipped.md`.
**Verify:** Protection policy visible in Compliance portal; access restricted to label-eligible users. Screenshot to `docs/evidence/day3-phase5.4-protection-policy.png`.

**3.9 [HUMAN]** Phase 5.6 — Manually apply labels to 9 pilot Fabric assets (3 per data product) per `label-policy.csv.applies_to_asset_ids`.
**Verify:** Each Fabric item shows label badge in the Fabric portal. Screenshot to `docs/evidence/day3-phase5.6-labeled-assets.png` (collage of 9 items or 3 representative).

**3.10 [HUMAN]** Re-run Purview scans with custom SIN SIT in the rule set.
- Purview portal → Data Map → Scan rule sets → System default (or your active rule set) → Add classification → `ENERCARE.PRIVACY.SIN_BACKSTOP` → Save
- Run the SQL scan against `sqldemo`
- Run the Fabric scan against `Purview-West3` workspace
**Verify:** Scan run history shows both scans completed. Open `employees` → Schema → confirm `sin_full` column has the new SIN classification applied. Same for `customers.sin_last_4`. Screenshot to `docs/evidence/day3-scan-sin-classified.png`.
**If scan fails on auth:** confirm Purview Managed Identity has `db_datareader` (per `sql/03_purview_scan_grants.sql`) — should already be in place from prior work.

### Day 3 evening commit
```bash
# AGENT
git add fabric/nb_07_publish_to_purview.Notebook/ docs/evidence/
git commit -m "Day 3 — Phase 4 glossary/CDE + Phase 5 labels + scan with SIN SIT classifying"
```

### Day 3 exit criteria
- [ ] 35 glossary terms visible with linked data products, assets, columns, CDEs
- [ ] 12 CDEs visible, each auto-associated to its data product
- [ ] 4 labels visible; Highly Confidential carries Protection Policy (if E3/E5)
- [ ] Classification dashboard shows SIN + other classifications on labeled assets
- [ ] Phase A + B commit on `enercare` branch

---

## Day 4 — Phase C: agent enablement (glossary expansion + term policies)

### Objective
Glossary expanded with the agent vocabulary needed for the Maria scenario (6 equipment terms + 5 CX KPIs); term-level access policies on regulated terms; 5 new CX measures on `BrookfieldEnercare` with descriptions.

### Inputs
- Day 3 exit criteria met
- `purview/glossary-master.csv` (35 rows)

### Outputs
- `glossary-master.csv` updated to 46 rows (35 + 11)
- 5 term-level access policies live on regulated terms
- 5 new SM measures on `BrookfieldEnercare` (NPS, CSAT, AHT, Quality Score, Repeat Complaint Rate)
- 5 verified Q&A entries staged in `lh_metadata.metadata.qa_verified`

### Steps

**4.1 [AGENT]** Update `purview/glossary-master.csv` — add 11 rows:

Equipment ontology (6 rows, parent = `GT-EQUIP`):
- `GT-EQUIP-FURNACE` — acronym: Furnace; definition tied to `equipment_type = 'Furnace'` in `dbo.service_accounts`
- `GT-EQUIP-AC` — acronym: AC; definition tied to `equipment_type = 'Air Conditioner'`
- `GT-EQUIP-WATERHEATER` — acronym: WH; definition tied to `equipment_type = 'Water Heater'`
- `GT-EQUIP-HEATPUMP` — acronym: HP; definition tied to `equipment_type = 'Heat Pump'`
- `GT-EQUIP-HRV` — acronym: HRV; definition tied to `equipment_type = 'HRV'`
- `GT-EQUIP-TANKLESS` — acronym: Tankless; definition tied to `equipment_type = 'Tankless Water Heater'`

CX KPI terms (5 rows, parent = `GT-CX-METRIC`):
- `GT-NPS` — definition: Net Promoter Score; bound to `BrookfieldEnercare/_Measures/NPS`
- `GT-CSAT` — definition: Customer Satisfaction Score; bound to `_Measures/CSAT`
- `GT-AHT` — definition: Average Handle Time; bound to `_Measures/AvgHandleTime`
- `GT-QASCORE` — definition: Call Quality Assurance Score; bound to `_Measures/QAScore`
- `GT-REPEATCOMPLAINT` — definition: Repeat Complaint Rate; bound to `_Measures/RepeatComplaintRate`

Commit:
```bash
git add purview/glossary-master.csv
git commit -m "Day 4 — Glossary expansion: 6 equipment terms + 5 CX KPIs (35 → 46)"
```

**4.2 [HUMAN]** Re-upload updated `glossary-master.csv` to `lh_metadata/Files/purview/` (overwrite).

**4.3 [HUMAN]** Re-run `nb_07a` (ingest) → `nb_07b` (merge).
**Verify:**
- `nb_07a` summary shows `glossary_terms 46`
- `nb_07b` summary shows additional annotations from the new terms

**4.4 [HUMAN]** Re-run `nb_07` Cell 6 (Phase 4.1 republish — idempotent; PATCH on existing, POST on new).
**Verify:** Purview → Glossary → 46 terms listed. Spot-check `GT-EQUIP-FURNACE` and `GT-NPS`. Screenshot to `docs/evidence/day4-glossary-46.png`.

**4.5 [AGENT]** Add Phase 4.2 cell to `nb_07_publish_to_purview` — attach term-level access policies to 5 regulated terms: `GT-CONSENT`, `GT-PII`, `GT-SIN`, `GT-GEOPII`, `GT-PCISCOPE`.

Policy template (per term):
- Read approved roles from `metadata.role_assignments` filtered to the term's regulatory scope
- POST term-level access policy: `eligible_principals` = those role assignments

Commit:
```bash
git add fabric/nb_07_publish_to_purview.Notebook/notebook-content.py
git commit -m "Day 4 — nb_07 Phase 4.2 term-level access policies on regulated terms"
```

**4.6 [HUMAN]** Run the new Phase 4.2 cell.
**Verify:** Purview → Glossary → `GT-PII` → Access policy tab shows eligible principals. Screenshot to `docs/evidence/day4-term-policies.png`.

**4.7 [AGENT]** Extend `nb_04_sempy_writeback` (or create a new cell block in the existing notebook) to add 5 CX measures to `BrookfieldEnercare`:

Measure DAX (sketch):
- `NPS = (CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[promoter_flag]=1) - CALCULATE(COUNTROWS(fct_cc_interactions), fct_cc_interactions[detractor_flag]=1)) / COUNTROWS(fct_cc_interactions) * 100`
- `CSAT = AVERAGE(fct_cc_interactions[csat_score])`
- `AvgHandleTime = AVERAGE(fct_cc_interactions[handle_time_seconds])`
- `QAScore = AVERAGE(fct_cc_qa_evaluations[score])` (note: `fct_cc_qa_evaluations` may not exist yet; if so, mock a placeholder or add a stub fact via `nb_05a`)
- `RepeatComplaintRate = DIVIDE(CALCULATE(COUNTROWS(fct_complaints), fct_complaints[is_repeat]=1), COUNTROWS(fct_complaints))`

Use SemPy Labs `update_measure` or `add_measure` to create each.

Commit:
```bash
git add fabric/nb_04_sempy_writeback.Notebook/notebook-content.py
git commit -m "Day 4 — Add 5 CX KPI measures to BrookfieldEnercare via SemPy"
```

**4.8 [HUMAN]** Run the new `nb_04` cell.
**Verify:** Power BI service → `BrookfieldEnercare` → Measures pane shows the 5 new measures with descriptions matching the glossary term definitions.
**If DAX fails on missing column:** stub the missing fact. Add a cell to `nb_05a` to create a placeholder `fct_cc_qa_evaluations` (50 rows, scores 60–95) if needed and re-run.

**4.9 [AGENT]** Stub 5 verified Q&A entries in `lh_metadata.metadata.qa_verified`.

Q&A entries (per `docs/purview-maria-north-star-scenario.md` §Required SM Q&A):
1. "What is Maria's furnace status?" → references `fct_service_requests`, `dim_customer`, `dim_service_account`, equipment ontology
2. "Why hasn't anyone fixed Maria's furnace?" → service requests + technician notes + SLA + history
3. "What's our NPS this month?" → `_Measures/NPS` + `dim_date`
4. "What's the average handle time for furnace-related calls?" → `_Measures/AvgHandleTime` filtered to equipment_type = Furnace
5. "Show me repeat complaints by service zone" → `_Measures/RepeatComplaintRate` + `dim_service_zone`

Stage them by either:
- Adding cells to a new `fabric/nb_05_push_qa_verified_answers.Notebook/notebook-content.py` (Day 5 will run it), OR
- Writing a DataFrame directly to `lh_metadata.metadata.qa_verified` in a one-off cell in `nb_07a`

Commit:
```bash
git add fabric/nb_05_push_qa_verified_answers.Notebook/
git commit -m "Day 4 — Stub 5 verified Q&A entries for Maria scenario"
```

### Day 4 evening commit
```bash
# AGENT
git add docs/evidence/
git commit -m "Day 4 — Phase C: glossary +11, term policies, 5 CX measures, Q&A staged"
```

### Day 4 exit criteria
- [ ] Glossary expanded to 46 terms; republished in Purview
- [ ] 5 term-level policies live on regulated terms
- [ ] 5 new SM measures with descriptions in `BrookfieldEnercare`
- [ ] 5 verified Q&A entries staged in `lh_metadata.metadata.qa_verified`
- [ ] Day 4 commit on `enercare` branch

---

## Day 5 — Maria scenario E2E + demo rehearsal

### Objective
Maria scenario answers end-to-end via Data Agent; exec view (Power BI) renders all 5 CX KPIs from `BrookfieldEnercare`; governance walkthrough tells a coherent story; evidence captured; 3 rehearsal passes complete.

### Inputs
- Day 4 exit criteria met

### Outputs
- Verified Q&A annotations pushed to `BrookfieldEnercare`
- Data Agent answers the 5 Maria-scenario questions
- Power BI exec dashboard renders 5 KPIs
- `docs/evidence/` complete
- 3 successful rehearsals

### Steps

**5.1 [HUMAN]** Run `nb_05_push_qa_verified_answers` to push the 5 Q&A entries to `BrookfieldEnercare`.
**Verify:** SemPy `list_qa_pairs("BrookfieldEnercare")` shows 5 verified Q&A entries. Screenshot to `docs/evidence/day5-qa-verified.png`.

**5.2 [HUMAN]** Dry-run Maria scenario in the Data Agent surface.

Test queries (paste into the agent, one at a time):
1. "Why hasn't anyone fixed Maria Costa's furnace?"
2. "What's the status of Maria Costa's service request?"
3. "What's our NPS this month?"
4. "What's the average handle time for furnace-related calls?"
5. "Show me repeat complaints by service zone"

**Verify:** Each answer:
- References the correct data product
- Resolves "furnace" via equipment ontology (not literal string match)
- Surfaces service request status, technician note, SLA, billing line items where relevant
- Cites the verified Q&A entry where applicable

Screenshot each answer to `docs/evidence/day5-agent-answer-N.png` (1–5).

**If agent doesn't resolve "furnace":** glossary term `GT-EQUIP-FURNACE` may not be in the agent's vocabulary. Re-run Day 4 step 4.4 to confirm the term is published; restart the agent to re-index.

**5.3 [HUMAN]** Validate exec view — Power BI report on `BrookfieldEnercare`.
- Open the exec dashboard
- Confirm 5 KPI cards render: NPS, CSAT, AvgHandleTime, QAScore, RepeatComplaintRate
- Confirm values match what SemPy returns for the measures (no drift)

**Verify:** SemPy spot-check from a notebook cell:
```python
import sempy.fabric as fabric
m = fabric.evaluate_dax("BrookfieldEnercare", "EVALUATE ROW(\"NPS\", [NPS], \"CSAT\", [CSAT], \"AHT\", [AvgHandleTime])")
print(m)
```
Compare to dashboard values. Screenshot to `docs/evidence/day5-exec-view.png`.

**5.4 [HUMAN]** Capture remaining evidence (if not already during Day 1–4):
- Domain list screenshot
- Data product list screenshot
- Glossary term detail page (e.g., `GT-PII`)
- CDE detail page (e.g., `CDE-CUST-ID`)
- Lineage view (a SM measure → asset → column path)
- Classification dashboard
- A labeled Fabric item showing the label badge
- Each Data Agent answer

Save all to `docs/evidence/` with descriptive filenames.

**5.5 [HUMAN]** Rehearsal pass 1 — Tom (agent persona) Maria call.
Run through the Maria scenario as if you were Tom on the phone with Maria. Time it.
**Verify:** End-to-end story works in ≤8 minutes. Note any awkward transitions in `docs/evidence/day5-rehearsal-1-notes.md`.

**5.6 [HUMAN]** Rehearsal pass 2 — Victoria (CCO persona) exec review.
Walk the Power BI dashboard. Show the 5 KPIs. Drill into one ("Why is repeat complaint rate up?") to demonstrate that the measure traces back to the same governed source as Tom uses.
**Verify:** KPIs read cleanly; drill-through works. Notes in `docs/evidence/day5-rehearsal-2-notes.md`.

**5.7 [HUMAN]** Rehearsal pass 3 — Ci Zhu (governance persona) catalog walkthrough.
Walk Purview: domain → data product → glossary term → CDE → label → lineage → certified KPI bound to SM measure.
**Verify:** Every claim is provable on screen; no manual reconciliation. Notes in `docs/evidence/day5-rehearsal-3-notes.md`.

### Day 5 evening commit
```bash
# AGENT
git add docs/evidence/ fabric/nb_05_push_qa_verified_answers.Notebook/
git commit -m "Day 5 — Maria scenario E2E; 3 rehearsals complete; evidence captured"
```

### Day 5 exit criteria
- [ ] Maria scenario answerable by Data Agent end-to-end
- [ ] Exec view renders all 5 CX KPIs from single SM source
- [ ] All evidence captured in `docs/evidence/`
- [ ] All 3 rehearsals complete with notes
- [ ] Final commit: Phase A + B + C complete on `enercare` branch

---

## Schedule risk register

| Risk | Day at risk | Mitigation |
|---|---|---|
| M365 E3/E5 SKU missing | Day 3 | Day 0.3 verification; if missing, demo labels via annotation only and skip step 3.8 |
| Fabric mirror lag on new columns | Day 1 → Day 2 | Day 1 step 1.4 explicit wait + restart-replication fallback |
| Purview SDK / CDE API instability | Day 2 → Day 3 | Pre-script both API and portal paths; if API fails on CDEs, do the 12 CDEs in UI (sub-1hr) |
| Asset curation enablement breaks something | Day 2 | Approval gate at step 2.5; Day 1 SIT registration (1.6) is the smoke test that proves API path before flipping |
| Custom SIN SIT mis-fires (over- or under-classifies) | Day 3 | Day 1 step 1.6 standalone test; Purview SIT test tool against sample data |
| SemPy Labs writeback fails mid-batch | Day 2 → Day 4 | nb_04 idempotent — re-run from the merged DataFrame on every cell run; no destructive state |
| Power BI Q&A latency on new measures | Day 5 | Push Q&A late Day 4 evening so latency surfaces before rehearsal |
| Lakehouse Files mount path changes | Any | Step 0.7 verification cell catches it; re-upload if mount is reset |

---

## Definition of done

The demo is ready when **all three personas** can be served from the same governed surface, with the same definitions, by the same data products, with no manual reconciliation step:

1. **Tom (agent persona)** — Asks "what's the status of Maria Costa's furnace?" via Data Agent → gets equipment + service request + technician + SLA + credit eligibility, in business terms.
2. **Victoria (CCO persona)** — Sees a Power BI dashboard with NPS, CSAT, AvgHandleTime, QAScore, RepeatComplaintRate, MTTR, FCR — same definitions as Tom uses.
3. **Ci Zhu (governance persona)** — Walks the Purview catalog showing domain → data product → glossary term → CDE → label → lineage → certified KPI bound to SM measure — every claim provable.

If any persona's view diverges from the others, KPI drift has won and the demo fails on the central thesis.

---

## Appendix — Reference docs

The agent should treat these as authoritative context. Re-read on demand when a step requires it.

| Doc | When to consult |
|---|---|
| `docs/purview-demo-data-design.md` | Source schema, column shapes, design rationale |
| `docs/purview-csv-alignment.md` | Exact CSV column lists, enum values, bound_assets/bound_columns format |
| `docs/purview-sin-classifier-backstop.md` | SIN SIT design, two-layer strategy, regex + Luhn checksum |
| `docs/purview-maria-north-star-scenario.md` | Maria scenario script, required Q&A, required SM measures |
| `docs/purview-design-readiness-assessment.md` | Phase 0–5 mapping to the SOW phases; what's gated by what |
| `docs/design-gap-analysis.md` | Known gaps and resolutions, including SQL network posture (G7-2) |
| `docs/purview-5-day-execution-plan.md` | Earlier activity-table view of this same plan (kept for stakeholder reference) |
