# Phase 3 Step 3 Runtime Smoke Log

## Scope

- Milestone: P3-3 Verified Answers pack for call-agent prompts
- Prompt source: docs/runbooks/phase3-auto/phase3-step3-smoke-prompts.csv
- Run date: 2026-06-24

## Test execution instructions

1. Open the Enercare Data Agent runtime in Fabric.
2. Run each prompt exactly as written.
3. Paste the response excerpt into the Actual Response column.
4. Mark Pass if behavior matches Expected Class and Expected Behavior.
5. Save this file and include it in P3 sign-off packet.

## Runtime smoke table

| Intent Key | Intent ID | Expected Class | Prompt | Expected Behavior | Actual Response (excerpt) | Pass/Fail | Notes |
|---|---|---|---|---|---|---|---|
| no-heat | P3I-002 | SUPPORTED | Customer says no heat since yesterday. What is current SLA status and next action? | Return evidence-backed recommendation path. | Cites emergency SLA targets (4-hour dispatch, 24-hour resolution), identifies potential breach risk, and provides escalation + dispatch actions with owner/SLA timing. | PASS | Response class and action path align to SUPPORTED behavior. Runtime noted ~6 sec. |
| missed appointment | P3I-003 | BACKFIT_REQUIRED | Customer missed appointment and asks why technician did not arrive. What deterministic cause can be provided? | Return safe fallback and identify missing governed data attribute. | States deterministic cause unavailable from model; names missing governed attribute (dispatch exception/missed appointment cause); provides safe fallback and escalation/reschedule path. | PASS | Correct BACKFIT fallback with explicit missing-attribute disclosure. Runtime noted ~8 sec. |
| billing while unresolved outage | P3I-004 | SUPPORTED | Customer has an unresolved outage and still sees charges. Explain whether billing exposure exists and what remediation applies. | Return evidence-backed recommendation path. | Confirms billing exposure during unresolved outage; provides remediation sequence (pause billing, credit/refund, escalation, documentation) with ownership and SLA window. | PASS | Meets SUPPORTED evidence-backed recommendation expectation. Runtime noted ~16 sec. |
| credit eligibility | P3I-006 | BACKFIT_REQUIRED | Is this customer eligible for credit based on service outage and billing state? | Return safe fallback and identify missing governed data attribute. | Provides provisional fallback logic; identifies missing governed attributes (credit eligibility reason / adjudication outcome); routes to manual billing review and follow-up SLA. | PASS | Correct BACKFIT response with governed data gap called out. Runtime noted ~7 sec. |
| repeat complaint risk | P3I-005 | BACKFIT_REQUIRED | Does complaint history indicate repeat-complaint escalation risk? | Return safe fallback and identify missing governed data attribute. | Indicates no deterministic repeat-risk flag; names missing complaint-frequency/escalation attribute; provides safe fallback using recent history + supervisor escalation. | PASS | Correct BACKFIT fallback and missing-attribute disclosure. Runtime noted ~6 sec. |

## Completion gate

- P3-3 passes when all 5 prompts are executed and no SUPPORTED intent returns fallback-only responses.
- BACKFIT_REQUIRED intents are expected to return explicit fallback and missing-data disclosure.

## Execution result

- Prompts executed: 5/5
- SUPPORTED intents passing expected behavior: 2/2
- BACKFIT_REQUIRED intents returning compliant fallback behavior: 3/3
- Overall P3-3 runtime smoke status: PASS

## WP-1 revalidation rerun (post backfill)

- Rerun date: 2026-06-24
- Prompt rerun: `P3I-003 missed appointment`
- Runtime response time: ~4 sec
- Observed behavior: agent still returned fallback-only response with missing-attribute disclosure (no deterministic dispatch cause surfaced)
- Interim outcome: WP-1 SQL/schema backfill is implemented, but runtime grounding has not yet reflected `no_show_reason_code`
- Required next step: refresh/re-publish Data Agent grounding surfaces and rerun P3I-003 before closing WP-1
