from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from backend.api.dependencies import DatabaseSession, Weather
from backend.db.models import Catch, Location, Species, Tournament, TournamentLocation
from backend.api.routes.common import Limit, Offset, OptionalId, TournamentId
from backend.api.schemas import CatchResponse, Page, TournamentDetail, TournamentResponse, TournamentWeather
from backend.weather import WeatherProviderError, WeatherTimeout, WeatherUnavailable

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("/{tournament_id}/weather", response_model=TournamentWeather, responses={
    404: {"description": "Tournament not found"},
    409: {"description": "Tournament has no weather coordinates or duration"},
    502: {"description": "Weather provider failed or returned invalid data"},
    503: {"description": "Historical weather is not available yet"},
    504: {"description": "Weather provider timed out"},
})
def get_tournament_weather(tournament_id: TournamentId, session: DatabaseSession, weather: Weather):
    tournament = session.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if any(getattr(tournament, key) is None for key in (
        "weather_latitude", "weather_longitude", "starts_at", "ends_at",
    )):
        raise HTTPException(status_code=409, detail="Tournament weather coordinates and start/end times are required")
    try:
        return weather.get_tournament_weather(tournament)
    except WeatherTimeout:
        raise HTTPException(status_code=504, detail="Weather provider timed out") from None
    except WeatherProviderError:
        raise HTTPException(status_code=502, detail="Weather provider temporarily unavailable") from None
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


def tournament_query():
    catch_count = (
        select(func.count(Catch.id)).where(Catch.tournament_id == Tournament.id)
        .correlate(Tournament).scalar_subquery().label("catch_count")
    )
    return select(*Tournament.__table__.c, catch_count)


@router.get("", response_model=Page[TournamentResponse])
def list_tournaments(
    session: DatabaseSession, limit: Limit = 50, offset: Offset = 0,
    location_id: OptionalId = None,
):
    filters = []
    if location_id is not None:
        filters.append(select(TournamentLocation.tournament_id).where(
            TournamentLocation.tournament_id == Tournament.id,
            TournamentLocation.location_id == location_id,
        ).exists())
    total = session.scalar(select(func.count()).select_from(Tournament).where(*filters))
    rows = session.execute(
        tournament_query().where(*filters).order_by(Tournament.date.desc(), Tournament.id)
        .limit(limit).offset(offset)
    ).mappings().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/{tournament_id}", response_model=TournamentDetail)
def get_tournament(tournament_id: TournamentId, session: DatabaseSession):
    row = session.execute(tournament_query().where(Tournament.id == tournament_id)).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Tournament not found")
    locations = session.execute(
        select(*Location.__table__.c, TournamentLocation.boundary_notes)
        .join(TournamentLocation, TournamentLocation.location_id == Location.id)
        .where(TournamentLocation.tournament_id == tournament_id)
        .order_by(Location.name, Location.id)
    ).mappings().all()
    species_counts = session.execute(
        select(
            Species.name.label("species_name"),
            func.count(Catch.id).label("catch_count"),
            func.avg(Catch.length_inches).label("average_length_inches"),
        )
        .select_from(Catch)
        .outerjoin(Species, Catch.species_id == Species.id)
        .where(Catch.tournament_id == tournament_id)
        .group_by(Species.name).order_by(Species.name)
    ).mappings().all()
    return dict(row) | {
        "locations": locations,
        "species_caught": [item["species_name"] for item in species_counts if item["species_name"] is not None],
        "species_catch_counts": species_counts,
    }


@router.get("/{tournament_id}/catches", response_model=Page[CatchResponse])
def list_catches(
    tournament_id: TournamentId, session: DatabaseSession,
    limit: Limit = 50, offset: Offset = 0, species_id: OptionalId = None,
    angler_id: OptionalId = None,
    angler_name: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
):
    if session.scalar(select(Tournament.id).where(Tournament.id == tournament_id)) is None:
        raise HTTPException(status_code=404, detail="Tournament not found")
    filters = [Catch.tournament_id == tournament_id]
    if species_id is not None:
        filters.append(Catch.species_id == species_id)
    if angler_id is not None:
        filters.append(Catch.angler_id == angler_id)
    if angler_name is not None:
        filters.append(func.lower(Catch.angler_name) == angler_name.lower())
    total = session.scalar(select(func.count()).select_from(Catch).where(*filters))
    rows = session.execute(
        select(*Catch.__table__.c, Species.name.label("species_name"))
        .outerjoin(Species, Catch.species_id == Species.id).where(*filters)
        .order_by(Catch.catch_time, Catch.id).limit(limit).offset(offset)
    ).mappings().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}
