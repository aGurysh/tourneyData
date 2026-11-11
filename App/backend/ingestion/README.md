# Tournament ingestion

Run from the repository root after [local setup](../../../README.md#first-time-setup).

```bash
App/.venv/bin/python -m playwright install chromium

# Capture and preview; review reports before importing.
App/.venv/bin/python -m backend.ingestion --dry-run
App/.venv/bin/python -m backend.ingestion --offline
```

## Manifest

Edit `App/backend/ingestion/new_tournaments.json` before running:

```json
[
  {
    "url": "https://tourneyx.com/leaderboard/standings/another-tournament-slug",
    "timezone": "America/New_York",
    "locations": [{ "name": "Lake X", "state": "PA" }]
  }
]
```

Use a reviewed waterbody name/state or an existing location (`{"id": 3}`).
Only add `boundary_notes` when known. Never infer eligible waters from event cities
or weather coordinates. During refresh, omitted locations preserve assignments;
`"locations": []` removes them.

## Batch commands

```bash
# Collect and import new events; skip existing tournaments.
App/.venv/bin/python -m backend.ingestion

# Use another manifest.
App/.venv/bin/python -m backend.ingestion path/to/manifest.json --dry-run

# Fetch new snapshots and preview replacements, then apply.
App/.venv/bin/python -m backend.ingestion --refresh --dry-run
App/.venv/bin/python -m backend.ingestion --refresh
```

`--refresh` replaces catches and entries while preserving shared anglers.
It cannot combine with `--offline`. Add `--headed` to watch collection or
`--timeout-ms 60000` for slow pages. Migrations must be applied separately.

Snapshots: `App/backend/ingestion/output/snapshots/<slug>/`.
Reports: `App/backend/ingestion/output/reports/`. Dry runs can write both;
failed snapshots are never reused. Offline mode requires complete saved responses.
Each event is transactional; other events continue after a failure. Exit codes:
`0` success, `2` manifest/event failure, `1` initial database connection failure.

Only supported single-day, inch-scored standings are accepted. Coverage is
`standings_only`; photo time is a catch-time proxy and absent culled fish cannot
be recovered. Review capture times, warnings, timezone, and waterbody assignments.

## Reviewed JSON exports

Use cleaned named-field JSON, never `.raw.json`. These commands preview by default:

```bash
App/.venv/bin/python -m backend.ingestion.cli path/to/export.json
App/.venv/bin/python -m backend.ingestion.cli path/to/export.json --apply

# Replace an existing snapshot (catch IDs change).
App/.venv/bin/python -m backend.ingestion.cli path/to/export.json --replace
App/.venv/bin/python -m backend.ingestion.cli path/to/export.json --replace --apply

# Patch only duration/weather coordinates, preserving catches and waterbody links.
App/.venv/bin/python -m backend.ingestion.cli path/to/export.json --metadata-only
App/.venv/bin/python -m backend.ingestion.cli path/to/export.json --metadata-only --apply
```

Replacement preserves the tournament ID. Review timestamps: older snapshots are
not automatically rejected. `--replace` and `--metadata-only` are mutually exclusive.

## Legacy angler backfill

For populated databases predating angler IDs, run in order:

```bash
App/.venv/bin/alembic -c App/alembic.ini upgrade 0003
App/.venv/bin/python -m backend.ingestion --backfill --dry-run
App/.venv/bin/python -m backend.ingestion --backfill
# Only after the report has no failures:
App/.venv/bin/alembic -c App/alembic.ini upgrade head
```

Backfill links existing catches using matching raw snapshots without replacing
them. Identity is never guessed from names. Legacy cleaned exports without angler
IDs require matching sibling `.raw.json` files.
