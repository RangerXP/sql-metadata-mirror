# Notebook Reference — What Each Notebook Does, Demo Fit, Talking Points

**Purpose:** One-page-per-glance reference for the current 10-notebook build. Each entry
covers what the notebook does, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and the talking points to use live.

**Last updated:** 2026-08-16 — full rewrite after the notebook consolidation/renumbering,
the `sql/` repack, and the notebook-1 governance-metadata-duplication migration (see
`docs/design-gap-analysis.md` and `docs/build-scorecard.md` update logs for the dated history).
The repo previously ran 18 separate `nb_XX_name.Notebook` items; those were consolidated into
the 10 notebooks described below (`01_setup_source_data.Notebook` … `10_reset_demo.Notebook`).
Any `nb_XX` name you see in older docs (`design-gap-analysis.md`, `Enercare-Demo-SemPy-Design-Guide.md`,
`build-scorecard.md`) refers to a predecessor of one of these 10 — those documents are
intentionally left as dated historical logs and were not rewritten; see the mapping table below.

**Central tenant:** Metadata management is governance-first. SQL metadata definitions are the
customer-authored source-of-truth (see `sql/README.md` and `docs/sql-prep-catalog.md`),
stewardship and approval are required before adoption, lineage is preserved through every step,
and downstream Fabric/Purview surfaces are consumers of approved metadata rather than
independent authors.

**DEMO_MODE** shown is the CURRENT COMMITTED default in `main` — check before running live.

> **Read this first:** notebooks marked `DEMO_MODE = False` will execute real writes the
> moment they're run, with no confirmation prompt. Before a demo pass, decide per-notebook
> whether that's intended (several notebooks, e.g. `07_apply_approved_changes`, are meant to
> apply real state as their normal mode) or whether it should be flipped to `True` first.

---

## Legacy `nb_XX` → current notebook name mapping

For cross-referencing older dated docs that still cite the pre-consolidation names:

| Current notebook | Predecessor(s) (`nb_XX`) |
|---|---|
| `01_setup_source_data` | `nb_01_setup_demo_environment`, `nb_05a_publish_synthetic_data_to_sql`, `nb_06a_create_sin_backstop` |
| `02_build_metadata_foundation` | `nb_02_metadata_pipeline_demo` (thin `@tag` reader), `nb_07a_ingest_customer_files`, `nb_07b_merge_customer_metadata` |
| `03_build_semantic_model` | `nb_03_pbi_star_schema` |
| `04_writeback_governed_metadata` | `nb_04_sempy_writeback`, `nb_04a_extend_metadata_schema`, `nb_05_push_qa_verified_answers` |
| `05_publish_governance_domains` | `nb_07_publish_to_purview` (domains/data products portion) |
| `06_publish_glossary_and_lineage` | `nb_08_purview_glossary_cde`, `nb_09_purview_labels_lineage` |
| `07_apply_approved_changes` | `nb_11_gated_governance_sync` |
| `08_validate_governance_evidence` | `nb_10_purview_stewardship_ai`, `nb_12_purview_workflow_sync` (P1) |
| `09_reconcile_semantic_model` | `nb_13_semantic_reconcile` (P2), `nb_14_purview_access_sync` (P3), `nb_15_purview_dataproduct_sync` (P4 publish), `nb_16_dataproduct_semantic_reconcile` (P4 reconcile), `nb_17_g18_semantic_promotion` (G19 semantic promotion) |
| `10_reset_demo` | `nb_18_demo_reset` |

---

## Phase 0 — Environment & Source Data (architectural, run once per environment)

### `01_setup_source_data` — `DEMO_MODE = False`
**What it does:** Three sections in one notebook:
1. **Lakehouse source tables** — creates the 7 core transactional tables (products, customers,
   service accounts, equipment, contracts, service requests, billing) plus a **call-center
   extension** (`cc_agents`, `fct_cc_interactions`, `fct_cc_transcript_turns`, and the
   intentionally-unmapped `ref_cc_billing_adj_category`) directly in `lh_enercare_demo` via
   PySpark. 50 synthetic Ontario customers, Maria Castellanos among them. The call-center data
   is generated with a deliberate, checked correlation: 14 customers who called billing in
   Jan–Feb 2026 get a protection-plan renewal call within 30 days, and 6 of those 14 decline
   (57% acceptance vs. ~76% baseline) — the 19-point gap the Data Agent is meant to surface.
