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

