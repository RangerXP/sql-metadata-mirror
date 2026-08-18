# Notebook 09: `09_reconcile_semantic_model` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/09_Notebook_Description.md` (validation history),
this document catalogs the **governance artifacts this notebook produces**, evaluates them
against build requirements, and explains how they support the demo narrative. Source document
for demo slide development.

---

## Notebook purpose & role

**What it is:** The closed-loop payoff notebook — it's where three separately-approved Purview
governance decisions (a glossary term, a data product access request, a data product publish)
actually land as real metadata inside the live semantic model, plus one brand-new KPI measure
born from a governed source object.

**How it's applied:** Runs ninth. Five phases, each independently gated on its own upstream
approval/receipt, each writing only the metadata it owns, each re-verifying a fresh read-back
before marking its own request `Completed`.

**Use-case delivery objective:** This is the "does the approval actually change anything a
report consumer sees" proof point — a glossary term's governed definition shows up as a real
measure description, a data product's approved publish shows up as real column annotations, and
a new Key Result gets a real KPI measure, not a slide claiming one exists.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| GT-SLA semantic annotations | `_Measures[SLA Breach Count]`/`[SLA Compliance Rate]`, `fct_service_request.IsSlaBreachFlag` | Governed definition text + 4 traceability annotations | The measure a report author sees now carries Ci Zhu's approved SLA definition, not a generic description |
| DP-CUST360 access evidence | `sqldemo.dbo.governance_requests`/`events`/`target_receipts` | Victoria Tan's two-tier approval of Rupal Solanki's access request, clearly labeled attested | The demo's honest answer to "can you always machine-verify an approval" — no, and here's exactly where and why |
| DP-SVCPERF publish evidence | `sqldemo.dbo.governed_object_versions`/`governance_target_receipts` | Ranbir Singh's real Draft→Published workflow transition, observed via the product's own live status | A real workflow event, not a SQL-side simulation of one |
| DP-SVCPERF semantic annotations | `fct_service_request.TechnicianId`, `dim_equipment.EquipmentType` | Governed DP-SVCPERF definition text + 4 traceability annotations | Same "approval actually changes the model" proof as GT-SLA, on a different object type |
| `Technician Utilization Rate` measure | `fct_service_request[Technician Utilization Rate]` (new) | `DIVIDE(DISTINCTCOUNT(TechnicianId), COUNTROWS(...))`, tied to `KR-TECH-UTIL` | The full-circle "governed source table becomes a real report KPI" moment |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Approvals must change the model, not just a SQL row" | Every phase writes real `Description`/annotation changes via SemPy Labs TOM, then re-reads the model read-only to verify the write actually landed, before marking anything `Completed` |
| Fail closed on missing upstream evidence | Every phase's first real cell checks its specific upstream receipt/gate and raises immediately if it's missing or hasn't passed |
| Honest about platform limitations | P3's access decision is clearly labeled operator-attested in both the code (`ATTESTATION_LIMITATION_NOTICE`) and this notebook's own printed output — never presented as machine-verified when it isn't |
| Idempotent re-runnability | Rerunning any phase against the same request produces the *same* receipt ID, re-validated — confirmed live for GT-SLA (P2) and proven necessary for DP-SVCPERF (P4a) when an idempotent rerun surfaced and fixed a real guard-tolerance bug |
| Governance contract adherence | `tools/audit_seed_vs_source.py --target both` and `tools/validate_required_columns_not_null.py --target both` both ran clean immediately after this notebook's live run |

## Demo narrative support

- **The "did it actually change anything" moment:** open the `SLA Breach Count` or
  `TechnicianId` object in the model and show its `Description` and annotations — this is the
  literal, physical result of an approval that happened minutes or days earlier in Purview, not
  a screenshot.
- **The honesty moment (P3):** "Purview doesn't expose an API or log for data-product access
  decisions — so instead of pretending we machine-verified it, we record it as attested, clearly
  labeled, right next to the parts we genuinely did verify (the product's own live status)."
  This is a stronger trust story than quietly papering over the gap.
- **The full-circle moment (G18):** `Technician Utilization Rate` started as a plain SQL view
  someone tagged with `@tag`; by the end of this notebook it's a real, governed measure a report
  author can drag onto a canvas — the entire discovery-to-KPI pipeline made visible in one demo.
- **A real bug made the idempotency story concrete, not theoretical:** this notebook's first
  live run surfaced a genuine guard bug — an already-`Completed` request from a prior session
  was incorrectly rejected on rerun as "no prior Draft observation." Fixing it (tolerate
  `Completed` as proof Draft was already seen) is itself a good talking point about what
  "idempotent" has to mean in practice, not just in theory.

## High-level outcome

By the end of this notebook, 4 governance requests spanning 3 independent Purview scenarios are
`Completed` with 6 `Passed` receipts, the live semantic model carries real governed metadata on
5 existing objects, and a brand-new measure exists for a governed Key Result — all confirmed via
direct SQL query and a fresh Power BI Modeling MCP reconnect, not just notebook print output.

---

See also: [`docs/09_Notebook_Description.md`](../09_Notebook_Description.md) (validation history) ·
[`docs/runbooks/notebook-validation/09_reconcile_semantic_model.md`](../runbooks/notebook-validation/09_reconcile_semantic_model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
