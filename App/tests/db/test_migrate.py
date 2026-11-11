"""Deployment must never silently migrate using runtime credentials."""

import pytest

from backend.db import migrate


def test_deployment_migrations_require_explicit_owner_url(monkeypatch):
    monkeypatch.setattr(migrate, "load_settings", lambda: None)
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://runtime@localhost/app")
    with pytest.raises(RuntimeError, match="MIGRATION_DATABASE_URL"):
        migrate.main()
