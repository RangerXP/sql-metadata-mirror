/*
================================================================================
Purpose:
  Seed the Purview-extension tables with synthetic data sized to fire Microsoft
  Purview classifiers and populate the 3-domain / 3-data-product MVP.

Coverage:
  - DOB, SIN partial, owner_email, marketing_consent backfilled on dbo.customers
  - Lat/long, service_zone_code backfilled on dbo.service_accounts
  - Bank routing / PAN last 4 backfilled on dbo.billing_transactions
  - 15 employees including 6 technicians (matches existing service_requests.technician_id range)
  - 8 service zones, Ontario-focused
    - 124 customer consent rows, including Maria Castellanos's explicit consent state
    - 19 complaints (3 regulator-reportable), including Maria Castellanos's SLA case
  - data_owners_directory pre-populated for all 13 source tables
    - 204 audit access rows over the last 30 days, including Tom Nguyen's Maria access trail

Notes:
  - SIN columns (dbo.employees.sin_full and dbo.customers.sin_last_4) are left
    NULL by this script and populated separately by the Python notebook
    nb_05a_publish_synthetic_data_to_sql using the Luhn-valid generator in
    tools/sin_luhn_generator.py. This is Layer 1 of the SIN classifier backstop.
    See docs/purview-sin-classifier-backstop.md for the full strategy.
  - All values here are synthetic and do not correspond to real persons.
  - Update value ranges if your customer count differs.
================================================================================
*/

SET NOCOUNT ON;
GO

/* ------------------------------------------------------------------------------
   1. Service zones (Ontario hierarchy)
------------------------------------------------------------------------------ */

DELETE FROM dbo.service_zones;
GO

INSERT INTO dbo.service_zones (zone_code, zone_name, parent_zone_code, province, zone_manager_upn, sla_target_minutes) VALUES
('CA-ON',       'Ontario',                NULL,    'ON', 'ranbir.singh@enercare.ca', NULL),
('CA-ON-GTA',   'Greater Toronto Area',   'CA-ON', 'ON', 'ranbir.singh@enercare.ca', 120),
('CA-ON-GTA-N', 'GTA North',              'CA-ON-GTA', 'ON', 'mhuang@enercare.ca', 90),
('CA-ON-GTA-S', 'GTA South',              'CA-ON-GTA', 'ON', 'mhuang@enercare.ca', 90),
('CA-ON-GTA-E', 'GTA East',               'CA-ON-GTA', 'ON', 'rpatel@enercare.ca', 90),
('CA-ON-GTA-W', 'GTA West',               'CA-ON-GTA', 'ON', 'rpatel@enercare.ca', 90),
('CA-ON-OTT',   'Ottawa Region',          'CA-ON', 'ON', 'Rupal.Solanki@enercare.ca', 150),
('CA-ON-SWO',   'Southwestern Ontario',   'CA-ON', 'ON', 'Rupal.Solanki@enercare.ca', 180);
GO

/* ------------------------------------------------------------------------------
   2. Employees (15 rows; 6 technicians with technician_id 101-106)
------------------------------------------------------------------------------ */

DELETE FROM dbo.employees;
GO

