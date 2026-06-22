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

SEED = Path("sql/07_seed_purview_metadata.sql")
BASE_REPORT = Path("tools/purview_intent_metadata_write_report.json")
DESC_CONTACT_REPORT = Path("tools/purview_descriptions_contacts_remediation_report.json")
MEASURE_DESC_REPORT = Path("tools/purview_measure_description_remediation_report.json")
MEASURE_GOV_REPORT = Path("tools/purview_measure_governance_report.json")

OUT_SCORECARD = Path("tools/purview_lh_metadata_scorecard_report.json")
OUT_CONSOLIDATED = Path("tools/purview_consolidated_final_delta_report.json")

DATASET_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/datasets/8cb6f6a6-6a9c-4560-9f28-17a1dc4a921c"
REPORT_QN = "https://app.powerbi.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/reports/7c4f1103-e22c-4a8c-930d-9fe20b71b409"


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


def parse_expected_count(sql_text, table):
    m = re.search(rf"-\s*{re.escape(table)}:\s*(\d+)", sql_text, flags=re.I)
    return int(m.group(1)) if m else 0


def parse_roles_from_cte(sql_text):
    m = re.search(
        r"WITH\s+roles\s+AS\s*\(\s*SELECT\s+\*\s+FROM\s*\(VALUES\s*(.*?)\)\s*v\s*\(",
        sql_text,
        flags=re.I | re.S,
    )
    if not m:
        return []

    cols = [
        "role_id",
        "principal_email",
        "principal_display_name",
        "role_type",
        "scope_target",
        "scope_target_type",
        "governance_layer",
    ]

    block = m.group(1)
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
    if not az:
        raise RuntimeError("Azure CLI not found")
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


def classify_ref(asset_ref):
    a = safe(asset_ref).lower()
    if a.startswith("dbo."):
        parts = a.split(".")
        if len(parts) >= 3:
            return "sql_column"
        if len(parts) == 2:
            return "sql_table"
    if a.startswith("brookfieldenercare/_measures/"):
        return "semantic_measure"
    if a.startswith("brookfieldenercare/"):
        return "semantic_object"
    if a in ("brookfieldenercare.semanticmodel", "brookfieldenercare.report"):
        return "semantic_anchor"
    if a.startswith("dp-"):
        return "data_product_ref"
    if a.startswith("dom-"):
        return "domain_ref"
    if ":" in a:
        return "logical_ref"
    return "other"


resolve_cache = {}


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

        if arl.startswith("dbo.") and ("table" in et or "column" in et or "view" in et):
            score += 18
        if arl.startswith("brookfieldenercare/_measures/") and "measure" in et:
            score += 20
        if arl in ("brookfieldenercare.report", "brookfieldenercare.semanticmodel") and (
            "report" in et or "dataset" in et or "semantic" in et
        ):
            score += 16

        if arl.startswith("dbo."):
            parts = ar.split(".")
            tbl = parts[1].lower() if len(parts) > 1 else ""
            col = parts[2].lower() if len(parts) > 2 else ""
            if tbl and tbl in qn:
                score += 7
            if tbl and tbl in nm:
                score += 5
            if col and col in qn:
                score += 6
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
    if key in resolve_cache:
        return resolve_cache[key]

    ar = safe(asset_ref)
    candidates = []

    if ar.lower().startswith("dbo."):
        p = ar.split(".")
        if len(p) >= 3:
            candidates.extend(search(token, f"{p[1]} {p[2]} sqldemo", 35))
        candidates.extend(search(token, ar, 35))
    elif ar.startswith("BrookfieldEnercare/_Measures/"):
        m = ar.split("/_Measures/", 1)[1]
        candidates.extend(search(token, f"{m} measure BrookfieldEnercare", 35))
    elif ar in ("BrookfieldEnercare.Report", "BrookfieldEnercare.SemanticModel"):
        candidates.extend(search(token, f"{ar} powerbi", 35))
    elif ar.startswith("DOM-") or ar.startswith("DP-"):
        candidates.extend(search(token, ar, 35))
    else:
        candidates.extend(search(token, ar, 25))

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
                "entityType": safe(c.get("entityType") or c.get("typeName")),
                "qualifiedName": safe(c.get("qualifiedName")),
                "name": safe(c.get("name")),
            }
        )

    best = pick_best(uniq, ar)
    resolve_cache[key] = best
    return best


