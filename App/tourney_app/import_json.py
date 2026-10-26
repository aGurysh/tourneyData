"""Preview or import a reviewed scraper export: python -m tourney_app.import_json."""

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Connection, delete, func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from tourney_app.db import create_db_engine
from tourney_app.models import Catch, Location, Species, Tournament, TournamentLocation


class ImportError(ValueError):
    """An export or existing record needs attention before import."""


@dataclass
class Export:
    tournament: dict
    locations: list[dict]
    catches: list[dict]
    scraped_at: datetime
    warnings: list[str]


def object_value(value, label):
    if not isinstance(value, dict):
        raise ImportError(f"{label} must be a JSON object.")
    return value


def string(value, label, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ImportError(f"{label} must be a nonempty string.")
    return value.strip()


def decimal_value(value, label, precision, optional=False):
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ImportError(f"{label} must be an exact decimal string or integer.")
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or number >= Decimal(10) ** (precision - 2):
            raise InvalidOperation
        if number != number.quantize(Decimal("0.01")):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise ImportError(f"{label} must be finite, nonnegative, and fit NUMERIC({precision},2).") from None
    return number


def timestamp(value, label):
    try:
        result = datetime.fromisoformat(string(value, label))
    except ValueError:
        raise ImportError(f"{label} must be an ISO timestamp with a UTC offset.") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ImportError(f"{label} must include a UTC offset.")
    return result.astimezone(timezone.utc)


def load_export(path: Path) -> Export:
    """Validate the complete file before opening a database transaction."""
    try:
        data = json.loads(path.read_text(), parse_float=Decimal)
    except (OSError, ValueError) as exc:
        raise ImportError(f"Cannot read JSON export {path}: {exc}") from None
    object_value(data, "Export")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ImportError("Expected a schema_version 1 cleaned export, not raw JSON or a legacy catch cache.")
    summary = object_value(data.get("summary"), "summary")
    issues = data.get("issues")
    if not isinstance(issues, list):
        raise ImportError("issues must be a list.")
    warnings = []
    for issue in issues:
        object_value(issue, "issue")
        if issue.get("severity") not in {"warning", "error"}:
            raise ImportError("Each issue must have warning or error severity.")
        message = string(issue.get("message"), "issue.message")
        if issue["severity"] == "error":
            raise ImportError(f"Export contains a blocking issue: {message}")
        warnings.append(message)
    if summary.get("ready_for_review") is not True or summary.get("blocking_issues") != 0:
        raise ImportError("Export has not passed collection checks; review summary and issues.")
    for name in ("source_anglers", "anglers_processed", "fish_discovered", "fish_exported", "fish_skipped", "blocking_issues"):
        if type(summary.get(name)) is not int or summary[name] < 0:
            raise ImportError(f"summary.{name} must be a nonnegative integer.")
    if summary["source_anglers"] != summary["anglers_processed"] or summary["fish_skipped"]:
        raise ImportError("Partial exports or exports with skipped catches cannot be imported.")

    source = object_value(data.get("tournament"), "tournament")
    tournament = {key: string(source.get(key), f"tournament.{key}") for key in ("name", "timezone", "source_url", "catch_coverage")}
    if tournament["catch_coverage"] != "standings_only":
        raise ImportError("Only standings_only coverage is supported by this importer.")
    url = urlsplit(tournament["source_url"])
    if url.scheme not in {"http", "https"} or not url.netloc or url.fragment or url.query:
        raise ImportError("tournament.source_url must be a canonical HTTP(S) URL without query or fragment.")
    try:
        tournament["date"] = date.fromisoformat(string(source.get("date"), "tournament.date"))
        ZoneInfo(tournament["timezone"])
    except (ValueError, ZoneInfoNotFoundError):
        raise ImportError("Tournament date or IANA timezone is invalid.") from None
    tournament["external_id"] = string(source.get("external_id"), "tournament.external_id", optional=True)
    for key in ("winning_length_inches", "top_10_percent_length_inches"):
        tournament[key] = decimal_value(source.get(key), f"tournament.{key}", 12, optional=True)

    locations = data.get("locations")
    catches = data.get("catches")
    if not isinstance(locations, list) or not isinstance(catches, list):
        raise ImportError("locations and catches must be lists.")
    normalized_locations = []
    for location in locations:
        object_value(location, "location")
        row = {key: string(location.get(key), f"location.{key}", optional=key != "name") for key in ("name", "state", "boundary_notes")}
        if row["state"]:
            row["state"] = row["state"].upper()
        row["id"] = location.get("id")
        if row["id"] is not None and (type(row["id"]) is not int or row["id"] <= 0):
            raise ImportError("location.id must be a positive database ID when supplied.")
        normalized_locations.append(row)

    normalized_catches, ids = [], set()
    for index, catch in enumerate(catches):
        object_value(catch, f"catches[{index}]")
        row = {key: string(catch.get(key), f"catches[{index}].{key}", optional=key != "angler_name") for key in ("angler_name", "external_id", "species")}
        if row["external_id"] is not None:
            if row["external_id"] in ids:
                raise ImportError(f"Duplicate source catch ID: {row['external_id']}")
            ids.add(row["external_id"])
        if row["species"]:
            row["species"] = {"bass": "Largemouth Bass", "largemouth bass": "Largemouth Bass", "smallmouth bass": "Smallmouth Bass"}.get(row["species"].casefold(), row["species"])
        row["length_inches"] = decimal_value(catch.get("length_inches"), f"catches[{index}].length_inches", 6)
        if row["length_inches"] == 0:
            raise ImportError(f"catches[{index}].length_inches must be positive.")
        row["catch_time"] = timestamp(catch.get("catch_time"), f"catches[{index}].catch_time")
        normalized_catches.append(row)
    if summary["fish_exported"] != len(catches) or summary["fish_discovered"] != len(catches):
        raise ImportError("Catch count does not match the complete export summary.")
    if not locations:
        warnings.append("No waterbody assignments; tournament will remain unassigned.")
    missing_ids = sum(row["external_id"] is None for row in normalized_catches)
    if missing_ids:
        warnings.append(f"{missing_ids} catches lack source IDs. Reimport requires --replace.")
    unknown_species = sum(row["species"] is None for row in normalized_catches)
    if unknown_species:
        warnings.append(f"{unknown_species} catches have unknown species; stored as NULL.")
    return Export(tournament, normalized_locations, normalized_catches,
                  timestamp(data.get("scraped_at"), "scraped_at"), list(dict.fromkeys(warnings)))


def import_export(connection: Connection, export: Export, *, apply=False, replace=False) -> dict:
    """Plan/import within the caller's transaction; never commit independently."""
    if apply:
        # Serialize imports, including lookup creation, without changing the schema.
        connection.execute(text("SELECT pg_advisory_xact_lock(77321, 1)"))
    source = export.tournament
    criteria = [Tournament.source_url == source["source_url"]]
    if source["external_id"] is not None:
        criteria.append(Tournament.external_id == source["external_id"])
    matches = connection.execute(select(Tournament.__table__).where(or_(*criteria))).mappings().all()
    if len(matches) > 1:
        raise ImportError("Source URL and tournament external ID identify different database records.")
    existing = matches[0] if matches else None
    if existing:
        if existing["source_url"] != source["source_url"] or (
            existing["external_id"] is not None and source["external_id"] is not None
            and existing["external_id"] != source["external_id"]
        ):
            raise ImportError("Source URL/external ID conflicts with an existing tournament; review its identity.")
        if not replace:
            raise ImportError(f"Tournament {existing['id']} already exists. Use --replace to preview or apply a full snapshot replacement.")

    resolved_locations, keys = [], set()
    for location in export.locations:
        if location["id"] is not None:
            rows = connection.execute(select(Location.__table__).where(Location.id == location["id"])).mappings().all()
            if not rows or any(rows[0][key] != location[key] for key in ("name", "state")):
                raise ImportError(f"Location ID {location['id']} does not match the exported name/state.")
        else:
            rows = connection.execute(select(Location.__table__).where(Location.name == location["name"], Location.state == location["state"])).mappings().all()
        if len(rows) > 1:
            raise ImportError(f"Ambiguous location {location['name']!r}; add its database id to the JSON location object.")
        location_id = rows[0]["id"] if rows else None
        key = ("id", location_id) if location_id else ("new", location["name"], location["state"])
        if key in keys:
            raise ImportError("Export contains duplicate waterbody assignments.")
        keys.add(key)
        resolved_locations.append((location, location_id))

    old_count = connection.scalar(select(func.count()).select_from(Catch).where(Catch.tournament_id == existing["id"])) if existing else 0
    plan = {
        "action": "replace" if existing else "create", "applied": False,
        "tournament": source["name"], "source_url": source["source_url"],
        "date": source["date"].isoformat(), "timezone": source["timezone"],
        "catch_coverage": source["catch_coverage"],
        "winning_length_inches": str(source["winning_length_inches"]) if source["winning_length_inches"] is not None else None,
        "top_10_percent_length_inches": str(source["top_10_percent_length_inches"]) if source["top_10_percent_length_inches"] is not None else None,
        "tournament_id": existing["id"] if existing else None,
        "scraped_at": export.scraped_at.isoformat(),
        "catches_in_file": len(export.catches), "existing_catches": old_count,
        "locations": [{"name": loc["name"], "state": loc["state"], "boundary_notes": loc["boundary_notes"], "id": loc_id, "action": "reuse" if loc_id else "create"} for loc, loc_id in resolved_locations],
        "species": sorted({row["species"] for row in export.catches if row["species"]}),
        "warnings": export.warnings,
    }
    if not apply:
        return plan

    values = dict(source)
    if existing:
        tournament_id = existing["id"]
        if values["external_id"] is None:
            values["external_id"] = existing["external_id"]
        connection.execute(update(Tournament).where(Tournament.id == tournament_id).values(**values))
        connection.execute(delete(Catch).where(Catch.tournament_id == tournament_id))
        connection.execute(delete(TournamentLocation).where(TournamentLocation.tournament_id == tournament_id))
    else:
        tournament_id = connection.scalar(insert(Tournament).values(**values).returning(Tournament.id))
    for location, location_id in resolved_locations:
        if location_id is None:
            location_id = connection.scalar(insert(Location).values(name=location["name"], state=location["state"]).returning(Location.id))
        connection.execute(insert(TournamentLocation).values(tournament_id=tournament_id, location_id=location_id, boundary_notes=location["boundary_notes"]))
    species_ids = {}
    for name in plan["species"]:
        connection.execute(pg_insert(Species).values(name=name).on_conflict_do_nothing(index_elements=[Species.name]))
        species_ids[name] = connection.scalar(select(Species.id).where(Species.name == name))
    if export.catches:
        connection.execute(insert(Catch), [
            {key: value for key, value in row.items() if key != "species"}
            | {"tournament_id": tournament_id, "species_id": species_ids.get(row["species"])}
            for row in export.catches
        ])
    plan.update(applied=True, tournament_id=tournament_id)
    return plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Cleaned schema_version 1 JSON export")
    parser.add_argument("--apply", action="store_true", help="Write the import; default is read-only preview")
    parser.add_argument("--replace", action="store_true", help="Replace an existing tournament's metadata, catches, and waterbody links")
    args = parser.parse_args(argv)
    engine = None
    try:
        export = load_export(args.path)
        engine = create_db_engine()
        with engine.begin() as connection:
            plan = import_export(connection, export, apply=args.apply, replace=args.replace)
        print(json.dumps(plan, indent=2))
        if not args.apply:
            print("Preview only. Review the JSON, timestamps, and locations; rerun with --apply to import.")
        return 0
    except (ImportError, RuntimeError, ValueError) as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        # Avoid exposing credentials or catch data from SQLAlchemy exception text.
        print("Database operation failed; transaction rolled back. Check connectivity, migrations, and constraints.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
