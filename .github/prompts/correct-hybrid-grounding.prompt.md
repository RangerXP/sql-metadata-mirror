---
description: Correct the Fabric-native hybrid grounding architecture
mode: agent
---

# Implement Fabric-Native Hybrid Grounding for Enercare

Work in:

`C:\Users\seankelley\OneDrive - Microsoft\Documents\Demos\sql-metadata-mirror`

## Purpose

Use GitHub Copilot only to inspect and modify the repository.

The completed grounding architecture must execute from **Fabric-native artifacts**, not from this prompt, `.github` instructions, or a custom `.copilot` directory.

Git provides version control and deployment lifecycle. It is not the runtime grounding layer.

## Target Fabric Architecture

Implement three distinct grounding layers:

```text
Fabric Data Agent
    stage_config.json
    Agent-level pre-query grounding
            |
            v
Fabric Data Source Binding
    datasource.json
    fewshots.json where supported
    Source-specific retrieval grounding
            |
            v
Selected Query Runtime
    Semantic model, Lakehouse, Warehouse, KQL, or Ontology
    Analytical or source-native grounding
```

Published governance remains external to query execution:

```text
Purview
    Definitions, ownership, CDEs,
    classifications, policies, and lineage
```

## Authoritative Placement Rules

| Concern | Fabric-native destination |
|---|---|
| Agent persona and supported scope | Data Agent `stage_config.json` |
| Source routing | Data Agent `stage_config.json` |
| Request-ID-first workflow | Data Agent `stage_config.json` |
| Account and identifier normalization | Data Agent `stage_config.json` |
| Cross-source lookup sequence | Data Agent `stage_config.json` |
| Required response structure | Data Agent `stage_config.json` |
| Missing-evidence and non-fabrication rules | Data Agent `stage_config.json` |
| Source-specific interpretation | Source `datasource.json` |
| Source schema and table selection | Source `datasource.json` |
| Source-specific identifiers and joins | Source `datasource.json` |
| SQL or KQL question/query examples | Source `fewshots.json`, where supported |
| KPI formulas and certified measures | Semantic model |
| Relationships and analytical behavior | Semantic model |
| Aggregation and date behavior | Semantic model |
| Business terminology needed for DAX | Semantic-model descriptions and AI instructions |
| Approved analytical question patterns | Semantic-model verified answers |
| Domains, glossary, CDEs, and ownership | Purview and governance metadata |
| Classification, sensitivity, and lineage | Purview and governance metadata |
| Business proposal and approval history | Governance tables and `nb_11` |
| Repository-development guidance | `.github` only; never runtime grounding |

## Files to Inspect

### Fabric Data Agent

Locate the active `*.DataAgent` item and inspect:

```text
Files/Config/data_agent.json
Files/Config/publish_info.json
Files/Config/draft/stage_config.json
Files/Config/published/stage_config.json
Files/Config/draft/<data-source-folder>/datasource.json
Files/Config/published/<data-source-folder>/datasource.json
Files/Config/draft/<data-source-folder>/fewshots.json
Files/Config/published/<data-source-folder>/fewshots.json
```

The current semantic-model source is expected under:

```text
semantic-model-BrookfieldEnercare/
```

Also determine whether direct Lakehouse, Warehouse, KQL, mirrored-database, or ontology bindings already exist.

### Semantic Model

Inspect:

```text
fabric/BrookfieldEnercare.SemanticModel/definition/model.tmdl
fabric/BrookfieldEnercare.SemanticModel/definition/tables/*.tmdl
```

### Metadata Publication Notebooks

Inspect:

```text
fabric/nb_04_sempy_writeback.Notebook/notebook-content.py
fabric/nb_05_push_qa_verified_answers.Notebook/notebook-content.py
fabric/nb_07b_merge_customer_metadata.Notebook/notebook-content.py
fabric/nb_11_gated_governance_sync.Notebook/notebook-content.py
```

### Governance Inputs

Inspect the relevant:

```text
lh_metadata metadata tables
purview/*.csv
sql/*governance*.sql
docs/semantic-model-annotations.md
docs/design-gap-analysis.md
```

## Phase 1: Inventory Existing Grounding

Extract every grounding rule from:

1. Data Agent `aiInstructions`.
2. Each `dataSourceInstructions` value.
3. Each `fewshots.json`.
4. Semantic-model descriptions and annotations.
5. Verified-answer generation logic.
6. Governance metadata that supplies runtime definitions.

Produce an inventory with:

| Rule | Current location | Correct Fabric location | Action |
|---|---|---|---|
| Example rule | Current file/property | Target file/property | Retain, move, split, consolidate, or remove |

Pay special attention to duplication involving:

- No-heat SLA wording.
- Certified KPI targets.
- Default analytical windows.
- Request-ID-first retrieval.
- Account-key normalization.
- Customer lookup order.
- Service-history fallback.
- Support-call-history fallback.
- Required response fields.
- Missing-data behavior.
- Non-fabrication constraints.

## Phase 2: Correct Agent-Level Grounding

Refactor the draft `stage_config.json` so `aiInstructions` contains only behavior that applies to the Data Agent interaction:

