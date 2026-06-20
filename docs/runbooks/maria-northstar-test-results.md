# Maria Northstar Test Results

Test pack source: docs/runbooks/maria-northstar-test-pack.md
Answer key: docs/runbooks/maria-northstar-answer-key.md

## Submission Evidence
- Commit: 43ebdef
- Branch: main
- Remote: origin/main
- Status: Submitted and pushed

## Execution Results
Note: The cases below require live execution through the Data Agent runtime. This file captures the current state and provides a place to record outcomes.

| Case ID | Scenario | Result | What Worked | Gaps | Remediation | Owner | Retest Date |
|---|---|---|---|---|---|---|---|
| 01 | Core Maria incident | Fail | Returned a deterministic lookup outcome and explicitly stated no qualifying incident found in current model rows. | No urgent customer-impact handling; no dispute hold path; no conditional fee-review workflow; no actionable owner/ETA; defaulted to deflection asking for more identifiers instead of safe operational fallback. | Add fallback policy behavior when incident evidence is incomplete: acknowledge outage harm, open provisional billing dispute hold, trigger priority dispatch review, and escalate to supervisor queue with decision SLA. Add test assertion that responses must include ownership and next-step timeline even on no-match outcomes. | Sean Kelley / Copilot | 2026-06-20 |
| 02 | Paid already, wants refund | Pending |  |  |  |  |  |
| 03 | Vulnerable household urgency | Pending |  |  |  |  |  |
| 04 | Duplicate accounts at address | Pending |  |  |  |  |  |
| 05 | Third miss in 60 days | Pending |  |  |  |  |  |
| 06 | Credit authority boundary | Pending |  |  |  |  |  |
| 07 | Contradictory data states | Pending |  |  |  |  |  |
| 08 | Service completed vs customer dispute | Pending |  |  |  |  |  |
| 09 | Explainability and provenance | Pending |  |  |  |  |  |
| 10 | Supervisor handoff quality | Pending |  |  |  |  |  |

## Current Summary
- Pack submission: Complete
- Case execution: In progress (live runtime unstable; Case 01 captured)
- Captured case outcomes: 1/10
