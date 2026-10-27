"""Preview and apply reviewed exports within the caller's transaction."""

from sqlalchemy import Connection, delete, func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.db.models import Catch, Location, Species, Tournament, TournamentLocation
from backend.ingestion.validation import Export, ImportError


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


