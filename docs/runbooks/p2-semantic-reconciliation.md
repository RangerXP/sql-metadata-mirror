# P2 Semantic Reconciliation Runbook

**Request:** `PV-GT-SLA-0359C207890E4EB1B8AB`
**Notebook:** `nb_13_semantic_reconcile`
**Target model:** `BrookfieldEnercare`

This step applies the approved `GT-SLA` definition to the existing SLA semantic objects. It changes descriptions and governance annotations only; it does not alter DAX, lineage tags, columns, relationships, or partitions.

## 1. Sync Fabric from Git

1. In the Fabric workspace, open **Source control**.
2. Select **Update all** so `nb_13_semantic_reconcile` appears.
3. Open the notebook and confirm the `SempyLabsV2` environment and `lh_metadata` lakehouse are attached.

## 2. Run the Dry Run

In Cell 1, use:

```python
DEMO_MODE = True
RUN_REQUEST_ID = "PV-GT-SLA-0359C207890E4EB1B8AB"
```

Run all cells. Expected result:

```text
[READY] ... status=Approved targets=3 ...
[DEMO_MODE] Semantic metadata write skipped.
[DEMO_MODE] SQL receipt and request completion skipped.
```

The request remains `Approved`.

## 3. Apply and Verify

Change Cell 1 to:

```python
DEMO_MODE = False
RUN_REQUEST_ID = "PV-GT-SLA-0359C207890E4EB1B8AB"
```

Run all cells. The required terminal output is:

```text
[READBACK] status=Passed ...
[COMPLETED] request=PV-GT-SLA-0359C207890E4EB1B8AB SemanticModelReadback=Passed
[VERIFIED] request=PV-GT-SLA-0359C207890E4EB1B8AB status=Completed receipts=2/2 Passed
```

If read-back fails, the notebook records a failed `SemanticModelReadback` receipt and leaves the request `Approved`.

## 4. Inspect the Result

In the `sqldemo` SQL analytics endpoint, run:

```sql
SELECT request_id, current_status, completed_at
FROM dbo.governance_requests
WHERE request_id = 'PV-GT-SLA-0359C207890E4EB1B8AB';

SELECT target_system, target_object_type, target_object_id,
       receipt_type, validation_status, expected_hash, observed_hash
FROM dbo.governance_target_receipts
WHERE request_id = 'PV-GT-SLA-0359C207890E4EB1B8AB'
ORDER BY target_system, receipt_type;
```

Expected result: the request is `Completed`, and both `PublicationReadback` and `SemanticModelReadback` are `Passed` with matching hashes.

## Proven Execution

Validated on 2026-08-11 for request `PV-GT-SLA-0359C207890E4EB1B8AB`:

- Three semantic objects were updated and read back successfully.
- `SemanticModelReadback` passed with hash `e699c7842d8009828a21e17962224e3ee92989029bfea34d35c3d1081987dede`.
- `PublicationReadback` passed with hash `7bbd4fa674b042d407af51b8ced5ebd0ed24f9a8f6b54c9107d1f31394c5b40a`.
- The request reached `Completed` at `2026-08-11 23:10:02.516876` UTC.
- The `sqldemo` SQL analytics endpoint showed the completed request and both passing receipts after mirroring caught up.