def looks_like_column_ref(asset_ref):
    a = safe(asset_ref)
    return a.lower().startswith("dbo.") and len(a.split(".")) >= 3


def looks_like_column_entity(entity_type, qualified_name):
    et = safe(entity_type).lower()
    qn = safe(qualified_name).lower()
    if "column" in et:
        return True
    if "/columns/" in qn:
        return True
    return False


def is_domain_entity_type(entity_type):
    et = safe(entity_type).lower()
    return any(token in et for token in ["domain", "purview_datadomain", "datadomain"]) 


def is_product_entity_type(entity_type):
    et = safe(entity_type).lower()
    return any(token in et for token in ["dataproduct", "data_product", "product"]) 


def resolve_publication_entity(token, code, name, kind):
    cands = []
    for kw in [code, name, f"{code} {name}"]:
        if kw:
            cands.extend(search(token, kw, 40))

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

    filtered = []
    for c in uniq:
        et = safe(c.get("entityType"))
        if kind == "domain" and not is_domain_entity_type(et):
            continue
        if kind == "product" and not is_product_entity_type(et):
            continue
        filtered.append(c)

    if not filtered:
        return None

    best = None
    best_score = -10**9
    code_n = norm(code)
    name_n = norm(name)
    for c in filtered:
        qn = safe(c.get("qualifiedName"))
        nm = safe(c.get("name"))
        score = 0
        if code_n and code_n in norm(qn):
            score += 8
        if code_n and code_n in norm(nm):
            score += 8
        if name_n and name_n in norm(qn):
            score += 5
        if name_n and name_n in norm(nm):
            score += 5
        if score > best_score:
            best_score = score
            best = c
    return best


def lineage_exists(token, guid):
    if not guid:
        return {"exists": False, "relation_count": 0, "http_status": 0}
    st, bd = req("GET", f"/catalog/api/atlas/v2/lineage/{guid}", token, params={"direction": "BOTH", "depth": 3})
    if st != 200:
        return {"exists": False, "relation_count": 0, "http_status": st, "detail": safe(bd)[:200]}
    p = to_json(bd) if bd else {}
    rels = (p or {}).get("relations") or []
    return {"exists": len(rels) > 0, "relation_count": len(rels), "http_status": st}


