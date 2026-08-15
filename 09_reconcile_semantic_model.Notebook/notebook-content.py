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

# Fabric Notebook: nb_14_purview_access_sync
# Purpose: P3 proof for one Purview-native Data Product access decision loop (DP-CUST360).
#
# CONFIRMED LIMITATION (2026-08-12, see repo memory purview-api-notes.md): no REST API, Microsoft
# Graph endpoint, or Purview diagnostic log captures a Data Product access request's decision.
# Unlike nb_12 (which observes the term's own `status` field as a real API proxy for approval),
# there is no equivalent observable signal for an access decision. This notebook therefore records
# the decision as OPERATOR-ATTESTED evidence -- directly witnessed in the Purview portal by the
# person running this notebook -- clearly labeled as attested, not machine-verified. The Data
# Product's own current state (status, domain, definition hash) IS read live and IS real,
# API-verified evidence; only the access decision itself is attested.

DEMO_MODE = False
WORKFLOW_CONFIGURED = True
RUN_CORRELATION_ID = "DP-CUST360-ACCESS-RUPAL-A"

ATTESTED_REQUESTER_UPN = "rupal.solanki@MngEnvMCAP660444.onmicrosoft.com"
ATTESTED_PRIVACY_REVIEWER_UPN = "victoria.tan@MngEnvMCAP660444.onmicrosoft.com"
ATTESTED_APPROVER_UPN = "victoria.tan@MngEnvMCAP660444.onmicrosoft.com"
ATTESTED_PURPOSE = "Customer-experience analytics"
ATTESTED_BUSINESS_JUSTIFICATION = "Rupal Solanki (Data Steward, Customer Operations) requested access to Customer 360 to support customer-experience analytics reporting. Victoria Tan completed both required approval tiers (Privacy Compliance Approval, then the main Approval for data access request) in the Requests and approvals flyout."
ATTESTED_DECISION = "Approved"
ATTESTED_BY = "sean.kelley@microsoft.com - directly observed both approval tiers completed live in Requests and approvals"

PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_CATALOG_BASE_URL = (
    "https://b7e47691-9726-4f67-a302-e567815f3522-api."
    "purview-service.microsoft.com/datagovernance/catalog"
)
PURVIEW_DATA_PRODUCT_ID = "22794e10-31d6-4f15-b4f0-8238a2657503"
PURVIEW_DATA_PRODUCT_CODE = "DP-CUST360"
PURVIEW_DOMAIN_ID = "01aaf58a-727e-4a91-bbe9-880fb3d934ee"

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

