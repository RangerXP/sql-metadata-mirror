-- Run this directly in SSMS/Azure Data Studio against the sqldemo database
-- (connect via Entra auth, as you already have). Purpose: check whether the
-- Fabric mirroring engine (SPN fabric-sqldemo-mirroring-spn) is actually
-- connecting to / reading from the source database at all.

-- 1. Currently active connections/sessions (mirroring connections are often
--    short-lived, so this may show nothing if you catch it between polls --
--    run it a few times over a minute or two).
SELECT
    s.session_id,
    s.login_name,
    s.host_name,
    s.program_name,
    s.status,
    s.login_time,
    s.last_request_start_time,
    s.last_request_end_time,
    c.client_net_address,
    c.connect_time
FROM sys.dm_exec_sessions s
LEFT JOIN sys.dm_exec_connections c ON c.session_id = s.session_id
WHERE s.is_user_process = 1
ORDER BY s.login_time DESC;

-- 2. Same, filtered to just the mirroring SPN login (in case the list above
--    is noisy with your own SSMS session).
SELECT
    s.session_id,
    s.login_name,
    s.host_name,
    s.program_name,
    s.status,
    s.login_time,
    s.last_request_start_time
FROM sys.dm_exec_sessions s
WHERE s.login_name LIKE '%fabric-sqldemo-mirroring-spn%'
   OR s.program_name LIKE '%Mirroring%'
   OR s.program_name LIKE '%Fabric%';

-- 3. Change Feed status flag + any Change Feed error log (columns vary by
--    engine version, so select * to see whatever is actually available).
SELECT name, is_change_feed_enabled
FROM sys.databases
WHERE name = DB_NAME();

SELECT * FROM sys.dm_change_feed_errors;
SELECT * FROM sys.dm_change_feed_log_scan_sessions;

-- 4. Confirm the SPN's SQL user/login still exists and has the expected
--    grants (in case something reverted after the delete+recreate).
SELECT dp.state_desc, dp.permission_name, dp.class_desc, pr.name AS principal_name
FROM sys.database_permissions dp
JOIN sys.database_principals pr ON pr.principal_id = dp.grantee_principal_id
WHERE pr.name = 'fabric-sqldemo-mirroring-spn';

-- 5. Server-level login existence check (run against master, not sqldemo).
-- SELECT name, type_desc, create_date, modify_date
-- FROM sys.server_principals
-- WHERE name = 'fabric-sqldemo-mirroring-spn';
