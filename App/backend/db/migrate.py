"""Deployment migrations use an explicit owner URL, never the runtime URL."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.config import load_settings
from backend.db.session import create_db_engine


def main() -> None:
    load_settings()
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError("Set MIGRATION_DATABASE_URL for deployment migrations.")
    engine = create_db_engine(url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
