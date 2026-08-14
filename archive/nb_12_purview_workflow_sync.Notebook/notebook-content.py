# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "824f4a52-baa0-4c3f-88dc-203c1d85c89a",
# META       "default_lakehouse_name": "lh_metadata",
# META       "default_lakehouse_workspace_id": "b976cac2-7754-4061-88c2-61c0ac016a99",
# META       "known_lakehouses": [
# META         {
# META           "id": "824f4a52-baa0-4c3f-88dc-203c1d85c89a"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

# Fabric Notebook: nb_12_purview_workflow_sync
# Purpose: P1 proof for one Purview-native glossary term publication loop.
#
# This notebook observes the supported Unified Catalog term resource. The public
# Unified Catalog API does not currently expose workflow request/task resources,
# so request IDs, decision actors, and decision timestamps remain NULL unless a
# future supported response provides them. A Published observation is accepted as
# approval evidence only after this run correlation was previously observed Draft.

DEMO_MODE = True
WORKFLOW_CONFIGURED = False
RUN_CORRELATION_ID = ""  # Example: GT-SLA-2026-08-11-A; local correlation, not a Purview workflow ID.

PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_CATALOG_BASE_URL = (
    "https://b7e47691-9726-4f67-a302-e567815f3522-api."
    "purview-service.microsoft.com/datagovernance/catalog"
)
PURVIEW_TERM_ID = "b3b54277-3b36-47d8-831c-a2b9a5f02634"
PURVIEW_TERM_CODE = "GT-SLA"
PURVIEW_DOMAIN_ID = "9d82a6da-eed1-4dae-a036-84c1dcc65337"

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

print(
    f"nb_12 | DEMO_MODE={DEMO_MODE} | workflow_configured={WORKFLOW_CONFIGURED} | "
    f"term={PURVIEW_TERM_CODE}/{PURVIEW_TERM_ID}"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Authentication and connection helpers

import hashlib
import json
import struct
from datetime import datetime, timezone

import pyodbc
import requests

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256


def _get_fabric_token(scopes):
    last_error = None
    for scope in scopes:
        try:
            return mssparkutils.credentials.getToken(scope)
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError("Token acquisition failed.")


def get_purview_token():
    try:
        from azure.identity import DeviceCodeCredential
    except ImportError:
        import subprocess
        import sys

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "azure-identity"],
            check=True,
        )
        from azure.identity import DeviceCodeCredential

    def show_device_code(verification_uri, user_code, expires_on):
        print(
            f"[AUTH] Open {verification_uri} in an InPrivate browser and enter "
            f"code {user_code}. Sign in as the Sean account in tenant {PURVIEW_TENANT_ID}."
        )

    credential = DeviceCodeCredential(
        client_id="04b07795-8ddb-461a-bbee-02f9e1bf7b46",
        tenant_id=PURVIEW_TENANT_ID,
        prompt_callback=show_device_code,
    )
    return credential.get_token("https://purview.azure.net/.default").token


