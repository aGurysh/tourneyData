# Kayak Tournament Analytics

This application gives anglers access to deeper insights from kayak fishing tournament results. All tournament data is collected from public TourneyX result pages. This software is not a replacement for TourneyX, or meant to compete with it in any way. The goal is to provide data visualizations and summaries based on the data that is already publicly available.

The tech stack includes a React/Vite frontend, a FastAPI/PostgreSQL backend.

## Project layout

```text
App/
├── backend/                # FastAPI API, database models, and ingestion
├── frontend/               # React/Vite web UI
├── migrations/             # Versioned Alembic schema changes
├── tests/                  # Backend and ingestion tests
├── pyproject.toml          # Python dependencies and backend package discovery
├── uv.lock                 # Locked Python dependencies
├── alembic.ini
└── compose.yaml            # Local PostgreSQL database
DB_SCHEMA.md                # Database schema reference
```

## Start locally

1. Follow the [backend guide](App/backend/README.md) to install Python dependencies,
   configure `App/.env`, start PostgreSQL, apply migrations, and run the API.
2. Follow the [frontend guide](App/frontend/README.md) to install frontend
   dependencies and start Vite. The frontend proxies `/api` to the backend on
   port 8000 during development.
3. Follow the [ingestion guide](App/backend/ingestion/README.md) to collect and
   import tournament data.

Backend commands generally run from `App`; frontend commands run from
`App/frontend`. The ingestion guide provides commands for the repository root.

## Dependency installs and updates

The pinned tools are Python **3.12.3** (`App/.python-version`), uv **0.13.6**
(`App/pyproject.toml`), Node **24.18.0** (`App/frontend/.nvmrc`), and npm
**11.16.0** (`App/frontend/package.json`). Docker with Docker Compose is needed
for the local database.

Commit `App/uv.lock` and `App/frontend/package-lock.json`. Use
`uv sync --locked --extra dev` from `App` and `npm ci` from `App/frontend`
for reproducible development installs. See the component guides for setup,
intentional dependency updates, and verification commands.

## Continuous integration

For the private Render preview, see the [deployment guide](App/deploy/README.md)
and [Render Blueprint](render.yaml).

The [CI workflow](.github/workflows/ci.yml) runs on pull requests, pushes to
`main`, and manual runs from GitHub's Actions tab. It provides three checks:

- **Frontend tests and build** installs the pinned Node/npm versions, runs
  `npm ci`, then `npm test` and `npm run build`.
- **Backend tests with PostgreSQL** installs the pinned Python/uv versions,
  runs `uv sync --locked --extra dev`, then runs the full pytest suite against a
  fresh PostgreSQL 18 service container.
- **Deployment image and smoke test** builds the production Docker image, applies
  migrations to another disposable PostgreSQL 18 database, and verifies protected
  frontend/API access, built assets, and database reads over HTTP.

Each test database exists only for its job. Its credentials are local
test values in the workflow; no repository secrets or hosted database are needed.
The backend job's database URL variables point to its disposable database. Its
fixtures apply migrations to an isolated schema and create their own test data;
the deployment job exercises the explicit pre-deploy migration command. Neither
needs production data or an ingestion run. GitHub removes the service containers
when the jobs end. New commits cancel older runs for the same PR.
