"""Explicit connection configuration; importing this module never connects."""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from backend.config import load_settings


def database_url() -> str:
    # Explicit environment variables take precedence over the local .env file.
    load_settings()
    value = os.environ.get("DATABASE_URL")
    if not value and os.environ.get("RENDER_DATABASE_URL"):
        # Blueprint connection strings use PostgreSQL's default URL scheme.
        url = make_url(os.environ["RENDER_DATABASE_URL"])
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
            raise ValueError("RENDER_DATABASE_URL must be a PostgreSQL URL.")
        value = url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
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
