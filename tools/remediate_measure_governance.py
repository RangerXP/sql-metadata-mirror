import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://Purview-West3.purview.azure.com"
API = "2023-09-01"
AZ_FALLBACK = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
SEED_META = Path("sql/07_seed_purview_metadata.sql")
OUT = Path("tools/purview_measure_governance_report.json")

EXPECTED_MEASURE_REFS = [
    "BrookfieldEnercare/_Measures/FCR",
    "BrookfieldEnercare/_Measures/NPS",
    "BrookfieldEnercare/_Measures/CSAT",
    "BrookfieldEnercare/_Measures/AvgHandleTime",
    "BrookfieldEnercare/_Measures/RepeatComplaintRate",
]

FALLBACK_LABEL = "Executive KPI"


def safe(value):
    return (value or "").strip() if isinstance(value, str) else ("" if value is None else str(value).strip())


def split_tokens(value):
    text = safe(value)
    return [part.strip() for part in re.split(r"[;,|\n]+", text) if part and part.strip()] if text else []


def parse_insert_values(sql_text, table):
    match = re.search(
        rf"INSERT\s+INTO\s+dbo\.{table}\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\nGO|\nPRINT|\nSELECT|$)",
        sql_text,
        flags=re.I | re.S,
    )
    if not match:
        return []

    columns = [col.strip().strip("[]") for col in match.group(1).split(",")]
    values_blob = match.group(2)

    tuples = []
    current = ""
    depth = 0
    in_string = False
    idx = 0
    while idx < len(values_blob):
        ch = values_blob[idx]
        if ch == "'":
            if idx + 1 < len(values_blob) and values_blob[idx + 1] == "'":
                current += "''"
                idx += 2
                continue
            in_string = not in_string
            current += ch
            idx += 1
            continue
        if not in_string and ch == "(":
            depth += 1
        if depth > 0:
            current += ch
        if not in_string and ch == ")":
            depth -= 1
            if depth == 0 and current.strip():
                tuples.append(current.strip())
                current = ""
        idx += 1

    rows = []
    for item in tuples:
        inner = item[1:-1]
        tokens = []
        token = ""
        in_string = False
        pos = 0
        while pos < len(inner):
            ch = inner[pos]
            if ch == "'":
                if pos + 1 < len(inner) and inner[pos + 1] == "'":
                    token += "''"
                    pos += 2
                    continue
                in_string = not in_string
                token += ch
                pos += 1
                continue
            if ch == "," and not in_string:
                tokens.append(token.strip())
                token = ""
                pos += 1
                continue
            token += ch
            pos += 1
        if token.strip() or inner.endswith(","):
            tokens.append(token.strip())
        if len(tokens) != len(columns):
            continue

        row = {}
        for col, value in zip(columns, tokens):
            if value.upper() == "NULL":
                row[col] = ""
            elif value.startswith("'") and value.endswith("'"):
                row[col] = value[1:-1].replace("''", "'")
            else:
                row[col] = value
        rows.append(row)

    return rows


def az_token():
    az = shutil.which("az") or shutil.which("az.cmd") or (AZ_FALLBACK if Path(AZ_FALLBACK).exists() else None)
    if not az:
        raise RuntimeError("Azure CLI not found.")
    return subprocess.check_output(
        [az, "account", "get-access-token", "--resource", "https://purview.azure.net", "--query", "accessToken", "-o", "tsv"],
        text=True,
    ).strip()


def req(method, path, token, body=None, params=None, timeout=45):
    url = BASE + path
    query = dict(params or {})
    if path.startswith("/datamap/") and "api-version" not in query:
        query["api-version"] = API
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)

    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode("utf-8", errors="replace")
    except Exception as ex:
        return 599, str(ex)


def to_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def search(token, keywords, limit=30):
    status, body = req("POST", "/datamap/api/search/query", token, body={"keywords": keywords, "limit": limit})
    if status != 200:
        return []
    payload = to_json(body)
    return payload.get("value") if isinstance(payload, dict) else []


