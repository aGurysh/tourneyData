# Database reference

Current columns, constraints, and indexes: [SQLAlchemy models](App/backend/db/models.py).
Schema history: [Alembic migrations](App/migrations/versions).
[Migration commands](App/backend/README.md#migrations).

| Table | Purpose |
| --- | --- |
| `tournaments` | Source identity, date/timezone, duration, weather coordinates, standings scores. |
| `locations` | Canonical waterbody name/state. |
| `tournament_locations` | Eligible waters and event-specific boundary notes. |
| `species` | Canonical species names. |
| `anglers` | TourneyX user identity and latest captured display name. |
| `tournament_entries` | Event participants, including zero-fish anglers; event display names. |
| `catches` | Event/angler links, photo timestamp, species, and length. |

Catch times are stored in UTC; tournaments retain their IANA timezone for display.
Lengths use exact decimal values. Unknown species remains null; source `Bass`
normalizes to `Largemouth Bass`. Angler identity comes from TourneyX user IDs,
never names. Waterbody links identify eligible waters, not individual catch locations.

Coverage is `standings_only`: culled fish absent from standings are unavailable,
and photo time is the catch-time proxy. Weather coordinates describe the source's
event point. [Ingestion commands and review rules](App/backend/ingestion/README.md).
