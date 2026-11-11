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
3. The pre-deploy command applies migrations. For populated pre-angler databases,
   complete the [staged backfill](../backend/ingestion/README.md#legacy-angler-backfill)
   first. Do not cancel active migrations.
4. Open the service's HTTPS URL. Verify `/` returns 401 without credentials, sign
   in and check the UI and `/api/health`, then check public `/health` returns 200.

One Docker service serves the UI at `/` and API at `/api`; one PostgreSQL database
stores data. `RENDER_DATABASE_URL` is injected automatically; explicit
`DATABASE_URL` overrides it and requires `postgresql+psycopg://`. Private access
protects pages, assets, API, and docs except the health probe. Use HTTPS for credentials.

## Administrative imports

Run locally using the deployed release's code; the image has no browser or scheduler.
Keep `render.yaml`'s `ipAllowList: []`. Finish pending Blueprint syncs, then temporarily
add your public IP `/32` in Render Dashboard → database → Networking. Blueprint syncs
can clear that dashboard exception.

Configure `DATABASE_URL` privately with the external database connection, psycopg
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
