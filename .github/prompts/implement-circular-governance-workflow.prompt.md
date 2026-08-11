---
description: Implement the circular Purview and SQL governance workflow
mode: agent
---

# Implement the Enercare Circular Governance Workflow

Work in:

`C:\Users\seankelley\OneDrive - Microsoft\Documents\Demos\sql-metadata-mirror`

## Purpose

Use GitHub Copilot only to implement the required changes.

Use `docs/closed-loop-governance-reference-model.md` and `docs/Option_B_Closed_Loop_Governance_Development_Guide.docx` as the controlling architecture decision. Deliver one Purview-native publication workflow first. Do not expand into additional workflow types or SQL-controlled approvals until its read-back, SQL receipt, semantic reconciliation, and validation loop is proven.

The eventual expanded workflow may execute through Microsoft Purview, Azure SQL, Fabric Mirroring, Fabric notebooks, the semantic model, and the Fabric Data Agent. The first milestone ends at the selected Purview-native publication, SQL ledger, mirror observation, required semantic reconciliation, and validated receipts. This prompt is not part of the runtime.

The current demo proves metadata publication, but its approval loop is still too static. Replace the single SQL-only gate with a **two-authority circular governance model**:

1. **Purview is the change-control authority for governance operations that Purview Unified Catalog can natively approve.**
2. **Azure SQL is the change-control authority for governed changes that Purview workflows don't support.**
3. **Both paths produce a common, versioned governance event in SQL.**
4. **Fabric Mirroring carries the approved event into Fabric.**
5. **Fabric applies the event to runtime metadata and republishes governed surfaces.**
6. **Publication and validation receipts return to SQL so the cycle can be audited end to end.**

## Governing Principle

> Use Purview workflows where Purview can natively own the approval. Use SQL governance requests where Purview has no native approval type. Normalize both approval paths into one SQL governance-event contract, propagate through Fabric Mirroring, apply changes to runtime surfaces, and write publication evidence back to SQL.

## Network and Lineage Guardrail

- Keep Azure SQL and Purview private.
- Preserve native Azure SQL and Fabric scans for discovery, classifications where supported, stable GUIDs/qualified names, search, and schema-change detection.
- Use custom Atlas Process entities only for missing SQL-to-Fabric, notebook, governance-process, publication, and validation edges.
- Resolve custom process inputs and outputs to native scanned assets; do not create duplicate stand-in entities.
- Store the canonical lineage manifest and read-back receipts in SQL.
- Treat native SQL stored-procedure lineage extraction as optional diagnostics, not a dependency.
- Never open Azure SQL publicly merely to enable native stored-procedure lineage extraction.

## Delivery Sequence

### Phase 1: Purview-native closed loop

Implement and prove exactly one initial publication scenario:

1. Glossary-term publication or data-product publication.
2. Purview polling/read-back into the unified SQL event contract.
3. Semantic reconciliation only where the approved object requires it.
4. Object-specific Purview and semantic read-back.
5. SQL events, object versions, and target receipts.

Data-product access is a later audit-only native scenario and must not block the first closeout. It must not mutate semantic definitions merely because access changed.

### Phase 2: SQL source discovery

Detect one newly mirrored regular SQL table, inventory its identity and schema hash, assign an onboarding disposition, and create a governance design request when eligible. Do not automatically expose newly mirrored tables in the semantic model. Treat views through a separate materialization, pipeline, or semantic-definition path.

### Later extension: SQL-controlled approvals

Only after the native workflow and source-onboarding mechanics are proven, add SQL-controlled KPI, verified-answer, CDE, agent-grounding, semantic-metadata, and label-policy approvals.

## Native Purview Workflow Scope

Microsoft Purview Unified Catalog currently supports workflows for:

- Data product publication.
- Glossary term publication.
- Data product access requests.

Purview is the approval authority for these operations.

Purview workflows do **not** provide a generic approval mechanism for:

- KPI certification or KPI formula changes.
- Verified-answer certification.
- Data Agent instruction changes.
- Semantic-model description, annotation, or measure changes.
- CDE classification changes.
- Sensitivity-label policy changes.
- Arbitrary metadata changes.

Do not pretend that Purview approves unsupported change types.

## Authority Matrix

