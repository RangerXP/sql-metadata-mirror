# Notebook 06: `06_publish_glossary_and_lineage` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/06_Notebook_Description.md` (validation history —
the four-bug debugging saga), this document catalogs the **Purview-published artifacts** this
notebook creates, evaluates them against build requirements, and explains how they support the
demo narrative. Source document for demo slide development.

---

## Notebook purpose & role

**What it is:** The glossary, CDE, labels, and lineage publication notebook — the second and
final Purview publication step, building directly on top of the domains/data products
`05_publish_governance_domains` already created. This is what makes every `GT-*`/`CDE-*` code
referenced throughout the demo a real, resolvable Purview object, and what gives Purview's
lineage view something to actually show.

**How it's applied:** Runs sixth. Two merged phases sharing one Purview token cache: glossary/
CDE publish with self-healing term maintenance, then sensitivity labels, CDE classifications,
and custom Atlas lineage edges. Always writes dry-run artifacts; live publish is config-driven.

**Use-case delivery objective:** This is every `GT-*`/`CDE-*` reference throughout Maria's
scenario (GT-SLA, GT-CONSENT, CDE-CONTRACTAMT, CDE-CONSENTSTATE, etc.) becoming a real,
governed Purview object — and it's what powers the single most visually compelling moment in
Act 3: Ci Zhu clicking "View lineage" and showing the auditor the full chain from a Power BI
visual back to source SQL.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| Purview glossary terms × 35 | Live Atlas entity | Every business term cited in the demo (GT-CUST, GT-SLA, GT-CONSENT, GT-CONTRACT, GT-FCR, GT-MTTR, etc.) | The single certified definition source an auditor, agent, or executive can look up directly in Purview |
| Term self-heal mechanism | Runtime behavior, not a static artifact | Detects and corrects a term's `shortDescription` when it drifts from the current `term_code` naming convention | Proves the catalog stays internally consistent across repeated runs/code evolution, not a one-time snapshot |
| `EnercareCriticalDataElement` × 12 (Purview Atlas entities) | Live CDE entity | Critical Data Elements (CDE-CONTRACTAMT, CDE-CONSENTSTATE, CDE-SVCADDR, etc.) | Marks specific data columns as governance-critical, independently visible/auditable in Purview |
| CDE-to-GlossaryTerm associations × 12 | Live Atlas relationship | Links each CDE entity to its parent glossary term | The exact linkage Ci Zhu cites when proving single-source-of-truth: "this data element traces to this one definition" |
| Sensitivity label assignments | Live Purview classification | Confidential / Highly Confidential labels on governed assets | The policy gate behind Tom's credit authority and PII-visibility rules during the call |
| CDE classifications | Live Purview classification | `EnercareCriticalDataElementClassification` tags on classified assets | Machine-readable proof that sensitive fields are actually flagged, not just documented |
| Custom Atlas lineage edges | Live Atlas Process entities | SQL → Fabric → semantic model process chain | What makes Purview's "View lineage" button show something real instead of an empty graph — native scans establish asset identity but not this cross-system connectivity |
| Glossary-to-asset associations | Live Atlas relationship | Links glossary terms to their bound SQL/Fabric/semantic-model assets (with a semantic-model anchor fallback) | Lets a user navigate from a term definition directly to the physical/logical assets it governs |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| "Native scans provide asset identity; custom Atlas processes provide cross-system edges native scans cannot observe" | This notebook's lineage-edge publish is exactly that custom process layer |
| Self-healing governance — catalog stays correct across repeated runs | The term shortDescription self-heal mechanism is a direct, working example of this principle from the design guide |
| Every governed object must be independently verifiable, not just "probably published" | Validated live: 35/35 terms, 12/12 CDEs, 12/12 CDE-term associations confirmed via direct Atlas read-back, not just a "job Completed" assumption |
| Shared auth/token infrastructure across governance notebooks | Confirmed reusing the same OneLake-cached Purview token as notebook 05, avoiding repeated interactive sign-ins |

## Demo narrative support

- **Act 3 (the lineage moment):** this is the single strongest visual artifact in the entire
  governance pipeline. A slide showing the Purview lineage graph — Power BI visual → semantic
  model measure → lakehouse table → mirrored SQL → source SQL — directly demonstrates "no
  manual reconciliation" in a way no other notebook's output can.
- **Act 1/3 (term-to-CDE-to-policy chain):** `GT-SLA` → the SLA credit-policy verified answer →
  `CDE-CONTRACTAMT`'s sensitivity label is a three-artifact chain spanning notebooks 2, 4, and
  6 that a single slide could trace end-to-end to show governance consistency across the whole
  pipeline, not just within one notebook.
- **Talking point:** "GT-SLA is the term that ties Tom's credit calculation, Victoria's MTTR
  dashboard, and Ci Zhu's audit answer to one published definition — and native scans tell
  Purview an asset exists, while this notebook tells Purview how assets connect across systems."

## High-level outcome

By the end of this notebook, Purview's Unified Catalog holds a complete, self-consistent
glossary and CDE catalog, correctly classified and labeled, with real cross-system lineage
connecting every governed asset back to its source. This is the artifact set that makes Ci
Zhu's Act 3 "click View lineage" audit moment possible, and it completes the T4-tier publication
started by notebook 05.

---

See also: [`docs/06_Notebook_Description.md`](../06_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
