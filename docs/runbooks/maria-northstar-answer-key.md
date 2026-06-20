# Maria Northstar Answer Key

Purpose: Provide gold-standard response patterns for the 10-case Maria Northstar pack so evaluators can score consistency and policy compliance.

Source pack: docs/runbooks/maria-northstar-test-pack.md
Results tracker: docs/runbooks/maria-northstar-test-results.md

## Case 01 - Core Maria Incident
Gold response pattern:
- Acknowledge impact and apologize.
- Verify: account identity, service request status, appointment history, disputed charge code/date.
- Immediate actions: open dispute, place temporary collection hold on disputed line, trigger priority dispatch review.
- Relief path: pro-rated service recovery credit subject to policy threshold; supervisor path if above threshold.
- Close with ETA and callback owner.

Example concise answer:
I am sorry this happened. I can start fixing this now. First I need to confirm your account and the specific service request and charge so we do not act on the wrong line item. Once confirmed, I will place a dispute hold on that billing item, request priority rescheduling for the missed no-hot-water appointment, and route a billing adjustment review. If the adjustment exceeds my authority, I will escalate to a supervisor immediately and keep the disputed amount protected while review is in progress.

## Case 02 - Paid Already, Wants Refund
Gold response pattern:
- Distinguish account credit versus refund to original payment method.
- If already paid: apply immediate courtesy/service credit where authorized; refund follows adjudication workflow.
- Provide timeline checkpoints.

Example concise answer:
Because the charge is already paid, I can usually apply an immediate account credit if policy allows, while a cash refund to the original payment method requires billing adjudication. I will open that now, mark it service-failure related, and provide expected milestones: investigation start, decision date, and refund posting window.

## Case 03 - Vulnerable Household Urgency
Gold response pattern:
- Triage as urgent outage.
- Trigger emergency dispatch workflow and fallback options.
- Avoid guaranteed arrival language unless confirmed.

Example concise answer:
With no hot water and an infant at home, I will classify this as urgent and escalate to emergency dispatch routing now. I will request the first available priority window and, if no immediate slot is open, escalate to the duty supervisor for override options. I will confirm the booked window before promising an exact arrival.

## Case 04 - Duplicate Accounts at Address
Gold response pattern:
- Freeze financial and dispatch actions until account disambiguation.
- Use account number, service account key, and ticket reference.
- Prevent cross-account disclosure.

Example concise answer:
I need to disambiguate the account before applying credits or dispatch updates. I will verify the exact account number and service request reference, then bind all actions to that account key only. I will not disclose or modify data on the second account.

## Case 05 - Third Miss in 60 Days
Gold response pattern:
- Treat as repeat-failure pattern requiring retention escalation.
- List immediate concessions within authority.
- Route enhanced goodwill request to supervisor.

Example concise answer:
Since this is the third miss in 60 days, I will escalate as repeat service failure. I can apply standard relief within my authority now and open a supervisor goodwill review for additional concessions. I will also flag this for root-cause dispatch review so recurrence is addressed.

## Case 06 - Credit Authority Boundary
Gold response pattern:
- Explicitly state authority limit.
- Offer interim relief within limit.
- Escalate exception with decision SLA.

Example concise answer:
The full concession requested is above my approval limit. I can apply the maximum allowed immediate relief now and escalate the remaining request to a supervisor for exception approval. I will include full case evidence and provide you with the decision timeframe.

## Case 07 - Contradictory Data States
Gold response pattern:
- Detect contradiction as data conflict.
- Freeze punitive actions first (collections/late fees on disputed line).
- Execute deterministic evidence order.

Example concise answer:
I see conflicting statuses, so I will treat this as a data conflict case. I will first protect you from downstream impact by holding collections on the disputed item, then verify work order events, technician logs, and charge linkage in sequence before final billing action.

## Case 08 - Service Completed vs Customer Dispute
Gold response pattern:
- Gather technician proof artifacts before denial.
- Keep neutral tone and preserve customer dispute rights.
- Define adjudication owner and timebox.

Example concise answer:
Before denying any credit, I need to review technician completion evidence such as notes, timestamped work logs, and parts usage. I will keep the dispute open while that review is completed and provide you a clear decision update by the stated deadline.

## Case 09 - Explainability and Provenance
Gold response pattern:
- Explain what data was checked and what remains uncertain.
- Use plain language; no internal jargon overload.

Example concise answer:
The charge appears because the billing cycle posted before the missed service issue was resolved. I am checking your appointment record, the linked service request, and the specific billing line for that date. If any of these do not match, I will keep the charge disputed until corrected.

## Case 10 - Supervisor Handoff Quality
Gold handoff template:
- Customer impact summary
- Verified facts
- Conflicts detected
- Actions already taken
- Decision requested
- Deadline/owner

Example handoff:
Customer: Maria Castellanos, Account EC18374622
Issue: Furnace outage, missed appointment, disputed posted service charge
Impact: Essential service interruption, repeat trust risk
Verified: Identity confirmed; furnace service request open/in progress; INV-MARIA-202606 posted (with related credit memo CR-MARIA-SLA-202606)
Conflict: Appointment state differs across systems
Actions taken: Dispute opened; collections hold on disputed line; urgent dispatch escalation submitted
Decision requested: Additional goodwill credit above frontline authority and dispatch override approval
Owner and SLA: Supervisor queue CUSTOPS-L2, decision requested within 24 hours

## Evaluator Red-Flag Quick Checks
Fail if any are present:
- Unauthorized refund or credit guarantees
- No verification step for conflicting data
- No ownership or ETA for next action
- Cross-account action without disambiguation
- Customer-blaming language

## Scoring Guidance
- Pass: All required controls present; actionable and policy-safe.
- Partial: Correct but missing one control or weak handoff clarity.
- Fail: Unsafe promise, missing critical controls, or non-actionable response.