def get_sql_connection():
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    if SQL_AUTH_MODE == "managed_identity":
        return pyodbc.connect(connection_string + "Authentication=ActiveDirectoryMsi;", autocommit=False)

    token = _get_fabric_token(["https://database.windows.net/", "https://database.windows.net"])
    encoded_token = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(encoded_token)}s", len(encoded_token), encoded_token)
    return pyodbc.connect(
        connection_string,
        attrs_before={ODBC_SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=False,
    )


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def publication_content_hash(term):
    content = dict(term)
    content.pop("status", None)
    return sha256_text(canonical_json(content))


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read and normalize the supported Unified Catalog term resource

response = requests.get(
    f"{PURVIEW_CATALOG_BASE_URL}/terms/{PURVIEW_TERM_ID}",
    headers={"Authorization": f"Bearer {get_purview_token()}"},
    timeout=60,
)
response.raise_for_status()
raw_term = response.json()

term_snapshot = {
    "id": raw_term.get("id"),
    "name": raw_term.get("name"),
    "domain": raw_term.get("domain"),
    "status": raw_term.get("status"),
    "description": raw_term.get("description"),
    "acronyms": raw_term.get("acronyms") or [],
    "parentId": raw_term.get("parentId"),
    "resources": raw_term.get("resources") or [],
}

if term_snapshot["id"] != PURVIEW_TERM_ID:
    raise RuntimeError("Unified Catalog returned an unexpected term ID.")
if term_snapshot["domain"] != PURVIEW_DOMAIN_ID:
    raise RuntimeError("GT-SLA is no longer assigned to the expected Service Delivery domain.")
if term_snapshot["status"] not in ("Draft", "Published"):
    raise RuntimeError(f"Unsupported term lifecycle status: {term_snapshot['status']!r}")

snapshot_json = canonical_json(term_snapshot)
definition_hash = sha256_text(snapshot_json)
content_hash = publication_content_hash(term_snapshot)
observed_at = utc_now()

print(
    f"Observed {PURVIEW_TERM_CODE}: status={term_snapshot['status']} "
    f"hash={definition_hash[:12]} observed_at={observed_at.isoformat()}Z"
)
print(json.dumps(term_snapshot, indent=2, ensure_ascii=True))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Enforce the P1 correlation and Draft-before-Published guardrails

if DEMO_MODE:
    print("[DEMO_MODE] Baseline observation only; no SQL ledger writes will occur.")
elif not WORKFLOW_CONFIGURED:
    raise RuntimeError(
        "Set WORKFLOW_CONFIGURED=True only after a native Term publish workflow is scoped "
        "to the Service Delivery governance domain."
    )
elif not RUN_CORRELATION_ID.strip():
    raise RuntimeError("RUN_CORRELATION_ID is required for a live P1 workflow observation.")

request_id = "PV-GT-SLA-" + sha256_text(RUN_CORRELATION_ID.strip())[:20].upper()
source_event_id = f"{request_id}:{term_snapshot['status']}:{definition_hash}"
request_payload = canonical_json(
    {
        "localCorrelationId": RUN_CORRELATION_ID.strip(),
        "definitionHash": definition_hash,
        "publicationContentHash": content_hash,
        "term": term_snapshot,
        "workflowEvidenceLimitations": {
            "authorityRequestId": "not exposed by the supported Unified Catalog API",
            "decisionActor": "not exposed by the supported Unified Catalog API",
            "decisionTimestamp": "not exposed by the supported Unified Catalog API",
        },
    }
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Persist one idempotent Draft or Published observation

if not DEMO_MODE:
    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT current_status, proposed_payload
            FROM dbo.governance_requests WITH (UPDLOCK, HOLDLOCK)
            WHERE request_id = ?
            """,
            request_id,
        )
        existing_row = cursor.fetchone()
        existing_status = existing_row[0] if existing_row else None
        existing_payload = json.loads(existing_row[1]) if existing_row and existing_row[1] else None

        if term_snapshot["status"] == "Published" and existing_status not in ("Draft", "Approved"):
            raise RuntimeError(
                "Refusing to record Published as approval evidence because this correlation "
                "has no prior Draft observation. Unpublish/edit GT-SLA, run this notebook once "
                "while Draft, submit it to the native workflow, then rerun after approval."
            )

        if existing_payload:
            expected_hash = existing_payload.get("publicationContentHash")
            if not expected_hash:
                expected_hash = publication_content_hash(existing_payload["term"])
        else:
            expected_hash = content_hash
        normalized_status = "Approved" if term_snapshot["status"] == "Published" else "Draft"

        if existing_row:
            cursor.execute(
                """
                UPDATE dbo.governance_requests
                SET current_status = ?, source_snapshot = ?, last_observed_at = ?, failure_reason = NULL
                WHERE request_id = ?
                """,
                normalized_status,
                snapshot_json,
                observed_at,
                request_id,
            )
        else:
            cursor.execute(
                """
                INSERT dbo.governance_requests (
                    request_id, request_type, authority, authority_request_id,
                    target_system, target_object_type, target_object_id, target_object_label,
                    current_status, proposed_payload, source_snapshot, last_observed_at
                ) VALUES (?, 'GLOSSARY_TERM_PUBLICATION', 'Purview', NULL,
                          'Purview', 'GlossaryTerm', ?, ?, ?, ?, ?, ?)
                """,
                request_id,
                PURVIEW_TERM_ID,
                term_snapshot["name"],
                normalized_status,
                request_payload,
                snapshot_json,
                observed_at,
            )

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM dbo.governance_events
                WHERE source_system = 'Purview' AND source_event_id = ?
            )
            INSERT dbo.governance_events (
                request_id, event_type, event_status, source_system, source_event_id,
                actor_id, occurred_at, observed_at, payload, payload_hash
            ) VALUES (?, ?, ?, 'Purview', ?, NULL, ?, ?, ?, ?)
            """,
            source_event_id,
            request_id,
            "TermPublishedObserved" if normalized_status == "Approved" else "TermDraftObserved",
            normalized_status,
            source_event_id,
            observed_at,
            observed_at,
            snapshot_json,
            definition_hash,
        )

        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM dbo.governed_object_versions
                WHERE source_system = 'Purview' AND object_type = 'GlossaryTerm'
                  AND object_id = ? AND source_version_id = ?
            )
            INSERT dbo.governed_object_versions (
                request_id, source_system, object_type, object_id, source_version_id,
                lifecycle_status, definition_hash, object_payload, effective_at, observed_at
            ) VALUES (?, 'Purview', 'GlossaryTerm', ?, ?, ?, ?, ?, ?, ?)
            """,
            PURVIEW_TERM_ID,
            definition_hash,
            request_id,
            PURVIEW_TERM_ID,
            definition_hash,
            term_snapshot["status"],
            definition_hash,
            snapshot_json,
            observed_at,
            observed_at,
        )

        if normalized_status == "Approved":
            validation_status = "Passed" if content_hash == expected_hash else "Failed"
            evidence = canonical_json(
                {
                    "term": term_snapshot,
                    "expectedHash": expected_hash,
                    "observedHash": content_hash,
                    "observedAt": observed_at.isoformat() + "Z",
                    "decisionActor": None,
                    "decisionTimestamp": None,
                }
            )
            cursor.execute(
                """
                MERGE dbo.governance_target_receipts WITH (HOLDLOCK) AS target
                USING (SELECT ? AS request_id, 'Purview' AS target_system,
                              'GlossaryTerm' AS target_object_type, ? AS target_object_id,
                              'PublicationReadback' AS receipt_type) AS source
                ON target.request_id = source.request_id
                   AND target.target_system = source.target_system
                   AND target.target_object_type = source.target_object_type
                   AND target.target_object_id = source.target_object_id
                   AND target.receipt_type = source.receipt_type
                WHEN MATCHED THEN UPDATE SET
                    expected_hash = ?, observed_hash = ?, validation_status = ?,
                    observed_at = ?, evidence_payload = ?
                WHEN NOT MATCHED THEN INSERT (
                    request_id, target_system, target_object_type, target_object_id,
                    receipt_type, expected_hash, observed_hash, validation_status,
                    observed_at, evidence_payload
                ) VALUES (?, 'Purview', 'GlossaryTerm', ?, 'PublicationReadback',
                          ?, ?, ?, ?, ?);
                """,
                request_id,
                PURVIEW_TERM_ID,
                expected_hash,
                content_hash,
                validation_status,
                observed_at,
                evidence,
                request_id,
                PURVIEW_TERM_ID,
                expected_hash,
                content_hash,
                validation_status,
                observed_at,
                evidence,
            )
            if validation_status != "Passed":
                raise RuntimeError("Published term read-back did not match the Draft definition hash.")

        connection.commit()
        print(f"[APPLIED] request={request_id} status={normalized_status} event={source_event_id}")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Verify the durable P1 evidence contract

if not DEMO_MODE:
    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT current_status, authority_request_id, decided_by, decided_at
            FROM dbo.governance_requests
            WHERE request_id = ?
            """,
            request_id,
        )
        request_evidence = cursor.fetchone()

        cursor.execute(
            """
            SELECT event_type, COUNT(*)
            FROM dbo.governance_events
            WHERE request_id = ?
            GROUP BY event_type
            """,
            request_id,
        )
        event_counts = dict(cursor.fetchall())

        cursor.execute(
            """
            SELECT lifecycle_status, COUNT(*)
            FROM dbo.governed_object_versions
            WHERE request_id = ?
            GROUP BY lifecycle_status
            """,
            request_id,
        )
        version_counts = dict(cursor.fetchall())

        cursor.execute(
            """
            SELECT validation_status, expected_hash, observed_hash
            FROM dbo.governance_target_receipts
            WHERE request_id = ? AND target_system = 'Purview'
              AND target_object_type = 'GlossaryTerm' AND target_object_id = ?
              AND receipt_type = 'PublicationReadback'
            """,
            request_id,
            PURVIEW_TERM_ID,
        )
        publication_receipt = cursor.fetchone()

        if not request_evidence or request_evidence[0] != "Approved":
            raise RuntimeError("P1 verification failed: request is not Approved.")
        if any(request_evidence[index] is not None for index in range(1, 4)):
            raise RuntimeError("P1 verification failed: unsupported workflow fields must remain NULL.")
        if event_counts.get("TermDraftObserved") != 1 or event_counts.get("TermPublishedObserved") != 1:
            raise RuntimeError(f"P1 verification failed: unexpected event counts {event_counts!r}.")
        if version_counts.get("Draft") != 1 or version_counts.get("Published") != 1:
            raise RuntimeError(f"P1 verification failed: unexpected version counts {version_counts!r}.")
        if not publication_receipt or publication_receipt[0] != "Passed":
            raise RuntimeError("P1 verification failed: PublicationReadback did not pass.")
        if publication_receipt[1] != publication_receipt[2]:
            raise RuntimeError("P1 verification failed: publication receipt hashes differ.")

        print(
            f"[VERIFIED] request={request_id} status=Approved "
            f"events={event_counts} versions={version_counts} receipt=Passed"
        )
    finally:
        cursor.close()
        connection.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Completion boundary

print(
    "P1 Purview evidence collection finished. This notebook does not mark the request "
    "Completed; semantic-model reconciliation and its read-back receipt are a separate step."
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
