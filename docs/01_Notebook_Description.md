# Notebook Reference — What Each Notebook Does, Demo Fit, Talking Points

**Purpose:** One-page-per-glance reference for the first full end-to-end demo pass. Each entry
covers what the notebook does, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and the talking points to use live.

**Central tenant:** Metadata management is governance-first. SQL metadata definitions are the
customer-authored source-of-truth, stewardship and approval are required before adoption,
lineage is preserved through every step, and downstream Fabric/Purview surfaces are consumers of
approved metadata rather than independent authors. The repo is being organized around the
10-stage lifecycle in `docs/ten-notebook-governance-reorg-plan.md` and the standard contract in
`docs/sql-metadata-governance-standard.md`.

**DEMO_MODE** shown is the CURRENT COMMITTED default in `main` — check before running live.

> **Read this first:** notebooks marked `DEMO_MODE = False` will execute real writes the
> moment they're run, with no confirmation prompt. Before the demo pass, decide per-notebook
> whether that's intended (e.g. `nb_11`/`nb_16`/`nb_17` are meant to apply real state) or
> whether it should be flipped to `True` for a dry-run rehearsal first.

---

## Phase 0 — Environment & Source Data (architectural, run once per environment)

### `nb_01_setup_demo_environment`
**What it does:** Creates the 7 transactional source tables (products, customers, service
accounts, equipment, contracts, service requests, billing) directly in `lh_enercare_demo` via
PySpark — no SQL Server dependency. Pure synthetic seed data (50 Ontario customers, Maria
Castellanos among them).
**Demo fit:** Foundational — nothing else runs without this. Not shown live; it's the "before
the curtain" step.
**Talking points:** "This is the synthetic Enercare universe — real Ontario geography, real
FSAs, a realistic customer/contract/service mix, entirely synthetic data."

### `nb_05a_publish_synthetic_data_to_sql` — `DEMO_MODE = False`
**What it does:** Publishes the 7 source tables from `lh_enercare_demo` into Azure SQL
(`sqldemo`), making SQL the authoritative mirrored source. Handles Phase B child tables
(`customer_complaints`, `customer_consents`) too.
**Demo fit:** This is the moment "the data becomes real" — SQL Server, not just a lakehouse
table, is now the system of record Purview scans.
**Talking points:** "From here forward, Azure SQL is the authoritative source — Fabric
Mirroring picks this up automatically, no manual export/import step."