- Purpose and supported domain.
- Global source-routing rules.
- Operational-versus-analytical intent classification.
- Request-ID-first retrieval.
- Account and service-account normalization.
- Cross-source retrieval order.
- Service-restoration-before-credit workflow.
- Escalation rules.
- Required response structure.
- Missing-evidence disclosure.
- Non-fabrication rules.
- General response style.

Do not retain detailed DAX formulas, measure definitions, relationship instructions, or duplicated KPI specifications here.

## Phase 3: Correct Source-Specific Grounding

For each Data Agent source folder:

### `datasource.json`

Keep:

- Source-specific purpose.
- Selected tables.
- Source-specific identifiers.
- Physical relationships not represented by a semantic layer.
- Source freshness or coverage limitations.
- Guidance unique to this binding.

Do not duplicate:

- Global agent workflow.
- Response-format requirements.
- Semantic-model KPI formulas.
- Generic safety rules already owned by `stage_config.json`.

### `fewshots.json`

For Lakehouse, Warehouse, KQL, or other supported sources, add representative examples only where they improve query generation.

Each example must contain:

- A realistic natural-language question.
- The correct SQL or KQL query.
- Approved joins.
- Expected filters.
- Correct aggregation behavior.

Do not create `fewshots.json` for a semantic-model source if Fabric does not support it.

## Phase 4: Correct Analytical Semantic Grounding

The `BrookfieldEnercare` semantic model must own:

- Explicit certified DAX measures.
- KPI formula definitions.
- Numerator and denominator meaning.
- Target, warning, and critical thresholds where analytically relevant.
- Default calculation windows.
- Date behavior.
- Aggregation behavior.
- Analytical relationships.
- Business-friendly object descriptions.
- Terminology and synonyms required during DAX generation.
- Verified analytical answers.

Remove operational workflow content such as:

- Request-ID-first retrieval.
- Customer-service escalation sequence.
- Required call-triage response fields.
- Operational source-selection logic.

Preserve unrelated TMDL, partitions, lineage tags, relationships, and model metadata.

## Phase 5: Preserve Governance Authority

Do not move governance responsibilities into agent prompts.

Continue to source the following from governance metadata and Purview publication:

- Domains.
- Owners and stewards.
- Glossary terms.
- CDEs.
- Data products.
- Classifications and sensitivity.
- Policy references.
- Lineage.
- Certification and approval evidence.

`nb_11_gated_governance_sync` remains the apply-after-approval mechanism for:

- `KPI_APPROVAL`.
- `VERIFIED_ANSWER_CERTIFICATION`.
- `CDE_CLASSIFICATION`.
- `GLOSSARY_TERM_DEFINITION`.

The corrected runtime artifacts must continue to be generated from approved metadata.

## Phase 6: Draft and Published Lifecycle

Make authoring changes only in the Data Agent `draft` configuration.

Do not hand-edit the `published` configuration as the source of truth.

After testing:

1. Publish the Data Agent through the supported Fabric lifecycle.
2. Confirm the resulting `published` configuration reflects the approved draft.
3. Verify draft and published behavior are synchronized.
4. Commit the resulting Fabric item definitions through Fabric Git integration.

## Required Behavior

Preserve the Maria north-star behaviors:

- Resolve `EC18374622`, `EC18374622-SVC`, customer ID, and service-account variants.
- Resolve request `2026051142` by request ID before name matching.
- Retrieve customer, account, equipment, service request, contract, billing, complaint, and support-history context.
- Do not fabricate technician, dispatch, billing, credit, or status values.
- Return only unresolved fields as unavailable.
- Use certified semantic measures for FCR, CSAT, AHT, PP renewal, and SLA analytics.
- Preserve governed no-heat SLA behavior.
- Keep governance-only requests separate from operational service requests.

## Validation Matrix

Test and record:

| Prompt class | Example | Expected grounding layer |
|---|---|---|
| Operational request | `Show request 2026051142` | Agent plus source grounding |
| Customer triage | `Show the current status and history for Maria Castellanos` | Agent plus source grounding |
| Certified KPI | `What is our FCR?` | Semantic grounding |
| Analytical SLA | `What was the SLA breach rate over the last 12 months?` | Semantic grounding |
| Direct SLA policy | `What is the SLA for a no-heat call?` | Approved semantic/runtime answer |
| Governance | `Who owns the SLA definition?` | Governance/Purview source |
| Missing data | Request with incomplete operational fields | Agent non-fabrication behavior |

For each test capture:

- Selected source.
- Generated DAX, SQL, or KQL where available.
- Applied instruction layer.
- Returned answer.
- Pass/fail result.
- Any duplicated or ignored instruction discovered.

## Deliverables

Return:

1. The grounding inventory.
2. The classification decision for every existing rule.
3. The Fabric files changed.
4. The semantic-model objects changed.
5. The governance objects retained as authoritative.
6. The validation results.
7. Remaining limitations.
8. Confirmation that `.github` was used only to drive implementation and is not a runtime dependency.

The completed architecture must follow this rule:

> Use Fabric Data Agent instructions to govern the interaction. Use Fabric source configuration to govern retrieval. Use the semantic model to govern analytical meaning. Use Purview and governance metadata to govern published definitions and evidence. Use Git only to version and deploy those Fabric artifacts.
