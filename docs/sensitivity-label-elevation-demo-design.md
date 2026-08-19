# Sensitivity Label Elevation — Demo Design Notes

**Status:** Label elevation validated; column-level enforcement implementation in progress on 2026-08-19.
This document records the design, implementation, and validation evidence.

## Goal

Extend the closed-loop governance demo with a use case that proves a governance decision has
a real, live, *enforced* consequence — not just a database row changing. Specifically: elevate
a data element's sensitivity classification through a real governed approval, and show that this
results in an unauthorized user being denied only the protected columns while retaining access to
the semantic model and all nonprotected data.

## Why this aligns with the existing SQL contract (not a new architecture)

`docs/closed-loop-governance-reference-model.md`, under **"Later extension: SQL-controlled
approvals,"** already names this exact category:

> "Defer KPI certification, verified-answer certification, CDE classification, semantic
> metadata, Data Agent grounding, and **label-policy changes** until Phase 1 is proven. These
> changes may later use **controlled SQL approval procedures** when no supported native Purview
> workflow exists."

Sensitivity labels are authored in Microsoft Purview Information Protection, a system with no
Unified Catalog native workflow object type — so this uses the SQL-controlled
Draft→Submitted→PendingApproval→Approved→Applying→Validated→Completed pattern, identical to
every other gate in this repo (07_apply_approved_changes dispatcher), not Purview-native workflow.

## The use case: elevate `CDE-GEO`

Derived from the actual data, not an invented narrative. There are 4 tables carrying genuinely
sensitive columns in the seed data:

| Table | Sensitive column(s) | Current label | Current tier |
|---|---|---|---|
| `dbo.customers` | `date_of_birth`, `sin_last_4` | `LBL-006` Privacy Restricted | Highly Confidential (already top tier) |
| `dbo.employees` | `sin_full`, `date_of_birth` | `LBL-006` Privacy Restricted | Highly Confidential (already top tier) |
| `dbo.billing_transactions` | `card_pan_last_4`, `bank_routing_last_4` | `LBL-004`/`LBL-005` | Highly Confidential (already top tier) |
| `dbo.service_accounts` | `latitude`, `longitude` | `LBL-007` Operations Sensitive | **Confidential** (one tier below top) |

Three of the four are already seeded at the highest tier — there's no headroom to "elevate" them
without inventing a brand-new tier above what already exists. `service_accounts` geolocation is
the only one of the four with real headroom, which is why it's the one the data itself picks:

- **Asset:** `CDE-GEO` ("Geo Coordinates") — `dbo.service_accounts.latitude`/`longitude`, bound to
  glossary term `GT-GEOPII` ("Geolocation PII").
- **Elevation:** `LBL-007` "Operations Sensitive" (Confidential) → real MIP label
  **"Enercare Highly Confidential"** (Highly Confidential).

## Cast

Not arbitrary — reuses ownership already baked into the seed data:

| Role | Persona | Why |
|---|---|---|
| Requester | **Ranbir Singh** | Already `GT-GEOPII`'s real `owner_upn` in `07_seed_purview_metadata.sql` |
| Approver | **Victoria Tan** | Already `GT-GEOPII`'s `additional_owners_upn`, and the repo's designated `Privacy Officer (Functional)` role in `purview/role-directory.csv` |
| Authorized business consumers | **Victoria Tan**, **Ranbir Singh** | Victoria is the approval-workflow manager; Ranbir owns the Service Delivery domain and `GT-GEOPII`. Both retain Viewer access and must not be assigned to the restricted OLS role. |
| Authorized steward | **Shruthi Srinivas** | Steward for `CDE-GEO`; Workspace Member has full model access and bypasses OLS. |
| Restricted data consumer | **Rupal Solanki** (`7d0013fe-3538-419b-ac8a-aef6bf13192e`) | Retains Workspace Viewer and report access but is assigned to `RestrictedGeolocation`, which hides only latitude and longitude. |
| Governance administrators | **Sean Kelley**, **Ci Zhu** | Workspace Admins with full model access; Admin roles bypass OLS. Sean remains the API executor and delegated label user. |

