# Tournament analytics app

This folder houses the backend and frontend. The existing scraper
and plotting scripts stay at the repository root. The tables follow
[`../DB_SCHEMA.md`](../DB_SCHEMA.md), including the two tournament standings scores.

## Project layout

```text
App/
├── backend/
│   ├── main.py             # FastAPI app, middleware, and router registration
│   ├── config.py           # Shared environment loading and app paths
│   ├── api/
│   │   ├── dependencies.py # Request-scoped database sessions
│   │   ├── schemas.py      # API response contracts
│   │   └── routes/         # Health, tournaments, and locations endpoints
│   ├── db/
│   │   ├── session.py      # Database URL and engine configuration
│   │   └── models.py       # SQLAlchemy table definitions
│   └── ingestion/
│       ├── cli.py          # Import arguments, output, and exit codes
│       ├── validation.py   # Cleaned-export validation and normalization
│       └── importer.py     # Import previews and transactional writes
├── frontend/               # Reserved for the web UI and its own build config
├── migrations/             # Versioned Alembic schema changes
├── tests/
│   ├── conftest.py         # Shared isolated PostgreSQL fixtures
│   ├── api/
│   ├── db/
│   └── ingestion/
├── pyproject.toml          # Python dependencies and backend package discovery
├── alembic.ini
└── compose.yaml
```

Run backend commands from `App`. The frontend will keep its own `package.json`
and build configuration inside `frontend/`. Scraping remains separate: capture
and review a cleaned JSON export, preview its import, then apply it explicitly.

## Start locally

Requirements: Python 3.12+ and Docker with Docker Compose. Run these commands from
this folder:

```bash
cd App
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
docker compose up -d --wait db
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

`upgrade head` creates the five application tables and an `alembic_version` table
that tracks the applied migration. Running it again is safe: applied migrations
are not repeated. It does not scrape or import tournament data.

The Compose database is available on localhost only. Its data lives in the
`postgres_data` Docker volume and survives `docker compose down`. The example
credentials are for local development. If you change the port, user, password,
or database, update `DATABASE_URL` too. PostgreSQL initialization settings only
take effect when creating a new data volume. URL-encode special characters in
credentials in `DATABASE_URL`.

If you already have PostgreSQL, set `DATABASE_URL` to its connection URL using the
`postgresql+psycopg://` driver and skip the Docker command. Shell environment
variables override `.env`. Keep `.env` out of Git; `.env.example` is the template.

## How the pieces fit together

- `backend/db/models.py` describes the current tables as typed Python classes.
  SQLAlchemy also uses these definitions to build queries and compare schemas.
- `migrations/versions/0001_initial_schema.py` contains the actual, versioned
  commands that create the tables. It is independent of future model edits.
- `migrations/env.py` connects Alembic to the models and database configuration.
- `backend/db/session.py` reads the connection URL and creates database engines.
  Importing Python modules never connects or creates tables automatically.
- `compose.yaml` runs PostgreSQL 18 for local development.

