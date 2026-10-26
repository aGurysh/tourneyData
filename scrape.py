"""Export reviewable TourneyX standings data: python scrape.py --help.

scrape_tourneyx remains an adapter for the existing plotting scripts.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

TIMEZONES = {"Eastern": "America/New_York", "Central": "America/Chicago",
             "Mountain": "America/Denver", "Pacific": "America/Los_Angeles"}


def _source_url(url):
    parsed = urlparse(url)
    parts = parsed.path.rstrip("/").split("/")
    if (parsed.scheme != "https" or parsed.hostname != "tourneyx.com"
            or parts[:3] != ["", "leaderboard", "standings"] or len(parts) != 4
            or not re.fullmatch(r"[A-Za-z0-9_-]+", parts[3])):
        raise ValueError("Use an https://tourneyx.com/leaderboard/standings/<slug> URL")
    return f"https://tourneyx.com/leaderboard/standings/{parts[3]}"


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _normalize_species(species):
    if not species or not species.strip():
        return None
    return "Largemouth Bass" if species.strip().casefold() == "bass" else species.strip()


def _parse_timestamp(text):
    """Parse photo time without assuming a fixed timezone suffix."""
    text = text.strip()
    if "Picture Taken:" in text:
        text = text.split("Picture Taken:", 1)[1].split("Fish submitted:", 1)[0]
    text = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text.strip(), flags=re.I)
    text = re.sub(r"\s+(Eastern|Central|Mountain|Pacific)(?:\s+Time)?\s*$", "", text)
    text = re.sub(r"(?<=\d)(am|pm)\b", r" \1", text, flags=re.I)
    text = " ".join(text.split())
    for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %I:%M:%S %p"):
        try:
            return datetime.strptime(text.upper(), fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _utc_timestamp(local_time, zone):
    if local_time.tzinfo is not None:
        return local_time.astimezone(timezone.utc)
    candidates = set()
    for fold in (0, 1):
        candidate = local_time.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == local_time:
            candidates.add(candidate)
    if len(candidates) != 1:
        raise ValueError("Photo time is ambiguous or nonexistent at a daylight saving transition")
    return candidates.pop()


def _source_rows(standings):
    """Support the observed single-day response explicitly, including zero-fish rows."""
    if not isinstance(standings, dict):
        raise ValueError("No standings JSON captured; rerun with --refresh")
    results = standings.get("results")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], list):
        raise ValueError("Unsupported standings layout or multiple result groups; review raw JSON")
    rows = results[0]
    for row in rows:
        if not isinstance(row, dict) or not row.get("user_id"):
            raise ValueError("Standings row lacks an angler identifier")
        if row.get("submissions") is not None and not isinstance(row["submissions"], list):
            raise ValueError("Unsupported submissions layout; review raw JSON")
        if any(not isinstance(fish, dict) for fish in row.get("submissions") or []):
            raise ValueError("Unsupported submission record; review raw JSON")
    return rows


def _standings_lengths(rows, issues):
    """Select winning and nearest top-decile scores from the complete field."""
    scores = []
    seen = set()
    for row_index, row in enumerate(rows):
        try:
            if str(row["user_id"]) in seen:
                raise ValueError("Duplicate angler prevents tournament length calculation")
            seen.add(str(row["user_id"]))
            value = row.get("total_fish_length")
            if value in (None, "") and not row.get("submissions"):
                value = 0
            score = Decimal(str(value))
            if not score.is_finite() or score < 0 or score != score.quantize(Decimal("0.01")):
                raise ValueError("Invalid standings score for tournament length calculation")
            scores.append(score)
        except (InvalidOperation, ValueError, TypeError) as error:
            issues.append({"severity": "error", "row_index": row_index,
                           "message": f"Cannot calculate tournament lengths: {error}"})
            return None, None
    if not scores:
        return None, None
    scores.sort(reverse=True)
    # Nearest finishing place to 10% of the field; round .5 upward.
    top_place = max(1, (len(scores) + 5) // 10)
    return (str(scores[0].quantize(Decimal("0.01"))),
            str(scores[top_place - 1].quantize(Decimal("0.01"))))


def _fetch_snapshot(url, headed, timeout_ms, snapshot_path):
    raw = {"source_url": url, "scraped_at": datetime.now(timezone.utc).isoformat(),
           "capture_version": 2, "collection_complete": False}
    # Let the page make its normal requests; read only their JSON responses.
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not headed)
            try:
                page = browser.new_page()
                page.set_default_timeout(timeout_ms)
                endpoints = {"metadata": "get_react_page_tournament_details",
                             "standings": "post_tournament_standings_summary"}

                def matches(response, endpoint):
                    parsed = urlparse(response.url)
                    return (parsed.hostname == "api.tourneyx.com"
                            and parsed.path.endswith("/" + endpoint)
                            and response.request.method == "POST")

                with page.expect_response(lambda response: matches(response, endpoints["metadata"])) as metadata:
                    with page.expect_response(lambda response: matches(response, endpoints["standings"])) as standings:
                        page.goto(url, wait_until="domcontentloaded")
                    for key, response in (("metadata", metadata.value), ("standings", standings.value)):
                        if not response.ok:
                            raise ValueError(f"{key} request failed with HTTP {response.status}")
                        raw[key] = response.json()
                raw["collection_complete"] = True
            finally:
                browser.close()
    finally:
        _write_json(snapshot_path, raw)
    return raw


def _build_export(raw, config, max_anglers=None):
    url = _source_url(raw["source_url"])
    if config.get("source_url") and _source_url(config["source_url"]) != url:
        raise ValueError("Configuration belongs to a different tournament")
    meta = raw["metadata"]
    zone_name = config.get("timezone") or TIMEZONES.get(meta.get("timezone"), meta.get("timezone"))
    if not zone_name:
        raise ValueError("Set an IANA timezone in the configuration")
    zone = ZoneInfo(zone_name)
    day = datetime.fromisoformat(meta["start_date"]).date()
    if day != datetime.fromisoformat(meta["end_date"]).date():
        raise ValueError("Multi-day events are not supported by this date-only export yet")
    if meta.get("measurement_type") != "length" or meta.get("measurement_name") != "inch":
        raise ValueError("Only length tournaments measured in inches are supported")
    if not str(meta.get("tournament_title") or "").strip():
        raise ValueError("Tournament name is missing")
    if meta.get("slug") != url.rsplit("/", 1)[1]:
        raise ValueError("Source metadata does not match the requested tournament")
    standings = raw.get("standings")
    rows = _source_rows(standings)
    if str(standings.get("tournamentId")) != str(meta["id"]):
        raise ValueError("Standings response belongs to a different tournament")
    if standings.get("measurement_type") != "length":
        raise ValueError("Standings response is not a length tournament")
    try:
        fish_limit = int(meta["total_fish"])
        if fish_limit < 1:
            raise ValueError("Invalid scoring fish limit")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Could not determine the scoring fish limit") from error
    issues = []
    winning_length, top_10_percent_length = _standings_lengths(rows, issues)
    locations = config.get("locations", [])
    if not isinstance(locations, list):
        raise ValueError("locations must be a list")
    for location in locations:
        if not isinstance(location, dict) or not str(location.get("name") or "").strip():
            raise ValueError("Every location needs a canonical name")
    if not locations:
        issues.append({"severity": "warning", "message": "Waterbody assignments await manual review"})
    if max_anglers is not None:
        issues.append({"severity": "error", "message": "Partial run: max_anglers was set"})
    processed_rows = rows if max_anglers is None else rows[:max_anglers]
    catches = []
    discovered = 0
    seen_ids = set()
    seen_anglers = set()
    culled_count = 0
    for row_index, row in enumerate(processed_rows):
        name = str(row.get("angler_name") or "").strip()
        submissions = row.get("submissions") or []
        discovered += len(submissions)
        if str(row["user_id"]) in seen_anglers:
            issues.append({"severity": "error", "message": "Duplicate source angler row", "row_index": row_index})
        seen_anglers.add(str(row["user_id"]))
        try:
            culled_count += int(row.get("culled_fish_records") or 0)
            if row.get("fish_caught") is not None and int(row["fish_caught"]) != len(submissions):
                issues.append({"severity": "error", "message": "Submission count differs from reported fish count",
                               "angler_name": name})
        except (TypeError, ValueError):
            issues.append({"severity": "error", "message": "Unrecognized source fish counts", "angler_name": name})
        if len(submissions) > fish_limit:
            issues.append({"severity": "error", "message": "Response exceeds scoring limit; review catch coverage",
                           "angler_name": name})
        if not submissions and row.get("total_fish_length") not in (None, "", "0", "0.00", 0):
            issues.append({"severity": "error", "message": "Scored angler has no submission records", "angler_name": name})
        row_lengths = []
        for fish_index, fish in enumerate(submissions):
            try:
                if not name:
                    raise ValueError("Missing angler name")
                if fish.get("tournament_id") is not None and str(fish["tournament_id"]) != str(meta["id"]):
                    raise ValueError("Catch belongs to a different tournament")
                if str(fish.get("status")) != "1":
                    raise ValueError("Unrecognized or unaccepted catch status; review source record")
                length = Decimal(str(fish.get("fish_length")))
                if not length.is_finite() or length <= 0 or length > Decimal("9999.99"):
                    raise ValueError("Length must be a positive numeric(6,2) value")
                if length != length.quantize(Decimal("0.01")):
                    raise ValueError("Length has more than two decimal places")
                # date_taken is local photo time, unlike date_submitted (UTC).
                # Its interpretation was checked against formatted_date_taken in the snapshot.
                timestamp = _parse_timestamp(fish.get("date_taken") or fish.get("formatted_date_taken") or "")
                if timestamp is None:
                    raise ValueError("Missing or unrecognized photo timestamp")
                catch_zone_name = fish.get("catch_timezone")
                catch_zone = ZoneInfo(TIMEZONES.get(catch_zone_name, catch_zone_name)) if catch_zone_name else zone
                utc = _utc_timestamp(timestamp, catch_zone)
                formatted = _parse_timestamp(fish.get("formatted_date_taken") or "")
                if formatted is not None:
                    formatted_utc = _utc_timestamp(formatted, catch_zone)
                    if formatted_utc.replace(second=0, microsecond=0) != utc.replace(second=0, microsecond=0):
                        raise ValueError("Raw and formatted photo timestamps disagree")
                if utc.astimezone(zone).date() != day:
                    raise ValueError("Photo date differs from the tournament date")
                external_id = str(fish["submission_id"]) if fish.get("submission_id") else None
                if external_id is not None:
                    if external_id in seen_ids:
                        raise ValueError(f"Duplicate source catch ID: {external_id}")
                    seen_ids.add(external_id)
                catches.append({"angler_name": name, "catch_time": utc.isoformat(),
                                "species": _normalize_species(fish.get("fish_type")),
                                "length_inches": str(length.quantize(Decimal("0.01"))),
                                "external_id": external_id})
                row_lengths.append(length)
            except (ValueError, InvalidOperation, KeyError, TypeError) as error:
                issues.append({"severity": "error", "row_index": row_index, "fish_index": fish_index,
                               "angler_name": name, "message": str(error)})
        if row.get("total_fish_length") is not None and len(row_lengths) == len(submissions):
            try:
                if sum(row_lengths, Decimal(0)) != Decimal(str(row["total_fish_length"])):
                    issues.append({"severity": "error", "message": "Fish lengths differ from reported score",
                                   "angler_name": name})
            except InvalidOperation:
                issues.append({"severity": "error", "message": "Unrecognized source score", "angler_name": name})
    if not discovered:
        issues.append({"severity": "error", "message": "No standings fish found; review the source response"})
    no_ids = sum(catch["external_id"] is None for catch in catches)
    if no_ids:
        issues.append({"severity": "warning", "message": f"{no_ids} catches lack a source ID; do not blindly append on reimport"})
    summary = {"source_anglers": len(rows), "anglers_processed": len(processed_rows),
               "anglers_with_fish": sum(bool(row.get("submissions")) for row in processed_rows),
               "fish_discovered": discovered, "fish_exported": len(catches),
               "fish_skipped": discovered - len(catches), "reported_culled_fish": culled_count,
               "unknown_species": sum(catch["species"] is None for catch in catches),
               "missing_external_ids": no_ids,
               "blocking_issues": sum(issue["severity"] == "error" for issue in issues),
               "locations_assigned": bool(locations)}
    summary["ready_for_review"] = summary["blocking_issues"] == 0
    return {"schema_version": 1, "scraped_at": raw["scraped_at"],
            "tournament": {"name": meta["tournament_title"].strip(), "date": day.isoformat(),
                           "timezone": zone_name, "source_url": url,
                           "external_id": str(meta["id"]) if meta.get("id") else None,
                           "catch_coverage": "standings_only",
                           "winning_length_inches": winning_length,
                           "top_10_percent_length_inches": top_10_percent_length},
            "locations": locations, "catches": catches, "summary": summary, "issues": issues}


def scrape_tournament(url, *, config=None, output_path=None, refresh=False,
                      max_anglers=None, headed=False, timeout_ms=30000):
    """Export named fields; reuse only a matching raw snapshot unless refreshed."""
    url = _source_url(url)
    if max_anglers is not None and max_anglers < 1:
        raise ValueError("max_anglers must be positive")
    output_path = Path(output_path or f"output/{url.rsplit('/', 1)[1]}.json")
    if output_path.suffix != ".json":
        raise ValueError("Output path must end in .json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path = output_path.with_suffix(".raw.json")
    if raw_path.exists() and not refresh:
        raw = json.loads(raw_path.read_text())
        if raw.get("source_url") != url:
            raise ValueError("Snapshot URL differs; use --refresh or another output path")
        print(f"Using saved snapshot: {raw_path} (use --refresh to fetch again)")
    else:
        raw = _fetch_snapshot(url, headed, timeout_ms, raw_path)
    # Old HTML runs may have stopped after capturing both complete JSON responses.
    # Reuse those responses, without trusting or requiring the old DOM collection.
    if not isinstance(raw.get("metadata"), dict) or not isinstance(raw.get("standings"), dict):
        raise ValueError("Saved snapshot lacks JSON responses; rerun with --refresh")
    result = _build_export(raw, config or {}, max_anglers=max_anglers)
    _write_json(output_path, result)
    print(f"Export: {output_path}\nReview summary: {json.dumps(result['summary'], indent=2)}")
    return result


def scrape_tourneyx(url, max_anglers=None, cache_path=None):
    """Return local naive tuples for existing plots, using tournament-specific caches."""
    if cache_path is not None:
        raise ValueError("Legacy cache_path is no longer supported; use scrape_tournament(output_path=...) "
                         "or omit cache_path for tournament-specific caching")
    result = scrape_tournament(url, max_anglers=max_anglers)
    # Plotting trials may intentionally limit anglers; other errors remain blocking.
    errors = [issue for issue in result["issues"] if issue["severity"] == "error"
              and issue["message"] != "Partial run: max_anglers was set"]
    if errors:
        raise ValueError("Scrape has blocking issues; inspect its JSON export before plotting")
    zone = ZoneInfo(result["tournament"]["timezone"])
    return [(record["angler_name"], datetime.fromisoformat(record["catch_time"]).astimezone(zone).replace(tzinfo=None),
             float(record["length_inches"]), record["species"]) for record in result["catches"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="TourneyX standings URL")
    parser.add_argument("--config", type=Path, help="JSON with source_url, timezone, and reviewed locations")
    parser.add_argument("--output", type=Path, help="Export path (default: output/<tournament-slug>.json)")
    parser.add_argument("--refresh", action="store_true", help="Fetch again instead of reusing the raw snapshot")
    parser.add_argument("--max-anglers", type=int, help="Partial trial run; marked incomplete")
    parser.add_argument("--headed", action="store_true", help="Show the browser")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config else {}
    result = scrape_tournament(args.url, config=config, output_path=args.output, refresh=args.refresh,
                               max_anglers=args.max_anglers, headed=args.headed, timeout_ms=args.timeout_ms)
    return 0 if result["summary"]["ready_for_review"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
