/*
================================================================================
Purpose:
  G18-A — Extract @tag: comment-annotation markers from live SQL view/procedure
  definitions natively in T-SQL (via sys.sql_modules), replacing nb_02's
  standalone Python/regex prototype. Wired directly into the existing unified
  closed-loop ledger (dbo.governance_requests / dbo.governance_events) — no
  new parallel staging table, per docs/closed-loop-governance-reference-model.md's
  append-only contract for governance_events and "one current-state row per
  proposed change" contract for governance_requests.

Scope / safety:
  - Additive only. Does not read or write kpi_metadata, ai_metadata,
    governance_cdes, governance_glossary_terms, or any existing governed table.
  - New request_type = 'SourceTagAnnotationDetected', new event_type =
    'SOURCE_TAG_DETECTED'. Both are new values within the EXISTING open-ended
    VARCHAR columns (dbo.governance_requests.request_type has no CHECK
    constraint restricting values; dbo.governance_events.event_type is
    likewise unconstrained) -- no schema change needed to add them.
  - Status on write is 'Submitted' ONLY (per docs/closed-loop-governance-reference-model.md's
    minimal state model, Draft -> Submitted -> PendingApproval -> ...). This
    proc NEVER sets Approved/Completed -- that remains a separate, human, gate
    (Loop B), exactly like every other governance workstream in this repo.
  - Idempotent: HASHBYTES('SHA2_256', ...) over the extracted tag content
    means an unchanged object produces zero new rows on a rerun. A still-open
    (non-terminal) request for the same object has its proposed_payload
    updated in place (matching the "one current-state row" contract) rather
    than creating a duplicate; a terminal (Approved/Rejected/Completed/
    Superseded) request for the same object gets a genuinely NEW request on
    its next content change, preserving the terminal request's history.

Prerequisite: sql/13_closed_loop_governance_ledger.sql must already be applied.
================================================================================
*/

SET NOCOUNT ON;
GO