print(
    f"nb_14 | DEMO_MODE={DEMO_MODE} | workflow_configured={WORKFLOW_CONFIGURED} | "
    f"product={PURVIEW_DATA_PRODUCT_CODE}/{PURVIEW_DATA_PRODUCT_ID}"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Authentication and connection helpers (mirrors nb_12)

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


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ATTESTATION_LIMITATION_NOTICE = (
    "No Purview REST API, Microsoft Graph endpoint, or diagnostic log exposes a Data Product "
    "access request's decision for independent machine verification (confirmed 2026-08-12 via "
    "exhaustive endpoint probing, $metadata discovery, Graph API checks, and a live diagnostic-"
    "logging test that captured zero relevant events). The decision below is attested by the "
    "operator who directly observed it in the Purview portal, not independently verified by this "
    "notebook. The Data Product's own live status/domain/definition hash IS independently verified."
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Read and normalize the supported Data Product resource (real, API-verified evidence)

response = requests.get(
    f"{PURVIEW_CATALOG_BASE_URL}/dataproducts/{PURVIEW_DATA_PRODUCT_ID}",
    headers={"Authorization": f"Bearer {get_purview_token()}"},
    timeout=60,
)
response.raise_for_status()
raw_product = response.json()

product_snapshot = {
    "id": raw_product.get("id"),
    "name": raw_product.get("name"),
    "domain": raw_product.get("domain"),
    "status": raw_product.get("status"),
    "type": raw_product.get("type"),
    "description": raw_product.get("description"),
    "businessUse": raw_product.get("businessUse"),
    "endorsed": raw_product.get("endorsed"),
}

if product_snapshot["id"] != PURVIEW_DATA_PRODUCT_ID:
    raise RuntimeError("Unified Catalog returned an unexpected data product ID.")
if product_snapshot["domain"] != PURVIEW_DOMAIN_ID:
    raise RuntimeError(f"{PURVIEW_DATA_PRODUCT_CODE} is no longer assigned to the expected Customer Operations domain.")
if product_snapshot["status"] not in ("Draft", "Published"):
    raise RuntimeError(f"Unsupported data product lifecycle status: {product_snapshot['status']!r}")

snapshot_json = canonical_json(product_snapshot)
definition_hash = sha256_text(snapshot_json)
observed_at = utc_now()

print(
    f"Observed {PURVIEW_DATA_PRODUCT_CODE}: status={product_snapshot['status']} "
    f"hash={definition_hash[:12]} observed_at={observed_at.isoformat()}Z"
)
print(json.dumps(product_snapshot, indent=2, ensure_ascii=True))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Enforce guardrails and build the attested decision payload

if DEMO_MODE:
    print("[DEMO_MODE] Baseline observation only; no SQL ledger writes will occur.")
elif not WORKFLOW_CONFIGURED:
    raise RuntimeError(
        "Set WORKFLOW_CONFIGURED=True only after the native Data product access policy is "
        "configured on DP-CUST360 with Victoria Tan as Approver and Privacy reviewer."
    )
elif not RUN_CORRELATION_ID.strip():
    raise RuntimeError("RUN_CORRELATION_ID is required for a live P3 access observation.")
elif ATTESTED_DECISION not in ("Approved", "Rejected"):
    raise RuntimeError("ATTESTED_DECISION must be exactly 'Approved' or 'Rejected'.")
elif not all(
    [
        ATTESTED_REQUESTER_UPN.strip(),
        ATTESTED_PRIVACY_REVIEWER_UPN.strip(),
        ATTESTED_APPROVER_UPN.strip(),
        ATTESTED_PURPOSE.strip(),
        ATTESTED_BUSINESS_JUSTIFICATION.strip(),
        ATTESTED_BY.strip(),
    ]
):
    raise RuntimeError("All ATTESTED_* fields are required for a live P3 access observation.")

request_id = "PV-CUST360-ACCESS-" + sha256_text(RUN_CORRELATION_ID.strip())[:20].upper()
source_event_id = f"{request_id}:{ATTESTED_DECISION}:{definition_hash}"
attestation_payload = canonical_json(
    {
        "localCorrelationId": RUN_CORRELATION_ID.strip(),
        "definitionHash": definition_hash,
        "dataProduct": product_snapshot,
        "requesterUpn": ATTESTED_REQUESTER_UPN.strip(),
        "privacyReviewerUpn": ATTESTED_PRIVACY_REVIEWER_UPN.strip(),
        "approverUpn": ATTESTED_APPROVER_UPN.strip(),
        "purpose": ATTESTED_PURPOSE.strip(),
        "businessJustification": ATTESTED_BUSINESS_JUSTIFICATION.strip(),
        "decision": ATTESTED_DECISION,
        "attestedBy": ATTESTED_BY.strip(),
        "attestationLimitation": ATTESTATION_LIMITATION_NOTICE,
    }
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 5: Persist one idempotent Submitted/Approved-or-Rejected observation

if not DEMO_MODE:
    connection = get_sql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT current_status
            FROM dbo.governance_requests WITH (UPDLOCK, HOLDLOCK)
            WHERE request_id = ?
            """,
            request_id,
        )
        existing_row = cursor.fetchone()
        existing_status = existing_row[0] if existing_row else None

        normalized_status = "Approved" if ATTESTED_DECISION == "Approved" else "Rejected"

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
                    requested_by, current_status, proposed_payload, source_snapshot, last_observed_at
                ) VALUES (?, 'DataProductAccess', 'Purview', NULL,
                          'Purview', 'DataProduct', ?, ?, ?, ?, ?, ?, ?)
                """,
                request_id,
                PURVIEW_DATA_PRODUCT_ID,
                product_snapshot["name"],
                ATTESTED_REQUESTER_UPN.strip(),
                normalized_status,
                attestation_payload,
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
            ) VALUES (?, ?, ?, 'Purview', ?, ?, ?, ?, ?, ?)
            """,
            source_event_id,
            request_id,
            "AccessDecisionAttested",
            normalized_status,
            source_event_id,
            ATTESTED_BY.strip(),
            observed_at,
            observed_at,
            attestation_payload,
            definition_hash,
        )

        if normalized_status == "Approved":
            evidence = canonical_json(
                {
                    "dataProduct": product_snapshot,
                    "attestation": json.loads(attestation_payload),
                    "observedAt": observed_at.isoformat() + "Z",
                    "verificationMethod": "operator-attested; data product state independently API-verified",
                }
            )
            cursor.execute(
                """
                MERGE dbo.governance_target_receipts WITH (HOLDLOCK) AS target
                USING (SELECT ? AS request_id, 'Purview' AS target_system,
                              'DataProduct' AS target_object_type, ? AS target_object_id,
                              'AccessDecisionReadback' AS receipt_type) AS source
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
                ) VALUES (?, 'Purview', 'DataProduct', ?, 'AccessDecisionReadback',
                          ?, ?, ?, ?, ?);
                """,
                request_id,
                PURVIEW_DATA_PRODUCT_ID,
                definition_hash,
                definition_hash,
                "Passed",
                observed_at,
                evidence,
                request_id,
                PURVIEW_DATA_PRODUCT_ID,
                definition_hash,
                definition_hash,
                "Passed",
                observed_at,
                evidence,
            )
            cursor.execute(
                """
                UPDATE dbo.governance_requests
                SET current_status = 'Completed', completed_at = ?
                WHERE request_id = ?
                """,
                observed_at,
                request_id,
            )

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

# Cell 6: Verify the durable P3 evidence contract

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
            SELECT validation_status, expected_hash, observed_hash
            FROM dbo.governance_target_receipts
            WHERE request_id = ? AND target_system = 'Purview'
              AND target_object_type = 'DataProduct' AND target_object_id = ?
              AND receipt_type = 'AccessDecisionReadback'
            """,
            request_id,
            PURVIEW_DATA_PRODUCT_ID,
        )
        access_receipt = cursor.fetchone()

        if ATTESTED_DECISION == "Approved":
            if not request_evidence or request_evidence[0] != "Completed":
                raise RuntimeError("P3 verification failed: request is not Completed.")
            if not access_receipt or access_receipt[0] != "Passed":
                raise RuntimeError("P3 verification failed: AccessDecisionReadback did not pass.")
            if access_receipt[1] != access_receipt[2]:
                raise RuntimeError("P3 verification failed: access receipt hashes differ.")
            print(
                f"[VERIFIED] request={request_id} status=Completed "
                f"events={event_counts} receipt=Passed (attested decision)"
            )
        else:
            if not request_evidence or request_evidence[0] != "Rejected":
                raise RuntimeError("P3 verification failed: request is not Rejected.")
            print(f"[VERIFIED] request={request_id} status=Rejected events={event_counts}")
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
    "P3 Purview access-decision evidence collection finished. This is an audit-only scenario: "
    "no semantic-model reconciliation step follows, per docs/purview-native-workflow-wireframe.md. "
    "The decision itself is operator-attested, not independently machine-verified -- see "
    "ATTESTATION_LIMITATION_NOTICE and repo memory for the confirmed platform limitation."
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }




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

