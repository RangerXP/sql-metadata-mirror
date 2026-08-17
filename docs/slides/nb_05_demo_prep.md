# Notebook 05: `05_publish_governance_domains` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/05_Notebook_Description.md` (validation history),
this document catalogs the **Purview-published artifacts** this notebook creates, evaluates
them against build requirements, and explains how they support the demo narrative. Source
document for demo slide development.

---

## Notebook purpose & role

**What it is:** The first Purview publication notebook. It takes the governance domains, data
products, and business-objective (OKR) layer built in `lh_metadata` and publishes them as real,
live entities in Microsoft Purview via the Atlas API — the moment governance metadata leaves
Fabric's own working store and becomes visible in the actual governed catalog (T4 tier).

**How it's applied:** Runs fifth, always writes dry-run artifacts; live Purview publish is
config-driven (`SQL_MIRROR_ONLY_DEPLOYMENT` / `PURVIEW_PUBLISH_OVERRIDE` / `APPLY_CHANGES`).
Authenticates to Purview via a shared, cached bearer token (falling back to interactive
device-code sign-in only if no cached token exists — a real operational gotcha found and fixed
during validation, since an unattended run with no valid cache would otherwise hang
indefinitely).

**Use-case delivery objective:** This is literally "Customer Operations", "Service Delivery",
and "Revenue and Contracts" domains, and "Customer 360"/"Service Performance"/"Billing and
Contract Health" data products *appearing in Purview* — the exact objects Ci Zhu references
when she shows the auditor the governed catalog in Act 3.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| `EnercareGovernanceDomain` × 3 (Purview Atlas entities) | Live governance domain | Customer Operations, Service Delivery, Revenue and Contracts | The top-level organizing structure Ci Zhu points to when explaining who owns what in the demo |
| `EnercareDataProduct` × 3 (Purview Atlas entities) | Live data product | Customer 360 (DP-CUST360), Service Performance (DP-SVCPERF), Billing and Contract Health (DP-BILLHEALTH) | The exact three data products Tom's CRM and Victoria's dashboard conceptually query against — now visible as real, ownable, governed catalog objects |
| `EnercareOKR` × 3 (Purview Atlas entities) | Business Objective | Strategic objectives linked to data products (G11-1 ontology layer) | Lets a business stakeholder trace a strategic goal down through Purview to the governed data product backing it |
| `EnercareOKRKeyResult` × 5 (Purview Atlas entities) | Key Result | Measurable KPI targets under each Objective | Ties strategic intent to the same certified KPIs (e.g. PP Renewal Rate) the semantic model reports |
| `Files/purview_publish/typedefs_day2.json` | Dry-run artifact | Atlas entity-type definitions | Reviewable payload of exactly what will be/was published — auditable even without live Purview access |
| `Files/purview_publish/entities_day2.json` | Dry-run artifact | Full entity payload (14 entities: 3 domains, 3 products, 3 OKRs, 5 key results) | Same purpose — a durable, inspectable record independent of the live Purview state |
| `Files/purview_publish/.purview_token_cache.json` | Shared auth artifact | Cached Purview bearer token | Lets this notebook and 06/08/09 avoid repeating an interactive sign-in within the token's validity window |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Purview is the governed catalog endpoint" (T4 tier) | This is the first notebook to actually write into that tier — domains and data products become real Purview objects here |
| "Deliver one native Purview workflow first" before expanding | Domains/data products are the simplest, foundational publish — glossary/CDE/lineage (notebook 06) build on top of these already existing |
| G11-1 ontology layer: OKRs linked to data products | Directly implemented — `EnercareOKR`/`EnercareOKRKeyResult` entities carry `linked_data_product_ids` reference attributes |
| Unattended runs must not silently hang | Found and fixed during validation: an unattended run with no cached Purview token blocked on an interactive device-code prompt for ~18 minutes before Fabric cancelled it — fixed by pre-seeding the shared token cache |

## Demo narrative support

- **Act 3 (Ci Zhu's audit walkthrough):** open Purview's Unified Catalog, navigate to Governance
  Domains, and the three domains/three data products are simply *there* — a slide can screenshot
  the Purview portal directly next to the `entities_day2.json` payload that produced it, showing
  code-to-catalog traceability.
- **Talking point:** "One notebook, three domains, three data products, published directly via
  the Atlas API — the same objects a Purview admin would create by hand in the portal. The OKRs
  on top of them are what let a business stakeholder trace a strategic goal down to the governed
  data product backing it."

## High-level outcome

By the end of this notebook, Purview's Unified Catalog holds real, live governance domains,
data products, and business objectives — the foundational catalog structure that notebook 06's
glossary terms and CDEs attach to, and that Ci Zhu's Act 3 audit walkthrough is built around.

---

See also: [`docs/05_Notebook_Description.md`](../05_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
