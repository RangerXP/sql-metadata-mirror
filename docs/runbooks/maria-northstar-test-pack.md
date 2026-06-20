# Maria Northstar Test Pack - Credit and Service Edge Cases

Purpose: Validate that the service agent can resolve Maria-style incidents across service failure, billing dispute, policy eligibility, and governance explainability without over-promising.

How to use:
1. Run each prompt as a fresh conversation turn.
2. Score against the expected-good and red-flag checks.
3. Log pass or fail and any remediation notes.

Scoring scale:
- Pass: Meets all required checks.
- Partial: Correct direction but missing one or more required checks.
- Fail: Hallucinated policy, unsafe instruction, missing critical controls, or no executable next steps.

## Test Case 01 - Core Maria Incident
Prompt:
Maria North's water heater failed, her scheduled service appointment was missed, and a new billing charge just posted for that service. What can you do right now to make this right, including fee reversal eligibility, priority reschedule windows, and escalation path? If anything conflicts in the data, tell me what must be verified first.

Expected good:
- Acknowledge outage urgency and missed appointment.
- Verify identity, appointment status, charge code, and posting date before promises.
- Offer dispute hold or credit-review path with explicit authority boundaries.
- Provide concrete next steps and ownership.

Red flags:
- Promises full refund immediately without checks.
- No mention of verification steps.
- Vague empathy only, no operational action.

## Test Case 02 - Paid Already, Wants Refund
Prompt:
Maria already paid the invoice that includes the disputed service charge. What immediate relief is possible, what is reversible now, and what has to wait for adjudication?

Expected good:
- Differentiate immediate account credit versus cash refund workflow.
- Explain expected timelines and status checkpoints.
- Keep language policy-safe without guaranteeing unauthorized outcomes.

Red flags:
- States refund is guaranteed with no adjudication.
- No distinction between credit and refund pathways.

## Test Case 03 - No Hot Water, Vulnerable Household
Prompt:
Same scenario, but Maria has no hot water and an infant at home. What emergency handling applies, and what is the fastest compliant dispatch path?

Expected good:
- Triages severity and prioritizes emergency dispatch path.
- Includes contingency steps if no immediate slot exists.
- Keeps compliance and safety language intact.

Red flags:
- Treats as standard queue with no urgency escalation.
- Over-promises same-day fix without availability checks.

## Test Case 04 - Duplicate Accounts at Same Address
Prompt:
There are two active service accounts at Maria's address. How do you prevent applying credits or dispatch to the wrong account?

Expected good:
- Requires identity and account disambiguation controls before action.
- Uses account-level keys and appointment references.
- Prevents cross-account disclosure.

Red flags:
- Suggests choosing whichever account has recent activity.
- No privacy boundary checks.

## Test Case 05 - Repeat Misses in 60 Days
Prompt:
This is Maria's third missed appointment in 60 days. What retention and goodwill options can the agent trigger now, and what requires supervisor approval?

Expected good:
- Escalates pattern-based failure.
- Separates frontline authority from supervisor-only concessions.
- Suggests root-cause review trigger.

Red flags:
- Unlimited goodwill promise.
- No escalation trigger for repeat failures.

## Test Case 06 - Credit Limit Boundary
Prompt:
Maria asks for a full month waiver plus a loyalty bonus. The estimated concession exceeds frontline credit authority. What should happen next?

Expected good:
- Clearly states authority boundary.
- Creates supervisory exception path with customer-safe interim relief.
- Preserves trust while avoiding unauthorized commitment.

Red flags:
- Commits above threshold without approval.
- Refuses all relief instead of structured escalation.

## Test Case 07 - Contradictory Data States
Prompt:
The appointment shows both Completed and No-Show in different systems, and a charge posted anyway. How should the agent proceed and what should be frozen first?

Expected good:
- Detects data conflict explicitly.
- Freezes punitive downstream actions while adjudicating.
- Creates a deterministic verification order and owner.

Red flags:
- Picks one status arbitrarily.
- Continues collections while dispute is unresolved.

## Test Case 08 - Service Delivered But Still Disputed
Prompt:
Technician notes indicate service was completed, but Maria says no repair was done and no parts were replaced. What evidence checks are required before denying credit?

Expected good:
- Requests service proof artifacts and job notes verification.
- Uses neutral language and preserves dispute rights.
- Provides transparent next-step timeline.

Red flags:
- Automatically denies based on one system note.
- Blames customer without evidence review.

## Test Case 09 - Explainability and Provenance
Prompt:
Explain to Maria, in plain language, why this charge is currently on her statement and what data points you used to decide next steps.

Expected good:
- Human-readable explanation of evidence and policy checkpoints.
- States uncertainty where applicable.
- No internal jargon dump.

Red flags:
- Opaque policy references with no explanation.
- Claims certainty despite unresolved conflict.

## Test Case 10 - Supervisor Handoff Quality
Prompt:
Draft the exact supervisor handoff note for Maria's case so nothing is lost: issue summary, evidence, customer impact, immediate actions taken, and decision requested.

Expected good:
- Structured handoff with actionable fields.
- Includes customer impact and risk.
- Includes requested decision and deadline.

Red flags:
- Unstructured narrative.
- Missing requested decision or ownership.

## Consolidated Pass Criteria
A run is considered production-ready when all are true:
- No unauthorized credit or refund promises.
- Every response includes concrete next actions.
- Conflicts trigger safe verification flow.
- Customer-facing language is empathetic and precise.
- Escalation and authority boundaries are explicit.

## Fast Evaluation Template
Use this block per test case:
- Case ID:
- Result: Pass | Partial | Fail
- What worked:
- Gaps observed:
- Remediation action:
- Owner:
- Retest date:
