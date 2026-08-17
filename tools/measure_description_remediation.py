import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://Purview-West3.purview.azure.com"
API = "2023-09-01"
AZ_FALLBACK = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
SEED_META = Path("sql/02_metadata_foundation/07_seed_purview_metadata.sql")
OUT = Path("tools/purview_measure_description_remediation_report.json")


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
    with urllib.request.urlopen(r, timeout=40) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


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


def resolve_measure_guid(token, measure_ref):
    vals = search(token, measure_ref, 20)
    for v in vals:
        et = safe(v.get("entityType") or v.get("typeName"))
        if et == "EnercareSemanticMeasure":
            return safe(v.get("id") or v.get("guid"))
    return ""


meta = SEED_META.read_text(encoding="utf-8")
glossary = parse_insert_values(meta, "governance_glossary_terms")
cdes = parse_insert_values(meta, "governance_cdes")

manifest = []
for r in cdes:
    desc = safe(r.get("business_definition"))
    for a in split_tokens(r.get("bound_columns", "")):
        if desc and a.startswith("BrookfieldEnercare/_Measures/"):
            manifest.append({"asset_ref": a, "description": desc, "source": "cdes"})
for r in glossary:
    desc = safe(r.get("definition"))
    for a in split_tokens(r.get("bound_assets", "")):
        if desc and a.startswith("BrookfieldEnercare/_Measures/"):
            manifest.append({"asset_ref": a, "description": desc, "source": "glossary"})

# Dedupe
seen = set()
rows = []
for r in manifest:
    k = (safe(r["asset_ref"]).lower(), safe(r["description"]).lower()[:120])
    if k in seen:
        continue
    seen.add(k)
    rows.append(r)

report = {
    "measure_rows": len(rows),
    "results": {
        "not_supported": 0,
        "resolved_measure_guid": 0,
        "unresolved_measure_guid": 0,
    },
    "items": [],
}

print("getting token...")
tok = az_token()
for r in rows:
    gid = resolve_measure_guid(tok, r["asset_ref"])
    if gid:
        report["results"]["resolved_measure_guid"] += 1
        report["results"]["not_supported"] += 1
        report["items"].append(
            {
                "asset_ref": r["asset_ref"],
                "measure_guid": gid,
                "status": "not_supported_by_type",
                "reason": "EnercareSemanticMeasure typedef has no description/userDescription attribute",
            }
        )
    else:
        report["results"]["unresolved_measure_guid"] += 1
        report["items"].append(
            {
                "asset_ref": r["asset_ref"],
                "measure_guid": "",
                "status": "unresolved_measure_guid",
                "reason": "Search did not return EnercareSemanticMeasure",
            }
        )

OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report["results"], indent=2))
print("WROTE", str(OUT))