Ci Zhu was originally considered for the denied-user role but is the wrong choice structurally:
she's Workspace Admin on `Enercare-West3` plus Information Protection Admin / Label Policy Owner
— exactly who a DLP "restrict to owner" action is designed to exempt, not catch.

## Technical flow (SQL → real enforcement)

Two label-carrying mechanisms exist and only one of them is what DLP actually reads:

1. **SQL contract update** (Tier 1) — the G21 SQL apply moves CDE-GEO's bound columns from
  `LBL-007` to `LBL-010` in `dbo.governance_label_assignments` and records a version and receipt.
2. **Purview Data Map tag refresh** (descriptive only, does NOT feed DLP) — the existing Atlas
   `_apply_sensitivity_label()` call from `06_publish_glossary_and_lineage`
   (`/catalog/api/atlas/v2/entity/guid/{guid}/labels`) updates the Data Map entity's tag.
3. **The step that actually matters** — a real MIP label applied directly to the Fabric item via
   the Power BI Admin API:
   ```http
   POST https://api.powerbi.com/v1.0/myorg/admin/informationprotection/setLabels
   {
     "artifacts": { "datasets": [ { "id": "<BrookfieldEnercare semantic model GUID>" } ] },
     "labelId": "0dd498ed-386a-4f71-aa94-2dda1b6e34e5",
     "assignmentMethod": "Standard",
     "delegatedUser": { "emailAddress": "seankelley@MngEnvMCAP660444.onmicrosoft.com" }
   }
   ```
   The notebook reads `SLE_DELEGATED_USER_UPN` when an override is needed. The delegated user must
   be included in the label's published policy; using Victoria's real Entra UPN without that policy
   assignment fails with `InformationProtectionLabelNotAssigned`. The caller must also be a Fabric
   administrator (`Tenant.ReadWrite.All`); max 25 requests/hour, up to 2000 items per call.
4. **⚠️ DLP does not evaluate instantly on label-apply.** Per Microsoft's docs, DLP re-evaluates
   a semantic model only on **Publish, Republish, on-demand refresh, or scheduled refresh**. The
   dispatcher must trigger an **on-demand refresh** immediately after `setLabels` succeeds, or the
   demo's deny moment won't reliably fire on a predictable schedule.
5. **DLP match → detection and response** — the DLP policy detects the label, raises the policy
  tip and alert, and records the incident. Remove its owner-only Restrict Access action only after
  OLS is deployed and Rupal's role membership is confirmed.
6. **Object-level security → protected-column enforcement** — the source-controlled
  `RestrictedGeolocation` role sets `metadataPermission: none` on
  `dim_service_account[Latitude]` and `[Longitude]`. Assign only Rupal to this role. Do not create
  a Fabric protection policy for this use case because protection policies control whole items.
7. **Rupal's experience** — the report and all nonprotected model data remain available. The two
  coordinate columns and their metadata behave as if they do not exist. Victoria, Ranbir,
  Shruthi, Sean, and Ci retain authorized access to the coordinates.

### Access-control configuration that must be right

Fabric DLP and Fabric protection policies operate at item scope; neither can express "allow the
semantic model but hide two columns." DLP therefore remains the detection, notification, and
alerting layer without Restrict Access. OLS is the enforcement layer. OLS applies only to Workspace
Viewers, so Rupal remains a Viewer. Sean and Ci are Admins and Shruthi is a Member, all authorized
to see the protected data and structurally exempt from OLS. Victoria and Ranbir are authorized
Viewers and are not members of `RestrictedGeolocation`.

## Confirmed live so far

- **Label**: `Enercare Highly Confidential`, GUID `0dd498ed-386a-4f71-aa94-2dda1b6e34e5`,
  Priority 12 — confirmed via `Get-Label` in Security & Compliance PowerShell
  (`Connect-IPPSSession -UserPrincipalName seankelley@MngEnvMCAP660444.onmicrosoft.com`).
