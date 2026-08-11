---
mode: agent
description: "Final completion pass for the Enercare metadata demo. Audit the active build against Alison Pouw's governance requirements, distinguish custom Atlas artifacts from native Purview capabilities, close verified gaps safely, execute the full demo test pack, and produce an evidence-backed completion package."
tools: ["filesystem"]
---

# Enercare Demo — Verify, Refresh, and Re-enforce the Active Build Model

The Enercare metadata demo was **largely completed**. Your job is NOT to rebuild it. Audit the
current branch and live environment, distinguish code generation from live deployment, close only
the gaps proved by evidence, and produce the final completion package.

Do not equate any of the following:

- a CSV definition with a deployed Purview object;
- an Atlas custom entity with a native Unified Catalog governance domain or data product;
- an Atlas label/classification with a Microsoft Information Protection sensitivity label;
- a generated payload or PASS validation row with successful live publication;
- a metadata status column with a functioning Purview approval workflow;
- a five-prompt smoke test with completion of the full Maria test pack.

**Primary design document (read first, then UPDATE at the end):**
`docs/Enercare-Demo-SemPy-Design-Guide.md` — this is the canonical design stage. Its §5B (five
Purview Delivery Milestones), §5C (Phase 3 / Maria milestones), §6 (Layer Responsibilities), and
§7 (Things to Validate) are your checklist. You will add verified build+deploy status to it.

**Supporting docs:** `docs/design-gap-analysis.md`, `docs/semantic-model-annotations.md`,
`docs/purview-maria-north-star-scenario.md`, `docs/purview-demo-data-design.md`,
`docs/purview-csv-alignment.md`.

---

## 0. How to work

- **Evidence-based.** Use these statuses: `BUILT`, `DRY_RUN_VALIDATED`, `LIVE_ATLAS_PUBLISHED`,
  `NATIVE_PURVIEW_DEPLOYED`, `DEMO_VALIDATED`, `GAP`, or `DRIFTED`. Use the highest status whose
  evidence exists. A validation table or payload is not deployment evidence.
- **Native-versus-custom gate.** Record separately whether domains, products, workflows, and labels
  are native Purview/Unified Catalog/Information Protection capabilities or custom Atlas metadata.
- **Portal/runtime evidence required.** `NATIVE_PURVIEW_DEPLOYED` requires an export, screenshot,
  API read-back, or portal read-back of the live object. `DEMO_VALIDATED` requires successful runtime
  execution using the live object.
- **Do not rebuild deployed components.** If verification passes, leave it and record the proof.
- **Safe execution is a release gate.** Before running anything, change every notebook to default to
  dry-run. `APPLY_CHANGES=False` and `PURVIEW_PUBLISH_OVERRIDE=False` must be committed defaults.
  Live execution is enabled only for the approved run and must not auto-enable an override.
- **Reconcile reality against the doc.** If actual repo/tenant state contradicts the guide, trust reality and correct the guide — but report the delta.
- **One repo, three worktrees.** Confirm you are on the branch that carries the full `nb_07→nb_10` chain AND the two named Data Agents before auditing (see design-gap-analysis for the branch reconciliation state).

### Mandatory preflight corrections

Complete these before evaluating any existing PASS/DEPLOYED claim:

1. Fix `nb_10_purview_stewardship_ai` so `has_steward` and `has_owner` validate actual populated
   values. Do not allow object-type checks to make those flags automatically true.
2. Set `nb_08_purview_glossary_cde` and `nb_09_purview_labels_lineage` to dry-run defaults and remove
   automatic enabling of `PURVIEW_PUBLISH_OVERRIDE`.
3. Confirm credentials/tokens are acquired at runtime and no credential is stored in source.
4. Re-run the Phase 8-10 closeout after the stewardship-gate correction. Discard the previous
   zero-`ACTION_REQUIRED` result as completion evidence until this rerun passes.

### Manual-action and evidence contract

Some native Purview, Information Protection, Fabric lineage, and workflow actions may require the
portal or tenant permissions unavailable to the VS Code agent. In those cases:

1. Generate an exact operator checklist with the object names, settings, and expected result.
2. Stop before claiming completion and request the resulting screenshot/export/API read-back.
3. Save supplied evidence under `docs/runbooks/final-evidence/` with a descriptive filename.
4. Resume the matrix only after the evidence exists.

Never replace a native portal requirement with a custom Atlas object merely because it is easier to
automate. Never fabricate a successful tenant action.