### `nb_03_pbi_star_schema`
**What it does:** Builds the Power BI-ready dimensional star schema (`dim_customer`,
`dim_equipment`, `fct_service_request`, etc.) on top of the Fabric-mirrored SQL source. Falls
back to the demo lakehouse if the mirror is temporarily unreadable.
**Demo fit:** This produces the actual tables the `BrookfieldEnercare` semantic model and every
downstream KPI/measure are built on — the physical backbone of Act 2 (Victoria's dashboard).
**Talking points:** "Same dimensional model whether you're a data engineer looking at Delta
tables or an executive looking at a Power BI report."

---

## Phase 1 — Metadata Foundation & Semantic Writeback

### `nb_02_metadata_pipeline_demo` — `DEMO_MODE = True`
**What it does:** Thin reader only (rebuilt 2026-08-13, G18-A). Reads `Draft`/`Submitted`
`SOURCE_TAG_DETECTED` governance requests (fed by a native SQL DDL trigger, not this notebook)
and surfaces them into `lh_metadata.source_tag_detections` for steward review.
**Demo fit:** This is the "new SQL object shows up for review" moment in the G18/G19 source
onboarding narrative — a steward-facing worklist, not itself a decision-maker.
**Talking points:** "A new SQL view gets tagged in T-SQL comments; this notebook is how it
surfaces for a steward to see it's waiting for review — nothing here approves anything."

### `nb_04a_extend_metadata_schema` — `DEMO_MODE = False`
**What it does:** Schema migration + seed notebook. Adds certification columns to
`kpi_metadata`/`ai_metadata`, seeds 29 KPIs (5 certified, the rest not), and reseeds the
baseline AI instruction / verified-answer content (Maria's source story, KPI definitions,
terminology) on every run — guarded so it never wipes a governance-approved row.
**Demo fit:** This is where Maria's whole grounding story lives — "Maria Source Story",
"Verified Answer Consistency", the 5 certified call-center KPI thresholds Tom's credit
authority and Victoria's dashboard both use.
**Talking points:** "This is the single source of business truth Copilot grounds against — and
notice the reseed logic explicitly protects any row a real governance approval already
touched; a schema refresh can never silently undo an approved change."

### `nb_04_sempy_writeback` — `DEMO_MODE = False`
**What it does:** Writes table/column/measure descriptions and AI instructions into the
`BrookfieldEnercare` semantic model via SemPy Labs. KPI descriptions are correctly gated —
`WHERE IsCertified = 1` — only certified KPIs get written.
**Demo fit:** This is the mechanism behind Ci Zhu's Act 3 promise: "there's only one
`_Measures/Net Revenue`... it's owned by me" — because this notebook is the only path that
writes measure metadata, and it only writes certified ones.
**Talking points:** "Notice the certification filter — an uncertified KPI formula change never
reaches the semantic model through this path. That's what makes KPI drift structurally
impossible, not just a policy."

### `nb_05_push_qa_verified_answers` — `DEMO_MODE = False`
**What it does:** Writes `ai_instruction` and `verified_answer` rows from `ai_metadata` into
two separate semantic-model annotations (`PBI_AI_Instructions`, `PBI_AI_VerifiedAnswers`) that
the Fabric Data Agent reads for grounding.
**Demo fit:** This is what lets Tom ask the Data Agent "show me Maria's furnace status" and get
a grounded answer (Act 1 / Acceptance Criterion 7).
**Talking points:** "Two independent annotations — instructions and verified answers — so they
can be audited and regenerated independently."
**⚠️ Governance finding (see below):** this notebook filters only on `IsDraft = 0`, not
`IsCertified = 1` — unlike `nb_04`'s KPI path, an uncertified `ai_instruction`/`verified_answer`
row would still reach the Data Agent's live grounding surface. See **Governance Review
Findings** at the end of this document.

---

## Phase 2 — Purview Publication (SQL-controlled, native scans + custom Atlas)

### `nb_07a_ingest_customer_files`
**What it does:** Ingests governance CSVs/mirrored SQL tables (domains, data products,
glossary terms, CDEs, role assignments, label assignments, OKRs, legacy change requests) into
`lh_metadata.metadata.*` for the Purview-publish notebooks to read.
**Demo fit:** Invisible plumbing — keeps the governance content Purview publishes in sync with
its SQL source of truth.
**Talking points:** "Every governance object — domain, product, term, CDE — has one SQL source
row; this is just the sync step into the Fabric layer."

### `nb_07b_merge_customer_metadata`
**What it does:** Merges/cross-references ingested metadata tables (glossary/CDE/data-product/
label associations) against the semantic model's actual table/column names, resolving aliases.
**Demo fit:** Ensures the CDE-to-column and glossary-to-asset bindings Ci Zhu shows in Act 3
actually resolve to real semantic model objects, not stale names.
**Talking points:** "This is the reconciliation step that keeps metadata bindings honest as the
semantic model evolves."

### `nb_07_publish_to_purview`
**What it does:** Publishes governance Domains and Data Products to Purview via Atlas typedefs
+ entity bulk API. `SQL_MIRROR_ONLY_DEPLOYMENT`/`APPLY_CHANGES` guard live publish.
**Demo fit:** This is literally "Customer Operations", "Service Delivery", "Revenue and
Contracts" domains and "Customer 360"/"Service Performance"/"Billing and Contract Health"
appearing in Purview — the domains/products Ci Zhu references in Act 3.
**Talking points:** "One notebook, three domains, three data products, published directly via
the Atlas API — the same objects a Purview admin would create by hand in the portal."

### `nb_08_purview_glossary_cde`
**What it does:** Publishes ~35 glossary terms and 12 CDEs to Purview, associates CDEs to their
parent glossary term, and self-heals stale term `shortDescription` values on every run.
**Demo fit:** This is every `GT-*`/`CDE-*` reference throughout Maria's scenario — GT-SLA,
GT-CONSENT, CDE-CONTRACTAMT, CDE-CONSENTSTATE, etc.
**Talking points:** "GT-SLA is the term that ties Tom's credit calculation, Victoria's MTTR
dashboard, and Ci Zhu's audit answer to one published definition."

### `nb_09_purview_labels_lineage`
**What it does:** Publishes sensitivity labels, CDE classifications, and custom Atlas lineage
edges (SQL → Fabric → semantic model) since native scans only establish asset identity, not
cross-system process lineage.
**Demo fit:** This is the "click View lineage" moment in Act 3.6 — the 8-edge chain from Power
BI visual back to source SQL.
**Talking points:** "Native scans tell Purview an asset exists; this notebook tells Purview how
assets connect across systems — that's the answer to 'where did this number come from?'"

### `nb_10_purview_stewardship_ai`
**What it does:** Read-only scorecard — checks steward coverage, control completeness, AI
readiness, and (Phase 11) OKR/ontology graph integrity. No writes; pure validation.
**Demo fit:** The "proof it all worked" notebook — run this after any publish chain to confirm
zero `ACTION_REQUIRED`.
**Talking points:** "This is our own governance health check — it fails loudly if anything
published without a steward, an owner, or a resolved OKR link."

---

## Phase 3 — Gated Governance (SQL-controlled approval, apply-on-approve)

### `nb_11_gated_governance_sync` — `DEMO_MODE = False`
**What it does:** The apply-on-approve dispatcher. Reads `Approved`/unapplied rows from the
legacy `governance_change_requests` table, dispatches by `request_type` (KPI approval, verified
answer, CDE classification, glossary term, AI instruction certification, AI instruction
rollback), applies the change, stamps `Applied`.
**Demo fit:** This is the live "click Approve → watch the data change" moment for every
SQL-controlled scenario — KPI reformulation, a new verified answer, an AI instruction fix.
**Talking points:** "One dispatcher, six request types, all sharing the same
Draft→Approved→Applied contract — this is what makes the closed loop closed."
**Note:** committed as live-apply (not dry-run) — this notebook's normal operating mode IS
live; that's intentional, not an oversight, since its job is to actually apply approved
changes.

---

## Phase 4 — Purview-Native Workflow Proofs (P1–P4, real Purview UI-driven workflows)

### `nb_12_purview_workflow_sync` — `DEMO_MODE = True`
**What it does:** P1 proof — observes a real Purview-native Glossary Term publish workflow
(GT-SLA) via the term's own `status` field (the only real API-observable proxy for approval,
since Purview exposes no workflow-request API).
**Demo fit:** Ci Zhu's audit answer for GT-SLA — a REAL Purview workflow run, not a SQL
simulation.
**Talking points:** "This isn't a SQL-side approximation of Purview governance — Victoria
Tan/Ranbir Singh clicked Approve inside the actual Purview portal, and this notebook observes
that real state change."
**Requires interactive run:** uses `DeviceCodeCredential`-only auth — must run in the Fabric
portal notebook editor, not a headless trigger.