2. **Publish to Azure SQL** (`DEMO_MODE = False`) — publishes the 7 source tables from
   `lh_enercare_demo` into Azure SQL (`sqldemo`), making SQL the authoritative mirrored source.
3. **Phase B — Purview demo extensions (CELL B0–B7)** — applies PII/classifier extensions (DOB,
   partial SIN, GPS, payment partials) and 6 new tables (`employees`, `service_zones`,
   `customer_consents`, `customer_complaints`, `data_owners_directory`, `audit_data_access`),
   seeds Maria-specific consent/complaint/audit rows, backfills and spot-checks Luhn-valid SINs,
   and grants the Purview managed identity read access. **As of 2026-08-16, this notebook no
   longer creates or seeds governance metadata (domains, data products, glossary, CDEs, roles,
   labels, OKRs)** — that duplicated, drifted-behind copy was removed. CELL B4A now only
   *verifies* `sql/02_metadata_foundation/06_purview_metadata_schema.sql` /
   `07_seed_purview_metadata.sql` / `11_ontology_okr_schema.sql` / `12_seed_ontology_okrs.sql`
   have already been applied to `sqldemo`, and raises a clear `RuntimeError` naming those
   scripts if `dbo.governance_domains` is empty.
**Demo fit:** Foundational — nothing else runs without this. Not shown live; it's the "before
the curtain" step, except for the call-center correlation, which is exactly what Tom's Data
Agent grounding surfaces in Act 1.
**Talking points:** "This is the synthetic Enercare universe — real Ontario geography, real
FSAs, a realistic customer/contract/service/call-center mix, entirely synthetic data — and one
correlation baked in on purpose: customers who call about billing are meaningfully less likely
to renew their protection plan."

