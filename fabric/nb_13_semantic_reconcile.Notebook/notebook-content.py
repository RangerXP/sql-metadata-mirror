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
# META     },
# META     "environment": {
# META       "environmentId": "7380ddbb-a87b-8113-489c-049cb1998b35",
# META       "workspaceId": "00000000-0000-0000-0000-000000000000"
# META     }
# META   }
# META }

# CELL ********************

# Fabric Notebook: nb_13_semantic_reconcile
# Purpose: P2 semantic reconciliation for an approved Purview glossary term.
#
# The notebook fails closed: it requires a passed PublicationReadback receipt,
# changes metadata only, verifies a fresh semantic-model read-back, and marks the
# request Completed only after both required receipts pass.

DEMO_MODE = True
RUN_REQUEST_ID = ""  # Example: PV-GT-SLA-0359C207890E4EB1B8AB

MODEL_NAME = "BrookfieldEnercare"
PURVIEW_TERM_ID = "b3b54277-3b36-47d8-831c-a2b9a5f02634"
PURVIEW_TERM_CODE = "GT-SLA"

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

SEMANTIC_TARGETS = [
    {
        "table": "_Measures",
        "objectType": "Measure",
        "objectName": "SLA Breach Count",
        "descriptionPrefix": "Count of service requests that breached the governed service-level target.",
    },
    {
        "table": "_Measures",
        "objectType": "Measure",
        "objectName": "SLA Compliance Rate",
        "descriptionPrefix": "Share of service requests that met the governed service-level target.",
    },
    {
        "table": "fct_service_request",
        "objectType": "Column",
        "objectName": "IsSlaBreachFlag",
        "descriptionPrefix": "Indicates whether the service request breached the governed service-level target.",
    },
]

print(f"nb_13 | DEMO_MODE={DEMO_MODE} | request={RUN_REQUEST_ID or '<not set>'} | model={MODEL_NAME}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Connection and normalization helpers

import hashlib
import json
import struct
from datetime import datetime, timezone

import pyodbc

try:
    from sempy_labs.tom import connect_semantic_model
except ImportError as exc:
    raise RuntimeError(
        "semantic-link-labs is required. Attach the SempyLabsV2 environment and restart the session."
    ) from exc

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256
ANNOTATION_KEYS = (
    "Glossary_Term_References",
    "Purview_Term_Id",
    "Purview_Publication_Content_Hash",
    "Governance_Request_Id",
)


def get_sql_connection():
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:{SERVER_NAME},{SQL_PORT};"
        f"Database={DATABASE_NAME};Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout={SQL_LOGIN_TIMEOUT_SECONDS};"
    )
    if SQL_AUTH_MODE == "managed_identity":
        return pyodbc.connect(connection_string + "Authentication=ActiveDirectoryMsi;", autocommit=False)

    token = mssparkutils.credentials.getToken("https://database.windows.net/")
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


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def find_by_name(collection, name):
    try:
        return collection[name]
    except Exception:
        pass

    target = name.strip().lower()
    for item in collection:
        item_name = getattr(item, "Name", None)
        if isinstance(item_name, str) and item_name.strip().lower() == target:
            return item
    return None


def description_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("plainText", "description", "value", "text"):
            candidate = description_text(value.get(key))
            if candidate:
                return candidate
    if isinstance(value, list):
        return " ".join(filter(None, (description_text(item) for item in value))).strip()
    return ""


def semantic_object(tom, target):
    table = find_by_name(tom.model.Tables, target["table"])
    if table is None:
        raise RuntimeError(f"Semantic table not found: {target['table']}")

    collection = table.Measures if target["objectType"] == "Measure" else table.Columns
    obj = find_by_name(collection, target["objectName"])
    if obj is None:
        raise RuntimeError(
            f"Semantic {target['objectType'].lower()} not found: "
            f"{target['table']}.{target['objectName']}"
        )
    return obj