### `nb_13_semantic_reconcile` — `DEMO_MODE = True`
**What it does:** P2 — reconciles the approved GT-SLA definition into the semantic model
(`IsSlaBreachFlag` column + 2 SLA measures), fails closed unless a `PublicationReadback`
receipt already passed.
**Demo fit:** Completes the GT-SLA chain — Purview approval → semantic model update →
read-back proof.
**Talking points:** "Same apply-then-verify pattern as the SQL-controlled path, just sourced
from a real Purview approval instead of a SQL request."

### `nb_14_purview_access_sync` — `DEMO_MODE = False`
**What it does:** P3 — records Rupal Solanki's real Data Product access request to Customer
360 and Victoria Tan's two-tier approval (Privacy + main). Purview exposes no API/log for
access decisions, so the decision itself is operator-attested (clearly labeled), while the
Data Product's own state is real, API-verified evidence.
**Demo fit:** This is the access-governance half of DP-CUST360 — who can see Maria's data and
why.
**Talking points:** "Everything about the product itself is machine-verified; only the
decision event is attested, because Purview genuinely doesn't expose that API today — and we
say so, rather than pretending otherwise."

### `nb_15_purview_dataproduct_sync` — `DEMO_MODE = False`
**What it does:** P4 — records Ranbir Singh's real Data Product Publish workflow run for
Service Performance, observed via the product's own `status` field (a real API-observable
proxy, same tier as Term publish).
**Demo fit:** DP-SVCPERF going from Draft to Published for real — Tom's equipment/ticket
surface becoming a governed, published product.
**Talking points:** "Same Tier-1 real-evidence rigor as the glossary term — no attestation
needed here, the API tells us the truth directly."

### `nb_16_dataproduct_semantic_reconcile` — `DEMO_MODE = False`
**What it does:** P4 semantic reconciliation — writes `TechnicianId`/`EquipmentType` metadata
annotations once DP-SVCPERF's Publish is confirmed; this is also the notebook proven live for
G17-R6's drift-and-restore self-healing test.
**Demo fit:** Completes the DP-SVCPERF chain and is the notebook that PROVES self-healing:
corrupt a value manually, re-run this, watch it restore — with no new approval fabricated.
**Talking points:** "Run this twice against the same request and you get the exact same
result — same receipt ID, re-validated, not a new one. That's idempotent self-correction, the
crux of 'self-healing.'"

---

## Phase 5 — G18/G19 Source Onboarding, Ontology & Semantic Promotion