-- Enercare leadership in scope for this demo (from Brian Lung's correspondence
-- and the 2026-05-20 Deeper Dive Data Mirroring and Governance meeting).
-- sin_full is left NULL and populated by the Python Luhn-valid generator in
-- nb_05a (Layer 1 of the SIN backstop strategy).
--
-- Note: Christopher Dingle (VP Data Analytics & Governance at Enercare) is
-- intentionally out of scope for this demo. His governance authoring duties
-- (glossary, CDE catalog, label policy, tenant-level Purview admin) are
-- represented in the demo by Ci Zhu (Senior Manager, Data Strategy & Analytics).
INSERT INTO dbo.employees (employee_id, upn, first_name, last_name, email, phone, role, department, manager_employee_id, hire_date, sin_full, date_of_birth, home_postal_code, is_active) VALUES
(1, 'Victoria.Tan@enercare.ca',     'Victoria', 'Tan',      'Victoria.Tan@enercare.ca',     '+1-416-555-0101', 'Chief Customer Officer',                   'Executive',   NULL, '2016-04-01', NULL, '1976-04-22', 'M5V', 1),
(2, 'ranbir.singh@enercare.ca',     'Ranbir',   'Singh',    'ranbir.singh@enercare.ca',     '+1-416-555-0102', 'Enercare Leadership — Data Plane',         'Engineering', 1,    '2020-02-15', NULL, '1981-03-22', 'M4Y', 1),
(3, 'Ci.Zhu@enercare.ca',           'Ci',       'Zhu',      'Ci.Zhu@enercare.ca',           '+1-437-860-6862', 'Senior Manager Data Strategy & Analytics', 'Data Office', 1,    '2021-06-07', NULL, '1985-11-04', 'L3R', 1),
(4, 'Rupal.Solanki@enercare.ca',    'Rupal',    'Solanki',  'Rupal.Solanki@enercare.ca',    '+1-416-555-0104', 'Data & Analytics Lead',                    'Data Office', 3,    '2020-09-21', NULL, '1979-06-30', 'M4W', 1),
(5, 'Shruthi.Srinivas@enercare.ca', 'Shruthi',  'Srinivas', 'Shruthi.Srinivas@enercare.ca', '+1-416-555-0105', 'Data & Analytics Lead',                    'Data Office', 3,    '2018-01-10', NULL, '1971-09-15', 'L4C', 1);
GO

-- Synthetic operational employees (technicians, supervisors) — these remain
-- fictional Enercare HR records as scan targets. sin_full populated by nb_05a.
-- manager_employee_id rolls up to Ranbir Singh (employee_id=2) for the field-ops chain.
INSERT INTO dbo.employees (employee_id, upn, first_name, last_name, email, phone, role, department, manager_employee_id, hire_date, sin_full, date_of_birth, home_postal_code, is_active) VALUES
(101, 'tnguyen@enercare.ca',    'Tom',     'Nguyen',   'tnguyen@enercare.ca',    '+1-416-555-1101', 'Service Technician', 'Field Ops', 2, '2022-03-14', NULL, '1990-04-12', 'L6T', 1),
(102, 'smehta@enercare.ca',     'Sneha',   'Mehta',    'smehta@enercare.ca',     '+1-416-555-1102', 'Service Technician', 'Field Ops', 2, '2021-11-01', NULL, '1988-07-19', 'L5N', 1),
(103, 'bfontaine@enercare.ca',  'Benoit',  'Fontaine', 'bfontaine@enercare.ca',  '+1-416-555-1103', 'Service Technician', 'Field Ops', 2, '2020-05-08', NULL, '1985-01-25', 'K2H', 1),
(104, 'kahmed@enercare.ca',     'Karim',   'Ahmed',    'kahmed@enercare.ca',     '+1-416-555-1104', 'Service Technician', 'Field Ops', 2, '2023-02-20', NULL, '1992-12-03', 'L1S', 1),
(105, 'mhuang@enercare.ca',     'Mei',     'Huang',    'mhuang@enercare.ca',     '+1-416-555-1105', 'Field Supervisor',   'Field Ops', 2, '2019-08-18', NULL, '1983-05-21', 'L4G', 1),
(106, 'rpatel@enercare.ca',     'Rashmi',  'Patel',    'rpatel@enercare.ca',     '+1-416-555-1106', 'Field Supervisor',   'Field Ops', 2, '2019-10-04', NULL, '1982-09-08', 'L8N', 1);
GO

/* ------------------------------------------------------------------------------
   2A. Maria Castellanos source-story rows across the authoritative SQL model
------------------------------------------------------------------------------ */

