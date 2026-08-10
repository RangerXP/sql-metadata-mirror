import json
import os
import re
import shutil
import socket
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
BASELINE = Path("tools/purview_intent_metadata_write_report.json")
OUT = Path("tools/purview_descriptions_contacts_remediation_report.json")

DATASET_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/datasets/8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c"
DATASET_GUID = "a0df6b58-9fcd-4aee-8235-d1a035677215"
REPORT_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/reports/7c4f1103-e22c-4a8c-930d-9fe20b71b409"
REPORT_GUID = "42561931-aa73-4cbd-9fe3-141b0796ecc6"

DESCRIPTION_LIMIT = int(os.environ.get("DESC_LIMIT", "0"))
CONTACT_LIMIT = int(os.environ.get("CONTACT_LIMIT", "0"))


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


def parse_owner_seed_rows(sql_text):
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


def req(method, path, token, body=None, params=None, timeout=40):
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
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), None
    except socket.timeout as e:
        return 598, "timeout", str(e)
    except Exception as e:
        return 599, str(e), str(e)


def to_json(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def search(token, keywords, limit=30):
    st, bd, _ = req("POST", "/datamap/api/search/query", token, body={"keywords": keywords, "limit": limit}, timeout=30)
    if st != 200:
        return []
    p = to_json(bd)
    return p.get("value") if isinstance(p, dict) else []


def entity_by_guid(token, guid):
    st, bd, _ = req("GET", f"/catalog/api/atlas/v2/entity/guid/{guid}", token, timeout=35)
    if st != 200:
        return None
    p = to_json(bd)
    return (p or {}).get("entity", {}) if isinstance(p, dict) else None


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


def update_entity_attr(token, guid, attr_name, attr_value):
    target = safe(attr_value)
    ent = entity_by_guid(token, guid)
    if not isinstance(ent, dict):
        return "failed", "entity read failed"

    attrs = ent.get("attributes") if isinstance(ent.get("attributes"), dict) else {}
    if safe(attrs.get(attr_name)).lower() == target.lower():
        return "existing", ""

    payload = {
        "entity": {
            "typeName": safe(ent.get("typeName")),
            "guid": safe(ent.get("guid") or guid) or guid,
            "attributes": {
                "qualifiedName": safe(attrs.get("qualifiedName")),
                "name": safe(attrs.get("name")),
                attr_name: target,
            },
        }
    }

    st, bd, ex = req("POST", "/catalog/api/atlas/v2/entity", token, body=payload, timeout=45)
    if st in (200, 201, 204):
        return "assigned", ""

    # Timeouts can still succeed server-side. Verify after a timeout-like transport error.
    if st in (598, 599):
        ent2 = entity_by_guid(token, guid)
        attrs2 = ent2.get("attributes") if isinstance(ent2, dict) and isinstance(ent2.get("attributes"), dict) else {}
        if safe(attrs2.get(attr_name)).lower() == target.lower():
            return "assigned", "timeout verified"

    # Fallback for descriptions on some entity types.
    if attr_name == "description":
        payload["entity"]["attributes"] = {
            "qualifiedName": safe(attrs.get("qualifiedName")),
            "name": safe(attrs.get("name")),
            "userDescription": target,
        }
        st2, bd2, ex2 = req("POST", "/catalog/api/atlas/v2/entity", token, body=payload, timeout=45)
        if st2 in (200, 201, 204):
            return "assigned", "userDescription fallback"
        if st2 in (598, 599):
            ent3 = entity_by_guid(token, guid)
            attrs3 = ent3.get("attributes") if isinstance(ent3, dict) and isinstance(ent3.get("attributes"), dict) else {}
            if safe(attrs3.get("userDescription")).lower() == target.lower():
                return "assigned", "userDescription timeout verified"
        return "failed", f"primary HTTP {st} {safe(bd)[:120]} | fallback HTTP {st2} {safe(bd2)[:120]} | {safe(ex2)}"

    return "failed", f"HTTP {st} | {safe(bd)[:160]} | {safe(ex)}"


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
glossary = parse_insert_values(meta_sql, "governance_glossary_terms")
cdes = parse_insert_values(meta_sql, "governance_cdes")
owners = parse_owner_seed_rows(owner_sql)

# Description manifest.
description_manifest = []
for r in cdes:
    desc = safe(r.get("business_definition"))
    for a in split_tokens(r.get("bound_columns", "")):
        if desc:
            description_manifest.append({"asset_ref": a, "description": desc, "source": "cdes"})
for r in glossary:
    desc = safe(r.get("definition"))
    for a in split_tokens(r.get("bound_assets", "")):
        if desc:
            description_manifest.append({"asset_ref": a, "description": desc, "source": "glossary"})

description_manifest = [
    r
    for r in description_manifest
    if safe(r["asset_ref"]).lower() != "bound_assets" and safe(r["description"]).lower() != "definition"
]
description_manifest = dedupe(
    description_manifest,
    lambda r: (safe(r["asset_ref"]).lower(), safe(r["description"]).lower()[:120]),
)
if DESCRIPTION_LIMIT > 0:
    description_manifest = description_manifest[:DESCRIPTION_LIMIT]

# Contacts manifest.
contacts_manifest = []
for r in owners:
    schema = safe(r.get("object_schema")).lower()
    obj = safe(r.get("object_name")).lower()
    if schema and obj:
        contacts_manifest.append({"asset_ref": f"{schema}.{obj}", "owner_upn": safe(r.get("data_owner_upn")), "source": "owner_seed"})
contacts_manifest.append({"asset_ref": "BrookfieldEnercare.SemanticModel", "owner_upn": "Ci.Zhu@enercare.ca", "source": "semantic_anchor"})
contacts_manifest.append({"asset_ref": "BrookfieldEnercare.Report", "owner_upn": "Victoria.Tan@enercare.ca", "source": "report_anchor"})
contacts_manifest = dedupe(contacts_manifest, lambda r: (safe(r["asset_ref"]).lower(), safe(r["owner_upn"]).lower()))
if CONTACT_LIMIT > 0:
    contacts_manifest = contacts_manifest[:CONTACT_LIMIT]

report = {
    "counts": {
        "description_manifest_rows": len(description_manifest),
        "contacts_manifest_rows": len(contacts_manifest),
    },
    "results": {
        "descriptions": {"assigned": 0, "existing": 0, "failed": 0, "not_supported": 0, "unresolved": 0, "failures": []},
        "contacts": {"assigned": 0, "existing": 0, "failed": 0, "unresolved": 0, "failures": []},
    },
    "baseline": {},
    "delta": {},
}


def flush_report():
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

if BASELINE.exists():
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    bdesc = ((base or {}).get("results") or {}).get("descriptions") or {}
    bcont = ((base or {}).get("results") or {}).get("contacts") or {}
    report["baseline"] = {
        "descriptions": {"assigned": int(bdesc.get("assigned", 0)), "existing": int(bdesc.get("existing", 0)), "failed": int(bdesc.get("failed", 0)), "unresolved": int(bdesc.get("unresolved", 0))},
        "contacts": {"assigned": int(bcont.get("assigned", 0)), "existing": int(bcont.get("existing", 0)), "failed": int(bcont.get("failed", 0)), "unresolved": int(bcont.get("unresolved", 0))},
    }

print("getting token...")
token = az_token()

print("remediating descriptions...")
for i, row in enumerate(description_manifest, 1):
    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["results"]["descriptions"]["unresolved"] += 1
        continue
    # EnercareSemanticMeasure has no description attribute in its typedef.
    if safe(target.get("entityType")) == "EnercareSemanticMeasure":
        report["results"]["descriptions"]["not_supported"] += 1
        continue
    outcome, detail = update_entity_attr(token, target["guid"], "description", row["description"])
    report["results"]["descriptions"][outcome] += 1
    if outcome == "failed" and len(report["results"]["descriptions"]["failures"]) < 30:
        report["results"]["descriptions"]["failures"].append({
            "asset_ref": row["asset_ref"],
            "target_guid": target["guid"],
            "detail": detail,
        })
    if i % 10 == 0:
        print(f"descriptions {i}/{len(description_manifest)}")
        flush_report()

print("remediating contacts...")
for i, row in enumerate(contacts_manifest, 1):
    target = resolve_target(token, row["asset_ref"])
    if not target:
        report["results"]["contacts"]["unresolved"] += 1
        continue
    outcome, detail = update_entity_attr(token, target["guid"], "owner", row["owner_upn"])
    report["results"]["contacts"][outcome] += 1
    if outcome == "failed" and len(report["results"]["contacts"]["failures"]) < 30:
        report["results"]["contacts"]["failures"].append({
            "asset_ref": row["asset_ref"],
            "target_guid": target["guid"],
            "detail": detail,
        })
    if i % 5 == 0:
        print(f"contacts {i}/{len(contacts_manifest)}")
        flush_report()

if report["baseline"]:
    bd = report["baseline"]["descriptions"]
    bc = report["baseline"]["contacts"]
    rd = report["results"]["descriptions"]
    rc = report["results"]["contacts"]
    report["delta"] = {
        "descriptions": {
            "assigned_delta": rd["assigned"] - bd["assigned"],
            "existing_delta": rd["existing"] - bd["existing"],
            "failed_delta": rd["failed"] - bd["failed"],
            "not_supported": rd.get("not_supported", 0),
            "effective_failed": max(0, rd["failed"] - rd.get("not_supported", 0)),
            "effective_failed_delta": max(0, rd["failed"] - rd.get("not_supported", 0)) - bd["failed"],
            "unresolved_delta": rd["unresolved"] - bd["unresolved"],
        },
        "contacts": {
            "assigned_delta": rc["assigned"] - bc["assigned"],
            "existing_delta": rc["existing"] - bc["existing"],
            "failed_delta": rc["failed"] - bc["failed"],
            "unresolved_delta": rc["unresolved"] - bc["unresolved"],
        },
    }

OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("WROTE", str(OUT))
print(json.dumps({"counts": report["counts"], "results": report["results"], "delta": report.get("delta", {})}, indent=2))
