# Native Purview Workflow Wireframe — Phase 5 Stakeholder Coverage

**Last updated:** 2026-08-11
**Status:** Design committed. P1 proven live. P3/P4 not yet built.
**Owner:** Sean Kelley

## 1. Purpose

Extend the closed-loop governance pattern proven in P1/P2 (`nb_12_purview_workflow_sync` +
`nb_13_semantic_reconcile`, Ci Zhu's `GT-SLA` term publication) to cover the remaining 4
stakeholders, using only **native Purview Unified Catalog workflow types** — no SQL-controlled
gating for this phase. Each scenario must be built end-to-end with validation steps before its
own closeout, methodically, one at a time. Only after all 5 stakeholders have a proven native
scenario does this phase close and the **non-native workflow phase** begin.

## 2. Ground truth: what native workflow types actually exist

Per Microsoft Learn (`unified-catalog-workflows`, verified 2026-08-11), Unified Catalog supports
**exactly two workflow categories, three workflow types**:

| Workflow category | Workflow type | Scope | Role required to author/manage |
|---|---|---|---|
| Catalog curation | **Term publish** | Governance domain | Governance Domain Creator |
| Catalog curation | **Data product publish** | Governance domain | Governance Domain Creator |
| Data product access | **Data product access** | Single data product or governance domain | Data Product Owner |

There is no native workflow type for CDE classification, KPI approval, verified-answer
certification, OKR approval, or label-policy change — those remain SQL-controlled (already
proven live via `nb_11_gated_governance_sync` in Phase 4/G14) and are explicitly out of scope for
this phase, per `docs/closed-loop-governance-reference-model.md` §"Later extension: SQL-controlled
approvals". Do not represent any of those as Purview-native in this phase.

## 2a. Evidence tier model (confirmed 2026-08-12)

Every closed-loop scenario's evidence falls into one of three tiers. Classify each scenario before
building its bridge notebook, rather than assuming machine verification is always possible:

| Tier | Definition | Verification | Examples in this repo |
|---|---|---|---|
| **Tier 1 — Governed object state** | The Unified Catalog API exposes the governed object's own current state directly | Independently machine-verified — read the object, hash it, compare | Terms (`status` Draft→Published, `nb_12`), Data Products (`status`, `nb_15` planned), Business Domains, CDEs, OKRs, Data Assets, Data Columns |
| **Tier 2 — Policy/relationship configuration** | The API exposes configuration/relationship objects (e.g. RBAC role assignments) | Machine-verifiable for *configuration*, not for individual *decisions* | `Policies` operation group (role-assignment rules) — confirmed 2026-08-12 to be RBAC/ABAC config, not request records |
| **Tier 3 — Workflow execution artifacts** | The decision/approval itself, as an event | **No API, Graph endpoint, or diagnostic log exposes this today** (confirmed via exhaustive research + a live empirical test) | Data Product access-request decisions (`nb_14`) |

**The governing principle:** the governed object is the system of record, not the workflow. A
workflow authorizes a change; evidence comes from reading the resulting object directly, where
that's possible (Tier 1). Where it isn't (Tier 3), evidence must be honestly labeled as
operator-attested rather than falsely claimed as machine-verified — never invent a fake
verification for a scenario that is genuinely Tier 3. Classify each new scenario against this model
in Stage 1 (Configure) before assuming its bridge notebook can follow the `nb_12` pattern.

## 3. Stakeholder-to-scenario coverage matrix

All 5 stakeholders fit across the 3 available native workflow types — no stakeholder is left
without a native scenario, and no scenario is invented that Purview doesn't actually support.

| Stakeholder | Governance role | Scenario | Workflow type | Governed object |
|---|---|---|---|---|
| **Ci Zhu** | Domain Owner DOM-REVCON, Governance Domain Creator (tenant) | **P1 — DONE** | Term publish | `GT-SLA` |
| **Victoria Tan** | Domain Owner DOM-CUSTOPS, Data Product Owner DP-CUST360, Privacy Officer | **P3 — approver** | Data product access | `DP-CUST360` |
| **Rupal Solanki** | Steward DOM-CUSTOPS, Steward DP-CUST360 | **P3 — requester** | Data product access | `DP-CUST360` |
| **Ranbir Singh** | Domain Owner DOM-SVCDEL, Data Product Owner DP-SVCPERF | **P4 — approver** | Data product publish | `DP-SVCPERF` (domain DOM-SVCDEL) |
| **Shruthi Srinivas** | Steward DOM-SVCDEL, Steward DP-SVCPERF | **P4 — requester** | Data product publish | `DP-SVCPERF` (domain DOM-SVCDEL) |

P3 and P4 each pair one owner/approver with one steward/requester, matching the real reporting
structure in `docs/purview-demo-data-design.md` §7 and giving each scenario a genuine
non-self-approval flow.

## 4. Required manual role setup (per repo memory: no REST API for Unified Catalog RBAC)

Confirmed 2026-08-11 against Microsoft Learn and this repo's own tested Data Governance API
surface: Unified Catalog role assignment (Governance Domain Creator, Governance Domain Owner,
Data Product Owner, Data Steward, Catalog Reader) has **no REST API** — it is UI-only, via
**Settings > Unified Catalog > Roles and permissions** (catalog-level) or a domain's **Roles**
tab (domain-level). This is separate from the `contacts.owner`/`contacts.steward` metadata field
already set on Terms/CDEs/Data Products via the Data Governance API. Manual assignment is the
correct and required method — not a workaround.

Before building each scenario, confirm these role assignments are in place manually in the portal:

| Scenario | Person | Required role | Where assigned |
|---|---|---|---|
| P3 | Victoria Tan | Data Product Owner on `DP-CUST360` | Data product > Roles, or domain Roles tab |
| P3 | Rupal Solanki | Global Catalog Reader (or Local Catalog Reader on DOM-CUSTOPS) — sufficient to submit an access request | Settings > Unified Catalog > Roles and permissions, or domain Roles tab |
| P4 | Ranbir Singh | Governance Domain Owner on DOM-SVCDEL, Data Product Owner on `DP-SVCPERF` | Domain Roles tab |
| P4 | Shruthi Srinivas | Data Steward on DOM-SVCDEL / `DP-SVCPERF` | Domain Roles tab |
| P4 (authoring) | Ci Zhu (or Sean, build-phase) | Governance Domain Creator (tenant) — required only to author/manage the **Data product publish** workflow itself; Ranbir does not need this role to be assigned as its approver | Settings > Unified Catalog > Roles and permissions |

Do the manual UI check before starting each scenario's build; do not assume a prior role
assignment persisted across a domain/data product rebuild (this repo has had full rebuild events
before — see `purview-api-notes.md`).

Step-by-step assignment/verification instructions for all 4 remaining stakeholders are in
`docs/runbooks/p3-p4-role-assignment-setup.md`.

## 5. End-to-end build template (extends the P1/P2 pattern)

Every scenario follows the same 9-stage shape already proven for `GT-SLA`:

1. **Configure** — create the native Purview workflow (category/type per §2), assign the correct
   approver, scope it to the correct domain/data product.
2. **Safe baseline dry run** — bridge notebook with `DEMO_MODE = True` writes nothing, only reads
   and prints the current Purview snapshot/hash.
3. **Draft/revision created** — the requester edits the governed object (or submits the access
   request) in Purview, leaving it in the pre-decision state.
4. **Capture Draft** — bridge notebook (`DEMO_MODE = False`) writes one idempotent `Draft`
   request/event/version row to `dbo.governance_requests`/`governance_events`.
5. **Human decision** — requester submits, approver approves or rejects in the native workflow.
6. **Capture decision** — bridge notebook re-run advances the SQL request to `Approved` (or
   `Rejected`) and appends the decision event exactly once.
7. **Reconcile downstream target(s)** — only for scenarios that mutate governed content (P1, P4);
   an audit-only scenario (P3) skips this stage entirely, per
   `docs/closed-loop-governance-reference-model.md`'s explicit rule that access decisions do not
   mutate semantic definitions.
8. **Validate** — each required receipt (`PublicationReadback`, `AccessDecisionReadback`,
   `SemanticModelReadback`) must independently read back and match an expected hash/value before
   the request can close.
9. **Closeout** — `dbo.governance_requests.current_status` transitions to `Completed` only when
   every required receipt for that request type is `Passed`. Repeating any bridge notebook run
   must remain a no-op (idempotent upsert, no duplicate events/receipts).

No SQL schema change is required for P3/P4 — `governance_requests.request_type`,
`governance_target_receipts.receipt_type`, and `.target_system` are free-text `VARCHAR` with no
`CHECK` constraint restricting values (confirmed by reading `sql/13_closed_loop_governance_ledger.sql`).
Only `authority` (`Purview`/`SQL`) and `current_status` (state machine) are constrained, and both
already cover these scenarios.

## 6. Concrete build plan

### P3 — Data Product Access (`DP-CUST360`)

- `request_type = 'DataProductAccess'`, `authority = 'Purview'`
- Confirmed live 2026-08-11: use the **Approvers list** path in the "Manage access policies" flyout
  (Policy Configuration tab > Approval requirements), NOT the custom workflow canvas. Per Microsoft
  Learn, populating the **Approvers** field directly auto-generates the backing workflow on Save —
  no need to hand-build/edit a visual workflow (the canvas's default "Manager approver required"
  template is tied to dynamic Entra-manager lookup, not a named-person picker, and fighting it is
  unnecessary extra work). Set **Approvers = Victoria Tan**, leave **Manager approval required**
  unchecked, check **Privacy and compliance review required** (matches her Privacy Officer role).
- Confirmed live 2026-08-11: the workflow-authoring entry point is the **"Before you can publish"**
  dialog shown when publishing/re-publishing `DP-CUST360` — it offers a **"Set up workflow"** radio
  option alongside "Add data assets"; selecting it opens **Manage access policies**, which has two
  paths (Approvers list — used — or New Workflow custom canvas — not used).
- Confirmed live 2026-08-12: NO Purview REST API, Microsoft Graph endpoint, or diagnostic log
  exposes a Data Product access request's decision for independent verification (exhaustively
  checked — candidate endpoints, `$metadata` discovery, Graph API, and a live diagnostic-logging
  test with a real fresh event all confirmed nothing is captured). `nb_14_purview_access_sync`
  therefore uses **operator-attested evidence** for the decision itself, while independently
  API-verifying the data product's own live state (status, domain, definition hash). This is the
  same transparency pattern `nb_12` already uses for its own documented evidence gaps.
