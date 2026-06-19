# Demo Walkthrough Script

## Audience Profile

**Microsoft SEs in Financial Services** — Your peers understand the technology stack. They want to see how it fits together to solve real customer problems. Keep it snappy, skip the basics, show the integration points.

---

## Pre-Demo Setup (5 min before)

1. **Fabric portal open** — Workspace `Enercare-Demo` visible
2. **Purview portal open** — Unified Catalog ready
3. **Power BI report open** — "BrookfieldEnercare" dashboard loaded
4. **Data Agent open** — Ready for conversational queries
5. **Have bearer token fresh** if you plan to show live notebook execution

---

## Opening Hook (1 minute)

> "Let me tell you about Maria."
>
> "Maria Castellanos is an Enercare customer in Markham. Her furnace broke Saturday. It's now Wednesday. No technician has shown up, but her $89.95 rental charge has posted."
>
> "She picks up the phone."
>
> "What happens next — and whether Enercare keeps her as a customer — depends entirely on whether their data platform can answer three questions from three different people with the same answer."

---

## Act 1: Tom the Agent (3-4 minutes)

### The Scene

Tom takes Maria's call. He needs to answer three questions in under a minute:
1. Who is Maria, and what equipment does she have?
2. Is she in her loyalty protection window?
3. What credit authority does he have?

### Demo Flow

**Show: Data Agent (Conversational)**

> "When Tom looks up Maria, he doesn't query a database. He asks a Data Agent."

**Type in Data Agent:**
```
What is the service status for Maria Castellanos?
```

**Point out:**
- The agent returns structured data from the semantic model
- Contract status, equipment, open service requests
- FCR eligibility flag

**Type in Data Agent:**
```
What credit can I offer a customer in loyalty protection?
```

**Point out:**
- Verified Q&A response (not hallucinated)
- This answer came from `nb_05_push_qa_verified_answers`
- Guardrailed by governance

### SE Talking Point

> "This is a Data Agent backed by a DirectLake semantic model. No API coding — just SemPy writeback to enrich the model with business definitions. The agent understands 'loyalty protection' because that term is in the glossary."

---

## Act 2: Victoria the CCO (3-4 minutes)

### The Scene

Next day. Victoria reviews the customer experience dashboard before her board meeting. She needs:
1. Overall service performance across all zones
2. Drill-down into problem areas
3. Exact metric definitions for the board deck

### Demo Flow

**Show: Power BI Dashboard**

> "Victoria doesn't call IT. She opens the same dashboard she uses every week."

**Navigate to:**
- Service Performance page
- Show AHT, FCR, NPS metrics
- Drill down into Toronto Central (where Maria is)

**Hover over any measure:**

> "Watch this. When I hover over any KPI..."

**Point out:**
- Measure description appears
- Business definition, not technical formula
- This came from `nb_04_sempy_writeback`

**Click on a metric → View Lineage (if Purview integration is live) or describe:**

> "If Victoria clicks 'Where did this come from?', she sees the lineage from her dashboard all the way back to the source SQL table. Eight edges we published this morning."

### SE Talking Point

> "Same semantic model Tom used. Same KPI definitions. When Victoria says 'FCR is 87%' in the board meeting, it's the same 87% Tom saw when he looked up Maria. That's the point."

---

## Act 3: Ci Zhu the Auditor (3-4 minutes)

### The Scene

Quarterly governance review. Ci Zhu needs to prove to the external auditor:
1. Metrics are certified with clear definitions
2. Data lineage is documented
3. Sensitive data is classified and protected
4. Access controls are in place

### Demo Flow

**Show: Purview Unified Catalog**

> "Ci Zhu doesn't chase data engineers. She opens Purview."

**Navigate to:**
- **Governance Domains** → Show 3 domains (Customer Operations, Service Delivery, Revenue & Contracts)
- **Data Products** → Show Customer 360, Service Performance, Billing & Contract Health
- **Glossary** → Show 35+ terms with owners and definitions

**Click on any glossary term (e.g., Net Revenue):**

**Point out:**
- Term definition
- Owner (accountable person)
- Related assets bound to this term
- CDE status if applicable

**Navigate to:**
- **Lineage** → Pick any semantic model table

**Point out:**
- Visual lineage from SQL source → Fabric lakehouse → Semantic model
- Click-through to source metadata
- "This is what we published in `nb_09_purview_labels_lineage`"

**Navigate to:**
- **Data Estate Health** or **Sensitivity Labels** (show classification coverage)

### SE Talking Point

> "This is the same data Tom queried, the same KPIs Victoria presented. But now Ci Zhu can show the auditor: here's the definition, here's the owner, here's the lineage. No spreadsheet reconciliation."

---

## Closing: The Point (1 minute)

> "Maria's furnace still needs fixing. But when her case gets escalated..."
>
> "...the call center manager sees the same data as the regional VP..."
>
> "...who sees the same data as the CCO..."
>
> "...who presents the same numbers to the board..."
>
> "...that the auditor validates against source..."
>
> "...and the regulator accepts."
>
> "**Same data. Same definition. Same truth.**"
>
> "That's the demo."

---

## Common Questions

### "How long does the full pipeline take?"

> "Full rebuild from scratch: ~20 minutes of notebook execution. But in production, only the incremental steps run daily. The governance publication (Purview steps) only runs when definitions change — which is monthly at most."

### "Can this work without SemPy Labs?"

> "SemPy Labs is the preferred path because it writes directly to the TOM (Tabular Object Model). You could use TMDL REST APIs instead, but SemPy Labs is cleaner and GA-supported."

### "What about real-time?"

> "Fabric Mirroring is near-real-time CDC. For a utility customer, the latency is ~5 minutes from SQL commit to lakehouse availability. That's fast enough for operational dashboards, not fast enough for payment fraud. Know your use case."

### "How do I set up the Purview integration?"

> "Three pieces: (1) Register your sources (Azure SQL, Fabric workspace) in Purview. (2) Run scans to populate the catalog. (3) Use our notebooks to publish the governance overlay — domains, products, glossary, lineage. The notebooks are the custom part; everything else is standard Purview."

---

## Timing Guide

| Section | Duration | Running Total |
|---------|----------|---------------|
| Opening Hook | 1 min | 1 min |
| Act 1: Tom | 4 min | 5 min |
| Act 2: Victoria | 4 min | 9 min |
| Act 3: Ci Zhu | 4 min | 13 min |
| Closing | 1 min | 14 min |
| Q&A | 5 min | ~20 min |

---

## Demo Hot Tips

1. **Don't show notebooks** unless asked. SEs know what a notebook looks like. Show the outputs.

2. **Don't explain mirroring**. SEs know what mirroring is. Just say "this data came from SQL via mirroring."

3. **Do show the hover-over descriptions** in Power BI. That's the "aha" — governance metadata surfacing at the point of consumption.

4. **Do have Purview lineage ready**. The visual lineage graph is the most impressive proof point for auditor scenarios.

5. **Do personalize the Maria story**. Change the name, the utility, the location to match the customer you'll eventually pitch.

---

## Backup Slides (if questioned)

- **Architecture diagram**: See `01-demo-overview.md`
- **Notebook reference**: See `02-notebook-guide.md`
- **Capability breakdown**: See `04-capability-showcase.md`
- **Gap analysis**: See `docs/design-gap-analysis.md`
