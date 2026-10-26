"""Explicit connection configuration; importing this module never connects."""

import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

APP_ROOT = Path(__file__).resolve().parents[1]


def database_url() -> str:
    # Explicit environment variables take precedence over the local .env file.
    load_dotenv(APP_ROOT / ".env", override=False)
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("Set DATABASE_URL or copy App/.env.example to App/.env.")
    if make_url(value).drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use the postgresql+psycopg:// driver.")
    return value


def create_db_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or database_url(),
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 5},
    )


def get_session(request: Request):
    """One session per request; close/rollback without committing any writes."""
    with request.app.state.session_factory() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_session)]
