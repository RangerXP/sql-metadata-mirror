# Phase 3 Step 5 Backfit Execution Plan

## Scope

- Milestone: P3-5 Backfit sprint for annotation-data gaps
- Source log: docs/runbooks/phase3-auto/phase3-step5-backfit-log.csv
- Run date: 2026-06-24

## Backfit work packages

### WP-1: Missed appointment deterministic causality

- Intent: P3I-003
- Owner: Service Ops Steward
- Gap: no_show_reason_code / dispatch-failure taxonomy missing
- Implementation target: add governed field and backfill recent request history
- Implementation status: IMPLEMENTED on 2026-06-24
- Implementation notes: added `dbo.service_requests.no_show_reason_code` and deterministic backfill taxonomy (`DISPATCH_NO_REASSIGN`, `CUSTOMER_NOT_HOME`, `TECH_CAPACITY_CONSTRAINT`, `WEATHER_DELAY`, `CAUSE_UNSPECIFIED`, `NOT_APPLICABLE`)
- Exit proof (pending): rerun P3-3 missed-appointment runtime prompt and capture deterministic no-show causality output

### WP-2: Repeat complaint recurrence indicator

- Intent: P3I-005
- Owner: Customer Ops Steward
- Gap: repeat complaint lookback/threshold marker missing
- Implementation target: define recurrence policy and derive repeat_complaint_flag
- Proposed target date: 2026-07-08
- Exit proof: risk flag available for repeat complaint prompts

### WP-3: Credit eligibility governed rule artifact

- Intent: P3I-006
- Owner: Domain Owner
- Gap: governed credit eligibility decision artifact missing
- Implementation target: create credit_eligibility_rule table/view and bind to instruction priority
- Proposed target date: 2026-07-10
- Exit proof: deterministic credit eligibility output without fallback-only behavior

## Sprint cadence

1. Design freeze and field definitions: 2026-06-26
2. Implementation + backfill: 2026-06-27 to 2026-07-08
3. Validation rerun (P3-3 smoke prompts for affected intents): 2026-07-10
4. Close or formally defer each item with owner/date/risk: 2026-07-11

## Conditional closeout rule

- P3-6 can close conditionally now with documented risk acceptance.
- Full close requires all three backfit items implemented or explicitly deferred with approved risk acceptance.