def resolve_measure_entity(token, asset_ref):
    measure_name = safe(asset_ref.split("/_Measures/", 1)[-1])
    candidates = search(token, f"{measure_name} measure BrookfieldEnercare", 40)
    best = None
    best_score = -1
    for candidate in candidates:
        entity_type = safe(candidate.get("entityType") or candidate.get("typeName")).lower()
        qualified_name = safe(candidate.get("qualifiedName")).lower()
        source_asset = safe((candidate.get("attributes") or {}).get("sourceAssetRef")).lower()
        guid = safe(candidate.get("id") or candidate.get("guid"))
        if not guid:
            continue
        score = 0
        if "measure" in entity_type:
            score += 30
        if measure_name.lower() in qualified_name:
            score += 15
        if safe(asset_ref).lower() in qualified_name:
            score += 10
        if source_asset == safe(asset_ref).lower():
            score += 30
        if score > best_score:
            best_score = score
            best = {
                "guid": guid,
                "entityType": safe(candidate.get("entityType") or candidate.get("typeName")),
                "qualifiedName": safe(candidate.get("qualifiedName")),
                "name": safe(candidate.get("name")),
            }

    # If search omitted attributes/name, fall back to direct exact-known GUID query by scanning likely matches.
    if best:
        return best

    for candidate in candidates:
        guid = safe(candidate.get("id") or candidate.get("guid"))
        if not guid:
            continue
        status, body = req("GET", f"/catalog/api/atlas/v2/entity/guid/{guid}", token)
        if status != 200:
            continue
        payload = to_json(body) or {}
        entity = payload.get("entity") or {}
        if safe(entity.get("typeName")).lower() != "enercaresemanticmeasure":
            continue
        attrs = entity.get("attributes") or {}
        if safe(attrs.get("sourceAssetRef")).lower() == safe(asset_ref).lower():
            return {
                "guid": safe(entity.get("guid")),
                "entityType": safe(entity.get("typeName")),
                "qualifiedName": safe(attrs.get("qualifiedName")),
                "name": safe(attrs.get("name")),
            }

    return None


def get_entity(token, guid):
    status, body = req("GET", f"/catalog/api/atlas/v2/entity/guid/{guid}", token)
    if status != 200:
        return None
    payload = to_json(body)
    if not isinstance(payload, dict):
        return None
    return payload.get("entity")


def ensure_label(token, guid, label_name):
    path = f"/catalog/api/atlas/v2/entity/guid/{guid}/labels"
    compact = "".join(ch for ch in safe(label_name) if ch.isalnum())

    for candidate in [safe(label_name), compact]:
        if not candidate:
            continue
        for method in ("POST", "PUT"):
            for payload in ([candidate], {"labels": [candidate]}, {"labels": [{"name": candidate}]}):
                status, body = req(method, path, token, body=payload)
                low = safe(body).lower()
                if status in (200, 201, 204):
                    return "assigned", ""
                if status == 409 or "already" in low or "duplicate" in low:
                    return "existing", ""
                if status in (400, 404, 405):
                    continue
                return "failed", f"HTTP {status} | {safe(body)[:240]}"

    return "failed", "label API rejected all payload variants"


def list_glossaries(token):
    status, body = req("GET", "/catalog/api/atlas/v2/glossary", token)
    if status != 200:
        return []
    payload = to_json(body)
    return payload if isinstance(payload, list) else []


def list_glossary_terms(token, glossary_guid):
    status, body = req("GET", f"/catalog/api/atlas/v2/glossary/{glossary_guid}/terms", token)
    if status != 200:
        return []
    payload = to_json(body)
    return payload if isinstance(payload, list) else []


def create_term(token, glossary_guid, name, long_desc):
    body = {
        "name": name,
        "shortDescription": (long_desc or name)[:200],
        "longDescription": long_desc or name,
        "anchor": {"glossaryGuid": glossary_guid},
    }
    status, resp_body = req("POST", "/catalog/api/atlas/v2/glossary/term", token, body=body)
    if status in (200, 201):
        payload = to_json(resp_body) or {}
        return safe(payload.get("guid") or payload.get("termGuid")), ""
    return "", f"HTTP {status} | {safe(resp_body)[:240]}"


