# P3 Native Data Product Access Runbook

**Scenario:** Data Product Access request on `DP-CUST360` (Customer 360)
**Governance domain:** Customer Operations
**Requester:** Rupal Solanki (Steward, DOM-CUSTOPS / DP-CUST360; Global Catalog Reader)
**Approver / Privacy reviewer:** Victoria Tan (Data Product Owner, DP-CUST360; Privacy Officer)
**Control boundary:** Purview approves access. Azure SQL will store normalized evidence once the
bridge notebook (`nb_14_purview_access_sync`, not yet built) is run. Fabric does not approve the
request. This scenario is **audit-only** — an access decision does not mutate the semantic model
or any governed object definition.

## Status

- ✅ Native Purview access request submitted, reviewed, and **Approved** (live, 2026-08-11).
- 🔴 Not yet done: bridge notebook (`nb_14_purview_access_sync`) to write the SQL ledger evidence
  (`governance_requests`/`governance_events`/`governance_target_receipts`) and the
  `AccessDecisionReadback` receipt. Until that runs, this loop has live Purview evidence but is not
  yet `Completed` in the SQL ledger sense — see `docs/purview-native-workflow-wireframe.md` §5-6.

## 1. Prerequisites (all confirmed live)

1. `DP-CUST360` published to the catalog with a real 3-tier asset set attached:
   - SQL tier: `customers`, `service_accounts`, `customer_consents`, `customer_complaints`
   - Fabric tier: `dim_customer`, `dim_service_account`, `fct_billing`
   - Semantic model tier: `BrookfieldEnercare`
2. Victoria Tan: **Data Product Owner** on `DP-CUST360` (set via the product's Edit > Basic
   details > Owner field) **and** **Global Catalog Reader** (tenant catalog-level role — required
   separately; the Owner field alone does not grant Unified Catalog nav/portal access).
3. Rupal Solanki: **Global Catalog Reader** (tenant catalog-level role).
4. Access policy configured on `DP-CUST360` (Manage access policies > Policy Configuration):
   - **Access time limit:** 30 days
   - **Data usage purposes:** `Customer-experience analytics`, `Marketing eligibility lookup`,
     `Privacy compliance reporting` (added to match `docs/purview-maria-north-star-scenario.md`)
   - **Approvers:** Victoria Tan
   - **Manager approval required:** unchecked (explicit named approver used instead of an
     Entra-manager lookup)
   - **Privacy and compliance review required:** checked

## 2. Live request evidence

| Field | Value |
|---|---|
| User or system that needs access | Rupal Solanki |
| Privacy reviewer | Victoria Tan |
| Purpose | Customer-experience analytics |
| Business justification | "Validating Rupal Submit to Victoria Approver request workflow" |
| Terms of use acknowledged | Data copies are not permitted |
| Decision | **Approved** by Victoria Tan |

## 3. Customer walkthrough narrative

Use this narrative when presenting the scenario live:

> "Rupal Solanki, a data steward on the Customer Operations team, needs access to the Customer 360
> data product to support a customer-experience analytics initiative. Rather than emailing someone
> or filing an IT ticket, she goes straight to the Unified Catalog, finds Customer 360, and clicks
> **Request access**. She picks her purpose from a governed list — Customer-experience analytics —
> and states her justification.
>
> Because Customer 360 contains consent and complaint data, the policy requires **both** a data
> product approver and a privacy reviewer. In this case Victoria Tan, the Chief Customer Officer,
> covers both roles — she owns the data product and is accountable for privacy compliance on it.
>
> Victoria reviews the request in **Requests and approvals** and approves it. No email chain, no
> spreadsheet tracker — the request, the approval, the purpose, and the time-bound access grant are
> all captured natively in Purview, against a governed data product with real attached assets and a
> real access policy."

This directly demonstrates the north-star scenario's "Manager + Privacy review" access-gate design
(`docs/purview-maria-north-star-scenario.md` §1.3) using real, live Purview mechanics rather than a
described/aspirational one.

## 4. Real build gotchas worth knowing (technical audience)

- Unified Catalog RBAC (Data Product Owner, Global Catalog Reader, Governance Domain Owner, etc.)
  has no REST API — assignment is UI-only, via **Settings > Unified Catalog > Roles and
  permissions** (catalog-level) or a data product's own **Edit** screen (product-level owner field).
- Setting someone as a product's "Owner" via the Edit screen is a metadata field, not a role grant
  by itself — a separate catalog-level role (at minimum Global Catalog Reader) is required before
  that person can even see the Unified Catalog navigation item.
- The Fabric tenant scan needed a Fabric workspace role assignment for Purview's managed identity
  before it could enumerate OneLake/Lakehouse files (a 403 Forbidden was blocking full asset
  discovery) — same fix pattern as the earlier SQL Mirroring managed-identity issue.
- A PIM-activated Global Administrator role requires a fresh sign-in/token before it takes effect —
  activating it in an already-open browser tab does not retroactively elevate that session.

## 5. Remaining work

- Build `nb_14_purview_access_sync` (bridge notebook) to capture this Approved decision into
  `dbo.governance_requests`/`governance_events`, write the `AccessDecisionReadback` receipt, and
  transition the SQL request to `Completed`. No schema change required — see
  `docs/purview-native-workflow-wireframe.md` §6-7.
- After P3 closes, proceed to P4 (Data Product Publish, `DP-SVCPERF`, Ranbir Singh / Shruthi
  Srinivas) per the wireframe's sequencing commitment.
