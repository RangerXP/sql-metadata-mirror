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
| 01 | Core Maria incident | Partial (Retest) | Correctly resolved Maria Castellanos context with Emergency Repair service request 2026051142 (InProgress), SLA breach, furnace equipment, and dispatch escalation owner (GTA North supervisor). | Did not return INV-MARIA-202606 / CR-MARIA-SLA-202606 rows; did not commit to provisional dispute hold when billing evidence was missing; timeline/SLA for billing adjudication remained weak. | Tighten prompt contract to require fallback actions on missing billing rows: provisional billing-dispute hold, named billing adjudication owner, and explicit decision SLA (for example 24 hours). Continue using model anchors (EC18374622, invoice and credit memo IDs) for deterministic lookup. | Sean Kelley / Copilot | 2026-06-20 |
| 02 | Paid already, wants refund | Fail | Correctly avoided unauthorized refund guarantees and identified that no matching charge was visible. | No immediate customer-safe relief path (for example provisional dispute hold); no distinction between account credit vs cash refund workflow; no owner/ETA/SLA for adjudication; excessive deflection to user-provided identifiers. | Implement no-match fallback policy: open provisional billing dispute hold, route manual billing adjudication with owner and decision SLA, and explain conditional paths for immediate account credit vs post-adjudication cash refund. Add evaluator rule that Case 02 must include timelines and ownership even when record lookup fails. | Sean Kelley / Copilot | 2026-06-20 |
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
- Case execution: In progress (live runtime unstable; Cases 01-02 captured)
- Captured case outcomes: 2/10 (Case 01 retested with model-aligned prompt; now Partial)