def refresh_consolidated_delta():
    base = to_json(BASE_REPORT.read_text(encoding="utf-8")) or {}
    run = to_json(DESC_CONTACT_REPORT.read_text(encoding="utf-8")) or {}
    measure_desc = to_json(MEASURE_DESC_REPORT.read_text(encoding="utf-8")) or {}
    measure_gov = to_json(MEASURE_GOV_REPORT.read_text(encoding="utf-8")) or {}

    base_desc = ((base.get("results") or {}).get("descriptions") or {})
    base_contacts = ((base.get("results") or {}).get("contacts") or {})
    run_desc = ((run.get("results") or {}).get("descriptions") or {})
    run_contacts = ((run.get("results") or {}).get("contacts") or {})

    not_supported = int((measure_desc.get("results") or {}).get("not_supported") or run_desc.get("not_supported") or 0)
    failed_raw = int(run_desc.get("failed") or 0)
    effective_failed = max(0, failed_raw - not_supported)

    final = {
        "baseline": {
            "descriptions": base_desc,
            "contacts": base_contacts,
        },
        "final": {
            "descriptions": {
                "assigned": int(run_desc.get("assigned") or 0),
                "existing": int(run_desc.get("existing") or 0),
                "failed_raw": failed_raw,
                "not_supported": not_supported,
                "failed_effective": effective_failed,
                "unresolved": int(run_desc.get("unresolved") or 0),
            },
            "contacts": {
                "assigned": int(run_contacts.get("assigned") or 0),
                "existing": int(run_contacts.get("existing") or 0),
                "failed": int(run_contacts.get("failed") or 0),
                "unresolved": int(run_contacts.get("unresolved") or 0),
            },
        },
        "delta": {
            "descriptions": {
                "assigned_delta": int(run_desc.get("assigned") or 0) - int(base_desc.get("assigned") or 0),
                "existing_delta": int(run_desc.get("existing") or 0) - int(base_desc.get("existing") or 0),
                "failed_raw_delta": failed_raw - int(base_desc.get("failed") or 0),
                "failed_effective_delta": effective_failed - int(base_desc.get("failed") or 0),
                "unresolved_delta": int(run_desc.get("unresolved") or 0) - int(base_desc.get("unresolved") or 0),
            },
            "contacts": {
                "assigned_delta": int(run_contacts.get("assigned") or 0) - int(base_contacts.get("assigned") or 0),
                "existing_delta": int(run_contacts.get("existing") or 0) - int(base_contacts.get("existing") or 0),
                "failed_delta": int(run_contacts.get("failed") or 0) - int(base_contacts.get("failed") or 0),
                "unresolved_delta": int(run_contacts.get("unresolved") or 0) - int(base_contacts.get("unresolved") or 0),
            },
        },
        "notes": {
            "measure_description_path": "EnercareSemanticMeasure has no description/userDescription attribute in Purview typedef; counted as not_supported.",
            "measure_governance": {
                "resolution": (measure_gov.get("resolution") or {}),
                "labels": (measure_gov.get("labels") or {}),
                "meanings": (measure_gov.get("meanings") or {}),
            },
            "source_reports": [
                str(BASE_REPORT).replace("\\", "/"),
                str(DESC_CONTACT_REPORT).replace("\\", "/"),
                str(MEASURE_DESC_REPORT).replace("\\", "/"),
                str(MEASURE_GOV_REPORT).replace("\\", "/"),
            ],
        },
    }

    OUT_CONSOLIDATED.write_text(json.dumps(final, indent=2), encoding="utf-8")
    return final


