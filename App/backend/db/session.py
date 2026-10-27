"""Explicit connection configuration; importing this module never connects."""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from backend.config import load_settings


def database_url() -> str:
    # Explicit environment variables take precedence over the local .env file.
    load_settings()
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
