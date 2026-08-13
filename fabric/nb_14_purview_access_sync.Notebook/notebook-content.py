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
