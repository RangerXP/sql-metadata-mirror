# Notebook 02: `02_build_metadata_foundation` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/02_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The governance metadata foundation. Ingests the customer-authored governance CSVs
(`purview/*.csv` — domains, data products, glossary terms, CDEs, roles, labels, OKRs, mirrored
from their SQL-seeded source) into `lh_metadata`, then reconciles that curated metadata against
the live semantic model to build the annotation payloads later notebooks write back. Runs
second, always live.

**Why it matters for the demo:** this is where "one governed definition" becomes real,
queryable data instead of a design document. Every `GT-*`/`CDE-*`/`DP-*` code referenced
anywhere in Tom's call, Victoria's review, or Ci Zhu's audit answer has exactly one row here.

## Where this fits: the 3-tier contract & ontology

This notebook is the **Tier 3 ingestion point** — the first place the Tier 1 SQL contract's
governance content lands for consumption. (See
`docs/governance-ontology-and-data-contract-model.md` §2–3 for the full 3-tier model and
ontology graph.)

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 3 (consumption)** — reads the Tier 1 SQL contract via its Tier 2 Fabric-mirrored copy, never invents governance content itself |
| Ontology footprint | Populates the **entire ontology dimension layer**: `domains`, `data_products`, `glossary_terms`, `cdes`, `okrs`/`okr_key_results`/`okr_data_products` — every entity and typed relationship in the ontology graph originates here |
| Governance workflow | None directly — this is metadata *ingestion*, not an approval workflow. It also stages `sm_annotations`, the reconciliation payload `04_writeback_governed_metadata` later applies under its own certification gate |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| `domains` / `data_products` (3 / 3 rows) | Customer Operations, Service Delivery, Revenue and Contracts domains; Customer 360, Service Performance, Billing and Contract Health products | The exact three-and-three Ci Zhu references in Act 3 and Tom's/Victoria's tools query against |
| `glossary_terms` / `cdes` (35 / 12 rows) | The certified business-term and critical-data-element catalog | The single definition source for every business term the demo cites (`GT-SLA`, `GT-CONSENT`, etc.) |
| `role_assignments` (48 rows) | Domain/product/term ownership and stewardship | Backs every "who owns this" answer (Victoria, Ci Zhu, Rupal, Shruthi, Ranbir) |
| `label_assignments` (9 rows) | Sensitivity label assignments | The label-policy gate behind Tom's credit authority and PII visibility during the call |
| `okrs` / `okr_key_results` / `okr_data_products` (3 / 5 / 3 rows) | Business Objectives linked to data products | Lets a stakeholder trace a strategic goal down to the governed data product measuring it |
| `ai_metadata` (certified KPI instructions + verified Q&A) | Certified AI grounding content, gated by `IsDraft`/`IsCertified` | What the Fabric Data Agent reads to answer natural-language questions — including the quantified billing-caller/PP-renewal insight |
| `sm_annotations` (77 rows) | Staged reconciliation payload between curated metadata and the live semantic model | The exact "compile step" between governance intent and semantic-model reality — what notebook 04 applies |

## High-level takeaways (what to say)

- "Every governance object here has exactly one row — one domain, one glossary term, one CDE —
  and that single row is what every other notebook and every Purview publication traces back
  to. That's what makes 'one governed definition' a structural fact, not a policy statement."
- "This notebook doesn't invent metadata — it ingests from the SQL contract and reconciles
  against the live semantic model, proving the two agree before anything gets written back."
- "The AI grounding content here is gated on certification, exactly like the KPI path — nothing
  reaches the Data Agent that hasn't been approved."

## Demo requirements this notebook satisfies

- Establishes every governed entity (domain, data product, glossary term, CDE, objective, key
  result) the rest of the demo references by name.
- Stages the certified, quantified churn-insight verified-answer the Data Agent later cites.
- Proves the semantic model and governance metadata are reconciled before writeback — the
  technical basis for "one measure, one meaning" in Act 3.

---

See also: [`docs/02_Notebook_Description.md`](../02_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

