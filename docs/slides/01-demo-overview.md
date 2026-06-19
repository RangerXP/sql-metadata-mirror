# Enercare Governance Demo — Executive Overview

## The One-Liner

**"Same data, same definition, same truth — from call center to boardroom to audit."**

---

## What This Demo Proves

A residential utility customer calls with a service complaint. The **call center agent**, the **chief customer officer**, and the **compliance auditor** all consume the same metrics from the same governed data products — with zero manual reconciliation.

This is **Microsoft Fabric + Purview + Azure SQL** working as a unified governed data platform.

---

## The Customer Story: Maria's Furnace

**Maria Castellanos** is an Enercare customer in Markham, Ontario. Her furnace broke on Saturday. By Wednesday, no technician has arrived — but her $89.95 monthly rental charge has posted.

She picks up the phone.

### Three Acts, One Truth

| Act | Persona | Question They Ask | Data They Need |
|-----|---------|-------------------|----------------|
| **Act 1: The Call** | Tom (Agent) | "What's Maria's contract? What credit can I give?" | Customer identity, equipment status, billing terms |
| **Act 2: The Review** | Victoria (CCO) | "How many Marias are there? What's the revenue impact?" | Aggregate KPIs, service zone drill-down |
| **Act 3: The Audit** | Ci Zhu (Data Gov) | "Prove the number on the board slide matches what Tom used" | Lineage, certified definitions, access logs |

### The Demo Passes When:
- Tom's credit authority threshold
- Victoria's churn dashboard
- Finance's quarterly filing

...all resolve to the **same semantic model measures**, governed by the **same glossary terms**, traced by the **same lineage**.

---

## Architecture at a Glance

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           SUB 3: PURVIEW                                 │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│   │  Governance     │  │   Glossary &    │  │   Sensitivity   │          │
│   │  Domains (3)    │  │   CDEs (35+12)  │  │   Labels (4)    │          │
│   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘          │
│            │                    │                    │                   │
│            └────────────────────┼────────────────────┘                   │
│                                 │                                        │
│                         ┌───────▼───────┐                                │
│                         │   Lineage &   │                                │
│                         │   Catalog     │                                │
│                         └───────┬───────┘                                │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │ scans
┌─────────────────────────────────┼────────────────────────────────────────┐
│                           SUB 1: FABRIC                                  │
│                                 │                                        │
│   ┌─────────────────────────────▼─────────────────────────────────┐      │
│   │              BrookfieldEnercare Semantic Model                │      │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │      │
│   │   │ Dimensions   │  │    Facts     │  │   Measures   │        │      │
│   │   │ (customer,   │  │ (billing,    │  │ (FCR, AHT,   │        │      │
│   │   │  product,    │  │  service,    │  │  NetRev,     │        │      │
│   │   │  equipment)  │  │  contracts)  │  │  Churn...)   │        │      │
│   │   └──────────────┘  └──────────────┘  └──────────────┘        │      │
│   └───────────────────────────────────────────────────────────────┘      │
│                                 ▲                                        │
│   ┌─────────────────────────────┴─────────────────────────────────┐      │
│   │                  lh_enercare_demo Lakehouse                   │      │
│   │        Star schema rebuilt from mirrored SQL source           │      │
│   └─────────────────────────────┬─────────────────────────────────┘      │
│                                 │                                        │
│                         ┌───────▼───────┐                                │
│                         │   Mirroring   │                                │
│                         │   (sqldemo)   │                                │
│                         └───────┬───────┘                                │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │ mirrors
┌─────────────────────────────────┼────────────────────────────────────────┐
│                           SUB 2: AZURE SQL                               │
│                                 │                                        │
│   ┌─────────────────────────────▼─────────────────────────────────┐      │
│   │                    sqldemo Database                           │      │
│   │   customers, contracts, service_requests, billing_transactions│      │
│   │   equipment_registry, customer_consents, customer_complaints  │      │
│   └───────────────────────────────────────────────────────────────┘      │
│                    Authoritative Operational Source                      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Capability Summary

| Layer | Technology | Role in Demo |
|-------|------------|--------------|
| **Source** | Azure SQL Database | Authoritative operational data (7+ tables) |
| **Ingestion** | Fabric Mirroring | Real-time CDC replication to OneLake |
| **Transform** | Spark Notebooks | Star schema build, metadata enrichment |
| **Serve** | DirectLake Semantic Model | Single source of KPIs for all consumers |
| **Govern** | Microsoft Purview | Domains, data products, glossary, CDEs, labels, lineage |
| **Consume** | Power BI + Data Agent + Copilot | Executive dashboards, conversational analytics |

---

## The Value Proposition

### For Financial Services Customers:

1. **Regulatory Compliance** — PIPEDA, CASL, OCPA, OEB compliance is structural, not procedural
2. **Single Source of Truth** — One metric definition from agent to CFO
3. **Audit-Ready Lineage** — Click any number, trace to source
4. **Privacy-by-Design** — Sensitivity labels gate access, not training
5. **AI Governance** — Copilot and Data Agents consume governed metadata

### For Microsoft SEs:

- **Cross-product integration**: SQL → Fabric → Purview working end-to-end
- **Real metadata engineering**: SemPy Labs semantic model writeback
- **Production-grade governance**: Not just scanning, but domains/products/CDEs
- **Demo-ready**: North star scenario with complete acceptance criteria

---

## Key Metrics (Demo Closure 2026-06-18)

| Metric | Value |
|--------|-------|
| Governance Domains | 3 (Customer Operations, Service Delivery, Revenue & Contracts) |
| Data Products | 3 (Customer 360, Service Performance, Billing & Contract Health) |
| Glossary Terms | 35+ |
| Critical Data Elements | 12 |
| Sensitivity Labels | 4 (Public → Highly Confidential) |
| Lineage Edges Published | 8 (SQL → Fabric Semantic Model) |
| Semantic Model Measures | 15+ KPIs |
| Notebooks in Pipeline | 13 |

---

## Demo Success Criteria

The demo passes when all three personas — **Agent**, **Executive**, **Auditor** — see the same numbers from the same definitions with no manual reconciliation.

**That's the test. Pass it, ship it.**
