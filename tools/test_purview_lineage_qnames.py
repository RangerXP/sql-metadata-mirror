from tools.purview_qname_resolution import (
    build_fabric_table_qualified_name,
    build_sql_table_qualified_name,
    canonicalize_source_qname,
    canonicalize_target_qname,
)


def test_sql_qname_uses_live_hosted_pattern():
    assert build_sql_table_qualified_name("service_requests") == (
        "mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/service_requests"
    )
    assert canonicalize_source_qname("mssql://sqldemo/dbo/service_requests") == (
        "mssql://sqlserver-sk2wus3.database.windows.net/sqldemo/dbo/service_requests"
    )


def test_fabric_qname_uses_live_https_pattern():
    assert build_fabric_table_qualified_name("lh_enercare_demo", "fct_service_request") == (
        "https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/"
        "lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/fct_service_request"
    )
    assert canonicalize_target_qname("fabric://b976cac2-7754-4061-88c2-61c0ac016a99/lakehouses/lh_enercare_demo/tables/fct_service_request") == (
        "https://app.fabric.microsoft.com/groups/b976cac2-7754-4061-88c2-61c0ac016a99/"
        "lakehouses/e9b09e4e-b7b9-4208-b9ec-bb3433154555/tables/fct_service_request"
    )
