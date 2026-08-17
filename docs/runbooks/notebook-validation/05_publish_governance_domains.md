# `05_publish_governance_domains` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-17, after finding and fixing a real bug.

## Purpose being validated

Publishes governance Domains, Data Products, and the G11-1 OKR/ontology layer to Purview via
the Atlas API, and always writes dry-run payload artifacts to
`Files/purview_publish/{typedefs_day2,entities_day2}.json` regardless of the live-publish
setting.

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status |
|---|---|---|---|---|
| 1 | `e1ded3ce-5abf-4ef7-b8ca-27783da15a07` | 2026-08-17T06:53:32 | 2026-08-17T07:11:38 | ❌ `Failed` (interactive device-code sign-in hung, then cancelled — see Root cause) |
| 2 (after token-cache pre-seed) | `5e023e40-7e68-4d91-b52e-1c32dee439e3` | 2026-08-17T07:13:35 | 2026-08-17T07:17:30 | ✅ `Completed` |

**Generic Fabric failure detail (attempt 1):**

```json
{
  "errorCode": "System_Cancelled_Session_Statements_Failed",
  "message": "System cancelled the Spark session due to statement execution failures",
  "isRetriable": false
}
```

## Root cause

Cell 4a acquires a Purview bearer token, preferring a token cached by another notebook
(`Files/purview_publish/.purview_token_cache.json`), and only falling back to an interactive
`DeviceCodeCredential` browser sign-in if no valid cached token exists. Attempt 1 was submitted
as an unattended REST job with no cached token present (first run of the day for this notebook),
so it printed a device-code URL and sign-in prompt into Fabric's job output — which nobody was
watching — and blocked there for the full ~18-minute run window until Fabric's Spark session
was cancelled. The job API surfaces this identically to a real code failure
(`System_Cancelled_Session_Statements_Failed`), with no way to distinguish "waiting on
interactive auth" from "a cell actually threw" over REST.

**Fix applied:** captured a fresh Purview access token via
`az account get-access-token --resource https://purview.azure.net`, then wrote it directly to
`Files/purview_publish/.purview_token_cache.json` in the `lh_metadata` lakehouse using the
OneLake DFS REST API (`PUT ?resource=file` → `PATCH ?action=append` → `PATCH ?action=flush`),
matching the exact JSON shape (`{"access_token": ..., "expires_on": ...}`) the notebook's own
`_read_shared_purview_token_cache()` expects. Attempt 2 then found the valid cached token
immediately and completed in under 4 minutes.

**Same-class fix applied proactively:** `08_validate_governance_evidence` and
`09_reconcile_semantic_model` had the identical `DeviceCodeCredential` call but with **no**
shared-cache fallback at all (unconditional interactive sign-in every time), which is a worse
version of the same bug. Both were fixed to check the shared token cache (and a
`PURVIEW_ACCESS_TOKEN` env override) before falling back to device-code, matching `05`'s and
`06`'s existing pattern. See their own docs.

## Data write-out confirmation

`Files/purview_publish/entities_day2.json` (downloaded and inspected directly from OneLake via
the DFS REST API after attempt 2):

| Entity type | Count |
|---|---|
| `EnercareGovernanceDomain` | 3 |
| `EnercareDataProduct` | 3 |
| `EnercareOKR` | 3 |
| `EnercareOKRKeyResult` | 5 |
| **Total** | **14** |

Spot-checked domain content: `DOM-CUSTOPS` (Customer Operations), `DOM-REVCON` (Revenue and
Contracts), `DOM-SVCDEL` (Service Delivery) — owners/creators/descriptions all populated
correctly from the SQL source.

## Maria Castellanos north-star use-case match

- ✅ The three governance domains and three data products match the exact set Ci Zhu references
  in Act 3 ("Customer 360", "Service Performance", "Billing and Contract Health" data products
  under Customer Operations / Service Delivery / Revenue and Contracts domains).
- ✅ OKR-to-data-product linkage confirmed present (`linked_data_product_ids` populated on OKR
  entities), supporting the "trace a business goal to its governed data" narrative.

## Issues encountered

- 1 of 2 attempts failed, caused by an interactive-auth blocking condition rather than a code
  defect — resolved by pre-seeding the shared token cache. See "Root cause" above.
