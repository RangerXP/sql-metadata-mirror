# Phase 3 Step 1 - Source Readiness and Coverage Review

## Purpose

Kick off Phase 3 with a deterministic source-readiness baseline for call-center AI enrichment.
This step verifies whether current data assets can support Maria northstar intents and identifies backfit gaps.

## Scope for this step

1. Review fact, dimension, and measure coverage for call-center AI intents.
2. Trace each high-priority intent to SQL source tables and semantic model objects.
3. Classify each intent as SUPPORTED or BACKFIT_REQUIRED.
4. Produce evidence artifacts required for Phase 3 Milestone P3-1 closure.

## Baseline assets reviewed

### SQL governance and source tables (mirrored)

- governance_domains
- governance_data_products
- governance_glossary_terms
- governance_cdes
- governance_role_assignments
- governance_label_assignments
- customers
- service_accounts
- equipment_registry
- contracts
- billing_transactions
- service_requests
- customer_consents
- customer_complaints
- products
- employees
- service_zones

### Semantic model tables

- dim_customer
- dim_service_account
- dim_equipment
- dim_product
- dim_date
- dim_cc_agent
- dim_cc_billing_adj
- fct_service_request
- fct_billing
- fct_contract_month
- fct_cc_interactions
- fct_cc_transcript_turns

### Semantic model measures (call-center relevant)

- SLA Breach Count
- SLA Compliance Rate
- FCR Rate
- Avg CSAT
- Avg Handle Time (sec)
- Escalation Rate
- Total MRR
- Net MRR Change

## Evidence artifact for this step

- Traceability matrix: docs/runbooks/phase3-step1-traceability-matrix.csv

## Execution checklist

### 1) SQL row-level evidence extraction

Run these queries against sqldemo mirror and export outputs for review:

```sql
SELECT TOP 200 * FROM dbo.customers ORDER BY customer_id;
SELECT TOP 200 * FROM dbo.service_accounts ORDER BY service_account_id;
SELECT TOP 200 * FROM dbo.equipment_registry ORDER BY equipment_id;
SELECT TOP 200 * FROM dbo.service_requests ORDER BY request_id;
SELECT TOP 200 * FROM dbo.billing_transactions ORDER BY transaction_id;
SELECT TOP 200 * FROM dbo.contracts ORDER BY contract_id;
SELECT TOP 200 * FROM dbo.customer_complaints ORDER BY complaint_id;
SELECT TOP 200 * FROM dbo.customer_consents ORDER BY consent_id;
SELECT TOP 200 * FROM dbo.governance_glossary_terms ORDER BY term_code;
SELECT TOP 200 * FROM dbo.governance_cdes ORDER BY cde_id;
```

### 2) Maria cohort pull

```sql
SELECT * FROM dbo.customers WHERE customer_id = 18374622 OR account_number = 'EC18374622';
SELECT * FROM dbo.service_accounts WHERE customer_id = 18374622;
SELECT * FROM dbo.equipment_registry WHERE service_account_id IN (
  SELECT service_account_id FROM dbo.service_accounts WHERE customer_id = 18374622
);
SELECT * FROM dbo.service_requests WHERE service_account_id IN (
  SELECT service_account_id FROM dbo.service_accounts WHERE customer_id = 18374622
) ORDER BY created_date DESC;
SELECT * FROM dbo.billing_transactions WHERE service_account_id IN (
  SELECT service_account_id FROM dbo.service_accounts WHERE customer_id = 18374622
) ORDER BY transaction_date DESC;
SELECT * FROM dbo.customer_complaints WHERE customer_id = 18374622 ORDER BY opened_date DESC;
```

### 3) Semantic runtime verification

In Fabric, confirm the semantic model exposes current call-center tables and measures used by the matrix.
Record successful lookups for each mapped table and measure.

### 4) Classification update

Update the matrix rows from provisional to final status after row-level checks:

- SUPPORTED
- BACKFIT_REQUIRED

No high-priority intent can remain unclassified for P3-1 closure.

## Approval proof for P3-1 closure

1. Matrix is complete with status for every priority intent.
2. Each matrix row has source-table and semantic-object mapping.
3. BACKFIT_REQUIRED rows include explicit gap note and owner.
4. Domain owner and steward review sign-off is captured.

## Exit criteria for moving to P3-2

1. All priority intents are classified.
2. No blocking unknown remains on Maria core flow:
   - customer profile
   - no-heat SLA breach detection
   - billing during unresolved outage
   - recommendation eligibility path

## Full-auto execution (all Phase 3 steps where possible)

Use the orchestrator below to run Phase 3 automation end-to-end from current evidence and matrix state.

```powershell
# Use existing evidence files and regenerate Steps 2-6 artifacts
./tools/run_phase3_auto.ps1

# Optional: refresh Step 1 SQL evidence first, then regenerate Steps 2-6
./tools/run_phase3_auto.ps1 -RunSql
```

Generated outputs:

- docs/runbooks/phase3-auto/phase3-step1-evidence-inventory.csv
- docs/runbooks/phase3-auto/phase3-step2-kpi-certification.csv
- docs/runbooks/phase3-auto/phase3-step3-smoke-prompts.csv
- docs/runbooks/phase3-auto/phase3-step4-ordering-check.md
- docs/runbooks/phase3-auto/phase3-step5-backfit-log.csv
- docs/runbooks/phase3-auto/phase3-step6-closeout-gate.md
