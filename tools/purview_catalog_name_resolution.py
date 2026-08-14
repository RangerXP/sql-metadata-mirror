from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "docs" / "purview_live_catalog_snapshot.json"

EXPECTED_NAMES = [
    "DOM-CUSTOPS",
    "DOM-SVCDEL",
    "DOM-REVCON",
    "DP-CUST360",
    "DP-SVCPERF",
    "DP-BILLHEALTH",
    "GT-SLA",
    "GT-CONSENT",
    "GT-CONTRACT",
    "GT-SVCREQ",
    "GT-PII",
    "BrookfieldEnercare",
    "governance_domains",
    "governance_requests",
    "governance_object_mappings",
    "governed_object_versions",
    "governance_change_requests",
    "governance_role_assignments",
    "governance_glossary_terms",
    "governance_data_products",
    "vw_technician_utilization_summary",
    "service_requests",
    "fct_service_request",
]

ALIASES = {
    "DOM-CUSTOPS": ["DOM-CUSTOPS", "Customer Operations", "customer operations"],
    "DOM-SVCDEL": ["DOM-SVCDEL", "Service Delivery", "service delivery"],
    "DOM-REVCON": ["DOM-REVCON", "Revenue and Contracts", "revenue and contracts"],
    "DP-CUST360": ["DP-CUST360", "Customer 360", "customer 360"],
    "DP-SVCPERF": ["DP-SVCPERF", "Service Performance", "service performance"],
    "DP-BILLHEALTH": ["DP-BILLHEALTH", "Billing Health", "billing health"],
    "GT-SLA": ["GT-SLA", "SLA", "service level agreement"],
    "GT-CONSENT": ["GT-CONSENT", "Customer Consent", "customer consent"],
    "GT-CONTRACT": ["GT-CONTRACT", "Contract", "contract"],
    "GT-SVCREQ": ["GT-SVCREQ", "Service Request", "service request"],
    "GT-PII": ["GT-PII", "PII", "personally identifiable information"],
}


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def find_in_item(item: Dict[str, Any], needle: str) -> bool:
    haystacks = []
    for key in ("name", "displayText", "qualifiedName", "description", "sourceQuery"):
        value = item.get(key)
        if isinstance(value, str):
            haystacks.append(value)
    for value in item.get("assetType", []) or []:
        if isinstance(value, str):
            haystacks.append(value)
    combined = " ".join(haystacks)
    return needle.lower() in combined.lower()


def class_by_name(items: Iterable[Dict[str, Any]], needle: str) -> Dict[str, Any]:
    exact = []
    alias = []
    for item in items:
        if find_in_item(item, needle):
            exact.append({
                "name": item.get("name") or item.get("displayText"),
                "entityType": item.get("entityType"),
                "qualifiedName": item.get("qualifiedName"),
                "sourceQuery": item.get("sourceQuery"),
            })
            continue

        for alias_name in ALIASES.get(needle, []):
            if alias_name and find_in_item(item, alias_name):
                alias.append({
                    "name": item.get("name") or item.get("displayText"),
                    "entityType": item.get("entityType"),
                    "qualifiedName": item.get("qualifiedName"),
                    "sourceQuery": item.get("sourceQuery"),
                })
                break

    if exact:
        status = "exact"
        hits = exact
    elif alias:
        status = "indirect_alias"
        hits = alias
    else:
        status = "missing"
        hits = []

    return {"needle": needle, "status": status, "hits": hits[:5]}


def main() -> None:
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    items = payload.get("items", [])
    summary = [class_by_name(items, name) for name in EXPECTED_NAMES]
    present = sum(1 for item in summary if item["status"] != "missing")
    missing = sum(1 for item in summary if item["status"] == "missing")

    print(json.dumps({
        "snapshot": str(SNAPSHOT_PATH.name),
        "total_items": payload.get("itemCount", len(items)),
        "checked": len(EXPECTED_NAMES),
        "present_count": present,
        "missing_count": missing,
        "results": summary,
    }, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
