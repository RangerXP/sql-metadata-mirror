# Phase 4 — Gated Governance Workflow (Operating Runbook)

**Status:** Design complete; live scenario runs not yet executed (see `docs/design-gap-analysis.md` G13/G14).
**Companion design doc:** `docs/Enercare-Demo-SemPy-Design-Guide.md` §5D.
**Prerequisite:** G10 steward pipeline fix (2026-08-08) already live; Fabric Mirroring new-table autosync already enabled.

This runbook walks each of the 4 gated-change demo scenarios end-to-end using the notebooks that exist **today**. Until `nb_11_gated_governance_sync` (Milestone P4-4) is built, the "apply on approve" step is done manually per scenario, using the exact SQL/PySpark shown below. Once `nb_11` exists, steps 3–4 in each scenario collapse into a single automated notebook run.

---

## 0. One-time setup

1. Apply the gating schema to `sub2` SQL (`sqldemo` source):
   ```sql
   :r sql/09_gated_governance_requests_schema.sql
   ```
2. Seed the 4 demo scenarios (idempotent — deletes/re-inserts by `request_id`):
   ```sql
   :r sql/10_seed_gated_governance_scenarios.sql
   ```
3. Confirm Fabric Mirroring picks up the new `dbo.governance_change_requests` table (schema autosync). Wait for mirror status `Running` on the new table in the Fabric Mirrored Database item.
4. Run `nb_07a_ingest_customer_files` once to pull `governance_change_requests` into `lh_metadata.metadata.governance_change_requests`. Confirm row count = 4, all `status='PendingApproval'`.

---

## 1. Scenario walkthroughs

Each scenario follows the same 4-step shape:

1. **Show the request** — query `governance_change_requests` filtered to the scenario's `request_id`, narrate `change_summary` and `proposed_payload`.
2. **Approve (or reject) it** — run the `UPDATE` against `sub2` SQL.
3. **Apply it** — run the manual apply step (PySpark, in the relevant notebook) that mutates the real governed object.
4. **Prove it propagated** — re-run `nb_04_sempy_writeback` → `nb_05_push_qa_verified_answers` → `nb_10_purview_stewardship_ai` and show the scorecard still returns 0 `ACTION_REQUIRED`.

### Scenario 1 — KPI Approval (`GCR-KPI-001`, `SLA_BRCH_RATE` v1 → v2)

**Requester:** Ranbir Singh. **Approver:** Ci Zhu.

1. Show the request:
   ```sql
   SELECT request_id, target_object_label, change_summary, proposed_payload, status
   FROM dbo.governance_change_requests WHERE request_id = 'GCR-KPI-001';
   ```
2. Approve:
   ```sql
   UPDATE dbo.governance_change_requests
   SET status = 'Approved', approver_upn = 'Ci.Zhu@enercare.ca', approved_at = SYSUTCDATETIME()
   WHERE request_id = 'GCR-KPI-001';
   ```
3. Apply (run in `nb_04a_extend_metadata_schema` or a scratch cell against `lh_metadata`):
   ```python
   spark.sql(f"""
     UPDATE {METADATA_LAKEHOUSE}.kpi_metadata
     SET Version = 2,
         PreviousFormula = Formula,
         CertifiedBy = 'Ci.Zhu@enercare.ca',
         CertifiedDate = current_date(),
         WarningThreshold = 0.08,
         CriticalThreshold = 0.12,
         IsCertified = 1
     WHERE KPICode = 'SLA_BRCH_RATE'
   """)
   ```
   Then, back in SQL: `UPDATE dbo.governance_change_requests SET status='Applied', applied_at=SYSUTCDATETIME() WHERE request_id='GCR-KPI-001';`
4. Prove: re-run `nb_04_sempy_writeback` (annotates the updated KPI certification onto the semantic model), then `nb_10_purview_stewardship_ai` and confirm `phase_08_stewardship` is still `0,PASS`.

### Scenario 2 — Verified Answer Certification (`GCR-VA-001`)

**Requester:** Rupal Solanki. **Approver:** Ci Zhu.

1. Show the request (same query pattern, `request_id = 'GCR-VA-001'`).
2. Approve (same `UPDATE` pattern, `approver_upn='Ci.Zhu@enercare.ca'`).
3. Apply — insert into `ai_metadata` (first run Milestone P4-2's `ALTER TABLE` to add `IsCertified`/`CertifiedBy`/`CertifiedDate` if not already present):
   ```python
   from pyspark.sql import Row
   row = Row(
       RecordID=<next_id>, ModelName="BrookfieldEnercare", RecordType="verified_answer",
       TriggerText="What is our SLA credit policy for a no-heat call during heating season?",
       ResponseText="Total Home Protection Plan customers are entitled to a daily pro-rated rental credit "
                    "for every day past a 24-hour no-heat SLA breach during heating season, plus a full-month "
                    "courtesy credit on final resolution.",
       LinkedKPICode="SLA_BRCH_RATE", IsDraft=0, IsCertified=1,
       CertifiedBy="Ci.Zhu@enercare.ca", CertifiedDate=date.today(), CreatedDate=date.today(),
   )
   spark.createDataFrame([row], schema=AI_METADATA_SCHEMA).write.format("delta").mode("append") \
       .saveAsTable(f"{METADATA_LAKEHOUSE}.ai_metadata")
   ```
   Then stamp `GCR-VA-001` as `Applied` in SQL.
4. Prove: re-run `nb_05_push_qa_verified_answers` and confirm the new verified answer publishes to the Data Agent surface; re-run `nb_10_purview_stewardship_ai` phase_10 check.

### Scenario 3 — CDE Classification (`GCR-CDE-001`, new `CDE-COMPLAINTREF`)

**Requester:** Shruthi Srinivas. **Approver:** Ci Zhu.

1. Show the request (`request_id = 'GCR-CDE-001'`) — note `target_object_id IS NULL` because this creates a **new** CDE.
2. Approve (same pattern).
3. Apply — insert the new row directly into `sub2.dbo.governance_cdes` (this is a SQL-side governed table, mirrored automatically):
   ```sql
   INSERT INTO dbo.governance_cdes
       (cde_id, cde_name, expected_data_type, business_definition, owner_role, owner_upn, status,
        parent_glossary_term, bound_columns, classification_approved_by, classification_approved_at)
   VALUES
       ('CDE-COMPLAINTREF', 'Complaint Reference', 'text',
        'Unique reference for a logged customer complaint; auto-generates a regulator_case_ref when severity/repeat criteria mark it RegulatorReportable under OEB rules.',
        'Data Steward', 'Shruthi.Srinivas@enercare.ca', 'Highly Confidential',
        'GT-COMPLAINT', 'dbo.customer_complaints.complaint_ref;dbo.customer_complaints.regulator_case_ref',
        'Ci.Zhu@enercare.ca', SYSUTCDATETIME());

   UPDATE dbo.governance_change_requests
   SET status='Applied', applied_at=SYSUTCDATETIME() WHERE request_id='GCR-CDE-001';
   ```
   Wait for mirror sync, then re-run `nb_07a_ingest_customer_files` to bring the new CDE into `lh_metadata.metadata.governance_cdes`.
4. Prove: re-run `nb_08_purview_glossary_cde` to publish the new CDE and its Highly Confidential classification to Purview; re-run `nb_10_purview_stewardship_ai` phase_09_controls check.

### Scenario 4 — Glossary Term Definition (`GCR-GT-001`, publish `GT-SLA`)

**Requester:** Victoria Tan. **Approver:** Ci Zhu.

1. Show the request (`request_id = 'GCR-GT-001'`) — note this formally registers a term that was previously only referenced narratively in `docs/purview-maria-north-star-scenario.md`.
2. Approve (same pattern).
3. Apply — insert into `sub2.dbo.governance_glossary_terms`:
   ```sql
   INSERT INTO dbo.governance_glossary_terms
       (term_code, term_name, parent_term_code, domain_id, owner_upn, additional_owners_upn,
        definition, status, is_cde, industry_origin, resources, bound_assets, approved_by, approved_at)
   VALUES
       ('GT-SLA', 'Service Level Agreement', NULL, 'DOM-SVCDEL', 'ranbir.singh@enercare.ca', 'Ci.Zhu@enercare.ca',
        'Committed service response window by request type and season (e.g., 24-hour no-heat SLA during heating season) with an associated pro-rated daily credit remedy on breach, per the Total Home Protection Plan contract terms.',
        'Published', 0, 'Service Industry', 'internal://sla/policy', 'dbo.contracts;dbo.service_requests',
        'Ci.Zhu@enercare.ca', SYSUTCDATETIME());

   UPDATE dbo.governance_change_requests
   SET status='Applied', applied_at=SYSUTCDATETIME() WHERE request_id='GCR-GT-001';
   ```
   *(Column names above assume `governance_glossary_terms` matches the shape seeded in `sql/07_seed_purview_metadata.sql`; confirm exact column list with `sp_help` before running live.)*
4. Prove: re-run `nb_08_purview_glossary_cde` to publish `GT-SLA` to the Purview glossary; re-run `nb_10_purview_stewardship_ai` phase_08 check.

---

## 2. Closure checklist (Milestone P4-5)

- [ ] All 4 `governance_change_requests` rows show `status='Applied'` with non-null `applied_at`.
- [ ] `nb_10_purview_stewardship_ai` re-run shows 0 `ACTION_REQUIRED` across all three phases after each apply.
- [ ] Ci Zhu's Act 3 audit answer (`docs/purview-maria-north-star-scenario.md` §3.7) can be demonstrated live against the newly-certified objects.
- [ ] Update `docs/design-gap-analysis.md` G14-4..G14-8 rows to 🟢 Done as each scenario is proven live.

## 3. Future automation (Milestone P4-4)

Once `nb_11_gated_governance_sync` exists, steps 3 in each scenario above (the manual PySpark/SQL apply) are replaced by a single scheduled/triggered run of `nb_11` that:
1. Reads `lh_metadata.metadata.governance_change_requests` where `status='Approved' AND applied_at IS NULL`.
2. Dispatches by `request_type` to the appropriate target-table mutation (as shown per-scenario above).
3. Stamps `status='Applied'`, `applied_at=now()`.
4. Triggers `nb_04_sempy_writeback` → `nb_05_push_qa_verified_answers` → `nb_07_publish_to_purview`/`nb_08`/`nb_09` → `nb_10_purview_stewardship_ai` in sequence, closing the loop automatically.
