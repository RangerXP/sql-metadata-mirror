import re
from pathlib import Path


NOTEBOOK = Path("06_publish_glossary_and_lineage.Notebook/notebook-content.py")


def _read_config_value(name: str):
    text = NOTEBOOK.read_text(encoding="utf-8")
    match = re.search(rf"^{name}\s*=\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"Could not find {name} in the notebook")
    return match.group(1).strip()


def test_publish_glossary_and_lineage_live_defaults_are_enabled_for_governance_workflow():
    assert _read_config_value("APPLY_CHANGES") == "True"
    assert _read_config_value("SQL_MIRROR_ONLY_DEPLOYMENT") == "False"
    assert _read_config_value("PURVIEW_PUBLISH_OVERRIDE") == "True"