- Audit-only: **no semantic reconciliation notebook**. Only one required receipt:
  `receipt_type = 'AccessDecisionReadback'`, `target_system = 'PURVIEW_WORKFLOW'`
- New bridge notebook: `nb_14_purview_access_sync.Notebook` — same `DEMO_MODE` /
  `WORKFLOW_CONFIGURED` / `RUN_CORRELATION_ID` config-flag shape as `nb_12`
- New runbook: `docs/runbooks/p3-native-dataproduct-access.md`
- Closeout: `Completed` once `AccessDecisionReadback = Passed`

### P4 — Data Product Publish (`DP-SVCPERF`, domain DOM-SVCDEL)

- `request_type = 'DataProductPublish'`, `authority = 'Purview'`
- Mutates governed content the same way Term publish does — full two-notebook pattern:
  - New bridge notebook: `nb_15_purview_dataproduct_sync.Notebook` (mirrors `nb_12`) — **built 2026-08-12**
  - New reconciliation notebook: `nb_16_dataproduct_semantic_reconcile.Notebook` (mirrors `nb_13`,
    targeting the semantic objects tied to `DP-SVCPERF`, e.g. `fct_service_request`-linked
    measures/annotations) — **built 2026-08-12**; `SEMANTIC_TARGETS` are placeholders needing
    confirmation against the live semantic model before the first live run
