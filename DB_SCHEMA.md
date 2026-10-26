# Proposed database schema

This schema supports an initial database populated from TourneyX standings.
The scraper is an import aid, not a production service. Data can be reviewed
and locations assigned manually before import.

## Tables

### tournaments

| Column           | Suggested type | Constraints / purpose                                                                            |
| ---------------- | -------------- | ------------------------------------------------------------------------------------------------ |
| `id`             | bigint         | Primary key, generated internally.                                                               |
| `name`           | text           | Required tournament name.                                                                        |
| `date`           | date           | Required calendar date; no tournament start or end timestamps.                                   |
| `timezone`       | text           | Required IANA timezone, such as `America/New_York`, for interpreting and displaying catch times. |
| `source_url`     | text           | Required canonical source standings URL; unique for the initial TourneyX import.                 |
| `external_id`    | text           | Optional TourneyX tournament identifier; unique when present.                                    |
| `catch_coverage` | text           | Required; initially `standings_only`.                                                            |

The calendar date can be displayed as day/month/year. `DATE` stores the date
without a time or display format. The initial model assumes one date per
tournament; multi-day event support would require a later decision.

### locations

| Column  | Suggested type | Constraints / purpose                                                    |
| ------- | -------------- | ------------------------------------------------------------------------ |
| `id`    | bigint         | Primary key, generated internally.                                       |
| `name`  | text           | Required canonical waterbody name.                                       |
| `state` | text           | State abbreviation, such as `PA`; nullable if unknown or not applicable. |

Locations represent waterbodies, rather than the event's listed city or awards
venue. Assign canonical locations manually during initial import. Do not assume a waterbody name alone is globally
unique.

### tournament_locations

| Column           | Suggested type | Constraints / purpose                                             |
| ---------------- | -------------- | ----------------------------------------------------------------- |
| `tournament_id`  | bigint         | Required foreign key to `tournaments.id`.                         |
| `location_id`    | bigint         | Required foreign key to `locations.id`.                           |
| `boundary_notes` | text           | Optional description of the section eligible for this tournament. |

Use `(tournament_id, location_id)` as the composite primary key. This permits
multiple waterbodies per tournament and multiple tournaments per waterbody.
Boundary notes belong here because eligible sections can differ between events.
A tournament can temporarily have no location assignments while awaiting review.

### species

| Column | Suggested type | Constraints / purpose                    |
| ------ | -------------- | ---------------------------------------- |
| `id`   | bigint         | Primary key, generated internally.       |
| `name` | text           | Required, unique canonical species name. |

Normalize source labels of `Bass` to `Largemouth Bass` during import.

### catches

| Column          | Suggested type           | Constraints / purpose                                                 |
| --------------- | ------------------------ | --------------------------------------------------------------------- |
| `id`            | bigint                   | Primary key, generated internally.                                    |
| `tournament_id` | bigint                   | Required foreign key to `tournaments.id`.                             |
| `angler_name`   | text                     | Required angler display name stored directly on the catch.            |
| `catch_time`    | timestamp with time zone | Required full catch date and time, normalized to UTC on import.       |
| `species_id`    | bigint                   | Nullable foreign key to `species.id`; older records may lack species. |
| `length_inches` | numeric(6,2)             | Required positive decimal length in inches.                           |
| `external_id`   | text                     | Optional stable source catch identifier, if available.                |

When `external_id` is present, enforce uniqueness on
`(tournament_id, external_id)`. Do not treat angler name, timestamp, and length
as a guaranteed unique catch identifier. When a stable source identifier is
unavailable, review or replace a tournament's imported catch set rather than
blindly appending it on every import.

## Relationships

```mermaid
erDiagram
    tournaments ||--o{ catches : contains
    species o|--o{ catches : identifies
    tournaments ||--o{ tournament_locations : has
    locations ||--o{ tournament_locations : participates_in
```

For a multi-waterbody event, create one tournament and link each eligible
waterbody through `tournament_locations`. Do not duplicate its catches for each
waterbody.

## Import conventions and known limitations

- Only fish visible in the standings are available. These are not all submitted
  fish; record `catch_coverage = 'standings_only'`.
- `catch_time` currently comes from the source's **Picture Taken** timestamp,
  used as a proxy for catch time rather than submission time.
- Interpret source timestamps in the tournament's configured timezone before
  converting them to UTC. For these Eastern US events, use
  `America/New_York`, which accounts for daylight saving time.
- Preserve unknown species as `NULL`; retain the agreed Bass-to-Largemouth Bass
  normalization when a source species label is present.
- Internal IDs belong to this database. External IDs refer to source records
  and are nullable when the source does not expose a stable identifier.
- The initial source is TourneyX. Supporting additional providers later requires
  source-qualified external identifiers and corresponding uniqueness rules.
- Keep raw snapshots and import issue reports outside these core tables so
  parsing errors and missing data can be reviewed before database insertion.

## Initial indexes

Primary keys and unique constraints provide their corresponding indexes.
Additionally, add:

- `catches (tournament_id, catch_time)` for tournament catch timelines.
- `catches (species_id)` for species filtering.
- `tournament_locations (location_id, tournament_id)` for finding tournaments
  associated with a waterbody.

Add further indexes when actual application queries justify them.
