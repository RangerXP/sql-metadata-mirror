# `05_publish_governance_domains` — Notebook Description & Artifact Catalog

**Purpose:** Full descriptive reference for `05_publish_governance_domains.Notebook` — what it
does, what it consumes/produces, how it fits the Maria Castellanos north-star scenario
(`docs/purview-maria-north-star-scenario.md`), and its live-validation history.

**Status:** ✅ Live-validated end-to-end 2026-08-17, after finding and fixing a real bug (see
`docs/runbooks/notebook-validation/05_publish_governance_domains.md` for the full run evidence).

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
(`Files/purview_publish/.purview_token_cache.json`) if one is valid, and only falls back to an
interactive device-code sign-in if no cached token exists — see the git-sync/token-cache
pitfall documented in the validation doc.

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

## Live-validation findings

| Finding | Detail | Status |
|---|---|---|
| **Interactive device-code sign-in blocks unattended runs** | Cell 4a falls back to an interactive `DeviceCodeCredential` browser sign-in if no valid cached Purview token exists. Submitted as an unattended REST job with no cached token present, the notebook silently hung for ~18 minutes waiting for a human to complete a sign-in that never came, then Fabric cancelled the session (`System_Cancelled_Session_Statements_Failed` — indistinguishable from a real code failure over the REST API). | ✅ **Fixed 2026-08-17.** Pre-seeded the shared token cache (`Files/purview_publish/.purview_token_cache.json`) directly via the OneLake DFS REST API using a token captured with `az account get-access-token --resource https://purview.azure.net`, so the notebook's existing cache-first fallback picked it up instead of blocking. Re-run completed in ~4 minutes. Applied the same defensive fix (shared-cache read before any device-code fallback) to `08_validate_governance_evidence` and `09_reconcile_semantic_model`, which had the identical unconditional device-code call with no cache fallback at all — see their docs. |
| **Data output confirmed correct** | Dry-run `entities_day2.json` inspected directly from OneLake: 3 `EnercareGovernanceDomain`, 3 `EnercareDataProduct`, 3 `EnercareOKR`, 5 `EnercareOKRKeyResult` — 14 entities total, matching the expected demo scale. | ✅ Confirmed. |

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
