from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import httpx
import pytest

from backend.api.dependencies import get_session
from backend.api.main import create_app
from backend.weather import VARIABLES, WeatherProviderError, WeatherService, WeatherUnavailable

UTC = timezone.utc
DAY = datetime(2026, 7, 18, tzinfo=UTC)


def tournament(**changes):
    return SimpleNamespace(**(dict(
        id=1, timezone="America/New_York", starts_at=DAY + timedelta(hours=9, minutes=45),
        ends_at=DAY + timedelta(hours=18, minutes=30),
        weather_latitude=41.09588, weather_longitude=-79.68106,
    ) | changes))


@pytest.fixture
def payload():
    return dict(latitude=41.1, longitude=-79.7,
                hourly_units={"time": "unixtime"} | {provider: unit for provider, _, unit in VARIABLES},
                hourly={"time": [int((DAY + timedelta(hours=i)).timestamp()) for i in range(24)],
                        "temperature_2m": [72.5] * 24, "pressure_msl": [1015.2] * 24,
                        "cloud_cover": [25] * 24, "wind_speed_10m": [8.2] * 24,
                        "wind_direction_10m": [270] * 24})


def service(payload, **kwargs):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=payload)
    return WeatherService(httpx.Client(transport=httpx.MockTransport(respond)), **kwargs), calls


def test_units_utc_hours_filtering_and_cache(payload):
    weather, calls = service(payload)
    result = weather.get_tournament_weather(tournament())
    assert result.coverage == "complete"
    assert [row.time.hour for row in result.hourly] == list(range(10, 19))
    assert result.hourly[0].temperature_f == 72.5
    assert result.hourly[0].pressure_hpa == 1015.2
    assert result.hourly[0].wind_direction_degrees == 270
    assert result.requested_coordinates.latitude == 41.09588
    assert result.grid_coordinates.latitude == 41.1
    request = calls[0]
    assert str(request.url).startswith("https://archive-api.open-meteo.com/v1/archive?")
    assert request.url.params["hourly"] == ",".join(row[0] for row in VARIABLES)
    for key, value in dict(timezone="GMT", timeformat="unixtime", temperature_unit="fahrenheit",
                           wind_speed_unit="mph", start_date="2026-07-18", end_date="2026-07-18").items():
        assert request.url.params[key] == value
    repeated = weather.get_tournament_weather(tournament())
    assert repeated.fetched_at == result.fetched_at and len(calls) == 1
    # Cache full UTC days, then filter independently for another event's hours.
    shorter = weather.get_tournament_weather(tournament(id=2, starts_at=DAY + timedelta(hours=12)))
    assert shorter.hourly[0].time.hour == 12 and len(calls) == 1


def test_offset_timestamps_and_utc_date_boundaries(payload):
    weather, calls = service(payload)
    offset = timezone(timedelta(hours=-4))
    result = weather.get_tournament_weather(tournament(
        starts_at=datetime(2026, 7, 17, 23, 30, tzinfo=offset),
        ends_at=datetime(2026, 7, 18, 1, 0, tzinfo=offset),
    ))
    assert calls[0].url.params["start_date"] == "2026-07-18"
    assert [row.time.hour for row in result.hourly] == [4, 5]


@pytest.mark.parametrize("change", [
    lambda p: p["hourly"]["cloud_cover"].pop(),
    lambda p: p["hourly"].update(time=[1] * 24),
    lambda p: p["hourly"]["time"].reverse(),
    lambda p: p["hourly_units"].update(temperature_2m="°C"),
    lambda p: p["hourly"]["cloud_cover"].__setitem__(10, 101),
    lambda p: p["hourly"]["wind_speed_10m"].__setitem__(10, -1),
    lambda p: p["hourly"]["temperature_2m"].__setitem__(10, True),
    lambda p: p.pop("latitude"),
])
def test_invalid_provider_responses_are_not_cached(payload, change):
    change(payload)
    weather, calls = service(payload)
    for _ in range(2):
        with pytest.raises(WeatherProviderError):
            weather.get_tournament_weather(tournament())
    assert len(calls) == 2


