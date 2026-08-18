# Notebook 06: `06_publish_glossary_and_lineage` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/06_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that).

---

## Role in the demo

The glossary, CDE, labels, and lineage publication notebook — the second and final Purview
publication step, building on top of the domains/data products `05_publish_governance_domains`
already created. Runs sixth. Two merged phases sharing one Purview token cache: glossary/CDE
publish with self-healing term maintenance, then sensitivity labels, CDE classifications, and
custom Atlas lineage edges.

**Why it matters for the demo:** this is what makes every `GT-*`/`CDE-*` code referenced
throughout the demo a real, resolvable Purview object, and what gives Purview's lineage view
something to actually show — the single most visually compelling moment in Act 3, Ci Zhu
clicking "View lineage" and tracing a Power BI visual back to source SQL.

## Where this fits: the 3-tier contract & ontology

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 3 (consumption)** — publishes Tier 3-staged glossary/CDE content to Purview, the same consumption surface `05` writes to |
| Ontology footprint | Publishes the **Glossary Term** and **Critical Data Element** ontology entities (and their typed edges — CDE → parent Glossary Term) as real Purview Atlas objects, plus the custom lineage edges that connect the ontology to physical assets across SQL/Fabric/semantic-model |
| Governance workflow | Not itself an approval workflow — a direct, config-gated publish with a self-healing consistency check (term `shortDescription` drift correction) |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| Purview glossary terms × 35 | Live Atlas entity | Every business term cited in the demo (`GT-CUST`, `GT-SLA`, `GT-CONSENT`, etc.) | The single certified definition source an auditor, agent, or executive can look up directly in Purview |
| `EnercareCriticalDataElement` × 12 + CDE-to-term associations | Live Atlas entity + relationship | Critical Data Elements linked to their parent glossary term | The exact linkage Ci Zhu cites when proving single-source-of-truth |
| Sensitivity labels + CDE classifications | Live Purview classification | Confidential/Highly Confidential labels, machine-readable CDE tags | The policy gate behind Tom's credit authority and PII-visibility rules |
| Custom Atlas lineage edges | Live Atlas Process entities | SQL → Fabric → semantic model process chain | Makes Purview's "View lineage" button show something real — native scans establish asset identity but not this cross-system connectivity |

## High-level takeaways (what to say)

- "GT-SLA is the term that ties Tom's credit calculation, Victoria's MTTR dashboard, and Ci
  Zhu's audit answer to one published definition — and native scans tell Purview an asset
  exists, while this notebook tells Purview how assets connect across systems."
- "The term self-heal mechanism proves the catalog stays internally consistent across repeated
  runs — this isn't a one-time snapshot, it corrects drift every time it runs."
- "35/35 terms, 12/12 CDEs, 12/12 CDE-term associations — every one of these is independently
  verifiable by direct Atlas read-back, not just a 'job completed' assumption."

## Demo requirements this notebook satisfies

- Act 3's signature moment: the Purview lineage graph from Power BI visual back to source SQL.
- Every `GT-*`/`CDE-*` code spoken anywhere in the script resolves to a real, governed Purview
  object with a real owner and definition.
- Completes the Purview publication surface `05` started — domains/products plus glossary/CDEs
  together form the full governed catalog Ci Zhu walks the auditor through.

---

See also: [`docs/06_Notebook_Description.md`](../06_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

