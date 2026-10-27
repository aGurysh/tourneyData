"""Public response contracts, independent of database table definitions."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_serializer

Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    items: list[Item]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]


class WeatherCoordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class WeatherHour(BaseModel):
    time: datetime
    temperature_f: float | None = Field(allow_inf_nan=False)
    pressure_hpa: float | None = Field(gt=0, allow_inf_nan=False)
    cloud_cover_percent: float | None = Field(ge=0, le=100, allow_inf_nan=False)
    wind_speed_mph: float | None = Field(ge=0, allow_inf_nan=False)
    wind_direction_degrees: float | None = Field(ge=0, le=360, allow_inf_nan=False)


class TournamentWeather(BaseModel):
    tournament_id: int
    source: Literal["Open-Meteo"] = "Open-Meteo"
    source_url: str = "https://open-meteo.com/"
    attribution: str = "Weather data by Open-Meteo, CC BY 4.0"
    data_kind: Literal["historical_reanalysis"] = "historical_reanalysis"
    timezone: str
    starts_at: datetime
    ends_at: datetime
    requested_coordinates: WeatherCoordinates
    grid_coordinates: WeatherCoordinates
    fetched_at: datetime
    coverage: Literal["complete", "partial"]
    hourly: list[WeatherHour]


class LocationResponse(BaseModel):
    id: int
    name: str
    state: str | None


class TournamentWaterbody(LocationResponse):
    boundary_notes: str | None


class TournamentResponse(BaseModel):
    id: int
    name: str
    date: date
    timezone: str
    source_url: str
    external_id: str | None
    catch_coverage: str
    winning_length_inches: Decimal | None
    top_10_percent_length_inches: Decimal | None
    catch_count: int
    starts_at: datetime | None
    ends_at: datetime | None
    weather_latitude: float | None
    weather_longitude: float | None


class SpeciesCatchCount(BaseModel):
    species_name: str | None
    catch_count: int
    average_length_inches: Decimal


class TournamentDetail(TournamentResponse):
    locations: list[TournamentWaterbody]
    species_caught: list[str]
    species_catch_counts: list[SpeciesCatchCount]


class CatchResponse(BaseModel):
    id: int
    tournament_id: int
    angler_name: str
    catch_time: datetime
    species_id: int | None
    species_name: str | None
    length_inches: Decimal
    external_id: str | None

    @field_serializer("catch_time")
    def serialize_catch_time(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
