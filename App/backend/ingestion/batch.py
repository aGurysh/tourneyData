"""Import a tournament manifest directly from saved or freshly captured responses."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError

from backend.db.models import Catch, Location, Species, Tournament, TournamentLocation
from backend.db.session import create_db_engine
from backend.ingestion.importer import import_entries, import_export
from backend.ingestion.source import CaptureSession, _build_export, _source_url, _write_json
from backend.ingestion.validation import validate_export, timestamp

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "output"


def read_manifest(path):
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("Manifest must be a JSON array of URL strings or objects with url, timezone, locations.")
    entries, seen = [], set()
    for item in data:
        item = {"url": item} if isinstance(item, str) else item
        if not isinstance(item, dict) or set(item) - {"url", "timezone", "locations"}:
            raise ValueError("Each entry must be a URL or an object with url, timezone, locations.")
        if not isinstance(item.get("url"), str):
            raise ValueError("Each entry needs a url string")
        url = _source_url(item["url"])
        if "timezone" in item:
            from zoneinfo import ZoneInfo
            if not isinstance(item["timezone"], str):
                raise ValueError("timezone must be an IANA timezone string")
            ZoneInfo(item["timezone"])
        if "locations" in item:
            if not isinstance(item["locations"], list):
                raise ValueError("locations must be a list")
            for location in item["locations"]:
                if not isinstance(location, dict):
                    raise ValueError("Each location must be an object")
                if "id" in location:
                    if type(location["id"]) is not int or location["id"] <= 0:
                        raise ValueError("location.id must be a positive database ID")
                elif not isinstance(location.get("name"), str) or not location["name"].strip():
                    raise ValueError("Each location needs an id or name")
        normalized = dict(item, url=url)
        if url in seen:
            if next(e for e in entries if e["url"] == url) != normalized:
                raise ValueError(f"Conflicting duplicate manifest entries: {url}")
            continue
        entries.append(normalized)
        seen.add(url)
    return entries


def snapshot_candidates(url, output):
    slug = url.rsplit("/", 1)[1]
    paths = list((output / "snapshots" / slug).glob("*.raw.json"))
    legacy = output / f"{slug}.raw.json"
    if legacy.exists():
        paths.append(legacy)
    # Capture time is authoritative, not the filesystem modification time.
    candidates = []
    for path in paths:
        try:
            raw = json.loads(path.read_text())
            if raw.get("source_url") == url and isinstance(raw.get("metadata"), dict) and isinstance(raw.get("standings"), dict):
                candidates.append((timestamp(raw["scraped_at"], "scraped_at"), path, raw))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(candidates, key=lambda c: c[0], reverse=True)


def get_snapshot(url, output, session, *, refresh=False, offline=False):
    if not refresh:
        candidates = snapshot_candidates(url, output)
        if candidates:
            _, path, raw = candidates[0]
            return path, raw
    if offline:
        raise ValueError("No complete matching raw snapshot is available offline.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = output / "snapshots" / url.rsplit("/", 1)[1]
    pending = folder / f"{stamp}.failed.json"
    raw = session.fetch(url, pending)
    complete = folder / f"{stamp}.raw.json"
    pending.rename(complete)
    return complete, raw


def location_config(connection, item, existing):
    config = {key: item[key] for key in ("timezone", "locations") if key in item}
    if existing and "timezone" not in config:
        config["timezone"] = existing["timezone"]
    if existing and "locations" not in config:
        config["locations"] = [dict(row) for row in connection.execute(
            select(Location.id, Location.name, Location.state, TournamentLocation.boundary_notes)
            .join(TournamentLocation, TournamentLocation.location_id == Location.id)
            .where(TournamentLocation.tournament_id == existing["id"])).mappings()]
    resolved = []
    for location in config.get("locations", []):
        location = dict(location)
        if location.get("id") is not None:
            row = connection.execute(select(Location.__table__).where(Location.id == location["id"])).mappings().one_or_none()
            if row is None:
                raise ValueError(f"Unknown location ID {location['id']}")
            if any(key in location and location[key] != row[key] for key in ("name", "state")):
                raise ValueError("Location ID conflicts with supplied name/state")
            location = dict(row) | location
        resolved.append(location)
    config["locations"] = resolved
    return config


def prepare_export(raw, config):
    return validate_export(_build_export(raw, config))


def backfill_one(connection, tournament, raw, *, apply):
    """Link existing catches by source ID after verifying the entire saved catch set."""
    connection.execute(text("SELECT pg_advisory_xact_lock(77321, 1)"))
    export = prepare_export(raw, {"timezone": tournament["timezone"]})
    if (export.tournament["source_url"] != tournament["source_url"]
            or export.tournament["external_id"] != tournament["external_id"]
            or export.tournament["date"] != tournament["date"]):
        raise ValueError("Backfill snapshot does not match tournament identity/date")
    catches = connection.execute(
        select(*Catch.__table__.c, Species.name.label("species"))
        .outerjoin(Species, Species.id == Catch.species_id)
        .where(Catch.tournament_id == tournament["id"])).mappings().all()
    by_id = {c["external_id"]: c for c in export.catches if c["external_id"] is not None}
    if len(by_id) != len(export.catches) or len(catches) != len(by_id):
        raise ValueError("Backfill needs a complete matching catch set with source IDs")
    links = []
    for catch in catches:
        source = by_id.get(catch["external_id"])
        if source is None or any(catch[key] != source[key] for key in ("angler_name", "catch_time", "length_inches", "species")):
            raise ValueError(f"Backfill catch {catch['id']} differs from saved source; no changes applied")
        if catch["angler_id"] is not None:
            from backend.db.models import Angler
            identity = connection.scalar(select(Angler.external_id).where(Angler.id == catch["angler_id"]))
            if identity != source["source_angler_id"]:
                raise ValueError("Existing catch angler conflicts with source identity")
        links.append((catch["id"], source["source_angler_id"]))
    if apply:
        ids = import_entries(connection, export, tournament["id"])
        for catch_id, source_id in links:
            connection.execute(update(Catch).where(Catch.id == catch_id).values(angler_id=ids[source_id]))
    return {"action": "backfill", "applied": apply, "tournament_id": tournament["id"],
            "anglers_in_file": len(export.anglers), "catches_in_file": len(links), "warnings": export.warnings}


def run(entries, engine, *, output=OUTPUT, refresh=False, offline=False, dry_run=False,
        backfill=False, headed=False, timeout_ms=30000):
    results = []
    with CaptureSession(headed, timeout_ms) as session:
        for item in entries:
            url = item["url"]
            result = {"source_url": url}
            try:
                # Finish the read transaction before collecting network responses.
                with engine.connect() as connection:
                    existing = connection.execute(select(Tournament.__table__).where(Tournament.source_url == url)).mappings().one_or_none()
                if existing and not refresh and not backfill:
                    result.update(action="skipped", reason="Already imported; use --refresh to replace")
                else:
                    path, raw = get_snapshot(url, output, session, refresh=refresh, offline=offline)
                    result["snapshot"] = str(path)
                    result["scraped_at"] = raw["scraped_at"]
                    with engine.begin() as connection:
                        if backfill:
                            if existing is None:
                                raise ValueError("Backfill requires an existing tournament")
                            result.update(backfill_one(connection, existing, raw, apply=not dry_run))
                        else:
                            config = location_config(connection, item, existing)
                            export = prepare_export(raw, config)
                            if not dry_run:
                                # Recheck under the same lock used by the importer.
                                connection.execute(text("SELECT pg_advisory_xact_lock(77321, 1)"))
                                concurrent = connection.scalar(select(Tournament.id).where(Tournament.source_url == url))
                                if concurrent and not refresh:
                                    result.update(action="skipped", reason="Imported by another process")
                                    results.append(result)
                                    continue
                            result.update(import_export(connection, export, apply=not dry_run, replace=refresh))
            except SQLAlchemyError:
                result.update(action="failed", applied=False, error="Database operation failed; transaction rolled back. Check migrations, connectivity, and constraints.")
            except Exception as exc:
                # Per-event isolation: retain failures and continue through the list.
                result.update(action="failed", applied=False, error=str(exc))
            results.append(result)
            print(f"{result['action']}: {url}", flush=True)
            if "error" in result:
                print(f"  {result['error']}", flush=True)
            for warning in result.get("warnings", []):
                print(f"  Warning: {warning}", flush=True)
    counts = {action: sum(r["action"] == action for r in results)
              for action in ("create", "replace", "backfill", "skipped", "failed")}
    report = {"finished_at": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run, "counts": counts, "results": results}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = output / "reports" / f"{stamp}.json"
    _write_json(report_path, report)
    print(json.dumps(counts), flush=True)
    print(f"Report: {report_path}", flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", default=ROOT / "new_tournaments.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true", help="Fetch and replace listed tournaments")
    mode.add_argument("--offline", action="store_true", help="Use saved raw snapshots exclusively")
    parser.add_argument("--dry-run", action="store_true", help="Collect and preview without database writes")
    parser.add_argument("--backfill", action="store_true", help="Link all existing tournaments from saved snapshots without changing catches")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    args = parser.parse_args(argv)
    if args.timeout_ms <= 0:
        parser.error("--timeout-ms must be positive")
    engine = None
    try:
        if args.backfill and args.refresh:
            raise ValueError("Backfill uses saved source data; --refresh is not allowed")
        entries = None if args.backfill else read_manifest(args.manifest)
        if entries == []:
            print("No tournaments listed; nothing to import.")
            return 0
        engine = create_db_engine()
        if args.backfill:
            with engine.connect() as connection:
                entries = [{"url": url} for url in connection.scalars(select(Tournament.source_url).order_by(Tournament.id))]
        report = run(entries, engine, refresh=args.refresh, offline=args.offline or args.backfill,
                     dry_run=args.dry_run, backfill=args.backfill, headed=args.headed, timeout_ms=args.timeout_ms)
        return 2 if report["counts"]["failed"] else 0
    except SQLAlchemyError:
        print("Database unavailable; check configuration and migrations.", file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        return 2
    finally:
        if engine:
            engine.dispose()