# Fabric Notebook: nb_15_purview_dataproduct_sync
# Purpose: P4 proof for one Purview-native Data Product publish workflow (DP-SVCPERF).
#
# Data Products are a Tier 1 evidence object (docs/purview-native-workflow-wireframe.md §2a):
# the Unified Catalog API exposes the product's own `status` field directly, the same real,
# independently-verifiable proxy signal nb_12 uses for Term publish. This notebook mirrors nb_12's
# structure exactly, substituting DataProduct for GlossaryTerm.

DEMO_MODE = False
WORKFLOW_CONFIGURED = True
RUN_CORRELATION_ID = "DP-SVCPERF-PUBLISH-71e05bec"  # Real workflow run 71e05bec-d1fb-4923-b503-ca41d10d3310, approved by Ranbir Singh 2026-08-12.

PURVIEW_TENANT_ID = "b7e47691-9726-4f67-a302-e567815f3522"
PURVIEW_CATALOG_BASE_URL = (
    "https://b7e47691-9726-4f67-a302-e567815f3522-api."
    "purview-service.microsoft.com/datagovernance/catalog"
)
PURVIEW_DATA_PRODUCT_ID = "d5c9cc77-aaaf-4e07-9010-e3758d50cb87"  # Re-verified 2026-08-12 via /dataproducts list; changed from 59e0c2d5-... after unpublish/edit/republish/unpublish cycle.
PURVIEW_DATA_PRODUCT_CODE = "DP-SVCPERF"
PURVIEW_DOMAIN_ID = "9d82a6da-eed1-4dae-a036-84c1dcc65337"  # Re-verified 2026-08-12 via /businessdomains; changed from 061ad71f-...

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

