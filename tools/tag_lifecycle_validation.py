import json
import re
from typing import Any, Dict, Iterable, List, Optional

REQUIRED_TAG_FIELDS = {
    "domain",
    "owner",
    "sensitivity",
    "semantic_role",
    "business_use",
}

CANONICAL_SENSITIVITY_LABELS = {
    "general": "General",
    "internal": "Internal",
    "confidential": "Confidential",
    "highly confidential": "Highly Confidential",
    "pci restricted": "Highly Confidential",
    "privacy restricted": "Highly Confidential",
}


def canonicalize_sensitivity_label(raw_value: Any) -> str:
    if raw_value is None:
        return ""
    text = str(raw_value).strip()
    if not text:
        return ""
    normalized = CANONICAL_SENSITIVITY_LABELS.get(text.lower(), text)
    return normalized.strip()


def extract_tag_fields(raw_text: str) -> Dict[str, str]:
    if raw_text is None:
        raise ValueError("@tag input is missing")

    match = re.search(r"@tag:\s*(.*?)(?:\*/|$)", raw_text, flags=re.IGNORECASE)
    if not match:
        return {}

    tag_value = match.group(1).strip()
    fields: Dict[str, str] = {}

    pattern = re.compile(
        r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>(?:(?!\s+[A-Za-z_][A-Za-z0-9_-]*=).)*)",
        flags=re.IGNORECASE,
    )

    for item in pattern.finditer(tag_value):
        key = item.group("key").strip().lower()
        value = item.group("value").strip()
        if key and value:
            fields[key] = value

    if not fields:
        raise ValueError("No valid @tag field pairs were found")

    return fields


def validate_tag_fields(tag_fields: Dict[str, Any]) -> Dict[str, Any]:
    missing = sorted(REQUIRED_TAG_FIELDS - set((k or "").lower() for k in tag_fields.keys()))
    if missing:
        raise ValueError(f"Missing required @tag fields: {', '.join(missing)}")

    cleaned = {str(k).lower(): str(v).strip() for k, v in tag_fields.items() if v is not None}
    for key in REQUIRED_TAG_FIELDS:
        if not cleaned.get(key):
            raise ValueError(f"@tag field '{key}' is empty")

    normalized_sensitivity = canonicalize_sensitivity_label(cleaned.get("sensitivity") or cleaned.get("sensitivity_label"))
    if not normalized_sensitivity:
        raise ValueError("@tag field 'sensitivity' is empty")
    valid_labels = {value.lower() for value in CANONICAL_SENSITIVITY_LABELS.values()}
    if normalized_sensitivity.lower() not in valid_labels:
        raise ValueError(f"Unsupported sensitivity label '{normalized_sensitivity}'. Use one of: {', '.join(sorted({v for v in CANONICAL_SENSITIVITY_LABELS.values()}))}")

    cleaned["sensitivity"] = normalized_sensitivity
    cleaned["sensitivity_label"] = normalized_sensitivity
    return cleaned


def evaluate_governance_state(request: Dict[str, Any]) -> Dict[str, Any]:
    status = (request.get("current_status") or "").strip()
    payload = request.get("proposed_payload")
    if isinstance(payload, str):
        payload_obj = json.loads(payload)
    elif payload is None:
        payload_obj = {}
    else:
        payload_obj = payload

    sensitivity_value = payload_obj.get("sensitivity") if isinstance(payload_obj, dict) else None
    if sensitivity_value is None and isinstance(payload_obj, dict):
        sensitivity_value = payload_obj.get("sensitivity_label")
    normalized_sensitivity = canonicalize_sensitivity_label(sensitivity_value)
    valid_labels = {value.lower() for value in CANONICAL_SENSITIVITY_LABELS.values()}
    has_valid_purview_label = bool(normalized_sensitivity) and normalized_sensitivity.lower() in valid_labels
    if isinstance(payload_obj, dict):
        payload_obj["sensitivity"] = normalized_sensitivity if has_valid_purview_label else payload_obj.get("sensitivity", "")
        payload_obj["sensitivity_label"] = normalized_sensitivity if has_valid_purview_label else payload_obj.get("sensitivity_label", "")

    approved = status.lower() == "approved"
    can_apply = approved and bool(payload_obj) and has_valid_purview_label

    return {
        "status": status,
        "is_approved": approved,
        "can_apply": can_apply,
        "has_valid_purview_label": has_valid_purview_label,
        "purview_label": normalized_sensitivity if has_valid_purview_label else None,
        "payload_summary": payload_obj,
    }


def validate_tag_lifecycle(raw_sql_definition: str, request: Dict[str, Any]) -> Dict[str, Any]:
    tag_fields = validate_tag_fields(extract_tag_fields(raw_sql_definition))
    state = evaluate_governance_state(request)

    result = {
        "tag_fields": tag_fields,
        "governance_state": state,
        "is_valid": bool(tag_fields and state["is_approved"] and state["can_apply"]),
    }
    return result
