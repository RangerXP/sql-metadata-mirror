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
SEED_OWNERS = Path("sql/05_seed_purview_demo_data.sql")
OUT = Path("tools/purview_intent_metadata_write_report.json")

DATASET_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/datasets/8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c"
DATASET_GUID = "a0df6b58-9fcd-4aee-8235-d1a035677215"
REPORT_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/reports/7c4f1103-e22c-4a8c-930d-9fe20b71b409"
REPORT_GUID = "42561931-aa73-4cbd-9fe3-141b0796ecc6"


def safe(x):
    return (x or "").strip() if isinstance(x, str) else ("" if x is None else str(x).strip())


def split_tokens(v):
    t = safe(v)
    return [p.strip() for p in re.split(r"[;,|\n]+", t) if p and p.strip()] if t else []


def parse_insert_values(sql_text, table):
    m = re.search(
        rf"INSERT\s+INTO\s+dbo\.{table}\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\nGO|\nPRINT|\nSELECT|$)",
        sql_text,
        flags=re.I | re.S,
    )
    if not m:
        return []
    cols = [c.strip().strip("[]") for c in m.group(1).split(",")]
    vals = m.group(2)

    tuples = []
    cur = ""
    depth = 0
    ins = False
    i = 0
    while i < len(vals):
        ch = vals[i]
        if ch == "'":
            if i + 1 < len(vals) and vals[i + 1] == "'":
                cur += "''"
                i += 2
                continue
            ins = not ins
            cur += ch
            i += 1
            continue
        if not ins and ch == "(":
            depth += 1
        if depth > 0:
            cur += ch
        if not ins and ch == ")":
            depth -= 1
            if depth == 0 and cur.strip():
                tuples.append(cur.strip())
                cur = ""
        i += 1

    rows = []
    for tup in tuples:
        inner = tup[1:-1]
        parts = []
        tok = ""
        ins = False
        j = 0
        while j < len(inner):
            ch = inner[j]
            if ch == "'":
                if j + 1 < len(inner) and inner[j + 1] == "'":
                    tok += "''"
                    j += 2
                    continue
                ins = not ins
                tok += ch
                j += 1
                continue
            if ch == "," and not ins:
                parts.append(tok.strip())
                tok = ""
                j += 1
                continue
            tok += ch
            j += 1
        if tok.strip() or inner.endswith(","):
            parts.append(tok.strip())
        if len(parts) != len(cols):
            continue
        rec = {}
        for c, v in zip(cols, parts):
            if v.upper() == "NULL":
                rec[c] = ""
            elif v.startswith("'") and v.endswith("'"):
                rec[c] = v[1:-1].replace("''", "'")
            else:
                rec[c] = v
        rows.append(rec)
    return rows


def parse_owner_rows(sql_text):
    m = re.search(
        r"INSERT\s+INTO\s+dbo\.data_owners_directory\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\n\s*\n|\n/\*|\n--|$)",
        sql_text,
        flags=re.I | re.S,
    )
    if not m:
        return []
    cols = [c.strip().strip("[]") for c in m.group(1).split(",")]
    block = m.group(2)

    tuples = []
    cur = ""
    depth = 0
    ins = False
    i = 0
    while i < len(block):
        ch = block[i]
        if ch == "'":
            if i + 1 < len(block) and block[i + 1] == "'":
                cur += "''"
                i += 2
                continue
            ins = not ins
            cur += ch
            i += 1
            continue
        if not ins and ch == "(":
            depth += 1
        if depth > 0:
            cur += ch
        if not ins and ch == ")":
            depth -= 1
            if depth == 0 and cur.strip():
                tuples.append(cur.strip())
                cur = ""
        i += 1

    rows = []
    for tup in tuples:
        inner = tup[1:-1]
        parts = []
        tok = ""
        ins = False
        j = 0
        while j < len(inner):
            ch = inner[j]
            if ch == "'":
                if j + 1 < len(inner) and inner[j + 1] == "'":
                    tok += "''"
                    j += 2
                    continue
                ins = not ins
                tok += ch
                j += 1
                continue
            if ch == "," and not ins:
                parts.append(tok.strip())
                tok = ""
                j += 1
                continue
            tok += ch
            j += 1
        if tok.strip() or inner.endswith(","):
            parts.append(tok.strip())
        if len(parts) != len(cols):
            continue
        rec = {}
        for c, v in zip(cols, parts):
            if v.upper() == "NULL":
                rec[c] = ""
            elif v.startswith("'") and v.endswith("'"):
                rec[c] = v[1:-1].replace("''", "'")
            else:
                rec[c] = v
        rows.append(rec)
    return rows


