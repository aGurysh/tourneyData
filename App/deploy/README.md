# Render deployment

## Local image check

Run from the repository root:

```bash
docker build -f App/deploy/Dockerfile -t tourney-preview .
docker run --rm --env-file /path/to/private-preview.env -p 10000:10000 tourney-preview
```

The private env file needs a reachable `DATABASE_URL`, `PREVIEW_USERNAME`, and
`PREVIEW_PASSWORD`. Container `localhost` refers to the container. Apply migrations
before starting; then open http://localhost:10000.

## Deploy

1. Push the configuration and let checks pass. In Render, create a Blueprint from
   the repo/branch using [render.yaml](../../render.yaml). Review plans, region,
   storage, and the provisioning estimate before creating paid resources.
2. Supply `PREVIEW_USERNAME` (no colon) and a long random `PREVIEW_PASSWORD` as
   server secrets. Set the workspace overlapping deploy policy to **Wait**.
3. Complete the database-role setup below and supply both connection secrets
   before syncing the Blueprint. The pre-deploy command uses
   `MIGRATION_DATABASE_URL` to apply migrations. Do not cancel active migrations.
4. Open the service's HTTPS URL. Verify `/` returns 401 without credentials, sign
   in and check the UI and `/api/health`, then check public `/health` returns 200.

One Docker service serves the UI at `/` and API at `/api`; one PostgreSQL database
stores data. `DATABASE_URL` uses the restricted API login;
`MIGRATION_DATABASE_URL` uses the existing schema owner. Both require
`postgresql+psycopg://`. The legacy `RENDER_DATABASE_URL` fallback remains supported
for older configurations, but is no longer injected by the Blueprint. Private access
protects pages, assets, API, and docs except the health probe. Use HTTPS for credentials.

## Database roles and credential cutover

Use the existing `tourney_owner` for migrations to preserve ownership of current
objects. Create separate, fresh logins for the API and administrative importer.
Run this once in a private `psql` session connected as the owner to the intended
database, after taking an export. Use the internal hostname from Render for
service secrets; local administration uses the external hostname with TLS and
the temporary IP allowance described below. Keep passwords out of shell history,
Git, and command arguments; `\password` prompts privately.

```sql
CREATE ROLE tourney_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE tourney_importer LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password tourney_api
\password tourney_importer
\set api_role tourney_api
\set importer_role tourney_importer
\i App/deploy/database-grants.sql
```

Run `psql` from the repo root so the include path resolves. The grants script is
transactional and can be reapplied. It revokes public table/sequence permissions
and public schema creation in this dedicated database. The API can select; the
importer can select/insert/update/delete and use identity sequences, but cannot
change `alembic_version`, truncate tables, or perform schema changes. Neither
login should own objects or receive membership in the owner role or other roles.
Future tables/sequences receive grants from the current owner's default
privileges. Always run migrations as that same owner; a different creator needs
its own defaults. Review grants when introducing functions or additional schemas.
See [PostgreSQL default privileges](https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html).

Before deploying this Blueprint change:

1. In Render service environment settings, set `DATABASE_URL` to the internal
   API-login URL and `MIGRATION_DATABASE_URL` to the internal owner URL. URL-encode
   credentials. Remove the old owner-valued `RENDER_DATABASE_URL` variable.
   Coordinate saving secrets with deploying this release; old migration commands
   use `DATABASE_URL` and would fail after switching it to the API login.
2. Sync/deploy this release. Confirm migrations reach head and the API health,
   tournament, location, detail, catch, and weather routes still work with imported
   data. Check fresh authenticated browser access too.
3. Connect separately using the API login and verify a read succeeds and an
   `UPDATE tournaments SET name = name WHERE false` fails with permission denied.
   Verify `CREATE TABLE public.permission_check (id int)` is denied for both new
   logins. Run attempted writes inside a transaction and roll back.
4. Store the external importer URL privately for manual imports. Keep owner
   credentials for migrations, grants, and recovery. Remove temporary external
   access when finished. Do not change local development's owner-based `.env`.

Render shares service environment secrets between pre-deploy and runtime. These
URLs enforce separate database privileges for API connections, but an application
process compromise could still access the migration secret. Isolating that secret
requires moving migrations to a separately secured runner. Do not put importer
credentials in the web service. Logical exports do not preserve these roles;
recreate them and reapply grants after restoring as the owner.

## Administrative imports

Run locally using the deployed release's code; the image has no browser or scheduler.
Keep `render.yaml`'s `ipAllowList: []`. Finish pending Blueprint syncs, then temporarily
add your public IP `/32` in Render Dashboard → database → Networking. Blueprint syncs
can clear that dashboard exception.

Configure `DATABASE_URL` privately with the external **importer** connection, psycopg
scheme, and required TLS. Confirm the target host/database and take a backup first.
From the repository root:

```bash
App/.venv/bin/python -m backend.ingestion --dry-run
# Review the manifest, snapshots, and report before applying.
App/.venv/bin/python -m backend.ingestion --offline
```

Verify standings, bite windows, and weather in the UI; create a fresh database
export. Remove the temporary IP in the dashboard; no redeploy/sync is needed.
Raw snapshots/reports are optional diagnostic records; the database is the recovery
source for imported application data.

## Back up and restore

1. Export before imports, replacements, and migrations, after verified imports,
   and before launch. In Render → database → **Recovery** → **Create export**,
   download the `.dir.tar.gz` archive.
2. Keep private copies outside Git, this computer, and Render. Record UTC time,
   database identity, commit SHA, Alembic revision, and SHA-256 checksum. Retain
   three verified exports and pre-migration exports until the release is verified.
3. Rehearse restoration into a separate, empty PostgreSQL 18 database. Extract the
   archive; the directory containing `toc.dat` is the restore input. Configure
   libpq credentials privately and verify the target before running:

   ```bash
   pg_restore --no-owner --no-acl --exit-on-error --single-transaction \
     --dbname=tourney_restore_check /private/path/to/export-directory
   ```

4. Compare application table counts, Alembic revision, representative catches, and
   identity sequences with production. Point a local API at the restore and verify
   tournament list/detail/catch reads. Record results with the backup. An archive
   listing alone does not verify restoration.
5. During recovery, restore and verify a separate database before switching the app
   connection; preserve the original until confirmed. Recreate grants as needed.

Exports do not preserve application secrets, custom roles, raw responses, or reports.
Keep configuration/role instructions separately. The recovery point is the latest
verified export; measure the two-hour recovery target during rehearsal. Check
[Render recovery settings](https://render.com/docs/postgresql-backups) for provider
retention and temporary database costs; download exports you intend to retain.

## Release and public launch

Record the commit and Alembic revision before release. Verify authentication,
health, and representative pages after deployment or rollback. Image rollback does
not undo migrations; use code compatible with the current schema.

Before public launch, finish restricted API credentials, restore rehearsal,
uptime/error alerts, performance checks, and source attribution. Set
`DEPLOYMENT_ACCESS: public` in `render.yaml`, sync, and verify unauthenticated access.
Budget for separate private staging before creating it. Check current
[pricing](https://render.com/pricing) before changing resources.
