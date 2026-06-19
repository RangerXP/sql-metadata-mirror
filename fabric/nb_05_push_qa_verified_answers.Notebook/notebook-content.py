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

# Standalone Copilot grounding reads semantic model annotation surfaces.
# Keep this enabled so write path stays on SemPy Labs-only and avoids TOM drift.
USE_SEMPY_ONLY      = True

DEMO_MODE            = False
MODEL_NAME           = "BrookfieldEnercare"
MODEL_WORKSPACE_ID   = "b976cac2-7754-4061-88c2-61c0ac016a99"
METADATA_LH          = "lh_metadata"
# Keep this high enough to include all valid instructions + verified Q&A.
# If your environment enforces a lower annotation limit, the notebook now reports
# that explicitly instead of silently dropping content.
MAX_ANNOTATION_CHARS = 12000

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

# Exact service request IDs should rank first in grounding payload assembly.
verified_answers.sort(
    key=lambda r: (
        0 if any(ch.isdigit() for ch in (r.TriggerText or "")) else 1,
        (r.TriggerText or "").lower(),
    )
)

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
    f"Q: {_safe(r.TriggerText)} -> {_safe(r.ResponseText)}"
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


def _find_collection_item_by_name(collection, name: str):
    target = name.strip().lower()

    try:
        return collection[name]
    except Exception:
        pass

    for item in collection:
        item_name = getattr(item, "Name", None)
        if isinstance(item_name, str) and item_name.strip().lower() == target:
            return item

    return None


def _resolve_model_workspace_id() -> str:
    return globals().get("MODEL_WORKSPACE_ID", "b976cac2-7754-4061-88c2-61c0ac016a99")


def _discover_tom_connector(labs_module):
    candidates = []

    if labs_module is not None:
        fn = getattr(labs_module, "connect_semantic_model", None)
        if callable(fn):
            candidates.append(("labs.connect_semantic_model", fn))

    for mod_name in [
        "sempy_labs.tom",
        "sempy_labs.tom._model",
        "sempy_labs._model",
    ]:
        try:
            module_obj = __import__(mod_name, fromlist=["connect_semantic_model"])
            fn = getattr(module_obj, "connect_semantic_model", None)
            if callable(fn):
                candidates.append((f"{mod_name}.connect_semantic_model", fn))
        except Exception:
            pass

    return candidates[0] if candidates else (None, None)


def _set_annotation_via_labs(labs_module, name: str, value: str):
    if labs_module is None:
        return False, "sempy_labs unavailable"

    candidate_modules = [labs_module]
    for mod_name in ["sempy_labs.annotations", "sempy_labs"]:
        try:
            candidate_modules.append(__import__(mod_name, fromlist=["*"]))
        except Exception:
            pass

    candidate_methods = [
        "set_annotation",
        "update_annotation",
        "add_annotation",
        "set_model_annotation",
    ]

    workspace_id = _resolve_model_workspace_id()

    errors = []
    for module_obj in candidate_modules:
        module_name = getattr(module_obj, "__name__", "labs")
        for method_name in candidate_methods:
            method = getattr(module_obj, method_name, None)
            if not callable(method):
                continue

            call_variants = [
                {
                    "dataset": MODEL_NAME,
                    "workspace": workspace_id,
                    "annotation_name": name,
                    "annotation_value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "workspace_id": workspace_id,
                    "annotation_name": name,
                    "annotation_value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "annotation_name": name,
                    "annotation_value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "workspace": workspace_id,
                    "name": name,
                    "value": value,
                },
                {
                    "dataset": MODEL_NAME,
                    "name": name,
                    "value": value,
                },
            ]

            for kwargs in call_variants:
                try:
                    method(**kwargs)
                    return True, f"{module_name}.{method_name}"
                except Exception as ex:
                    errors.append(f"{module_name}.{method_name}: {ex}")

    # SemPy Labs v2 commonly exposes connect_semantic_model/TOM wrapper
    # rather than direct set_annotation helpers. Treat this as SemPy path.
    connector_name, connector = _discover_tom_connector(labs_module)
    ok_tom, detail_tom = _set_annotation_via_tom(connector, connector_name, name=name, value=value)
    if ok_tom:
        return True, f"{detail_tom} (SemPy Labs v2 TOM wrapper)"

    if errors:
        errors.append(f"tom_wrapper: {detail_tom}")
        return False, " | ".join(errors[:3])

    return False, f"no compatible sempy_labs annotation writer found | tom_wrapper: {detail_tom}"