- **DLP policy**: `Enercare Sensitivity Elevation Restrict Access` (name truncated in portal UI),
  Locations: Fabric and Power BI workspaces only; rule `Restrict Enercare Highly Confidential to
  Owner` — Condition: content contains sensitivity label `Enercare Highly Confidential`; Actions:
  restrict access to the content (**"Block everyone"** variant, not "outside organization" — this
  matters since Rupal Solanki is internal), notify users with email and policy tips, send alerts
  to administrator. Policy mode: **Turn the policy on immediately** (full enforcement, not
  simulation). Submitted via the Purview portal 2026-08-18; portal showed `Sync in progress`
  immediately after submission, then `Sync completed` the next day (2026-08-19) — matches the
  documented DLP-for-Fabric tenant onboarding propagation delay, not an error. **Fully confirmed
  live via `Get-DlpCompliancePolicy`/`Get-DlpComplianceRule`** (2026-08-19): policy `Mode: Enable`,
  `Enabled: True`, Priority 3; rule `BlockAccessScope: All` (confirms "Block everyone" was
  correctly selected, not the "outside organization" variant — required to catch Rupal, an
  internal identity), `Disabled: False`.
  **Correction required:** this owner-only action blocks every authorized nonowner. Retain the
  rule's detection, notification, and alert behavior, but remove its Restrict Access action after
  `RestrictedGeolocation` is deployed and assigned to Rupal.
