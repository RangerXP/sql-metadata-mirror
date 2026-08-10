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
OUT = Path("tools/purview_glossary_remediation_report.json")

DATASET_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/datasets/8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c"
DATASET_GUID = "a0df6b58-9fcd-4aee-8235-d1a035677215"
REPORT_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/reports/7c4f1103-e22c-4a8c-930d-9fe20b71b409"
REPORT_GUID = "42561931-aa73-4cbd-9fe3-141b0796ecc6"


def safe(x):
    return (x or "").strip() if isinstance(x, str) else ("" if x is None else str(x).strip())


def norm(x):
    return "".join(ch for ch in safe(x).lower() if ch.isalnum())


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
        with urllib.request.urlopen(r, timeout=30) as resp:
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


cache = {}


def pick_best(cands, asset_ref):
    ar = safe(asset_ref)
    arl = ar.lower()
    arn = norm(ar)
    best = None
    best_score = -10**9
    for c in cands:
        et = safe(c.get("entityType") or c.get("typeName")).lower()
        qn = safe(c.get("qualifiedName")).lower()
        nm = safe(c.get("name")).lower()
        score = 0

        if arn and arn in norm(qn):
            score += 2

        if arl.startswith("dbo.") and ("table" in et or "view" in et):
            score += 18
        if arl.startswith("brookfieldenercare/_measures/") and "measure" in et:
            score += 20
        if arl in ("brookfieldenercare.report", "brookfieldenercare.semanticmodel") and (
            "report" in et or "dataset" in et
        ):
            score += 16

        if arl.startswith("dbo."):
            parts = ar.split(".")
            tbl = parts[1].lower() if len(parts) > 1 else ""
            if tbl and tbl in qn:
                score += 7
            if tbl and tbl in nm:
                score += 5
            if "mssql://" in qn:
                score += 3

        if ar.startswith("BrookfieldEnercare/_Measures/"):
            m = ar.split("/_Measures/", 1)[1].lower()
            if m and m in qn:
                score += 12

        if arl == "brookfieldenercare.report" and REPORT_QN.lower() in qn:
            score += 20
        if arl == "brookfieldenercare.semanticmodel" and DATASET_QN.lower() in qn:
            score += 20

        if score > best_score:
            best_score = score
            best = c

    return best


def resolve_target(token, asset_ref):
    key = safe(asset_ref).lower()
    if key in cache:
        return cache[key]

    ar = safe(asset_ref)
    cands = []

    if ar.lower().startswith("dbo."):
        p = ar.split(".")
        if len(p) >= 3:
            cands.extend(search(token, f"{p[1]} {' '.join(p[2:])} sqldemo", 30))
        cands.extend(search(token, ar, 30))
        cands.extend(search(token, f"{p[1]} sqldemo", 30))
    elif ar.startswith("BrookfieldEnercare/_Measures/"):
        m = ar.split("/_Measures/", 1)[1]
        cands.extend(search(token, f"{m} measure BrookfieldEnercare", 30))
    elif ar in ("BrookfieldEnercare.Report", "BrookfieldEnercare.SemanticModel"):
        cands.extend(search(token, f"{ar} powerbi", 30))
    else:
        cands.extend(search(token, ar, 20))

    uniq = []
    seen = set()
    for c in cands:
        gid = safe(c.get("id") or c.get("guid"))
        if not gid or gid in seen:
            continue
        seen.add(gid)
        uniq.append(
            {
                "guid": gid,
                "entityType": safe(c.get("entityType") or c.get("typeName")),
                "qualifiedName": safe(c.get("qualifiedName")),
                "name": safe(c.get("name")),
            }
        )

    best = pick_best(uniq, ar)
    if best:
        cache[key] = best
        return best

    fallback = (
        {
            "guid": REPORT_GUID,
            "entityType": "powerbi_report",
            "qualifiedName": REPORT_QN,
            "name": "BrookfieldEnercare",
        }
        if ar == "BrookfieldEnercare.Report"
        else {
            "guid": DATASET_GUID,
            "entityType": "powerbi_dataset",
            "qualifiedName": DATASET_QN,
            "name": "BrookfieldEnercare",
        }
    )
    cache[key] = fallback
    return fallback


def list_glossaries(token):
    st, bd = req("GET", "/catalog/api/atlas/v2/glossary", token)
    if st != 200:
        return []
    p = to_json(bd)
    return p if isinstance(p, list) else []


def create_term(token, glossary_guid, name, long_desc):
    body = {
        "name": name,
        "shortDescription": (long_desc or name)[:200],
        "longDescription": long_desc or name,
        "anchor": {"glossaryGuid": glossary_guid},
    }
    st, bd = req("POST", "/catalog/api/atlas/v2/glossary/term", token, body=body)
    if st in (200, 201):
        p = to_json(bd)
        return safe((p or {}).get("guid") or (p or {}).get("termGuid")), ""
    return "", f"HTTP {st} | {bd[:240]}"


