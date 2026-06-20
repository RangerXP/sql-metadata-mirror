# Maria Northstar Test Pack - Model-Aligned Credit and Service Edge Cases

Purpose: Validate that the service agent can resolve Maria-style incidents against seeded BrookfieldEnercare records across service failure, billing dispute, policy eligibility, and governance explainability without over-promising.

Model anchors for this pack:
- Customer: Maria Castellanos
- AccountNumber: EC18374622
- Equipment: Furnace (Lennox SLP98V, serial LX2020-MARIA98V)
- Posted billing rows: INV-MARIA-202606 (MonthlyCharge 89.95), CR-MARIA-SLA-202606 (Credit -14.99)
- Service location: Markham, ON, PostalCode L4G 2H9

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
For Maria Castellanos (AccountNumber EC18374622), confirm what the model currently shows for her furnace-related service status and her posted billing items (INV-MARIA-202606 and CR-MARIA-SLA-202606). Then explain what you can do right now to make this right: dispute/credit eligibility, fastest compliant reschedule path, escalation owner, and decision SLA. If any required evidence is missing, you must still provide a safe fallback action plan (provisional billing-dispute hold, manual billing adjudication owner, and expected timeline) and state exactly what must be verified first.

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
Using Maria Castellanos (EC18374622), first identify the posted charge and posted credit from the model. If Maria says the invoice INV-MARIA-202606 is already paid, explain what immediate relief is possible now, what is reversible now, and what must wait for adjudication. If either billing row is missing, do not stop at data-missing language: provide owner, SLA, and interim customer-safe steps (provisional dispute hold and manual billing review path).

Expected good:
- Differentiate immediate account credit versus cash refund workflow.
- Explain expected timelines and status checkpoints.
- Keep language policy-safe without guaranteeing unauthorized outcomes.

Red flags:
- States refund is guaranteed with no adjudication.
- No distinction between credit and refund pathways.

## Test Case 03 - No Hot Water, Vulnerable Household
Prompt:
Same customer and account, but treat it as a no-heat emergency (furnace outage) with an infant at home. What emergency handling applies, and what is the fastest compliant dispatch path without over-promising availability?

Expected good:
- Triages severity and prioritizes emergency dispatch path.
- Includes contingency steps if no immediate slot exists.
- Keeps compliance and safety language intact.

Red flags:
- Treats as standard queue with no urgency escalation.
- Over-promises same-day fix without availability checks.

## Test Case 04 - Duplicate Accounts at Same Address
Prompt:
If lookup at Maria's service address (Markham, L4G 2H9) returns more than one account, how do you prevent applying credits or dispatch to the wrong one? Answer using explicit disambiguation fields available in the model (for example AccountNumber, CustomerKey, ServiceAccountKey).

Expected good:
- Requires identity and account disambiguation controls before action.
- Uses account-level keys and appointment references.
- Prevents cross-account disclosure.

Red flags:
- Suggests choosing whichever account has recent activity.
- No privacy boundary checks.

## Test Case 05 - Repeat Misses in 60 Days
Prompt:
Check Maria's service-request history for the last 60 days and state what count of missed or unresolved visits is actually visible. If the pattern is repeat failure (3+), what retention and goodwill actions can frontline trigger now, and what requires supervisor approval?

Expected good:
- Escalates pattern-based failure.
- Separates frontline authority from supervisor-only concessions.
- Suggests root-cause review trigger.

Red flags:
- Unlimited goodwill promise.
- No escalation trigger for repeat failures.

## Test Case 06 - Credit Limit Boundary
Prompt:
Maria requests a full-month waiver plus loyalty bonus on top of existing adjustments. If the total concession exceeds frontline credit authority, what should happen next, what can be granted immediately within limit, and who owns exception approval?

Expected good:
- Clearly states authority boundary.
- Creates supervisory exception path with customer-safe interim relief.
- Preserves trust while avoiding unauthorized commitment.

Red flags:
- Commits above threshold without approval.
- Refuses all relief instead of structured escalation.

## Test Case 07 - Contradictory Data States
Prompt:
For Maria, read the current service status and posted billing state from the semantic model first. If an external workflow system later reports a contradictory completion/no-show state, how should the agent proceed, and what customer-impacting actions should be frozen first?

Expected good:
- Detects data conflict explicitly.
- Freezes punitive downstream actions while adjudicating.
- Creates a deterministic verification order and owner.

Red flags:
- Picks one status arbitrarily.
- Continues collections while dispute is unresolved.

## Test Case 08 - Service Delivered But Still Disputed
Prompt:
If service appears completed but Maria disputes the repair outcome, what evidence checks are required before denying credit? Use model-accessible evidence explicitly (service status, ResolutionNotes when present, billing rows, and equipment context).

Expected good:
- Requests service proof artifacts and job notes verification.
- Uses neutral language and preserves dispute rights.
- Provides transparent next-step timeline.

Red flags:
- Automatically denies based on one system note.
- Blames customer without evidence review.

## Test Case 09 - Explainability and Provenance
Prompt:
Explain to Maria, in plain language, why the INV-MARIA-202606 charge is currently on her statement and what data points you used to decide next steps (customer/account, service status, posted billing rows, and any uncertainty).

Expected good:
- Human-readable explanation of evidence and policy checkpoints.
- States uncertainty where applicable.
- No internal jargon dump.

Red flags:
- Opaque policy references with no explanation.
- Claims certainty despite unresolved conflict.

## Test Case 10 - Supervisor Handoff Quality
Prompt:
Draft the exact supervisor handoff note for Maria Castellanos (EC18374622) so nothing is lost: issue summary, evidence from the semantic model, customer impact, immediate actions taken, decision requested, owner, and decision SLA.

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
