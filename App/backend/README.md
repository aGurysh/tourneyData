# Backend commands

[Local setup and startup](../../README.md#start-locally). Run commands below from `App`.

## Tests

```bash
.venv/bin/python -m pytest -q

# Include PostgreSQL integration tests (isolated temporary schemas).
TEST_DATABASE_URL=postgresql+psycopg://tourney:tourney_local@localhost:5432/tourney \
  .venv/bin/python -m pytest -q
```

Database tests skip without `TEST_DATABASE_URL`. Use a development/test database;
the test user needs permission to create schemas.

## Migrations

```bash
.venv/bin/alembic current
.venv/bin/alembic upgrade head --sql
.venv/bin/alembic upgrade head
.venv/bin/alembic check

# After editing backend/db/models.py, generate and review a new revision.
.venv/bin/alembic revision --autogenerate -m "Describe the schema change"
```

Add revisions instead of editing migrations already applied to shared databases.

## API checks

```bash
curl http://localhost:8000/health
curl 'http://localhost:8000/tournaments?limit=10'
curl 'http://localhost:8000/tournaments/1/catches?limit=20'
curl http://localhost:8000/tournaments/1/weather
```

Full endpoints, filters, and response schemas: http://localhost:8000/docs.
The API uses `App/.env`; it does not run migrations or imports at startup.
Shell environment variables override `.env`. Custom PostgreSQL URLs must use
`postgresql+psycopg://`; keep Compose credentials/port and `DATABASE_URL` aligned.
`CORS_ORIGINS` is a comma-separated list, defaulting to `http://localhost:5173`.

## Dependencies

```bash
uv sync --locked --extra dev
# Intentional update:
uv lock --upgrade-package PACKAGE
uv sync --locked --extra dev
```

Commit `pyproject.toml` and `uv.lock` together. [Ingestion commands](ingestion/README.md).
