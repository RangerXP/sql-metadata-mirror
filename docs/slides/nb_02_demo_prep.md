# Notebook 02: `02_build_metadata_foundation` — Demo Prep & Artifact Catalog

**Purpose of this document:** Unlike `docs/02_Notebook_Description.md` (the validation-history
record — the stale-schema bug hunt, fixes, run evidence), this document catalogs the
**governance metadata artifacts** this notebook produces, evaluates them against the build's
demo requirements, and explains how they support the Maria Castellanos north-star scenario.
This is the source document for demo slide development.

---

## Notebook purpose & role

**What it is:** The governance metadata foundation. It ingests the customer-authored governance
CSVs (`purview/*.csv` — domains, data products, glossary terms, CDEs, role assignments, labels,
OKRs) into `lh_metadata`, then reconciles that curated metadata against the live semantic model
to build the annotation payloads that later notebooks write back.

**How it's applied:** Runs second, always live. Two merged sections: Cells 1–9 seed/refresh the
governance tables from the SQL/CSV source; Cells 10–16 cross-reference those tables against the
live `BrookfieldEnercare` semantic model (via SemPy) to build `sm_annotations` — the staged
payload of glossary-term references, sensitivity labels, data-product ownership, and CDE
membership that `04_writeback_governed_metadata` later applies to the model.

**Use-case delivery objective:** This is where "one governed definition" becomes real data,
not just a design document. Every `GT-*`/`CDE-*`/`DP-*` code referenced anywhere in Tom's call,
Victoria's review, or Ci Zhu's audit answer has exactly one row here — this notebook is what
makes "there's only one definition" a structurally enforced fact rather than a talking point.

## Artifact catalog

| Artifact | Type | What it is | What it does |
|---|---|---|---|
| `lh_metadata.domains` | Table (3 rows) | Governance domains: Customer Operations, Service Delivery, Revenue and Contracts | Maps 1:1 to the three domains Ci Zhu references in Act 3 and that appear as Purview Governance Domains |
| `lh_metadata.data_products` | Table (3 rows) | Data products: Customer 360, Service Performance, Billing and Contract Health | The exact three data products Tom's/Victoria's CRM and dashboard surfaces query against |
| `lh_metadata.glossary_terms` | Table (35 rows) | Business glossary term catalog (GT-CUST, GT-SLA, GT-CONSENT, etc.) | The single certified definition source for every business term the demo cites |
| `lh_metadata.cdes` | Table (12 rows) | Critical Data Elements (CDE-CONTRACTAMT, CDE-CONSENTSTATE, etc.) | Marks specific columns as governance-critical, linked to their parent glossary term |
| `lh_metadata.role_assignments` | Table (48 rows) | Domain/product/term ownership and stewardship roles | Backs "who owns this definition" answers (Victoria, Ci Zhu, Rupal, Shruthi, Ranbir) |
| `lh_metadata.label_assignments` | Table (9 rows) | Sensitivity label assignments (Confidential, Highly Confidential) | The label-policy gate that governs Tom's credit authority and PII visibility during the call |
| `lh_metadata.governance_change_requests` | Table (10 rows) | Gated-approval request records (KPI, verified-answer, CDE, glossary-term, AI-instruction scenarios) | Feeds `07_apply_approved_changes`'s "click Approve → watch the data change" demo moment |
| `lh_metadata.okrs` / `okr_key_results` / `okr_data_products` | Tables (3 / 5 / 3 rows) | Business Objectives & Key Results, linked to data products | Lets a business stakeholder trace a strategic goal down to the governed data product backing it (G11-1 ontology layer) |
| `lh_metadata.ai_metadata` | Table (certified KPI instructions + verified Q&A) | Certified AI grounding content, gated by `IsDraft`/`IsCertified` | The exact content the Fabric Data Agent reads to answer Tom's/the auditor's natural-language questions — including the quantified billing-caller/PP-renewal churn insight |
| `lh_metadata.sm_annotations` | Table (77 rows: 62 Glossary_Term_References, 7 Sensitivity_Label, 6 Data_Product_Owner, 2 CDE_Member_Of) | Staged reconciliation payload between curated metadata and the live semantic model | The exact set of annotations `04_writeback_governed_metadata` applies to the model — this is the "compile step" between governance intent and semantic-model reality |
| `lh_metadata.nb02_diagnostics_log` | Table | Captured exception + traceback for any Cell 1–16 failure | Defense-in-depth: Fabric's job API exposes no cell-level detail, so this is the only way to diagnose a future failure without re-instrumenting from scratch |

## Build requirement evaluation

| Requirement | How this notebook satisfies it |
|---|---|
| T2 tier: customer-owned external files (`purview/*.csv`) as governance source | Cells 1–9 ingest directly from these CSVs (or their SQL-mirror equivalent), never inventing definitions in code |
| T3 tier: Fabric-native staging (`lh_metadata` + semantic model) | This notebook *is* the T3 staging layer — the working store for authoring and propagation before Purview (T4) publish |
| "Only certified content reaches AI grounding" | `ai_metadata` seeding gates on `IsDraft=0 AND IsCertified=1`, matching the same certification pattern used for KPIs |
| Closed-loop governance: every governed asset produces durable evidence | `sm_annotations` and `nb02_diagnostics_log` are both durable, independently queryable evidence tables, not just print-statement output |

## Demo narrative support

- **Act 1/3 (glossary + CDE definitions):** every `GT-*` and `CDE-*` code spoken in the script
  has a real row here with a real owner and definition — a slide can show the `glossary_terms`
  row for `GT-SLA` side-by-side with Tom citing the SLA policy on the call.
- **Act 2 (the churn insight):** the `ai_metadata` verified-answer row quantifying the
  billing-caller/PP-renewal gap (~51% vs. ~86%, a ~35-point gap) is a genuinely reusable slide
  artifact — it shows governed AI content isn't generic boilerplate, it's a specific, certified,
  quantified business fact.
- **Talking point:** "This is the reconciliation step — it's not enough to have a glossary CSV
  and a semantic model that don't know about each other. This notebook is what proves they
  agree, row for row, before anything gets written back."

## High-level outcome

By the end of this notebook, the full governance metadata foundation exists in `lh_metadata` —
domains, data products, glossary, CDEs, roles, labels, OKRs, and certified AI grounding content
— reconciled against the live semantic model and staged for writeback. This is the bridge
between "governance as a design document" and "governance as queryable, enforceable data."

---

See also: [`docs/02_Notebook_Description.md`](../02_Notebook_Description.md) (validation history) ·
[`docs/purview-maria-north-star-scenario.md`](../purview-maria-north-star-scenario.md)
