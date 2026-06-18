# Maria's Furnace — The Demo North Star Scenario

**Purpose:** This is the orienting scenario for the Enercare Purview + Fabric demo. Every design choice (data products, glossary terms, CDEs, sensitivity labels, term policies, SemPy writeback annotations, verified Q&A entries) earns its place in the build by serving this scenario. If a piece of the design doesn't show up here, it doesn't ship.

**Status:** Demo north star — committed Phase A.
**Linked from:** `docs/purview-demo-data-design.md`, `docs/purview-design-readiness-assessment.md`, `docs/purview-2-day-execution-plan.md` (2-day cadence), `docs/Enercare-Demo-SemPy-Design-Guide.md`.

---

## Scenario overview

Maria Castellanos is a residential Enercare customer in Markham, Ontario. Her furnace died on a Saturday morning. She opened a service ticket through the Enercare portal. By Wednesday — five days later — no technician has been dispatched, and her monthly $89.95 furnace rental charge has posted to her account on schedule. She picks up the phone.

The scenario plays out in three acts: **the call** (Tom the agent serving Maria in real time), **the aftermath** (Victoria the CCO seeing this case in her quarterly customer-experience review), and **the governance walkthrough** (Ci Zhu showing the auditor how every business term, KPI, and access decision traces back to a single certified definition).

The demo succeeds when all three acts run on the **same governed surface**, with the **same definitions**, served by the **same data products**, with **no manual reconciliation**.

---

## Cast of characters

| Persona | Name | Role | What they need from the demo |
|---|---|---|---|
| Customer | **Maria Castellanos** | Residential customer, Markham (FSA L4G) | Furnace fixed, billing corrected, dignity preserved |
| Agent | **Tom Nguyen** | Service Technician promoted to Call Center Specialist (employee_id 101 in the demo data) | Identity verification, equipment status, contract terms, credit authority — all in 90 seconds, with built-in privacy gates |
| Exec | **Victoria Tan** | Chief Customer Officer (Domain Owner DOM-CUSTOPS) | Aggregate view: how many Marias, where, why, and what's the customer-experience and revenue impact |
| Exec / Auditor | **Ci Zhu** | Senior Manager, Data Strategy & Analytics (Glossary Owner; Information Protection Admin; Data Governance Administrator post-handoff) | Provable single-source-of-truth: every KPI Tom and Victoria see traces to one certified definition |
| Steward | **Rupal Solanki** | Data Steward DOM-CUSTOPS | Customer data quality; consent state integrity |
| Steward | **Shruthi Srinivas** | Data Steward DOM-SVCDEL | Service request and equipment data quality |
| Exec | **Ranbir Singh** | Enercare Leadership — Data Plane (Domain Owner DOM-SVCDEL) | Field operations health — is the dispatch system surfacing the right work to the right tech? |

---

## Act 1 — The call (Tom serves Maria)

**Setting:** Wednesday, 2:14 PM. Tom Nguyen, headset on, queue ID #4471. He answers.

### 1.1 — Identity & authentication

**Maria:** "Hi, my name is Maria Castellanos. My account number is EC18374622. My furnace has been broken since Saturday and nobody's come and you're still charging me."

**Tom:** "Hi Maria, sorry to hear that. Let me pull your account. Can I confirm the service address with you?"

