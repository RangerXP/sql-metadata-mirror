# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "d4ba455b-9b80-46dd-afe8-d0b877b3a5d2",
# META       "default_lakehouse_name": "lh_metadata",
# META       "default_lakehouse_workspace_id": "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4",
# META       "known_lakehouses": [
# META         {
# META           "id": "d4ba455b-9b80-46dd-afe8-d0b877b3a5d2"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Fabric Notebook: nb_05_push_qa_verified_answers
# Purpose: Read ai_instruction + verified_answer rows from lh_metadata.ai_metadata,
#          build an enhanced PBI_AI_Instructions annotation that includes both
#          AI instructions and verified Q&A pairs, and push to the semantic model
#          via Fabric REST API (updateDefinition on model.tmdl only).
#
# DEMO_MODE = True  → dry-run (prints annotation preview, no write)
# DEMO_MODE = False → live (fetches TMDL, injects annotation, pushes)
#
# Run order: after nb_04a (ai_metadata must exist with IsDraft=0 rows)
# Default lakehouse: lh_metadata

DEMO_MODE              = False
WORKSPACE_ID           = "795ce5db-7ea0-4a7c-ba64-e27c9fb568f4"
MODEL_NAME             = "BrookfieldEnercare"
METADATA_LH            = "lh_metadata"
MAX_ANNOTATION_CHARS   = 3800   # safe limit for PBI_AI_Instructions
TRIGGER_DATA_REFRESH   = True   # True → fires Power BI Data refresh after annotation push
                                 # Required to frame new Direct Lake tables (e.g. fct_cc_interactions)

