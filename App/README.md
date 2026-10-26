# Tournament analytics backend

This folder contains the PostgreSQL foundation for the app. The existing scraper
and plotting scripts stay at the repository root. The tables follow
[`../DB_SCHEMA.md`](../DB_SCHEMA.md), including the two tournament standings scores.

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

- `tourney_app/models.py` describes the current tables as typed Python classes.
  SQLAlchemy also uses these definitions to build queries and compare schemas.
- `migrations/versions/0001_initial_schema.py` contains the actual, versioned
  commands that create the tables. It is independent of future model edits.
- `migrations/env.py` connects Alembic to the models and database configuration.
- `tourney_app/db.py` reads the connection URL and creates database engines.
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
.venv/bin/python -m tourney_app.import_json ../output/kawpa-allegheny-achigan-showdown.json
```

Review the cleaned JSON, the capture timestamp (`scraped_at`), waterbody names
and boundaries, and any warnings. Then use the same command with `--apply`:

```bash
.venv/bin/python -m tourney_app.import_json ../output/kawpa-allegheny-achigan-showdown.json --apply
```

Repeat with another export:

```bash
.venv/bin/python -m tourney_app.import_json ../output/kawpa-bass-on-the-bay-11.json
.venv/bin/python -m tourney_app.import_json ../output/kawpa-bass-on-the-bay-11.json --apply
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

The source URL identifies the tournament, with external IDs also checked for
identity conflicts. By default an existing tournament is rejected, preventing
duplicate inserts. To load a newer reviewed snapshot, preview and apply with
`--replace`:

```bash
.venv/bin/python -m tourney_app.import_json ../output/kawpa-allegheny-achigan-showdown.json --replace
.venv/bin/python -m tourney_app.import_json ../output/kawpa-allegheny-achigan-showdown.json --replace --apply
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
