# SQL Metadata Governance Standard

## Purpose

This repo now treats metadata management as a governed lifecycle, not a notebook side effect.
The central tenant is simple:

- the customer owns metadata at the SQL object level
- the SQL definition is the source of truth for metadata expression
- metadata is discovered through SQL-native extraction and captured in the governance ledger
- stewardship, lineage, and evidence are required before anything reaches the semantic model or Purview
- the semantic model and catalog are downstream consumers of approved metadata, not an alternative source of truth

This is the standard the demo should enforce across all governance scenarios.

---

## Metadata contract

Any managed SQL object requiring metadata governance must carry a standard, structured metadata header in its definition.

Example pattern:

```sql
/*
@tag: domain=DOM-SVCDEL
      owner=shruthi.srinivas@enercare.ca
      sensitivity=Internal
      semantic_role=CandidateFact
      business_use=Daily field-ops technician utilization and workload distribution
*/
```

Required fields for core managed objects:

- domain
- owner
- sensitivity
- semantic_role
- business_use

Optional governance fields:

- steward
- data_product
- cde
- source_system
- retention_policy
- quality_rule
- approved_by
- effective_date

The contract applies to views and procedures that are candidates for governance, lineage, semantic-model inclusion, or steward review.

---

## Governance lifecycle

The metadata lifecycle is:

1. Author in SQL
2. Detect in SQL through native extraction
3. Create a request in the governance ledger
4. Route to stewardship review
5. Approve or reject
6. Apply only approved metadata to the semantic model / lakehouse
7. Validate lineage and evidence
8. Publish or expose as governed metadata only after approval

The canonical state model remains:

Draft -> Submitted -> PendingApproval -> Approved -> Applying -> Validated -> Completed

With terminal outcomes:

- Rejected
- Failed
- Superseded

No unreviewed metadata should reach the semantic model or downstream governance surfaces.

---

## Required approval workflow

### 1) Source discovery

The SQL DDL trigger performs detection when a managed view or procedure is created or altered.

The extraction proc reads the object definition from sys.sql_modules and converts it to a governance request.

The request should be recorded as:

- request_type = SourceTagAnnotationDetected
- event_type = SOURCE_TAG_DETECTED
- target_system = SQL
- target_object_type = SqlModuleTagAnnotation
- current_status = Submitted

This ensures the source metadata becomes a traceable, reviewable governance item before it is trusted.

### 2) Steward review

The backlog is surfaced as a pending list for stewardship review.
The notebook layer should not be the origin of truth; it only reads the current governance state and makes it visible.

The steward then decides whether the metadata is:

- approved for semantic inclusion
- rejected as unsafe or ungoverned
- deferred while additional lineage or ownership data is gathered

### 3) Apply and validate

Only when a row is Approved should metadata be applied to:

- the lakehouse working metadata store
- the semantic model annotations
- downstream Purview publication surfaces

Validation must confirm:

- the object still exists
- the lineage is consistent
- the target metadata matches the approved payload hash
- the publish/read-back is successful

### 4) Evidence and lineage

Every approved metadata event should leave a durable evidence trail in SQL:

- request_id
- author and approver identity
- timestamp
- payload hash
- target object identity
- validation receipt
- publication readback

This provides the traceability required for stewardship review and business audit.

---

## Standardized notebook responsibilities

The repo should treat notebooks as execution stages, not as the governance source of truth.

The correct responsibility split is:

- SQL: metadata authoring + discovery + approval state + evidence ledger
- Lakehouse: staging and working metadata propagation
- Semantic model: runtime business metadata surface
- Purview: downstream catalog and governance publication
- Notebooks: orchestration, reconciliation, and validation

Important principle:

Notebooks may read and write metadata, but they should never create an alternative metadata authority separate from SQL/ledger-backed governance.

---

## 10-stage target architecture

The demo should be organized around governance stages rather than implementation detail.
The target notebook grouping is:

1. Environment and source baseline
2. Source publish to SQL and mirror validation
3. Source inventory and metadata discovery
4. Governance request backlog and stewardship intake
5. Curated metadata staging in lh_metadata
6. Semantic model metadata apply
7. AI grounding and verified-answer propagation
8. Purview publication of domains, products, glossary, and CDEs
9. Lineage, labels, and stewardship validation
10. Governance closeout and audit proof

This is the conceptual model the repo should move toward. The actual notebook files may remain grouped by current implementation until a deliberate consolidation pass is executed.

---

## Central tenant for the demo

The demo narrative should be framed as:

> Metadata is managed in SQL, validated by governance, applied through approved lifecycle steps, and then consumed by Fabric and Purview as the controlled business truth.

This should be the central story of the demo, not a side capability.

The narrative layers are:

- stewardship: the human decision-maker and owner
- lineage: the evidence chain from SQL object to data product to semantic model
- governance: the approval and certification gate
- runtime consumption: Data Agent, report, and semantic metadata surfaces

This unifies the architecture and gives the demo a single coherent story.

---

## Repo adoption guidance

To adopt this standard in practice:

- keep SQL authoring as the canonical metadata input surface
- preserve the ledger-driven approval model and approval receipts
- preserve the source-tag detection model in the SQL layer
- make stewardship explicit in the workflow and documentation
- ensure Purview and semantic-model updates are downstream of approved requests only
- reduce notebook duplication by grouping around lifecycle phases rather than per-tool output

This standardization does not remove the need for notebooks; it makes them clearly operational plumbing for a governance-first metadata lifecycle.
