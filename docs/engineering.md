# Engineering guide

Kayak Tournament Analytics is a personal full-stack project built with React,
TypeScript, FastAPI, and PostgreSQL. It turns public tournament results into
interactive summaries, estimated standings, and catch-time distributions.

## Request path

The React client requests tournament, angler, and catch data through a FastAPI
API backed by SQLAlchemy and PostgreSQL. Pydantic schemas define API responses;
Alembic migrations version the relational schema. Tournaments, entries, anglers,
catches, and locations are modeled separately so angler identity and waterbody
assignments can be shared across tournaments.

In deployment, one Docker service serves the built frontend at `/` and API routes
at `/api`, keeping browser requests on one origin. During local development,
Vite proxies `/api` to the separate FastAPI process.

## Importing results

Ingestion runs as a separate administrative command. Playwright captures the
standings page's JSON responses, which are saved as raw snapshots before
transformation and validation. Dry runs produce previews and reports; offline
mode can import reviewed snapshots without fetching the source again.

Each tournament import runs in a database transaction, so a failure cannot leave
half an event imported. A shared PostgreSQL transaction advisory lock serializes
participating imports to prevent concurrent import conflicts. Refreshes preserve
the tournament's identity and shared anglers while replacing its entries and
catches. Raw captures and reports stay outside version control.

## Analytics and data limits

The frontend calculates estimated standings from final scoring catches in photo
timestamp order, using integer hundredths of an inch for score arithmetic.
Simultaneous catches share a ranking snapshot. Culled catches and official
tie-break decisions are unavailable, so the chart is explicitly an estimate.

Bite Windows groups catches into 30-minute intervals in the tournament's IANA
timezone, with species and minimum-length filters. Photo timestamps are a proxy
for catch times; the distribution describes the available scoring catches.
Historical weather comes through the backend from Open-Meteo, with response
validation and a bounded in-memory cache that gives partial results a shorter
lifetime.

## Deployment and verification

The Render configuration pairs the Docker service with managed PostgreSQL and
keeps the hosted preview behind Basic Auth, including assets, API routes, and
documentation. Only the health probe is unauthenticated. Database grants separate
the API's read access, the importer's data writes, and the migration owner's schema
changes. The migration secret currently shares the web service environment;
these roles restrict database connections but do not isolate that secret from
the application process.

GitHub Actions runs frontend tests and builds, backend tests against disposable
PostgreSQL, and a production-image smoke test covering migrations, restricted
database access, authentication, static assets, and API reads. Pinned runtimes
and committed dependency lockfiles make local and CI installs reproducible.

See the [database schema](../DB_SCHEMA.md), [ingestion workflow](../App/backend/ingestion/README.md),
[deployment guide](../App/deploy/README.md), and [CI workflow](../.github/workflows/ci.yml)
for implementation and operational details.
