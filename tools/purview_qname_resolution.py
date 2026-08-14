import re

SQL_SERVER_FQDN = "sqlserver-sk2wus3.database.windows.net"
WORKSPACE_ID = "b976cac2-7754-4061-88c2-61c0ac016a99"
LAKEHOUSE_ID_LH_ENERCARE_DEMO = "e9b09e4e-b7b9-4208-b9ec-bb3433154555"


def _safe_text(value):
    return (value or "").strip() if isinstance(value, str) else ("" if value is None else str(value).strip())


def build_sql_table_qualified_name(table_name, db_name="sqldemo", schema_name="dbo", host=SQL_SERVER_FQDN):
    clean_table = _safe_text(table_name)
    if not clean_table:
        return ""
    return f"mssql://{host}/{db_name}/{schema_name}/{clean_table}"


def canonicalize_source_qname(value):
    qn = _safe_text(value)
    if not qn:
        return ""
    if not qn.lower().startswith("mssql://"):
        return qn

    match = re.match(r"^mssql://(?:(?P<host>[^/]+)/)?(?P<database>[^/]+)/(?P<schema>[^/]+)/(?P<table>[^#?]+)", qn, flags=re.IGNORECASE)
    if not match:
        return qn

    host = match.group("host") or SQL_SERVER_FQDN
    database = match.group("database")
    schema = match.group("schema")
    table = match.group("table")
    return f"mssql://{host}/{database}/{schema}/{table}"


def build_fabric_table_qualified_name(lakehouse_name_or_table, table_name=None, workspace_id=WORKSPACE_ID, lakehouse_id=None):
    if table_name is None:
        lakehouse_name = "lh_enercare_demo"
        clean_table = _safe_text(lakehouse_name_or_table)
    else:
        lakehouse_name = _safe_text(lakehouse_name_or_table)
        clean_table = _safe_text(table_name)

    if not clean_table:
        return ""

    resolved_lakehouse = lakehouse_name or "lh_enercare_demo"
    resolved_lakehouse_id = lakehouse_id or (
        LAKEHOUSE_ID_LH_ENERCARE_DEMO if resolved_lakehouse.lower() == "lh_enercare_demo" else ""
    )

    if not resolved_lakehouse_id:
        return f"fabric://{workspace_id}/{resolved_lakehouse}/tables/{clean_table}"
    return f"https://app.fabric.microsoft.com/groups/{workspace_id}/lakehouses/{resolved_lakehouse_id}/tables/{clean_table}"


def canonicalize_target_qname(value, workspace_id=WORKSPACE_ID, lakehouse_id=LAKEHOUSE_ID_LH_ENERCARE_DEMO):
    qn = _safe_text(value)
    if not qn:
        return ""

    lowered = qn.lower()
    if lowered.startswith("fabric://"):
        suffix = qn[len("fabric://") :]
        if "/lakehouses/" in suffix:
            tail = suffix.split("/lakehouses/", 1)[1]
            if "/tables/" in tail:
                tail_parts = tail.split("/tables/", 1)
                lakehouse_part = tail_parts[0]
                table_name = tail_parts[1]
                if lakehouse_part.lower() == "lh_enercare_demo":
                    return f"https://app.fabric.microsoft.com/groups/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table_name}"
                return f"https://app.fabric.microsoft.com/groups/{workspace_id}/lakehouses/{lakehouse_part}/tables/{table_name}"
        if "/tables/" in suffix:
            lakehouse_part, table_name = suffix.split("/tables/", 1)
            return f"https://app.fabric.microsoft.com/groups/{workspace_id}/lakehouses/{lakehouse_part}/tables/{table_name}"
        return qn

    if lowered.startswith("https://app.fabric.microsoft.com/") and "/lakehouses/" in lowered and "/tables/" in lowered:
        return qn

    return qn
