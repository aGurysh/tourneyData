"""Historical Open-Meteo acquisition, validation, and a bounded process-local cache."""

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

import httpx
from pydantic import ValidationError

from backend.api.schemas import TournamentWeather, WeatherCoordinates, WeatherHour

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Provider name, public name, expected provider unit.
VARIABLES = (
    ("temperature_2m", "temperature_f", "°F"),
    ("pressure_msl", "pressure_hpa", "hPa"),
    ("cloud_cover", "cloud_cover_percent", "%"),
    ("wind_speed_10m", "wind_speed_mph", "mp/h"),
    ("wind_direction_10m", "wind_direction_degrees", "°"),
)


class WeatherProviderError(Exception):
    """Provider failed or returned an invalid response."""


class WeatherTimeout(WeatherProviderError):
    """Provider did not respond in time."""


class WeatherUnavailable(Exception):
    """Historical data is not available for the requested hours."""


def parse_archive(data):
    """Reject misaligned arrays, wrong units and invalid values; retain real nulls."""
    try:
        coordinates = WeatherCoordinates(latitude=data["latitude"], longitude=data["longitude"])
        hourly, units = data["hourly"], data["hourly_units"]
        times = hourly["time"]
        if not isinstance(times, list) or units["time"] != "unixtime":
            raise ValueError
        for provider, _, unit in VARIABLES:
            if (units[provider] != unit or not isinstance(hourly[provider], list)
                    or len(hourly[provider]) != len(times)):
                raise ValueError
        rows = []
        for index, value in enumerate(times):
            if type(value) is not int or value % 3600:
                raise ValueError
            instant = datetime.fromtimestamp(value, timezone.utc)
            if rows and instant <= rows[-1].time:
                raise ValueError
            values = {public: hourly[provider][index] for provider, public, _ in VARIABLES}
            if any(value is not None and type(value) not in (int, float) for value in values.values()):
                raise ValueError
            rows.append(WeatherHour(time=instant, **values))
        return coordinates, rows
    except (KeyError, TypeError, ValueError, OverflowError, OSError, ValidationError) as exc:
        raise WeatherProviderError("Invalid response from weather provider") from exc


class WeatherService:
    def __init__(self, client: httpx.Client, *, cache_ttl=86400, cache_size=128, clock=monotonic):
        self.client = client
        self.cache_ttl = cache_ttl
        self.cache_size = cache_size
        self.clock = clock
        self._cache = OrderedDict()
        self._lock = Lock()

    def get_tournament_weather(self, tournament) -> TournamentWeather:
        starts_at = tournament.starts_at.astimezone(timezone.utc)
        ends_at = tournament.ends_at.astimezone(timezone.utc)
        if ends_at > datetime.now(timezone.utc):
            raise WeatherUnavailable("Historical weather is not yet available for this tournament")
        coordinates = WeatherCoordinates(
            latitude=tournament.weather_latitude, longitude=tournament.weather_longitude,
        )
        # Query UTC days to avoid provider timezone/DST ambiguity; filter afterwards.
        key = (coordinates.latitude, coordinates.longitude, starts_at.date(), ends_at.date())
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached[0] > self.clock():
                self._cache.move_to_end(key)
            else:
                self._cache.pop(key, None)
                cached = None
        if cached is None:
            try:
                response = self.client.get(ARCHIVE_URL, params={
                    "latitude": coordinates.latitude, "longitude": coordinates.longitude,
                    "start_date": starts_at.date().isoformat(), "end_date": ends_at.date().isoformat(),
                    "hourly": ",".join(item[0] for item in VARIABLES),
                    "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
                    "timezone": "GMT", "timeformat": "unixtime",
                })
                response.raise_for_status()
                grid, rows = parse_archive(response.json())
            except httpx.TimeoutException as exc:
                raise WeatherTimeout("Weather provider timed out") from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise WeatherProviderError("Weather provider request failed") from exc
            cached = (self.clock() + self.cache_ttl, datetime.now(timezone.utc), grid, rows)

        _, fetched_at, grid, rows = cached
        selected = [row for row in rows if starts_at <= row.time <= ends_at]
        if not selected or not any(
            getattr(row, public) is not None for row in selected for _, public, _ in VARIABLES
        ):
            # Empty/all-null data can reflect archive lag. Do not cache it.
            raise WeatherUnavailable("No historical weather available during the tournament hours")
        first_hour = starts_at.replace(minute=0, second=0, microsecond=0)
        if first_hour < starts_at:
            first_hour += timedelta(hours=1)
        expected = int((ends_at - first_hour).total_seconds() // 3600) + 1
        complete = len(selected) == expected and all(
            getattr(row, public) is not None for row in selected for _, public, _ in VARIABLES
        )
        # Partial results expire quickly so archive gaps can fill in.
        if not complete:
            cached = (min(cached[0], self.clock() + 300), *cached[1:])
        with self._lock:
            self._cache[key] = cached
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return TournamentWeather(
            tournament_id=tournament.id, timezone=tournament.timezone,
            starts_at=starts_at, ends_at=ends_at,
            requested_coordinates=coordinates, grid_coordinates=grid, fetched_at=fetched_at,
            coverage="complete" if complete else "partial", hourly=selected,
        )
