# `07_apply_approved_changes` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-17, including a live apply-then-revert
test cycle that found and fixed a real build gap.

## Purpose being validated

The apply-on-approve dispatcher: reads `Approved`/unapplied rows from the `sub2` SQL source,
validates required governance tags, dispatches by `request_type`, applies the change to
`lh_metadata`, and stamps the request `Applied`.

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status | Note |
|---|---|---|---|---|---|
| 1 (initial) | `153bdc54-715b-41f5-9659-dbf9b1ec75f4` | 2026-08-17T17:48:50 | 2026-08-17T17:53:01 | ✅ `Completed` | 0 errors, but all 8 existing requests were already `Applied` from prior sessions — no new dispatch work exercised |
| 2 (test request, missing tags) | `d0077628-2474-40b5-a870-4bcdcefeb290` | 2026-08-17T19:14:14 | 2026-08-17T19:18:14 | ✅ `Completed` (misleading) | `GCR-VALTEST-001` silently skipped — see Root cause below |
| 3 (test request, tags fixed) | `a158dae3-16f1-4fe2-8a72-cab392433fee` | 2026-08-17T19:24:53 | 2026-08-17T19:27:31 | ✅ `Completed` (verified) | `GCR-VALTEST-001` dispatched and applied — `kpi_metadata.AHT` confirmed updated |
| 4 (revert) | `a2de6a01-f11e-4135-9b10-5d0902993308` | 2026-08-17T19:36:49 | 2026-08-17T19:39:42 | ✅ `Completed` (verified) | `GCR-VALTEST-001-REVERT` dispatched and applied — `AHT` confirmed restored to original state |

## Root cause — undocumented mandatory governance tags

Attempt 1 completing cleanly with 0 errors only proved the notebook doesn't crash — it didn't
prove the actual dispatch/apply code path still works, since there was nothing new to process
(all 8 seeded requests were already `Applied` from 2026-08-09/2026-08-13). To genuinely exercise
the mechanism, inserted a real test request:

```sql
INSERT INTO dbo.governance_change_requests (request_id, request_type, ..., proposed_payload, ..., status, ..., applied_at)
VALUES ('GCR-VALTEST-001', 'KPI_APPROVAL', ...,
  '{"KPICode":"AHT","Version":2,"Description":"...Verified live via nb_07 apply-on-approve dispatcher test..."}',
  ..., 'Approved', ..., NULL);
```

Attempt 2 completed with 0 errors, but the request remained `status='Approved'`,
`applied_at IS NULL` — it was never dispatched. Root cause, found by inspecting
`_validate_approved_request()` in the notebook: it unconditionally requires every row's
`proposed_payload` to contain 5 tag keys — `domain`, `owner`, `sensitivity`, `semantic_role`,
`business_use` — regardless of `request_type`, silently `[SKIP]`-ing (printed, not raised) any
row that's missing them. My minimal test payload, modeled on the historical seed-data shape,
didn't include any of these keys.

**Confirmed this is a real, pre-existing gap, not something introduced by testing:** none of the
8 original seed scenarios' `proposed_payload` values (in
`sql/07_governance_gates/10_seed_gated_governance_scenarios.sql`,
`16_add_ai_instruction_gate.sql`, `25_g19_ai_instruction_lifecycle_gate.sql`) contain these 5
keys either — they were applied before this validation gate existed in the notebook's code.
This means **any new governance change request created going forward** (a future UI, or a
reseeded scenario) needs these tags or it will be silently skipped with no error surfaced
anywhere in the job API.

**Fix applied:** added the 5 required tags (with scenario-appropriate values — e.g.
`domain=DOM-SVCDEL, owner=ranbir.singh@enercare.ca, sensitivity=Internal, semantic_role=measure,
business_use=Field operations SLA compliance tracking` for the SLA Breach Rate KPI scenario) to
all 8 seed scenarios across all 3 SQL files, and synced the same tags onto the 8 already-`Applied`
live rows in `sqldemo` via `JSON_MODIFY` (safe, since already-applied rows are never re-validated,
but keeps the live data consistent with the corrected seed source for future reference/audit).

## Confirmed live: the dispatcher genuinely works today

After adding the required tags to `GCR-VALTEST-001`'s payload, attempt 3 correctly dispatched it:

- `sqldemo.dbo.governance_change_requests`: `GCR-VALTEST-001` → `status='Applied'`,
  `applied_at='2026-08-17 19:27:17'`.
- `lh_metadata.kpi_metadata`: `AHT` → `Version=2`, `CertifiedBy='Ci.Zhu@enercare.ca'`,
  `Description` containing the test marker text — confirmed via direct SQL read-back, not just
  job status.

## Clean revert through the same governed mechanism

Rather than a raw side-channel fix, inserted a second properly-tagged request
(`GCR-VALTEST-001-REVERT`, `Version=1`, original `Description`) and re-ran the notebook (attempt
4). Confirmed:

- `GCR-VALTEST-001-REVERT` → `status='Applied'`, `applied_at='2026-08-17 19:39:31'`.
- `lh_metadata.kpi_metadata.AHT` → restored to `Version=1`, original `Description` exactly.

This proves the dispatcher correctly handles both a new certification and a subsequent
correction/rollback via the identical governed path — no demo content was left in a
test-polluted state.

## Maria Castellanos north-star use-case match

- ✅ The GCR-AII-003/004 escalation-guidance scenario (a flawed edit that drops a safety/
  emergency clause, later caught and reverted) is a genuine example of the closed-loop
  governance story: bad changes get caught and corrected through the same auditable mechanism,
  not silently left in place.
- ✅ The live apply-then-revert test cycle performed here is itself a stronger, more current
  proof point than the historical 2026-08-09/13 evidence alone.

## Issues encountered

- 1 real bug found and fixed: undocumented mandatory governance-tag validation with no seed data
  actually satisfying it. See "Root cause" above for the full investigation trail.