def audit():
    seed = SEED.read_text(encoding="utf-8")
    domains = parse_insert_values(seed, "governance_domains")
    products = parse_insert_values(seed, "governance_data_products")
    roles = parse_roles_from_cte(seed)
    expected_roles = parse_expected_count(seed, "governance_role_assignments")
    cdes = parse_insert_values(seed, "governance_cdes")
    glossary = parse_insert_values(seed, "governance_glossary_terms")
    labels = parse_insert_values(seed, "governance_label_assignments")

    token = az_token()

    domain_checks = []
    domain_resolved_by_code = {}
    for d in domains:
        domain_id = safe(d.get("domain_id"))
        domain_name = safe(d.get("domain_name"))
        hit = resolve_publication_entity(token, domain_id, domain_name, "domain")
        resolved = bool(hit)
        domain_resolved_by_code[domain_id] = resolved
        domain_checks.append(
            {
                "domain_id": domain_id,
                "domain_name": domain_name,
                "resolved": resolved,
                "target_guid": safe((hit or {}).get("guid")),
                "target_entityType": safe((hit or {}).get("entityType")),
                "target_name": safe((hit or {}).get("name")),
            }
        )

    product_checks = []
    product_resolved_by_code = {}
    for p in products:
        product_id = safe(p.get("data_product_id"))
        product_name = safe(p.get("data_product_name"))
        hit = resolve_publication_entity(token, product_id, product_name, "product")
        attached = split_tokens(p.get("attached_assets"))
        attached_res = 0
        attached_unres = 0
        for a in attached:
            if resolve_target(token, a):
                attached_res += 1
            else:
                attached_unres += 1
        resolved = bool(hit)
        product_resolved_by_code[product_id] = resolved
        product_checks.append(
            {
                "data_product_id": product_id,
                "data_product_name": product_name,
                "resolved": resolved,
                "target_guid": safe((hit or {}).get("guid")),
                "target_entityType": safe((hit or {}).get("entityType")),
                "target_name": safe((hit or {}).get("name")),
                "attached_assets_total": len(attached),
                "attached_assets_resolved": attached_res,
                "attached_assets_unresolved": attached_unres,
            }
        )

    role_checks = []
    for r in roles:
        role_id = safe(r.get("role_id"))
        principal = safe(r.get("principal_email"))
        role_type = safe(r.get("role_type"))
        scope_target = safe(r.get("scope_target"))
        scope_type = safe(r.get("scope_target_type"))

        scope_status = "unknown"
        scope_hit = None
        if scope_target.startswith("DOM-"):
            scope_status = "resolved" if domain_resolved_by_code.get(scope_target, False) else "unresolved"
        elif scope_target.startswith("DP-"):
            scope_status = "resolved" if product_resolved_by_code.get(scope_target, False) else "unresolved"
        elif scope_target.lower() in ("enercare", "tenant") or scope_type.lower() == "tenant":
            scope_status = "tenant_scope"
        else:
            scope_hit = resolve_target(token, scope_target)
            scope_status = "resolved" if scope_hit else "unresolved"

        role_checks.append(
            {
                "role_id": role_id,
                "principal_email": principal,
                "role_type": role_type,
                "scope_target": scope_target,
                "scope_target_type": scope_type,
                "scope_status": scope_status,
                "target_guid": safe((scope_hit or {}).get("guid")),
                "target_entityType": safe((scope_hit or {}).get("entityType")),
                "target_name": safe((scope_hit or {}).get("name")),
            }
        )

    # Column fidelity checks from all seed metadata sources that bind assets.
    candidate_asset_refs = set()
    for row in cdes:
        for a in split_tokens(row.get("bound_columns")):
            candidate_asset_refs.add(a)
    for row in glossary:
        for a in split_tokens(row.get("bound_assets")):
            candidate_asset_refs.add(a)
    for row in labels:
        for a in split_tokens(row.get("applies_to_asset_ids")):
            candidate_asset_refs.add(a)

    column_fidelity_exceptions = []
    for asset_ref in sorted(candidate_asset_refs):
        if not looks_like_column_ref(asset_ref):
            continue
        hit = resolve_target(token, asset_ref)
        if not hit:
            column_fidelity_exceptions.append(
                {
                    "asset_ref": asset_ref,
                    "issue": "column_ref_unresolved",
                    "target_guid": "",
                    "target_entityType": "",
                    "target_qualifiedName": "",
                }
            )
            continue
        if not looks_like_column_entity(hit.get("entityType"), hit.get("qualifiedName")):
            column_fidelity_exceptions.append(
                {
                    "asset_ref": asset_ref,
                    "issue": "column_ref_resolved_to_non_column_entity",
                    "target_guid": safe(hit.get("guid")),
                    "target_entityType": safe(hit.get("entityType")),
                    "target_qualifiedName": safe(hit.get("qualifiedName")),
                }
            )

    # Lineage checks for a practical lh_metadata-wide sample of anchors and attached assets.
    lineage_targets = set([
        "BrookfieldEnercare.SemanticModel",
        "BrookfieldEnercare.Report",
    ])
    for p in products:
        for a in split_tokens(p.get("attached_assets")):
            if classify_ref(a) in ("sql_table", "semantic_object", "semantic_anchor"):
                lineage_targets.add(a)

    lineage_checks = []
    for ref in sorted(lineage_targets):
        hit = resolve_target(token, ref)
        if not hit:
            lineage_checks.append(
                {
                    "asset_ref": ref,
                    "resolved": False,
                    "target_guid": "",
                    "target_entityType": "",
                    "lineage_exists": False,
                    "lineage_relation_count": 0,
                    "lineage_http_status": 0,
                }
            )
            continue
        lineage = lineage_exists(token, safe(hit.get("guid")))
        lineage_checks.append(
            {
                "asset_ref": ref,
                "resolved": True,
                "target_guid": safe(hit.get("guid")),
                "target_entityType": safe(hit.get("entityType")),
                "lineage_exists": bool(lineage.get("exists")),
                "lineage_relation_count": int(lineage.get("relation_count") or 0),
                "lineage_http_status": int(lineage.get("http_status") or 0),
            }
        )

    consolidated = refresh_consolidated_delta()

    scorecard = {
        "scope": "lh_metadata-wide metadata enrichment audit",
        "counts": {
            "seed_domains": len(domains),
            "seed_data_products": len(products),
            "seed_role_assignments_seeded": expected_roles,
            "seed_role_assignments_base_set": len(roles),
            "seed_glossary_terms": len(glossary),
            "seed_cdes": len(cdes),
            "seed_label_assignments": len(labels),
        },
        "publication_checks": {
            "domains": {
                "resolved": sum(1 for x in domain_checks if x.get("resolved")),
                "unresolved": sum(1 for x in domain_checks if not x.get("resolved")),
                "items": domain_checks,
            },
            "data_products": {
                "resolved": sum(1 for x in product_checks if x.get("resolved")),
                "unresolved": sum(1 for x in product_checks if not x.get("resolved")),
                "items": product_checks,
            },
            "roles": {
                "resolved_scope": sum(1 for x in role_checks if x.get("scope_status") in ("resolved", "tenant_scope")),
                "unresolved_scope": sum(1 for x in role_checks if x.get("scope_status") == "unresolved"),
                "items": role_checks,
            },
        },
        "column_fidelity": {
            "exceptions": len(column_fidelity_exceptions),
            "items": column_fidelity_exceptions,
        },
        "lineage_checks": {
            "targets_checked": len(lineage_checks),
            "resolved_targets": sum(1 for x in lineage_checks if x.get("resolved")),
            "targets_with_lineage": sum(1 for x in lineage_checks if x.get("lineage_exists")),
            "targets_without_lineage": sum(1 for x in lineage_checks if x.get("resolved") and not x.get("lineage_exists")),
            "unresolved_targets": sum(1 for x in lineage_checks if not x.get("resolved")),
            "items": lineage_checks,
        },
        "refreshed_consolidated_delta": {
            "file": str(OUT_CONSOLIDATED).replace("\\", "/"),
            "delta": consolidated.get("delta", {}),
            "final": consolidated.get("final", {}),
        },
        "source_files": [
            str(SEED).replace("\\", "/"),
            str(BASE_REPORT).replace("\\", "/"),
            str(DESC_CONTACT_REPORT).replace("\\", "/"),
            str(MEASURE_DESC_REPORT).replace("\\", "/"),
            str(MEASURE_GOV_REPORT).replace("\\", "/"),
        ],
    }

    OUT_SCORECARD.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")

    print(f"WROTE {OUT_SCORECARD}")
    print(f"WROTE {OUT_CONSOLIDATED}")
    print(
        json.dumps(
            {
                "publication": {
                    "domains": scorecard["publication_checks"]["domains"]["resolved"],
                    "data_products": scorecard["publication_checks"]["data_products"]["resolved"],
                    "roles_scope_resolved": scorecard["publication_checks"]["roles"]["resolved_scope"],
                    "roles_scope_unresolved": scorecard["publication_checks"]["roles"]["unresolved_scope"],
                },
                "column_fidelity_exceptions": scorecard["column_fidelity"]["exceptions"],
                "lineage": {
                    "targets_checked": scorecard["lineage_checks"]["targets_checked"],
                    "targets_with_lineage": scorecard["lineage_checks"]["targets_with_lineage"],
                    "targets_without_lineage": scorecard["lineage_checks"]["targets_without_lineage"],
                    "unresolved_targets": scorecard["lineage_checks"]["unresolved_targets"],
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    audit()