DELETE FROM dbo.billing_transactions WHERE transaction_id IN (183746223, 183746224);
DELETE FROM dbo.service_requests WHERE request_id = 2026051142;
DELETE FROM dbo.contracts WHERE contract_id = 183746222;
DELETE FROM dbo.equipment_registry WHERE equipment_id = 183746221 OR serial_number = 'LX2020-MARIA98V';
DELETE FROM dbo.service_accounts WHERE service_account_id = 183746220 OR account_number = 'EC18374622-SVC';
DELETE FROM dbo.customers WHERE customer_id = 18374622 OR account_number = 'EC18374622';
GO

INSERT INTO dbo.customers
    (customer_id, account_number, first_name, last_name, email, phone, customer_type, status,
     city, province, postal_code, created_date, date_of_birth, sin_last_4, owner_email, marketing_consent)
VALUES
(18374622, 'EC18374622', 'Maria', 'Castellanos', 'maria.castellanos@example.ca', '905-555-4622',
 'Residential', 'Active', 'Markham', 'ON', 'L4G 2H9', '2020-10-17', '1983-07-09', NULL,
 'Rupal.Solanki@enercare.ca', 1);
GO

INSERT INTO dbo.service_accounts
    (service_account_id, customer_id, account_number, utility_type, rate_class, distributor, status,
     service_address, city, postal_code, opened_date, latitude, longitude, service_zone_code)
VALUES
(183746220, 18374622, 'EC18374622-SVC', 'Natural Gas', 'Residential', 'Enbridge Gas', 'Active',
 '47 Birch Drive, Unit 8', 'Markham', 'L4G 2H9', '2020-10-17', 43.879200, -79.263600, 'CA-ON-GTA-N');
GO

INSERT INTO dbo.equipment_registry
    (equipment_id, service_account_id, equipment_type, make, model, serial_number, ownership_type,
     fuel_type, install_date, warranty_expiry, status)
VALUES
(183746221, 183746220, 'Furnace', 'Lennox', 'SLP98V', 'LX2020-MARIA98V', 'Rental',
 'Natural Gas', '2020-10-17', '2030-10-17', 'Active');
GO

INSERT INTO dbo.contracts
    (contract_id, service_account_id, product_id, contract_status, start_date, end_date,
     monthly_amount, auto_renew, cancellation_date, cancellation_reason)
VALUES
(183746222, 183746220, 4, 'Active', '2020-10-17', NULL, 89.95, 1, NULL, NULL);
GO

INSERT INTO dbo.service_requests
    (request_id, service_account_id, equipment_id, request_type, priority, status, description,
     created_date, scheduled_date, completed_date, technician_id, no_show_reason_code, resolution_notes)
VALUES
(2026051142, 183746220, 183746221, 'Emergency Repair', 'Emergency', 'InProgress',
 'NoHeat furnace case opened through portal; scheduled pending tech after missed 24-hour SLA.',
 '2026-06-13', '2026-06-14', NULL, 105, 'DISPATCH_NO_REASSIGN',
 'Scheduled - Pending Tech; GTA North dispatch did not reassign after the SLA breach.');
GO

INSERT INTO dbo.billing_transactions
    (transaction_id, contract_id, service_account_id, transaction_type, transaction_date, due_date,
     amount, tax_amount, payment_method, status, invoice_number, bank_routing_last_4, card_pan_last_4)
VALUES
(183746223, 183746222, 183746220, 'MonthlyCharge', '2026-06-15', '2026-06-30',
 89.95, 11.69, 'CreditCard', 'Posted', 'INV-MARIA-202606', '1837', '4622'),
(183746224, 183746222, 183746220, 'Credit', '2026-06-17', NULL,
 -14.99, 0.00, 'CreditCard', 'Posted', 'CR-MARIA-SLA-202606', '1837', '4622');
GO

/* ------------------------------------------------------------------------------
   3. Backfill dbo.customers — DOB, SIN last 4, owner_email, marketing_consent
    Assumes customer_id range 1..50 plus Maria Castellanos at customer_id 18374622.
   Steward owner_email rotates across the three customer-ops stewards.
------------------------------------------------------------------------------ */

