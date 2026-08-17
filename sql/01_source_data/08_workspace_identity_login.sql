-- Grants Fabric Mirroring access to sqldemo via the Enercare-West3 workspace identity.
-- Run against the `sqldemo` database on sqlserver-sk2wus3, connected as an Entra ID
-- (Azure AD) admin/user over the private path (P2S VPN client to vnet-purview-west3,
-- peered to vnet-sql-west3-sub2). Requires Azure AD-only auth (already enabled).
--
-- Workspace identity resolved via Fabric REST API + az ad sp show on 2026-08-08:
--   Workspace:            Enercare-West3 (b976cac2-7754-4061-88c2-61c0ac016a99)
--   Application (client): cf473f52-e1dc-4239-8057-eb5e1e75e2db
--   Service principal:    307a5e87-92ee-42b7-abca-76ee00186f99
--   Entra display name:   Enercare-West3   <-- this is the login/user name below

CREATE LOGIN [Enercare-West3] FROM EXTERNAL PROVIDER;
GO

CREATE USER [Enercare-West3] FOR LOGIN [Enercare-West3];
GO

GRANT SELECT,
      ALTER ANY EXTERNAL MIRROR,
      VIEW DATABASE PERFORMANCE STATE,
      VIEW DATABASE SECURITY STATE
TO [Enercare-West3];
GO
