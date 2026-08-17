# Notebooks 05–10 — Pending Individual-File Split

**Status:** Temporary holding document. `docs/01_Notebook_Description.md` through
`docs/04_Notebook_Description.md` have been split into individual per-notebook files (one
file per notebook, matching the naming convention `NN_Notebook_Description.md`), each enriched
with artifact cataloging and live-validation findings as that notebook is worked through the
validation sequence (`docs/runbooks/notebook-validation/`).

The content below for notebooks 05–10 has not yet been split out or enriched with live-run
evidence — it's preserved verbatim from the prior consolidated `01_Notebook_Description.md` so
nothing is lost. As each notebook is reached in the validation sequence, its section here will
be extracted into its own `0N_Notebook_Description.md` (matching the pattern of 01–04) and
removed from this file.

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
**Note (2026-08-17):** its `_read_table()` was missing the `refreshTable()` guard against the
stale-Spark-catalog-schema bug found live in `02_build_metadata_foundation` — fixed proactively
during that same-day audit, not yet exercised by a live run of this notebook.

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

## Governance Review Findings (orphan check, carried forward)

Every notebook was reviewed for content that reaches a production/demo-facing surface WITHOUT
flowing through the closed-loop governance gate — i.e., anything that isn't pure seed data or
architectural schema-building. Findings for notebooks 01/02 have moved into their own docs
(`01_Notebook_Description.md`, `02_Notebook_Description.md`); findings not yet tied to a
specific split-out notebook remain here.

| Finding | Detail | Status |
|---|---|---|
| **Stale pre-consolidation paths in `tools/`** | `tools/validate_build_workflow.ps1` and `tools/normalize_fabric_canonical_state.ps1` referenced a `fabric/` prefix folder that doesn't exist in this repo layout, plus the old `nb_04_sempy_writeback`/`nb_05_push_qa_verified_answers` notebook names — both scripts would fail their Gate D checks with false-positive "file missing" issues. `tools/test_nb09_live_publish_defaults.py` pointed at a notebook path that no longer exists. | ✅ **Fixed 2026-08-16.** Both scripts updated to the current repo-root paths and the single merged `04_writeback_governed_metadata.Notebook`; re-run and confirmed passing. The test file was fixed and renamed to `tools/test_publish_glossary_and_lineage_live_defaults.py` and confirmed passing. |
| **Stale-Spark-catalog-schema risk audit (session-wide, 2026-08-17)** | Root-caused live in `02_build_metadata_foundation` (a `collectToPython`/`IllegalStateException` on a schema-drifted `parent_term_code` column); audited all 10 notebooks for the same `_read_table`/`spark.table()` pattern. | ✅ `05`/`06` already had the fix; `02`/`04`/`08` were vulnerable and fixed; `01`/`03`/`07` only do low-risk same-session-write or `.columns`-only reads; `09`/`10` don't use Spark table reads at all. |
| Everything else reviewed | Domain/data-product/glossary/CDE publication notebooks (`05`, `06`) republish already-governed SQL/CSV source content — no bypass found. `07_apply_approved_changes` and `09_reconcile_semantic_model` all correctly fail closed on a required prior receipt before applying. `08_validate_governance_evidence`'s scorecard cells are read-only. `10_reset_demo` never deletes a governed row. | 🟢 No other orphans found |
