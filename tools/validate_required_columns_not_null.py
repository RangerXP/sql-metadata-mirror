"""
Validate that no NULLs exist in columns nb_02 (02_build_metadata_foundation)
declares as REQUIRED (via validate_csv's required_cols lists), checking the
actual lh_metadata Lakehouse tables that nb_08 and downstream consumers read
-- not just the sub2 SQL source. validate_csv() only asserts column PRESENCE,
not that every row's VALUE is non-null, so this is a genuinely different check
than what nb_02 itself already enforces.

A small number of columns are intentionally excluded because they are
nullable BY DESIGN (parent/hierarchy references with no parent in this demo,
or genuinely optional descriptive fields) -- see NULLABLE_BY_DESIGN below.
"""
import argparse
import subprocess
import sys
from typing import Optional

FABRIC_SERVER = "sf3ojnzgs5tu7iyc4vtycxzvei-ylfhnokuo5qubcgcmhakyalkte.datawarehouse.fabric.microsoft.com"
FABRIC_DATABASE = "lh_metadata"
SUB2_SERVER = "sqlserver-sk2wus3.database.windows.net"
SUB2_DATABASE = "sqldemo"

# sub2 table names (dataset key -> actual dbo.<table> name); not a uniform prefix
# since "governance_change_requests" is already the literal sub2 table name.
SUB2_TABLE_NAMES = {
    "domains": "governance_domains",
    "data_products": "governance_data_products",
    "glossary_terms": "governance_glossary_terms",
    "cdes": "governance_cdes",
    "role_assignments": "governance_role_assignments",
    "label_assignments": "governance_label_assignments",
    "governance_change_requests": "governance_change_requests",
    "okrs": "governance_okrs",
    "okr_key_results": "governance_okr_key_results",
    "okr_data_products": "governance_okr_data_products",
}

# table -> required (non-key) columns per nb_02's validate_csv() calls
REQUIRED_COLUMNS = {
    "domains": [
        "domain_id", "domain_name", "domain_type", "description", "status",
        "governance_domain_owners", "governance_domain_creators",
    ],
    "data_products": [
        "data_product_id", "data_product_name", "product_type", "business_use_case",
        "audience", "owners", "attached_assets", "access_policy", "status", "parent_domain_id",
    ],
    "glossary_terms": [
        "term_code", "term_name", "domain_code", "owner_upn", "additional_owners_upn",
        "definition", "status", "is_cde", "industry_origin", "resources", "bound_assets",
    ],
    "cdes": [
        "cde_id", "cde_name", "expected_data_type", "business_definition", "owner_role",
        "status", "parent_glossary_term", "bound_columns",
    ],
    "role_assignments": [
        "role_id", "principal_email", "principal_display_name", "role_type",
        "scope_target", "scope_target_type", "governance_layer",
    ],
    "label_assignments": [
        "label_id", "label_name", "sensitivity_tier", "protection_policy",
        "applies_to_asset_ids", "scope",
    ],
    "governance_change_requests": [
        "request_id", "request_type", "target_object_label", "change_summary",
        "proposed_payload", "requested_by_upn", "status",
    ],
    "okrs": ["okr_id", "okr_name", "domain_id", "definition", "owner_upn", "status"],
    "okr_key_results": [
        "key_result_id", "okr_id", "result_name", "metric_source",
        "goal_amount", "max_amount", "progress_status",
    ],
    "okr_data_products": ["okr_id", "data_product_id"],
}

# Nullable by design: no parent/hierarchy in this demo dataset, or genuinely
# optional descriptive fields -- excluded from REQUIRED_COLUMNS above already,
# listed here only for documentation of what was deliberately left out.
NULLABLE_BY_DESIGN_NOTE = {
    "domains.parent_domain": "no domain hierarchy in this demo",
    "glossary_terms.parent_term_code": "not every term has a parent term",
    "glossary_terms.acronyms": "not every term has an acronym",
}

# Steward columns are not in validate_csv's required list but are central to
# this session's investigation -- check them too.
STEWARD_COLUMNS = {
    "domains": "governance_domain_stewards",
    "data_products": "stewards",
    "cdes": "steward_upn",
}


def run_sqlcmd(server: str, database: str, query: str) -> str:
    result = subprocess.run(
        ["sqlcmd", "-S", server, "-d", database, "-G", "-C", "-Q", query, "-h", "-1"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sqlcmd failed: {result.stderr or result.stdout}")
    return result.stdout


def check(server: str, database: str, table_names: Optional[dict] = None):
    violations = []
    checks = 0

    for table, cols in REQUIRED_COLUMNS.items():
        all_cols = list(cols)
        if table in STEWARD_COLUMNS:
            all_cols.append(STEWARD_COLUMNS[table])
        full_table = f"dbo.{table_names[table]}" if table_names else table
        selects = "\nUNION ALL\n".join(
            f"SELECT '{table}' AS tbl, '{c}' AS col, "
            f"SUM(CASE WHEN {c} IS NULL OR LTRIM(RTRIM(CAST({c} AS NVARCHAR(MAX)))) = '' THEN 1 ELSE 0 END) AS null_count, "
            f"COUNT(*) AS total_rows FROM {full_table}"
            for c in all_cols
        )
        out = run_sqlcmd(server, database, f"SET NOCOUNT ON;\n{selects};")
        for line in out.splitlines():
            parts = [p.strip() for p in line.split() if p.strip()]
            if len(parts) != 4 or not parts[2].isdigit():
                continue
            tbl, col, null_count, total = parts[0], parts[1], int(parts[2]), int(parts[3])
            checks += 1
            if null_count > 0:
                violations.append((tbl, col, null_count, total))

    return checks, violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["lakehouse", "sub2", "both"], default="both")
    args = parser.parse_args()

    targets = []
    if args.target in ("lakehouse", "both"):
        targets.append(("lh_metadata (Lakehouse)", FABRIC_SERVER, FABRIC_DATABASE, None))
    if args.target in ("sub2", "both"):
        targets.append(("sqldemo (sub2 SQL source)", SUB2_SERVER, SUB2_DATABASE, SUB2_TABLE_NAMES))

    exit_code = 0
    for label, server, database, table_names in targets:
        print(f"--- {label} ---")
        checks, violations = check(server, database, table_names)
        print(f"Checked {checks} required-column x table combinations across {len(REQUIRED_COLUMNS)} tables.")
        if violations:
            exit_code = 1
            print(f"{len(violations)} VIOLATION(S) FOUND (NULL/blank in a required column):")
            for tbl, col, null_count, total in violations:
                print(f"  {tbl}.{col}: {null_count}/{total} rows NULL or blank")
        else:
            print("0 violations. No NULLs found in any required column (including steward columns).")
        print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
