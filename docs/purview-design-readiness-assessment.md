# Purview Design — Readiness Assessment

**Date:** 2026-06-04
**Owner:** Sean Kelley
**Status:** Phase A — Ready to commit

## Purpose

This document is the design-phase quality gate. It captures (a) the end-state goal the demo serves, (b) a worked scenario that pressure-tests the design, (c) where the design holds up and where it doesn't, and (d) the phased commit plan that scopes the rest of the build.

It travels with the commit so future contributors (and future you) can see what was deliberately deferred vs. what was overlooked.

The pressure test that drives this assessment — *Maria Castellanos's furnace call* — is the demo's north star and is captured in full in `docs/purview-maria-north-star-scenario.md`. This assessment refers to the abbreviated form; the canonical scenario lives there.

---

## 1. End-state goal

The demo serves three outcomes, in priority order:

1. **Schemas + ontologies that let users query in business terms**, not data-driven definitions. When an analyst asks "what's our churn this quarter for furnace rental customers?", the system resolves *churn*, *furnace rental*, and *customer* to one canonical definition each.
2. **KPI consistency across business units.** When Finance says MRR, Operations says MRR, and the Call Center says MRR, they all mean the same number — by structure, not by goodwill.
3. **Governed AI grounding.** The same business definitions a human reads are the ones a Data Agent uses. Copilot doesn't invent its own glossary.

These three together are the difference between a Fabric demo that looks pretty and a Fabric demo that proves the platform's enterprise value.

---

## 2. The Maria scenario — pressure test

A customer call exercises every load-bearing part of the design at once.

**Customer (Maria):** "My furnace died Saturday. I opened a ticket. Nobody came. I'm still being charged $89.95 for the rental this month. I want a credit and I want this fixed."

**Agent (Tom)** needs, within 90 seconds:
1. Who Maria is + whether she can authenticate over phone (PIPEDA)
2. The furnace's identity, warranty state, install date
3. The service request status, technician notes, current ETA
4. The contract terms — rental, SLA on response, credit eligibility rules
5. The billing — what was charged Sat → today, what's pending
6. Whether she's a repeat-complaint customer (pattern signal)

**Exec (Victoria — CCO)** wants the aggregate two weeks later:
- How many Marias this quarter (FCR ↓, MTTR ↑, complaint volume)
- Concentrated by service zone? (Equipment failure pattern)
- Credit-leakage from SLA breaches (revenue impact)
- Churn-risk cohort identified

**Exec (Ci Zhu — data strategy)** needs to certify that Tom's call-center surface and Victoria's exec dashboard use the **same definition** of "SLA breach", "credit eligibility", "active contract", "churn risk". If they don't, two months later Finance reports one MRR number and the call center reports a different one, and the whole house of cards wobbles.

---

## 3. Where the design serves this well

| Outcome | How the current design supports it |
|---|---|
| Single Maria identity | Customer 360 is a single data product; Tom's CRM surface and Victoria's dashboard read the same `dim_customer` / `dim_service_account` |
| Single MRR / Churn / Net Revenue / FCR definition | These are semantic-model measures, bound via glossary terms (e.g. `GT-MRR` → `BrookfieldEnercare/_Measures/MRR`). A junior analyst rebuilding their own MRR in a personal workspace doesn't change the certified one — drift is structurally hard |
| Consent gating is enforced, not procedural | Consent state is a CDE (`CDE-CONSENTSTATE`). Tom cannot send a marketing follow-up when `consent_status='Withdrawn'` because the data product blocks it |
| Auditable credit decision | Lineage from SQL → mirror → semantic model → report is wired (`tools/purview_custom_lineage.py`). When the credit gets issued, the trail back to source data is visible |
| Balanced executive ownership | Two-headed domain ownership (CCO Victoria + Data Strategy Ci Zhu) means neither can unilaterally redefine "customer" or "revenue" |
| Compliance vocabulary is published | PIPEDA, CASL, OCPA, OEB are glossary terms with regulator references and policy bindings |

---

## 4. Where the design has real gaps

| Gap | Impact for the Maria scenario | Phase to close |
|---|---|---|
| **Glossary is governance-complete, agent-incomplete** — no equipment vocabulary (Furnace, AC, Water Heater, Heat Pump, HRV, Tankless) | Tom says "my furnace" — a Data Agent needs to disambiguate to `equipment_type LIKE 'Furnace%'`. Without the term, the agent fails | **Phase C** |
| **No customer-experience KPIs** — missing NPS, CSAT, Average Handle Time, Quality Score, Repeat-Complaint Rate | Victoria's exec view is missing 3/4 of her primary metrics | **Phase C** |
| **What we have is a glossary, not an ontology** — no typed relationships (Customer HAS Account, Service Account HAS Equipment, Contract OBLIGATES Auto-Renewal Disclosure) | "Show me all customers whose furnace failed within warranty" requires traversing relationships, not just terms | **Phase D (deferred)** |
| **No term-level policies (brief Phase 4.2 unused)** — glossary terms can carry access/health policies that auto-propagate | Attaching a "PIPEDA-protected" policy directly to `GT-CONSENT` makes compliance enforceable, not just documentary | **Phase B-C** (fast follow-up) |
| **No formal certified-KPI endorsement chain** — `status=Published` is naming, not enforcement | Junior team could build a shadow MRR; current design names it but doesn't endorse it as official | **Phase C-D** (depends on G10 steward workflow) |

