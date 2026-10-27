from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.main import create_app
from backend.db.models import Base, Catch, Location, Species, Tournament, TournamentLocation


@pytest.fixture
def api_client(connection, monkeypatch):
    # All requests use the test connection/schema, never the app's normal database.
    monkeypatch.setattr("backend.main.create_db_engine", lambda: connection.engine)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    app = create_app()

    def test_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_data(connection):
    def tournament(name, event_date, suffix):
        return connection.scalar(insert(Tournament).values(
            name=name, date=event_date, timezone="America/New_York",
            source_url=f"https://example.test/{suffix}", external_id=suffix,
            winning_length_inches=Decimal("89.25"), top_10_percent_length_inches=Decimal("83.00"),
        ).returning(Tournament.id))

    older = tournament("Earlier event", date(2026, 5, 2), "old")
    newer = tournament("Later event", date(2026, 7, 18), "new")
    tied = tournament("Same date event", date(2026, 7, 18), "tied")
    locations = [connection.scalar(insert(Location).values(name=name, state="PA").returning(Location.id)) for name in ("River", "Bay")]
    for location_id in locations:
        connection.execute(insert(TournamentLocation).values(
            tournament_id=newer, location_id=location_id, boundary_notes="Eligible section",
        ))
    species = connection.scalar(insert(Species).values(name="Smallmouth Bass").returning(Species.id))
    rows = [
        dict(tournament_id=newer, angler_name="Alex Example", species_id=species, external_id="1", length_inches=Decimal("19.25")),
        dict(tournament_id=newer, angler_name="Alex Example", species_id=None, external_id=None, length_inches=Decimal("18.00")),
        dict(tournament_id=newer, angler_name="Other Angler", species_id=species, external_id="3", length_inches=Decimal("20.00")),
    ]
    for row in rows:
        connection.execute(insert(Catch).values(**row, catch_time=datetime(2026, 7, 18, 12, 30, tzinfo=timezone.utc)))
    return {"older": older, "newer": newer, "tied": tied, "locations": locations, "species": species}


