# Notebook 01: `01_setup_source_data` — Demo Prep Digest

**Purpose of this document:** A notebook-driven digest for demo delivery — what this notebook
does, where it sits in the governance contract, and the high-level points to explain while
presenting it. Not the validation history (`docs/01_Notebook_Description.md`) and not the
end-to-end demo script (a separate demo-design-walkthrough document covers that). This is the
per-notebook reference you'd have open while explaining *this specific step*.

---

## Role in the demo

The foundational data-generation notebook — the single source of all synthetic Enercare
operational data used anywhere downstream: the lakehouse landing zone, the Azure SQL "system of
record," and the call-center interaction dataset that drives the entire Maria Castellanos
storyline. Runs first, always live (no dry-run gate — its entire job is to write data).

**Why it matters for the demo:** everything Tom sees on Maria's call (Act 1), everything
Victoria drills into in her quarterly review (Act 2), and the data Ci Zhu's audit answer traces
back to (Act 3) originates here — including a deliberately-designed correlation (billing-queue
contact → lower Protection-Plan renewal rate) that Victoria's dashboard later surfaces as a real
business insight.

## Where this fits: the 3-tier contract & ontology

This notebook **creates Tier 1** — it's the one place in the whole pipeline that writes the
authoritative operational data both the lakehouse and Azure SQL (`sqldemo`) ultimately agree on.
(See `docs/governance-ontology-and-data-contract-model.md` §2 for the full 3-tier model: Tier 1
Contract → Tier 2 Transport/Fabric Mirroring → Tier 3 Consumption.)

| Aspect | This notebook's role |
|---|---|
| Tier | **Tier 1 (the contract)** — writes `lh_enercare_demo` directly, then publishes the same data into `sqldemo` as the authoritative SQL source Fabric Mirroring replicates from |
| Ontology footprint | None of the governed *metadata* ontology (Domain/Data Product/Glossary Term/CDE/Objective) — this notebook is pure **operational data**, the substrate the ontology later governs |
| Governance workflow | None — no approval gate. This is raw source-data generation, not a governed change |

## Key artifacts

| Artifact | What it is | Why it matters in the demo |
|---|---|---|
| `lh_enercare_demo` core tables (customers, service accounts, equipment, contracts, service requests, billing) | The full synthetic operational dataset, incl. Maria Castellanos as a designed 51st customer | Every fact Tom reads aloud on the call — account, address, equipment, ticket, billing — comes from here |
| Call-center tables (`cc_agents`, `fct_cc_interactions`, `fct_cc_transcript_turns`, `ref_cc_billing_adj_category`) | 300 interactions with full transcripts, attributed to a named agent roster incl. Tom Nguyen | Backs FCR/CSAT/AHT/Escalation-Rate KPIs and the Data Agent's transcript-level answers |
| `sqldemo` mirror (same tables + `customer_consents`/`customer_complaints`) | The authoritative SQL "system of record" | Proves the sub2 (SQL) → sub1 (Fabric) mirroring pattern real enterprise deployments use |
| Synthetic Luhn-valid SINs | Realistic-but-fake Canadian SINs | Exercises the Purview SIN classifier without any real PII |
| Billing-caller / PP-renewal correlation | Billing-queue callers renew at ~51% vs. ~86% for everyone else | The single most reusable "aha" data point in the whole demo — Victoria's Act 2 insight |

## High-level takeaways (what to say)

- "This is a full operational system, not a static demo dataset — customers, contracts,
  billing, service requests, and 300 real call-center interactions with transcripts, all
  internally consistent enough to survive an executive drilling into it."
- "One correlation is baked in on purpose, and it's enforced structurally, not just narratively
  — the notebook itself asserts the churn gap holds on every run, so it can never silently
  regress."
- "SQL is the contract in this demo, and this notebook is where that contract's operational data
  starts — everything else downstream is a verified copy or a governed layer on top of it."

## Demo requirements this notebook satisfies

- Act 1 data: Maria's account, service address, equipment (Lennox SLP98V furnace), and open
  ticket (`SR-2026-051142`) all trace to a real row here.
- Act 2 data: the billing-caller/PP-renewal correlation Victoria's dashboard surfaces as a real
  churn driver.
- Foundational requirement: a realistic-enough synthetic dataset that every later governance
  and semantic-model step has real data to operate on.

---

See also: [`docs/01_Notebook_Description.md`](../01_Notebook_Description.md) (artifact catalog + validation pointer) ·
[`docs/governance-ontology-and-data-contract-model.md`](../governance-ontology-and-data-contract-model.md) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)