print(
    f"nb_15 | DEMO_MODE={DEMO_MODE} | workflow_configured={WORKFLOW_CONFIGURED} | "
    f"product={PURVIEW_DATA_PRODUCT_CODE}/{PURVIEW_DATA_PRODUCT_ID}"
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Authentication and connection helpers (mirrors nb_12)

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


def publication_content_hash(product):
    content = dict(product)
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

# Cell 3: Read and normalize the supported Data Product resource

response = requests.get(
    f"{PURVIEW_CATALOG_BASE_URL}/dataproducts/{PURVIEW_DATA_PRODUCT_ID}",
    headers={"Authorization": f"Bearer {get_purview_token()}"},
    timeout=60,
)
response.raise_for_status()
raw_product = response.json()

product_snapshot = {
    "id": raw_product.get("id"),
    "name": raw_product.get("name"),
    "domain": raw_product.get("domain"),
    "status": raw_product.get("status"),
    "type": raw_product.get("type"),
    "description": raw_product.get("description"),
    "businessUse": raw_product.get("businessUse"),
    "endorsed": raw_product.get("endorsed"),
}

if product_snapshot["id"] != PURVIEW_DATA_PRODUCT_ID:
    raise RuntimeError("Unified Catalog returned an unexpected data product ID.")
if product_snapshot["domain"] != PURVIEW_DOMAIN_ID:
    raise RuntimeError(f"{PURVIEW_DATA_PRODUCT_CODE} is no longer assigned to the expected Service Delivery domain.")
if product_snapshot["status"] not in ("Draft", "Published"):
    raise RuntimeError(f"Unsupported data product lifecycle status: {product_snapshot['status']!r}")

snapshot_json = canonical_json(product_snapshot)
definition_hash = sha256_text(snapshot_json)
content_hash = publication_content_hash(product_snapshot)
observed_at = utc_now()

print(
    f"Observed {PURVIEW_DATA_PRODUCT_CODE}: status={product_snapshot['status']} "
    f"hash={definition_hash[:12]} observed_at={observed_at.isoformat()}Z"
)
print(json.dumps(product_snapshot, indent=2, ensure_ascii=True))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 4: Enforce the P4 correlation and Draft-before-Published guardrails

if DEMO_MODE:
    print("[DEMO_MODE] Baseline observation only; no SQL ledger writes will occur.")
elif not WORKFLOW_CONFIGURED:
    raise RuntimeError(
        "Set WORKFLOW_CONFIGURED=True only after a native Data product publish workflow is scoped "
        "to the Service Delivery governance domain."
    )
elif not RUN_CORRELATION_ID.strip():
    raise RuntimeError("RUN_CORRELATION_ID is required for a live P4 workflow observation.")

request_id = "PV-DP-SVCPERF-" + sha256_text(RUN_CORRELATION_ID.strip())[:20].upper()
source_event_id = f"{request_id}:{product_snapshot['status']}:{definition_hash}"
request_payload = canonical_json(
    {
        "localCorrelationId": RUN_CORRELATION_ID.strip(),
        "definitionHash": definition_hash,
        "publicationContentHash": content_hash,
        "dataProduct": product_snapshot,
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

        if product_snapshot["status"] == "Published" and existing_status not in ("Draft", "Approved"):
            raise RuntimeError(
                "Refusing to record Published as approval evidence because this correlation "
                "has no prior Draft observation. Unpublish/edit DP-SVCPERF, run this notebook once "
                "while Draft, submit it to the native workflow, then rerun after approval."
            )

        if existing_payload:
            expected_hash = existing_payload.get("publicationContentHash")
            if not expected_hash:
                expected_hash = publication_content_hash(existing_payload["dataProduct"])
        else:
            expected_hash = content_hash
        normalized_status = "Approved" if product_snapshot["status"] == "Published" else "Draft"

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
                ) VALUES (?, 'DataProductPublish', 'Purview', NULL,
                          'Purview', 'DataProduct', ?, ?, ?, ?, ?, ?)
                """,
                request_id,
                PURVIEW_DATA_PRODUCT_ID,
                product_snapshot["name"],
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
            "DataProductPublishedObserved" if normalized_status == "Approved" else "DataProductDraftObserved",
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
                WHERE source_system = 'Purview' AND object_type = 'DataProduct'
                  AND object_id = ? AND source_version_id = ?
            )
            INSERT dbo.governed_object_versions (
                request_id, source_system, object_type, object_id, source_version_id,
                lifecycle_status, definition_hash, object_payload, effective_at, observed_at
            ) VALUES (?, 'Purview', 'DataProduct', ?, ?, ?, ?, ?, ?, ?)
            """,
            PURVIEW_DATA_PRODUCT_ID,
            definition_hash,
            request_id,
            PURVIEW_DATA_PRODUCT_ID,
            definition_hash,
            product_snapshot["status"],
            definition_hash,
            snapshot_json,
            observed_at,
            observed_at,
        )

        if normalized_status == "Approved":
            validation_status = "Passed" if content_hash == expected_hash else "Failed"
            evidence = canonical_json(
                {
                    "dataProduct": product_snapshot,
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
                              'DataProduct' AS target_object_type, ? AS target_object_id,
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
                ) VALUES (?, 'Purview', 'DataProduct', ?, 'PublicationReadback',
                          ?, ?, ?, ?, ?);
                """,
                request_id,
                PURVIEW_DATA_PRODUCT_ID,
                expected_hash,
                content_hash,
                validation_status,
                observed_at,
                evidence,
                request_id,
                PURVIEW_DATA_PRODUCT_ID,
                expected_hash,
                content_hash,
                validation_status,
                observed_at,
                evidence,
            )
            if validation_status != "Passed":
                raise RuntimeError("Published data product read-back did not match the Draft definition hash.")

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

# Cell 6: Verify the durable P4 evidence contract

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
              AND target_object_type = 'DataProduct' AND target_object_id = ?
              AND receipt_type = 'PublicationReadback'
            """,
            request_id,
            PURVIEW_DATA_PRODUCT_ID,
        )
        publication_receipt = cursor.fetchone()

        if not request_evidence or request_evidence[0] != "Approved":
            raise RuntimeError("P4 verification failed: request is not Approved.")
        if any(request_evidence[index] is not None for index in range(1, 4)):
            raise RuntimeError("P4 verification failed: unsupported workflow fields must remain NULL.")
        if event_counts.get("DataProductDraftObserved") != 1 or event_counts.get("DataProductPublishedObserved") != 1:
            raise RuntimeError(f"P4 verification failed: unexpected event counts {event_counts!r}.")
        if version_counts.get("Draft") != 1 or version_counts.get("Published") != 1:
            raise RuntimeError(f"P4 verification failed: unexpected version counts {version_counts!r}.")
        if not publication_receipt or publication_receipt[0] != "Passed":
            raise RuntimeError("P4 verification failed: PublicationReadback did not pass.")
        if publication_receipt[1] != publication_receipt[2]:
            raise RuntimeError("P4 verification failed: publication receipt hashes differ.")

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
    "P4 Purview evidence collection finished. This notebook does not mark the request "
    "Completed; semantic-model reconciliation and its read-back receipt are a separate step."
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }




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

