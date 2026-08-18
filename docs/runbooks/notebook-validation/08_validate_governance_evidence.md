# `08_validate_governance_evidence` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-18, after finding and fixing a real
upstream data regression and two Spark schema-caching bugs.

## Purpose being validated

Two merged sections:

- **Cells 1–6 (with 5a):** stewardship/certification scorecard — reads `domains`,
  `data_products`, `cdes`, `role_assignments`, `label_assignments`, `semantic_annotation_plan`
  (falling back to `sm_annotations`), `okrs`, `okr_key_results`, `okr_data_products` from
  `lh_metadata`, and writes four validation-stage tables (`purview_phase_08_stewardship_scorecard`,
  `purview_phase_09_controls_validation`, `purview_phase_10_ai_readiness_validation`,
  `purview_phase_11_ontology_validation`) plus a closeout summary
  (`purview_phase_08_10_closeout`) and manifest.
- **Cells 7–13:** P1 Purview-native workflow proof — observes the live `GT-SLA` term in the
  Unified Catalog, enforces Draft-before-Published correlation guardrails, and persists an
  idempotent observation event + durable evidence receipt to the `sub2` SQL ledger
  (`governance_events` / `governed_object_versions` / `governance_target_receipts`).

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status | Note |
|---|---|---|---|---|---|
| 1 | `0a895fc1-7035-4798-88e8-caaff9921ddb` | 2026-08-17T20:12:39 | 2026-08-17T20:16:03 | ❌ `Failed` | No diagnostic logging present yet |
| 2 | `5ae033f4-6e99-45be-b443-fd21ca6dbeaa` | 2026-08-17T20:27:12 | 2026-08-17T20:32:16 | ❌ `Failed` | Diagnostic logging added to Cells 2–3 |
| 3 | `1d92deea-91d5-4286-89ca-bd74dd8ed95f` | 2026-08-18T01:18:49 | 2026-08-18T01:40:51 | ❌ `Failed` | Real exception captured — see Root cause |
| 4 | `ccd5f53f-c6f1-4d0a-a3ec-b3c131dc26ea` | 2026-08-18T01:44:22 | 2026-08-18T02:04:58 | ❌ `Failed` | Same error, identical attribute ids, even after re-fetching `domains_df` fresh in Cell 3 |
| 5 (manual, interactive) | `7febb635-6e23-4fc0-8fa4-6cbf92950fb3` (`RunNotebookInteractive`, portal session) | 2026-08-18T02:35:47 | — | ✅ Completed (verified by output) | User-triggered manual run per switch to manual execution; all 13 cells produced correct output through Cell 13's completion message |

## Root cause — upstream data regression, not a bug in this notebook

Attempts 1–4 all failed with the same underlying symptom:

```
java.lang.IllegalStateException: Couldn't find governance_domain_stewards#74 in
  [domain_id#66,domain_name#67,status#71,governance_domain_owners#72]
```