Define the authority matrix now, but implement only the selected Purview-native publication type in the first milestone. Do not hard-code authority decisions throughout notebooks.

| Change type | Approval authority | Canonical approval evidence | Downstream action |
|---|---|---|---|
| `DATA_PRODUCT_PUBLISH` | Purview | Purview workflow request and published object read-back | Replicate approved snapshot to SQL, mirror to Fabric, reconcile catalog/runtime bindings |
| `GLOSSARY_TERM_PUBLISH` | Purview | Purview workflow request and published term read-back | Replicate approved snapshot to SQL, mirror to Fabric, refresh semantic/runtime term bindings |
| `DATA_PRODUCT_ACCESS` | Purview | Purview access request/subscription outcome | Replicate access decision to SQL audit/event table; don't mutate semantic calculations |
| `KPI_APPROVAL` | SQL | SQL request, approver, payload, version, and timestamps | Mirror to Fabric; update KPI metadata and semantic-model grounding |
| `VERIFIED_ANSWER_CERTIFICATION` | SQL | SQL request, approver, payload, version, and timestamps | Mirror to Fabric; update AI metadata and Data Agent/semantic answer surfaces |
| `CDE_CLASSIFICATION` | SQL | SQL request, approver, payload, version, and timestamps | Mirror to Fabric; update CDE state and publish to Purview |
| `AGENT_GROUNDING_CHANGE` | SQL | SQL request, approver, payload, version, and timestamps | Mirror to Fabric; update Data Agent draft configuration, test, then publish |
| `SEMANTIC_METADATA_CHANGE` | SQL | SQL request, approver, payload, version, and timestamps | Mirror to Fabric; update model descriptions, annotations, or governed settings |
| `LABEL_POLICY_CHANGE` | SQL unless a supported Purview approval workflow is verified | SQL request plus Purview publication/read-back receipt | Apply through authorized Purview/Information Protection process and record result |

Create the matrix as data, for example:

```sql
dbo.governance_change_authority
```

Minimum fields:

- `request_type`
- `authority_system` (`PURVIEW` or `SQL`)
- `is_enabled`
- `requires_mirror_confirmation`
- `requires_semantic_publish`
- `requires_agent_publish`
- `requires_purview_publish`
- `requires_validation`
- `effective_from`
- `effective_to`

## Target Circular Architecture

### Path A: Purview-controlled changes

```text
Draft data product or glossary term in Purview
    -> Purview domain-scoped publication workflow
    -> Named approver approves or rejects
    -> Purview publishes or retains Draft state
    -> Fabric sync process reads the Purview object and workflow outcome
    -> Approved snapshot is written to SQL governance tables
    -> SQL row is mirrored into Fabric
    -> Fabric reconciles semantic-model/Data Agent bindings as required
    -> Validation confirms runtime and Purview state
    -> Publication receipts and validation results return to SQL
```

Purview workflows currently don't provide external connectors for directly invoking this repository's notebooks. Implement a polling/read-back bridge rather than inventing a webhook.

Create a new notebook, unless equivalent functionality already exists:

```text
fabric/nb_12_purview_workflow_sync.Notebook/
```

Responsibilities:

1. Read Purview publication/access workflow outcomes through supported interfaces.
2. Read back the resulting published Purview object or access decision.
3. Normalize the result into the SQL governance-event contract.
4. Use idempotent upsert logic.
5. Record the Purview object ID, workflow/request ID where available, governance domain, status, version/hash, approvers, and timestamps.
6. Avoid creating a loop when the SQL replica is mirrored back into Fabric.

### Path B: SQL-controlled changes

```text
Submit SQL governance request
    -> PendingApproval
    -> Named SQL-side approver approves or rejects
    -> Approved event remains authoritative in Azure SQL
    -> Fabric Mirroring carries request/version/payload into OneLake
    -> Mirror confirmation gate verifies request ID, version, and payload hash
    -> Apply notebook dispatches the approved change
    -> Semantic model / Data Agent / Purview are refreshed as required
    -> Runtime and catalog validation run
    -> Publication receipts return to SQL
    -> Request becomes Completed
```

The mirror must be part of the demonstrated propagation path. Do not immediately apply from a stale or unverified Fabric copy.

Also do not apply an event merely because its status is `Approved`. Require confirmation that Fabric has received the exact approved version and payload hash.

## Unified Governance Event Contract

Extend or replace the existing `dbo.governance_change_requests` schema without losing existing data.

Required fields:

- `request_id`
- `correlation_id`
- `request_type`
- `authority_system`
- `origin_system`
- `domain_id`
- `target_object_id`
- `target_object_label`
- `change_summary`
- `proposed_payload`
- `previous_payload`
- `payload_hash`
- `version`
- `requested_by_upn`
- `requested_at`
- `status`
- `approver_upn`
- `approved_at`
- `rejection_reason`
- `purview_workflow_id`
- `purview_object_id`
- `mirror_confirmed_at`
- `applied_at`
- `completed_at`
- `last_error`
- `rowversion` or another concurrency token

Use an explicit state machine:

```text
Draft
PendingApproval
Approved
Rejected
AwaitingMirror
MirrorConfirmed
Applying
Applied
Publishing
Validating
Completed
Failed
```

For Purview-controlled changes, the SQL event can enter at `Approved` or `Rejected` only after Purview outcome and object read-back are verified.

For SQL-controlled changes, the normal path begins at `Draft` or `PendingApproval`.

## Publication Receipt Model

Create:

```sql
dbo.governance_publication_receipts
```

Minimum fields:

- `receipt_id`
- `request_id`
- `target_system`
- `target_object_id`
- `target_version`
- `publication_status`
- `published_at`
- `validated_at`
- `evidence_location`
- `observed_hash`
- `error_message`

Expected target systems:

- `SQL_CANONICAL`
- `FABRIC_MIRROR`
- `LH_METADATA`
- `SEMANTIC_MODEL`
- `DATA_AGENT_DRAFT`
- `DATA_AGENT_PUBLISHED`
- `PURVIEW`
- `VALIDATION`

A governance request reaches `Completed` only when every required target in the authority matrix has a successful, validated receipt.

## SQL Approval Interface

**Later extension only:** Do not build this interface as part of the first Purview-native publication milestone or the source-discovery milestone.

The current demonstration depends on direct SQL updates. Replace ad hoc updates with controlled stored procedures:

```sql
dbo.sp_submit_governance_change
dbo.sp_approve_governance_change
dbo.sp_reject_governance_change
dbo.sp_record_mirror_confirmation
dbo.sp_record_publication_receipt
dbo.sp_complete_governance_change
```

Requirements:

- Validate allowed state transitions.
- Validate that the request type is SQL-controlled before SQL approval.
- Reject SQL approval attempts for Purview-controlled request types.
- Record the acting UPN and timestamp.
- Use optimistic concurrency.
- Recalculate and verify payload hashes.
- Make procedures idempotent where retries are expected.
- Surface errors explicitly.

Create SQL views for the demo:

```sql
dbo.vw_governance_pending_approvals
dbo.vw_governance_propagation_status
dbo.vw_governance_failed_changes
dbo.vw_governance_completed_changes
```

## Mirror Confirmation Gate

For the initial Purview-native scenario, confirm that the normalized SQL event and approved payload are observed through Mirroring before runtime reconciliation. The SQL-controlled approval checks below apply only to the later extension.

Extend `nb_07a_ingest_customer_files` or create a focused control notebook so Fabric can prove the approved SQL event arrived through Mirroring.

For each SQL-controlled event:

1. Read the mirrored request.
2. Match `request_id`.
3. Match `version`.
4. Recalculate and match `payload_hash`.
5. Confirm expected authority is `SQL`.
6. Confirm status is `Approved` or `AwaitingMirror`.
7. Write `mirror_confirmed_at` through the controlled SQL procedure.
8. Only then make the event eligible for application.

The notebook must distinguish:

- SQL approval timestamp.
- Mirror observation timestamp.
- Runtime apply timestamp.
- Publication timestamps.
- Validation timestamp.

## Refactor `nb_11_gated_governance_sync`

**Later extension only:** Keep the current notebook intact during the first native-gate milestone unless a small compatibility change is required by the shared event contract.

Update `nb_11` to become the common apply dispatcher.

It must:

1. Select only events in `MirrorConfirmed`.
2. Verify authority and required targets from `governance_change_authority`.
3. Transition the request to `Applying`.
4. Dispatch by `request_type`.
5. Apply idempotently.
6. Record target publication receipts.
7. Transition to `Applied` and then `Publishing`.
8. Never stamp `Completed` before downstream validation succeeds.
9. On failure, record `last_error`, a failed receipt, and `Failed` state.

Support at least:

- `KPI_APPROVAL`
- `VERIFIED_ANSWER_CERTIFICATION`
- `CDE_CLASSIFICATION`
- `GLOSSARY_TERM_PUBLISH`
- `DATA_PRODUCT_PUBLISH`
- `AGENT_GROUNDING_CHANGE`
- `SEMANTIC_METADATA_CHANGE`
- `LABEL_POLICY_CHANGE`

For Purview-controlled glossary or data-product events, treat the Purview object as already approved and published. The SQL/Fabric portion reconciles and propagates the approved snapshot; it must not reapprove it.

## Make SQL the Canonical Propagation Record

Approved governance snapshots must be queryable in SQL even when Purview was the approval authority.

Add or normalize:

```sql
dbo.governance_data_products
dbo.governance_glossary_terms
dbo.governance_cdes
dbo.governance_kpis
dbo.governance_verified_answers
dbo.governance_agent_grounding
dbo.governance_semantic_metadata
dbo.governance_label_policies
```

Each table should support:

- Stable business identifier.
- Version.
- Current flag.
- Effective dates.
- Status.
- Authority system.
- Origin system.
- Approved by and approved at.
- Definition/payload.
- Payload hash.
- Purview object ID where relevant.

Use append/version plus a current-state view where practical. Avoid destructive overwrites that erase approval history.

## Runtime Propagation

### Semantic model

Use the active Enercare pattern:

- SemPy for discovery/read-back.
- SemPy Labs with TOM/XMLA-backed connection for descriptions and annotations.
- Explicit DAX measures remain the calculation authority.
- TMDL remains the model-definition representation.

Record receipts for:

- Semantic write attempted.
- Semantic write succeeded.
- Runtime read-back matched expected version/hash.

### Fabric Data Agent

For `AGENT_GROUNDING_CHANGE`:

1. Update only the draft configuration.
2. Keep agent-level behavior in `stage_config.json`.
3. Keep source-specific behavior in `datasource.json`.
4. Use `fewshots.json` only for supported raw sources.
5. Run the validation prompt matrix.
6. Publish through the Fabric Data Agent lifecycle.
7. Confirm published configuration matches the approved draft.
8. Record separate draft, published, and validation receipts.

### Purview

For SQL-controlled items requiring Purview publication:

1. Generate or update the Purview object from the approved SQL snapshot.
2. Publish through supported Purview interfaces.
3. Read the object back from the tenant.
4. Compare identifier, version/hash, definition, ownership, and status.
5. Record the Purview receipt.

Do not count a locally generated payload as publication evidence.

## Prevent Circular Loops

Every event and governed snapshot must include:

- `authority_system`
- `origin_system`
- `correlation_id`
- `version`
- `payload_hash`

Rules:

- A Purview-originated event replicated into SQL must not be republished to Purview unless reconciliation detects a material difference.
- A SQL-originated event published to Purview must not return as a new Purview approval event.
- The same `correlation_id`, object ID, version, and payload hash must be idempotent.
- A higher version may create a new event.
- A conflicting payload with the same version must fail validation.

## Demo Scenarios

Select and implement one of the first two Purview publication scenarios for Phase 1. The other native scenario and all SQL scenarios are follow-up work and must not block Phase 1 closeout.

### Scenario 1: Purview term publication

Object:

```text
GT-SLA
```

Flow:

1. Create or revise the term as Draft in Purview.
2. Trigger the domain-scoped term publication workflow.
3. Ci Zhu approves in Purview.
4. Purview publishes the term.
5. `nb_12_purview_workflow_sync` reads the published term and approval outcome.
6. Approved snapshot is written to SQL.
7. Mirroring carries it into Fabric.
8. Semantic-model/Data Agent term context is reconciled.
9. Runtime and Purview read-back receipts are recorded.
10. Event becomes `Completed`.

### Alternative Scenario 2: Purview data-product publication

Object:

```text
DP-SVCPERF
```

Demonstrate Purview publication approval, SQL snapshot replication, mirror confirmation, binding reconciliation, and completed receipts.

### Later Scenario 3: SQL KPI approval

Object:

```text
SLA_BRCH_RATE
```

Demonstrate:

- Submit.
- Approve through stored procedure.
- Mirror confirmation.
- KPI metadata update.
- Semantic-model writeback.
- DAX/runtime validation.
- Purview reconciliation if required.
- Completed receipts.

### Later Scenario 4: SQL verified-answer certification

Question:

```text
What is the SLA for a no-heat call?
```

Demonstrate SQL approval, mirror confirmation, AI metadata update, Data Agent/semantic answer refresh, publish, prompt validation, and completed receipts.

### Later Scenario 5: SQL CDE classification

Object:

```text
CDE-COMPLAINTREF
```

Demonstrate SQL approval followed by mirrored propagation and Purview publication/read-back.

## Validation Requirements

For every scenario included in the active delivery phase, capture:

- Authority decision.
- Approval request ID.
- Approver.
- Approved timestamp.
- Version and payload hash.
- Mirror confirmation timestamp.
- Apply timestamp.
- Target receipts.
- Validation result.
- Final state.

Verify:

1. SQL cannot approve a Purview-controlled change type.
2. Purview-controlled changes aren't applied before Purview publication read-back.
3. SQL-controlled changes aren't applied before mirror confirmation.
4. Reprocessing the same event is idempotent.
5. Conflicting payloads with the same version fail.
6. A failed target prevents `Completed`.
7. Runtime and Purview states match the approved payload.
8. The Maria operational and analytical prompt set still passes.

## Documentation

Update:

- `docs/Enercare-Demo-SemPy-Design-Guide.md`
- `docs/design-gap-analysis.md`
- The Phase 4 workflow runbook.
- The architecture guide if it describes the old single SQL-only approval model.

Document clearly:

- Which changes Purview approves.
- Which changes SQL approves.
- How Purview outcomes are replicated into SQL.
- How SQL outcomes propagate through Mirroring.
- How loops are prevented.
- Which target receipts are required for completion.
- Which parts require manual Purview workflow configuration.
- Current Purview workflow limitations, including lack of external connectors.

## Safety and Implementation Rules

- Preserve existing live data.
- Use additive migrations where possible.
- Make every operation idempotent and retry-safe.
- Keep `DEMO_MODE=True` as the safe default for mutation notebooks.
- Never silently convert an unsupported Purview approval into an SQL approval.
- Never mark an event completed without read-back validation.
- Do not rely on prompt text as a security or approval boundary.
- Use source permissions, stored procedures, Purview roles, and Fabric permissions for enforcement.
- Reuse existing authentication, SQL connectivity, SemPy, SemPy Labs, Purview, and validation helpers.
- Do not create undocumented Purview APIs or workflow webhooks.

## Deliverables

Return these first-milestone deliverables:

1. Authority matrix.
2. Additive SQL schema for requests, append-only events, object versions, target receipts, source/semantic inventories, and object mappings.
3. Controlled SQL write procedures required by the Purview bridge and receipt closeout, without the later SQL approval interface.
4. Purview workflow setup instructions for the selected publication type.
5. Purview polling/read-back synchronization logic.
6. Semantic reconciliation and object-level read-back for the selected scenario.
7. Publication receipt and loop-prevention implementation.
8. Source-discovery design and, after the native loop closes, one governed onboarding proof.
9. Updated documentation and runbook.
10. Validation evidence for the selected native scenario only.
11. Remaining limitations and the explicit backlog for additional native and SQL-controlled scenarios.

Later-phase deliverables include the SQL approval procedures, `nb_11` refactor, KPI/verified-answer/CDE scenarios, operational scheduling, and Advanced DAX evaluation. They must not block the first native-gate closeout.

The completed demonstration must show a genuinely circular process:

```text
Approve in the correct authority
    -> normalize the approved event in SQL
    -> propagate through Mirroring
    -> apply to Fabric runtime surfaces
    -> publish or reconcile Purview
    -> validate every target
    -> return receipts to SQL
    -> complete the governance event
```