print(f"nb_05_push_qa_verified_answers  |  DEMO_MODE={DEMO_MODE}  |  TRIGGER_DATA_REFRESH={TRIGGER_DATA_REFRESH}")
print(f"Workspace: {WORKSPACE_ID}  |  Target model: {MODEL_NAME}")
print(f"Max annotation chars: {MAX_ANNOTATION_CHARS}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ── Cell 2: Read ai_metadata ──────────────────────────────────────────────────
# Reads all IsDraft=0 rows from ai_metadata.
# Splits into two lists by RecordType:
#   - ai_instruction  → grounding instructions for Copilot
#   - verified_answer → Q&A pairs (TriggerText=question, ResponseText=answer)

ai_df = spark.sql(f"""
    SELECT RecordType, TriggerText, ResponseText, LinkedKPICode
    FROM {METADATA_LH}.ai_metadata
    WHERE IsDraft = 0
    ORDER BY RecordType, RecordID
""")
ai_rows = ai_df.collect()

ai_instructions   = list(dict.fromkeys(r.ResponseText for r in ai_rows if r.RecordType == "ai_instruction" and r.ResponseText))

# Deduplicate verified_answers by (TriggerText, ResponseText) — keeps first occurrence
_seen_qa = set()
verified_answers = []
for r in ai_rows:
    if r.RecordType == "verified_answer" and r.ResponseText:
        key = (r.TriggerText, r.ResponseText)
        if key not in _seen_qa:
            _seen_qa.add(key)
            verified_answers.append(r)

print(f"Loaded: {len(ai_instructions)} AI instruction(s), {len(verified_answers)} verified answer(s)")

if verified_answers:
    from collections import Counter
    kpi_counts = Counter(r.LinkedKPICode or "unlinked" for r in verified_answers)
    print("  Verified answers by KPI:")
    for kpi, cnt in sorted(kpi_counts.items()):
        print(f"    {kpi}: {cnt}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ── Cell 3: Fetch TMDL via Fabric REST API ────────────────────────────────────
# Reuses the same _post_lro pattern as nb_04 Cell 3.

import requests
import base64
import time

token   = mssparkutils.credentials.getToken("pbi")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type":  "application/json",
}

FABRIC_API = "https://api.fabric.microsoft.com/v1"

models_resp = requests.get(
    f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/semanticModels",
    headers=headers,
)
models_resp.raise_for_status()
MODEL_ID = next(
    m["id"] for m in models_resp.json()["value"]
    if m["displayName"] == MODEL_NAME
)
print(f"Found model: {MODEL_NAME}  ({MODEL_ID})")


def _post_lro(url, hdrs, max_wait=120):
    """POST to a Fabric LRO endpoint; poll Location/result until Succeeded."""
    resp = requests.post(url, headers=hdrs)
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code != 202:
        resp.raise_for_status()
    loc        = resp.headers["Location"]
    retry_secs = int(resp.headers.get("Retry-After", 20))
    waited     = 0
    while waited < max_wait:
        time.sleep(retry_secs)
        waited += retry_secs
        r = requests.get(loc, headers=hdrs)
        if r.status_code == 200 and r.json().get("status") == "Succeeded":
            result = requests.get(f"{loc}/result", headers=hdrs)
            result.raise_for_status()
            return result.json()
        if r.status_code not in (200, 202):
            r.raise_for_status()
    raise TimeoutError(f"LRO timed out after {max_wait}s: {url}")


defn_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/semanticModels/{MODEL_ID}/getDefinition"
defn     = _post_lro(defn_url, headers, max_wait=300)

tmdl_files = {
    part["path"]: base64.b64decode(part["payload"]).decode("utf-8")
    for part in defn["definition"]["parts"]
}
print(f"Fetched {len(tmdl_files)} TMDL parts from {MODEL_NAME}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ── Cell 4: Build enhanced PBI_AI_Instructions annotation ─────────────────────
# Format:
#   {instructions joined by ' | '}
#   | VERIFIED Q&A: Q: {TriggerText} -> {ResponseText[:180]} | ...
#
# Truncated at MAX_ANNOTATION_CHARS on a clean ' | ' boundary.

import re


def _safe(text: str) -> str:
    """Escape text for TMDL string literal (double → single quote)."""
    return text.replace('"', "'").strip()


def inject_ai_instructions(content: str, instructions_text: str) -> str:
    """Add/replace PBI_AI_Instructions annotation in model.tmdl."""
    new_ann = f'annotation PBI_AI_Instructions = "{_safe(instructions_text)}"'
    if "annotation PBI_AI_Instructions" in content:
        return re.sub(r'annotation PBI_AI_Instructions = "[^"]*"', new_ann, content)
    return re.sub(r'(ref table)', f'{new_ann}\n\n\\1', content, count=1)


# Instructions block
instr_block = " | ".join(_safe(t) for t in ai_instructions) if ai_instructions else ""

# Verified Q&A block: "Q: {question} -> {answer (truncated to 180 chars)}"
qa_parts = [
    f"Q: {_safe(r.TriggerText)} -> {_safe(r.ResponseText[:150])}"
    for r in verified_answers
    if r.TriggerText
]
qa_block = " | ".join(qa_parts) if qa_parts else ""

# Combine
if instr_block and qa_block:
    combined = f"{instr_block} | VERIFIED Q&A: {qa_block}"
elif qa_block:
    combined = f"VERIFIED Q&A: {qa_block}"
else:
    combined = instr_block

# Truncate at clean ' | ' boundary if over limit
if len(combined) > MAX_ANNOTATION_CHARS:
    truncated = combined[:MAX_ANNOTATION_CHARS]
    last_sep  = truncated.rfind(" | ")
    combined  = truncated[:last_sep] if last_sep > 0 else truncated
    print(f"  [WARN] Annotation truncated to {len(combined)} chars (limit={MAX_ANNOTATION_CHARS})")

print(f"Annotation length: {len(combined)} chars")
print(f"  Instructions: {len(ai_instructions)}, Q&A pairs: {len(qa_parts)}")
print(f"\n--- Annotation preview (first 500 chars) ---")
print(combined[:500])
print("..." if len(combined) > 500 else "")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ── Cell 5: Inject annotation and push model.tmdl ────────────────────────────
# Only model.tmdl is modified — minimal diff, fastest push.
# DEMO_MODE=True: prints what would be injected, no write.
# DEMO_MODE=False: injects and pushes via updateDefinition.

model_path = "definition/model.tmdl"
updated    = inject_ai_instructions(tmdl_files[model_path], combined)

if DEMO_MODE:
    print("[DRY RUN] model.tmdl would be updated with PBI_AI_Instructions annotation.")
    print("Set DEMO_MODE = False and re-run to apply.\n")
else:
    tmdl_files[model_path] = updated

    parts = [
        {
            "path":        path,
            "payload":     base64.b64encode(c.encode("utf-8")).decode("utf-8"),
            "payloadType": "InlineBase64",
        }
        for path, c in tmdl_files.items()
    ]
    body     = {"definition": {"format": "TMDL", "parts": parts}}
    push_url = (
        f"{FABRIC_API}/workspaces/{WORKSPACE_ID}"
        f"/semanticModels/{MODEL_ID}/updateDefinition"
    )
    push_resp = requests.post(push_url, headers=headers, json=body)
    if push_resp.status_code not in (200, 202):
        print(f"ERROR {push_resp.status_code}:\n{push_resp.text}")
    elif push_resp.status_code == 202:
        # updateDefinition is async — poll until Web Modeling refresh completes
        # CRITICAL: Data refresh (Cell 7) must not start until this finishes,
        # otherwise updateDefinition's Web Modeling refresh will invalidate the frame.
        lro_loc    = push_resp.headers.get("Location", "")
        retry_secs = int(push_resp.headers.get("Retry-After", 10))
        print(f"  updateDefinition accepted (202). Waiting for Web Modeling refresh...")
        wm_waited = 0
        wm_done   = False
        while wm_waited < 180:
            time.sleep(retry_secs)
            wm_waited += retry_secs
            r = requests.get(lro_loc, headers=headers)
            wm_status = r.json().get("status", "Unknown") if r.status_code in (200, 202) else "Error"
            print(f"    [{wm_waited:3d}s] Web Modeling status={wm_status}")
            if wm_status == "Succeeded":
                wm_done = True
                break
            if wm_status in ("Failed", "Cancelled", "Error"):
                print(f"  Web Modeling refresh ended with status={wm_status}")
                break
        if wm_done:
            print(f"SUCCESS — {MODEL_NAME} semantic model updated. Web Modeling refresh complete.")
        else:
            print(f"  [WARN] Web Modeling refresh did not confirm Succeeded within 180s — proceeding.")
    else:
        print(f"SUCCESS — {MODEL_NAME} semantic model updated (200 synchronous).")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ── Cell 6: Summary ───────────────────────────────────────────────────────────

from collections import Counter

print("\n=== nb_05 Summary ===")
print(f"  Model:              {MODEL_NAME} ({MODEL_ID})")
print(f"  AI instructions:    {len(ai_instructions)}")
print(f"  Verified Q&A pairs: {len(qa_parts)}")
print(f"  Annotation chars:   {len(combined)} / {MAX_ANNOTATION_CHARS}")

if verified_answers:
    kpi_counts = Counter(r.LinkedKPICode or "unlinked" for r in verified_answers)
    print("\n  Q&A coverage by KPI:")
    for kpi, cnt in sorted(kpi_counts.items()):
        print(f"    {kpi:<20} {cnt} answer(s)")

mode_tag = "DRY RUN — no changes written" if DEMO_MODE else "APPLIED — semantic model updated"
print(f"\n  Status: {mode_tag}")
print("\nTo verify: ask Copilot 'what is our FCR?' or 'what is our CSAT score?'")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# ── Cell 7: Trigger Power BI Data Refresh (frames Direct Lake tables) ─────────
# Web Modeling refreshes (from updateDefinition in Cell 5) update TMDL metadata
# only — they do NOT re-frame Delta tables in Direct Lake mode.
# A separate "Data" refresh via the Power BI REST API is required to:
#   - Create the columnar frame for new Direct Lake tables (fct_cc_interactions, etc.)
#   - Resolve "table is not refreshed" errors in Copilot and reports
#
# TRIGGER_DATA_REFRESH = True  → fires and polls to completion (~30–90 s)
# TRIGGER_DATA_REFRESH = False → prints instructions, no API call

import time as _time

PBI_API_GROUPS = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{MODEL_ID}"

if not TRIGGER_DATA_REFRESH or DEMO_MODE:
    print("[SKIPPED] Data refresh not triggered.")
    if DEMO_MODE:
        print("  DEMO_MODE=True — set DEMO_MODE=False to enable.")
    else:
        print("  TRIGGER_DATA_REFRESH=False — set True to auto-frame Direct Lake tables.")
    print("\n  Manual alternative:")
    print("  Fabric portal → semantic model → Settings → Refresh → Refresh now")
else:
    print("Triggering Power BI Data refresh (frames Direct Lake tables)...")
    refresh_req = requests.post(
        f"{PBI_API_GROUPS}/refreshes",
        headers={**headers, "Content-Type": "application/json"},
        json={"notifyOption": "NoNotification"},
    )
    if refresh_req.status_code not in (200, 202):
        print(f"ERROR {refresh_req.status_code}: {refresh_req.text}")
    else:
        print(f"  Refresh accepted ({refresh_req.status_code}). Polling every 15 s ...")
        max_polls    = 24   # 6 minutes total
        poll_secs    = 15
        final_status = "Unknown"
        for poll_i in range(max_polls):
            _time.sleep(poll_secs)
            hist = requests.get(f"{PBI_API_GROUPS}/refreshes?$top=1", headers=headers)
            hist.raise_for_status()
            top = hist.json().get("value", [{}])[0]
            final_status = top.get("status", "Unknown")
            end_time = top.get("endTime", "—")
            print(f"  [{poll_i+1:02d}/{max_polls}] status={final_status}  endTime={end_time}")
            if final_status in ("Completed", "Failed", "Cancelled"):
                break

        if final_status == "Completed":
            print(f"\nSUCCESS — Data refresh completed. Direct Lake tables are now framed.")
            print("  fct_cc_interactions, dim_cc_agent, dim_cc_billing_adj are queryable.")
            print("  Retry your Copilot question: 'What is our FCR Rate?'")
        else:
            err = top.get("serviceExceptionJson", "")
            print(f"\nERROR — Refresh ended with status={final_status}")
            if err:
                print(f"  Detail: {err[:400]}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