def _set_annotation_via_tom(connector, connector_name, name: str, value: str):
    if connector is None:
        return False, "no supported TOM connector found"

    workspace_id = _resolve_model_workspace_id()

    connect_variants = [
        {"dataset": MODEL_NAME, "workspace": workspace_id, "readonly": False},
        {"dataset": MODEL_NAME, "workspace_id": workspace_id, "readonly": False},
        {"dataset": MODEL_NAME, "readonly": False},
    ]

    last_ex = None
    for connect_kwargs in connect_variants:
        try:
            with connector(**connect_kwargs) as tom:
                annotations = getattr(tom.model, "Annotations", None)
                if annotations is None:
                    return False, "model annotations collection unavailable"

                existing = _find_collection_item_by_name(annotations, name)
                if existing is not None:
                    existing.Value = value
                    return True, f"updated via {connector_name or 'unknown_connector'}"

                try:
                    annotations.Add(name, value)
                    return True, f"added via {connector_name or 'unknown_connector'}"
                except Exception as ex:
                    return False, f"annotation add failed: {ex}"
        except Exception as ex:
            last_ex = ex

    return False, f"annotation write failed: {last_ex}"


def _publish_annotation_semantic_surface(name: str, value: str, labs_module):
    ok, detail = _set_annotation_via_labs(labs_module, name=name, value=value)
    if ok:
        return True, detail

    sempy_only_mode = globals().get("USE_SEMPY_ONLY", True)
    if sempy_only_mode:
        return False, f"SemPy-only mode enabled; annotation publish failed via SemPy Labs: {detail}"

    connector_name, connector = _discover_tom_connector(labs_module)
    return _set_annotation_via_tom(connector, connector_name, name=name, value=value)

LABS_SETUP_MESSAGE = (
    "semantic-link-labs is not installed in this Fabric environment. "
    "Install it in the environment configuration (not at notebook runtime), "
    "restart the session, and rerun this notebook."
)

try:
    import sempy_labs as labs
except ModuleNotFoundError:
    labs = None
    print(f"[WARN] {LABS_SETUP_MESSAGE}")
except Exception as ex:
    labs = None
    print("[WARN] sempy_labs import failed.")
    print("       Verify semantic-link-labs is installed in the environment configuration,")
    print("       then restart the session and rerun this notebook.")
    print(f"       Detail: {ex}")


annotation_applied = False
annotation_write_detail = "not attempted"


if DEMO_MODE:
    print("[DRY RUN] Annotation write skipped")
else:
    if labs is None:
        raise RuntimeError(f"DEMO_MODE=False requires sempy_labs. {LABS_SETUP_MESSAGE}")

    # Publish to semantic model annotation surface that standalone Copilot reads.
    annotation_applied, annotation_write_detail = _publish_annotation_semantic_surface(
        name="PBI_AI_Instructions",
        value=combined,
        labs_module=labs,
    )

    if annotation_applied:
        print(f"[APPLIED] Annotation PBI_AI_Instructions ({len(combined)} chars) | {annotation_write_detail}")
    else:
        print("[WARN] Annotation write was not applied.")
        print(f"       Detail: {annotation_write_detail}")
        print("       Annotation preview (first 500 chars):")
        print(combined[:500])


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
status = "DRY RUN" if DEMO_MODE else ("APPLIED" if annotation_applied else "FAILED")
print(f"  Status: {status}")
if not DEMO_MODE:
    print(f"  Write detail:       {annotation_write_detail}")
print("\nTo verify: ask Copilot 'what is our FCR?' or 'what is our CSAT score?'")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
