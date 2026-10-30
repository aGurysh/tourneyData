# Tournament ingestion

From the repository root, put tournament URLs in `App/backend/ingestion/new_tournaments.json`:

The entry below maps a tournament water body to an existing location.
To add entries for a water body not yet in db, use the following format

`"locations": [{ "name": "Lake X", "state": "PA" }]`

```json
[
  {
    "url": "https://tourneyx.com/leaderboard/standings/another-tournament-slug",
    "timezone": "America/New_York",
    "locations": [{ "id": 3, "boundary_notes": "Eligible section" }]
  }
]
```

Then run:

```bash
App/.venv/bin/python -m backend.ingestion
```

The default manifest is `App/backend/ingestion/new_tournaments.json`, resolved
relative to the module rather than the working directory. An explicit manifest path can also be
supplied. The adjacent example manifest demonstrates overrides; review its
waterbodies before using it.

New tournaments, all standings participants (including zero-fish anglers), and
catches are imported automatically after validation. Existing tournaments are
skipped. Each event has its own database transaction; failures are reported and
other events continue. Exit code 0 means success, 2 means a manifest or event
failed, and 1 means the initial database connection failed. A batch database error
is recorded as an event failure with exit code 2.

Useful options:

```bash
# Collect/validate and preview without changing the database.
App/.venv/bin/python -m backend.ingestion --dry-run

# Import new events using saved raw responses only.
App/.venv/bin/python -m backend.ingestion --offline

# Fetch every listed event anew and replace its database snapshot.
App/.venv/bin/python -m backend.ingestion --refresh
```

`--refresh` and `--offline` are mutually exclusive. `--dry-run` can accompany
either. Dry runs may write raw snapshots and reports. Use `--headed` to watch
collection or `--timeout-ms 60000` for slower pages.

## Raw snapshots and manual overrides

The pipeline is **raw JSON → Python transformation/validation → database**.
Cleaned JSON is no longer needed for ingestion. The cleaned-export CLI
(`python -m backend.ingestion.cli`) remains available for reviewed exports,
offline replacement, and metadata-only updates.

New captures are timestamped under `App/backend/ingestion/output/snapshots/<slug>/`. Failed captures
use `.failed.json`; they are never reused. Existing `App/backend/ingestion/output/<slug>.raw.json`
files remain usable if they contain both required responses. The newest complete
matching response is selected by capture time. A failed refresh never falls back
to old data. Parser/schema changes can replay saved responses without fetching.
The normal command still skips existing events; use the existing explicit
replacement CLI with a rebuilt export for offline replacement of an imported
event.

Every processed batch writes a JSON report under `App/backend/ingestion/output/reports/`, with the
snapshot path, capture time, action, record counts, warnings, and failures.

The manifest owns manual overrides. Timezone otherwise comes from source metadata
(or the stored timezone during refresh). Locations can use an existing database
ID, or `{ "name": "French Creek", "state": "PA" }` to resolve/create a location.
Ambiguous names require an ID. Boundary notes belong to the event/location link.
Missing waterbodies are a warning. During refresh, omitted locations preserve
existing assignments; an explicit empty list removes them. Never infer eligible
waterbodies from event cities or weather coordinates.

Anglers are identified by TourneyX user ID. Their latest captured name is stored
on `anglers`; older snapshots cannot overwrite newer names. Entries and catches
retain event-specific display names. Refresh replaces that tournament's catches
and entries and reuses shared anglers. It does not delete unused anglers.

Only single-day events with the supported standings layout and inch-based length
scoring are accepted. Multi-day events and unsupported result groups fail that
event. Coverage remains `standings_only`; photo time is the catch-time proxy and
individual culled fish unavailable in the source cannot be recovered by replay.

## Environment setup

Use the backend environment for the whole pipeline. Install the pinned uv version
as described in the [app setup guide](../../README.md), then from the repository root:

```bash
uv sync --project App --locked --extra dev
App/.venv/bin/python -m playwright install chromium
```

Configure `DATABASE_URL` in `App/.env` as for the API. The batch command never
runs migrations automatically. For a new empty database:

```bash
App/.venv/bin/alembic -c App/alembic.ini upgrade head
```

For a database with catches from before the anglers change, run these steps in
order from the repository root:

```bash
App/.venv/bin/alembic -c App/alembic.ini upgrade 0003
App/.venv/bin/python -m backend.ingestion --backfill --dry-run
App/.venv/bin/python -m backend.ingestion --backfill
App/.venv/bin/alembic -c App/alembic.ini upgrade head
```

Backfill uses only existing raw snapshots, matches tournaments and submission
IDs, verifies measurements/species/names/timestamps, and links catches without
replacing them or changing tournament metadata or waterbodies. It is rerunnable.
Mismatches stop that event for review. The final migration refuses to require
angler IDs until every catch is linked. Do not run it if the backfill report has
failures. Legacy cleaned exports without angler IDs need a matching sibling
`.raw.json`; identity is never guessed from a name.
