"""Exercise real PostgreSQL in an isolated, randomly named test schema."""

import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text

from tourney_app.db import create_db_engine


@pytest.fixture(scope="session")
def migrated_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests.")
    engine = create_db_engine(url)
    schema = "test_" + uuid4().hex
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.connect() as connection:
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.commit()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            yield connection, config
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            connection.commit()
            engine.dispose()


@pytest.fixture
def connection(migrated_database):
    conn, _ = migrated_database
    transaction = conn.begin()
    try:
        yield conn
    finally:
        transaction.rollback()