> **Data-plane behind the scenes:**
> - **Glossary terms in play:** GT-CUST (Customer), GT-ACCOUNT (Account), GT-PREMISE (Premise), GT-FSA (Forward Sortation Area)
> - **CDEs in play:** CDE-ACCTNUM (Account Number), CDE-SVCADDR (Service Address)
> - **Data product:** DP-CUST360 (Customer 360) — Tom's CRM surface queries this product, not raw SQL
> - **Source assets:** `dbo.customers` (Maria's master record) joined to `dbo.service_accounts` (her premise) — both classified by Purview as **Confidential**
> - **Sensitivity label applied:** Confidential — Tom's CRM session is gated by the label policy
> - **Term policy that fires:** GT-PIPEDA-bound access policy requires Tom to verify Maria via service address before disclosing further account state

**Maria:** "It's 47 Birch Drive, Unit 8, Markham, L4G 2H9."

**Tom:** "Thank you. I have you. Maria, before we go further — I see you have an email and phone marketing consent on file. I won't send anything new today; I just need to confirm I can text you the dispatch update if I get one. Yes?"

> - **CDE in play:** CDE-CONSENTSTATE
> - **Glossary term in play:** GT-CONSENT, GT-CASL
> - **Data product:** DP-CUST360 surfaces `dbo.customer_consents` filtered to Maria
> - **Term-level policy:** A "PIPEDA-protected" access policy attached to GT-CONSENT (Phase 4.2) ensures Tom sees consent_status before he can take a downstream action that depends on it. **Note:** this is a Phase B/C deliverable.

**Maria:** "Yes, you can text me. Just fix this."

### 1.2 — The furnace and its history

**Tom:** "Looking at your equipment registry now. You have a Lennox SLP98V variable-speed gas furnace, installed October 2020, fully under warranty. I see the service request you opened Saturday morning — SR-2026-051142, status 'Scheduled — Pending Tech.' Let me see what happened."

> - **Glossary terms in play:** GT-EQUIP-FURNACE (equipment ontology — Phase C deliverable), GT-EQUIP (Equipment Registry), GT-SVCREQ (Service Request), GT-WORKORDER, GT-TECH (Technician)
> - **Data product:** DP-SVCPERF (Service Performance) — Tom's view of service operations queries this product
> - **Source assets:** `dbo.equipment_registry`, `dbo.service_requests` joined to `dbo.employees` (technician_id resolution)
> - **Lineage:** Tom's CRM surface → DP-SVCPERF → `lh_enercare_demo.fct_service_request` → mirrored `dbo.service_requests` → source SQL. This is the chain Purview's lineage view shows.

**Tom:** "Maria, I see what happened. The work order was assigned to Mei Huang for dispatch from GTA North, and she has a SLA-exceeded flag from a separate incident on Monday that pulled her off the queue. The system never re-dispatched. I'm escalating this to my supervisor."

### 1.3 — Contract terms and credit eligibility

**Maria:** "OK but what about the charge? You can't be charging me $89.95 for a rental that isn't working."

**Tom:** "You're right. Let me check your contract terms. You're on the Total Home Protection Plan, monthly rental, with our SLA of 24 hours for a no-heat call during heating season. That SLA was breached at the 24-hour mark on Sunday. Under our credit policy, you're entitled to a daily pro-rated credit for every day past the SLA breach. From Sunday through today, that's five days — $14.99 prorated credit. I'll apply that now, and I'll add an additional courtesy credit of one full month's rental on resolution. Is that acceptable?"

> - **Glossary terms in play:** GT-CONTRACT, GT-AUTORENEW, GT-SLA, GT-BILLCYCLE
> - **CDE in play:** CDE-CONTRACTAMT (Contract Monthly Amount)
> - **Data product:** DP-BILLHEALTH (Billing and Contract Health)
> - **Source assets:** `dbo.contracts`, `dbo.billing_transactions` — labeled **Highly Confidential** because contracts contain CDE-CONTRACTAMT
> - **Sensitivity label gate:** Tom's credit authority is gated by the label policy. The mandatory rule on DP-BILLHEALTH means Tom's session is allowed to issue credits up to $200 (his role's limit) without supervisor approval; anything above triggers Phase 3.4 approval workflow.
> - **Regulatory term:** GT-OCPA (Ontario Consumer Protection Act) sits on the contract record because auto-renewal disclosure is OCPA-regulated

**Maria:** "Yes. And the furnace?"

**Tom:** "I have the supervisor on hold. We're rerouting Karim Ahmed to your address as the next service window opens. ETA is tomorrow morning between 8 and 10."

### 1.4 — Complaint logging

**Tom:** "Maria, because this exceeded our SLA by more than 48 hours, I'm logging this as a formal complaint — complaint_type 'Service', severity 'High'. That doesn't change anything for you; it goes into our quality review so this kind of mis-dispatch doesn't happen again."

> - **Glossary term in play:** GT-COMPLAINT, GT-OEB (Ontario Energy Board)
> - **CDE in play:** CDE-COMPLAINTREF — if the complaint crosses to RegulatorReportable (it doesn't here, but Tom's CRM evaluates), a regulator_case_ref would auto-generate
> - **Source asset:** `dbo.customer_complaints` (new in this demo — see `sql/04_purview_demo_extensions.sql`)
> - **Audit:** `dbo.audit_data_access` logs Tom's session — UPN, purpose-of-use 'CustomerService', rows touched, contains_pii flag

**Maria:** "Thank you. Tom, I appreciate it."

**Tom:** "You'll get an SMS confirmation in 10 minutes. Have a good afternoon."

**Call ends. Total: 7 minutes 22 seconds.**

> - **KPIs generated by this call (all single-sourced from `BrookfieldEnercare` semantic model):**
>   - FCR (First Call Resolution) — yes (count as 1 for the FCR numerator)
>   - AHT (Average Handle Time) — 7:22 contributes to Tom's daily AHT
>   - CSAT (Customer Satisfaction) — pending Maria's post-call survey
>   - Quality Score — Tom's QA team will sample this call; PIPEDA gate satisfaction, SLA acknowledgment, credit-policy adherence all scored

---

## Act 2 — The aftermath (Victoria's quarterly review)

**Setting:** Two weeks later, Tuesday 10:00 AM. Victoria Tan opens her CCO quarterly review dashboard in Power BI.

The dashboard reads from the **same `BrookfieldEnercare` semantic model** Tom's CRM resolved against. Victoria sees:

| KPI | Q-to-date | YoY | Source |
|---|---|---|---|
| First Call Resolution | 72.4% | -2.1 pp | GT-FCR → `BrookfieldEnercare/_Measures/FCR` |
| Mean Time to Repair | 31.2 hrs | +4.8 hrs | GT-MTTR → `BrookfieldEnercare/_Measures/MTTR` |
| Average Handle Time | 8:47 | +0:33 | GT-AHT → `BrookfieldEnercare/_Measures/AHT` |
| Net Promoter Score | 41 | -5 | GT-NPS → `BrookfieldEnercare/_Measures/NPS` |
| Repeat Complaint Rate | 11.8% | +2.2 pp | GT-REPEATCOMPLAINT → `BrookfieldEnercare/_Measures/RepeatComplaintRate` |
| Net Revenue | $14.2M | +3.1% | GT-NETREV → `BrookfieldEnercare/_Measures/NetRevenue` |
| Customer Churn | 8.4% | +0.6 pp | GT-CHURN → `BrookfieldEnercare/_Measures/Churn Rate` |

Victoria drills into the spike in Repeat Complaint Rate. The dashboard pivots to a service-zone heatmap. GTA North is anomalous — 18.2% repeat complaint rate vs. system-wide 11.8%.

She drills again. The underlying cohort surfaces — Maria is in it.

> - **Glossary terms in play:** all of the above + GT-SVCZONE (Service Zone), GT-CUST (Customer)
> - **Data products:** DP-CUST360 (the cohort) + DP-SVCPERF (the zone metrics) + DP-BILLHEALTH (the revenue impact) — Victoria's drill traverses three data products that all share a common `customer_id` and `service_zone_code` join key
> - **Lineage proof:** Victoria can click any metric → "View lineage" → Purview lineage view shows the chain from her Power BI visual → SM measure → lakehouse table → mirrored SQL → source SQL. **This is the same lineage chain Tom's CRM showed.**

Victoria messages Ranbir on Teams:

> *"GTA North repeat-complaint spike. Pull the dispatch logs. Same root cause as the Castellanos case? If yes, fix the queue routing this week."*

Ranbir replies in 4 minutes:

> *"Confirmed. Mei Huang's SLA-exceeded auto-suppression isn't releasing. Patched the dispatch logic. ETA fixed Friday. Pattern goes back 11 days, affected 47 service requests."*

---

## Act 3 — The governance walkthrough (Ci Zhu's audit answer)

**Setting:** Two weeks after Victoria's review. An external compliance auditor (PIPEDA / OCPA scope) asks Ci Zhu the central question:

> *"Show me that the number Victoria reported to her board is the same number Tom used when he gave Maria the credit, and the same number you'd use if you reran it tomorrow. Show me the provenance."*

Ci Zhu opens Purview Unified Catalog.

### 3.1 — The domain

> "Customer Operations is a published Governance Domain owned by Victoria Tan and me. Two owners, per Purview's Phase 2.2 requirement. Roles tab shows Rupal as Data Steward. Data estate mapping points to the Enercare collection in Data Map."

### 3.2 — The data product

> "Customer 360 is a published Data Product, type Master and reference data. Owner Victoria. Steward Rupal. Audience: Marketing Analytics, Customer Experience Operations, Privacy Office, Field Operations Supervisors. Permitted purposes: Customer-experience analytics, Marketing eligibility lookup, Privacy compliance reporting. Approval workflow on access — Manager + Privacy review for SIN partial visibility. Three attached assets each from SQL source, Fabric lakehouse, and the BrookfieldEnercare semantic model. Sensitivity label: Confidential."

### 3.3 — The glossary terms

> "Look at GT-NETREV — Net Revenue. Owners Ci Zhu (me) and Ranbir Singh. Definition: 'Billed revenue minus refunds credits and tax amounts.' Resources link to the internal KPI page. Related tab: bound to `BrookfieldEnercare/_Measures/Net Revenue`. Published 2026-05-15. Status: Published.
>
> That binding is what guarantees the number on Victoria's board slide is the same number Finance used to file the quarter and the same number Tom's credit authority was evaluated against. There's only one definition because there's only one `_Measures/Net Revenue` in the semantic model, and it's owned by me."

### 3.4 — The CDEs

> "CDE-CONTRACTAMT — Contract Monthly Amount. Expected data type: number. Linked column: `dbo.contracts.monthly_amount`. Sensitivity Highly Confidential. Owner: me. Steward: me. Auto-associated to Data Product DP-BILLHEALTH because that product has `dbo.contracts` attached.
>
> When Tom looked at Maria's $89.95 charge, his CRM surface resolved it through this CDE. When Victoria saw $14.2M Net Revenue, the SUM is over this CDE. When the auditor asks why those two numbers reconcile, the answer is: same CDE, same definition, same column."

### 3.5 — The labels and protection policy

> "Highly Confidential is enforced by a Fabric Protection Policy. Tom's session, Victoria's session, and Power BI report exports all evaluate against this policy. The 100-user cap is well under our pilot scope. Auto-apply rule: any column classified MICROSOFT.CANADIAN.SIN OR ENERCARE.PRIVACY.SIN_BACKSTOP OR CreditCardNumber OR BankRoutingNumber. Both classifiers fire; both are documented in the SIN classifier backstop strategy doc."

### 3.6 — The lineage

> "Click 'View lineage' on the Net Revenue measure. The chain: Power BI visual → SM measure → `lh_enercare_demo.fct_billing` → mirrored OneLake table from sqldemo → source `sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/billing_transactions`. Eight edges. Every edge is registered via either native Purview scan output or `tools/purview_custom_lineage.py`. This is the provable chain."

### 3.7 — The audit answer

> "The number is the same because it can't be different. The semantic-model measure is the only place the definition lives. Purview certifies it via a published glossary term and a CDE. Lineage proves the chain from source to consumption. Term-level policies gate access. Labels enforce sensitivity. Audit logs at `dbo.audit_data_access` show every read with purpose-of-use. If Victoria's dashboard ever diverges from Finance's filing, it would mean someone edited the semantic-model TMDL — which sits in Git-backed source control and requires my review."

The auditor closes the laptop. "OK."

---

## What this scenario proves (acceptance criteria)

When Maria's scenario plays end-to-end in the demo without intervention, the demo has proven:

1. **Single customer identity** — Tom and Victoria see the same Maria. ✓ Data product DP-CUST360 single-sources customer master.
2. **Single KPI definition** — Tom's credit authority threshold, Victoria's churn dashboard, and Finance's MRR filing all resolve to the same semantic-model measures. ✓ Glossary terms bind to `BrookfieldEnercare/_Measures/X`; KPI drift is structurally impossible.
3. **Privacy is enforced, not procedural** — Tom can't send a CASL-restricted follow-up to Maria without `consent_status='Granted'`; the data product blocks it. ✓ CDE-CONSENTSTATE + term-level policy on GT-CONSENT.
4. **Regulatory compliance is provable** — OCPA, OEB, PIPEDA, CASL each have a glossary term with an external regulator reference and binding to the relevant CDE/column. ✓ Glossary master covers all four.
5. **Sensitivity labels gate behavior, not just visibility** — Tom's $200 credit ceiling is enforced by the Confidential label's mandatory rule; SIN columns are Highly Confidential and trigger Protection Policy. ✓ Label policy + Fabric Protection Policy.
6. **Lineage answers "where did this number come from?"** — Every measure has a clickable chain from visual to source. ✓ `tools/purview_custom_lineage.py` plus native scan output.
7. **The Data Agent answers in business language** — Tom can ask "show me Maria's furnace status" and the agent disambiguates "furnace" via the equipment ontology, resolves the service request, and surfaces the SLA breach. ✓ Phase C deliverable: equipment ontology + verified Q&A pack.
8. **Three personas, one truth** — Tom, Victoria, and the auditor see the same KPIs by the same definitions through the same governed surfaces, with no manual reconciliation step. ✓ End-to-end demo run.

If any of those eight acceptance criteria fails when the scenario runs, the demo fails on the central thesis. They are the demo's pass/fail bar.

---

## How the design serves Maria — feature traceability

| Design element | Maria-scenario role |
|---|---|
| 3 governance domains | DOM-CUSTOPS hosts Maria's customer record; DOM-SVCDEL hosts her service request; DOM-REVCON hosts her contract and billing |
| 3 data products | DP-CUST360 is Tom's identity surface; DP-SVCPERF is Tom's equipment + ticket surface; DP-BILLHEALTH is Tom's credit authority surface |
| ~46 glossary terms (Phase C complete) | Every business term Tom or Victoria uses in conversation maps to a published glossary term with an owner, definition, and source binding |
| 12 CDEs | Every load-bearing data element (account number, consent state, contract amount, SIN partial, payment partial) is certified by a published CDE |
| 4 sensitivity labels + Protection Policy | Tom's credit authority and Victoria's drill-down are both gated by labels; Highly Confidential is protection-enforced |
| Two-headed domain ownership | Victoria (business) and Ci Zhu (data governance) co-own DOM-CUSTOPS, preventing either from unilaterally redefining "customer" |
| Term-level policies on PIPEDA / CASL / CONSENT / SIN / PCISCOPE terms | Tom can't text Maria without active consent; the data product enforces the rule, not Tom's training |
| SemPy Labs writeback of descriptions, AI instructions, verified Q&A on `BrookfieldEnercare` | The Data Agent can answer Tom's natural-language questions because the runtime metadata surface carries the business definitions Purview governs |
| Custom Purview SIT (ENERCARE.PRIVACY.SIN_BACKSTOP) | Layered SIN classification guarantee — even on synthetic data, classification fires and the Highly Confidential auto-apply rule engages |
| Custom Atlas lineage via `tools/purview_custom_lineage.py` | The "where did this number come from?" answer is one click from any KPI |
| `dbo.audit_data_access` table | Every Tom-style session and Victoria-style query is logged with purpose-of-use, supporting privacy-incident response |

---

## What's NOT in Maria's scenario (Phase D scope)

These are intentionally out of the 2-day window:

- **Ontology with typed relationships** — Maria's profile DOES traverse Customer → Service Account → Equipment → Service Request, but those traversals happen through SQL foreign keys, not declared Purview relationships. A future ontology layer would let the Data Agent answer "what other Marias have a Lennox SLP98V?" by ontology query rather than JOIN.
- **Certified-KPI endorsement workflow** — KPIs are Published. They aren't formally Certified with an expiry, an attesting role, and a re-certification cadence. Steward workflow (G10) closes this in Phase D.
- **Bilingual glossary** — The brief noted the built-in SIN classifier responds to French context (NAS, "numéro d'assurance sociale"). The demo runs in English only.
- **Real Power BI Embedded surface for Tom's CRM** — Tom's persona view in the demo is conceptual; the actual rendering target is the Fabric Data Agent for the agent narrative and a Power BI dashboard for the exec narrative.

---

## Maintenance rule

If a future change to the design (new glossary term, new data product, new role assignment, new policy) doesn't serve some part of this scenario — either Tom's call, Victoria's review, or Ci Zhu's audit answer — interrogate whether it belongs in the demo at all.

The scenario is the test. Pass it, ship it.