SQLAlchemy models describe the desired current state; migrations describe the
steps to get there. We use migrations rather than `Base.metadata.create_all()`
so later schema changes can be reviewed and applied to existing databases.
See the [SQLAlchemy ORM quick start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
and [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

## What the database enforces

`tournaments`, `locations`, `species`, and `catches` have generated `BIGINT`
primary keys. `tournament_locations` uses the pair of tournament and location
IDs as its primary key. This connects an event to multiple eligible waters
without duplicating its catches or claiming where each fish was caught.

Foreign keys reject references to nonexistent records. Deleting a referenced
parent is blocked: dependent records must be handled explicitly. There are no
automatic cascading deletes.

Tournament source URLs and non-null tournament external IDs are unique. Catch
external IDs are unique within a tournament. PostgreSQL allows multiple nulls
in these unique constraints: catches lacking source IDs can still be stored,
but a future importer must reconcile or replace them rather than blindly append.
Waterbody names intentionally are not unique.

Fish lengths use `NUMERIC(6,2)`, and tournament standings lengths use
`NUMERIC(12,2)`. Python reads these as `Decimal`, keeping exact decimal values.
Catch lengths must be positive; standings lengths can be zero or unknown
(`NULL`). Checks also reject PostgreSQL's special numeric `NaN` value.
The database rounds extra decimal places to the declared scale; strict input
precision validation belongs in the importer/API.

Catch times use `TIMESTAMP WITH TIME ZONE` (`timestamptz`). PostgreSQL stores the
instant, and our connections return times in UTC. The tournament's IANA timezone
remains a separate text field for interpreting source times and displaying local
times. Tournament dates use `DATE`. The future importer must validate timezone
names and supply timezone-aware datetimes; PostgreSQL can accept naive timestamp
inputs and interpret them using its session timezone.

Unknown species remains nullable. `Bass` normalization, coverage review,
timezone validation, and the calculation of winning/top-10% scores belong in
the import layer. `catch_coverage` defaults to `standings_only`; it remains text
so a future coverage type does not need an enum migration. No species are seeded
and no scraped data is imported by this migration.

Indexes cover catches by tournament/time, catches by species, and tournament
links by location. Primary keys and unique constraints provide their own indexes.

## Inspect and change the schema

Inspect the SQL before applying a migration (does not connect):

```bash
.venv/bin/alembic upgrade head --sql
```

Check that the live schema matches the models:

```bash
.venv/bin/alembic check
```

For a future change, edit the models, generate a new revision, review its upgrade
and downgrade commands, then apply it:

```bash
.venv/bin/alembic revision --autogenerate -m "Describe the schema change"
.venv/bin/alembic upgrade head
```

Do not edit a migration already applied to a shared database. Add a new revision.
The initial migration's downgrade drops all five application tables and their
data; use it only against a disposable development/test database.

## Verify against PostgreSQL

The integration tests use real PostgreSQL, not SQLite. They create a uniquely
named schema, run migrations there, and drop that schema afterwards. The test
user needs permission to create schemas. Use a development/test database:

```bash
TEST_DATABASE_URL=postgresql+psycopg://tourney:tourney_local@localhost:5432/tourney \
  .venv/bin/python -m pytest -q
```

Tests cover upgrade/downgrade/re-upgrade, model/migration agreement, uniqueness,
foreign keys, multi-water events, indexes, invalid lengths, exact decimals, and
UTC timestamp round trips. Without `TEST_DATABASE_URL`, database tests are skipped.

## Import a reviewed JSON export

Run from `App`. Use the cleaned, named-field `.json` written by the scraper,
not `.raw.json` or the older positional-array catch caches. The scraper stays
at the repository root and is independent of this command.

First preview an import (reads the database, writes nothing):

```bash
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-allegheny-achigan-showdown.json
```

Review the cleaned JSON, the capture timestamp (`scraped_at`), waterbody names
and boundaries, and any warnings. Then use the same command with `--apply`:

```bash
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-allegheny-achigan-showdown.json --apply
```

Repeat with another export:

```bash
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-bass-on-the-bay-11.json
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-bass-on-the-bay-11.json --apply
```

The command validates the whole file before connecting. It rejects blocking
issues, incomplete collection summaries, inconsistent catch counts, duplicate
catch IDs, invalid timezones, naive timestamps, and lengths that would be
silently rounded or exceed database precision. Offset-aware catch times become
UTC; `Bass` becomes `Largemouth Bass`. Unknown species stays null, and no assigned
locations is allowed with a warning. A passing preview does not verify the
source's current data or approve its waterbody assignments for you.

On apply, the tournament, species lookups, waterbody lookups/links, and catches
are written in one transaction. Any failure rolls the transaction back. Lookup
species are reused by canonical name; locations are reused by exact name/state
(state is uppercased). Multiple matching waterbody records are ambiguous: add
an `id` field to the location object in the reviewed JSON to select the existing
database record. The command checks its name/state before using it. Different
spellings are not fuzzy-matched; keep canonical names consistent across exports.

### Refresh an existing tournament

To patch only tournament duration and weather coordinates from a rebuilt
export, preserving all catch IDs, waterbody links, scores, and other metadata:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-allegheny-achigan-showdown.json --metadata-only
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-allegheny-achigan-showdown.json --metadata-only --apply
```

The patch requires an existing tournament with matching source identity,
date, and timezone. Its preview shows old and new values. `--metadata-only`
and `--replace` are mutually exclusive. Legacy exports without these optional
fields remain importable and do not erase existing weather metadata.

The source URL identifies the tournament, with external IDs also checked for
identity conflicts. By default an existing tournament is rejected, preventing
duplicate inserts. To load a newer reviewed snapshot, preview and apply with
`--replace`:

```bash
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-allegheny-achigan-showdown.json --replace
.venv/bin/python -m backend.ingestion.cli ../output/kawpa-allegheny-achigan-showdown.json --replace --apply
```

Replacement keeps the tournament's database ID, updates its metadata/scores,
and replaces all its catches and waterbody links with the snapshot. Catch
database IDs change; source IDs are retained from the file. Existing lookup
locations and species are retained. This snapshot strategy also works when
source catch IDs are missing. An omitted tournament external ID does not erase
an existing one. Review the timestamp before replacement: the importer does not
track historical snapshots or prevent applying an older file.

All importer writes take the same transaction-scoped advisory lock to serialize
these imports and avoid competing lookup creation. Keep imports in this command
until any future writer implements compatible concurrency rules.

Exit codes: `0` successful preview/import; `2` file validation or review conflict;
`1` database failure. The command never fetches new source data automatically.

## Run the API

From `App`, install/update the dependencies and start the development server:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn backend.main:app --reload
```

Keep PostgreSQL running. Visit [interactive API documentation](http://localhost:8000/docs)
to try the endpoints, or fetch [the tournament list](http://localhost:8000/tournaments).
The machine-readable OpenAPI document is at `/openapi.json`.

| Endpoint | Response |
| --- | --- |
| `GET /health` | `{"status":"ok"}` when PostgreSQL is reachable; otherwise HTTP 503. |
| `GET /tournaments` | Tournament metadata, catch counts, and winning/top-10% scores. Optional `location_id` filter. |
| `GET /tournaments/{id}` | Tournament metadata, catch count, and eligible waterbodies with boundary notes. |
| `GET /tournaments/{id}/catches` | Catches with nullable species ID/name. Optional `species_id` and `angler_name` filters. |
| `GET /tournaments/{id}/weather` | Historical hourly weather during the tournament's saved start/end times. |
| `GET /locations` | Waterbody IDs, names, and states. |

All collection endpoints accept `limit` (default 50, range 1–200) and `offset`
(default 0, nonnegative). Responses use this envelope:

```json
{"items": [], "total": 0, "limit": 50, "offset": 0}
```

`total` counts every matching row before pagination. Tournament ordering is date
descending, then ID ascending. Catch ordering is time ascending, then ID
ascending. Locations and tournament waterbodies are ordered by name, then ID.
The angler filter is a case-insensitive exact match; filters combine with AND.
An unknown species or location filter returns an empty collection. Unknown
tournament IDs return HTTP 404, including on the catch endpoint. Invalid
parameters return HTTP 422.

Lengths are decimal strings such as `"19.25"`; catch times are UTC ISO timestamps
such as `"2026-07-18T12:30:00Z"`. Tournament dates are calendar date strings, and
their IANA timezones remain available for local display. Waterbody links describe
eligible waters; they do not assign individual catches to a waterbody. Catch
coverage and the photo-time proxy limitations from the source still apply.

Example requests:

```bash
curl http://localhost:8000/health
curl 'http://localhost:8000/tournaments?limit=10'
curl 'http://localhost:8000/tournaments/1/catches?species_id=1&limit=20'
curl --get 'http://localhost:8000/tournaments/1/catches' --data-urlencode 'angler_name=Rick McIntyre'
```

The API uses the same `.env`/`DATABASE_URL` as the importer. It creates one engine
at startup, closes it at shutdown, and opens/closes a session per request without
committing writes. It does not run migrations or imports at startup. Database
failures return HTTP 503 without exposing SQL parameters or connection secrets.

### Tournament weather

`GET /tournaments/{id}/weather` uses the tournament's `weather_latitude`,
`weather_longitude`, `starts_at`, and `ends_at`. These come from the reviewed
TourneyX export (source `lat_lng`, `start_date`, and `end_date`); no location
config additions or weather database table are needed. Apply migrations and
patch older tournaments with `--metadata-only` before using this endpoint.

The backend requests the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api),
using UTC date boundaries and Unix timestamps. It returns only hourly samples
whose timestamps fall within the tournament interval, including exact endpoints.
It does not interpolate values at fractional start/end hours: a 05:45 start
has its first sample at 06:00. `timezone` is the tournament's IANA timezone;
all returned timestamps include `Z` for UTC.

Each `hourly` row contains:

| Field | Meaning/unit |
| --- | --- |
| `time` | UTC ISO timestamp |
| `temperature_f` | Air temperature at 2 m, degrees Fahrenheit |
| `pressure_hpa` | Sea-level pressure, hPa |
| `cloud_cover_percent` | Total cloud cover, 0–100% |
| `wind_speed_mph` | Wind speed at 10 m, miles per hour |
| `wind_direction_degrees` | Direction the wind comes from, degrees clockwise from north |

The response includes `tournament_id`, `starts_at`, `ends_at`,
`requested_coordinates`, provider `grid_coordinates`, `fetched_at`,
`source`, `source_url`, `attribution`, and `data_kind: "historical_reanalysis"`.
These are estimated historical conditions near the event point. They are not
individual catch observations or water temperature. Preserve attribution when
displaying the data. Free API usage is for noncommercial use; commercial use
requires an appropriate [Open-Meteo plan](https://open-meteo.com/en/pricing).

Missing measurements remain null. `coverage` is `complete` if every expected
hour and measurement within the interval is present, otherwise `partial`.
No usable measurements, or a tournament that has not ended yet, returns HTTP
503. Unknown tournaments return 404; missing coordinates/duration returns 409.
Provider failures/invalid responses return 502; timeouts return 504.

Successful requests are cached in memory per worker by requested coordinates
and UTC date range for 24 hours, with at most 128 entries. Partial results
expire after five minutes. Failed/empty requests are not added to the cache.
Restarting the API clears this cache. Weather retrieval does not write to the
database. The HTTP client has a five-second connection timeout and a
15-second timeout for other network operations, and closes on app shutdown.

```bash
curl http://localhost:8000/tournaments/1/weather
```

`CORS_ORIGINS` is a comma-separated list of allowed frontend origins, defaulting
to `http://localhost:5173`. For another frontend port, set it in `.env` and restart
the API. For example: `CORS_ORIGINS=http://localhost:5173,http://localhost:3000`.
Only GET methods are enabled for browser CORS. This initial API has no
authentication or write endpoints; the development server binds to localhost.

API tests use the same isolated PostgreSQL test schema described above. They
cover endpoint results, pagination/filtering, empty/missing data, decimal/time
serialization, database failures, CORS, engine cleanup, and unchanged table data.
