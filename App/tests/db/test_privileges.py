"""Verify deployment grants against migrated PostgreSQL, including future objects."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.main import app


def test_runtime_and_importer_permissions(connection):
    schema = connection.execute(text("SELECT current_schema()")).scalar_one()
    api = "api_" + uuid4().hex
    importer = "import_" + uuid4().hex
    connection.execute(text(f'CREATE ROLE "{api}" NOLOGIN'))
    connection.execute(text(f'CREATE ROLE "{importer}" NOLOGIN'))
    script = (Path(__file__).resolve().parents[2] / "deploy/database-grants.sql").read_text()
    script = "\n".join(line for line in script.splitlines()
                       if not line.startswith(("--", "\\")))
    script = script.replace(':"api_role"', f'"{api}"')
    script = script.replace(':"importer_role"', f'"{importer}"')
    script = script.replace("public", f'"{schema}"')
    for statement in script.split(";"):
        if statement.strip() and statement.strip() not in {"BEGIN", "COMMIT"}:
            connection.execute(text(statement))
    connection.execute(text("CREATE TABLE permission_probe (id bigint GENERATED ALWAYS AS IDENTITY, value text)"))

    def denied(statement):
        with pytest.raises(DBAPIError) as error:
            with connection.begin_nested():
                connection.execute(text(statement))
        assert error.value.orig.sqlstate == "42501"

    connection.execute(text(f'SET LOCAL ROLE "{api}"'))
    with Session(bind=connection) as session:
        app.dependency_overrides[get_session] = lambda: session
        try:
            with TestClient(app) as client:
                for path in ("/health", "/tournaments", "/locations"):
                    assert client.get(path).status_code == 200
        finally:
            app.dependency_overrides.pop(get_session, None)
    connection.execute(text("SELECT * FROM permission_probe"))
    denied("INSERT INTO permission_probe (value) VALUES ('blocked')")
    denied("UPDATE tournaments SET name = name")
    denied("DELETE FROM catches")
    denied("CREATE TABLE forbidden (id int)")
    denied("ALTER TABLE tournaments ADD COLUMN forbidden int")
    denied("SELECT nextval('permission_probe_id_seq')")
    connection.execute(text("RESET ROLE"))

    connection.execute(text(f'SET LOCAL ROLE "{importer}"'))
    connection.execute(text("INSERT INTO permission_probe (value) VALUES ('allowed')"))
    connection.execute(text("UPDATE permission_probe SET value = 'updated'"))
    connection.execute(text("DELETE FROM permission_probe"))
    denied("UPDATE alembic_version SET version_num = 'forbidden'")
    denied("TRUNCATE tournaments CASCADE")
    denied("CREATE TABLE forbidden (id int)")
    denied("ALTER TABLE tournaments ADD COLUMN forbidden int")
    connection.execute(text("RESET ROLE"))