def is_term_assigned(token, term_guid, entity_guid):
    status, body = req("GET", f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities", token)
    if status != 200:
        return False
    payload = to_json(body)
    return isinstance(payload, list) and any(safe(item.get("guid")) == safe(entity_guid) for item in payload)


def apply_term(token, term_guid, entity_guid, entity_type):
    if is_term_assigned(token, term_guid, entity_guid):
        return "existing", ""

    status, body = req(
        "POST",
        f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities",
        token,
        body=[{"guid": entity_guid, "typeName": entity_type}],
    )
    if status in (200, 201, 202, 204):
        return "assigned", ""
    if is_term_assigned(token, term_guid, entity_guid):
        return "existing", ""
    return "failed", f"HTTP {status} | {safe(body)[:240]}"


def choose_glossary(glossaries):
    if not glossaries:
        return None
    preferred = [g for g in glossaries if safe(g.get("name")).lower() == "enercare glossary"]
    if preferred:
        return preferred[0]
    return glossaries[0]


def main():
    seed_text = SEED_META.read_text(encoding="utf-8")
    glossary_rows = parse_insert_values(seed_text, "governance_glossary_terms")
    label_rows = parse_insert_values(seed_text, "governance_label_assignments")

    glossary_by_measure = {}
    for row in glossary_rows:
        term_name = safe(row.get("term_name"))
        definition = safe(row.get("definition"))
        for asset_ref in split_tokens(row.get("bound_assets")):
            if asset_ref.startswith("BrookfieldEnercare/_Measures/"):
                glossary_by_measure.setdefault(asset_ref, []).append({
                    "term_name": term_name,
                    "definition": definition,
                })

    labels_by_measure = {}
    for row in label_rows:
        label_name = safe(row.get("label_name"))
        for asset_ref in split_tokens(row.get("applies_to_asset_ids")):
            if asset_ref.startswith("BrookfieldEnercare/_Measures/"):
                labels_by_measure.setdefault(asset_ref, set()).add(label_name)

    all_measure_refs = sorted(set(EXPECTED_MEASURE_REFS) | set(glossary_by_measure.keys()) | set(labels_by_measure.keys()))

    for measure_ref in all_measure_refs:
        labels_by_measure.setdefault(measure_ref, set())
        if not labels_by_measure[measure_ref]:
            labels_by_measure[measure_ref].add(FALLBACK_LABEL)

    token = az_token()

    glossaries = list_glossaries(token)
    glossary = choose_glossary(glossaries)
    if not glossary:
        raise RuntimeError("No glossary found in Purview.")

    glossary_guid = safe(glossary.get("guid"))
    glossary_name = safe(glossary.get("name"))

    existing_terms = list_glossary_terms(token, glossary_guid)
    term_guid_by_name = {}
    for term in existing_terms:
        name = safe(term.get("name"))
        guid = safe(term.get("guid") or term.get("termGuid"))
        if name and guid:
            term_guid_by_name[name.lower()] = guid

    results = {
        "counts": {
            "measure_refs": len(all_measure_refs),
            "expected_measure_refs": len(EXPECTED_MEASURE_REFS),
        },
        "glossary": {
            "selected_glossary_guid": glossary_guid,
            "selected_glossary_name": glossary_name,
            "terms_created": 0,
        },
        "labels": {
            "assigned": 0,
            "existing": 0,
            "failed": 0,
        },
        "meanings": {
            "assigned": 0,
            "existing": 0,
            "failed": 0,
        },
        "resolution": {
            "resolved": 0,
            "unresolved": 0,
        },
        "per_measure": [],
    }

    for idx, measure_ref in enumerate(all_measure_refs, start=1):
        entity = resolve_measure_entity(token, measure_ref)
        item = {
            "asset_ref": measure_ref,
            "resolved": bool(entity),
            "target_guid": safe(entity.get("guid")) if entity else "",
            "target_entityType": safe(entity.get("entityType")) if entity else "",
            "labels": [],
            "meanings": [],
        }

        if not entity:
            results["resolution"]["unresolved"] += 1
            results["per_measure"].append(item)
            continue

        results["resolution"]["resolved"] += 1

        for label_name in sorted(labels_by_measure.get(measure_ref, set())):
            state, detail = ensure_label(token, entity["guid"], label_name)
            item["labels"].append({"label": label_name, "state": state, "detail": detail})
            results["labels"][state] = results["labels"].get(state, 0) + 1

        terms = glossary_by_measure.get(measure_ref, [])
        for term in terms:
            term_name = safe(term.get("term_name"))
            if not term_name:
                continue
            term_guid = term_guid_by_name.get(term_name.lower(), "")
            if not term_guid:
                term_guid, detail = create_term(token, glossary_guid, term_name, safe(term.get("definition")))
                if term_guid:
                    results["glossary"]["terms_created"] += 1
                    term_guid_by_name[term_name.lower()] = term_guid
                else:
                    item["meanings"].append({"term": term_name, "state": "failed", "detail": detail})
                    results["meanings"]["failed"] += 1
                    continue

            state, detail = apply_term(token, term_guid, entity["guid"], entity["entityType"])
            item["meanings"].append({"term": term_name, "state": state, "detail": detail})
            results["meanings"][state] = results["meanings"].get(state, 0) + 1

        results["per_measure"].append(item)

        if idx % 2 == 0:
            print(f"measures {idx}/{len(all_measure_refs)}")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}")
    print(json.dumps({
        "resolution": results["resolution"],
        "labels": results["labels"],
        "meanings": results["meanings"],
        "glossary": results["glossary"],
    }, indent=2))


if __name__ == "__main__":
    main()
