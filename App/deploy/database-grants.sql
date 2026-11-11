-- Run with psql as the existing schema/table owner after creating the two logins.
-- Variables: api_role, importer_role. This is for the dedicated app database.
-- The current role must also create all future migration objects.
\set ON_ERROR_STOP on
BEGIN;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM :"api_role", :"importer_role";
GRANT USAGE ON SCHEMA public TO :"api_role", :"importer_role";
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"api_role", :"importer_role";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"api_role", :"importer_role";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"api_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"importer_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"importer_role";
-- Imports must not change the migration revision.
REVOKE ALL ON TABLE public.alembic_version FROM :"importer_role";
GRANT SELECT ON TABLE public.alembic_version TO :"importer_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO :"api_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"importer_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO :"importer_role";
COMMIT;
