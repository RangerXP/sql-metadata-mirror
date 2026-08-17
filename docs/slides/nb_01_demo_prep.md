# Notebook 01: `01_setup_source_data` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/01_Notebook_Description.md` (which documents the
live-run validation history — bugs found, fixes applied, run evidence), this document catalogs
the **artifacts this notebook produces**, evaluates them against the build's demo requirements,
and explains how they support the Maria Castellanos north-star scenario. This is the source
document for demo slide development — every artifact listed here should be traceable to a
specific moment in the demo narrative.

---

## Notebook purpose & role

**What it is:** The foundational data-generation notebook. It is the single source of all
synthetic Enercare operational data used anywhere downstream — the lakehouse landing zone, the
Azure SQL "system of record," and the call-center interaction dataset that drives the entire
Maria Castellanos storyline.

**How it's applied:** Runs first in the 10-notebook sequence, always in live mode (no
`DEMO_MODE` dry-run gate — its entire job is to write data). It seeds `lh_enercare_demo` lakehouse
tables directly via Spark, then publishes the same data into Azure SQL (`sqlserver-sk2wus3` /
`sqldemo`) as the authoritative source system that Fabric Mirroring replicates back from —
establishing the sub2 (SQL) → sub1 (Fabric) architecture pattern the whole demo is built on.

**Use-case delivery objective:** Everything Tom sees on Maria's call (Act 1), everything
Victoria drills into in her quarterly review (Act 2), and the underlying data Ci Zhu's audit
answer traces back to (Act 3) originates here. This notebook's job is to make that data
*realistic enough* that the Maria scenario reads as a genuine operational incident, not a
scripted demo — including the deliberately-designed correlation (billing-queue contact →
lower PP-renewal rate) that Victoria's dashboard surfaces as an insight in Act 2.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| `lh_enercare_demo.dim_date` | Lakehouse table (4,748 rows) | Calendar date dimension | Powers all daily/monthly/fiscal trend calculations across every downstream KPI |
| `lh_enercare_demo.dim_customer` | Lakehouse table (51 rows) | Customer master, incl. Maria Castellanos as row 51 | Anchors every customer-scoped query (Tom's CRM lookup, Victoria's cohort drill) |
| `lh_enercare_demo.dim_product` | Lakehouse table (10 rows) | Product/plan catalog (HVAC_PLAN, WH_RENTAL_PLAN, etc.) | Classifies contracts and equipment by product line |
| `lh_enercare_demo.dim_service_account` | Lakehouse table (57 rows) | Service address / premise dimension | Backs GT-PREMISE / GT-FSA lookups Tom uses to verify Maria's identity |
| `lh_enercare_demo.dim_equipment` | Lakehouse table (39 rows) | Equipment registry incl. Maria's Lennox SLP98V furnace | The exact record Tom reads from during the call ("installed October 2020, fully under warranty") |
| `lh_enercare_demo.fct_billing` | Lakehouse table (587 rows) | Billing transaction fact | Source for DP-BILLHEALTH; the $89.95 monthly charge and SLA credit Tom applies live here |
| `lh_enercare_demo.fct_service_request` | Lakehouse table (31 rows) | Open/in-progress service requests | Contains Maria's SR-2026-051142 no-heat ticket and its missed-SLA state |
| `lh_enercare_demo.fct_contract_month` | Lakehouse table (1,250 rows) | Monthly MRR contribution per contract | Powers Net MRR / Churn / New MRR measures Victoria reviews |
| `lh_enercare_demo.dim_cc_agent` | Lakehouse table (15 rows) | Call-center agent roster incl. Tom Nguyen (employee_id 101) | Attributes every interaction to a named agent for AHT/FCR/QA scoring |
| `lh_enercare_demo.dim_cc_billing_adj` | Lakehouse table (12 rows) | Billing-adjustment/credit category reference | Classifies the SLA credit Tom applies during the call |
| `lh_enercare_demo.fct_cc_interactions` | Lakehouse table (300 rows) | Call-center interaction fact — queue, handle time, CSAT, PP-renewal outcome | The dataset behind FCR, CSAT, AHT, Escalation Rate, and PP Renewal Rate KPIs |
| `lh_enercare_demo.fct_cc_transcript_turns` | Lakehouse table (3,479 rows) | Turn-by-turn call transcript detail | Supports the Data Agent's ability to answer transcript-level questions about specific interactions |
| `sqldemo.customers`, `.service_accounts`, `.equipment_registry`, `.contracts`, `.service_requests`, `.billing_transactions`, `.customer_consents`, `.customer_complaints` | Azure SQL tables (sub2) | Authoritative "system of record" mirror of the same operational dataset | The source Fabric Mirroring replicates from — proves the sub2→sub1 lakehouse pattern enterprise customers actually deploy |
| Synthetic SINs (Luhn-valid) | Data element within `customers` | Realistic-but-fake Canadian Social Insurance Numbers | Exercises the Purview SIN classifier/backstop without using any real PII |
| Billing-caller / PP-renewal cohort design | Data correlation embedded in `fct_cc_interactions` | Deliberately-designed churn signal: billing-queue callers renew at ~51% vs. ~86% for others | The exact insight Victoria's dashboard surfaces and the Data Agent cites as a verified, quantified fact (see notebook 2's `ai_metadata`) |

## Build requirement evaluation

| Requirement (per `docs/design-gap-analysis.md` design decisions) | How this notebook satisfies it |
|---|---|
| T1 tier: source SQL holds operational data + PII | `sqldemo` publish step is the T1 landing point; SINs and consent data live here, not in Fabric-native tiers |
| "Do not assume source extended properties exist" | All descriptive metadata is generated fresh by this notebook's own data model, never assumed from source schema comments |
| Maria scenario is the pass/fail bar | Every table above is directly traceable to a specific line of dialogue in `docs/purview-maria-north-star-scenario.md` Act 1 |
| Demo correlation must be robust, not cohort-specific | Cell-level runtime assertion (`RuntimeError` if non-billing-caller rate doesn't exceed billing-caller rate) enforces this structurally, not just narratively |

## Demo narrative support

- **Act 1 (Tom's call):** every data point Tom reads aloud — account number, service address,
  equipment model/warranty status, the SR-2026-051142 ticket, the $89.95 monthly charge —
  originates in this notebook's tables. A slide showing "one seeded dataset, one live call" can
  literally screenshot `dim_equipment`/`fct_service_request` rows next to the script excerpt.
- **Act 2 (Victoria's review):** the billing-caller/PP-renewal correlation is the single most
  reusable "aha" artifact from this notebook — it's a genuine, quantified, defensible business
  insight (not a vanity stat) that a slide can present as "the KPI dashboard surfaced a real
  churn driver the business didn't know it had."
- **Talking point:** "This isn't a static demo dataset — it's a full operational system:
  customers, contracts, billing, service requests, and 300 real call-center interactions with
  transcripts, all internally consistent enough to survive an executive drilling into it."

## High-level outcome

By the end of this notebook, a complete, internally-consistent synthetic operational dataset
exists in both the Fabric lakehouse and Azure SQL, ready to be mirrored, reshaped into a star
schema, and governed. Every subsequent notebook in the sequence builds on data that originates
here — this is the foundation the entire Maria Castellanos narrative and every downstream KPI
depends on.

---

See also: [`docs/01_Notebook_Description.md`](../01_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
