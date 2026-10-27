"""HTTP request dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.weather import WeatherService


def get_session(request: Request):
    """One session per request; close/rollback without committing any writes."""
    with request.app.state.session_factory() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_session)]


def get_weather_service(request: Request) -> WeatherService:
    return request.app.state.weather_service


Weather = Annotated[WeatherService, Depends(get_weather_service)]
