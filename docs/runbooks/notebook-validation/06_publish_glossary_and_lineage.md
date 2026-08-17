# `06_publish_glossary_and_lineage` — Validation Capture

**Status:** ✅ Completed — validated end-to-end 2026-08-17, after finding and fixing four real bugs.

## Purpose being validated

Two merged sections: Cells 1–5 (glossary/CDE Atlas publish + term self-heal) and Cells 6–11
(sensitivity labels, CDE classifications, and custom Atlas lineage edge publish).

## Run record

| Attempt | Job ID | Start (UTC) | End (UTC) | Status |
|---|---|---|---|---|
| 1 | `223c2941-8136-4c20-8e0d-59b14271879a` | 2026-08-17T08:00:53 | 2026-08-17T08:05:21 | ❌ `Failed` |
| 2 (after DROP TABLE generalization) | `0ddd45b8-09a0-40fa-85fd-bc4f9e4e3ae5` | 2026-08-17T15:21:07 | 2026-08-17T15:40:45 | ❌ `Failed` |
| 3 (after CDE_COLUMNS_NEEDED fix) | `77264e48-b255-4025-9f85-623dd3ffe18d` | 2026-08-17T16:57:39 | 2026-08-17T17:17:52 | ❌ `Failed` |
| 4 (after diagnostic wrap + Cell 6 endpoint fix) | `c8a91f6f-8e2d-4e82-813b-2c992669568e` | 2026-08-17T17:19:02 | 2026-08-17T17:31:39 | ✅ `Completed` |

**Generic Fabric failure detail (identical across all 3 failed attempts):**

```json
{
  "errorCode": "System_Cancelled_Session_Statements_Failed",
  "message": "System cancelled the Spark session due to statement execution failures",
  "isRetriable": false
}
```

## Root cause 1 — stale Delta column-mapping ID on `glossary_terms`

Diagnostic instrumentation already present in this notebook (`nb08_diagnostics_log`, inherited
from the pre-consolidation `nb_08_purview_glossary_cde`) captured the real exception on attempt 1:

```
stage: cell3_build_payloads
error_type: Py4JJavaError
error_message: An error occurred while calling o6019.collectToPython.
: java.lang.IllegalStateException: Couldn't find previous_definition#63 in
  [term_code#48,term_name#49,acronyms#50,parent_term_code#51,domain_code#52,owner_upn#53,
   additional_owners_upn#54,definition#55,status#56,is_cde#57,industry_origin#58,resources#59,
   bound_assets#60,approved_by#61,approved_at#62]
```

`previous_definition` was neither in the current physical schema (confirmed via
`INFORMATION_SCHEMA.COLUMNS`) nor referenced anywhere in this notebook's Python code — a
genuinely phantom, stale attribute ID from Spark's cached plan, matching the same class of bug
as the historical 2026-08-10 OKR `progress_amount` all-NULL-column fix.

**Fix applied:** generalized `02_build_metadata_foundation.Notebook`'s `write_table_from_pandas()`
to `DROP TABLE IF EXISTS {full_table}` before every table overwrite — previously this guard was
scoped only to `okr_key_results` (the one table the 2026-08-10 fix originally covered). Applying
it universally purges stale column-mapping IDs for `glossary_terms` and every other written
table, not just the one that happened to be diagnosed first.

## Root cause 2 — phantom columns hardcoded in `CDE_COLUMNS_NEEDED`

After the DROP TABLE fix, attempt 2 failed with a different but same-shaped error:

```
stage: cell3_build_payloads
error_message: ... IllegalStateException: Couldn't find steward_upn#172 in
  [cde_id#164,cde_name#165,expected_data_type#166,business_definition#167,owner_role#168,
   status#169,parent_glossary_term#170,bound_columns#171]
```