def upsert_annotation(obj, key, value):
    annotations = getattr(obj, "Annotations", None)
    if annotations is None:
        raise RuntimeError(f"Annotations are unavailable on semantic object {obj.Name}.")

    existing = find_by_name(annotations, key)
    if existing is not None:
        existing.Value = value
    else:
        try:
            from Microsoft.AnalysisServices.Tabular import Annotation as TomAnnotation
        except ImportError as exc:
            raise RuntimeError("The TOM Annotation type is unavailable in this Fabric runtime.") from exc

        new_annotation = TomAnnotation()
        new_annotation.Name = key
        new_annotation.Value = value
        annotations.Add(new_annotation)


def read_annotation(obj, key):
    annotation = find_by_name(obj.Annotations, key)
    return None if annotation is None else str(annotation.Value)


if not RUN_REQUEST_ID.strip():
    raise RuntimeError("Set RUN_REQUEST_ID to the approved P1 governance request ID.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Load the approved source definition and enforce the P1 gate

connection = get_sql_connection()
cursor = connection.cursor()
try:
    cursor.execute(
        """
        SELECT current_status, proposed_payload
        FROM dbo.governance_requests
        WHERE request_id = ? AND request_type = 'GLOSSARY_TERM_PUBLICATION'
        """,
        RUN_REQUEST_ID,
    )
    request_row = cursor.fetchone()
    if not request_row:
        raise RuntimeError("Governance request was not found or has the wrong request type.")
    if request_row[0] not in ("Approved", "Completed"):
        raise RuntimeError(f"Request must be Approved before reconciliation; found {request_row[0]!r}.")

    cursor.execute(
        """
        SELECT validation_status, expected_hash, observed_hash
        FROM dbo.governance_target_receipts
        WHERE request_id = ? AND target_system = 'Purview'
          AND target_object_type = 'GlossaryTerm' AND target_object_id = ?
          AND receipt_type = 'PublicationReadback'
        """,
        RUN_REQUEST_ID,
        PURVIEW_TERM_ID,
    )
    publication_receipt = cursor.fetchone()
    if not publication_receipt or publication_receipt[0] != "Passed":
        raise RuntimeError("PublicationReadback must pass before semantic reconciliation.")
    if publication_receipt[1] != publication_receipt[2]:
        raise RuntimeError("PublicationReadback expected and observed hashes differ.")

    cursor.execute(
        """
        SELECT TOP (1) object_payload
        FROM dbo.governed_object_versions
        WHERE request_id = ? AND source_system = 'Purview'
          AND object_type = 'GlossaryTerm' AND object_id = ?
          AND lifecycle_status = 'Published'
        ORDER BY observed_at DESC, version_id DESC
        """,
        RUN_REQUEST_ID,
        PURVIEW_TERM_ID,
    )
    version_row = cursor.fetchone()
    if not version_row:
        raise RuntimeError("No Published Purview object version exists for this request.")
finally:
    cursor.close()
    connection.close()

request_payload = json.loads(request_row[1]) if request_row[1] else {}
published_term = json.loads(version_row[0])
if published_term.get("id") != PURVIEW_TERM_ID or published_term.get("status") != "Published":
    raise RuntimeError("Published source payload does not match the configured GT-SLA term.")

approved_definition = description_text(published_term.get("description"))
if not approved_definition:
    raise RuntimeError("Published GT-SLA has no usable description to reconcile.")

receipt_content_hash = publication_receipt[1]
payload_content_hash = request_payload.get("publicationContentHash")
if receipt_content_hash and payload_content_hash and receipt_content_hash != payload_content_hash:
    raise RuntimeError("P1 receipt and proposed_payload publication hashes differ.")

if receipt_content_hash:
    publication_content_hash = receipt_content_hash
elif payload_content_hash:
    publication_content_hash = payload_content_hash
else:
    publication_content = dict(published_term)
    publication_content.pop("status", None)
    publication_content_hash = sha256_text(canonical_json(publication_content))

if len(publication_content_hash) != 64:
    raise RuntimeError("Resolved publication content hash is not a SHA-256 value.")

semantic_annotations = {
    "Glossary_Term_References": PURVIEW_TERM_CODE,
    "Purview_Term_Id": PURVIEW_TERM_ID,
    "Purview_Publication_Content_Hash": publication_content_hash,
    "Governance_Request_Id": RUN_REQUEST_ID,
}
expected_metadata = []
for target in SEMANTIC_TARGETS:
    expected_metadata.append(
        {
            "table": target["table"],
            "objectType": target["objectType"],
            "objectName": target["objectName"],
            "description": (
                f"{target['descriptionPrefix']} "
                f"Governed definition ({PURVIEW_TERM_CODE}): {approved_definition}"
            ),
            "annotations": semantic_annotations,
        }
    )

expected_hash = sha256_text(canonical_json(expected_metadata))
print(
    f"[READY] request={RUN_REQUEST_ID} status={request_row[0]} "
    f"targets={len(expected_metadata)} expected_hash={expected_hash}"
)
for item in expected_metadata:
    print(f"  {item['objectType']}: {item['table']}.{item['objectName']}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Apply only descriptions and annotations through SemPy Labs TOM

if DEMO_MODE:
    print("[DEMO_MODE] Semantic metadata write skipped.")
else:
    with connect_semantic_model(dataset=MODEL_NAME, readonly=False) as tom:
        for expected in expected_metadata:
            obj = semantic_object(tom, expected)
            obj.Description = expected["description"]
            for key, value in expected["annotations"].items():
                upsert_annotation(obj, key, value)
    print(f"[APPLIED] semantic metadata written to {len(expected_metadata)} object(s).")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Reopen the model read-only and compute the observed metadata hash

if DEMO_MODE:
    observed_metadata = expected_metadata
    observed_hash = expected_hash
    validation_status = "Pending"
    print("[DEMO_MODE] Read-back skipped; expected metadata shown as the plan.")
else:
    observed_metadata = []
    with connect_semantic_model(dataset=MODEL_NAME, readonly=True) as tom:
        for expected in expected_metadata:
            obj = semantic_object(tom, expected)
            observed_metadata.append(
                {
                    "table": expected["table"],
                    "objectType": expected["objectType"],
                    "objectName": expected["objectName"],
                    "description": str(obj.Description or ""),
                    "annotations": {key: read_annotation(obj, key) for key in ANNOTATION_KEYS},
                }
            )

    observed_hash = sha256_text(canonical_json(observed_metadata))
    validation_status = "Passed" if observed_hash == expected_hash else "Failed"
    print(
        f"[READBACK] status={validation_status} expected_hash={expected_hash} "
        f"observed_hash={observed_hash}"
    )

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 6: Persist the read-back receipt and complete only after both gates pass

if DEMO_MODE:
    print("[DEMO_MODE] SQL receipt and request completion skipped.")
else:
    observed_at = utc_now()
    evidence = canonical_json(
        {
            "model": MODEL_NAME,
            "termCode": PURVIEW_TERM_CODE,
            "termId": PURVIEW_TERM_ID,
            "publicationContentHash": publication_content_hash,
            "expectedMetadata": expected_metadata,
            "observedMetadata": observed_metadata,
            "expectedHash": expected_hash,
            "observedHash": observed_hash,
            "observedAt": observed_at.isoformat() + "Z",
        }
    )

    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            MERGE dbo.governance_target_receipts WITH (HOLDLOCK) AS target
            USING (SELECT ? AS request_id, 'Fabric' AS target_system,
                          'SemanticModel' AS target_object_type, ? AS target_object_id,
                          'SemanticModelReadback' AS receipt_type) AS source
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
            ) VALUES (?, 'Fabric', 'SemanticModel', ?, 'SemanticModelReadback',
                      ?, ?, ?, ?, ?);
            """,
            RUN_REQUEST_ID,
            MODEL_NAME,
            expected_hash,
            observed_hash,
            validation_status,
            observed_at,
            evidence,
            RUN_REQUEST_ID,
            MODEL_NAME,
            expected_hash,
            observed_hash,
            validation_status,
            observed_at,
            evidence,
        )

        event_type = "SemanticModelReadbackPassed" if validation_status == "Passed" else "SemanticModelReadbackFailed"
        event_status = "Validated" if validation_status == "Passed" else "Approved"
        source_event_id = f"{RUN_REQUEST_ID}:{event_type}:{observed_hash}"
        cursor.execute(
            """
            IF NOT EXISTS (
                SELECT 1 FROM dbo.governance_events
                WHERE source_system = 'Fabric' AND source_event_id = ?
            )
            INSERT dbo.governance_events (
                request_id, event_type, event_status, source_system, source_event_id,
                actor_id, occurred_at, observed_at, payload, payload_hash
            ) VALUES (?, ?, ?, 'Fabric', ?, NULL, ?, ?, ?, ?)
            """,
            source_event_id,
            RUN_REQUEST_ID,
            event_type,
            event_status,
            source_event_id,
            observed_at,
            observed_at,
            evidence,
            observed_hash,
        )

        if validation_status == "Passed":
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM dbo.governance_target_receipts
                WHERE request_id = ? AND validation_status = 'Passed'
                  AND ((target_system = 'Purview' AND receipt_type = 'PublicationReadback')
                    OR (target_system = 'Fabric' AND receipt_type = 'SemanticModelReadback'))
                """,
                RUN_REQUEST_ID,
            )
            if cursor.fetchone()[0] != 2:
                raise RuntimeError("Both required read-back receipts must pass before completion.")

            cursor.execute(
                """
                UPDATE dbo.governance_requests
                SET current_status = 'Completed', completed_at = COALESCE(completed_at, ?),
                    last_observed_at = ?, failure_reason = NULL
                WHERE request_id = ? AND current_status IN ('Approved', 'Completed')
                """,
                observed_at,
                observed_at,
                RUN_REQUEST_ID,
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Request status changed concurrently; completion was refused.")

            completed_event_id = f"{RUN_REQUEST_ID}:GovernanceRequestCompleted:{expected_hash}"
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.governance_events
                    WHERE source_system = 'Fabric' AND source_event_id = ?
                )
                INSERT dbo.governance_events (
                    request_id, event_type, event_status, source_system, source_event_id,
                    actor_id, occurred_at, observed_at, payload, payload_hash
                ) VALUES (?, 'GovernanceRequestCompleted', 'Completed', 'Fabric', ?,
                          NULL, ?, ?, ?, ?)
                """,
                completed_event_id,
                RUN_REQUEST_ID,
                completed_event_id,
                observed_at,
                observed_at,
                evidence,
                expected_hash,
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    if validation_status != "Passed":
        raise RuntimeError("Semantic read-back differs from the approved metadata; request remains Approved.")
    print(f"[COMPLETED] request={RUN_REQUEST_ID} SemanticModelReadback=Passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 7: Final verification

if not DEMO_MODE:
    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT current_status, completed_at
            FROM dbo.governance_requests
            WHERE request_id = ?
            """,
            RUN_REQUEST_ID,
        )
        final_request = cursor.fetchone()
        cursor.execute(
            """
            SELECT target_system, receipt_type, validation_status,
                   CASE WHEN expected_hash = observed_hash THEN 1 ELSE 0 END AS hashes_match
            FROM dbo.governance_target_receipts
            WHERE request_id = ?
              AND receipt_type IN ('PublicationReadback', 'SemanticModelReadback')
            ORDER BY target_system, receipt_type
            """,
            RUN_REQUEST_ID,
        )
        final_receipts = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    if not final_request or final_request[0] != "Completed" or final_request[1] is None:
        raise RuntimeError("Final verification failed: request is not durably Completed.")
    if len(final_receipts) != 2 or any(row[2] != "Passed" or row[3] != 1 for row in final_receipts):
        raise RuntimeError(f"Final verification failed: unexpected receipts {final_receipts!r}.")

    print(f"[VERIFIED] request={RUN_REQUEST_ID} status=Completed receipts=2/2 Passed")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }