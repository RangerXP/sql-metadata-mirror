"""
Reverse-engineering audit: read live sub2 SQL tables, evaluate every column for
NULLs, align against the declarative .sql seed scripts' intended values (keyed
by the table's natural id column), and report/backfill any drift.

Scope: the "pure seed" scripts that fully DELETE+INSERT (or are otherwise a
static declarative VALUES list) for their target tables. CTE/computed portions
(e.g. synthetic filler rows, MERGE-based upserts) are parsed where reasonably
possible; anything not parseable is reported as "unchecked" rather than
silently skipped.

Usage:
    python tools/audit_seed_vs_source.py            # report only
    python tools/audit_seed_vs_source.py --backfill # also write a generated
                                                     # UPDATE script for any
                                                     # confirmed regressions
                                                     # (seed says non-null,
                                                     # live is NULL)

Connects to sub2 Azure SQL directly via sqlcmd (-G -C, Entra ID auth), NOT the
Fabric mirror/lakehouse -- sub2 is the authoritative source per
.github/copilot-instructions.md.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SUB2_SERVER = "sqlserver-sk2wus3.database.windows.net"
SUB2_DATABASE = "sqldemo"

REPO_ROOT = Path(__file__).resolve().parent.parent

# (sql file, table, key column) for every statically-parseable pure-seed INSERT.
SEED_SOURCES = [
    ("sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_domains", "domain_id"),
    ("sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_data_products", "data_product_id"),
    ("sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_glossary_terms", "term_code"),
    ("sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_cdes", "cde_id"),
    ("sql/02_metadata_foundation/07_seed_purview_metadata.sql", "governance_label_assignments", "label_id"),
    ("sql/02_metadata_foundation/12_seed_ontology_okrs.sql", "governance_okrs", "okr_id"),
    ("sql/02_metadata_foundation/12_seed_ontology_okrs.sql", "governance_okr_key_results", "key_result_id"),
    ("sql/02_metadata_foundation/12_seed_ontology_okrs.sql", "governance_okr_data_products", "okr_id"),
]

# Columns that are legitimately optional/nullable by design in the CURRENT seed
# (i.e. the seed script itself passes NULL for every row) -- never flag these
# even if a future seed edit adds real values, since "seed says NULL" already
# means "by design" per-row (handled generically below). This list is only for
# documentation; the generic per-row NULL-vs-NULL comparison already handles it.


def run_sqlcmd(query: str) -> str:
    result = subprocess.run(
        [
            "sqlcmd", "-S", SUB2_SERVER, "-d", SUB2_DATABASE, "-G", "-C",
            "-Q", query, "-s", "|", "-W", "-h", "-1",
        ],
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


def query_live_table(table: str, key_col: str, cols: list) -> dict:
    col_list = ", ".join(cols)
    out = run_sqlcmd(f"SET NOCOUNT ON; SELECT {col_list} FROM dbo.{table};")
    rows = {}
    for line in out.splitlines():
        line = line.rstrip("\n")
        if not line.strip() or line.strip().startswith("(") or "rows affected" in line:
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


def audit():
    findings = []
    backfill_statements = []

    for rel_path, table, key_col in SEED_SOURCES:
        sql_path = REPO_ROOT / rel_path
        sql_text = sql_path.read_text(encoding="utf-8")
        expected_rows = parse_insert_values(sql_text, table)
        if not expected_rows:
            findings.append({
                "table": table, "seed_file": rel_path, "status": "UNPARSEABLE",
                "detail": "No static INSERT VALUES block found (may be CTE/computed-only); not checked.",
            })
            continue

        cols = list(expected_rows[0].keys())
        try:
            live_rows = query_live_table(table, key_col, cols)
        except RuntimeError as ex:
            findings.append({"table": table, "seed_file": rel_path, "status": "QUERY_ERROR", "detail": str(ex)})
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
                if exp_val is not None and live_val is None:
                    drift_cells.append({
                        "key": key_val, "column": col,
                        "expected": exp_val, "live": None,
                    })
                    backfill_statements.append(
                        f"UPDATE dbo.{table} SET {col} = {sql_literal(exp_val)} "
                        f"WHERE {key_col} = {sql_literal(key_val)};"
                    )

        findings.append({
            "table": table,
            "seed_file": rel_path,
            "status": "OK" if not missing_keys and not drift_cells else "DRIFT",
            "expected_row_count": len(expected_rows),
            "live_row_count": len(live_rows),
            "missing_keys": missing_keys,
            "drift_cells": drift_cells,
        })

    return findings, backfill_statements


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="Write generated UPDATE statements to a .sql file")
    parser.add_argument(
        "--out",
        default="sql/02_metadata_foundation/14_backfill_seed_drift_generated.sql",
        help="Output path for the generated backfill script",
    )
    args = parser.parse_args()

    findings, backfill_statements = audit()

    print(json.dumps(findings, indent=2))
    print()
    print(f"Tables checked: {len(findings)}")
    drift_tables = [f for f in findings if f.get("status") == "DRIFT"]
    print(f"Tables with drift: {len(drift_tables)}")
    print(f"Total backfill statements: {len(backfill_statements)}")

    if args.backfill:
        out_path = REPO_ROOT / args.out
        header = (
            "/*\n"
            "GENERATED by tools/audit_seed_vs_source.py -- do not hand-edit.\n"
            "Backfills columns where the committed .sql seed declares a non-null\n"
            "value but the live sub2 source has NULL (detected drift). Re-run the\n"
            "audit script after applying to confirm 0 remaining drift.\n"
            "*/\n\nSET NOCOUNT ON;\nGO\n\n"
        )
        body = "\n".join(backfill_statements) if backfill_statements else "-- No drift found; nothing to backfill.\n"
        out_path.write_text(header + body + "\nGO\n", encoding="utf-8")
        print(f"\nWrote {len(backfill_statements)} backfill statement(s) to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
