"""Export reviewable TourneyX standings data; legacy plotting adapter."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Root scripts share the backend implementation without requiring an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parent / "App"))
from backend.ingestion.source import (
    _source_url, _write_json, _normalize_species, _parse_timestamp,
    _utc_timestamp, _source_rows, _standings_lengths, _fetch_snapshot, _build_export,
)

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