-- sin_last_4 is intentionally left NULL here; nb_05a populates it from the
-- last 4 digits of a Luhn-valid 9-digit SIN per the backstop strategy.
UPDATE dbo.customers
SET
    date_of_birth = DATEADD(DAY,
        -((ABS(CHECKSUM(NEWID())) % 14600) + 7300),  -- ages 20-60ish
        CAST(GETDATE() AS DATE)),
    owner_email = CASE customer_id % 3
        WHEN 0 THEN 'Rupal.Solanki@enercare.ca'
        WHEN 1 THEN 'Shruthi.Srinivas@enercare.ca'
        ELSE        'Ci.Zhu@enercare.ca'
    END,
    marketing_consent = CASE WHEN customer_id % 4 = 0 THEN 0 ELSE 1 END
WHERE date_of_birth IS NULL;
GO

/* ------------------------------------------------------------------------------
   4. Backfill dbo.service_accounts — GPS (within GTA bounding box) + zone
   GTA bounding box approx: lat 43.4-44.1, long -79.8 to -78.9
------------------------------------------------------------------------------ */

UPDATE dbo.service_accounts
SET
    latitude  = 43.4 + (ABS(CHECKSUM(NEWID())) % 700) / 1000.0,
    longitude = -79.8 + (ABS(CHECKSUM(NEWID())) % 900) / 1000.0,
    service_zone_code = CASE ABS(CHECKSUM(NEWID())) % 6
        WHEN 0 THEN 'CA-ON-GTA-N'
        WHEN 1 THEN 'CA-ON-GTA-S'
        WHEN 2 THEN 'CA-ON-GTA-E'
        WHEN 3 THEN 'CA-ON-GTA-W'
        WHEN 4 THEN 'CA-ON-OTT'
        ELSE        'CA-ON-SWO'
    END
WHERE latitude IS NULL;
GO

/* ------------------------------------------------------------------------------
   5. Backfill dbo.service_requests — no-show causality taxonomy
   Taxonomy: DISPATCH_NO_REASSIGN, CUSTOMER_NOT_HOME, TECH_CAPACITY_CONSTRAINT,
             WEATHER_DELAY, CAUSE_UNSPECIFIED, NOT_APPLICABLE
------------------------------------------------------------------------------ */

UPDATE dbo.service_requests
SET no_show_reason_code =
    CASE
        WHEN completed_date IS NOT NULL OR status IN ('Completed', 'Closed', 'Resolved', 'Cancelled')
            THEN 'NOT_APPLICABLE'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%DISPATCH%REASSIGN%'
             OR UPPER(COALESCE(resolution_notes, '')) LIKE '%DID NOT REASSIGN%'
            THEN 'DISPATCH_NO_REASSIGN'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%CUSTOMER NOT HOME%'
             OR UPPER(COALESCE(resolution_notes, '')) LIKE '%NO ANSWER AT DOOR%'
            THEN 'CUSTOMER_NOT_HOME'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%NO TECH%'
             OR UPPER(COALESCE(resolution_notes, '')) LIKE '%TECH UNAVAILABLE%'
             OR UPPER(COALESCE(resolution_notes, '')) LIKE '%CAPACITY%'
            THEN 'TECH_CAPACITY_CONSTRAINT'
        WHEN UPPER(COALESCE(resolution_notes, '')) LIKE '%WEATHER%'
             OR UPPER(COALESCE(resolution_notes, '')) LIKE '%STORM%'
            THEN 'WEATHER_DELAY'
        WHEN scheduled_date IS NOT NULL AND completed_date IS NULL
            THEN 'CAUSE_UNSPECIFIED'
        ELSE 'NOT_APPLICABLE'
    END
WHERE no_show_reason_code IS NULL;
GO

/* ------------------------------------------------------------------------------
   6. Backfill dbo.billing_transactions — payment partials
------------------------------------------------------------------------------ */

UPDATE dbo.billing_transactions
SET
    bank_routing_last_4 = RIGHT('0000' + CAST(ABS(CHECKSUM(NEWID())) % 10000 AS VARCHAR(4)), 4),
    card_pan_last_4     = RIGHT('0000' + CAST(ABS(CHECKSUM(NEWID())) % 10000 AS VARCHAR(4)), 4)