# Fabric Notebook: nb_16_dataproduct_semantic_reconcile
# Purpose: P4 semantic reconciliation for an approved Purview Data Product publish (DP-SVCPERF).
#
# Mirrors nb_13's pattern exactly, substituting the DataProduct evidence chain (nb_15) for the
# GlossaryTerm chain (nb_12/nb_13). Fails closed: requires a passed PublicationReadback receipt,
# changes metadata only, verifies a fresh semantic-model read-back, and marks the request
# Completed only after both required receipts pass.
#
# SEMANTIC_TARGETS below are confirmed real columns (verified 2026-08-12 against the live TMDL
# definitions in BrookfieldEnercare.SemanticModel/definition/tables/).

DEMO_MODE = False
RUN_REQUEST_ID = "PV-DP-SVCPERF-9EAF4919D7DFD8F8B5C6"  # Real, live-approved P4 request confirmed via nb_15 2026-08-12.

MODEL_NAME = "BrookfieldEnercare"
PURVIEW_DATA_PRODUCT_ID = "d5c9cc77-aaaf-4e07-9010-e3758d50cb87"  # Re-verified 2026-08-12; changed from 59e0c2d5-... after unpublish/edit/republish/unpublish cycle.
PURVIEW_DATA_PRODUCT_CODE = "DP-SVCPERF"

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

SEMANTIC_TARGETS = [
    # Confirmed 2026-08-12 against BrookfieldEnercare.SemanticModel/definition/tables/*.tmdl.
    # ServiceZoneCode does not exist anywhere in the model; swapped for dim_equipment.EquipmentType.
    # fct_service_request.IsSlaBreachFlag is intentionally excluded: it already carries P1's GT-SLA
    # governance annotations (Glossary_Term_References=GT-SLA) and must not be overwritten here.
    {
        "table": "fct_service_request",
        "objectType": "Column",
        "objectName": "TechnicianId",
        "descriptionPrefix": "Identifies the dispatched technician for the service request.",
    },
    {
        "table": "dim_equipment",
        "objectType": "Column",
        "objectName": "EquipmentType",
        "descriptionPrefix": "Identifies the equipment category serviced under this request.",
    },
]

