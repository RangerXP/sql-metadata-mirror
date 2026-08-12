# P1/P2 Native Closed-Loop Walkthrough — Ci Zhu (`GT-SLA`)

**Scenario:** Native Purview Term Publish, followed by semantic-model reconciliation
**Governance domain:** Service Delivery
**Requester:** Victoria Tan (Domain Owner, Customer Operations; submits the revised term definition)
**Approver:** Ci Zhu (Governance Domain Creator/tenant Data Governance Administrator; secondary
Governance Domain Owner on Service Delivery)
**Control boundary:** Purview approves publication. Azure SQL stores normalized evidence. Fabric
does not approve the request. Unlike the P3 access scenario, this one **does** mutate governed
content — the approved term definition is reconciled into the semantic model.

## Status

✅ **Fully proven end-to-end and closed** (`docs/build-scorecard.md` G15-1/2/3). This is the first
scenario in the native workflow phase and the template the P3/P4 scenarios extend from.

## 1. Prerequisites (all confirmed live)

1. Native Purview workflow configured: **Workflow category = Catalog curation**, **Workflow type =
   Term publish**, scoped to the Service Delivery governance domain, approver assigned to a real
   person who is not the requester.
2. Bridge notebook `nb_12_purview_workflow_sync` built and dry-run validated (`DEMO_MODE=True`)
   before any live event.
3. Reconciliation notebook `nb_13_semantic_reconcile` built for the semantic-model side of the loop.

## 2. Live request evidence

| Field | Value |
|---|---|
| Term | `Service Level Agreement` (`GT-SLA`, `b3b54277-3b36-47d8-831c-a2b9a5f02634`) |
| Domain | Service Delivery (`9d82a6da-eed1-4dae-a036-84c1dcc65337`) |
| Published description | "The contracted or policy-defined response and resolution targets per service-request priority and service zone. Targets are governed by the Service Delivery domain and require approval before publication." |
| Governance request ID | `PV-GT-SLA-0359C207890E4EB1B8AB` |
| Publication content hash | `7bbd4fa674b042d407af51b8ced5ebd0ed24f9a8f6b54c9107d1f31394c5b40a` |
| Semantic read-back hash | `e699c7842d8009828a21e17962224e3ee92989029bfea34d35c3d1081987dede` |
| `PublicationReadback` | Passed (hash match) |
| `SemanticModelReadback` | Passed (hash match) |
| Completed at | `2026-08-11 23:10:02.516876` UTC |
| Semantic objects updated | `_Measures[SLA Breach Count]`, `_Measures[SLA Compliance Rate]`, `fct_service_request[IsSlaBreachFlag]` |

## 3. Customer walkthrough narrative

> "The Service Level Agreement term defines how Enercare measures and reports on-time service
> delivery — it's referenced by real KPIs like SLA Breach Count and SLA Compliance Rate in the
> semantic model. When Victoria Tan needs to revise its definition, she doesn't email IT or edit a
> spreadsheet of business definitions — she edits the term directly in Unified Catalog and submits
> it for publication.
>
> Ci Zhu, who holds tenant-wide governance authority, reviews and approves the revision through
> Purview's native approval workflow — the same 'Requests and approvals' experience you just saw
> Victoria use for Customer 360's access request.
>
> But this scenario goes one step further: once approved, the new definition doesn't just sit in
> the catalog — it's automatically reconciled into the actual Power BI semantic model. The SLA
> Breach Count measure, the SLA Compliance Rate measure, and the underlying `IsSlaBreachFlag`
> column all get the governed description and lineage annotations applied, and the system reads
> the semantic model back to prove the definitions actually landed correctly — not just that an API
> call returned success. Only then is the request marked Completed."

## 4. Real build gotchas worth knowing (technical audience)

- Fabric NotebookUtils doesn't support a Purview token audience — `nb_12`/`nb_13` use interactive
  `DeviceCodeCredential` for Purview specifically, separate from the Fabric-native SQL auth path.
- TOM's `Annotations.Add(name, value)` has no matching overload for two plain strings — creating a
  brand-new annotation (not updating an existing one) requires constructing a real
  `Microsoft.AnalysisServices.Tabular.Annotation` object first.
- The publication content hash intentionally excludes the `status` field, so re-publishing an
  otherwise-identical term doesn't spuriously fail hash comparison due to a lifecycle-state change.

## 5. Relationship to P3/P4

This scenario is the template the P3 (`docs/runbooks/p3-native-dataproduct-access.md`) and planned
P4 scenarios extend — see `docs/purview-native-workflow-wireframe.md` for the full stakeholder
coverage plan and sequencing.

