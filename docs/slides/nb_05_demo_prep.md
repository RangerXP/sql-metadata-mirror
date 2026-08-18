# Notebook 05: `05_publish_governance_domains` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/05_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The first Purview publication notebook. Takes the governance domains, data products, and
business-objective (OKR) layer built in `lh_metadata` and publishes them as real, live entities
in Microsoft Purview via the Atlas API — the moment governance metadata leaves Fabric's own
working store and becomes visible in the actual governed catalog. Runs fifth; live publish is
config-driven (`SQL_MIRROR_ONLY_DEPLOYMENT` / `PURVIEW_PUBLISH_OVERRIDE` / `APPLY_CHANGES`).
Purview authentication reuses a shared cached token, falling back to a non-interactive Azure
CLI credential — it never blocks an unattended run on an interactive sign-in prompt.

**Why it matters for the demo:** this is literally "Customer Operations", "Service Delivery",
and "Revenue and Contracts" domains, and "Customer 360"/"Service Performance"/"Billing and
Contract Health" data products *appearing in Purview* — the exact objects Ci Zhu references
when she shows the auditor the governed catalog in Act 3.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 3 (consumption)** — publishes Tier 3-staged (`lh_metadata`) governance content out to Purview, the catalog-of-record consumption surface |
| Ontology footprint | Publishes the **Domain**, **Data Product**, **Objective**, and **Key Result** ontology entities as real Purview Atlas objects — the first point these entities become externally visible/governable outside this repo's own SQL/Lakehouse tiers |
| Governance workflow | Not itself an approval workflow — a direct, config-gated publish. (Purview-native *approval* workflows for these object types are exercised later, in `08`/`09`.) |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| `EnercareGovernanceDomain` × 3 | Live Purview Atlas entity | Customer Operations, Service Delivery, Revenue and Contracts | The top-level structure Ci Zhu points to when explaining ownership |
| `EnercareDataProduct` × 3 | Live Purview Atlas entity | Customer 360, Service Performance, Billing and Contract Health | The three data products now visible as real, ownable, governed catalog objects |
| `EnercareOKR` × 3 / `EnercareOKRKeyResult` × 5 | Live Purview Atlas entity | Business Objectives and Key Results, linked to data products | Lets a stakeholder trace a strategic goal through Purview to the governed data product backing it |
| `Files/purview_publish/{typedefs,entities}_day2.json` | Dry-run artifacts | Always-written, reviewable publish payloads | Auditable record of what was/will be published, independent of live Purview access |

## High-level takeaways (what to say)

- "One notebook, three domains, three data products, published directly via the Atlas API — the
  same objects a Purview admin would create by hand in the portal."
- "The OKRs on top of them are what let a business stakeholder trace a strategic goal down to
  the governed data product backing it."
- "This is the foundational catalog structure — notebook 06's glossary terms and CDEs attach to
  what gets published here."

## Demo requirements this notebook satisfies

- Act 3: the domains and data products Ci Zhu shows the auditor directly in the Purview portal.
- The ontology's business-objective layer becomes independently visible in the governed catalog,
  not just a SQL/Lakehouse-internal concept.

---

See also: [`docs/05_Notebook_Description.md`](../05_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