---

## 5. Honest commit-readiness call

**Yes — commit this as Phase A.**

The structural design is sound:
- Every Purview brief Phase 1–5 requirement maps to a CSV column (per `purview-csv-alignment.md`)
- Role taxonomy is correct
- Dual-permission rule is explicit
- Ownership is balanced
- The SIN backstop strategy guarantees classification fires regardless of built-in classifier behavior

You can hand this to Alison and she can author it into Purview without hitting a missing-field blocker. The Maria scenario *would* work end-to-end for the load-bearing parts (identity, contract, billing, lineage, consent gating).

What it would NOT do well today is the "ask in business terms" experience for a call-center agent — because the glossary doesn't yet have the agent's vocabulary, the equipment ontology is one term deep, and the customer-experience KPIs aren't represented. That's a Phase B/C addition, not a Phase A rewrite.

---

## 6. Phased plan

| Phase | Scope | Outcome |
|---|---|---|
| **A — Design** (this commit) | Brief-aligned schemas, role taxonomy, dataset, SIN backstop strategy, SQL DDL + seed, customer-input CSVs | Reviewable, ingestable; Maria scenario works for identity/contract/billing/lineage/consent |
| **B — Build** | Notebooks that ingest the CSVs → `lh_metadata` → SemPy writeback → Purview push; scan validation; MIP label application | Demo runs end-to-end with the existing glossary; classification dashboard populated; lineage visible |
| **C — Agent enablement** | Equipment ontology (5–6 terms), customer-experience KPIs (NPS / CSAT / AHT / Quality / Repeat Complaint), agent vocabulary (HVAC / HRV / AC / WH / HP / Tankless), term-level policies on consent/PIPEDA/CASL, verified Q&A pack for call-center scenarios | Maria scenario answerable by a Data Agent in business language; exec view complete |
| **D — Ontology** (deferred) | Typed relationships, certified-KPI endorsement workflow | Post-MVP; depends on Purview ontology GA and G10 steward workflow |

**Target for the 2-day window: Phase C complete.** See `purview-2-day-execution-plan.md` for compressed day-by-day deliverables.

---

## 7. What's deferred and why (explicit so it doesn't surprise reviewers)

- **True ontology (typed relationships)** — Purview Unified Catalog doesn't yet support typed relationships natively. The brief covers CDEs (linked columns) but not declarative relationships. Defer to Phase D.
- **Certified-KPI registry with formal endorsement chain** — Depends on steward workflow (G10 in `design-gap-analysis.md`). Defer to Phase D.
- **Bulk CDE import via API** — Preview-flagged in the brief; treat as preview through Phase B. Do up to 12 manually if API is unstable.
- **Cross-tenant scan** — Brief explicitly flagged this degrades classification / labeling / policy. Out of scope; same-tenant only.
- **Full PCI-scope data** — Partial last-4 only by design; never put full PANs in a demo.
- **Asset curation enablement** — One-way per brief Gap Check #1. Schedule as a single coordinated step with named owner approving; do once in Phase B.

## 8. Risks for the 2-day window

| Risk | Impact | Mitigation |
|---|---|---|
| Purview scan latency (≥15 min per brief Gap Check #3) | Eats clock if scans need re-running | Run scans overnight in Day 2/3; cache classification results |
| CDE API stability (preview) | Manual fallback adds time | Pre-script both API and UI paths; pick whichever works in Day 2 |
| M365 E3/E5 licensing for Protection Policies | Phase 5.4 blocked if SKU missing | Confirm SKU on Day 1; if missing, demo labels via annotation only |
| Asset curation enablement is irreversible | One bad click breaks state | Do once with Ci Zhu approving; non-production catalog first if available |
| Custom classifier rejection by scan rule set | Layer 2 SIN backstop doesn't fire | Day 1 smoke test with the SIT against synthetic data |

---

## Conclusion

The structural foundation is committable. Moving forward, the work shifts from *designing the model* to *populating, publishing, and demonstrating it*. The 2-day compressed plan is aggressive but Phase C completion is achievable if scans run cleanly and licensing is verified at startup.