CREATE OR ALTER PROCEDURE dbo.usp_extract_tag_annotations
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(7) = SYSUTCDATETIME();
    DECLARE @actor VARCHAR(255) = CONVERT(VARCHAR(255), ORIGINAL_LOGIN());

    -- 1) Find every view/procedure definition that contains at least one @tag: marker.
    --    Excludes this extraction infrastructure's own objects -- their header comments
    --    mention "@tag:" in descriptive prose (not real annotation syntax), which would
    --    otherwise self-match and create a false-positive governance request every run.
    IF OBJECT_ID('tempdb..#tag_modules') IS NOT NULL DROP TABLE #tag_modules;
    SELECT
        o.object_id,
        SCHEMA_NAME(o.schema_id) AS schema_name,
        o.name                  AS object_name,
        o.type_desc              AS object_type_desc,
        m.definition
    INTO #tag_modules
    FROM sys.sql_modules m
    JOIN sys.objects o ON o.object_id = m.object_id
    WHERE o.type IN ('V', 'P')            -- views and stored procedures
      AND m.definition LIKE '%@tag:%'
      AND o.name NOT IN ('usp_extract_tag_annotations');

    -- 2) Split each definition into lines, keep only lines carrying an @tag: marker,
    --    extract the text following the marker (no CLR -- PATINDEX/SUBSTRING only).
    IF OBJECT_ID('tempdb..#tag_lines') IS NOT NULL DROP TABLE #tag_lines;
    SELECT
        tm.object_id, tm.schema_name, tm.object_name, tm.object_type_desc,
        LTRIM(RTRIM(SUBSTRING(
            LTRIM(RTRIM(s.value)),
            PATINDEX('%@tag:%', LTRIM(RTRIM(s.value))) + 5,
            4000
        ))) AS tag_body
    INTO #tag_lines
    FROM #tag_modules tm
    CROSS APPLY STRING_SPLIT(REPLACE(tm.definition, CHAR(13), ''), CHAR(10)) s
    WHERE s.value LIKE '%@tag:%';

    -- 3) Aggregate all @tag: lines per object into one semicolon-joined tag string,
    --    and build the proposed payload (JSON) + its content hash.
    IF OBJECT_ID('tempdb..#tag_payloads') IS NOT NULL DROP TABLE #tag_payloads;
    SELECT
        tl.object_id, tl.schema_name, tl.object_name, tl.object_type_desc,
        STRING_AGG(tl.tag_body, '; ') WITHIN GROUP (ORDER BY tl.tag_body) AS tags_raw
    INTO #tag_payloads
    FROM #tag_lines tl
    GROUP BY tl.object_id, tl.schema_name, tl.object_name, tl.object_type_desc;

    IF OBJECT_ID('tempdb..#tag_final') IS NOT NULL DROP TABLE #tag_final;
    SELECT
        tp.schema_name + '.' + tp.object_name AS target_object_id,
        tp.schema_name, tp.object_name, tp.object_type_desc, tp.tags_raw,
        (SELECT tp.schema_name AS schemaName, tp.object_name AS objectName,
                tp.object_type_desc AS objectType, tp.tags_raw AS tagsRaw,
                @actor AS detectedByLogin, @now AS detectedAt
         FOR JSON PATH, WITHOUT_ARRAY_WRAPPER) AS proposed_payload
    INTO #tag_final
    FROM #tag_payloads tp;

    ALTER TABLE #tag_final ADD definition_hash CHAR(64) NULL;
    -- Content hash is computed over STABLE fields only (schema/object/type/tags) -- deliberately
    -- excludes detectedAt/detectedByLogin from the full payload, otherwise every run would look
    -- "changed" purely because the timestamp differs, breaking idempotency.
    UPDATE #tag_final
    SET definition_hash = CONVERT(CHAR(64), HASHBYTES('SHA2_256',
        schema_name + '|' + object_name + '|' + object_type_desc + '|' + tags_raw), 2);

    -- 4) For each detected object: compare against the latest existing request (if any).
    --    Skip entirely if content is unchanged (idempotent). Update in place if an open
    --    (non-terminal) request exists. Otherwise insert a new request + event.
    DECLARE @object_id VARCHAR(256), @schema_name VARCHAR(128), @object_name VARCHAR(128),
            @object_type_desc VARCHAR(60), @tags_raw NVARCHAR(MAX), @proposed_payload NVARCHAR(MAX),
            @definition_hash CHAR(64);
    DECLARE @existing_request_id VARCHAR(64), @existing_status VARCHAR(32), @existing_hash CHAR(64);
    DECLARE @new_request_id VARCHAR(64), @source_event_id VARCHAR(256);
    DECLARE @detected_count INT = 0, @skipped_count INT = 0, @updated_count INT = 0, @new_count INT = 0;

    DECLARE tag_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT target_object_id, schema_name, object_name, object_type_desc, tags_raw, proposed_payload, definition_hash
        FROM #tag_final;

    OPEN tag_cursor;
    FETCH NEXT FROM tag_cursor INTO @object_id, @schema_name, @object_name, @object_type_desc, @tags_raw, @proposed_payload, @definition_hash;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @detected_count += 1;

        SELECT TOP (1)
            @existing_request_id = request_id,
            @existing_status = current_status,
            @existing_hash = CONVERT(CHAR(64), HASHBYTES('SHA2_256',
                JSON_VALUE(proposed_payload, '$.schemaName') + '|' +
                JSON_VALUE(proposed_payload, '$.objectName') + '|' +
                JSON_VALUE(proposed_payload, '$.objectType') + '|' +
                JSON_VALUE(proposed_payload, '$.tagsRaw')), 2)
        FROM dbo.governance_requests
        WHERE request_type = 'SourceTagAnnotationDetected'
          AND target_system = 'SQL' AND target_object_type = 'SqlModuleTagAnnotation'
          AND target_object_id = @object_id
        ORDER BY requested_at DESC;

        IF @existing_request_id IS NOT NULL AND @existing_hash = @definition_hash
        BEGIN
            -- No change since last detection -- idempotent no-op.
            SET @skipped_count += 1;
        END
        ELSE IF @existing_request_id IS NOT NULL AND @existing_status IN ('Draft', 'Submitted', 'PendingApproval')
        BEGIN
            -- Still-open request for this object: update in place (one current-state row).
            UPDATE dbo.governance_requests
            SET proposed_payload = @proposed_payload, last_observed_at = @now
            WHERE request_id = @existing_request_id;

            SET @source_event_id = @existing_request_id + ':SOURCE_TAG_DETECTED:' + @definition_hash;
            IF NOT EXISTS (SELECT 1 FROM dbo.governance_events WHERE source_system = 'SQL' AND source_event_id = @source_event_id)
                INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
                VALUES (@existing_request_id, 'SOURCE_TAG_DETECTED', 'Submitted', 'SQL', @source_event_id, @actor, @now, @now, @proposed_payload, @definition_hash);

            SET @updated_count += 1;
        END
        ELSE
        BEGIN
            -- No open request exists (either never seen, or the prior one reached a terminal
            -- state) -- start a fresh request.
            SET @new_request_id = 'TAG-' + CONVERT(VARCHAR(16), HASHBYTES('SHA2_256', @object_id + CONVERT(VARCHAR(33), @now, 127)), 2);

            INSERT INTO dbo.governance_requests (
                request_id, request_type, authority, target_system, target_object_type,
                target_object_id, target_object_label, requested_by, requested_at,
                current_status, proposed_payload
            )
            VALUES (
                @new_request_id, 'SourceTagAnnotationDetected', 'SQL', 'SQL', 'SqlModuleTagAnnotation',
                @object_id, @schema_name + '.' + @object_name + ' (' + @object_type_desc + ') @tag annotations',
                @actor, @now, 'Submitted', @proposed_payload
            );

            SET @source_event_id = @new_request_id + ':SOURCE_TAG_DETECTED:' + @definition_hash;
            INSERT INTO dbo.governance_events (request_id, event_type, event_status, source_system, source_event_id, actor_id, occurred_at, observed_at, payload, payload_hash)
            VALUES (@new_request_id, 'SOURCE_TAG_DETECTED', 'Submitted', 'SQL', @source_event_id, @actor, @now, @now, @proposed_payload, @definition_hash);

            SET @new_count += 1;
        END

        SET @existing_request_id = NULL; SET @existing_status = NULL; SET @existing_hash = NULL;
        FETCH NEXT FROM tag_cursor INTO @object_id, @schema_name, @object_name, @object_type_desc, @tags_raw, @proposed_payload, @definition_hash;
    END

    CLOSE tag_cursor;
    DEALLOCATE tag_cursor;

    PRINT 'usp_extract_tag_annotations: detected=' + CAST(@detected_count AS VARCHAR(10))
        + ' new=' + CAST(@new_count AS VARCHAR(10))
        + ' updated=' + CAST(@updated_count AS VARCHAR(10))
        + ' unchanged_skipped=' + CAST(@skipped_count AS VARCHAR(10));