print(f"nb_16 | DEMO_MODE={DEMO_MODE} | request={RUN_REQUEST_ID or '<not set>'} | model={MODEL_NAME}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 2: Connection and normalization helpers (mirrors nb_13)

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
    "DataProduct_References",
    "Purview_DataProduct_Id",
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
    raise RuntimeError("Set RUN_REQUEST_ID to the approved P4 governance request ID.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cell 3: Load the approved source definition and enforce the P4 gate

connection = get_sql_connection()
cursor = connection.cursor()
try:
    cursor.execute(
        """
        SELECT current_status, proposed_payload
        FROM dbo.governance_requests
        WHERE request_id = ? AND request_type = 'DataProductPublish'
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
          AND target_object_type = 'DataProduct' AND target_object_id = ?
          AND receipt_type = 'PublicationReadback'
        """,
        RUN_REQUEST_ID,
        PURVIEW_DATA_PRODUCT_ID,
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
          AND object_type = 'DataProduct' AND object_id = ?
          AND lifecycle_status = 'Published'
        ORDER BY observed_at DESC, version_id DESC
        """,
        RUN_REQUEST_ID,
        PURVIEW_DATA_PRODUCT_ID,
    )
    version_row = cursor.fetchone()
    if not version_row:
        raise RuntimeError("No Published Purview object version exists for this request.")
finally:
    cursor.close()
    connection.close()

request_payload = json.loads(request_row[1]) if request_row[1] else {}
published_product = json.loads(version_row[0])
if published_product.get("id") != PURVIEW_DATA_PRODUCT_ID or published_product.get("status") != "Published":
    raise RuntimeError("Published source payload does not match the configured DP-SVCPERF data product.")

approved_definition = description_text(published_product.get("description"))
if not approved_definition:
    raise RuntimeError("Published DP-SVCPERF has no usable description to reconcile.")

receipt_content_hash = publication_receipt[1]
payload_content_hash = request_payload.get("publicationContentHash")
if receipt_content_hash and payload_content_hash and receipt_content_hash != payload_content_hash:
    raise RuntimeError("P4 receipt and proposed_payload publication hashes differ.")

if receipt_content_hash:
    publication_content_hash = receipt_content_hash
elif payload_content_hash:
    publication_content_hash = payload_content_hash
else:
    publication_content = dict(published_product)
    publication_content.pop("status", None)
    publication_content_hash = sha256_text(canonical_json(publication_content))

if len(publication_content_hash) != 64:
    raise RuntimeError("Resolved publication content hash is not a SHA-256 value.")

semantic_annotations = {
    "DataProduct_References": PURVIEW_DATA_PRODUCT_CODE,
    "Purview_DataProduct_Id": PURVIEW_DATA_PRODUCT_ID,
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
                f"Governed definition ({PURVIEW_DATA_PRODUCT_CODE}): {approved_definition}"
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
            "dataProductCode": PURVIEW_DATA_PRODUCT_CODE,
            "dataProductId": PURVIEW_DATA_PRODUCT_ID,
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

        if validation_status == "Passed":
            cursor.execute(
                """
                UPDATE dbo.governance_requests
                SET current_status = 'Completed', completed_at = ?
                WHERE request_id = ?
                """,
                observed_at,
                RUN_REQUEST_ID,
            )

        connection.commit()
        print(f"[READBACK] status={validation_status} request={RUN_REQUEST_ID}")
        if validation_status != "Passed":
            raise RuntimeError("Semantic read-back did not match the expected metadata hash.")
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

# Cell 7: Verify the closed-loop completion

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
        request_evidence = cursor.fetchone()

        cursor.execute(
            """
            SELECT receipt_type, validation_status
            FROM dbo.governance_target_receipts
            WHERE request_id = ?
            """,
            RUN_REQUEST_ID,
        )
        receipts = dict(cursor.fetchall())

        if not request_evidence or request_evidence[0] != "Completed":
            raise RuntimeError("P4 closeout verification failed: request is not Completed.")
        if receipts.get("PublicationReadback") != "Passed" or receipts.get("SemanticModelReadback") != "Passed":
            raise RuntimeError(f"P4 closeout verification failed: unexpected receipts {receipts!r}.")

        print(
            f"[VERIFIED] request={RUN_REQUEST_ID} status=Completed "
            f"receipts={receipts} completed_at={request_evidence[1]}"
        )
    finally:
        cursor.close()
        connection.close()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }




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

# Fabric Notebook: nb_17_g18_semantic_promotion
# Purpose: G19-6 -- real semantic-model TOM promotion for a G18-A-approved source object,
# completing the discovery->classify->approve->CDE/ontology-map->promote chain.
#
# Unlike nb_13/nb_16 (which only annotate EXISTING columns), this notebook ADDS a brand-new
# measure to the semantic model -- the actual "promotion" step G18's design always intended.
# Fails closed: requires the gating SemanticModelPromotion request to be Approved and its
# prerequisite ontology-mapping receipt to have passed.
#
# Kept as a single flattened cell -- a multi-cell version of this notebook repeatedly failed
# with a generic System_Cancelled_Session_Statements_Failed error (no cell-level detail
# available) even though a flattened single-cell diagnostic replicating the same TOM read+write
# logic succeeded twice. Matches an established repo pattern (see repo memory): flatten to one
# cell when a multi-cell notebook fails this way.

DEMO_MODE = False
RUN_REQUEST_ID = "SEMPROMO-TECHUTIL-001"  # Real, Approved via sql/28, gated on ONTOMAP-TECHUTIL-001.

MODEL_NAME = "BrookfieldEnercare"
TARGET_TABLE = "fct_service_request"
NEW_MEASURE_NAME = "Technician Utilization Rate"
NEW_MEASURE_EXPRESSION = "DIVIDE(DISTINCTCOUNT(fct_service_request[TechnicianId]), COUNTROWS(fct_service_request))"
NEW_MEASURE_FORMAT_STRING = "0.0%"

SERVER_NAME = "sqlserver-sk2wus3.database.windows.net"
DATABASE_NAME = "sqldemo"
SQL_PORT = 1433
SQL_LOGIN_TIMEOUT_SECONDS = 30
SQL_AUTH_MODE = "tokenlibrary"  # tokenlibrary | managed_identity

print(f"nb_17 | DEMO_MODE={DEMO_MODE} | request={RUN_REQUEST_ID} | model={MODEL_NAME}")

import hashlib
import json
import struct
import subprocess
import sys
from datetime import datetime, timezone

import pyodbc

try:
    from sempy_labs.tom import connect_semantic_model
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "semantic-link-labs"], check=True)
    from sempy_labs.tom import connect_semantic_model

ODBC_SQL_COPT_SS_ACCESS_TOKEN = 1256
ANNOTATION_KEYS = ("SourceObject_References", "KeyResult_Id", "Governance_Request_Id")


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


def upsert_annotation(obj, key, value):
    annotations = getattr(obj, "Annotations", None)
    if annotations is None:
        raise RuntimeError(f"Annotations are unavailable on semantic object {obj.Name}.")
    existing = find_by_name(annotations, key)
    if existing is not None:
        existing.Value = value
    else:
        from Microsoft.AnalysisServices.Tabular import Annotation as TomAnnotation
        new_annotation = TomAnnotation()
        new_annotation.Name = key
        new_annotation.Value = value
        annotations.Add(new_annotation)


def read_annotation(obj, key):
    annotation = find_by_name(obj.Annotations, key)
    return None if annotation is None else str(annotation.Value)


if not RUN_REQUEST_ID.strip():
    raise RuntimeError("Set RUN_REQUEST_ID to the approved SemanticModelPromotion request ID.")

# Load the approved request and enforce the gate -- requires the prerequisite ontology-mapping
# receipt to have already passed (fails closed).
connection = get_sql_connection()
cursor = connection.cursor()
try:
    cursor.execute(
        """
        SELECT current_status, proposed_payload
        FROM dbo.governance_requests
        WHERE request_id = ? AND request_type = 'SemanticModelPromotion'
        """,
        RUN_REQUEST_ID,
    )
    request_row = cursor.fetchone()
    if not request_row:
        raise RuntimeError("Governance request was not found or has the wrong request type.")
    if request_row[0] not in ("Approved", "Completed"):
        raise RuntimeError(f"Request must be Approved before promotion; found {request_row[0]!r}.")

    request_payload = json.loads(request_row[1]) if request_row[1] else {}
    ontology_request_id = request_payload.get("ontologyMappingRequestId")
    source_object_id = request_payload.get("sourceObjectId")
    key_result_id = request_payload.get("keyResultId")

    cursor.execute(
        """
        SELECT validation_status FROM dbo.governance_target_receipts
        WHERE request_id = ? AND target_object_id = ? AND receipt_type = 'OntologyMappingReadback'
        """,
        ontology_request_id,
        source_object_id,
    )
    ontology_receipt = cursor.fetchone()
    if not ontology_receipt or ontology_receipt[0] != "Passed":
        raise RuntimeError("Prerequisite OntologyMappingReadback must pass before semantic promotion.")
finally:
    cursor.close()
    connection.close()

expected_measure = {
    "table": TARGET_TABLE,
    "name": NEW_MEASURE_NAME,
    "expression": NEW_MEASURE_EXPRESSION,
    "formatString": NEW_MEASURE_FORMAT_STRING,
    "annotations": {
        "SourceObject_References": source_object_id,
        "KeyResult_Id": key_result_id,
        "Governance_Request_Id": RUN_REQUEST_ID,
    },
}
expected_hash = sha256_text(canonical_json(expected_measure))
print(f"[READY] request={RUN_REQUEST_ID} status={request_row[0]} target={TARGET_TABLE}.{NEW_MEASURE_NAME} expected_hash={expected_hash}")

# Apply -- add the new measure via SemPy Labs TOM (real TMDL mutation, not just a SQL receipt).
# NOTE: Microsoft.AnalysisServices.Tabular is only importable AFTER connect_semantic_model has
# bootstrapped the CLR bridge in this session -- importing it before any connect_semantic_model
# call raises ModuleNotFoundError: No module named 'Microsoft'. Always import it INSIDE the
# active `with` block (matches nb_16's upsert_annotation, which only ever runs inside one).
if DEMO_MODE:
    print("[DEMO_MODE] Semantic measure creation skipped.")
else:
    with connect_semantic_model(dataset=MODEL_NAME, readonly=False) as tom:
        from Microsoft.AnalysisServices.Tabular import Measure as TomMeasure

        table = find_by_name(tom.model.Tables, TARGET_TABLE)
        if table is None:
            raise RuntimeError(f"Semantic table not found: {TARGET_TABLE}")

        existing_measure = find_by_name(table.Measures, NEW_MEASURE_NAME)
        if existing_measure is None:
            new_measure = TomMeasure()
            new_measure.Name = NEW_MEASURE_NAME
            new_measure.Expression = NEW_MEASURE_EXPRESSION
            new_measure.FormatString = NEW_MEASURE_FORMAT_STRING
            table.Measures.Add(new_measure)
            target_measure = new_measure
            print(f"[APPLIED] Created new measure {TARGET_TABLE}.{NEW_MEASURE_NAME}")
        else:
            existing_measure.Expression = NEW_MEASURE_EXPRESSION
            existing_measure.FormatString = NEW_MEASURE_FORMAT_STRING
            target_measure = existing_measure
            print(f"[APPLIED] Updated existing measure {TARGET_TABLE}.{NEW_MEASURE_NAME}")

        for key, value in expected_measure["annotations"].items():
            upsert_annotation(target_measure, key, value)

# Reopen the model read-only and compute the observed hash (real read-back).
if DEMO_MODE:
    observed_measure = expected_measure
    observed_hash = expected_hash
    validation_status = "Pending"
    print("[DEMO_MODE] Read-back skipped; expected measure shown as the plan.")
else:
    with connect_semantic_model(dataset=MODEL_NAME, readonly=True) as tom:
        table = find_by_name(tom.model.Tables, TARGET_TABLE)
        measure = find_by_name(table.Measures, NEW_MEASURE_NAME)
        if measure is None:
            raise RuntimeError(f"Read-back failed: measure {TARGET_TABLE}.{NEW_MEASURE_NAME} does not exist.")
        observed_measure = {
            "table": TARGET_TABLE,
            "name": NEW_MEASURE_NAME,
            "expression": str(measure.Expression),
            "formatString": str(measure.FormatString or ""),
            "annotations": {key: read_annotation(measure, key) for key in ANNOTATION_KEYS},
        }

    observed_hash = sha256_text(canonical_json(observed_measure))
    validation_status = "Passed" if observed_hash == expected_hash else "Failed"
    print(f"[READBACK] status={validation_status} expected_hash={expected_hash} observed_hash={observed_hash}")

# Persist the read-back receipt and complete only after it passes.
if DEMO_MODE:
    print("[DEMO_MODE] SQL receipt and request completion skipped.")
else:
    observed_at = utc_now()
    evidence = canonical_json(
        {
            "model": MODEL_NAME,
            "sourceObjectId": source_object_id,
            "keyResultId": key_result_id,
            "expectedMeasure": expected_measure,
            "observedMeasure": observed_measure,
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
            f"{TARGET_TABLE}.{NEW_MEASURE_NAME}",
            expected_hash,
            observed_hash,
            validation_status,
            observed_at,
            evidence,
            RUN_REQUEST_ID,
            f"{TARGET_TABLE}.{NEW_MEASURE_NAME}",
            expected_hash,
            observed_hash,
            validation_status,
            observed_at,
            evidence,
        )

        if validation_status == "Passed":
            cursor.execute(
                "UPDATE dbo.governance_requests SET current_status = 'Completed', completed_at = ? WHERE request_id = ?",
                observed_at,
                RUN_REQUEST_ID,
            )

        connection.commit()
        print(f"[READBACK] status={validation_status} request={RUN_REQUEST_ID}")
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