WHERE bank_routing_last_4 IS NULL
  AND payment_method IN ('CreditCard', 'BankACH', 'PreAuthDebit');
GO

/* ------------------------------------------------------------------------------
    7. customer_consents — ~120 rows (mix of consent types)
   Picks 30 customers, 4 consent types each, mixing granted/withdrawn.
------------------------------------------------------------------------------ */

DELETE FROM dbo.customer_consents;
GO

;WITH numbers AS (
    SELECT TOP (30) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
    FROM sys.objects
), consent_types AS (
    SELECT 1 AS k, 'Marketing-Email' AS t, 'CASL' AS lb UNION ALL
    SELECT 2,      'Marketing-SMS',         'CASL'        UNION ALL
    SELECT 3,      'Data-Sharing',          'PIPEDA'      UNION ALL
    SELECT 4,      'Retention',             'PIPEDA'
)
INSERT INTO dbo.customer_consents
    (consent_id, customer_id, consent_type, consent_status, legal_basis,
     granted_date, withdrawn_date, source_channel, captured_by_upn)
SELECT
    (n.n - 1) * 4 + ct.k                                         AS consent_id,
    n.n                                                          AS customer_id,
    ct.t                                                         AS consent_type,
    CASE WHEN (n.n + ct.k) % 5 = 0 THEN 'Withdrawn' ELSE 'Granted' END AS consent_status,
    ct.lb                                                        AS legal_basis,
    DATEADD(DAY, -((n.n * 7 + ct.k * 13) % 800), CAST(GETDATE() AS DATE)) AS granted_date,
    CASE WHEN (n.n + ct.k) % 5 = 0
         THEN DATEADD(DAY, -((n.n * 3 + ct.k * 5) % 200), CAST(GETDATE() AS DATE))
         ELSE NULL END                                           AS withdrawn_date,
    CASE (n.n + ct.k) % 4
        WHEN 0 THEN 'Web' WHEN 1 THEN 'CallCenter'
        WHEN 2 THEN 'Paper' ELSE 'AppPush'
    END                                                          AS source_channel,
    'Rupal.Solanki@enercare.ca'                                      AS captured_by_upn
FROM numbers n
CROSS JOIN consent_types ct;
GO

INSERT INTO dbo.customer_consents
    (consent_id, customer_id, consent_type, consent_status, legal_basis,
     granted_date, withdrawn_date, source_channel, captured_by_upn)
VALUES
(183746221, 18374622, 'Marketing-Email', 'Granted', 'CASL',   '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca'),
(183746222, 18374622, 'Marketing-SMS',   'Granted', 'CASL',   '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca'),
(183746223, 18374622, 'Data-Sharing',    'Granted', 'PIPEDA', '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca'),
(183746224, 18374622, 'Retention',       'Granted', 'PIPEDA', '2026-06-17', NULL, 'CallCenter', 'tnguyen@enercare.ca');
GO

/* ------------------------------------------------------------------------------
   7. customer_complaints — 18 rows, 3 regulator-reportable
------------------------------------------------------------------------------ */

DELETE FROM dbo.customer_complaints;
GO

INSERT INTO dbo.customer_complaints
    (complaint_id, customer_id, service_account_id, complaint_type, severity, opened_date, closed_date, status, assigned_to_upn, description, regulator_case_ref)