---

## 1. The active build model — 5 architectural pillars (re-enforce these)

Everything you verify must serve this model. Bind each pillar to the correct **plane**:
**Data plane** (OneLake Delta / lakehouse) · **Model plane** (semantic model TOM descriptions + annotations, via SemPy Labs) · **Governance plane** (Purview Unified Catalog).

### Pillar 1 — Self-adapting metadata repository (closed reconciliation loop)
As the data model changes, the loop re-converges: **SemPy reads** current model → **diff vs `lh_metadata`** on `DefinitionHash` → new/changed objects seeded (drafts flagged) → **`nb_07b` reconciles** to `vw_business_metadata_current` (only `status=Published` flows on) → **`nb_04_sempy_writeback` writes back** changed objects only (idempotent) → **SemPy re-reads** → report/Copilot surface the new state. Loop must sit downstream of mirror + `nb_03` star-schema refresh, and be schedulable (pipeline/notebook trigger).
- **Verify:** add a new column to a mirrored table → run the loop → confirm the column appears in the model with seeded draft metadata, and re-runs touch only changed objects.

### Pillar 2 — Lineage back to the SQL Server source record
Scan **both Azure SQL and Fabric**. The SQL scan supplies source inventory, classifications, and the
source-of-record anchor; the Fabric scan supplies lakehouse, semantic-model, and report inventory.
Retire only the dependency on `sys.extended_properties`, not the SQL scan. Two lineage surfaces are
required. **Fabric semantic-model lineage view** shows mirror→lakehouse→model→report. **Purview
lineage** extends left to Azure SQL. If native lineage is incomplete under private networking, use
custom Atlas process edges from `nb_09_purview_labels_lineage`. Keep SQL and Purview private; native
SQL stored-procedure lineage extraction is optional diagnostics and must not justify public SQL
access. Custom edges must resolve to native scanned asset identities.
- **Verify:** at least one KPI chain (Net Revenue or FCR) resolves **SQL server → OneLake → semantic model → report** in Purview, and the mirrored-source origin is visible in the Fabric lineage view.

### Pillar 3 — AI annotations that travel with the data (model level)
Grounding is written at the **semantic-model level** as TOM **descriptions** (first-class) + **annotations** (`AI_Instruction`, `PBI_AI_Instructions`, `PBI_AI_VerifiedAnswers`, `IsCertified`, `GlossaryTerm`) via SemPy Labs (`nb_04_sempy_writeback`, `nb_05_push_qa_verified_answers`). Verified Q&A is written to its own `PBI_AI_VerifiedAnswers` annotation, distinct from `PBI_AI_Instructions`, so the two governed constructs stay independently addressable/regenerable. They travel with the model (export, Git-TMDL sync, Purview scan) and are read by every consumer — **no `.copilot`/skills folder**. Optionally mirror key descriptions onto the lakehouse table (data plane) for OneLake-catalog discovery.
- **Verify:** column descriptions + AI annotations present on the model; Copilot and BOTH Data Agents answer FCR / PP-renewal / CSAT from the governed definitions; confirm no skills-folder dependency exists.

### Pillar 4 — Purview governance objects (Alison's required artifacts)
Author on the governance plane from the source CSVs: **3 native governance domains**, **3 native
Unified Catalog data products**, **35 glossary terms**, **12 CDEs**, **48 role assignments**,
Data Map classifications, **Microsoft sensitivity labels and policy behavior**, lineage edges, and
the custom SIN classifier/SIT.

`EnercareGovernanceDomain` and `EnercareDataProduct` custom Atlas entities may remain as supplemental
technical metadata, but they do not satisfy the native-domain or native-data-product requirement.

Separate:

- Data Map classifications and custom SIN classification;
- MIP/Fabric sensitivity labels;
- mandatory/default/auto-label policy behavior.

- **Verify:** native domains and products are discoverable in Unified Catalog; products are bound to
  real SQL, Fabric, and semantic-model assets; glossary/CDE bindings read back; the SQL and Fabric
  scans are healthy; the custom SIN classifier is active; the Fabric semantic model displays the
  expected real sensitivity label.

### Pillar 5 — Purview as the functional governance model (authoring, status, KPI certification, approval gates) — must be DEMOABLE
Native governance objects carry owners, stewards, lifecycle state, and approval/publishing workflow.
The demo must not simulate approval by editing a CSV status alone.

Implement the return path:

`Purview approval/certification state → scheduled/API read-back → lh_metadata.governance_state →
nb_07b reconciliation → nb_04 SemPy Labs writeback → semantic-model certification annotation`.

Use one representative KPI (FCR recommended): Draft → steward review → domain-owner approval →
Published/Certified → governance-state sync → `IsCertified=true` + approved definition + steward →
changed Copilot/Data Agent answer. Draft and AI-generated metadata remain excluded.

- **Verify:** capture the native workflow request, approval, state read-back, reconciliation result,
  semantic-model annotation, and before/after AI response. Re-run corrected `nb_10` and require zero
  genuine `ACTION_REQUIRED` rows.

---

## 2. Verification matrix — pillar → design-guide milestone → artifact → deployment evidence

Cross-walk each pillar to the guide's own milestones and validation tables. Fill the Status column.

| Pillar | Guide milestone (§5B / §5C) | Notebook / artifact | Completion evidence to capture | Status |
|---|---|---|---|---|
| P4 (scans) | M1 — Platform registration & scans | Purview scans; `nb_05b`, `nb_07a` | SQL + Fabric assets searchable in Data Map; scan history clean | |
| P4 (native domains/products) | M2 — Governance foundation & data products | Native Unified Catalog configuration plus `domain-charter.csv` and `data-product-catalog.csv` | 3 native domains + 3 native products read back; each product bound to SQL, Fabric, and model assets; owners/stewards visible | |
| P4 (custom Atlas supplemental objects) | M2 — Supplemental technical metadata | `nb_07_publish_to_purview` | Atlas API read-back explicitly labeled supplemental, not counted as native domains/products | |
| P4 (glossary/CDE) | M3 — Glossary & CDEs | `glossary-master.csv`, `cde-catalog.csv`, `nb_08_purview_glossary_cde` | validation PASS plus live glossary/CDE read-back and asset bindings | |
| P2 + P4 (classifications/lineage) | M4 — Data Map classification and lineage | `nb_09_purview_labels_lineage` | classification read-back; one SQL→mirror→semantic model→report chain visible in Purview; Fabric lineage screenshot | |
| P4 (sensitivity labels) | M4 — Information Protection | `label-policy.csv` plus Fabric/Purview Information Protection configuration | real MIP label displayed on pilot semantic model; mandatory/default/auto-label behavior demonstrated | |
| P1 + P3 (metadata/writeback) | M5 — Runtime metadata and AI readiness | `nb_07b_merge_customer_metadata`, `nb_04_sempy_writeback`, `nb_05_push_qa_verified_answers` | model read-back of descriptions/annotations; repeat run proves idempotence; schema-change test passes | |
| P5 (stewardship controls) | M5 — Stewardship/certification | corrected `nb_10_purview_stewardship_ai` | corrected closeout has zero genuine `ACTION_REQUIRED`; DLP mode explicitly chosen | |
| P5 (native certification loop) | M5 / §7 item 5 | native approval workflow + governance-state sync + `IsCertified` annotation | live Draft→approval→Published→model-writeback→changed-answer transition captured | |
| P3 (Maria AI quality) | §5C P3-1…P3-6 | KPIs, Verified Answers, AI Instructions, backfit artifacts | all 10 Maria cases executed; no unresolved blocking backfit; signed P3-6 closeout | |

For any incomplete row: fix the implementation, run dry-run, obtain explicit approval for the live
run, publish, read the object back, execute its demo behavior, and record the evidence. Never promote
a row based only on generated JSON or a validation-table count.

---

## 3. Update the design guide (modify in place)

After the audit, **edit `docs/Enercare-Demo-SemPy-Design-Guide.md`** so it reflects verified state — do not fork a new doc:

1. Replace the broad `DEPLOYED` statements with the evidence statuses defined in §0. Split M2 into
   native Unified Catalog versus custom Atlas evidence, and split M4 into classifications/lineage
   versus MIP sensitivity labels.
2. Add a new top section **`## 0. Build Verification Summary (<date>)`** with a status table across the 5 pillars and the 5 milestones, and a short "remaining gaps" list.
3. Update **§7 Things to Validate** — check off items now resolved (target semantic model, subscription/tenant choice, AI Data Schema scope, ontology shape, certification authority); leave open ones flagged.
4. Reconcile any notebook-name or numbering references to the branch you verified against (`nb_07 / nb_07a / nb_07b / nb_08 / nb_09 / nb_10`, `nb_04_sempy_writeback`).
5. Correct the architecture text so SQL and Fabric are both scanned. Retire only the
   `sys.extended_properties` dependency, not the SQL source scan.
