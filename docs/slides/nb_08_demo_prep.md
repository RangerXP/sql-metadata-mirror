# Notebook 08: `08_validate_governance_evidence` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/08_Notebook_Description.md` (validation history),
this document catalogs the **governance artifacts this notebook produces**, evaluates them
against build requirements, and explains how they support the demo narrative. Source document
for demo slide development.

---

## Notebook purpose & role

**What it is:** The governance health-check notebook — a read-only scorecard proving the
stewardship, control, and AI-readiness state of everything built by notebooks 02–07, plus the
one place in the demo that observes a *real* Purview-native approval workflow (`GT-SLA`)
through its own API rather than a SQL-side simulation.

**How it's applied:** Runs eighth. Cells 1–6 (with 5a) are pure validation — no writes to
source data, only to this notebook's own scorecard tables. Cells 7–13 (`DEMO_MODE = False`)
observe and record one real Purview workflow event.

**Use-case delivery objective:** This is the proof point for "we don't just claim governance
maturity, we can show it" — every domain, data product, and CDE has a resolvable steward and
owner, every control check passes, and the `GT-SLA` term shows a genuine Draft→Published
correlation chain observed through the Unified Catalog API.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| Stewardship scorecard | `lh_metadata.purview_phase_08_stewardship_scorecard` (18 rows) | Every domain/data-product/CDE with its resolved owner, steward, and certification status | The single table an auditor or a skeptical SE would ask for first — "prove every governed object has an accountable human" |
| Controls validation | `lh_metadata.purview_phase_09_controls_validation` (4 checks) | Confidential-label-rule coverage, sensitive-CDE identification, label-policy coverage, DLP mode (manual gate) | Shows the sensitivity/label layer is populated and internally consistent before any DLP policy is actually switched on live |
| AI readiness validation | `lh_metadata.purview_phase_10_ai_readiness_validation` (4 checks) | Certified/published product count, glossary-term/CDE binding coverage, semantic annotation availability | The "is it safe to let Copilot/Data Agents answer from this" gate — governed grounding, not raw table access |
| Ontology validation | `lh_metadata.purview_phase_11_ontology_validation` (4 checks) | OKR availability, OKR↔data-product linkage, key-result↔OKR resolution | Proves the business-objective layer (OKRs) is a real, resolvable graph on top of the governed data, not a decorative addition |
| Closeout rollup | `lh_metadata.purview_phase_08_10_closeout` | 4-row summary (rows checked / action-required / PASS-FAIL per phase) | The one table to screenshot for a "governance health: all green" slide |
| `GT-SLA` P1 evidence | `sqldemo.dbo.governance_events` / `governed_object_versions` / `governance_target_receipts` | A real Purview Unified Catalog term's Draft→Published transition, observed and durably recorded | The demo's one moment of "this actually happened inside Purview, we're reading it back, not asserting it" |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Prove governance maturity with real data, not assertions" | Every scorecard row is computed from `lh_metadata` tables written by earlier notebooks, keyed by real UPNs (Rupal Solanki, Shruthi Srinivas, Ci Zhu) — confirmed via direct SQL read-back, not just notebook print output |
| Real Purview workflow evidence (not SQL-only simulation) | Cell 9 calls the live Unified Catalog API for `GT-SLA`'s actual `status`; Purview exposes no workflow-request API, so status + correlation ID is the best real observable proxy for "was this approved" |
| Governance contract adherence | Every table this notebook reads passed a full governance-contract audit — value parity, row counts, enum compliance, and referential integrity against the seed `.sql` files (`tools/audit_seed_vs_source.py`) — 0 failures |
| No NULLs in required governance fields | `tools/validate_required_columns_not_null.py --target both` — 0 violations across 74 required-column checks, including all 3 steward columns |

## Demo narrative support

- **The scorecard as opening/closing proof point:** show the closeout rollup table (4 rows, all
  PASS) early to set the "everything here is real and governed" frame, or late as the payoff
  after walking through the individual approval scenarios in notebooks 05–07.
- **The `GT-SLA` moment:** this is Ci Zhu's audit answer — "who approved the SLA definition, and
  how do you know?" — answered by a live API read-back of the term's own status and a durable
  evidence chain, not a screenshot or a claim.
- **Talking point:** "This is our own governance health check, and this is what a real approval
  inside the Purview portal looks like once read back through the API — not a SQL-side
  approximation."
- **A real regression made this a stronger story, not a weaker one:** the steward columns
  briefly regressed to NULL during this build (see `docs/02_Notebook_Description.md`), and this
  notebook's scorecard is exactly what caught it — a genuine demonstration of why a governance
  health-check notebook belongs in the pipeline at all.

## High-level outcome

By the end of this notebook, four independent validation phases (stewardship, controls, AI
readiness, ontology) all report 0 `ACTION_REQUIRED`, and one real Purview-native workflow
(`GT-SLA`) has a durable, re-verifiable evidence receipt. Live validation on 2026-08-18 also
confirmed the entire governance metadata layer (10 tables, both at the sub2 SQL source and the
`lh_metadata` destination) genuinely adheres to its own `.sql` governance contract — correct
values, correct counts, correct enums, and a fully-resolving ontology graph.

---

See also: [`docs/08_Notebook_Description.md`](../08_Notebook_Description.md) (validation history) ·
[`docs/runbooks/notebook-validation/08_validate_governance_evidence.md`](../runbooks/notebook-validation/08_validate_governance_evidence.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
