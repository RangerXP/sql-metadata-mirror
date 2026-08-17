# `01_setup_source_data` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-17.

## Purpose being validated

Establishes the environment and authoritative source data: 7 lakehouse source tables, the
call-center extension (`cc_agents`, `fct_cc_interactions`, `fct_cc_transcript_turns`,
`ref_cc_billing_adj_category`), publish to Azure SQL (`sqldemo`), Purview PII/demo extensions
(Phase B), Luhn-valid SIN backfill, and the (as of 2026-08-16) governance-metadata *prerequisite
check* rather than duplicate creation.

## Run record

| Field | Value |
|---|---|
| Notebook item ID | `72fcdfdf-cf7d-40b6-be03-fe76c877f2d9` |
| Job ID | `000c66c0-62c5-4226-9b49-d65d1cc98e21` |
| Start (UTC) | 2026-08-17T04:56:16.59 |
| End (UTC) | 2026-08-17T05:03:45.41 (≈7.5 min) |
| Status | `Completed` |
| Failure reason | `null` |

## Data write-out confirmation

**Lakehouse (`lh_enercare_demo`, via SQL analytics endpoint):**

| Table | Row count | Expected |
|---|---|---|
| `customers` | 50 | 50 (seed) ✅ |
| `cc_agents` | 15 | 15 (seed) ✅ |
| `ref_cc_billing_adj_category` | 12 | 12 (seed) ✅ |
| `fct_cc_interactions` | 300 | 300 (target) ✅ |
| `fct_cc_transcript_turns` | 3,479 | variable (6–18 turns/interaction) ✅ plausible |

**Azure SQL (`sqldemo`, authoritative mirrored source):**

| Table | Row count | Note |
|---|---|---|
| `customers` | 51 | 50 synthetic + Maria Castellanos (`customer_id=18374622`), added by the Phase B seed on top of the base 50 — **not a duplication bug**, confirmed no `customer_id` appears more than once |
| `service_accounts` | 57 | ✅ |
| `equipment_registry` | 39 | ✅ |
| `contracts` | 57 | ✅ |
| `service_requests` | 31 | ✅ |
| `billing_transactions` | 587 | ✅ |
| `employees` | 19 | ✅ (Phase B) |
| `service_zones` | 8 | ✅ (Phase B) |
| `customer_consents` | 124 | ✅ (Phase B) |
| `customer_complaints` | 19 | ✅ (Phase B) |
| `data_owners_directory` | 13 | ✅ (Phase B) |
| `audit_data_access` | 204 | ✅ (Phase B) |

## Maria Castellanos north-star use-case match

- ✅ Maria's customer record exists in Azure SQL (`customer_id=18374622`), distinct from the 50
  generic synthetic customers.
- ✅ Maria has 4 `customer_consents` rows, all `Granted` (Marketing-Email, Marketing-SMS,
  Data-Sharing, Retention).
- ✅ Maria has 1 `customer_complaints` row (`Service` type).
- ✅ The 14-customer designed correlation cohort (`CORR_CUSTOMERS`) renews at **60%** in the
  live data (target ~57% per the notebook's own embedded check) — matches intent.
- ⚠️ **Finding (not a bug, a narrative-scoping nuance):** the "~76% baseline" language used to
  describe this correlation (in this session's own earlier documentation) describes the
  *designed 14-customer cohort's counterfactual*, not a broadly-queryable population statistic.
  Independently re-querying with two different broader baseline definitions gives different,
  smaller gaps:
  - `customer_id NOT IN (the 14)`, unfiltered for incidental billing calls: **54.5%** (n=58) —
    gap vs. cohort is small and in the *wrong* direction (54.5% < 60%).
  - Customers with **zero** billing-queue interaction anywhere in the dataset (a cleaner
    "never called about billing" cohort): **71.4%** (n=7, very small sample) — direction is
    correct (billing callers renew less) but the sample is too thin to be a robust standalone
    Data Agent talking point.
  - **Root cause:** service-queue assignment for the other 272 interaction rows is random
    across all 50 customers (`cust_id = (seq % 50) + 1`), so most customers end up with at
    least one incidental billing-queue interaction by chance, diluting any broad "billing
    caller" cohort query.
  - **Implication for Act 1 (Tom's Data Agent grounding):** the "billing callers renew less"
    insight is only reliably true for the specific, hand-designed 14-customer cohort. It depends
    on `04_writeback_governed_metadata`'s AI-grounding annotations correctly scoping the
    verified answer/AI instruction to that cohort (or the Q1-2026 billing-then-renewal pattern),
    not on the Data Agent constructing an ad-hoc broad-population query on its own. This is a
    dependency to check explicitly during notebook 4's validation, not a fix needed here.

## Governance-metadata prerequisite check (CELL B4A)

- ✅ Passed. `dbo.governance_domains` already had 3 rows (from a prior manual run of
  `sql/02_metadata_foundation/06_purview_metadata_schema.sql` / `07_seed_purview_metadata.sql`),
  so the prerequisite check's `RuntimeError` path was not triggered — correct behavior for an
  environment where the SQL-first governance scripts have already been applied.

## Issues encountered

None. Job completed on the first attempt with the hardened runner tool (~7.5 minutes,
well within the new 30-minute execution timeout).


## Issues encountered

*(pending)*