def az_token():
    az = shutil.which("az") or shutil.which("az.cmd") or (AZ_FALLBACK if Path(AZ_FALLBACK).exists() else None)
    return subprocess.check_output(
        [az, "account", "get-access-token", "--resource", "https://purview.azure.net", "--query", "accessToken", "-o", "tsv"],
        text=True,
    ).strip()


def req(method, path, token, body=None, params=None):
    url = BASE + path
    q = dict(params or {})
    if path.startswith("/datamap/") and "api-version" not in q:
        q["api-version"] = API
    if q:
        url += "?" + urllib.parse.urlencode(q, doseq=True)
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 599, str(e)


def to_json(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def search(token, keywords, limit=30):
    st, bd = req("POST", "/datamap/api/search/query", token, body={"keywords": keywords, "limit": limit})
    if st != 200:
        return []
    p = to_json(bd)
    return p.get("value") if isinstance(p, dict) else []


def entity_by_guid(token, guid):
    st, bd = req("GET", f"/catalog/api/atlas/v2/entity/guid/{guid}", token)
    if st != 200:
        return None
    p = to_json(bd)
    return (p or {}).get("entity", {}) if isinstance(p, dict) else None


cache = {}


def resolve_target(token, asset_ref):
    key = safe(asset_ref).lower()
    if key in cache:
        return cache[key]

    ar = safe(asset_ref)
    candidates = []
    if ar.lower().startswith("dbo."):
        p = ar.split(".")
        if len(p) >= 3:
            candidates.extend(search(token, f"{p[1]} {' '.join(p[2:])} sqldemo", 25))
        candidates.extend(search(token, ar, 25))
    elif ar.startswith("BrookfieldEnercare/_Measures/"):
        m = ar.split("/_Measures/", 1)[1]
        candidates.extend(search(token, f"{m} measure BrookfieldEnercare", 25))
    elif ar in ("BrookfieldEnercare.Report", "BrookfieldEnercare.SemanticModel"):
        candidates.extend(search(token, f"{ar} powerbi", 25))
    else:
        candidates.extend(search(token, ar, 20))

    uniq = []
    seen = set()
    for c in candidates:
        gid = safe(c.get("id") or c.get("guid"))
        if not gid or gid in seen:
            continue
        seen.add(gid)
        uniq.append(
            {
                "guid": gid,
                "entityType": safe(c.get("entityType") or c.get("typeName")).lower(),
                "qualifiedName": safe(c.get("qualifiedName")).lower(),
                "name": safe(c.get("name")).lower(),
            }
        )

    # Prefer table/view for dbo refs and measure for measure refs.
    best = None
    best_score = -10**9
    for c in uniq:
        score = 0
        et = c["entityType"]
        qn = c["qualifiedName"]
        if ar.lower().startswith("dbo."):
            if "table" in et or "view" in et:
                score += 20
            if "mssql://" in qn:
                score += 5
            parts = ar.split(".")
            if len(parts) >= 2 and parts[1].lower() in qn:
                score += 8
        if ar.startswith("BrookfieldEnercare/_Measures/") and "measure" in et:
            score += 20
        if ar == "BrookfieldEnercare.Report" and REPORT_QN.lower() in qn:
            score += 20
        if ar == "BrookfieldEnercare.SemanticModel" and DATASET_QN.lower() in qn:
            score += 20
        if score > best_score:
            best_score = score
            best = c

    if not best:
        best = {
            "guid": REPORT_GUID if ar == "BrookfieldEnercare.Report" else DATASET_GUID,
            "entityType": "powerbi_report" if ar == "BrookfieldEnercare.Report" else "powerbi_dataset",
            "qualifiedName": REPORT_QN if ar == "BrookfieldEnercare.Report" else DATASET_QN,
            "name": "BrookfieldEnercare",
        }

    cache[key] = best
    return best


def apply_label(token, entity_guid, label_name):
    path = f"/catalog/api/atlas/v2/entity/guid/{entity_guid}/labels"
    compact = "".join(ch for ch in safe(label_name) if ch.isalnum())
    for lbl in [safe(label_name), compact]:
        if not lbl:
            continue
        for method in ("POST", "PUT"):
            for payload in ([lbl], {"labels": [lbl]}, {"labels": [{"name": lbl}]}):
                st, bd = req(method, path, token, body=payload)
                low = bd.lower()
                if st in (200, 201, 204):
                    return "assigned"
                if st == 409 or "already" in low or "duplicate" in low:
                    return "existing"
                if st in (400, 404, 405):
                    continue
                return "failed"
    return "failed"


def resolve_term_guid(token, term_name):
    target = safe(term_name).lower()
    if not target:
        return ""
    vals = search(token, term_name, 25)
    for e in vals:
        et = safe(e.get("entityType") or e.get("typeName")).lower()
        nm = safe(e.get("name")).lower()
        qn = safe(e.get("qualifiedName")).lower()
        gid = safe(e.get("id") or e.get("guid"))
        if gid and "glossaryterm" in et and (nm == target or target in nm or "@" in qn):
            return gid
    return ""


def is_term_assigned(token, term_guid, entity_guid):
    st, bd = req("GET", f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities", token)
    if st != 200:
        return False
    p = to_json(bd)
    return isinstance(p, list) and any(safe(e.get("guid")) == safe(entity_guid) for e in p)


def apply_term(token, term_guid, entity_guid, entity_type):
    if is_term_assigned(token, term_guid, entity_guid):
        return "existing"
    st, _ = req(
        "POST",
        f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities",
        token,
        body=[{"guid": entity_guid, "typeName": safe(entity_type)}],
    )
    if st in (200, 201, 202, 204):
        return "assigned"
    if is_term_assigned(token, term_guid, entity_guid):
        return "existing"
    return "failed"


def apply_attr(token, entity_guid, attr_name, attr_value):
    ent = entity_by_guid(token, entity_guid)
    if not isinstance(ent, dict):
        return "failed"
    attrs = ent.get("attributes") if isinstance(ent.get("attributes"), dict) else {}
    if safe(attrs.get(attr_name)).lower() == safe(attr_value).lower():
        return "existing"
    payload = {
        "entity": {
            "typeName": safe(ent.get("typeName")),
            "guid": safe(ent.get("guid") or entity_guid) or entity_guid,
            "attributes": {
                "qualifiedName": safe(attrs.get("qualifiedName")),
                "name": safe(attrs.get("name")),
                attr_name: attr_value,
            },
        }
    }
    for method, path in [
        ("PUT", f"/catalog/api/atlas/v2/entity/guid/{entity_guid}"),
        ("PUT", "/catalog/api/atlas/v2/entity"),
        ("POST", "/catalog/api/atlas/v2/entity"),
    ]:
        st, _ = req(method, path, token, body=payload)
        if st in (200, 201, 204):
            return "assigned"
        if st in (400, 404, 405):
            continue
        return "failed"
    return "failed"


def dedupe(rows, keyfn):
    out = []
    seen = set()
    for r in rows:
        k = keyfn(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


meta_sql = SEED_META.read_text(encoding="utf-8")
owner_sql = SEED_OWNERS.read_text(encoding="utf-8")
labels = parse_insert_values(meta_sql, "governance_label_assignments")
glossary = parse_insert_values(meta_sql, "governance_glossary_terms")
cdes = parse_insert_values(meta_sql, "governance_cdes")
owner_rows = parse_owner_rows(owner_sql)

label_manifest = []
for r in labels:
    for a in split_tokens(r.get("applies_to_asset_ids", "")):
        label_manifest.append({"asset_ref": a, "label_name": safe(r.get("label_name"))})

glossary_manifest = []
code_to_name = {safe(r.get("term_code")).upper(): safe(r.get("term_name")) for r in glossary if safe(r.get("term_code")) and safe(r.get("term_name"))}
for r in glossary:
    for a in split_tokens(r.get("bound_assets", "")):
        glossary_manifest.append({"asset_ref": a, "term_name": safe(r.get("term_name"))})
for r in cdes:
    parent = safe(r.get("parent_glossary_term"))
    term = code_to_name.get(parent.upper(), parent) if parent else safe(r.get("cde_name"))
    for a in split_tokens(r.get("bound_columns", "")):
        if term:
            glossary_manifest.append({"asset_ref": a, "term_name": term})

description_manifest = []
for r in cdes:
    desc = safe(r.get("business_definition"))
    for a in split_tokens(r.get("bound_columns", "")):
        if desc:
            description_manifest.append({"asset_ref": a, "description": desc})
for r in glossary:
    desc = safe(r.get("definition"))
    for a in split_tokens(r.get("bound_assets", "")):
        if desc:
            description_manifest.append({"asset_ref": a, "description": desc})

contacts_manifest = []
for r in owner_rows:
    schema = safe(r.get("object_schema")).lower()
    obj = safe(r.get("object_name")).lower()
    if schema and obj:
        contacts_manifest.append({"asset_ref": f"{schema}.{obj}", "owner_upn": safe(r.get("data_owner_upn"))})
contacts_manifest.append({"asset_ref": "BrookfieldEnercare.SemanticModel", "owner_upn": "Ci.Zhu@enercare.ca"})
contacts_manifest.append({"asset_ref": "BrookfieldEnercare.Report", "owner_upn": "Victoria.Tan@enercare.ca"})

label_manifest = dedupe(label_manifest, lambda r: (safe(r["asset_ref"]).lower(), safe(r["label_name"]).lower()))
glossary_manifest = dedupe(glossary_manifest, lambda r: (safe(r["asset_ref"]).lower(), safe(r["term_name"]).lower()))
description_manifest = dedupe(description_manifest, lambda r: (safe(r["asset_ref"]).lower(), safe(r["description"]).lower()[:120]))
contacts_manifest = dedupe(contacts_manifest, lambda r: (safe(r["asset_ref"]).lower(), safe(r["owner_upn"]).lower()))

report = {
    "counts": {
        "label_manifest_rows": len(label_manifest),
        "glossary_manifest_rows": len(glossary_manifest),
        "description_manifest_rows": len(description_manifest),
        "contacts_manifest_rows": len(contacts_manifest),
    },
    "results": {
        "labels": {"assigned": 0, "existing": 0, "failed": 0, "unresolved": 0},
        "glossary": {"assigned": 0, "existing": 0, "failed": 0, "unresolved_asset": 0, "unresolved_term": 0},
        "descriptions": {"assigned": 0, "existing": 0, "failed": 0, "unresolved": 0},
        "contacts": {"assigned": 0, "existing": 0, "failed": 0, "unresolved": 0},
    },
}

print("getting token...")
token = az_token()
print("applying labels...")
for i, row in enumerate(label_manifest, 1):
    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["results"]["labels"]["unresolved"] += 1
        continue
    out = apply_label(token, target["guid"], row["label_name"])
    report["results"]["labels"][out] += 1
    if i % 10 == 0:
        print(f"labels {i}/{len(label_manifest)}")

print("applying glossary...")
term_cache = {}
for i, row in enumerate(glossary_manifest, 1):
    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["results"]["glossary"]["unresolved_asset"] += 1
        continue
    key = safe(row["term_name"]).lower()
    if key not in term_cache:
        term_cache[key] = resolve_term_guid(token, row["term_name"])
    term_guid = term_cache.get(key, "")
    if not term_guid:
        report["results"]["glossary"]["unresolved_term"] += 1
        continue
    out = apply_term(token, term_guid, target["guid"], target.get("entityType", ""))
    report["results"]["glossary"][out] += 1
    if i % 10 == 0:
        print(f"glossary {i}/{len(glossary_manifest)}")

print("applying descriptions...")
for i, row in enumerate(description_manifest, 1):
    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["results"]["descriptions"]["unresolved"] += 1
        continue
    out = apply_attr(token, target["guid"], "description", row["description"])
    report["results"]["descriptions"][out] += 1
    if i % 10 == 0:
        print(f"descriptions {i}/{len(description_manifest)}")

print("applying contacts...")
for i, row in enumerate(contacts_manifest, 1):
    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["results"]["contacts"]["unresolved"] += 1
        continue
    out = apply_attr(token, target["guid"], "owner", row["owner_upn"])
    report["results"]["contacts"][out] += 1
    if i % 5 == 0:
        print(f"contacts {i}/{len(contacts_manifest)}")

OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("WROTE", str(OUT))
print(json.dumps(report, indent=2))
