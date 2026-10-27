"""Validate and normalize reviewed JSON exports without database access."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