- Two required receipts: `PublicationReadback` + `SemanticModelReadback` (identical contract to
  P1/P2)
- New runbooks: `docs/runbooks/p4-native-dataproduct-publish.md` +
  `docs/runbooks/p4b-dataproduct-semantic-reconciliation.md`
- Closeout: `Completed` once both receipts are `Passed`

### P4 workflow-surface map (confirmed live 2026-08-12, corrected against Microsoft Learn)

The **Data product publish** workflow is authored via **Unified Catalog > Process automation >
Workflows > New** (Category: Catalog curation, Type: Data product publish) — confirmed as the ONLY
documented creation path via a direct fetch of `learn.microsoft.com/purview/unified-catalog-workflows`.
The governance domain page's own "Workflows" tab (behind the Roles-tab overflow menu) is NOT
documented anywhere and is most likely a status/shortcut view for an already-existing workflow
object — attempting to attach an approver directly through that toggle produced a persistent 404
"Resource not found", even after confirming Ranbir held every role we hypothesized was required.
Building the workflow through the correct **Process automation** canvas succeeded immediately,
with no 404 and no additional role dependency beyond **Governance Domain Creator** to author it.

**Real workflow built and saved:** "Service Delivery Data Product Publish" — trigger "When a data
product is published", **Start and wait for an approval** (Pending on all, Assigned to: Ranbir
Singh), **Condition** `Approval.Outcome = Approved`, If yes → publish / If no → stays Draft,
**Set scope** → Service Delivery domain only. Confirmed saved ("Succeeded" toast, 2026-08-12).