- **`BrookfieldEnercare`'s current owner**: `seankelley@MngEnvMCAP660444.onmicrosoft.com` —
  confirmed via `Get-PowerBIDataset -WorkspaceId b976cac2-7754-4061-88c2-61c0ac016a99 -Scope
  Organization` (`ConfiguredBy` field), dataset ID `8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c`. A real
  user, not a service principal (so DLP will actually evaluate this model) and not Rupal Solanki
  (so she's a genuine non-owner the "Block everyone" restriction will catch).
- **G21 apply and receipts**: Cell 13 completed live on 2026-08-19. `setLabels` returned HTTP 200
  with dataset status `Succeeded`; `SLELEV-CDE-GEO-001` is `Completed`; all three receipts
  (`SQL`, `PURVIEW_DATA_MAP`, and `FABRIC_INFORMATION_PROTECTION`) are `Passed`. The Fabric receipt
  records label GUID `0dd498ed-386a-4f71-aa94-2dda1b6e34e5`, delegated user Sean Kelley, HTTP 200,
  and `refreshTriggered=true`.
- **DLP reevaluation refresh**: the apply-triggered `ViaApi` refresh completed from
  `2026-08-19T17:31:37.997Z` to `17:31:48.013Z`. After Rupal was added as a Workspace Viewer, a
  second `ViaApi` refresh (`678a662d-43c4-4b35-a239-e9a93a12cdcf`) completed at
  `2026-08-19T17:37:27.950Z`, ensuring policy evaluation used the current access state.
- **Denied-user baseline**: Power BI workspace-user read-back confirms Rupal's real Entra UPN,
  `rupal.solanki@MngEnvMCAP660444.onmicrosoft.com`, has `Viewer` access. Her denial can therefore
  prove DLP enforcement rather than merely missing workspace permission.
- **Denied-user enforcement**: signed in interactively as Rupal on 2026-08-19, the
  `BrookfieldEnercare` report shell opened but every semantic-model visual was blocked. Technical
  details reported `Underlying Error: Missing_References` at `2026-08-19 10:47:41 PDT` (Activity
  ID `d37856ab-f8cd-4f35-adef-600aa09c3856`). Power BI API read-back still reported Rupal as
  Workspace `Viewer` and dataset `Read`, while an owner `executeQueries` call against the same
  `_Measures[Total MRR]` reference succeeded and returned `9956.89`. This isolates the failure to
  effective query-time restriction rather than a missing measure or absent baseline permission.
- **Victoria authorization defect reproduced**: Victoria was granted Workspace `Viewer`; API read-back
  confirmed dataset `Read`. A subsequent `ViaApi` reevaluation refresh
  (`f03a9968-aaf5-460c-9e3f-8e63e1df04ee`) completed at `2026-08-19T17:51:56.053Z`. Signed in as
  Victoria, the report reproduced `Underlying Error: Missing_References` at
  `2026-08-19 10:53:39 PDT` (Activity ID `a6d7536c-9be7-47ee-a53b-1b5842acfe6c`). This is evidence
  that the owner-only DLP action is too broad for the workflow, not a successful denied-persona
  test. Victoria must be allowed by the Fabric protection policy and retested successfully.

## Open items / not yet confirmed

1. Sync the committed notebook and semantic-model definition to Fabric.
2. Run `03_build_semantic_model` so the Direct Lake dimension contains `Latitude` and `Longitude`.
3. Confirm the deployed semantic model contains the `RestrictedGeolocation` OLS role.
4. In the semantic model **Security** page, assign only
   `rupal.solanki@MngEnvMCAP660444.onmicrosoft.com` to `RestrictedGeolocation`.
5. Remove only the DLP rule's Restrict Access action; retain detection, policy tips, notifications,
   and alerts. Do not create an item-wide Fabric protection policy for this scenario.
6. Test all six personas: Sean and Ci have full Admin access; Shruthi has full Member access;
   Victoria and Ranbir have authorized Viewer access; Rupal can query general model data but cannot
   discover or query `Latitude` or `Longitude`.

## Built

- **`sql/07_governance_gates/29_g21_sensitivity_label_elevation.sql`** — the SQL-controlled
  request lifecycle (Draft→Submitted→Approved) and the SQL-side apply (`LBL-007` → `LBL-010`).
  Committed `d4ce67d`, run live against `sqldemo`, verified idempotent.
- **`06_publish_glossary_and_lineage.Notebook`, new Cells 12–13** — Cell 12 adds governance-ledger
  SQL connectivity (this notebook previously only had Purview/Fabric API connectivity, not SQL
  read/write); Cell 13 reads `SLELEV-CDE-GEO-001`, refreshes the Purview Data Map Atlas tag
  (reusing the existing `_apply_sensitivity_label`/`_resolve_entity` helpers), calls the Power BI
  Admin `setLabels` API on `BrookfieldEnercare` (dataset ID `8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c`)
  with `delegatedUser = seankelley@MngEnvMCAP660444.onmicrosoft.com` by default (configurable via
  `SLE_DELEGATED_USER_UPN`), triggers an on-demand refresh, then writes the
  `PURVIEW_DATA_MAP`/`FABRIC_INFORMATION_PROTECTION` receipts and marks the request `Completed` --
  **only if `setLabels` reports `Succeeded`**; otherwise it raises, logs to `nb09_diagnostics_log`,
  and leaves the request at `Approved`. Live apply, receipt write-back, and refresh all succeeded
  on 2026-08-19.
- **`03_build_semantic_model.Notebook`** — publishes governed `Latitude` and `Longitude` columns
  into `dim_service_account` for authorized semantic-model consumers.
- **`BrookfieldEnercare.SemanticModel/definition/roles/RestrictedGeolocation.tmdl`** — hides only
  the protected coordinate columns while preserving model access.

## Not yet done

Deploy the OLS assets, assign Rupal, remove the conflicting DLP Restrict Access action, and run the
six-persona validation matrix.

## See also

- [`docs/closed-loop-governance-reference-model.md`](./closed-loop-governance-reference-model.md)
  — the reference architecture this design extends.
- [`docs/governance-ontology-and-data-contract-model.md`](./governance-ontology-and-data-contract-model.md)
  — the 3-tier contract and ontology this fits into.
- [`purview/role-directory.csv`](../purview/role-directory.csv) — actor role/permission source.
- [`sql/02_metadata_foundation/07_seed_purview_metadata.sql`](../sql/02_metadata_foundation/07_seed_purview_metadata.sql)
  — `GT-GEOPII`, `CDE-GEO`, `LBL-006`/`LBL-007` seed source.
