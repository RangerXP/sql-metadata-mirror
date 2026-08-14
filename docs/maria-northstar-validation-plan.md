# Maria North Star Validation Plan

## Purpose

This plan treats the demo as a governed semantic lifecycle proof, not a notebook-execution smoke test.

The success condition is:

> A single governed definition can be authored, approved, published, consumed by Maria, reviewed by Victoria, and audited by Ci Zhu with complete lineage and governance evidence.

This aligns with the repo's North Star scenario in `docs/purview-maria-north-star-scenario.md` and the validation status model in `docs/Enercare-Demo-SemPy-Design-Guide.md`.

---

## Core Principle

The repo already makes the right distinction:

- Platform execution success is necessary but not sufficient.
- The business proof is whether a definition can travel from source metadata to semantic model to Data Agent / Copilot and then be explained in Purview with lineage and certification evidence.

In other words, the plan is designed to validate the chain:

Maria (call center) -> Victoria (business reviewer) -> Ci Zhu (auditor / governance reviewer)

---

## Validation Lens

The validation should focus on the following authoritative business object:

- KPI or measure: "Customer Retention Rate" / "Customer Lifetime Value" / equivalent approved metric used in the demo
- Authority: semantic model definition + glossary term + certification metadata
- Evidence: source SQL, mirrored metadata, Lakehouse/semantic model, report, Purview lineage, Data Agent answer

The proof is complete only when the same approved definition is visible across all layers and can be read back with evidence.

---

## M0. Environment Validation

### Goal

Confirm the runtime environment is correctly provisioned and the expected platform assets exist before governance validation begins.

### Evidence to collect

- Fabric workspace exists and contains expected items
- Lakehouse(s) exist and are populated
- Semantic model is present and accessible
- Mirror database is present for the authoritative source
- Purview or Unified Catalog connection and access exist
- Notebook execution state and artifact outputs are available

### Target artifacts

- `fabric/`
- `lh_enercare_demo.Lakehouse/`
- `lh_metadata.Lakehouse/`
- `BrookfieldEnercare.SemanticModel/`
- `sqldemo.MirroredDatabase/`
- `purview/`

### Pass criteria

- All required demo assets exist.
- Notebook run outputs are present.
- Base environment is stable enough to run business proof tests.

### Validation notebooks

- `nb_01_setup_demo_environment.Notebook/`
- `nb_03_pbi_star_schema.Notebook/`
- `nb_04_sempy_writeback.Notebook/`
- `nb_05a_publish_synthetic_data_to_sql.Notebook/`
- `nb_07_publish_to_purview.Notebook/`
- `nb_08_purview_glossary_cde.Notebook/`
- `nb_09_purview_labels_lineage.Notebook/`
- `nb_10_purview_stewardship_ai.Notebook/`
- `nb_11_gated_governance_sync.Notebook/`

---

## M1. Source Data Validation

### Goal

Prove the authoritative source layer contains the records behind the Maria scenario and the intended KPI logic.

### Test objects

- Maria customer record
- Service account and premise data
- Equipment registry
- Contract billing data
- Service request / SLA breach records
- Complaint and audit records

### Evidence to collect

- Source SQL query output for Maria customer row
- Service request / billing / equipment evidence
- Expected row counts for the seeded dataset
- Confirmation that Maria's record is present in the source authoritative tables

### Pass criteria

- Maria's data exists in the source system.
- The data can be traced to the same customer identity used downstream.
- The billing and service issue used in the scenario are represented in the authoritative tables.

### Example validation checks

- `customer_id` / `account_id` consistency across source tables
- service request linked to the appropriate service account and equipment
- billing transaction for the monthly charge and any credit entry
- SLA breach logic is represented in the seeded dataset

---

## M2. Metadata Validation

### Goal

Confirm that business meaning is authored, stored, and discoverable as governed metadata before it reaches runtime AI surfaces.

### Test object

An example KPI or governed term such as:

- Customer Retention Rate
- Customer Lifetime Value
- Net Revenue
- GT-SLA / GT-CONSENT / GT-CONTRACT

### Validate the metadata chain

| Layer | Expected result |
|---|---|
| SQL metadata | definition exists and is known to the source data model |
| Metadata Lakehouse | definition exists in the staging / governance metadata tables |
| Semantic model | description populated and traceable |
| Fabric Data Agent | returns governed definition |
| Copilot / AI surface | returns the same governed definition |
| Purview catalog | glossary term / classification exists |

### Evidence to collect

- Metadata inventory outputs
- Semantic model description values
- Data Agent output for the term or KPI
- Copilot answer for the same item
- Purview glossary entry / term record

### Pass criteria

- The same definition resolves at each layer without mismatch.
- AI output reflects governed metadata rather than a free-form or stale definition.
- Metadata is not only present, but operationally consistent across runtime surfaces.

---

## M3. Semantic Model Validation

### Goal

Prove the semantic model is the source-of-truth business layer used by both the report and the AI-facing semantic surfaces.

### Evidence to collect

- semantic model measure definitions
- description / annotation values
- lineage to Lakehouse or mirrored SQL tables
- report-level consumption of the same measure
- model metadata exported from Fabric or read back via SemPy

### Pass criteria

