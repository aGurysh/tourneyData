# Private Render deployment

The root [render.yaml](../../render.yaml) creates one paid web service and one
paid PostgreSQL 18 database in Virginia. The Docker image builds React and serves
it with FastAPI on one origin: `/` is the UI, `/api/*` is the API. Local Vite/API
development is unchanged. No custom domain is needed.

## Budget and access

The intended baseline is `0.5c-512mb` web compute (formerly Starter, about
$7/month), `0.1c-256mb` Postgres (formerly Basic-256mb, about $6/month), and
**1 GB** database storage (about $0.30/month).
Treat roughly **$13.30/month as an estimate**, not a spending cap. Confirm current
[pricing](https://render.com/pricing) and the provisioning estimate before creating
resources. Pipeline minutes, traffic, tax, larger storage, and temporary recovery
databases can add charges. Use a Hobby workspace, one instance, no additional
preview environments, and keep storage autoscaling disabled to limit costs.

The application defaults to private access. Render prompts for `PREVIEW_USERNAME`
and `PREVIEW_PASSWORD`; choose a unique username without a colon and a long random
password. These remain server-side secrets. Every page, asset, API route, and API
documentation route requires HTTP Basic authentication. Only `GET /health` is
public, returning database readiness without tournament data. Render supplies
HTTPS. Never use the preview credentials over plain HTTP outside localhost.

Missing credentials or an invalid `DEPLOYMENT_ACCESS` value stop startup. Private
responses are marked `no-store` and `noindex`. This gate is intended for your own
preview, rather than a multi-user account system. Browser Basic credentials can
remain remembered until the browser session ends.

## First deployment

1. Push this configuration to your GitHub repository and let CI pass. CI includes
   a Docker image build and a smoke test against disposable PostgreSQL.
2. In Render, create a Blueprint from that repository and branch. Review
   `render.yaml`, especially resource names, region, plans, and 1 GB storage.
   Supply the two preview secrets and approve provisioning only after checking
   the total estimate. The initial deployment starts during creation.
3. In workspace settings, choose the **Wait** overlapping deploy policy. Later
   deploys use **After CI Checks Pass**; do not cancel an active migration.
4. The pre-deploy command runs `alembic upgrade head` once, before the new web
   instance starts. A failure stops that release. This configuration starts with
   an empty database. For an existing populated database, follow the staged
   `0003` / angler backfill / `0004` procedure in the
   [ingestion guide](../backend/ingestion/README.md) before enabling normal deploys.
5. Open the service's `https://...onrender.com` address. An unauthenticated request
   must return 401. Sign in and check the selector (initially empty), `/api/health`,
   and the UI. `/health` must return 200 without credentials. Check deploy logs
   for the applied migration and successful startup. No password belongs in a
   URL, Git commit, or Vite environment variable.

Render's managed connection string is injected as `RENDER_DATABASE_URL` and
converted to the required psycopg driver URL by the backend. An explicit
`DATABASE_URL` still takes precedence and must use `postgresql+psycopg://`.
The initial private environment uses the database owner for API and migrations;
separate read-only API and administrative roles remain a prerequisite before
public launch. The Blueprint does not create those roles automatically.

## Administrative imports

The deployed image has no browser binaries, ingestion outputs, or scheduler.
Run the existing ingestion process on your computer using the same release's
code and retain/back up its local raw snapshots and reports.

Keep `render.yaml`'s database `ipAllowList: []` as the normal configuration: temporarily add IP as allowed source via render dashboard
Use Render's **external** connection details and provider-required TLS for your
local `DATABASE_URL`, using the explicit `postgresql+psycopg://` scheme. Supply it
through a private environment/secret file rather than pasting credentials into
shell history. Confirm the target host/database before running commands. From
the repository root:

```bash
App/.venv/bin/python -m backend.ingestion --dry-run
# Review the saved report, manifest, and snapshots, then:
App/.venv/bin/python -m backend.ingestion --offline
```

Use location IDs from this database, or name/state mappings. Existing tournaments
are skipped. Verify an imported tournament in the UI, including standings, bite
windows, and weather. Remove your temporary IP entry in the Render Dashboard when
finished; no redeploy or Blueprint sync is needed to remove it. Keep the YAML's
`ipAllowList: []` unchanged so future syncs preserve the normal configuration.
The importer does not run migrations or require redeploying the web app.

## Release and recovery rehearsal

Record the current release's commit SHA and `alembic current` output before a
release. Merge a small UI change, verify CI and Render deploy it, then exercise
authentication and representative tournament pages. Check health, errors, and
the deployed commit in the Render dashboard.

Use Render's rollback action to restore the prior successful service image, then
repeat the checks. An application rollback does **not** undo database migrations.
Only roll back to code compatible with the current schema; use forward fixes for
incompatible schema changes rather than an automatic `alembic downgrade`.

Before relying on stored data, rehearse a backup restore. Paid Render Postgres
currently provides a three-day recovery window on Hobby. Recovery creates another
database: verify it before switching connections, account for its temporary cost,
and delete the extra instance after verification. Retain independent logical
exports and ingestion snapshots according to your recovery needs.

## Public launch

Finish the deployment backlog: restricted API credentials, restore rehearsal,
uptime/error alerts, representative performance checks, and source attribution.
Then change `DEPLOYMENT_ACCESS` in `render.yaml` to `public`, sync, and verify
unauthenticated browsing. Update the Blueprint itself so later syncs preserve the
intended access mode. You can attach a domain later. Keep private staging separate
once public production holds data you cannot afford to disrupt; budget for the
additional environment before creating it.

## Local container check

From the repository root:

```bash
docker build -f App/deploy/Dockerfile -t tourney-preview .
docker run --rm --env-file /path/to/private-preview.env -p 10000:10000 tourney-preview
```

The private environment file must supply a reachable `DATABASE_URL`,
`PREVIEW_USERNAME`, and `PREVIEW_PASSWORD`. Inside a container, `localhost` is the
container itself. Apply migrations explicitly before this local check; container
startup does not run them. Visit `http://localhost:10000` only on your own machine.

References: [Blueprint fields](https://render.com/docs/blueprint-spec),
[deploy lifecycle](https://render.com/docs/deploys),
[database recovery](https://render.com/docs/postgresql-backups),
and [HTTP Basic authentication](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/).