def test_nulls_are_preserved_and_partial_results_expire_soon(payload):
    payload["hourly"]["pressure_msl"][10] = None
    now = [0]
    weather, calls = service(payload, clock=lambda: now[0])
    result = weather.get_tournament_weather(tournament())
    assert result.coverage == "partial" and result.hourly[0].pressure_hpa is None
    now[0] = 301
    weather.get_tournament_weather(tournament())
    assert len(calls) == 2


def test_empty_weather_is_not_cached(payload):
    for provider, _, _ in VARIABLES:
        payload["hourly"][provider] = [None] * 24
    weather, calls = service(payload)
    for _ in range(2):
        with pytest.raises(WeatherUnavailable):
            weather.get_tournament_weather(tournament())
    assert len(calls) == 2


def test_cache_expiry_and_capacity(payload):
    now = [0]
    weather, calls = service(payload, cache_size=1, cache_ttl=60, clock=lambda: now[0])
    weather.get_tournament_weather(tournament())
    now[0] = 61
    weather.get_tournament_weather(tournament())
    weather.get_tournament_weather(tournament(weather_latitude=42))
    weather.get_tournament_weather(tournament())
    assert len(calls) == 4


def test_future_event_does_not_request_historical_weather(payload):
    weather, calls = service(payload)
    with pytest.raises(WeatherUnavailable):
        weather.get_tournament_weather(tournament(ends_at=datetime.now(UTC) + timedelta(days=2)))
    assert not calls


@pytest.fixture
def weather_api(monkeypatch, payload):
    monkeypatch.setattr("backend.api.main.create_db_engine", Mock)
    weather, calls = service(payload)
    session = Mock()
    session.get.return_value = tournament()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        app.state.weather_service = weather
        yield client, session, calls


def test_weather_endpoint_serialization(weather_api):
    client, _, calls = weather_api
    response = client.get("/tournaments/1/weather")
    assert response.status_code == 200
    data = response.json()
    assert data["hourly"][0]["time"] == "2026-07-18T10:00:00Z"
    assert data["starts_at"] == "2026-07-18T09:45:00Z"
    assert data["data_kind"] == "historical_reanalysis"
    assert data["attribution"] == "Weather data by Open-Meteo, CC BY 4.0"
    assert data["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert data["modifications"] == "Filtered to tournament hours; fields renamed."
    assert client.get("/tournaments/1/weather").json() == data
    assert len(calls) == 1


def test_unknown_and_unconfigured_tournament(weather_api):
    client, session, calls = weather_api
    session.get.return_value = None
    assert client.get("/tournaments/999/weather").status_code == 404
    session.get.return_value = tournament(weather_latitude=None)
    assert client.get("/tournaments/1/weather").status_code == 409
    assert client.get("/tournaments/0/weather").status_code == 422
    assert not calls


@pytest.mark.parametrize("failure, status", [
    (httpx.ReadTimeout("secret provider detail"), 504),
    (httpx.ConnectError("secret provider detail"), 502),
    (httpx.Response(429, json={"reason": "secret provider detail"}), 502),
    (httpx.Response(200, content="not JSON"), 502),
    (httpx.Response(200, json={}), 502),
])
def test_weather_endpoint_provider_errors(weather_api, failure, status):
    client, _, _ = weather_api
    def respond(request):
        if isinstance(failure, Exception):
            raise failure
        return failure
    client.app.state.weather_service = WeatherService(httpx.Client(transport=httpx.MockTransport(respond)))
    response = client.get("/tournaments/1/weather")
    assert response.status_code == status
    assert "secret" not in response.text


def test_weather_endpoint_unavailable_data(weather_api, payload):
    client, _, _ = weather_api
    for provider, _, _ in VARIABLES:
        payload["hourly"][provider] = [None] * 24
    assert client.get("/tournaments/1/weather").status_code == 503
