"""
Governance-contract compliance audit: SQL (the seed .sql files under
sql/02_metadata_foundation/) is the authoritative governance contract for this
demo's metadata layer. This tool validates that BOTH the sub2 SQL source and
the lh_metadata Lakehouse destination actually conform to that contract:

  1. VALUE-LEVEL parity -- every column of every seeded row matches the
     seed .sql file's declared value exactly (not just "non-null").
  2. ROW COUNTS -- each table has the exact row count the seed script's own
     header comment declares.
  3. ENUM/ALLOWED-VALUE compliance -- constrained columns (domain_type,
     product_type, expected_data_type, ...) only contain values nb_02's own
     validate_csv() enum_cols would accept.
  4. REFERENTIAL INTEGRITY -- foreign-key-shaped references (data_products ->
     domains, cdes -> glossary_terms, okr_key_results -> okrs, ...) all
     resolve to an existing parent row.

Scope: the "pure seed" scripts that fully DELETE+INSERT (or are otherwise a
static declarative VALUES list) for their target tables. CTE/computed portions
(e.g. synthetic filler rows) are parsed where reasonably possible for value
parity; anything not parseable is reported as "unchecked" rather than
silently skipped, but counts/enum/referential checks still run against it.

Usage:
    python tools/audit_seed_vs_source.py --target both
    python tools/audit_seed_vs_source.py --target lakehouse --backfill
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

SUB2_SERVER = "sqlserver-sk2wus3.database.windows.net"
SUB2_DATABASE = "sqldemo"
LAKEHOUSE_SERVER = "sf3ojnzgs5tu7iyc4vtycxzvei-ylfhnokuo5qubcgcmhakyalkte.datawarehouse.fabric.microsoft.com"
LAKEHOUSE_DATABASE = "lh_metadata"

# dataset key (bare, lh_metadata-style name) -> (seed .sql file, sub2 table name, key column)
SEED_SOURCES = [
    ("domains", "sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_domains", "domain_id"),
    ("data_products", "sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_data_products", "data_product_id"),
    ("glossary_terms", "sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_glossary_terms", "term_code"),
    ("cdes", "sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_cdes", "cde_id"),
    ("label_assignments", "sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_label_assignments", "label_id"),
    ("okrs", "sql/02_metadata_foundation/12_seed_ontology_okrs.sql", "governance_okrs", "okr_id"),
    ("okr_key_results", "sql/02_metadata_foundation/12_seed_ontology_okrs.sql", "governance_okr_key_results", "key_result_id"),
    ("okr_data_products", "sql/02_metadata_foundation/12_seed_ontology_okrs.sql", "governance_okr_data_products", "okr_id"),
]

# Expected row counts per the seed scripts' own header comments (governance_change_requests
# is a dynamic gate-workflow ledger, not a pure seed -- checked as "must be >= " instead).
EXPECTED_COUNTS = {
    "domains": 3, "data_products": 3, "glossary_terms": 35, "cdes": 12,
    "role_assignments": 48, "label_assignments": 9,
    "okrs": 3, "okr_key_results": 5, "okr_data_products": 3,
}
MIN_COUNTS = {"governance_change_requests": 10}

# (dataset key, column) -> allowed values, matching nb_02's own validate_csv() enum_cols.
ENUM_RULES = {
    ("domains", "domain_type"): {"Data domain", "Functional unit", "Line of business", "Regulatory", "Project"},
    ("data_products", "product_type"): {"Dataset", "Dashboards/Reports", "Master and reference data"},
    ("cdes", "expected_data_type"): {"number", "text", "date", "Boolean"},
}

# (dataset key, fk column, ref dataset key, ref column, nullable)
REFERENTIAL_RULES = [
    ("data_products", "parent_domain_id", "domains", "domain_id", False),
    ("glossary_terms", "domain_code", "domains", "domain_id", False),
    ("glossary_terms", "parent_term_code", "glossary_terms", "term_code", True),
    ("cdes", "parent_glossary_term", "glossary_terms", "term_code", False),
    ("okrs", "domain_id", "domains", "domain_id", False),
    ("okr_key_results", "okr_id", "okrs", "okr_id", False),
    ("okr_data_products", "okr_id", "okrs", "okr_id", False),
    ("okr_data_products", "data_product_id", "data_products", "data_product_id", False),
]

TABLE_NAME_MAP = {key: sub2_table for key, _, sub2_table, _ in SEED_SOURCES}
TABLE_NAME_MAP.update({
    "role_assignments": "governance_role_assignments",
    "governance_change_requests": "governance_change_requests",
})


def table_name(dataset_key: str, table_names: Optional[dict]) -> str:
    if table_names is None:
        return dataset_key
    return f"dbo.{table_names[dataset_key]}"


def run_sqlcmd(server: str, database: str, query: str) -> str:
    result = subprocess.run(
        ["sqlcmd", "-S", server, "-d", database, "-G", "-C", "-Q", query, "-s", "|", "-W", "-h", "-1"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sqlcmd failed: {result.stderr or result.stdout}")
    return result.stdout


def parse_insert_values(sql_text: str, table: str):
    """Parse a static `INSERT INTO dbo.<table> (...) VALUES (...), (...);` block."""
    m = re.search(
        rf"INSERT\s+INTO\s+dbo\.{re.escape(table)}\s*\(([^)]*)\)\s*VALUES\s*(.*?)(?:\nGO|\nPRINT|\n;WITH|$)",
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
                rec[c] = None
            elif v.startswith("'") and v.endswith("'"):
                rec[c] = v[1:-1].replace("''", "'")
            else:
                rec[c] = v
        rows.append(rec)
    return rows


def query_keyed_rows(server: str, database: str, full_table: str, cols: list, key_col: str) -> dict:
    col_list = ", ".join(cols)
    out = run_sqlcmd(server, database, f"SET NOCOUNT ON; SELECT {col_list} FROM {full_table};")
    rows = {}
    for line in out.splitlines():
        line = line.rstrip("\n")
        if not line.strip() or line.strip().startswith("(") or "rows affected" in line or "Statement ID" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != len(cols):
            continue
        rec = dict(zip(cols, parts))
        key_val = rec.get(key_col)
        if key_val:
            rows[key_val] = {k: (v if v not in ("NULL", "") else None) for k, v in rec.items()}
    return rows


def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def audit_value_parity(server: str, database: str, table_names: Optional[dict]):
    findings = []
    backfill_statements = []

    for dataset_key, rel_path, sub2_table, key_col in SEED_SOURCES:
        sql_path = REPO_ROOT / rel_path
        sql_text = sql_path.read_text(encoding="utf-8")
        expected_rows = parse_insert_values(sql_text, sub2_table)
        if not expected_rows:
            findings.append({
                "table": dataset_key, "status": "UNPARSEABLE",
                "detail": "No static INSERT VALUES block found (may be CTE/computed-only); not checked.",
            })
            continue

        cols = list(expected_rows[0].keys())
        full_table = table_name(dataset_key, table_names)
        try:
            live_rows = query_keyed_rows(server, database, full_table, cols, key_col)
        except RuntimeError as ex:
            findings.append({"table": dataset_key, "status": "QUERY_ERROR", "detail": str(ex)})
            continue

        missing_keys = []
        drift_cells = []
        for exp in expected_rows:
            key_val = exp.get(key_col)
            live = live_rows.get(key_val)
            if live is None:
                missing_keys.append(key_val)
                continue
            for col, exp_val in exp.items():
                if col == key_col:
                    continue
                live_val = live.get(col)
                # Full value-level comparison, not just null-vs-non-null.
                if (exp_val or "") != (live_val or ""):
                    drift_cells.append({
                        "key": key_val, "column": col,
                        "expected": exp_val, "live": live_val,
                    })
                    if exp_val is not None and live_val is None:
                        backfill_statements.append(
                            f"UPDATE {full_table} SET {col} = {sql_literal(exp_val)} "
                            f"WHERE {key_col} = {sql_literal(key_val)};"
                        )

        findings.append({
            "table": dataset_key,
            "status": "OK" if not missing_keys and not drift_cells else "DRIFT",
            "expected_row_count": len(expected_rows),
            "live_row_count": len(live_rows),
            "missing_keys": missing_keys,
            "drift_cells": drift_cells,
        })

    return findings, backfill_statements


def audit_row_counts(server: str, database: str, table_names: Optional[dict]):
    findings = []
    for dataset_key in list(EXPECTED_COUNTS.keys()) + list(MIN_COUNTS.keys()):
        full_table = table_name(dataset_key, table_names)
        try:
            out = run_sqlcmd(server, database, f"SET NOCOUNT ON; SELECT COUNT(*) FROM {full_table};")
        except RuntimeError as ex:
            findings.append({"table": dataset_key, "status": "QUERY_ERROR", "detail": str(ex)})
            continue
        actual = None
        for line in out.splitlines():
            token = line.strip()
            if token.isdigit():
                actual = int(token)
                break
        if dataset_key in EXPECTED_COUNTS:
            expected = EXPECTED_COUNTS[dataset_key]
            findings.append({
                "table": dataset_key, "expected": expected, "actual": actual,
                "status": "PASS" if actual == expected else "FAIL",
            })
        else:
            minimum = MIN_COUNTS[dataset_key]
            findings.append({
                "table": dataset_key, "minimum": minimum, "actual": actual,
                "status": "PASS" if actual is not None and actual >= minimum else "FAIL",
            })
    return findings


def audit_enum_compliance(server: str, database: str, table_names: Optional[dict]):
    findings = []
    for (dataset_key, column), allowed in ENUM_RULES.items():
        full_table = table_name(dataset_key, table_names)
        try:
            out = run_sqlcmd(server, database, f"SET NOCOUNT ON; SELECT DISTINCT {column} FROM {full_table};")
        except RuntimeError as ex:
            findings.append({"table": dataset_key, "column": column, "status": "QUERY_ERROR", "detail": str(ex)})
            continue
        observed = {line.strip() for line in out.splitlines() if line.strip() and "Statement ID" not in line}
        invalid = sorted(v for v in observed if v and v not in allowed)
        findings.append({
            "table": dataset_key, "column": column, "allowed": sorted(allowed),
            "invalid_values_found": invalid, "status": "PASS" if not invalid else "FAIL",
        })
    return findings


def audit_referential_integrity(server: str, database: str, table_names: Optional[dict]):
    findings = []
    for dataset_key, fk_col, ref_key, ref_col, nullable in REFERENTIAL_RULES:
        full_table = table_name(dataset_key, table_names)
        ref_table = table_name(ref_key, table_names)
        null_clause = f"{fk_col} IS NOT NULL AND " if nullable else ""
        query = (
            f"SET NOCOUNT ON; SELECT COUNT(*) FROM {full_table} t "
            f"WHERE {null_clause}NOT EXISTS ("
            f"SELECT 1 FROM {ref_table} r WHERE r.{ref_col} = t.{fk_col});"
        )
        try:
            out = run_sqlcmd(server, database, query)
        except RuntimeError as ex:
            findings.append({
                "table": dataset_key, "column": fk_col, "references": f"{ref_key}.{ref_col}",
                "status": "QUERY_ERROR", "detail": str(ex),
            })
            continue
        orphans = None
        for line in out.splitlines():
            token = line.strip()
            if token.isdigit():
                orphans = int(token)
                break
        findings.append({
            "table": dataset_key, "column": fk_col, "references": f"{ref_key}.{ref_col}",
            "orphaned_rows": orphans, "status": "PASS" if orphans == 0 else "FAIL",
        })
    return findings


def run_all(label: str, server: str, database: str, table_names: Optional[dict]):
    print(f"\n=== {label} ===")

    print("\n-- Row counts vs seed-declared expectations --")
    count_findings = audit_row_counts(server, database, table_names)
    for f in count_findings:
        print(f"  [{f['status']}] {f['table']}: {f}")

    print("\n-- Value-level parity vs seed .sql --")
    value_findings, backfill_statements = audit_value_parity(server, database, table_names)
    for f in value_findings:
        print(f"  [{f['status']}] {f['table']}: "
              f"{f.get('live_row_count', '?')} rows, "
              f"{len(f.get('missing_keys', []))} missing, {len(f.get('drift_cells', []))} value mismatches")
        for cell in f.get("drift_cells", [])[:5]:
            print(f"      {f['table']}.{cell['column']} [{cell['key']}]: expected={cell['expected']!r} live={cell['live']!r}")

    print("\n-- Enum/allowed-value compliance --")
    enum_findings = audit_enum_compliance(server, database, table_names)
    for f in enum_findings:
        print(f"  [{f['status']}] {f['table']}.{f['column']}: invalid={f.get('invalid_values_found')}")

    print("\n-- Referential integrity --")
    ref_findings = audit_referential_integrity(server, database, table_names)
    for f in ref_findings:
        print(f"  [{f['status']}] {f['table']}.{f['column']} -> {f['references']}: orphaned_rows={f.get('orphaned_rows')}")

    all_findings = count_findings + value_findings + enum_findings + ref_findings
    failures = [f for f in all_findings if f["status"] in ("FAIL", "DRIFT", "QUERY_ERROR")]
    return all_findings, backfill_statements, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["lakehouse", "sub2", "both"], default="both")
    parser.add_argument("--backfill", action="store_true", help="Write generated UPDATE statements to a .sql file")
    parser.add_argument(
        "--out",
        default="sql/02_metadata_foundation/14_backfill_seed_drift_generated.sql",
        help="Output path for the generated backfill script",
    )
    args = parser.parse_args()

    targets = []
    if args.target in ("lakehouse", "both"):
        targets.append(("lh_metadata (Lakehouse)", LAKEHOUSE_SERVER, LAKEHOUSE_DATABASE, None))
    if args.target in ("sub2", "both"):
        targets.append(("sqldemo (sub2 SQL source)", SUB2_SERVER, SUB2_DATABASE, TABLE_NAME_MAP))

    total_failures = 0
    all_backfill = []
    for label, server, database, table_names in targets:
        _, backfill_statements, failures = run_all(label, server, database, table_names)
        total_failures += len(failures)
        all_backfill.extend(backfill_statements)

    print(f"\n=== SUMMARY: {total_failures} total failing check(s) across {len(targets)} target(s) ===")

    if args.backfill:
        out_path = REPO_ROOT / args.out
        header = (
            "/*\n"
            "GENERATED by tools/audit_seed_vs_source.py -- do not hand-edit.\n"
            "Backfills columns where the committed .sql seed declares a non-null\n"
            "value but the live source has NULL (detected drift). Re-run the\n"
            "audit script after applying to confirm 0 remaining drift.\n"
            "*/\n\nSET NOCOUNT ON;\nGO\n\n"
        )
        body = "\n".join(all_backfill) if all_backfill else "-- No drift found; nothing to backfill.\n"
        out_path.write_text(header + body + "\nGO\n", encoding="utf-8")
        print(f"Wrote {len(all_backfill)} backfill statement(s) to {out_path}")

    return 1 if total_failures else 0


if __name__ == "__main__":
    sys.exit(main())