This also confirmed (per docs) that P3's Data Product Access mechanism (the per-product "Manage
access policies" flyout Approvers list used for Victoria/Rupal) auto-generates a real workflow
object behind the scenes on Save — it is NOT a separate lightweight/legacy feature, it's the same
underlying workflow framework, just created through a different (also documented) shortcut path
specific to the Access workflow type. Publish workflows have no equivalent shortcut — Process
automation is the only path for them.

| Stakeholder | Workflow type | Approver field behavior | Domain-role fix needed? |
|---|---|---|---|
| Victoria Tan (P3, `DP-CUST360`) | Data Product **Access** | Free-text people-picker on "Manage access policies" flyout — Save auto-generates a real workflow object (confirmed per docs) | No |
| Rupal Solanki (P3) | Requester only | N/A | No |
| Ci Zhu (P1/P2, GT-SLA) | **Term publish** (same Process automation surface, different Workflow type) | Assigned to named user, not role-gated per docs — already ran live successfully in a prior session | No — already working |
| Shruthi Srinivas (P4) | Requester/steward only | N/A | No |
| Ranbir Singh (P4) | **Data product publish** | Built via Process automation > Workflows > New, Assigned to: Ranbir Singh directly — no domain-role gate encountered once using the correct authoring surface | Done — workflow saved 2026-08-12 |

**Lesson:** when a Purview UI surface produces a 404 despite correct role assignments, check
whether the feature has an alternate, differently-located authoring path in the current
documentation before assuming it's a role/permission gap — a 404 (not 403) is a strong signal the
resource itself doesn't exist yet, not that access is denied.

## 7. Sequencing commitment

Build and close P3 fully (configure → validate → closeout, with runbook evidence) before starting
P4. Do not start a second scenario's live approval step while another is mid-flight, to keep each
request's evidence trail unambiguous. After P4 closes:

1. Mark this phase Done in `docs/design-gap-analysis.md` and `docs/build-scorecard.md`.
2. All 5 stakeholders will have at least one proven native Purview workflow scenario.
3. Begin the non-native workflow phase — reconciling the already-proven SQL-controlled scenarios
   (KPI approval, Verified Answer certification, CDE classification — all live since Phase 4/G14)
   under this same ledger contract, planned separately.

## 8. What does not fit natively (explicitly out of scope this phase)

- CDE classification, KPI approval, verified-answer certification, OKR approval, label-policy
  change — no native Purview workflow type exists for any of these. They stay on the SQL-controlled
  path already proven in Phase 4 and are not to be re-implemented as Purview-native here.