### `03_build_semantic_model.Notebook` — single-notebook, no `DEMO_MODE` gate
**What it does:** Builds the Power BI-ready dimensional star schema (`dim_date`, core
dimensions, `dim_equipment`, `fct_billing`, `fct_service_request`, `fct_contract_month`, and
the call-center fact/dimension tables) on top of the Fabric-mirrored SQL source in one
straight-through run — no dry-run/live split, since this only ever rebuilds derived tables in
the lakehouse, never SQL or the semantic model itself.
**Demo fit:** This produces the actual tables the `BrookfieldEnercare` semantic model and every
downstream KPI/measure are built on — the physical backbone of Act 2 (Victoria's dashboard).
**Talking points:** "Same dimensional model whether you're a data engineer looking at Delta
tables or an executive looking at a Power BI report."

---

## Phase 1 — Metadata Foundation & Semantic Writeback

### `02_build_metadata_foundation.Notebook` — `DEMO_MODE = False` (two independent flags, one per merged section)
**What it does:** Two originally-separate notebooks merged into one file:
- **Cells 1–9 — governance ingestion** (formerly `nb_07a_ingest_customer_files`): reads
  `domain-charter.csv`, `data-product-catalog.csv`, `glossary-master.csv`, `cde-catalog.csv`,
  `role-directory.csv`, `label-policy.csv`, mirrored `governance_change_requests`, and the
  ontology/OKR tables into `lh_metadata.metadata.*` for the Purview-publish notebooks to read.
- **Cells 10–16 — semantic reconciliation** (formerly `nb_07b_merge_customer_metadata`):
  cross-references glossary/CDE/data-product/label associations against the semantic model's
  real table/column names via SemPy, resolves aliases, and writes the reconciled
  `sm_annotations` working table that `04_writeback_governed_metadata` depends on. A leftover
  `mssparkutils.notebook.exit()` from before this section was merged in briefly made Cells
  10–16 unreachable dead code — fixed 2026-08-16 (see Governance Review Findings below).
**Demo fit:** Invisible plumbing — keeps the governance content Purview publishes, and the
annotations the semantic model receives, in sync with the SQL source of truth.
**Talking points:** "Every governance object — domain, product, term, CDE — has one SQL source
row; this notebook is the sync-and-reconcile step into the Fabric/semantic-model layer."

### `04_writeback_governed_metadata.Notebook` — `DEMO_MODE = False`
**What it does:** Two originally-separate notebooks merged into one file:
- **Cells 1–10 — table/column/measure writeback** (formerly `nb_04_sempy_writeback`): reads
  curated metadata from `lh_metadata`, cross-checks the live model inventory (Power BI MCP),
  builds a write plan, and applies table/column/measure descriptions plus governance/ontology
  annotations into the `BrookfieldEnercare` semantic model via SemPy Labs TOM. Verified against
  a hard TOM read-back after every write.
- **Cells 11–15 — AI grounding writeback** (formerly `nb_05_push_qa_verified_answers`): reads
  `ai_metadata`, filters `WHERE IsDraft = 0 AND IsCertified = 1` (fixed 2026-08-13 to match the
  KPI path's certification gate), builds the annotation payload, and writes
  `PBI_AI_Instructions`/`PBI_AI_VerifiedAnswers` annotations the Fabric Data Agent reads for
  grounding. `MAX_ANNOTATION_CHARS = 32000` (root-caused and fixed after a live run failed at
  the old 12000-char limit with a real certified payload of 12001 chars).
**Demo fit:** This is the mechanism behind Ci Zhu's Act 3 promise — "there's only one
`_Measures/Net Revenue`... it's owned by me" — and also what lets Tom ask the Data Agent "show
me Maria's furnace status" and get a grounded answer (Act 1 / Acceptance Criterion 7).
**Talking points:** "Notice the certification filter on both halves of this notebook — an
uncertified KPI or AI instruction change never reaches the semantic model or the Data Agent
through this path. That's what makes drift structurally impossible, not just a policy."
**Dependency risk:** Cell 8's `sm_annotations` read depends on `02_build_metadata_foundation`'s
Cells 10–16 having run in the same environment (fixed 2026-08-16 — see Governance Review
Findings below).

---

## Phase 2 — Purview Publication (SQL-controlled, native scans + custom Atlas)

### `05_publish_governance_domains.Notebook` — no `DEMO_MODE` gate (dry-run artifact write is always on; live publish is config-driven)
**What it does:** Reads governance domain/data-product tables, builds Atlas typedef + entity
payloads, and publishes governance Domains and Data Products to Purview. Saves dry-run payload
artifacts for review on every run regardless of live-publish setting.
**Demo fit:** This is literally "Customer Operations", "Service Delivery", "Revenue and
Contracts" domains and "Customer 360"/"Service Performance"/"Billing and Contract Health"
appearing in Purview — the domains/products Ci Zhu references in Act 3.
**Talking points:** "One notebook, three domains, three data products, published directly via
the Atlas API — the same objects a Purview admin would create by hand in the portal."

### `06_publish_glossary_and_lineage.Notebook` — no top-level `DEMO_MODE` gate
**What it does:** Two originally-separate notebooks merged into one file, sharing one Purview
token cache:
- **Cells 1–5 — glossary/CDE publish** (formerly `nb_08_purview_glossary_cde`): publishes ~35
  glossary terms and 12 CDEs to Purview, associates each CDE to its parent glossary term, and
  self-heals stale term `shortDescription` values on every run.
- **Cells 6–11 — labels & lineage** (formerly `nb_09_purview_labels_lineage`): publishes
  sensitivity labels, CDE classifications, and custom Atlas lineage edges (SQL → Fabric →
  semantic model) since native scans only establish asset identity, not cross-system process
  lineage.
**Demo fit:** This is every `GT-*`/`CDE-*` reference throughout Maria's scenario (GT-SLA,
GT-CONSENT, CDE-CONTRACTAMT, CDE-CONSENTSTATE, etc.) plus the "click View lineage" moment in
Act 3.6 — the 8-edge chain from Power BI visual back to source SQL.
**Talking points:** "GT-SLA is the term that ties Tom's credit calculation, Victoria's MTTR
dashboard, and Ci Zhu's audit answer to one published definition — and native scans tell
Purview an asset exists, while this notebook tells Purview how assets connect across systems."

---

## Phase 3 — Gated Governance (SQL-controlled approval, apply-on-approve)

### `07_apply_approved_changes.Notebook` — `DEMO_MODE = False` (intentional — its job is to apply real state)
**What it does:** The apply-on-approve dispatcher. Reads `Approved`/unapplied rows directly
from the `sub2` SQL source (not the lakehouse mirror, to avoid acting on stale status),
dispatches by `request_type` (KPI approval, verified answer, CDE classification, glossary term,
AI instruction certification/rollback via an idempotent schema migration in Cell 3b), applies
the change, and stamps `Applied`.
**Demo fit:** This is the live "click Approve → watch the data change" moment for every
SQL-controlled scenario — KPI reformulation, a new verified answer, an AI instruction fix.
**Talking points:** "One dispatcher, several request types, all sharing the same
Draft→Approved→Applied contract — this is what makes the closed loop closed."

---

## Phase 4 — Governance Evidence & Purview-Native Workflow Proofs

### `08_validate_governance_evidence.Notebook` — Cells 1–6 no gate; Cell 7+ `DEMO_MODE = False`
**What it does:** Two originally-separate notebooks merged into one file:
- **Cells 1–6 — scorecard** (formerly `nb_10_purview_stewardship_ai`): read-only stewardship
  coverage, control completeness, AI readiness, and OKR/ontology graph-integrity checks. No
  writes; pure validation; writes a closeout manifest.
- **Cells 7–13 — P1 Purview-native workflow proof** (formerly `nb_12_purview_workflow_sync`):
  observes a real Purview-native Glossary Term publish workflow (GT-SLA) via the term's own
  `status` field — the only real API-observable proxy for approval, since Purview exposes no
  workflow-request API. Persists an idempotent Draft/Published observation and a durable P1
  evidence receipt.
**Demo fit:** The "proof it all worked" scorecard, plus Ci Zhu's audit answer for GT-SLA — a
REAL Purview workflow run, not a SQL simulation.
**Talking points:** "This is our own governance health check, and this is what a real approval
inside the Purview portal looks like once read back through the API — not a SQL-side
approximation."

### `09_reconcile_semantic_model.Notebook` — every phase gated `DEMO_MODE = False` independently
**What it does:** Four Purview-native phases (P2/P3/P4) plus the G18/G19 semantic-promotion
step, merged into one very large notebook:
- **Cells 1–7 (P2)** — reconciles the approved GT-SLA definition into the semantic model
  (`IsSlaBreachFlag` column + 2 SLA measures); fails closed unless the P1
  `PublicationReadback` receipt from `08_validate_governance_evidence` already passed.
- **Cells 8–14 (P3)** — records Rupal Solanki's real Data Product access request to Customer
  360 and Victoria Tan's two-tier approval. Purview exposes no API/log for access decisions, so
  the decision itself is operator-attested (clearly labeled), while the Data Product's own
  state is real, API-verified evidence.
- **Cells 15–21 (P4 publish)** — records Ranbir Singh's real Data Product Publish workflow run
  for Service Performance (`DP-SVCPERF`), observed via the product's own `status` field.
- **Cells 22–28 (P4 reconcile)** — writes `TechnicianId`/`EquipmentType` metadata annotations
  once `DP-SVCPERF`'s Publish is confirmed; this is the phase proven live for the
  drift-and-restore self-healing test (corrupt a value manually, re-run, confirm it restores
  with the *same* receipt, no new approval fabricated).
- **Cell 29 (G18/G19 semantic promotion)** — a single, deliberately flattened cell (worked
  around a documented Fabric/TOM import-ordering bug: `Microsoft.AnalysisServices.Tabular`
  types must be imported from inside an active `connect_semantic_model` session, never before
  it) that adds a REAL new measure (`Technician Utilization Rate`) to the `BrookfieldEnercare`
  model, gated on the `vw_technician_utilization_summary` → `KR-TECH-UTIL` ontology mapping
  already having passed.
**Demo fit:** Completes the GT-SLA, DP-CUST360, and DP-SVCPERF chains, and is the "new SQL
source becomes a real semantic-model KPI" full-circle moment for the G18/G19 onboarding
narrative.
**Talking points:** "Same apply-then-verify pattern throughout this notebook, whether the
source of truth is a SQL-controlled request or a real Purview approval — run any of these
phases twice against the same request and you get the same receipt ID, re-validated, not a new
one. That's idempotent self-correction."

---

## Phase 5 — Demo Operations

### `10_reset_demo.Notebook` — `DEMO_MODE = False` (its normal mode is to actually reset state)
**What it does:** Resets every demo request (Objective edits/certification/recertification, AI
Instruction effective-date/rollback, Data Product certification/expiration/decertification,
CDE/ontology mapping, semantic-model promotion) back to its pre-decision status across both SQL
(Cells 3–6) and the Lakehouse/semantic model (Cells 7–8), so the whole approval narrative can
be re-demoed live, indefinitely. Never deletes a governed object row.
**Demo fit:** Not part of the demo narrative itself — the "reset the stage" utility run between
rehearsals or between live audiences.
**Talking points:** (internal use only — not shown to an audience) "Run this after a live pass
to put every gated request back to 'awaiting approval' so tomorrow's demo starts fresh."
**Note:** re-approving after a reset needs a small manual status flip (`Submitted`→`Approved`)
plus re-running the matching apply notebook (`07_apply_approved_changes` or the relevant phase
of `09_reconcile_semantic_model`) — the original build scripts won't reapply a reset request
since they're guarded by existence, not status.

---

## Governance Review Findings (orphan check, carried forward + updated)

Every notebook was reviewed for content that reaches a production/demo-facing surface WITHOUT
flowing through the closed-loop governance gate — i.e., anything that isn't pure seed data or
architectural schema-building.

| Finding | Detail | Status |
|---|---|---|
| **AI grounding writeback was missing an `IsCertified` filter** | The AI-grounding half of `04_writeback_governed_metadata` originally filtered only `WHERE IsDraft = 0`, unlike the KPI writeback path's `WHERE IsCertified = 1`. | ✅ **Fixed 2026-08-13** — now filters `WHERE IsDraft = 0 AND IsCertified = 1`, matching the KPI pattern exactly. Live-verified: `verified_answer: total_draft0=34 certified=34`, `ai_instruction: total_draft0=8 certified=8`. |
| **`02_build_metadata_foundation`'s reconciliation half is unreachable dead code** | An unconditional `mssparkutils.notebook.exit(...)` at the end of Cell 9 prevents Cells 10–16 (the `sm_annotations` reconciliation, formerly `nb_07b`) from ever running. | 🔴 **Open, not yet fixed.** `04_writeback_governed_metadata` Cell 8 depends on `sm_annotations` and will raise `RuntimeError("sm_annotations is empty")` on a clean environment. Needs the `exit()` call removed or relocated. |
| **`02_build_metadata_foundation`'s reconciliation half was unreachable dead code** | An unconditional `mssparkutils.notebook.exit(...)` at the end of Cell 9 prevented Cells 10–16 (the `sm_annotations` reconciliation, formerly `nb_07b`) from ever running — a leftover from the merge: the `exit()` was correct for the original standalone notebook, which ended at that line, and was never removed once the reconciliation cells were appended during consolidation. | ✅ **Fixed 2026-08-16.** Removed the `exit()` call; Cells 10–16 now run normally. `04_writeback_governed_metadata` Cell 8's `sm_annotations` dependency is satisfied by a normal end-to-end run again. |
| **Stale pre-consolidation paths in `tools/`** | `tools/validate_build_workflow.ps1` and `tools/normalize_fabric_canonical_state.ps1` referenced a `fabric/` prefix folder that doesn't exist in this repo layout, plus the old `nb_04_sempy_writeback`/`nb_05_push_qa_verified_answers` notebook names — both scripts would fail their Gate D checks with false-positive "file missing" issues. `tools/test_nb09_live_publish_defaults.py` pointed at a notebook path that no longer exists. | ✅ **Fixed 2026-08-16.** Both scripts updated to the current repo-root paths and the single merged `04_writeback_governed_metadata.Notebook`; re-run and confirmed passing (`validate_build_workflow.ps1` → all Gate D checks PASS, `normalize_fabric_canonical_state.ps1` → no changes required). The test file was fixed and renamed to `tools/test_publish_glossary_and_lineage_live_defaults.py` and confirmed passing. |
| Notebook 1 duplicated and had drifted behind the SQL-first governance metadata schema** | `01_setup_source_data` previously embedded its own copy of the domains/data-products/glossary/CDE/role/label/OKR schema-and-seed SQL as Python string literals, and that copy was missing a `governance_domain_stewards` column the real `sql/02_metadata_foundation/06_purview_metadata_schema.sql` had. | ✅ **Fixed 2026-08-16.** The duplicate creation/seed logic was removed; the notebook now only verifies the prerequisite (`dbo.governance_domains` populated) and points to the 4 authoritative `sql/02_metadata_foundation/*.sql` scripts if it's not. See `docs/sql-prep-catalog.md`. |
| Everything else reviewed | Domain/data-product/glossary/CDE publication notebooks (`05`, `06`) republish already-governed SQL/CSV source content — no bypass found. `07_apply_approved_changes` and `09_reconcile_semantic_model` all correctly fail closed on a required prior receipt before applying. `08_validate_governance_evidence`'s scorecard cells are read-only. `10_reset_demo` never deletes a governed row. | 🟢 No other orphans found |
