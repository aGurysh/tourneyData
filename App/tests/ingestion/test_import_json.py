from copy import deepcopy
from decimal import Decimal
import json

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from backend.ingestion.validation import ImportError, load_export
from backend.ingestion.importer import import_export
from backend.ingestion.cli import main
from backend.db.models import Catch, Location, Species, Tournament, TournamentLocation


@pytest.fixture
def export_data():
    return {
        "schema_version": 1,
        "scraped_at": "2026-10-26T16:00:00Z",
        "tournament": {
            "name": "Test event", "date": "2026-07-18", "timezone": "America/New_York",
            "source_url": "https://tourneyx.com/leaderboard/standings/test-event",
            "external_id": "event-1", "catch_coverage": "standings_only",
            "winning_length_inches": "19.25", "top_10_percent_length_inches": "19.25",
        },
        "locations": [{"name": "Test River", "state": "pa", "boundary_notes": "Upstream section"}],
        "catches": [{"angler_name": "Test Angler", "catch_time": "2026-07-18T08:30:00-04:00",
                     "species": "Bass", "length_inches": "19.25", "external_id": "catch-1"}],
        "summary": {"ready_for_review": True, "blocking_issues": 0, "source_anglers": 1,
                    "anglers_processed": 1, "fish_discovered": 1, "fish_exported": 1, "fish_skipped": 0},
        "issues": [],
    }


@pytest.fixture
def read_export(tmp_path):
    def read(data):
        path = tmp_path / "export.json"
        path.write_text(json.dumps(data))
        return load_export(path)
    return read


@pytest.mark.parametrize("change", [
    lambda d: d.update(schema_version=2),
    lambda d: d["summary"].update(ready_for_review=False),
    lambda d: d["summary"].update(fish_exported=2),
    lambda d: d["summary"].update(anglers_processed=0),
    lambda d: d["summary"].update(fish_skipped=1),
    lambda d: d["issues"].append({"severity": "error", "message": "Partial run"}),
    lambda d: d["tournament"].update(timezone="Not/A_Zone"),
    lambda d: d["catches"][0].update(catch_time="2026-07-18T08:30:00"),
    lambda d: d["catches"][0].update(length_inches="19.251"),
    lambda d: d["catches"][0].update(length_inches="NaN"),
    lambda d: d["catches"].append(deepcopy(d["catches"][0])),
])
def test_invalid_exports_rejected_before_database_access(export_data, read_export, change):
    change(export_data)
    with pytest.raises(ImportError):
        read_export(export_data)


def test_validation_normalizes_values(export_data, read_export):
    export = read_export(export_data)
    assert export.locations[0]["state"] == "PA"
    assert export.catches[0]["species"] == "Largemouth Bass"
    assert export.catches[0]["length_inches"] == Decimal("19.25")
    assert export.catches[0]["catch_time"].isoformat() == "2026-07-18T12:30:00+00:00"


def test_preview_writes_nothing(connection, export_data, read_export):
    plan = import_export(connection, read_export(export_data))
    assert plan["action"] == "create" and plan["applied"] is False
    for model in (Tournament, Catch, Location, Species, TournamentLocation):
        assert connection.scalar(select(func.count()).select_from(model)) == 0


def test_import_repeat_guard_and_replacement(connection, export_data, read_export):
    export = read_export(export_data)
    first = import_export(connection, export, apply=True)
    with pytest.raises(ImportError, match="already exists"):
        import_export(connection, export, apply=True)
    export_data["tournament"]["name"] = "Updated event"
    export_data["catches"][0]["length_inches"] = "20.00"
    export_data["locations"][0]["boundary_notes"] = "Updated boundary"
    updated = read_export(export_data)
    preview = import_export(connection, updated, replace=True)
    assert preview["existing_catches"] == 1
    assert connection.scalar(select(Catch.length_inches)) == Decimal("19.25")
    result = import_export(connection, updated, apply=True, replace=True)
    assert result["tournament_id"] == first["tournament_id"]
    assert connection.scalar(select(Catch.length_inches)) == Decimal("20.00")
    assert connection.scalar(select(Tournament.name)) == "Updated event"
    assert connection.scalar(select(TournamentLocation.boundary_notes)) == "Updated boundary"
    for model in (Tournament, Catch, Location, Species, TournamentLocation):
        assert connection.scalar(select(func.count()).select_from(model)) == 1


def test_missing_source_ids_and_unknown_species(connection, export_data, read_export):
    export_data["catches"][0].update(external_id=None, species=None)
    export = read_export(export_data)
    assert len(export.warnings) == 2
    import_export(connection, export, apply=True)
    import_export(connection, export, apply=True, replace=True)
    assert connection.scalar(select(func.count()).select_from(Catch)) == 1
    row = connection.execute(select(Catch.__table__)).one()
    assert row.external_id is None and row.species_id is None


def test_existing_lookups_reused_across_events(connection, export_data, read_export):
    import_export(connection, read_export(export_data), apply=True)
    export_data["tournament"].update(source_url="https://example.test/second", external_id="event-2")
    import_export(connection, read_export(export_data), apply=True)
    assert connection.scalar(select(func.count()).select_from(Tournament)) == 2
    assert connection.scalar(select(func.count()).select_from(Location)) == 1
    assert connection.scalar(select(func.count()).select_from(Species)) == 1


def test_ambiguous_location_requires_explicit_id(connection, export_data, read_export):
    ids = [connection.scalar(insert(Location).values(name="Test River", state="PA").returning(Location.id)) for _ in range(2)]
    with pytest.raises(ImportError, match="Ambiguous location"):
        import_export(connection, read_export(export_data), apply=True)
    assert connection.scalar(select(func.count()).select_from(Tournament)) == 0
    export_data["locations"][0]["id"] = ids[1]
    import_export(connection, read_export(export_data), apply=True)
    assert connection.scalar(select(TournamentLocation.location_id)) == ids[1]


def test_identity_conflict_is_rejected(connection, export_data, read_export):
    import_export(connection, read_export(export_data), apply=True)
    export_data["tournament"]["external_id"] = "different-id"
    with pytest.raises(ImportError, match="conflicts"):
        import_export(connection, read_export(export_data), apply=True, replace=True)


def test_database_failure_rolls_back_replacement(connection, export_data, read_export):
    import_export(connection, read_export(export_data), apply=True)
    modified = read_export(export_data)
    modified.tournament["name"] = "Must roll back"
    # Force a database constraint failure after old catches/links are deleted.
    modified.catches[0]["length_inches"] = Decimal("0")
    with pytest.raises(IntegrityError), connection.begin_nested():
        import_export(connection, modified, apply=True, replace=True)
    assert connection.scalar(select(Tournament.name)) == "Test event"
    assert connection.scalar(select(Catch.length_inches)) == Decimal("19.25")
    assert connection.scalar(select(func.count()).select_from(TournamentLocation)) == 1


def test_cli_rejects_raw_json_without_connecting(tmp_path, monkeypatch, capsys):
    path = tmp_path / "raw.json"
    path.write_text('{"standings": []}')
    monkeypatch.setattr("backend.ingestion.cli.create_db_engine", lambda: pytest.fail("Must not connect"))
    assert main([str(path), "--apply"]) == 2
    assert "cleaned export" in capsys.readouterr().err
