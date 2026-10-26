# Initial tournament imports

Run from the repository root using the existing virtual environment:

```bash
.venv/bin/python scrape.py https://tourneyx.com/leaderboard/standings/kawpa-allegheny-achigan-showdown --config tournament-config.example.json
```

The example configuration contains the three waterbodies discussed for this
tournament. Review their names and boundary notes before import. For another
tournament, copy the configuration and change its URL, timezone, and locations.
You can omit `--config` to collect data before assigning waterbodies; the export
will flag the missing assignments. Locations are never inferred from the event's
city or assigned to individual catches.

The scraper requires Playwright and its Chromium browser. If Chromium is missing:

```bash
.venv/bin/python -m playwright install chromium
```

## Files produced

By default, files go under `output/<tournament-slug>`:

- `.json`: named tournament and catch fields, reviewed locations, summary, and issues.
- `.raw.json`: the tournament metadata and standings JSON responses captured
  while the page loads. No HTML parsing or hovering is needed.

Older raw files may also contain partial HTML-derived records and a false
`collection_complete` flag. If both JSON responses were captured, the exporter
can use them directly, independently of the interrupted HTML pass. It leaves
the original raw file intact.

The export contains one tournament object, a list of locations with optional
boundary notes, and a list of catches. Catch fields are `angler_name`,
`catch_time`, `species`, `length_inches`, and nullable `external_id`. Species
names and locations are resolved to database IDs during a later import;
database primary keys and foreign keys are not invented by the scraper.
Lengths are decimal strings to retain exact precision. Catch times include a
UTC offset and preserve seconds from `date_taken` when available; the tournament
has an ISO calendar date and an IANA timezone. The exporter checks raw photo
times against their formatted equivalents. It does not use `date_submitted`
as a catch timestamp.

Tournament fields `winning_length_inches` and `top_10_percent_length_inches`
are decimal strings derived from the full captured standings, even when
`--max-anglers` limits the catch export. Winning length is the first-place
angler's score. Top 10% length is the score at the finishing place nearest
`source_anglers / 10`, rounding .5 upward with a minimum place of 1. Thus 100
anglers use 10th place, 48 use 5th, and 73 use 7th. Zero-fish anglers count
in the field size. Scores are sorted highest first; tied scores have the same
value at the cutoff. An empty field exports both lengths as null. Invalid
scores make both fields null and add a blocking issue; missing scores for
zero-fish anglers count as zero. These scores exclude culled fish absent
from the standings.

Review `summary` and `issues` before writing anything to the database:

- `source_anglers`, `anglers_processed`, and `anglers_with_fish` describe the
  response, including anglers with no fish.
- `fish_discovered`, `fish_exported`, and `fish_skipped` show parsing coverage.
- `reported_culled_fish` is a source counter, not additional individual fish
  records available for export.
- `blocking_issues` includes timestamp failures, inconsistent source fish counts
  or scores, duplicate IDs, and intentionally partial runs.
- `ready_for_review` means collection checks passed, not automatic approval for
  insertion. Review waterbody assignments, unknown species, and missing source IDs.
- Missing locations are a warning: the schema permits an unassigned tournament.
- Catches without source IDs require a replacement/reconciliation strategy on
  repeat import, rather than blindly appending records.

Exit code `0` means the export passed collection checks; `2` means a reviewable
export was written with blocking issues. Fetch/configuration failures raise an
error. A raw file is retained if fetching fails, but it may lack the required
responses; rerun with `--refresh` after resolving the problem. An older cleaned export may still exist after a failed
refresh; check the command result and `scraped_at` before using it.

## Reusing or refreshing data

The scraper reuses a raw snapshot only when its URL matches and both required
JSON responses are present. The full response is cached; `--max-anglers` limits
the export rather than the page's response.
Editing a location configuration and rerunning rebuilds the cleaned export
without another network request. Old positional-array `catches.json` files are
not reused because they do not identify their tournament.

```bash
# Fetch again, even if a snapshot exists.
.venv/bin/python scrape.py https://tourneyx.com/leaderboard/standings/kawpa-allegheny-achigan-showdown --config tournament-config.example.json --refresh

# A short trial; its summary explicitly marks it incomplete.
.venv/bin/python scrape.py https://tourneyx.com/leaderboard/standings/kawpa-allegheny-achigan-showdown --max-anglers 3 --output output/achigan-trial.json
```

Use `--headed` to watch the browser, and `--timeout-ms` to change page/element
timeouts. Existing plotting calls to `scrape_tourneyx(URL, max_anglers=...)`
still return local naive datetime tuples, but use the new tournament-specific
exports. Explicit legacy `cache_path` arguments now raise an error.

## Scope

Only fish displayed in standings are exported. Photo timestamps are used as
`catch_time`; they are not submission timestamps. `Bass` becomes `Largemouth
Bass`, and an unknown species remains null.

The collector uses Playwright only to open the page and wait for the normal
tournament metadata and standings responses. The exporter reads each angler's
`submissions` directly, including its source catch ID. Counts and length totals
are checked against the response's per-angler summaries.

In the saved Allegheny Achigan Showdown response, 48 anglers are listed and 43
have fish. There are 175 individual fish records, all within the five-fish limit
and with accepted status. The response reports 45 culled fish through counters
but provides no individual records for them. Coverage remains `standings_only`.
Other events may differ: extra submission records are retained but flagged for
coverage review if they exceed the scoring limit.

Unsupported response layouts, multi-day events, and multiple result groups stop
with an error until their interpretation is explicitly supported. The current
JSON collector has been checked against saved responses; a fresh browser capture
still needs a live run.

Offline checks:

```bash
.venv/bin/python -m unittest discover -s tests -v
```