def is_term_assigned(token, term_guid, entity_guid):
    st, bd = req("GET", f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities", token)
    if st != 200:
        return False
    p = to_json(bd)
    return isinstance(p, list) and any(safe(e.get("guid")) == safe(entity_guid) for e in p)


def apply_term(token, term_guid, entity_guid, entity_type):
    if is_term_assigned(token, term_guid, entity_guid):
        return "existing", ""
    body = [{"guid": entity_guid, "typeName": safe(entity_type)}]
    st, bd = req("POST", f"/catalog/api/atlas/v2/glossary/terms/{term_guid}/assignedEntities", token, body=body)
    if st in (200, 201, 202, 204):
        return "assigned", ""
    if is_term_assigned(token, term_guid, entity_guid):
        return "existing", ""
    return "failed", f"HTTP {st} | {bd[:240]}"


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
glossary_rows = parse_insert_values(meta_sql, "governance_glossary_terms")
cdes = parse_insert_values(meta_sql, "governance_cdes")

# Definition map used when creating missing terms
term_def = {safe(r.get("term_name")).lower(): safe(r.get("definition")) for r in glossary_rows if safe(r.get("term_name"))}

# Build manifest
manifest = []
code_to_name = {
    safe(r.get("term_code")).upper(): safe(r.get("term_name"))
    for r in glossary_rows
    if safe(r.get("term_code")) and safe(r.get("term_name"))
}

for r in glossary_rows:
    term = safe(r.get("term_name"))
    term_code = safe(r.get("term_code") or term)
    for a in split_tokens(r.get("bound_assets", "")):
        if term and term.lower() != "term_name" and a.lower() != "bound_assets":
            manifest.append({"asset_ref": a, "term_name": term, "term_code": term_code, "source": "governance_glossary_terms"})

for r in cdes:
    parent = safe(r.get("parent_glossary_term"))
    term = code_to_name.get(parent.upper(), parent) if parent else safe(r.get("cde_name"))
    for a in split_tokens(r.get("bound_columns", "")):
        if term and term.lower() != "term_name" and a.lower() != "bound_assets":
            manifest.append({"asset_ref": a, "term_name": term, "term_code": safe(r.get("cde_id") or term), "source": "governance_cdes"})

manifest = dedupe(manifest, lambda r: (safe(r["asset_ref"]).lower(), safe(r["term_name"]).lower()))

report = {
    "counts": {
        "manifest_rows": len(manifest),
        "terms_in_manifest": len({safe(r['term_name']).lower() for r in manifest}),
    },
    "glossary": {
        "selected_glossary_guid": "",
        "selected_glossary_name": "",
        "existing_terms_loaded": 0,
        "created": 0,
        "create_failed": 0,
        "created_terms": [],
        "create_failures": [],
    },
    "assignments": {
        "assigned": 0,
        "existing": 0,
        "failed": 0,
        "unresolved_asset": 0,
        "unresolved_term": 0,
        "samples": [],
        "failures": [],
    },
}

print("getting token...")
token = az_token()

print("loading glossaries...")
glossaries = list_glossaries(token)
selected = None
for g in glossaries:
    if safe(g.get("name")).lower() == "enercare glossary":
        selected = g
        break
if not selected and glossaries:
    selected = glossaries[0]
if not selected:
    raise SystemExit("No glossary found in Purview")

glossary_guid = safe(selected.get("guid"))
glossary_name = safe(selected.get("name"))
report["glossary"]["selected_glossary_guid"] = glossary_guid
report["glossary"]["selected_glossary_name"] = glossary_name

existing_terms = {}
for t in selected.get("terms", []):
    gid = safe(t.get("guid") or t.get("termGuid"))
    name = safe(t.get("name") or t.get("displayText"))
    if gid and name:
        existing_terms[name.lower()] = {"guid": gid, "name": name}
report["glossary"]["existing_terms_loaded"] = len(existing_terms)

# Ensure all terms in manifest exist in glossary
wanted_terms = sorted({safe(r["term_name"]) for r in manifest if safe(r["term_name"])})
for term in wanted_terms:
    key = term.lower()
    if key in existing_terms:
        continue
    desc = safe(term_def.get(key)) or term
    guid, err = create_term(token, glossary_guid, term, desc)
    if guid:
        existing_terms[key] = {"guid": guid, "name": term}
        report["glossary"]["created"] += 1
        report["glossary"]["created_terms"].append({"term_name": term, "term_guid": guid})
    else:
        report["glossary"]["create_failed"] += 1
        report["glossary"]["create_failures"].append({"term_name": term, "error": err})

print("applying glossary assignments...")
for i, row in enumerate(manifest, 1):
    term = safe(row["term_name"])
    tk = term.lower()
    tinfo = existing_terms.get(tk)
    if not tinfo:
        report["assignments"]["unresolved_term"] += 1
        continue

    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["assignments"]["unresolved_asset"] += 1
        continue

    outcome, details = apply_term(token, tinfo["guid"], target["guid"], target.get("entityType", ""))
    report["assignments"][outcome] += 1

    if len(report["assignments"]["samples"]) < 40:
        report["assignments"]["samples"].append(
            {
                "asset_ref": row["asset_ref"],
                "term_name": term,
                "term_guid": tinfo["guid"],
                "target_guid": target.get("guid"),
                "target_entityType": target.get("entityType"),
                "outcome": outcome,
            }
        )
    if outcome == "failed" and len(report["assignments"]["failures"]) < 30:
        report["assignments"]["failures"].append(
            {
                "asset_ref": row["asset_ref"],
                "term_name": term,
                "details": details,
            }
        )

    if i % 10 == 0:
        print(f"assigned {i}/{len(manifest)}")

OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("WROTE", str(OUT))
print(
    json.dumps(
        {
            "counts": report["counts"],
            "glossary": {
                "selected_glossary_name": report["glossary"]["selected_glossary_name"],
                "existing_terms_loaded": report["glossary"]["existing_terms_loaded"],
                "created": report["glossary"]["created"],
                "create_failed": report["glossary"]["create_failed"],
            },
            "assignments": {
                "assigned": report["assignments"]["assigned"],
                "existing": report["assignments"]["existing"],
                "failed": report["assignments"]["failed"],
                "unresolved_asset": report["assignments"]["unresolved_asset"],
                "unresolved_term": report["assignments"]["unresolved_term"],
            },
        },
        indent=2,
    )
)
