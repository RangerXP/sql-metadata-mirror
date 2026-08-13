# P3/P4 Role Assignment Setup — Manual Steps

**Scope:** Victoria Tan, Rupal Solanki, Ranbir Singh, Shruthi Srinivas
**Method:** Manual, via the Purview portal — confirmed no REST API exists for this (see
`purview-native-workflow-wireframe.md` §4 and repo memory).
**Design source:** `purview/role-directory.csv` already specifies every role below as the intended
target state. This pass verifies each is actually live-assigned in the real tenant now that all 5
stakeholders have real Entra accounts, and assigns anything missing.

Do this before building `nb_14` (P3) — confirm P3's 2 rows first, then P4's rows before building
`nb_15`/`nb_16`.

## 0. Before you start

- Sign in to [https://purview.microsoft.com](https://purview.microsoft.com) with an account that
  holds the **Data Governance** tenant role group (Sean Kelley or Ci Zhu).
- When searching for a user in any "add user" picker below, search by **display name** (e.g.
  "Victoria Tan"), not the synthetic `@enercare.ca` UPN in the CSV — confirm whichever real Entra
  account you added is the one selected, even if its actual UPN/domain differs from the CSV.
- Two different assignment surfaces exist — don't confuse them:
  - **Catalog-level roles** → **Settings (gear icon) > Unified Catalog > Roles and permissions**
  - **Domain-level roles** → open the governance domain itself > **Roles** tab

## 1. P3 prerequisite — Data Product Access workflow (`DP-CUST360`)

| Stakeholder | Role | Where | Steps |
|---|---|---|---|
| Victoria Tan | **Data Product Owner** on `DP-CUST360` | Data product **Details** tab (confirmed live 2026-08-11 — no separate "Roles" tab; **Edit is greyed out while the product is Published**, per Microsoft Learn: editing requires Draft status) | 1. Open **Unified Catalog > Catalog management > Data products > Customer 360**. 2. Click **Unpublish**, then **Set to draft** (Edit is disabled while Published). 3. Click **Edit**. 4. On **Basic details**, add **Victoria Tan** to the owners field alongside Sean Kelley — do not remove him. 5. **Save**. 6. Click **Publish** again to restore its published state. |
| Rupal Solanki | **Global Catalog Reader** (tenant-wide; enough to submit an access request) | Catalog-level | 1. **Settings > Unified Catalog > Roles and permissions**. 2. Select **Global Catalog Reader**. 3. Select the add-user icon. 4. Search "Rupal Solanki", select her, **Save**. |

Expected result: Victoria Tan's name appears in the **Data product owner** field on Customer 360's
Details tab (alongside Sean Kelley); Rupal Solanki's name appears under the tenant-wide Global
Catalog Reader list.

## 2. P4 prerequisite — Data Product Publish workflow (`DP-SVCPERF`, domain DOM-SVCDEL)

**CONFIRMED (2026-08-12):** domain-level roles are assigned via a dedicated **Roles** tab on the
governance domain page (NOT an Edit-button field like the per-product Owner metadata field used in
§1). This tab has four sections — **Governance Domain Owners**, **Governance Domain Readers**,
**Data Product Owners**, **Data Steward** — each with its own add-person icon. Critically,
**"Data Product Owners" here is the REAL RBAC role**, domain-scoped (grants create/update rights on
ALL data products within that domain) — this supersedes the per-product Edit-button "Owner" field
used for Victoria in §1, which is descriptive metadata only (see repo memory: this likely explains
Victoria's earlier 403 deleting a request despite being listed as Customer 360's "Owner").

| Stakeholder | Role | Where | Status |
|---|---|---|---|
| Ranbir Singh | **Governance Domain Owner** on **Service Delivery** (DOM-SVCDEL) | Domain **Roles** tab | ✅ Done — confirmed live (RS now one of 3 owners alongside SK, CZ) |
| Ranbir Singh | **Data Product Owners** (domain-level, real RBAC role covering `DP-SVCPERF`) | Domain **Roles** tab, same page | ✅ Done |
| Shruthi Srinivas | **Data Steward** on **Service Delivery** domain | Domain **Roles** tab, same page | ✅ Done |
| Shruthi Srinivas | **Global Catalog Reader** | Catalog-level, **Settings > Unified Catalog > Roles and permissions** | ✅ Done — confirmed live (5 members: Ci Zhu, Sean Kelley, Rupal Solanki, Victoria Tan, Shruthi Srinivas) |

Expected result: Ranbir Singh appears as both a Governance Domain Owner and a Data Product Owner on
the Service Delivery domain's Roles tab; Shruthi Srinivas appears as a Data Steward on that same
tab, plus the tenant-wide Global Catalog Reader list. All 4 confirmed live.

**Follow-up item — RESOLVED 2026-08-13:** confirmed Victoria Tan was genuinely missing the real
domain-level **Data Product Owners** role on **Customer Operations** (only ever had the Customer
360 metadata Owner field, `ROLE-P3-001`) — matching the hypothesis that this was the root cause of
her earlier 403 on deleting an access request. Added live via the domain **Roles** tab; now one of
3 Data Product Owners (alongside Sean Kelley and "SA"). Recorded in the unified ledger as
`ROLE-P3-004` (`sql/22_victoria_data_product_owners_followup.sql`).

## 3. Workflow-authoring role (confirm, don't reassign)

The user who actually builds each native workflow (Stage 1 of the build template) needs:

- **P3** (Data product access workflow): **Data Product Owner** on `DP-CUST360` — Victoria Tan now
  qualifies after step 1 above; she (or Sean, during build) can author it.
- **P4** (Data product publish workflow, Catalog curation category): **Governance Domain Creator**
  (tenant-level) — Ci Zhu already holds this per `role-directory.csv` and per the `GT-SLA` P1 build.
  Confirm it's still assigned: **Settings > Unified Catalog > Roles and permissions >
  Governance Domain Creator** — Ci Zhu's name should already be listed. If not, add her the same
  way as step 1/2 above.

Ranbir Singh does **not** need Governance Domain Creator himself — he only needs to be the
assigned **approver** inside the workflow Ci Zhu (or Sean) authors, per the wireframe's role-vs-
approver distinction.

## 4. Verification checklist before starting either build

- [ ] Victoria Tan — Data Product Owner, `DP-CUST360`
- [ ] Rupal Solanki — Global Catalog Reader (tenant-wide)
- [ ] Ranbir Singh — Governance Domain Owner, Service Delivery
- [ ] Ranbir Singh — Data Product Owner, `DP-SVCPERF`
- [ ] Shruthi Srinivas — Data Steward, Service Delivery (domain)
- [ ] Shruthi Srinivas — Data Steward, `DP-SVCPERF`
- [ ] Shruthi Srinivas — Global Catalog Reader (tenant-wide)
- [ ] Ci Zhu — Governance Domain Creator (tenant-level, should already be assigned)

There is no API read-back for these role lists (UI-only, confirmed) — the check above is a manual
portal screenshot/visual confirmation, not a scriptable one.

## Next action

Work through §1 (P3) first. Once every P3 checkbox is confirmed, tell me and I'll build
`nb_14_purview_access_sync` and the P3 workflow configuration steps. Don't start §2 (P4) role
assignment until P3's build is closed out, per the wireframe's sequencing commitment.