def test_health(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/tournaments", "/locations"])
def test_empty_collections(api_client, path):
    response = api_client.get(path)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_tournament_list_counts_order_and_pagination(api_client, sample_data):
    response = api_client.get("/tournaments")
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 3
    assert [row["id"] for row in page["items"]] == [sample_data[key] for key in ("newer", "tied", "older")]
    assert [row["catch_count"] for row in page["items"]] == [3, 0, 0]
    assert page["items"][0]["winning_length_inches"] == "89.25"
    assert page["items"][0]["top_10_percent_length_inches"] == "83.00"
    assert page["items"][0]["date"] == "2026-07-18"
    paged = api_client.get("/tournaments?limit=1&offset=1").json()
    assert paged["total"] == 3 and len(paged["items"]) == 1
    assert paged["items"][0]["id"] == sample_data["tied"]
    beyond = api_client.get("/tournaments?offset=100").json()
    assert beyond["total"] == 3 and beyond["items"] == []


def test_filter_tournaments_by_location(api_client, sample_data):
    for location_id in sample_data["locations"]:
        page = api_client.get(f"/tournaments?location_id={location_id}").json()
        assert page["total"] == 1
        assert page["items"][0]["catch_count"] == 3
    assert api_client.get("/tournaments?location_id=999999").json()["total"] == 0


def test_details_include_waterbody_boundaries(api_client, sample_data):
    response = api_client.get(f"/tournaments/{sample_data['newer']}")
    assert response.status_code == 200
    row = response.json()
    assert row["catch_count"] == 3
    assert [loc["name"] for loc in row["locations"]] == ["Bay", "River"]
    assert all(loc["boundary_notes"] == "Eligible section" for loc in row["locations"])
    assert row["species_caught"] == ["Smallmouth Bass"]
    assert [dict(item, average_length_inches=Decimal(item["average_length_inches"])) for item in row["species_catch_counts"]] == [
        {"species_name": "Smallmouth Bass", "catch_count": 2, "average_length_inches": Decimal("19.625")},
        {"species_name": None, "catch_count": 1, "average_length_inches": Decimal("18.00")},
    ]
    assert api_client.get(f"/tournaments/{sample_data['older']}").json()["locations"] == []
    assert api_client.get(f"/tournaments/{sample_data['older']}").json()["species_caught"] == []
    assert api_client.get(f"/tournaments/{sample_data['older']}").json()["species_catch_counts"] == []


def test_details_include_both_species_from_catches(api_client, connection, sample_data):
    largemouth = connection.scalar(insert(Species).values(name="Largemouth Bass").returning(Species.id))
    connection.execute(insert(Catch).values(
        tournament_id=sample_data["newer"], angler_name="Another Angler",
        species_id=largemouth, length_inches=Decimal("17.50"),
        catch_time=datetime(2026, 7, 18, 13, 0, tzinfo=timezone.utc),
    ))
    response = api_client.get(f"/tournaments/{sample_data['newer']}")
    assert response.status_code == 200
    assert response.json()["species_caught"] == ["Largemouth Bass", "Smallmouth Bass"]
    counts = response.json()["species_catch_counts"]
    assert [dict(item, average_length_inches=Decimal(item["average_length_inches"])) for item in counts] == [
        {"species_name": "Largemouth Bass", "catch_count": 1, "average_length_inches": Decimal("17.50")},
        {"species_name": "Smallmouth Bass", "catch_count": 2, "average_length_inches": Decimal("19.625")},
        {"species_name": None, "catch_count": 1, "average_length_inches": Decimal("18.00")},
    ]
    assert sum(item["catch_count"] for item in response.json()["species_catch_counts"]) == response.json()["catch_count"]


def test_catches_serialization_nullable_species_and_order(api_client, sample_data):
    response = api_client.get(f"/tournaments/{sample_data['newer']}/catches")
    assert response.status_code == 200
    page = response.json()
    rows = page["items"]
    assert page["total"] == 3
    assert [row["id"] for row in rows] == sorted(row["id"] for row in rows)
    assert rows[0]["length_inches"] == "19.25"
    assert rows[0]["catch_time"] == "2026-07-18T12:30:00Z"
    assert rows[0]["species_name"] == "Smallmouth Bass"
    assert rows[1]["species_id"] is None and rows[1]["species_name"] is None
    assert rows[1]["external_id"] is None


def test_catch_filters_and_pagination(api_client, sample_data):
    path = f"/tournaments/{sample_data['newer']}/catches"
    page = api_client.get(path, params={"angler_name": "aLeX ExAmPlE", "limit": 1, "offset": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["items"][0]["length_inches"] == "18.00"
    filtered = api_client.get(path, params={"species_id": sample_data["species"], "angler_name": "Alex Example"}).json()
    assert filtered["total"] == 1
    assert api_client.get(path, params={"angler_name": "Alex"}).json()["total"] == 0
    # User input is a bound exact value, not a wildcard or SQL fragment.
    for value in ("%", "' OR 1=1 --"):
        assert api_client.get(path, params={"angler_name": value}).json()["total"] == 0
    assert api_client.get(path, params={"species_id": 999999}).json()["total"] == 0


def test_existing_tournament_with_no_catches(api_client, sample_data):
    response = api_client.get(f"/tournaments/{sample_data['older']}/catches")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_location_order_and_pagination(api_client, sample_data):
    page = api_client.get("/locations?limit=1&offset=1").json()
    assert page["total"] == 2
    assert page["items"] == [{"id": sample_data["locations"][0], "name": "River", "state": "PA"}]


@pytest.mark.parametrize("path", ["/tournaments/999999", "/tournaments/999999/catches"])
def test_unknown_tournament(api_client, path):
    assert api_client.get(path).status_code == 404


@pytest.mark.parametrize("path", [
    "/tournaments?limit=0", "/tournaments?limit=201", "/tournaments?offset=-1",
    "/locations?offset=bad", "/locations?limit=0", "/tournaments?location_id=0",
    "/tournaments/0", "/tournaments/not-an-id", "/tournaments/1/catches?species_id=-1",
    "/tournaments/1/catches?angler_name=", "/tournaments/1/catches?limit=201",
])
def test_invalid_parameters(api_client, path):
    assert api_client.get(path).status_code == 422


def test_database_failures_do_not_expose_exception_details(api_client):
    broken = Mock()
    error = OperationalError("secret SQL", {"secret": "password"}, RuntimeError("unavailable"))
    broken.execute.side_effect = error
    broken.scalar.side_effect = error

    def broken_session():
        yield broken

    api_client.app.dependency_overrides[get_session] = broken_session
    response = api_client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    response = api_client.get("/locations")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable"}


def test_openapi_docs_and_cors(api_client):
    assert api_client.get("/docs").status_code == 200
    document = api_client.get("/openapi.json").json()
    assert set(document["paths"]) == {"/health", "/tournaments", "/tournaments/{tournament_id}", "/tournaments/{tournament_id}/catches", "/locations"}
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"}
    assert api_client.options("/tournaments", headers=headers).headers["access-control-allow-origin"] == "http://localhost:5173"
    headers["Origin"] = "https://unconfigured.test"
    assert "access-control-allow-origin" not in api_client.options("/tournaments", headers=headers).headers


def test_requests_leave_all_tables_unchanged(api_client, connection, sample_data):
    def snapshot():
        return {table.name: connection.execute(select(table).order_by(*table.primary_key.columns)).all() for table in Base.metadata.sorted_tables}

    before = snapshot()
    for path in ("/health", "/tournaments", "/locations", f"/tournaments/{sample_data['newer']}", f"/tournaments/{sample_data['newer']}/catches"):
        assert api_client.get(path).status_code == 200
    assert api_client.post("/tournaments", json={"name": "Unwanted write"}).status_code == 405
    assert snapshot() == before


def test_app_lifecycle_disposes_engine_and_cors_is_configurable(monkeypatch):
    engine = Mock()
    monkeypatch.setattr("backend.main.create_db_engine", lambda: engine)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://frontend.test")
    with TestClient(create_app()) as client:
        assert not engine.dispose.called
        headers = {"Origin": "https://frontend.test", "Access-Control-Request-Method": "GET"}
        assert client.options("/locations", headers=headers).headers["access-control-allow-origin"] == "https://frontend.test"
    engine.dispose.assert_called_once()
