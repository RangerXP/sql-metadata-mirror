import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE = "https://Purview-West3.purview.azure.com"
API = "2023-09-01"
AZ_FALLBACK = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
SEED_META = Path("sql/02_metadata_foundation/07_seed_purview_metadata.sql")
OUT = Path("tools/purview_glossary_unresolved_analysis.json")


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


def search(token, keywords, limit=25):
    st, bd = req("POST", "/datamap/api/search/query", token, body={"keywords": keywords, "limit": limit})
    if st != 200:
        return []
    p = to_json(bd)
    return p.get("value") if isinstance(p, dict) else []


def resolve_term(token, term_name):
    target = safe(term_name).lower()
    if not target:
        return None
    vals = search(token, term_name, 30)
    for e in vals:
        et = safe(e.get("entityType") or e.get("typeName")).lower()
        nm = safe(e.get("name")).lower()
        qn = safe(e.get("qualifiedName")).lower()
        gid = safe(e.get("id") or e.get("guid"))
        if gid and "glossaryterm" in et and (nm == target or target in nm or "@" in qn):
            return {
                "guid": gid,
                "name": safe(e.get("name")),
                "qualifiedName": safe(e.get("qualifiedName")),
                "entityType": safe(e.get("entityType") or e.get("typeName")),
            }
    return None


def classify_asset(asset_ref):
    a = safe(asset_ref).lower()
    if a.startswith("dbo."):
        return "sql_table_or_column_ref"
    if a.startswith("brookfieldenercare/_measures/"):
        return "semantic_measure"
    if a == "brookfieldenercare.semanticmodel":
        return "semantic_model"
    if a == "brookfieldenercare.report":
        return "report"
    return "other"


meta_sql = SEED_META.read_text(encoding="utf-8")
glossary = parse_insert_values(meta_sql, "governance_glossary_terms")
cdes = parse_insert_values(meta_sql, "governance_cdes")

# Build glossary assignment intent manifest (same logic as writer)
manifest = []
code_to_name = {
    safe(r.get("term_code")).upper(): safe(r.get("term_name"))
    for r in glossary
    if safe(r.get("term_code")) and safe(r.get("term_name"))
}
for r in glossary:
    term = safe(r.get("term_name"))
    for a in split_tokens(r.get("bound_assets", "")):
        if term:
            manifest.append(
                {
                    "term_name": term,
                    "term_source": "governance_glossary_terms.bound_assets",
                    "source_key": safe(r.get("term_code") or term),
                    "asset_ref": a,
                    "asset_kind": classify_asset(a),
                }
            )
for r in cdes:
    parent = safe(r.get("parent_glossary_term"))
    term = code_to_name.get(parent.upper(), parent) if parent else safe(r.get("cde_name"))
    for a in split_tokens(r.get("bound_columns", "")):
        if term:
            manifest.append(
                {
                    "term_name": term,
                    "term_source": "governance_cdes.parent_glossary_term|cde_name",
                    "source_key": safe(r.get("cde_id") or term),
                    "asset_ref": a,
                    "asset_kind": classify_asset(a),
                }
            )

seen = set()
dedup = []
for r in manifest:
    k = (safe(r["term_name"]).lower(), safe(r["asset_ref"]).lower())
    if k in seen:
        continue
    seen.add(k)
    dedup.append(r)

term_usage = defaultdict(lambda: {
    "term_name": "",
    "occurrences": 0,
    "source_rows": set(),
    "asset_refs": set(),
    "asset_kind_counts": defaultdict(int),
})

for r in dedup:
    t = safe(r["term_name"])
    tu = term_usage[t.lower()]
    tu["term_name"] = t
    tu["occurrences"] += 1
    tu["source_rows"].add(f"{r['term_source']}:{r['source_key']}")
    tu["asset_refs"].add(safe(r["asset_ref"]))
    tu["asset_kind_counts"][r["asset_kind"]] += 1

print("resolving terms in Purview...")
token = az_token()
unresolved = []
resolved = []
for k in sorted(term_usage.keys()):
    rec = term_usage[k]
    term = rec["term_name"]
    found = resolve_term(token, term)
    out = {
        "term_name": term,
        "occurrences": rec["occurrences"],
        "source_rows": sorted(rec["source_rows"]),
        "asset_refs": sorted(rec["asset_refs"]),
        "asset_kind_counts": dict(sorted(rec["asset_kind_counts"].items())),
        "resolved_in_purview": bool(found),
        "purview_match": found,
    }
    if found:
        resolved.append(out)
    else:
        unresolved.append(out)

summary = {
    "manifest_rows": len(dedup),
    "unique_terms": len(term_usage),
    "resolved_terms": len(resolved),
    "unresolved_terms": len(unresolved),
}

payload = {
    "summary": summary,
    "resolved_terms": resolved,
    "unresolved_terms": unresolved,
}

OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
print(f"WROTE {OUT}")
