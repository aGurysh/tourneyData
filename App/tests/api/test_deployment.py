"""Exercise the authentication boundary and production URL layout."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.db.session import database_url
from backend.deployment import create_deployment_app


@pytest.fixture
def preview(monkeypatch, tmp_path):
    monkeypatch.setenv("DEPLOYMENT_ACCESS", "private")
    monkeypatch.setenv("PREVIEW_USERNAME", "owner")
    monkeypatch.setenv("PREVIEW_PASSWORD", "preview-test-password")
    (tmp_path / "index.html").write_text("<html>tournament preview</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('preview')")
    app = create_deployment_app(frontend_dir=tmp_path)
    session = Mock()
    app.dependency_overrides[get_session] = lambda: session
    # No lifespan here: these boundary checks do not need a database connection.
    return app, TestClient(app), session, tmp_path


@pytest.mark.parametrize("path", ["/", "/index.html", "/assets/app.js", "/api/tournaments",
                                      "/api/health", "/docs", "/openapi.json", "/tournaments"])
def test_preview_protects_all_content(preview, path):
    _, client, session, _ = preview
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic ")
    assert response.headers["cache-control"] == "no-store"
    session.execute.assert_not_called()


@pytest.mark.parametrize("authorization", ["Bearer token", "Basic ???", "Basic /w==",
                                             "Basic bm9jb2xvbg==", "Basic "])
def test_malformed_credentials_are_rejected(preview, authorization):
    assert preview[1].get("/", headers={"Authorization": authorization}).status_code == 401


@pytest.mark.parametrize("auth", [("owner", "wrong"), ("wrong", "preview-test-password"),
                                    ("", ""), ("øwner", "preview-test-password")])
def test_wrong_credentials_are_rejected(preview, auth):
    assert preview[1].get("/", auth=auth).status_code == 401


def test_authenticated_browser_and_api(preview):
    _, client, _, _ = preview
    client.auth = ("owner", "preview-test-password")
    response = client.get("/")
    assert response.status_code == 200
    assert "tournament preview" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/api/health").json() == {"status": "ok"}
    assert "/api/tournaments" in client.get("/openapi.json").json()["paths"]
    for path in ("/assets/missing.js", "/api/missing", "/tournaments", "/backend/config.py"):
        assert client.get(path).status_code == 404


def test_only_exact_health_probe_is_public(preview):
    _, client, session, _ = preview
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/").status_code == 401
    assert client.post("/health").status_code == 401
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("offline"))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.parametrize("mode, username, password", [
    ("private", "", "secret"), ("private", "owner", ""), ("private", "bad:name", "secret"),
    ("typo", "owner", "secret"),
])
def test_bad_configuration_fails_closed(preview, monkeypatch, mode, username, password):
    monkeypatch.setenv("DEPLOYMENT_ACCESS", mode)
    monkeypatch.setenv("PREVIEW_USERNAME", username)
    monkeypatch.setenv("PREVIEW_PASSWORD", password)
    with pytest.raises(RuntimeError):
        create_deployment_app(frontend_dir=preview[3])


def test_private_is_default(preview, monkeypatch):
    monkeypatch.delenv("DEPLOYMENT_ACCESS")
    monkeypatch.setenv("PREVIEW_PASSWORD", "")
    with pytest.raises(RuntimeError, match="Private deployment"):
        create_deployment_app(frontend_dir=preview[3])


def test_public_release_requires_explicit_setting(preview, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_ACCESS", "public")
    app = create_deployment_app(frontend_dir=preview[3])
    assert TestClient(app).get("/").status_code == 200


def test_missing_frontend_fails_at_startup(preview, tmp_path):
    with pytest.raises(RuntimeError, match="Build the frontend"):
        create_deployment_app(frontend_dir=tmp_path / "missing")


def test_production_api_reads_postgres(preview, connection, monkeypatch):
    app, _, _, _ = preview
    monkeypatch.setattr("backend.api.main.create_db_engine", lambda: connection.engine)

    def test_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        response = client.get("/api/tournaments", auth=("owner", "preview-test-password"))
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
        assert client.get("/health").status_code == 200


def test_render_database_url_uses_psycopg_without_losing_credentials(monkeypatch):
    monkeypatch.setattr("backend.db.session.load_settings", lambda: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RENDER_DATABASE_URL", "postgresql://owner:p%40ss%3Aword@db/tourney?sslmode=require")
    assert database_url() == "postgresql+psycopg://owner:p%40ss%3Aword@db/tourney?sslmode=require"
    explicit = "postgresql+psycopg://reader:secret@db/tourney"
    monkeypatch.setenv("DATABASE_URL", explicit)
    assert database_url() == explicit


def test_explicit_database_url_still_requires_correct_driver(monkeypatch):
    monkeypatch.setattr("backend.db.session.load_settings", lambda: None)
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:secret@db/tourney")
    with pytest.raises(ValueError, match="postgresql\\+psycopg"):
        database_url()