### `nb_17_g18_semantic_promotion` — `DEMO_MODE = False`
**What it does:** Adds a REAL new measure (`Technician Utilization Rate`) to the
`BrookfieldEnercare` semantic model via SemPy Labs TOM, gated on a prerequisite ontology
mapping (`vw_technician_utilization_summary` → `KR-TECH-UTIL`) already having passed. Apply +
read-back + receipt, same pattern as `nb_13`/`nb_16` but ADDING a new object instead of only
annotating one.
**Demo fit:** This is the "new SQL source becomes a real semantic-model KPI" full-circle
moment — discovery (G18-A) → classification → CDE/ontology mapping → semantic promotion.
**Talking points:** "A brand-new SQL view, tagged in T-SQL comments, ends up as a real DAX
measure in the production model — with a governance receipt at every hop in between."
**Known gotcha (documented in code + memory):** `Microsoft.AnalysisServices.Tabular` types must
be imported from inside an active `connect_semantic_model` session, never before it — this cost
significant debugging time and is now a standing repo convention.

---

## Phase 6 — Demo Operations

### `nb_18_demo_reset` — `DEMO_MODE = True`
**What it does:** Resets every G19 demo request (Objective edits/certification/recertification,
AI Instruction effective-date/rollback, Data Product certification/expiration/decertification,
CDE/ontology mapping, semantic model promotion) back to its pre-decision status, so the whole
approval narrative can be re-demoed live, indefinitely. Never deletes a governed object row.
**Demo fit:** Not part of the demo narrative itself — this is the "reset the stage" utility run
between rehearsals or between live audiences.
**Talking points:** (internal use only — not shown to an audience) "Run this after a live pass
to put every gated request back to 'awaiting approval' so tomorrow's demo starts fresh."
**Note:** re-approving after a reset needs a small manual status flip (`Submitted`→`Approved`)
plus re-running the matching apply notebook (`nb_11`/`nb_17`) — the original build scripts
won't reapply a reset request since they're guarded by existence, not status.

---

## Governance Review Findings (orphan check)

Per request, every notebook was reviewed for content that reaches a production/demo-facing
surface WITHOUT flowing through the closed-loop governance gate — i.e., anything that isn't
pure seed data or architectural schema-building.

| Finding | Detail | Maria-scenario relevance | Status |
|---|---|---|---|
| **`nb_05_push_qa_verified_answers` is missing an `IsCertified` filter** | `nb_04`'s KPI description write-back correctly filters `WHERE IsCertified = 1` before touching the semantic model. `nb_05`'s equivalent read (`ai_instruction`/`verified_answer` rows) filters only `WHERE IsDraft = 0` — there is no certification check at all. The baseline seed content in `nb_04a` (Maria's source story, KPI definitions, terminology, all verified answers) is written with `IsDraft=0` but **no `IsCertified` value at all** (the seed `AI_SCHEMA` doesn't include the column), so it lands as `IsCertified = NULL`. Nothing today stops a future `IsDraft=0, IsCertified=0` row from reaching the Data Agent's live grounding the same way. | Directly affects Act 1 (Tom's Data Agent grounding) and the Act 3 promise that KPI/definition drift is "structurally impossible" — that same structural guarantee does not currently extend to AI instructions/verified answers. | ✅ **Fixed 2026-08-13.** `nb_05` now filters `WHERE IsDraft = 0 AND IsCertified = 1`, matching `nb_04`'s KPI pattern exactly. `nb_04a`'s baseline seed (`AI_SCHEMA`) was extended with `IsCertified`/`CertifiedBy`/`CertifiedDate`, stamping all baseline content `IsCertified=1, CertifiedBy="Victoria Tan"` (a plain constant distinct from any real approver UPN) so the new gate doesn't silently drop Maria's grounding content. Both DELETE reseed guards updated to only ever reseed rows that are uncertified OR certified under this baseline-seed authority — a real `nb_11`-stamped governance approval (always a real UPN) is never touched. Live-verified end-to-end: reran `nb_04a` then `nb_05` in the live workspace, then a temp read-only notebook confirmed `verified_answer: total_draft0=34 certified=34` and `ai_instruction: total_draft0=8 certified=8` (5 rows `CertifiedBy=Victoria Tan` baseline + 3 rows `CertifiedBy=ci.zhu@...` real governance approvals) — 100% of grounding content reaches the Data Agent, nothing silently dropped. |
| Everything else reviewed | Domains/data products/glossary/CDE publication (`nb_07`/`nb_07a`/`nb_07b`/`nb_08`/`nb_09`) republish already-governed SQL/CSV source content — no bypass found. `nb_11`/`nb_16`/`nb_17` all correctly fail closed on a required prior receipt before applying. `nb_10` is read-only validation. `nb_18` never deletes a governed row. | — | 🟢 No other orphans found |

**Recommendation:** ~~Decide whether to fix the `nb_05` gap before the demo pass~~ — fixed and
live-verified 2026-08-13; no further action needed for this pass.