VALUES
( 1,  3, NULL, 'Billing',    'Medium',              '2026-04-12','2026-04-18','Resolved',  'Rupal.Solanki@enercare.ca',  'Duplicate billing on furnace rental for March cycle.',  NULL),
( 2,  5, NULL, 'AutoRenew',  'High',                '2026-03-22',NULL,        'In Review', 'Ci.Zhu@enercare.ca',      'Customer alleges auto-renewal not disclosed at sign-up.', NULL),
( 3,  9, NULL, 'Privacy',    'RegulatorReportable', '2026-05-04',NULL,        'Escalated', 'Victoria.Tan@enercare.ca', 'PIPEDA complaint: marketing email after withdrawn consent.', 'OPC-2026-0517'),
( 4, 11, NULL, 'Service',    'Low',                 '2026-05-09','2026-05-12','Resolved',  'Shruthi.Srinivas@enercare.ca', 'Technician arrival window missed by 90 minutes.', NULL),
( 5, 14, NULL, 'Billing',    'Medium',              '2026-04-30','2026-05-07','Resolved',  'Rupal.Solanki@enercare.ca',  'Tax calculation error on utility add-on.', NULL),
( 6, 17, NULL, 'Service',    'High',                '2026-05-15',NULL,        'In Progress','Shruthi.Srinivas@enercare.ca','Repeated water heater failure within 30 days.', NULL),
( 7, 20, NULL, 'AutoRenew',  'RegulatorReportable', '2026-03-08',NULL,        'Escalated', 'Ci.Zhu@enercare.ca',      'Ontario Consumer Protection: 90-day notice missed.', 'OCPB-2026-0210'),
( 8, 22, NULL, 'Other',      'Low',                 '2026-05-25','2026-05-26','Closed',    'Rupal.Solanki@enercare.ca',  'Online portal login issue (resolved by support).', NULL),
( 9, 25, NULL, 'Billing',    'Medium',              '2026-05-01','2026-05-08','Resolved',  'Rupal.Solanki@enercare.ca',  'Promotional discount not applied for first 3 months.', NULL),
(10, 27, NULL, 'Privacy',    'High',                '2026-05-19',NULL,        'In Review', 'Victoria.Tan@enercare.ca', 'Customer data shared with third party without consent.', NULL),
(11, 30, NULL, 'Service',    'Medium',              '2026-04-28','2026-05-04','Resolved',  'Shruthi.Srinivas@enercare.ca', 'Diagnostic charge disputed.', NULL),
(12, 32, NULL, 'Billing',    'Low',                 '2026-05-12','2026-05-14','Resolved',  'Rupal.Solanki@enercare.ca',  'Statement format unclear.', NULL),
(13, 35, NULL, 'AutoRenew',  'Medium',              '2026-04-19','2026-04-26','Resolved',  'Ci.Zhu@enercare.ca',      'Renewal pricing higher than expected.', NULL),
(14, 38, NULL, 'Service',    'High',                '2026-05-22',NULL,        'In Progress','Shruthi.Srinivas@enercare.ca','Repeat HVAC failure during heat advisory.', NULL),
(15, 41, NULL, 'Privacy',    'RegulatorReportable', '2026-05-30',NULL,        'In Review', 'Victoria.Tan@enercare.ca', 'Customer info incorrect after data update.', 'OPC-2026-0601'),
(16, 44, NULL, 'Billing',    'Medium',              '2026-05-06','2026-05-13','Resolved',  'Rupal.Solanki@enercare.ca',  'Late fee dispute, system-generated in error.', NULL),
(17, 46, NULL, 'Service',    'Low',                 '2026-05-18','2026-05-21','Resolved',  'Shruthi.Srinivas@enercare.ca', 'Technician did not provide service summary.', NULL),
(18, 49, NULL, 'Other',      'Medium',              '2026-05-24',NULL,        'In Review', 'Rupal.Solanki@enercare.ca',  'Equipment removal request not actioned.', NULL);
GO

INSERT INTO dbo.customer_complaints
    (complaint_id, customer_id, service_account_id, complaint_type, severity, opened_date,
     closed_date, status, assigned_to_upn, description, regulator_case_ref)
VALUES
(18374622, 18374622, 183746220, 'Service', 'High', '2026-06-17', NULL, 'Escalated',
 'tnguyen@enercare.ca',
 'NoHeat furnace request missed the 24-hour SLA in GTA North; customer was still billed monthly rental charge.',
 NULL);
GO

