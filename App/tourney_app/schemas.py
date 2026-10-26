"""Public response contracts, independent of database table definitions."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, field_serializer

Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    items: list[Item]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]


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


class TournamentDetail(TournamentResponse):
    locations: list[TournamentWaterbody]


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
