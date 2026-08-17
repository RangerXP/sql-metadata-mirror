/*
================================================================================
Purpose:
  G19-6 (part 2 gate) -- create the Approved request that
  09_reconcile_semantic_model reconciles, same division of labor as its
  earlier phases (creates the Approved DataProductPublish request / reconciles
  it into the semantic model). Gated on ONTOMAP-TECHUTIL-001 (the ontology
  mapping from sql/07_governance_gates/27_g19_g18_cde_ontology_mapping.sql) already being Completed -- the semantic promotion is
  not allowed to run ahead of the ontology mapping that justifies it.

Idempotent: safe to re-run.
================================================================================
*/

SET NOCOUNT ON;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = 'ONTOMAP-TECHUTIL-001' AND current_status = 'Completed')
BEGIN
    PRINT 'ONTOMAP-TECHUTIL-001 is not yet Completed -- run sql/07_governance_gates/27_g19_g18_cde_ontology_mapping.sql first. Aborting.';
    RETURN;
END
GO

DECLARE @request_id       VARCHAR(64)   = 'SEMPROMO-TECHUTIL-001';
DECLARE @object_id        VARCHAR(256)  = 'dbo.vw_technician_utilization_summary';
DECLARE @key_result_id    VARCHAR(64)   = 'KR-TECH-UTIL';
DECLARE @requested_by     VARCHAR(255)  = 'shruthi.srinivas@enercare.ca';
DECLARE @approved_by      VARCHAR(255)  = 'Ci.Zhu@enercare.ca';
DECLARE @proposed_payload NVARCHAR(MAX) = (
    SELECT @object_id AS sourceObjectId, @key_result_id AS keyResultId,
           'fct_service_request' AS targetTable, 'TechnicianUtilizationRate' AS targetMeasure,
           'ONTOMAP-TECHUTIL-001' AS ontologyMappingRequestId
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
);

IF NOT EXISTS (SELECT 1 FROM dbo.governance_requests WHERE request_id = @request_id)
INSERT INTO dbo.governance_requests (
    request_id, request_type, authority, target_system, target_object_type,
    target_object_id, target_object_label, requested_by, requested_at,
    decided_by, decided_at, current_status, proposed_payload
)
VALUES (
    @request_id, 'SemanticModelPromotion', 'SQL', 'Fabric', 'SemanticModel',
    @object_id, 'Technician Utilization Rate measure promotion (BrookfieldEnercare)',
    @requested_by, SYSUTCDATETIME(), @approved_by, SYSUTCDATETIME(), 'Approved', @proposed_payload
);

PRINT 'SEMPROMO-TECHUTIL-001 seeded as Approved: ' + CAST(@@ROWCOUNT AS VARCHAR(10)) + ' row(s). Ready for 09_reconcile_semantic_model.';
GO
