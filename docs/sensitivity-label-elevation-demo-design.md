# Sensitivity Label Elevation — Demo Design Notes

**Status:** Design in progress, not yet built. This document captures the decisions made
while designing the feature so far; it is not a runbook and not a completed build record.

## Goal

Extend the closed-loop governance demo with a use case that proves a governance decision has
a real, live, *enforced* consequence — not just a database row changing. Specifically: elevate
a data element's sensitivity classification through a real governed approval, and show that this
results in a real user being denied access to the semantic model as a result.

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
| Denied user (real test identity) | **Rupal Solanki** (`7d0013fe-3538-419b-ac8a-aef6bf13192e`) | Customer 360/consent steward — zero legitimate business tie to service-account geolocation data; plain Workspace Member (not Admin/owner), the correct permission tier for a DLP "restrict to owner" action to actually catch |
| Admin API executor (calls `setLabels`, needs Fabric-admin token) | Sean Kelley / Ci Zhu | Neither Ranbir nor Victoria plausibly holds Fabric-admin/`Tenant.ReadWrite.All` rights; `delegatedUser` field attributes the label to Victoria regardless of which admin technically calls the API |

Ci Zhu was originally considered for the denied-user role but is the wrong choice structurally:
she's Workspace Admin on `Enercare-West3` plus Information Protection Admin / Label Policy Owner
— exactly who a DLP "restrict to owner" action is designed to exempt, not catch.

## Technical flow (SQL → real enforcement)

Two label-carrying mechanisms exist and only one of them is what DLP actually reads:

1. **SQL contract update** (Tier 1) — `07_apply_approved_changes` updates
   `dbo.governance_cdes.sensitivity_label` for `CDE-GEO`.
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
     "delegatedUser": { "emailAddress": "Victoria.Tan@enercare.ca" }
   }
   ```
   Requires: caller must be a Fabric administrator (`Tenant.ReadWrite.All`); the admin/delegated
   user must have the label in their own label policy; max 25 requests/hour, up to 2000 items
   per call.
4. **⚠️ DLP does not evaluate instantly on label-apply.** Per Microsoft's docs, DLP re-evaluates
   a semantic model only on **Publish, Republish, on-demand refresh, or scheduled refresh**. The
   dispatcher must trigger an **on-demand refresh** immediately after `setLabels` succeeds, or the
   demo's deny moment won't reliably fire on a predictable schedule.
5. **DLP match → enforcement** — the DLP policy (content labeled "Enercare Highly Confidential"
   → Restrict Access) matches and Fabric overrides the item's effective access at the
   platform/item level — separate from the model's own RLS or workspace roles.
6. **Rupal's experience** — next attempt to open `BrookfieldEnercare` (or a report over it) is
   denied, since she isn't the registered owner.

### The one DLP config detail that must be right

The "Restrict access" action has two variants: *restrict to data owners* (blocks everyone else)
vs. *restrict to members of the organization* (only blocks external/guest users). Since Rupal is
an internal identity, the policy **must** use the data-owners-only variant — the org-members
variant would not catch her.

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
- **`BrookfieldEnercare`'s current owner**: `seankelley@MngEnvMCAP660444.onmicrosoft.com` —
  confirmed via `Get-PowerBIDataset -WorkspaceId b976cac2-7754-4061-88c2-61c0ac016a99 -Scope
  Organization` (`ConfiguredBy` field), dataset ID `8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c`. A real
  user, not a service principal (so DLP will actually evaluate this model) and not Rupal Solanki
  (so she's a genuine non-owner the "Block everyone" restriction will catch).

## Open items / not yet confirmed

*(none remaining — both prerequisites and the owner check are confirmed live as of 2026-08-19)*

## Built

- **`sql/07_governance_gates/29_g21_sensitivity_label_elevation.sql`** — the SQL-controlled
  request lifecycle (Draft→Submitted→Approved) and the SQL-side apply (`LBL-007` → `LBL-010`).
  Committed `d4ce67d`, run live against `sqldemo`, verified idempotent.
- **`06_publish_glossary_and_lineage.Notebook`, new Cells 12–13** — Cell 12 adds governance-ledger
  SQL connectivity (this notebook previously only had Purview/Fabric API connectivity, not SQL
  read/write); Cell 13 reads `SLELEV-CDE-GEO-001`, refreshes the Purview Data Map Atlas tag
  (reusing the existing `_apply_sensitivity_label`/`_resolve_entity` helpers), calls the Power BI
  Admin `setLabels` API on `BrookfieldEnercare` (dataset ID `8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c`)
  with `delegatedUser = Victoria.Tan@enercare.ca`, triggers an on-demand refresh, then writes the
  `PURVIEW_DATA_MAP`/`FABRIC_INFORMATION_PROTECTION` receipts and marks the request `Completed` --
  **only if `setLabels` reports `Succeeded`**; otherwise it raises, logs to `nb09_diagnostics_log`,
  and leaves the request at `Approved`. **Not yet run live** — needs a Fabric-admin-capable
  identity to actually succeed at the `setLabels` step; not yet pushed to Fabric/git-synced.

## Not yet done

- Push the notebook change to git, run `tools/sync_fabric_git.py`, then submit a live job via
  `tools/run_fabric_notebook_job.py --notebook 06_publish_glossary_and_lineage` to actually test
  Cells 12–13 end to end. This is the first live test of the `setLabels` call — genuinely unknown
  until run whether this Fabric workspace's notebook-execution identity has the required
  Fabric-admin rights.
- Add `FABRIC_INFORMATION_PROTECTION` as a named target-system category to
  `docs/closed-loop-governance-reference-model.md`'s "Recommended target systems" list (it's used
  in code now, but not yet documented there).

## See also

- [`docs/closed-loop-governance-reference-model.md`](./closed-loop-governance-reference-model.md)
  — the reference architecture this design extends.
- [`docs/governance-ontology-and-data-contract-model.md`](./governance-ontology-and-data-contract-model.md)
  — the 3-tier contract and ontology this fits into.
- [`purview/role-directory.csv`](../purview/role-directory.csv) — actor role/permission source.
- [`sql/02_metadata_foundation/07_seed_purview_metadata.sql`](../sql/02_metadata_foundation/07_seed_purview_metadata.sql)
  — `GT-GEOPII`, `CDE-GEO`, `LBL-006`/`LBL-007` seed source.