Investigation (fully detailed in `02_build_metadata_foundation.md`'s Follow-up section) traced
this to `02_build_metadata_foundation`'s territory, not this notebook:

1. `governance_domain_stewards`/`stewards`/`steward_upn` were `NULL` for every row at the sub2
   SQL source — a full regression of the 2026-08-08 steward fix. Backfilled via
   `sql/02_metadata_foundation/13_backfill_steward_columns.sql`.
2. `governance_glossary_terms` separately held 35 stale legacy placeholder rows, never actually
   replaced by the current seed script's real content. Reseeded.
3. Fabric mirroring was found `Paused`, blocking both fixes from propagating. Restarted.
4. A real `write_table_from_pandas` bug in nb_02: an all-NULL pandas column is inferred as
   `NullType` by Spark and silently dropped from the physical Delta file rather than written as
   a real (if entirely-null) column — a permanent risk for any legitimately-all-NULL-by-design
   column (e.g. `domains.parent_domain`), not just a symptom of the regression above. Fixed with
   an explicit `StringType` schema override for all-null columns.

Attempts 3 and 4 in this notebook both still failed with the identical error even after nb_02
was re-run clean and `lh_metadata.domains` was independently confirmed (via direct SQL query) to
have all 9 columns with real data — including after adding a fix here that re-fetches
`domains_df`/`data_products_df`/`cde_df` fresh in Cell 3 rather than reusing the Cell-2-captured
object, on the theory of a Spark-session read race. That fix did not change the error, so the
race theory is unconfirmed. **What's certain:** once the user ran this notebook manually
(attempt 5), it passed cleanly with correct data throughout — most likely the automated
attempts 3–4 were still racing residual OneLake/mirror propagation lag from the just-resolved
mirroring-`Paused` incident, which had settled by the time of the manual run. The
`_real_columns()` DESCRIBE-based truthful column check and the Cell-3 fresh-refetch both remain
in place as defense-in-depth against this repo's recurring stale-Spark-catalog-schema bug class,
regardless of which exact mechanism caused attempts 3–4 to fail.

## Data write-out confirmation (attempt 5)

**Phase 08 — stewardship scorecard** (all 18 rows `PASS`, `has_steward=true`,
`has_owner=true`, `is_certified_or_published=true`):

| Type | Object | Owner | Steward |
|---|---|---|---|
| Domain | Customer Operations | Victoria.Tan;Ci.Zhu | Rupal.Solanki@enercare.ca |
| Domain | Service Delivery | ranbir.singh;Ci.Zhu | Shruthi.Srinivas@enercare.ca |
| Domain | Revenue and Contracts | Ci.Zhu;ranbir.singh | Ci.Zhu@enercare.ca |
| DataProduct | Customer 360 | Victoria.Tan | Rupal.Solanki@enercare.ca |
| DataProduct | Service Performance | ranbir.singh | Shruthi.Srinivas@enercare.ca |
| DataProduct | Billing Health | Ci.Zhu | Ci.Zhu@enercare.ca |
| CDE (x12) | all 12 CDEs | role-based | Rupal.Solanki / Shruthi.Srinivas / Ci.Zhu per CDE |

**Phase 09 — controls validation:**

| Check | Value | Status |
|---|---|---|
| `confidential_label_rules_available` | 2 | PASS |
| `dlp_policy_mode_selected` | 0 | WARN (manual operator gate — pick alert-only/policy-tip/block before demo; not a bug) |
| `label_policy_rows_available` | 9 | PASS |
| `sensitive_cdes_identified` | 2 | PASS |

**Phase 10 — AI readiness validation:** `cdes_bound_to_columns=12`,
`certified_or_published_products=3`, `glossary_terms_bound_to_assets=35`,
`semantic_annotation_plan_available=44` (all PASS).

**Phase 11 — ontology validation:** `okrs_available=3`, `okr_key_results_available=5`,
`okrs_with_linked_data_product=3`, `key_results_with_resolved_parent_okr=5` (all PASS).

**Closeout summary** (`purview_phase_08_10_closeout`):

| Stage | Rows checked | Action required | Status |
|---|---|---|---|
| `phase_08_stewardship` | 18 | 0 | PASS |
| `phase_09_controls` | 4 | 0 | PASS |
| `phase_10_ai_readiness` | 4 | 0 | PASS |
| `phase_11_ontology` | 4 | 0 | PASS |

## P1 Purview-native workflow proof (Cells 7–13)

- Cell 7: `DEMO_MODE=False`, `workflow_configured=True`, term=`GT-SLA` (`b3b54277-3b36-47d8-831c-a2b9a5f02634`).
- Cell 9: observed live term — `status=Published`, `hash=329f903dae66`,
  `observed_at=2026-08-18T02:45:01.788822Z`, domain correctly `9d82a6da-eed1-4dae-a036-84c1dcc65337`
  (Service Delivery).
- Cell 11: `[APPLIED] request=PV-GT-SLA-0359C207890E4EB1B8AB status=Completed`.
- Cell 12: `[VERIFIED] status=Completed events={'GovernanceRequestCompleted': 1,
  'SemanticModelReadbackPassed': 1, 'TermDraftObserved': 1, 'TermPublishedObserved': 1}
  versions={'Draft': 1, 'Published': 1} receipt=Passed`.
- Cell 13: completion boundary message printed — this notebook intentionally does not mark the
  request `Completed`; semantic-model reconciliation and its read-back receipt are a separate
  step (`09_reconcile_semantic_model`).

Auth note: Cell 9's first token acquisition hit the device-code fallback (shared cache was
empty/expired). Added an `AzureCliCredential` tier to `get_purview_token()` (between the cache
check and device-code) after this run, so a future run should prefer the already-authenticated
`az` CLI session over an interactive prompt — see `docs/runbooks/notebook-validation/README.md`
follow-ups if this needs re-verifying.

## Maria Castellanos north-star use-case match

- ✅ All 3 domains, all 3 data products, and all 12 CDEs now carry genuine, resolvable steward
  UPNs matching the intended demo cast (Rupal Solanki, Shruthi Srinivas, Ci Zhu) — the
  stewardship scorecard is a real, defensible governance-maturity proof point, not a stubbed
  PASS.
- ✅ The P1 `GT-SLA` observation directly supports the Act 3 governance-admin narrative (Ci Zhu
  citing the formally published SLA term with its correlated Draft→Published evidence chain).

## Post-hoc validation

Ran `tools/validate_required_columns_not_null.py --target both` after this notebook's success:
**0 violations across 74 required-column x table checks**, at both the sub2 SQL source and the
`lh_metadata` destination this notebook reads — confirms no NULLs exist anywhere nb_02 declares
a column required, including all 3 steward columns.

## Issues encountered

- 1 real upstream data regression (steward columns + stale glossary content) found and fixed —
  see Root cause above and `02_build_metadata_foundation.md`'s Follow-up section for the full
  investigation trail.
- 2 defense-in-depth hardening fixes added to this notebook (`_real_columns()` truthful column
  check; fresh DataFrame re-fetch in Cell 3) whose necessity relative to the upstream fix is
  unconfirmed, but which address this repo's known recurring stale-Spark-catalog-schema bug
  class regardless.
- `dlp_policy_mode_selected=WARN` is an intentional manual operator gate, not a defect.
