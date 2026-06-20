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
| 01 | Core Maria incident | Pass (Retest) | Returned all required surfaces in one response: customer record (Maria Castellanos, EC18374622, Markham L4G 2H9, Active), service record (Request 2026051142, Emergency/InProgress, SLA breached, pending tech notes), billing record with both posted rows (INV-MARIA-202606 MonthlyCharge 89.95 and CR-MARIA-SLA-202606 Credit -14.99), and sentiment/complaint signal status. Provided clear credit-vs-refund decision (credit-first), named owners (GTA North dispatch supervisor + Billing Support), and 24-hour customer callback SLA. | Transcript sentiment/intent rows were not present in current model slice; response correctly flagged this as a data gap to verify rather than hallucinating sentiment evidence. | Keep Case 01 prompt in model-anchored form. For future sentiment completeness, ensure latest call transcript rows are mirrored into `fct_cc_transcript_turns` before retest. | Sean Kelley / Copilot | 2026-06-20 |
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
- Captured case outcomes: 2/10 (Case 01 retested with model-anchored prompt; now Pass)

## Case 01 Evidence Snapshot (Latest Retest)
- Runtime completion: 4 steps completed
- Customer view surfaced: Maria Castellanos, EC18374622, Markham, L4G 2H9, Active
- Service view surfaced: Request 2026051142 (Emergency, InProgress), SLA breached, pending-tech dispatch note
- Billing view surfaced: INV-MARIA-202606 (MonthlyCharge 89.95, Posted) and CR-MARIA-SLA-202606 (Credit -14.99, Posted)
- Sentiment view surfaced: no recent sentiment/intent/escalation rows found in current model slice (flagged as missing evidence)
- Decision surfaced: credit-first remedy, not refund-first, with owners (GTA North dispatch supervisor and Billing Support) and 24-hour callback SLA