/* ------------------------------------------------------------------------------
   8. data_owners_directory — every source table mapped to owner+steward+domain
------------------------------------------------------------------------------ */

DELETE FROM dbo.data_owners_directory;
GO

INSERT INTO dbo.data_owners_directory
    (owner_id, object_schema, object_name, object_type, data_owner_upn, data_steward_upn, domain_code, last_reviewed_date)
VALUES
( 1, 'dbo', 'customers',             'Table', 'Victoria.Tan@enercare.ca', 'Rupal.Solanki@enercare.ca',     'DOM-CUSTOPS', '2026-05-20'),
( 2, 'dbo', 'service_accounts',      'Table', 'Victoria.Tan@enercare.ca', 'Rupal.Solanki@enercare.ca',     'DOM-CUSTOPS', '2026-05-20'),
( 3, 'dbo', 'customer_consents',     'Table', 'Victoria.Tan@enercare.ca', 'Victoria.Tan@enercare.ca','DOM-CUSTOPS', '2026-05-20'),
( 4, 'dbo', 'customer_complaints',   'Table', 'Victoria.Tan@enercare.ca', 'Rupal.Solanki@enercare.ca',     'DOM-CUSTOPS', '2026-05-20'),
( 5, 'dbo', 'employees',             'Table', 'Victoria.Tan@enercare.ca', 'Victoria.Tan@enercare.ca','DOM-CUSTOPS', '2026-05-20'),

( 6, 'dbo', 'equipment_registry',    'Table', 'ranbir.singh@enercare.ca',       'Shruthi.Srinivas@enercare.ca',  'DOM-SVCDEL',  '2026-05-20'),
( 7, 'dbo', 'service_requests',      'Table', 'ranbir.singh@enercare.ca',       'Shruthi.Srinivas@enercare.ca',  'DOM-SVCDEL',  '2026-05-20'),
( 8, 'dbo', 'service_zones',         'Table', 'ranbir.singh@enercare.ca',       'Shruthi.Srinivas@enercare.ca',  'DOM-SVCDEL',  '2026-05-20'),

( 9, 'dbo', 'products',              'Table', 'Ci.Zhu@enercare.ca',             'Ci.Zhu@enercare.ca',            'DOM-REVCON',  '2026-05-20'),
(10, 'dbo', 'contracts',             'Table', 'Ci.Zhu@enercare.ca',             'Ci.Zhu@enercare.ca',            'DOM-REVCON',  '2026-05-20'),
(11, 'dbo', 'billing_transactions',  'Table', 'Ci.Zhu@enercare.ca',             'Ci.Zhu@enercare.ca',            'DOM-REVCON',  '2026-05-20'),

(12, 'dbo', 'data_owners_directory', 'Table', 'Ci.Zhu@enercare.ca',       'Ci.Zhu@enercare.ca',       'DOM-CUSTOPS', '2026-05-20'),
(13, 'dbo', 'audit_data_access',     'Table', 'Ci.Zhu@enercare.ca',       'Ci.Zhu@enercare.ca',       'DOM-CUSTOPS', '2026-05-20');
GO

/* ------------------------------------------------------------------------------
   9. audit_data_access — 200 rows in the last 30 days
------------------------------------------------------------------------------ */

DELETE FROM dbo.audit_data_access;
GO