Cross-checked against `02_build_metadata_foundation`'s actual CDE ingestion column list
(`cde_required`) and the live `cdes` table schema: `steward_upn`, `cde_code`, `domain_code`,
`sensitivity_label`, `owner_upn`, `validation_rule`, and `description` never existed in the CDE
data model at all — a real bug in this notebook's own `CDE_COLUMNS_NEEDED` constants (both the
Cell 2 and Cell 7 copies), not a data pipeline gap.

**Fix applied:** trimmed both `CDE_COLUMNS_NEEDED` lists to only the 6–8 columns that genuinely
exist in the source, matching the ingestion contract exactly.

## Root cause 3 — missing diagnostic instrumentation on both live-publish blocks

Attempt 3 (after the CDE fix) ran the full ~20-minute duration and still failed, but neither
`nb08_diagnostics_log` nor `nb09_diagnostics_log` gained a new row — meaning the real failure
was happening in a cell with **no exception logging at all**. Inspection found Cell 5 (glossary/
CDE Atlas publish, including the ~35-term self-heal loop) and Cell 11 (labels/lineage Atlas
publish) were both large `else:` blocks with zero diagnostic instrumentation, unlike every other
cell in this notebook.

**Fix applied:** wrapped both blocks in `try/except` with `_log_nb08_diagnostic("cell5_live_publish", ex)`
/ `_log_nb09_diagnostic("cell11_live_publish", ex)`. Given the blocks span ~280 and ~690 lines
respectively, the re-indentation was done via a small one-off Python script operating on exact
line-index boundaries (verified by unique-content search, not assumed line numbers) rather than
manual retyping, to avoid introducing an indentation bug in such a large edit.

## Root cause 4 — Purview endpoint/account misconfiguration in Cell 6

A manual interactive portal run of the labels/lineage phase raised:

```
RuntimeError: PURVIEW_API_BASE_URL/PURVIEW_PRIVATE_ENDPOINT_URL/PURVIEW_PRIVATE_BASE_URL is not
set. ... The public hostname https://Purview-West3.purview.azure.com will fail in
private-network Fabric runtimes.
```

Cell 6's `_resolve_purview_base_url()` hard-raised instead of falling back to the public
Purview hostname the way Cell 1's identical-purpose resolver does — and Cell 6 also defaulted
to the wrong account (`Purview-West3` instead of `Purview-West2`, the account actually hosting
the live glossary/Unified Catalog used by Cell 1's already-proven-working phase).

**Fix applied:** aligned Cell 6's resolver and account-name default to exactly match Cell 1's.

## Platform gotcha encountered during this investigation

A manual interactive Fabric portal session was open on this same notebook concurrently with
scripted git-sync + REST job attempts, causing `POST git/updateFromGit` to fail with
`MissingWorkspaceConflictResolution`. Fixed by adding explicit
`conflictResolution: {conflictResolutionType: "Workspace", conflictResolutionPolicy: "PreferRemote"}`
to `tools/sync_fabric_git.py` — git-side fixes now always win the sync.

## Data write-out confirmation (attempt 4, successful)

- Glossary terms: 35/35 created/existing, self-heal applied where needed.
- CDEs: 12/12 `EnercareCriticalDataElement` entities published.
- CDE-to-GlossaryTerm associations: 12/12 assigned, 0 unresolved.
- `nb08_diagnostics_log`: 3 rows total, all from pre-fix attempts — zero new rows on the
  successful run.

## Maria Castellanos north-star use-case match

- ✅ `GT-SLA`, `GT-CONSENT`, `CDE-CONTRACTAMT`, `CDE-CONSENTSTATE` and the rest of Maria's
  scenario's referenced terms/CDEs are live Atlas entities with correct associations.
- ✅ Custom lineage edges give Ci Zhu's audit walkthrough its "click View lineage" proof point.

## Issues encountered

- 3 of 4 attempts failed across two independent stale-schema bug classes plus one missing-
  instrumentation gap plus one endpoint-config bug — all four resolved and re-verified live. See
  "Root cause" sections above for the full investigation trail.
