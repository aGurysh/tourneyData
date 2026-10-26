"""Scrape catch data from a TourneyX standings page.

The returned catch records have the shape
``(angler_name, timestamp, length, species)``.
Timestamps are naive ``datetime`` objects in the local tournament time zone,
matching the format used by the existing plotting scripts.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


def _load_cached_catches(cache_path):
    """Load cached JSON records and convert ISO timestamps to datetimes."""
    with Path(cache_path).open("r") as cache_file:
        cached_catches = json.load(cache_file)

    # A cache from the original scraper has no species field. Returning None
    # for those records lets the caller decide whether the cache is usable.
    return [
        (
            record[0],
            datetime.fromisoformat(record[1]),
            record[2],
            record[3] if len(record) > 3 else None,
        )
        for record in cached_catches
    ]


def _save_catches(catches, cache_path):
    """Save catch records in a JSON-serializable format."""
    with Path(cache_path).open("w") as cache_file:
        json.dump(
            [
                (angler, timestamp.isoformat(), length, species)
                for angler, timestamp, length, species in catches
            ],
            cache_file,
            indent=2,
        )


def _parse_timestamp(tooltip_text):
    """Extract a datetime from a TourneyX fish tooltip."""
    match = re.search(r"Picture Taken: (.*?) Eastern", tooltip_text)
    if not match:
        return None

    timestamp_text = match.group(1).replace("am", "AM").replace("pm", "PM")
    timestamp_text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", timestamp_text)

    try:
        return datetime.strptime(timestamp_text, "%b %d, %Y %I:%M %p")
    except ValueError:
        return None


def _normalize_species(species):
    """Normalize TourneyX species labels to the app's species categories."""
    if species is None:
        return None
    if species.strip().casefold() == "bass":
        return "Largemouth Bass"
    return species.strip()


def scrape_tourneyx(url, max_anglers=None, cache_path="catches.json"):
    """Return catch records scraped from a TourneyX standings page.

    If ``cache_path`` exists, it is used instead of opening a browser. Set
    ``cache_path`` to ``None`` to disable caching.
    """
    if cache_path is not None and Path(cache_path).exists():
        print(f"Loading cached data from {cache_path}...")
        cached_catches = _load_cached_catches(cache_path)
        if all(species is not None for *_, species in cached_catches):
            return cached_catches
        print("Cached data has no species field; refreshing it from TourneyX...")

    print("Scraping data with Playwright...")
    catches = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )

        page.goto(url)
        page.wait_for_timeout(2000)

        rows = page.query_selector_all("tr.standing-user-list")
        angler_count = 0
        for row in rows:
            angler_cell = row.query_selector("td.standings-angler span.angler-name")
            if not angler_cell:
                continue
            if max_anglers is not None and angler_count >= max_anglers:
                break
            angler_count += 1

            angler_name = angler_cell.inner_text().strip()
            fish_divs = [
                fish_div
                for fish_div in row.query_selector_all(".standings-fish-score")
                if fish_div.inner_text().strip()
            ]

            print(f"Angler: {angler_name}, Fish Count: {len(fish_divs)}")
            for fish_div in fish_divs:
                length_text = fish_div.inner_text().strip().replace('"', "")
                try:
                    length = float(length_text)
                except ValueError:
                    continue

                fish_cell = fish_div.query_selector("xpath=..")
                species_element = (
                    fish_cell.query_selector(".standings-fish-accepted small")
                    if fish_cell
                    else None
                )
                species = (
                    _normalize_species(species_element.inner_text())
                    if species_element
                    else None
                )

                fish_div.hover()
                page.wait_for_timeout(200)
                tooltip = page.query_selector("div.tooltip")
                tooltip_text = tooltip.inner_text().strip() if tooltip else ""
                timestamp = _parse_timestamp(tooltip_text)
                if timestamp is not None:
                    catches.append((angler_name, timestamp, length, species))

        browser.close()

    if cache_path is not None:
        _save_catches(catches, cache_path)
        print(f"Data saved to {cache_path}")

    return catches