- Measures are present and match the expected business definitions.
- A selected KPI can be read in the semantic model and appears in the same form in the report.
- The business logic is consistent and not duplicated manually across multiple surfaces.

### Key repo references

- `docs/semantic-model-annotations.md`
- `docs/purview-maria-north-star-scenario.md`
- `fabric/BrookfieldEnercare.SemanticModel/`

---

## M4. AI Grounding Validation

### Goal

Demonstrate that the AI layer is grounded in approved, governed metadata rather than general model knowledge.

### Primary scenario

Maria asks:

> "What is Customer Lifetime Value?"

### Expected outcome

- Data Agent returns the approved definition
- Definition is sourced from governed metadata
- Certification / ownership metadata is present in the answer or answer path
- The model does not invent or drift from the approved business definition

### Evidence to collect

- question and response transcript
- JSON / structured response payload
- semantic model annotation or metadata record used to answer
- certificate / version / approval status associated with the term

### Pass criteria

- The response is exact or materially equivalent to the approved metadata definition.
- The output references the governing definition, not a loose paraphrase.
- The answer is explainable to an auditor.

### Repo evidence basis

- `docs/runbooks/phase3-step3-runtime-smoke-log.md`
- `docs/semantic-model-annotations.md`
- `docs/runbooks/maria-northstar-answer-key.md`

---

## M5. Governance Validation

### Goal

Prove the certification and approval flow controls publication behavior.

### Governance conditions to test

For each object and KPI:

- `IsDraft`
- `IsCertified`
- `CertifiedBy`
- `CertificationDate`

### Test cases

| Test case | Expected result |
|---|---|
| Uncertified KPI | not published |
| Draft KPI | not published |
| Certified KPI | published |
| Certification revoked | removed from runtime |

### Required validation

- Business owner update to a KPI definition
- Draft state set and applied
- Governance notebook executed
- Approval / certification step completed
- Publication propagated downstream
- Runtime surfaces refreshed

### Expected outputs

- Old definition disappears
- New definition appears in semantic model and AI output
- Purview governance object reflects the approved state

### Pass criteria

- Approval gates block unapproved metadata.
- Publication only occurs for certified objects.
- Runtime surfaces reflect the most recent approved state.

---

## M6. Lineage Validation

### Goal

Close the largest remaining gap: prove the chain from source to report and governance object.

### Lineage path to validate

Azure SQL -> Mirror -> Lakehouse -> Semantic Model -> Report -> Purview lineage

### Asset example

- Customer Retention KPI
- Net Revenue KPI
- Contract amount / billing metric

### Evidence to collect

- screenshot or read-back from source table
- mirrored table in Fabric
- Lakehouse table / semantic model measure
- report visual or semantic measure consumption
- Purview lineage view showing the full chain

### Pass criteria

- Each hop is visible and readable.
- The source object and downstream semantic/report object can be related.
- Purview read-back proves the path to the asset and not just a local notebook artifact.

### This is the key gap the repo already identifies

`docs/Enercare-Demo-SemPy-Design-Guide.md` explicitly calls out that the SQL -> OneLake -> semantic model -> report lineage remains a gap if not proven via fresh read-back.

---

## M7. Audit Validation (Ci Zhu Scenario)

### Goal

Validate the North Star proof for the auditor persona.

### Scenario

Ci Zhu asks:

> "Show me why Maria received that answer."

### System must produce

1. KPI definition
2. certification authority
3. approval date
4. data owner
5. lineage path
6. Purview object
7. source semantic model

### Evidence to collect

- exact KPI definition returned to Maria
- owner / approver metadata
- certification status and date
- lineage read-back view
- data product or glossary object in Purview
- semantic model annotation / measure source

### Pass criteria

- The answer is explainable end-to-end.
- The auditor can connect the business answer to the certification record and lineage trail.
- The model demonstrates governance, explainability, auditability, and responsible AI, not just a helpful chatbot response.

---

## Final Result Matrix

| Persona | Validation bar | Result |
|---|---|---|
| Maria | receives the right governed answer from the Data Agent | Maria ✅ |
| Victoria | sees the same approved KPI in review context with governed flow | Victoria ✅ |
| Ci Zhu | can explain provenance, approval, and lineage for the metric | Ci Zhu ✅ |

---

## Recommended Execution Order

1. M0 environment validation
2. M1 source data validation
3. M2 metadata validation
4. M3 semantic model validation
5. M4 AI grounding validation
6. M5 governance validation
7. M6 lineage validation
8. M7 audit validation

This order ensures the proof chain is established in the same sequence the business uses it: source -> model -> metadata -> governance -> AI answer -> audit evidence.

---

## Evidence Standard

A validation step is only considered passed when the evidence is read back from the live platform or repo-backed authoritative output, not merely inferred from notebook cells or dry-run logs.

This plan explicitly distinguishes between:

- dry-run / notebook-generated validation
- demo-validating runtime evidence
- live authoritative read-back evidence required for final governance proof

---

## Conclusion

The repo is not missing a notebook validation plan. It already contains the necessary model, story, and governance primitives.

What is missing is a single proof-chain validation artifact that tests the full governance lifecycle across Maria, Victoria, and Ci Zhu.

This plan closes that gap by making the success condition:

> the same governed definition can be authored, approved, published, consumed, and audited with lineage evidence.

That is the clearest expression of the Enercare North Star.
