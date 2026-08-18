# `09_reconcile_semantic_model` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `09_reconcile_semantic_model.Notebook` — what it does,
what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/09_reconcile_semantic_model.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** `False` throughout (intentional — every phase writes real semantic-model
metadata and/or SQL ledger state).

**Legacy name(s):** predecessor of `nb_13_semantic_reconcile` (P2), `nb_14_purview_access_sync`
(P3), `nb_15_purview_dataproduct_sync` (P4 publish), `nb_16_dataproduct_semantic_reconcile` (P4
reconcile), and `nb_17_g18_semantic_promotion` (G18/G19 semantic promotion).

---

## What it does

Four independent Purview-native governance scenarios, in five phases, merged into one file:

- **Cells 1–7 (P2 — GT-SLA):** reconciles the P1-approved `GT-SLA` glossary term definition into
  the `BrookfieldEnercare` semantic model (2 measures + 1 column), fails closed unless the P1
  `PublicationReadback` receipt (from `08_validate_governance_evidence`) already passed, writes
  only the object's `Description` and 4 governance annotations, verifies a fresh read-back, and
  marks the request `Completed` only once both receipts pass.
- **Cells 8–14 (P3 — DP-CUST360 access):** records Rupal Solanki's real Data Product access
  request to Customer 360 and Victoria Tan's two-tier approval. Purview exposes no API or
  diagnostic log for access-request decisions, so the decision is recorded as clearly-labeled
  operator-attested evidence, while the Data Product's own live state (status, domain,
  definition hash) is real, API-verified evidence. This phase has no semantic-model
  reconciliation step — it ends at Cell 14.
- **Cells 15–21 (P4a — DP-SVCPERF publish):** observes Ranbir Singh's real Data Product Publish
  workflow run for Service Performance via the product's own `status` field (a real,
  API-observable proxy, same pattern as P1's term-publish evidence). Enforces a
  Draft-before-Published correlation guardrail so a Published observation can never be recorded
  as approval evidence without a prior Draft baseline for the same correlation.
- **Cells 22–28 (P4b — DP-SVCPERF reconcile):** reconciles the approved publish into semantic-
  model annotations on `fct_service_request.TechnicianId` and `dim_equipment.EquipmentType`,
  mirroring Cells 1–7's pattern exactly.
- **Cell 29 (G18/G19 — semantic promotion):** a single, deliberately flattened cell (works
  around a documented Fabric/TOM import-ordering constraint — `Microsoft.AnalysisServices.
  Tabular` types are only importable from inside an already-active `connect_semantic_model`
  session) that adds a real new measure, `Technician Utilization Rate`, to the model — gated on
  the `vw_technician_utilization_summary` → `KR-TECH-UTIL` ontology mapping already having
  passed. Unlike Cells 1–28, this phase creates a brand-new model object rather than annotating
  an existing one.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `sqldemo.dbo.governance_requests` / `governance_target_receipts` / `governed_object_versions` | Every phase's upstream gate check (P1 receipt for P2, prior Draft observation for P4a, publish receipt for P4b, ontology-mapping receipt for G18) |
| Purview Unified Catalog `GT-SLA` term (already Published, from P1) | P2's source definition (Cell 3) |
| Purview Unified Catalog `Customer 360` data product | P3's live status/domain/definition-hash observation (Cell 10) |
| Purview Unified Catalog `Service Performance` data product | P4a's live status/domain/definition-hash observation (Cell 17) |
| `BrookfieldEnercare` semantic model (live, via SemPy Labs TOM) | Read/write target for P2, P4b, and G18 |

### Outputs produced

| Output | Detail |
|---|---|
| `fct_service_request[SLA Breach Count]` / `[SLA Compliance Rate]` measures, `fct_service_request.IsSlaBreachFlag` column | P2 — `Description` + `Glossary_Term_References`/`Purview_Term_Id`/`Purview_Publication_Content_Hash`/`Governance_Request_Id` annotations |
| `sqldemo.dbo.governance_target_receipts` (`SemanticModelReadback`, GT-SLA) | P2's read-back evidence; request `PV-GT-SLA-0359C207890E4EB1B8AB` marked `Completed` |
| `sqldemo.dbo.governance_requests`/`events`/`target_receipts` (`DataProductAccess`) | P3's attested access-decision record for `PV-CUST360-ACCESS-BD3BEBA460C530FA5076` |
| `sqldemo.dbo.governed_object_versions`/`governance_target_receipts` (`PublicationReadback`, DP-SVCPERF) | P4a's Draft/Published observation evidence for `PV-DP-SVCPERF-9EAF4919D7DFD8F8B5C6` |
| `fct_service_request.TechnicianId` / `dim_equipment.EquipmentType` columns | P4b — `Description` + `DataProduct_References`/`Purview_DataProduct_Id`/`Purview_Publication_Content_Hash`/`Governance_Request_Id` annotations |
| `sqldemo.dbo.governance_target_receipts` (`SemanticModelReadback`, DP-SVCPERF) | P4b's read-back evidence; same request marked `Completed` |
| `fct_service_request[Technician Utilization Rate]` measure (new) | G18 — a brand-new measure, not an annotation, gated on `SEMPROMO-TECHUTIL-001` |
| `lh_metadata.nb09_diagnostics_log` | Real exception + traceback capture across every phase, since Fabric's job API exposes no cell-level detail |

## Demo fit

Closes the loop for three of the four Purview-native scenarios started earlier in the sequence
(GT-SLA, DP-CUST360, DP-SVCPERF), and delivers the "a new SQL source becomes a real
semantic-model KPI" full-circle moment via the G18/G19 measure promotion.

## Talking points

"Same apply-then-verify pattern throughout, whether the source of truth is a SQL-controlled
request or a real Purview approval — rerun any of these phases against the same request and you
get the same receipt, re-validated, not a new one fabricated. That's idempotent self-correction,
not just a one-time write."

## Dependencies / downstream consumers

- P2 depends on `08_validate_governance_evidence`'s P1 `GT-SLA` `PublicationReadback` receipt
  already having passed.
- P4b depends on P4a's `PublicationReadback` receipt already having passed (same governance
  request, same notebook, two phases).
- G18 depends on a prior `OntologyMappingReadback` receipt for the source object already having
  passed (built outside this notebook).
- The `Technician Utilization Rate` measure this notebook adds is a real, git-tracked TMDL
  change to `BrookfieldEnercare.SemanticModel/definition/tables/fct_service_request.tmdl`.

---

See also: [`08_Notebook_Description.md`](./08_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/09_reconcile_semantic_model.md`](./runbooks/notebook-validation/09_reconcile_semantic_model.md)
(build/debug history and live-run evidence) ·
[`docs/10_Notebook_Description_pending.md`](./10_Notebook_Description_pending.md)
