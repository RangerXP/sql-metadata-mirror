import json

import pytest

from tools.tag_lifecycle_validation import (
    extract_tag_fields,
    validate_tag_fields,
    evaluate_governance_state,
)


def test_extract_tag_fields_parses_maria_tag():
    sample = (
        "/* @tag: domain=DOM-SVCDEL owner=shruthi.srinivas@enercare.ca "
        "sensitivity=Internal semantic_role=CandidateFact "
        "business_use=Daily field-ops technician utilization and workload distribution */"
    )

    fields = extract_tag_fields(sample)

    assert fields["domain"] == "DOM-SVCDEL"
    assert fields["owner"] == "shruthi.srinivas@enercare.ca"
    assert fields["sensitivity"] == "Internal"
    assert fields["semantic_role"] == "CandidateFact"
    assert "Daily field-ops technician utilization and workload distribution" in fields["business_use"]


def test_validate_tag_fields_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="Missing required @tag fields"):
        validate_tag_fields({"domain": "DOM-SVCDEL", "owner": "user@example.com"})


def test_validate_tag_fields_requires_canonical_purview_sensitivity_label():
    cleaned = validate_tag_fields({
        "domain": "DOM-SVCDEL",
        "owner": "user@example.com",
        "sensitivity": "Highly Confidential",
        "semantic_role": "CandidateFact",
        "business_use": "Monthly service contract QA",
    })

    assert cleaned["sensitivity"] == "Highly Confidential"
    assert cleaned["sensitivity_label"] == "Highly Confidential"


def test_evaluate_governance_state_requires_approved_and_purview_label():
    request = {
        "current_status": "Approved",
        "proposed_payload": json.dumps({
            "RecordType": "asset",
            "domain": "DOM-SVCDEL",
            "sensitivity": "Confidential",
            "sensitivity_label": "Confidential",
        }),
        "applicable_target": "semantic_model",
    }

    state = evaluate_governance_state(request)

    assert state["is_approved"] is True
    assert state["can_apply"] is True
    assert state["has_valid_purview_label"] is True
    assert state["purview_label"] == "Confidential"
    assert state["status"] == "Approved"
