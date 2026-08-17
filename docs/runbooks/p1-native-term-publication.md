# P1 Native Term Publication Runbook

**Scenario:** `GT-SLA` (`b3b54277-3b36-47d8-831c-a2b9a5f02634`)

**Governance domain:** Service Delivery (`9d82a6da-eed1-4dae-a036-84c1dcc65337`)

**Control boundary:** Purview approves publication. Azure SQL stores normalized evidence. Fabric does not approve the request.

## 1. Apply the additive ledger

Run `sql/07_governance_gates/13_closed_loop_governance_ledger.sql` against `sqldemo` on `sqlserver-sk2wus3.database.windows.net`.

Expected result:

```text
Native-first closed-loop governance ledger is ready.
```

The script is idempotent and does not alter `dbo.governance_change_requests`.

## 2. Configure the native workflow

1. Open Microsoft Purview and select **Unified Catalog**.
2. Under **Process automation**, select **Workflows**, then **New**.
3. Set **Workflow category** to **Catalog curation**.
4. Set **Workflow type** to **Term publish**.
5. Name the workflow `Enercare Service Delivery Term Publication`.
6. Configure **Start and wait for an approval** with **Pending on any** and assign a real approver who is not the requester.
7. Configure the approval condition so approval follows the positive branch and rejection follows the negative branch.
8. Select **Set scope**, choose only the **Service Delivery** governance domain, and save.

Do not use the classic Atlas glossary workflow. Do not enable public SQL or Purview access.

## 3. Capture the safe baseline

Run `nb_12_purview_workflow_sync` with its committed defaults:

```python
DEMO_MODE = True
WORKFLOW_CONFIGURED = False
RUN_CORRELATION_ID = ""
```

Expected result: the notebook reads `GT-SLA`, prints its supported Unified Catalog snapshot and hash, and writes nothing to SQL.

The current baseline term is already `Published`; that state predates this workflow test and is not approval evidence.

## 4. Start one controlled publication revision

1. In Unified Catalog, open the Service Delivery domain and select `Service Level Agreement`.
2. Select **Unpublish**.
3. Edit the definition with the approved P1 test revision and save it as `Draft`.
4. In `nb_12_purview_workflow_sync`, set:

   ```python
   DEMO_MODE = False
   WORKFLOW_CONFIGURED = True
   RUN_CORRELATION_ID = "GT-SLA-P1-A"
   ```

5. Run the notebook while the term is still `Draft`.

Expected result: one `Draft` request projection, event, and governed object version are written idempotently. Keep the same correlation ID for the rest of this test.

## 5. Execute the human approval

1. In Unified Catalog, submit `GT-SLA` for publication.
2. In **Requests and approvals**, confirm the request is pending.
3. Sign in as the assigned approver and approve it.
4. Confirm `GT-SLA` now shows `Published` in Unified Catalog.
5. Rerun `nb_12_purview_workflow_sync` with the same settings and correlation ID.

When prompted by Cell 3, open the device-login URL in an InPrivate browser and sign in
with Sean's account in tenant `b7e47691-9726-4f67-a302-e567815f3522`. The notebook uses
interactive MSAL authentication because Fabric NotebookUtils does not support a Purview
token audience.

Expected result: the SQL request advances to `Approved`, a publication observation event is appended once, and the Purview publication read-back receipt is `Passed`. Repeating the notebook produces no duplicate event or version.

## 6. Verify the durable evidence

```sql
SELECT request_id, authority, authority_request_id, target_object_label,
       current_status, requested_by, decided_by, decided_at, last_observed_at
FROM dbo.governance_requests
WHERE target_object_id = 'b3b54277-3b36-47d8-831c-a2b9a5f02634';

SELECT event_type, event_status, source_event_id, actor_id, occurred_at, observed_at
FROM dbo.governance_events
WHERE request_id = '<request_id-from-previous-query>'
ORDER BY event_id;

SELECT lifecycle_status, definition_hash, effective_at, observed_at
FROM dbo.governed_object_versions
WHERE request_id = '<request_id-from-previous-query>'
ORDER BY version_id;

SELECT target_system, receipt_type, expected_hash, observed_hash,
       validation_status, observed_at
FROM dbo.governance_target_receipts
WHERE request_id = '<request_id-from-previous-query>';
```

Required evidence:

- One Draft observation and one Published observation for the same local correlation.
- One immutable version per distinct canonical term hash.
- `PublicationReadback` has matching expected and observed hashes and status `Passed`.
- Governed-version hashes cover the full snapshot, including lifecycle status. Publication
   receipt hashes exclude `status` so the expected Draft content can be compared with the
   Published read-back without treating the approved lifecycle transition as content drift.
- `authority_request_id`, `decided_by`, and `decided_at` remain `NULL` because the supported Unified Catalog API does not expose those workflow fields.

## 7. Completion boundary

This proves the Purview approval-to-SQL half of Loop A. The request must remain `Approved`; do not mark it `Completed` until the semantic-model mapping is applied, read back, and recorded as a second passing target receipt.

After repo changes are pushed, refresh Fabric Source Control and update the workspace before running the notebook. Do not mix unresolved Fabric UI edits with local git edits.