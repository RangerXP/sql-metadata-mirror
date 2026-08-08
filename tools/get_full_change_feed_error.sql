SELECT TOP 5
    entry_time,
    error_number,
    error_severity,
    error_state,
    error_message,   -- widen this column in SSMS results grid, or use the CAST below
    CAST(error_message AS NVARCHAR(MAX)) AS error_message_full
FROM sys.dm_change_feed_errors
ORDER BY entry_time DESC;