6. Record Maria execution honestly: the project is not closed until 10/10 cases are executed and the
   P3-6 sign-off decisions are completed.
7. Keep the Appendix (Alison's verbatim comments) unchanged.

Mirror the same status into `docs/design-gap-analysis.md` gap rows (G5, G6, G8, G9, G10) so the two docs agree.

---

## 4. Constraints (do not violate)

- **Three planes, correct binding:** data (OneLake), model (TOM via SemPy Labs), governance (Purview). Annotations live on the **model**, not a `.copilot`/skills folder.
- **SemPy + SemPy Labs is the only primary write-back path.** TMDL stays a Git-backed artifact; do not reintroduce TMDL REST mutation as primary.
- **`sys.extended_properties` is 0/42,372 — do not assume it.** Author from `purview/*.csv`, notebooks, `lh_metadata`.
- **`status=Published` is the publish gate.** Drafts and AI-gap-fill stay in `lh_metadata`.
- **Dry-run defaults are committed.** Live flags are temporary runtime inputs, never source defaults,
  and no code may auto-enable an override.
- **Four-tier placement:** T1 SQL (source+PII) / T2 `purview/*.csv` (policy SoT) / T3 `lh_metadata`+model (working+runtime) / T4 Purview (published SoR).
- **Managed Identity for scans**, `Purview-Scan-Fallback` SP only where a connector requires it.
- **Personas fixed:** Victoria Tan, Ranbir Singh, Ci Zhu (governance admin + steward), Rupal Solanki, Shruthi Srinivas; Christopher Dingle out of demo scope (represented by Ci Zhu).

---

## 5. Definition of Done (verification pass complete when)

1. Every row in §2 is `DEMO_VALIDATED`, or is explicitly excluded from the approved demo scope with
   an owner, risk acceptance, and target date.
2. The self-adapting loop is demonstrated: a schema change re-converges through SemPy Labs and surfaces in Copilot without a full rebuild.
3. One KPI lineage chain (Net Revenue or FCR) shows **SQL server → OneLake → semantic model → report** in Purview, with the mirrored-source origin visible in the Fabric lineage view.
4. Model carries curated descriptions + AI annotations; Copilot and both Data Agents answer FCR / PP-renewal / CSAT from governed definitions — no skills folder.
5. Purview shows 3 **native** governance domains, 3 **native** data products, 35+ glossary terms,
   12 CDEs, and their real asset bindings. Supplemental custom Atlas objects are identified as such.
6. At least one pilot asset displays a real MIP sensitivity label and demonstrates the selected
   mandatory/default/auto-label policy behavior; Data Map classifications remain separately visible.
7. The KPI certification loop runs live through a native approval action and governance-state
   read-back (Draft → approve → Published → certified Copilot answer with steward).
8. `P3I-003`, `P3I-005`, and `P3I-006` are implemented and verified, or formally deferred with
   completed risk acceptance and sign-off.
9. All 10 cases in `maria-northstar-test-results.md` are executed; Case 02 is corrected; no case
   remains Pending.
10. Domain Owner, Data Steward, and Demo Owner complete `phase3-step6-signoff-record.md`.
11. `docs/Enercare-Demo-SemPy-Design-Guide.md` and `docs/design-gap-analysis.md` agree with evidence.
12. The git working tree is clean; changes are committed and pushed; the Fabric workspace is synced
    to the recorded commit; the final run order succeeds from a clean start.

---

## 6. Reporting

Output a single **Project Completion Package** containing:

1. The filled §2 matrix with evidence links/paths and native-versus-custom classification.
2. Safety preflight results and corrected notebook defaults.
3. Dry-run result, approved live-run result, and API/portal read-back for each deployed object.
4. Lineage screenshots/exports and the pilot sensitivity-label evidence.
5. The governance approval-loop before/after evidence.
6. The completed 10-case Maria results and signed P3-6 closeout.
7. Remaining exclusions, each with owner, approved risk, and date.
8. Exact design-guide and gap-analysis edits.
9. Final commit hash, pushed branch, Fabric sync confirmation, and clean run-order result.

Do not declare the project complete if any requirement is supported only by a payload, a custom
Atlas substitute for a native Purview feature, an uncorrected validation shortcut, a pending Maria
case, or an unsigned approval record.
