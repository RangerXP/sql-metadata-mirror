import re
from pathlib import Path


NOTEBOOK = Path("nb_09_lineage_and_labels_stage.Notebook/notebook-content.py")


def _read_config_value(name: str):
    text = NOTEBOOK.read_text(encoding="utf-8")
    match = re.search(rf"^{name}\s*=\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"Could not find {name} in the notebook")
    return match.group(1).strip()


def test_nb09_live_publish_defaults_are_enabled_for_governance_workflow():
    assert _read_config_value("APPLY_CHANGES") == "True"
    assert _read_config_value("SQL_MIRROR_ONLY_DEPLOYMENT") == "False"
    assert _read_config_value("PURVIEW_PUBLISH_OVERRIDE") == "True"
