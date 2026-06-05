# CSV-to-Purview Brief Alignment

**Purpose:** Map every required field from `docs/purview-governance-brief.md` Phases 1–5 to the corresponding column in the customer-files CSVs, with the source phase/step reference and any deliberate deviations called out.

**Date:** 2026-06-04
**Brief version:** docs/purview-governance-brief.md (37KB, 32 MS Learn sources)

---

## 1. domain-charter.csv — alignment to Phase 2

| Purview field | Brief reference | CSV column | Status | Notes |
|---|---|---|---|---|
| Name | Phase 2.1 ("Name, description, select Type, leave Parent blank") | `domain_name` | ✅ | |
| Description | Phase 2.1 | `description` | ✅ | |
| Type | Phase 2.1 — values from [Create governance domains](https://learn.microsoft.com/en-us/purview/unified-catalog-governance-domains-create-manage): Data domain / Functional unit / Line of business / Regulatory / Project | `domain_type` | ✅ | Values match enum exactly |
| Parent | Phase 2.1 ("leave Parent blank (flat hierarchy at MVP)") | `parent_domain_code` | ✅ | All blank — flat 3-domain MVP |
| **>=2 Governance Domain Owners** | Phase 2.2 ("add at least 2 Governance Domain Owners") | `domain_owner_1_upn`, `domain_owner_2_upn` | ✅ | Was a gap in v1; now fixed |
| Data Stewards (roles tab) | Phase 2.2 | sourced from `role-directory.csv` | ✅ | See Section 6 |
| Data Product Owners (roles tab) | Phase 2.2 | sourced from `role-directory.csv` | ✅ | See Section 6 |
| Data estate mappings (optional) | Phase 2.3 | `scan_collections` | ✅ | "Enercare" collection |
| Status | Phase 2.4 ("Publish the domain") | `published_status` | ✅ | All "Published" |

**Deliberate deviation:**
- **Domain names**: Brief's Phase 2 example names ("Customer 360 / Operations / Compliance") were generic. The Enercare project's `design-gap-analysis.md` (G8-3) specifies these exact names: "Customer Operations / Service Delivery / Revenue and Contracts". Keeping the project-specific names; flagged here so the brief drift is documented.

---

## 2. data-product-catalog.csv — alignment to Phase 3

| Purview field | Brief reference | CSV column | Status | Notes |
|---|---|---|---|---|
| Name | Phase 3.1 | `product_name` | ✅ | |
| **Type** | Phase 3.1 — values per [data product types](https://learn.microsoft.com/en-us/purview/unified-catalog-data-products-create-manage): "Dataset, Dashboards/Reports, Master and reference data" | `product_type` | ✅ | Was missing in v1; fixed. Customer 360 = Master and reference data; SVCPERF & BILLHEALTH = Dataset |
| Governance domain | Phase 3.2 | `domain_code` | ✅ | |
| **Business use case** | Phase 3.2 ("set the governance domain, business use case, and audience") | `business_use_case` | ✅ | Was missing in v1; fixed |
| **Audience** | Phase 3.2 | `audience` | ✅ | Was missing in v1; fixed |
| Owners | Phase 3.2 ("Add owners") | `owner_upn`, `owner_name` | ✅ | Each product has a single executive Owner; steward in separate column |
| Data assets | Phase 3.3 ("Add data assets: search scoped to the mapped collection") | `sql_assets`, `fabric_assets`, `semantic_model_assets` | ✅ | Qualified names — Purview resolves at attachment time |
| **Permitted access purposes** (3 default) | Phase 3.4 | `permitted_purposes` | ✅ | Was missing in v1; fixed. Semicolon-separated |
| **Approval requirements** (manager / privacy / reviewer tiers) | Phase 3.4 | `approval_requirements` | ✅ | Was missing in v1; fixed |
| **Access request approvers** | Phase 3.4 | `access_approvers` | ✅ | Was missing in v1; fixed. Semicolon-separated UPNs |
| Status | Phase 3.5 ("Publish on the data product") | `published_status` | ✅ | All "Published" |

**Deliberate deviation:**
- **Product count**: Brief's Phase 3 header says "Build 3 data products per domain" (= 9 total) but the brief's Conclusion also accepts 1 per domain. The Enercare project `design-gap-analysis.md` (G8-3) explicitly specifies 3 total (one per domain) for MVP. Keeping 3; can expand to 9 by adding 2 more per domain after MVP acceptance.

---

## 3. cde-catalog.csv — alignment to Phase 4.5

| Purview field | Brief reference | CSV column | Status | Notes |
|---|---|---|---|---|
| Name | Phase 4.5 ("Name, owner, expected data type") | `cde_name` | ✅ | |
| Owner | Phase 4.5 | `owner_upn` | ✅ | |
| **Expected data type** (number / text / date / Boolean) | Phase 4.5 — REQUIRED by Purview CDE schema per [Critical Data Elements (Preview)](https://learn.microsoft.com/en-us/purview/unified-catalog-critical-data-elements) | `expected_data_type` | ✅ | **Was missing in v1; this is required by the Purview API and would have blocked ingestion. Now fixed.** Values: text (10), number (2) |
| Add column → linked columns | Phase 4.6 ("map equivalent columns across data assets") | `bound_columns` | ✅ | Semicolon-separated qualified column names |
| Status | Phase 4.7 ("Update CDE status to Published") | `status` | ✅ | Was implicit; now explicit. All "Published" |

**Custom enrichment (kept as Purview ignores unknown columns):**
- `regulator`, `regulator_basis` — links each CDE to the regulating body (PIPEDA, CASL, PCI DSS, OEB, OCPA). Not a Purview field but supports the demo's compliance narrative.
- `validation_rule` — regex/format constraint. Not a Purview field but documents the data shape.
- `sensitivity_label` — informational; the actual label applies via Phase 5.

**Note on preview status:** Per brief Decision Note #7, CDEs are flagged as preview. Build is current at REST API version `2026-03-20-preview`.

---

## 4. glossary-master.csv — alignment to Phase 4.1

| Purview field | Brief reference | CSV column | Status | Notes |
|---|---|---|---|---|
| Name | Phase 4.1 ("Add owners, parent term (optional), acronyms, resources") | `term_name` | ✅ | |
| Owners (plural) | Phase 4.1 | `owner_upn` + `additional_owners_upn` | ✅ | Was singular in v1; now supports primary + additional |
| Parent term (optional) | Phase 4.1 | `parent_term_code` | ✅ | Used for term hierarchy (e.g., GT-SVCACCT inherits from GT-ACCOUNT) |
| Acronyms | Phase 4.1 | `acronyms` | ✅ | Was `acronym` (singular) in v1; renamed for brief alignment |
| **Resources** | Phase 4.1 | `resources` | ✅ | **Was missing in v1; now populated.** External: regulator URLs (PIPEDA, OEB, OCPA, CASL, PCI). Internal: enercare.ca/about/governance/glossary placeholders |
| Definition | Phase 4.1 (implicit; required for Term creation) | `definition` | ✅ | |
| Status | Phase 4.3 ("Publish the term") | `status` | ✅ | All "Published" |
| Related (data products, assets, columns, CDEs) | Phase 4.4 ("Open a term -> Related tab -> Add data product / Add data assets / Add column / Add critical data element") | `bound_assets`, `is_cde` | ✅ | `is_cde=1` flag links to cde-catalog.csv via term_code; `bound_assets` covers asset/column links |

**Custom enrichment:**
- `industry_origin` — categorizes terms as Utility / Canadian Regulatory / Finance / Service Industry / Generic. Useful for filtering during glossary review; not a Purview field.

**Glossary parent/child depth:** Currently 2 levels (parent terms: GT-ACCOUNT → GT-SVCACCT; GT-SVCREQ → GT-WORKORDER; GT-MRR → GT-ARR; GT-CONTRACT → GT-AUTORENEW; GT-PII → GT-GEOPII). Brief supports up to 5 levels; flagged in design doc §8.2 as an open decision if deeper hierarchy is desired.

---

## 5. label-policy.csv — alignment to Phase 5

| Purview field | Brief reference | CSV column | Status | Notes |
|---|---|---|---|---|
| Label name | Phase 5.2 ("Create or confirm 3 pilot labels") | `label_name` | ✅ | |
| Label order | Phase 5.2 (label ordering implicit in Purview Information Protection) | `label_order` | ✅ | 1–4 |
| Scope (Files & other data assets) | Phase 5.2 ("Scope must include Files & other data assets to be usable by Fabric") | `scope` | ✅ | "Tenant" with Fabric Lakehouse / Semantic Model enforcement targets |
| Label policy publication | Phase 5.3 ("Publish via a label policy to the pilot users/groups") | `policy_row_type` rows of LABEL | ✅ | |
| Protection settings (Control access) | Phase 5.4 ("For Confidential, configure protection settings to Control access") | `assignment_rule` (mandatory rule rows) | ✅ | Mandatory rules ensure Confidential / Highly Confidential apply to specific data products |
| Auto-apply via classifier match | Phase 5 implication | `assignment_rule` (auto-apply rule rows) | ✅ | Rule rows tie to classifier outputs including the custom ENERCARE.PRIVACY.SIN_BACKSTOP |
| Owner | n/a (informational) | `owner_upn` | ✅ | Ci Zhu (Label Policy Owner functional role) |

**Deliberate deviation:**
- **4 labels, not 3**: Brief Decision Note #5 says "Three labels (Public, Internal, Confidential) plus a single Protection Policy on Confidential is enough." This design uses 4 labels (General, Internal, Confidential, Highly Confidential). Rationale: the dataset has materially different sensitivity tiers — Confidential covers customer PII (name, email, address); Highly Confidential covers regulated identifiers (SIN, payment partials). Collapsing the two would understate the difference for the audience. Both labels can be enforced via a single Protection Policy on Highly Confidential to stay within the brief's 50-policy cap.

---

## 6. role-directory.csv — alignment to Minimum Required Roles table

The role directory now uses Purview's exact taxonomy. The `purview_role_name` column carries the canonical Purview role name; `is_purview_native` is 1 for catalog/data-map/IP-admin roles and 0 for custom functional bookkeeping (Privacy Officer, Glossary Owner, Label Policy Owner — kept for project-management traceability but clearly flagged as non-Purview).

| Brief role (Minimum Required Roles table) | Surface | CSV row coverage |
|---|---|---|
| Data Governance Administrator | Tenant | Ci Zhu (1), Alison Pouw (cover), Sean Kelley (backup) |
| Governance Domain Creator | Catalog | Ci Zhu (1), Alison Pouw (cover) |
| Governance Domain Owner (>=2 per domain) | Domain | DOM-CUSTOPS: Victoria + Ci Zhu. DOM-SVCDEL: Ranbir + Ci Zhu. DOM-REVCON: Ci Zhu + Ranbir |
| Data Product Owner (per domain) | Domain | Victoria (DP-CUST360), Ranbir (DP-SVCPERF), Ci Zhu (DP-BILLHEALTH) |
| Data Steward (per domain) | Domain | Rupal (DOM-CUSTOPS + DP-CUST360), Shruthi (DOM-SVCDEL + DP-SVCPERF), Ci Zhu (DOM-REVCON + DP-BILLHEALTH), Rupal backup (DOM-REVCON) |
| **Global Catalog Reader** (All pilot consumers) | Domain | Victoria, Ranbir, Ci Zhu, Rupal, Shruthi + Brian Lung, Sean Kelley, Naunihal Singh Sidhu (Microsoft observers). **Was missing in v1.** |
| **Data Reader (on SQL & Fabric collections)** — required for asset attachment | Data Map | Victoria, Ranbir, Ci Zhu, Rupal, Shruthi + Sean Kelley, Alison Pouw. **Was missing in v1. This is the brief's repeatedly-flagged dual-permission rule.** |
| Information Protection Admin | Purview IP | Ci Zhu (1), Alison Pouw (cover) |
| Fabric Admin | Fabric Tenant | Sean Kelley (build-time cover; transfers to Enercare IT post-handoff) |
| Workspace Member / Admin | Fabric Workspace | Rupal, Shruthi (Member), Ci Zhu (Admin) — required to apply sensitivity labels per Phase 5.6 |
| Data Source Administrator | Purview Account | Ajay Jagannathan |
| Data Curator | Collection (Enercare) | Alison Pouw, Ajay Jagannathan |

**Pre-mortem mitigation:** Brief's pre-mortem #2 specifically flags: "Data Product Owners can publish data products but cannot add assets because they lack Data Map Data Reader on the source collection." Mitigation: pair every domain-role assignment with a corresponding Data Map collection-role assignment. Every Data Product Owner and Data Steward now has an explicit `Data Reader / Data Map / Collection / Enercare` row in the directory.

**Custom functional roles** (kept for traceability, marked `is_purview_native=0`):
- Privacy Officer (Victoria) — Purview equivalent is just "owner" on PIPEDA-related glossary terms and CDEs
- Glossary Owner (Ci Zhu) — Purview equivalent is per-term owner
- Label Policy Owner (Ci Zhu) — Purview equivalent is the Information Protection Admin role (also assigned)

---

## 7. Summary — gap closure

| Gap from v1 (critical) | Resolution |
|---|---|
| CDE `expected_data_type` missing (required field) | Added to all 12 CDEs (text or number) |
| Data Product missing Type, business_use_case, audience, access policies | Added 5 new columns |
| Domain charter has 1 owner per domain (brief requires >=2) | Added domain_owner_2 column populated for all 3 domains |
| Glossary missing resources column | Added with regulator + internal references |
| Role taxonomy drift ("Domain Owner" not "Governance Domain Owner") | Renamed; `purview_role_name` column carries the exact taxonomy |
| Missing Global Catalog Reader rows | Added for all pilot consumers |
| Missing Data Reader on collection rows (dual-permission) | Added explicit rows for every Owner + Steward |
| Missing Information Protection Admin role | Added (Ci Zhu primary; Alison Pouw cover) |
| Missing Fabric Admin role | Added (Sean Kelley build-time cover) |
| Missing Workspace Member/Admin role for label applier | Added (Rupal, Shruthi, Ci Zhu) |

All ❌ blockers from the audit are now resolved. The CSVs are aligned to the brief's Phase 1–5 schema requirements.

## 8. Deliberate deviations (called out for review)

1. **Domain names** = "Customer Operations / Service Delivery / Revenue and Contracts" rather than the brief's generic "Customer 360 / Operations / Compliance" — to match the project's G8-3 spec in `design-gap-analysis.md`.
2. **Product count** = 3 (one per domain) for MVP rather than 9 (three per domain) — also per G8-3 spec. Expansion path documented.
3. **Label count** = 4 (added Highly Confidential) rather than the brief's recommended 3 — to differentiate SIN / payment partials from general customer PII.

Each is a conscious project-level choice, not an oversight.