;WITH numbers AS (
    SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
    FROM sys.objects a CROSS JOIN sys.objects b
), actors AS (
    SELECT 1 AS k, 'Rupal.Solanki@enercare.ca'  AS upn, 'Data Steward'        AS role UNION ALL
    SELECT 2,      'Shruthi.Srinivas@enercare.ca',         'Data Steward'                UNION ALL
    SELECT 3,      'Ci.Zhu@enercare.ca',              'Data Steward'                UNION ALL
    SELECT 4,      'Victoria.Tan@enercare.ca',         'Privacy Officer'             UNION ALL
    SELECT 5,      'ranbir.singh@enercare.ca',           'Engineer'                    UNION ALL
    SELECT 6,      'ajay@enercare.demo',             'Engineer'                    UNION ALL
    SELECT 7,      'Victoria.Tan@enercare.ca',          'Executive'
), objects_ AS (
    SELECT 1 AS k, 'dbo' AS sch, 'customers'             AS obj, 1 AS pii UNION ALL
    SELECT 2,      'dbo',        'service_accounts',           1          UNION ALL
    SELECT 3,      'dbo',        'billing_transactions',       1          UNION ALL
    SELECT 4,      'dbo',        'customer_consents',          1          UNION ALL
    SELECT 5,      'dbo',        'service_requests',           0          UNION ALL
    SELECT 6,      'dbo',        'contracts',                  0          UNION ALL
    SELECT 7,      'dbo',        'employees',                  1
), purposes AS (
    SELECT 1 AS k, 'BillingSupport'  AS p UNION ALL
    SELECT 2,      'RegulatorReport'      UNION ALL
    SELECT 3,      'MarketingCampaign'    UNION ALL
    SELECT 4,      'DataScience'          UNION ALL
    SELECT 5,      'CustomerService'
)
INSERT INTO dbo.audit_data_access
    (audit_id, accessed_at, accessor_upn, accessor_role, object_schema, object_name, operation, rows_affected, purpose_of_use, contains_pii)
SELECT
    n.n,
    DATEADD(MINUTE, -((n.n * 17) % 43200), GETDATE()),    -- last 30 days
    a.upn,
    a.role,
    o.sch,
    o.obj,
    CASE n.n % 10 WHEN 0 THEN 'EXPORT' WHEN 5 THEN 'MASK' ELSE 'SELECT' END,
    (n.n * 11) % 500 + 1,
    p.p,
    o.pii
FROM numbers n
JOIN actors a   ON a.k = ((n.n - 1) % 7) + 1
JOIN objects_ o ON o.k = ((n.n - 1) % 7) + 1
JOIN purposes p ON p.k = ((n.n - 1) % 5) + 1;
GO

INSERT INTO dbo.audit_data_access
    (audit_id, accessed_at, accessor_upn, accessor_role, object_schema, object_name,
     operation, rows_affected, purpose_of_use, contains_pii)
VALUES
(1837462201, DATEADD(MINUTE, -12, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'customers',             'SELECT', 1, 'CustomerService', 1),
(1837462202, DATEADD(MINUTE, -11, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'customer_consents',    'SELECT', 4, 'CustomerService', 1),
(1837462203, DATEADD(MINUTE, -10, SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'service_requests',     'SELECT', 1, 'CustomerService', 0),
(1837462204, DATEADD(MINUTE, -9,  SYSUTCDATETIME()), 'tnguyen@enercare.ca', 'CustomerService', 'dbo', 'billing_transactions', 'SELECT', 2, 'CustomerService', 1);
GO

PRINT 'Purview demo seed data inserted successfully.';
GO

/* ------------------------------------------------------------------------------
   Verification queries (uncomment to run after seed)
------------------------------------------------------------------------------ */

-- SELECT COUNT(*) AS employees             FROM dbo.employees;
-- SELECT COUNT(*) AS zones                 FROM dbo.service_zones;
-- SELECT COUNT(*) AS consents              FROM dbo.customer_consents;
-- SELECT COUNT(*) AS complaints            FROM dbo.customer_complaints;
-- SELECT COUNT(*) AS owner_directory_rows  FROM dbo.data_owners_directory;
-- SELECT COUNT(*) AS audit_rows            FROM dbo.audit_data_access;
-- SELECT * FROM dbo.customers WHERE account_number = 'EC18374622';
-- SELECT * FROM dbo.service_requests WHERE request_id = 2026051142;
-- SELECT TOP 5 customer_id, date_of_birth, sin_last_4, owner_email FROM dbo.customers WHERE sin_last_4 IS NOT NULL;
-- SELECT TOP 5 service_account_id, latitude, longitude, service_zone_code FROM dbo.service_accounts WHERE latitude IS NOT NULL;
