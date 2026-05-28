# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "824f4a52-baa0-4c3f-88dc-203c1d85c89a",
# META       "default_lakehouse_name": "lh_metadata",
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99",
# META       "known_lakehouses": [
# META         {
# META           "id": "824f4a52-baa0-4c3f-88dc-203c1d85c89a"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Fabric Notebook: nb_05_push_qa_verified_answers
# Purpose: Read ai_instruction + verified_answer rows from lh_metadata.ai_metadata,
#          build the PBI_AI_Instructions payload, and write it to the semantic
#          model using SemPy Labs (primary write-back path).
#
# DEMO_MODE = True  -> dry-run (prints annotation preview, no write)
# DEMO_MODE = False -> live (writes annotation to semantic model)

DEMO_MODE            = True
MODEL_NAME           = "BrookfieldEnercare"
METADATA_LH          = "lh_metadata"
MAX_ANNOTATION_CHARS = 3800

print(f"nb_05_push_qa_verified_answers | DEMO_MODE={DEMO_MODE}")
print(f"Target model: {MODEL_NAME}")
print(f"Max annotation chars: {MAX_ANNOTATION_CHARS}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Read ai_metadata

ai_df = spark.sql(f"""
    SELECT RecordType, TriggerText, ResponseText, LinkedKPICode
    FROM {METADATA_LH}.ai_metadata
    WHERE IsDraft = 0
    ORDER BY RecordType, RecordID
""")
ai_rows = ai_df.collect()

ai_instructions = list(
    dict.fromkeys(
        r.ResponseText
        for r in ai_rows
        if r.RecordType == "ai_instruction" and r.ResponseText
    )
)

_seen_qa = set()
verified_answers = []
for r in ai_rows:
    if r.RecordType == "verified_answer" and r.TriggerText and r.ResponseText:
        key = (r.TriggerText, r.ResponseText)
        if key not in _seen_qa:
            _seen_qa.add(key)
            verified_answers.append(r)

print(f"Loaded: {len(ai_instructions)} instruction(s), {len(verified_answers)} verified answer(s)")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Build annotation payload


def _safe(text: str) -> str:
    return text.replace('"', "'").strip()


instr_block = " | ".join(_safe(t) for t in ai_instructions)
qa_parts = [
    f"Q: {_safe(r.TriggerText)} -> {_safe(r.ResponseText[:150])}"
    for r in verified_answers
]
qa_block = " | ".join(qa_parts)

if instr_block and qa_block:
    combined = f"{instr_block} | VERIFIED Q&A: {qa_block}"
elif qa_block:
    combined = f"VERIFIED Q&A: {qa_block}"
else:
    combined = instr_block

if len(combined) > MAX_ANNOTATION_CHARS:
    truncated = combined[:MAX_ANNOTATION_CHARS]
    last_sep = truncated.rfind(" | ")
    combined = truncated[:last_sep] if last_sep > 0 else truncated
    print(f"[WARN] Annotation truncated to {len(combined)} chars")

print(f"Annotation length: {len(combined)}")
print("--- Preview (first 500 chars) ---")
print(combined[:500])
print("..." if len(combined) > 500 else "")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Write annotation with SemPy Labs

try:
    import sempy_labs as labs
except Exception as ex:
    labs = None
    print("[WARN] sempy_labs import failed.")
    print("       Install semantic-link-labs in this environment to run write-back.")
    print(f"       Detail: {ex}")


if DEMO_MODE:
    print("[DRY RUN] Annotation write skipped")
else:
    if labs is None:
        raise RuntimeError("DEMO_MODE=False requires sempy_labs to be installed")

    write_succeeded = False
    errors = []

    method = getattr(labs, "set_semantic_model_annotation", None)
    if method is not None:
        try:
            method(
                dataset=MODEL_NAME,
                annotation_name="PBI_AI_Instructions",
                annotation_value=combined,
            )
            write_succeeded = True
        except Exception as ex:
            errors.append(f"set_semantic_model_annotation: {ex}")

    if not write_succeeded:
        method = getattr(labs, "set_annotation", None)
        if method is not None:
            try:
                method(
                    dataset=MODEL_NAME,
                    annotation_name="PBI_AI_Instructions",
                    annotation_value=combined,
                )
                write_succeeded = True
            except Exception as ex:
                errors.append(f"set_annotation: {ex}")

    if not write_succeeded:
        raise RuntimeError("SemPy Labs annotation write failed: " + " | ".join(errors))

    print("SUCCESS - PBI_AI_Instructions written via SemPy Labs")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Summary

print("\n=== nb_05 Summary ===")
print(f"  Model:              {MODEL_NAME}")
print(f"  AI instructions:    {len(ai_instructions)}")
print(f"  Verified Q&A pairs: {len(qa_parts)}")
print(f"  Annotation chars:   {len(combined)} / {MAX_ANNOTATION_CHARS}")
print(f"  Status: {'DRY RUN' if DEMO_MODE else 'APPLIED'}")
print("\nTo verify: ask Copilot 'what is our FCR?' or 'what is our CSAT score?'")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
