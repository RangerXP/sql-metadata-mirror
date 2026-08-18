# `05_publish_governance_domains` — Notebook Description & Artifact Catalog

**Purpose:** Descriptive reference for `05_publish_governance_domains.Notebook` — what it
does, what it consumes/produces, and how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`). For build/debug history and live-run evidence,
see `docs/runbooks/notebook-validation/05_publish_governance_domains.md`.

**Status:** ✅ Validated.

**DEMO_MODE:** No top-level gate — the dry-run artifact write (`Files/purview_publish/*.json`)
always happens; live Purview publish is controlled by `SQL_MIRROR_ONLY_DEPLOYMENT` /
`PURVIEW_PUBLISH_OVERRIDE` / `APPLY_CHANGES`.

**Legacy name(s):** predecessor of `nb_07_publish_to_purview` (domains/data products portion).

---

## What it does

Reads governance domain, data-product, role-assignment, and OKR/ontology tables from
`lh_metadata`, builds Atlas typedef + entity payloads (`EnercareGovernanceDomain`,
`EnercareDataProduct`, `EnercareOKR`, `EnercareOKRKeyResult`), and publishes them to Purview via
the Atlas API. Saves the dry-run typedef/entity payloads to
`Files/purview_publish/{typedefs_day2,entities_day2}.json` on every run regardless of the
live-publish setting, for review/replay.

Purview authentication (Cell 4a) reuses a token cached by another notebook
(`Files/purview_publish/.purview_token_cache.json`) if one is valid, otherwise falls back to a
non-interactive Azure CLI credential -- it never blocks an unattended run on an interactive
sign-in prompt, and this same cache/cascade is shared with `06`/`08`/`09`.

## Artifact catalog

### Inputs consumed

| Source | Feeds |
|---|---|
| `lh_metadata.domains` | `EnercareGovernanceDomain` entities |
| `lh_metadata.data_products` | `EnercareDataProduct` entities (linked to parent domain) |
| `lh_metadata.role_assignments` | Domain/product owner and creator attribution |
| `lh_metadata.okrs` / `okr_key_results` / `okr_data_products` | `EnercareOKR` / `EnercareOKRKeyResult` entities, linked to data products |

### Outputs produced

| Output | Detail |
|---|---|
| `Files/purview_publish/typedefs_day2.json` | Atlas entity-type definitions (dry-run artifact, always written) |
| `Files/purview_publish/entities_day2.json` | Atlas entity payload (dry-run artifact, always written) |
| Purview Atlas entities (live) | 3 governance domains, 3 data products, 3 OKRs, 5 OKR key results — 14 entities total |
| `Files/purview_publish/.purview_token_cache.json` | Shared Purview bearer-token cache, read/written by `05`/`06`/`08`/`09` |

## Demo fit

This is literally "Customer Operations", "Service Delivery", "Revenue and Contracts" domains and
"Customer 360"/"Service Performance"/"Billing and Contract Health" data products appearing in
Purview — the domains/products Ci Zhu references in Act 3. The OKR/key-result layer is the G11-1
ontology extension: business Objectives linked to the same data products, the same way
Purview's native Unified Catalog "Related data products" feature works.

## Talking points

"One notebook, three domains, three data products, published directly via the Atlas API — the
same objects a Purview admin would create by hand in the portal. The OKRs on top of them are
what let a business stakeholder trace a strategic goal down to the governed data product backing
it."

## Dependencies / downstream consumers

- Depends on `02_build_metadata_foundation` having populated `domains`/`data_products`/
  `role_assignments`/`okrs`/`okr_key_results`/`okr_data_products`.
- Shares the Purview token cache (`Files/purview_publish/.purview_token_cache.json`) with
  `06_publish_glossary_and_lineage`, `08_validate_governance_evidence`, and
  `09_reconcile_semantic_model` — a sign-in done in any one of them is reused by the others
  within the token's validity window.
- `06_publish_glossary_and_lineage` publishes the glossary terms/CDEs that link back to these
  same domains.

---

See also: [`04_Notebook_Description.md`](./04_Notebook_Description.md) ·
[`docs/runbooks/notebook-validation/05_publish_governance_domains.md`](./runbooks/notebook-validation/05_publish_governance_domains.md)