END
GO

PRINT 'dbo.usp_extract_tag_annotations created/updated.';
GO

/*
--------------------------------------------------------------------------------
Database-scoped DDL trigger: fires the extraction proc automatically whenever a
view or procedure is created/altered. Wrapped in TRY/CATCH so a trigger-side
failure can NEVER block or roll back the underlying DDL change that fired it --
this is a best-effort detection trigger, not a gate on schema changes.

NOTE: matches the exact event set specified for this unit (CREATE_VIEW,
ALTER_VIEW, ALTER_PROCEDURE). CREATE_PROCEDURE is intentionally NOT included
per that spec -- a newly created (not yet altered) procedure with @tag:
markers will only be picked up on its first ALTER, or by a manual
`EXEC dbo.usp_extract_tag_annotations` sweep. Flagging this now in case that
gap should be closed later by also adding CREATE_PROCEDURE to the trigger's
event list.
--------------------------------------------------------------------------------
*/

CREATE OR ALTER TRIGGER trg_tag_annotation_extraction
ON DATABASE
FOR CREATE_VIEW, ALTER_VIEW, ALTER_PROCEDURE
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        EXEC dbo.usp_extract_tag_annotations;
    END TRY
    BEGIN CATCH
        -- Swallow all errors here on purpose -- extraction must never block a real DDL change.
        PRINT 'trg_tag_annotation_extraction: non-fatal error, extraction skipped this event: ' + ERROR_MESSAGE();
    END CATCH
END
GO

PRINT 'trg_tag_annotation_extraction created/updated.';
GO

