from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from backend.db.models import Angler, Catch, Tournament, TournamentEntry, TournamentLocation
from backend.ingestion.batch import backfill_one, prepare_export, read_manifest, run
from backend.ingestion.importer import import_export


@pytest.fixture
def raw():
    # Synthetic source response: no dependency on ignored local output files.
    rows = []
    for index in range(48):
        fish_count = (5 if index < 3 else 4) if index < 43 else 0
        rows.append({"user_id": str(index + 1), "angler_name": f"Angler {index + 1}",
            "fish_caught": fish_count, "total_fish_length": str(fish_count * 18),
            "submissions": [{"submission_id": str(index * 10 + fish + 1), "tournament_id": "123",
                "fish_length": "18.00", "fish_type": "Bass", "status": "1",
                "date_taken": "2026-07-18 08:00:00", "catch_timezone": "Eastern"}
                for fish in range(fish_count)]})
    return {"source_url": "https://tourneyx.com/leaderboard/standings/test-event",
        "scraped_at": "2026-10-26T12:00:00+00:00", "capture_version": 2, "collection_complete": True,
        "metadata": {"id": "123", "slug": "test-event", "tournament_title": "Test Event",
            "start_date": "2026-07-18 06:00:00", "end_date": "2026-07-18 15:00:00",
            "timezone": "Eastern", "measurement_type": "length", "measurement_name": "inch", "total_fish": "5"},
        "standings": {"tournamentId": "123", "measurement_type": "length", "results": [rows]}}


class TestEngine:
    __test__ = False

    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection

    @contextmanager
    def begin(self):
        with self.connection.begin_nested():
            yield self.connection


@pytest.fixture
def engine(connection):
    return TestEngine(connection)


def cache(tmp_path, raw):
    url = raw["source_url"]
    (tmp_path / f"{url.rsplit('/', 1)[1]}.raw.json").write_text(json.dumps(raw))
    return url


def test_manifest_urls_overrides_and_duplicates(tmp_path):
    url = "https://tourneyx.com/leaderboard/standings/test"
    path = tmp_path / "new.json"
    path.write_text(json.dumps([url + "/?ignored=1", url]))
    assert read_manifest(path) == [{"url": url}]
    path.write_text(json.dumps([url, {"url": url, "timezone": "America/New_York"}]))
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        read_manifest(path)


@pytest.mark.parametrize("value", [{}, [None], [{"url": "https://example.com"}],
    [{"url": "https://tourneyx.com/leaderboard/standings/test", "locations": [{"id": True}]}]])
def test_bad_manifest(tmp_path, value):
    path = tmp_path / "new.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        read_manifest(path)


def test_all_anglers_shared_identity_and_historical_names(connection, raw):
    export = prepare_export(raw, {})
    result = import_export(connection, export, apply=True)
    assert connection.scalar(select(func.count()).select_from(Angler)) == 48
    assert connection.scalar(select(func.count()).select_from(TournamentEntry)) == 48
    assert connection.scalar(select(func.count()).select_from(Catch)) == 175
    original = connection.execute(select(Angler.__table__).order_by(Angler.id)).mappings().first()
    newer = deepcopy(export)
    newer.tournament.update(source_url="https://tourneyx.com/leaderboard/standings/new", external_id="new")
    newer.scraped_at += timedelta(days=1)
    newer.anglers[0]["name"] = "Changed Name"
    import_export(connection, newer, apply=True)
    assert connection.scalar(select(func.count()).select_from(Angler)) == 48
    assert connection.scalar(select(Angler.name).where(Angler.id == original["id"])) == "Changed Name"
    import_export(connection, export, replace=True, apply=True)
    assert connection.scalar(select(Angler.name).where(Angler.id == original["id"])) == "Changed Name"
    assert connection.scalar(select(TournamentEntry.angler_name).where(
        TournamentEntry.tournament_id == result["tournament_id"], TournamentEntry.angler_id == original["id"])) == original["name"]


def test_same_names_do_not_merge(connection, raw):
    rows = raw["standings"]["results"][0]
    rows[1]["angler_name"] = rows[0]["angler_name"]
    export = prepare_export(raw, {})
    import_export(connection, export, apply=True)
    assert connection.scalar(select(func.count()).select_from(Angler)) == 48
    assert connection.scalar(select(func.count()).select_from(Angler).where(Angler.name == rows[0]["angler_name"])) == 2


def test_offline_dry_run_import_skip_and_report(engine, connection, raw, tmp_path):
    url = cache(tmp_path, raw)
    args = dict(output=tmp_path, offline=True)
    preview = run([{"url": url}], engine, dry_run=True, **args)
    assert preview["counts"]["create"] == 1
    assert connection.scalar(select(func.count()).select_from(Angler)) == 0
    first = run([{"url": url}], engine, **args)
    assert first["counts"]["create"] == 1
    second = run([{"url": url}], engine, **args)
    assert second["counts"]["skipped"] == 1
    assert connection.scalar(select(func.count()).select_from(Catch)) == 175
    assert len(list((tmp_path / "reports").glob("*.json"))) == 3


def test_refresh_failure_never_uses_cached_data(engine, connection, raw, tmp_path, monkeypatch):
    url = cache(tmp_path, raw)
    run([{"url": url}], engine, output=tmp_path, offline=True)
    before = connection.execute(select(Catch.__table__).order_by(Catch.id)).all()
    def fail(*args):
        raise ValueError("capture failed")
    monkeypatch.setattr("backend.ingestion.batch.CaptureSession.fetch", fail)
    result = run([{"url": url}], engine, output=tmp_path, refresh=True)
    assert result["counts"]["failed"] == 1
    assert connection.execute(select(Catch.__table__).order_by(Catch.id)).all() == before


def test_batch_continues_after_failure(engine, raw, tmp_path):
    url = cache(tmp_path, raw)
    result = run([{"url": "https://tourneyx.com/leaderboard/standings/missing"}, {"url": url}], engine,
                 output=tmp_path, offline=True)
    assert result["counts"]["failed"] == result["counts"]["create"] == 1


def test_refresh_preserves_locations(engine, connection, raw, tmp_path, monkeypatch):
    url = cache(tmp_path, raw)
    run([{"url": url, "locations": [{"name": "Test River", "state": "PA"}]}], engine, output=tmp_path, offline=True)
    before = connection.execute(select(TournamentLocation.__table__)).all()
    def fetch(self, url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw))
        return raw
    monkeypatch.setattr("backend.ingestion.batch.CaptureSession.fetch", fetch)
    result = run([{"url": url}], engine, output=tmp_path, refresh=True)
    assert result["counts"]["replace"] == 1
    assert connection.execute(select(TournamentLocation.__table__)).all() == before


def test_backfill_preserves_catch_ids_and_checks_mismatches(connection, raw):
    # This test needs the nullable, intermediate migration state; use a savepoint
    # so schema alteration is rolled back along with the data.
    from sqlalchemy import text
    connection.execute(text("ALTER TABLE catches ALTER COLUMN angler_id DROP NOT NULL"))
    export = prepare_export(raw, {})
    result = import_export(connection, export, apply=True)
    tournament = connection.execute(select(Tournament.__table__).where(Tournament.id == result["tournament_id"])).mappings().one()
    connection.execute(update(Catch).values(angler_id=None))
    before = connection.execute(select(Catch.id, Catch.length_inches, Catch.catch_time).order_by(Catch.id)).all()
    bad = deepcopy(raw)
    fish = bad["standings"]["results"][0][0]["submissions"][0]
    fish["date_taken"] = "2025-08-23 09:00:00"
    with pytest.raises(ValueError):
        backfill_one(connection, tournament, bad, apply=True)
    for _ in range(2):
        plan = backfill_one(connection, tournament, raw, apply=True)
        assert plan["catches_in_file"] == 175
    assert connection.execute(select(Catch.id, Catch.length_inches, Catch.catch_time).order_by(Catch.id)).all() == before
    assert connection.scalar(select(func.count()).select_from(Catch).where(Catch.angler_id.is_(None))) == 0


def test_catch_cannot_reference_angler_without_entry(connection, raw):
    export = prepare_export(raw, {})
    import_export(connection, export, apply=True)
    angler_id = connection.scalar(insert(Angler).values(external_id="outsider", name="Outsider",
        name_observed_at=export.scraped_at).returning(Angler.id))
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(update(Catch).values(angler_id=angler_id))


def test_unsupported_event_does_not_stop_batch(engine, raw, tmp_path):
    multi = deepcopy(raw)
    multi["source_url"] = "https://tourneyx.com/leaderboard/standings/multi"
    multi["metadata"].update(slug="multi", end_date="2026-07-19 15:00:00")
    cache(tmp_path, multi)
    url = cache(tmp_path, raw)
    result = run([{"url": multi["source_url"]}, {"url": url}], engine, output=tmp_path, offline=True)
    assert result["counts"]["failed"] == result["counts"]["create"] == 1
    assert "Multi-day" in result["results"][0]["error"]


def test_partial_capture_is_not_reused(engine, raw, tmp_path):
    del raw["standings"]
    url = cache(tmp_path, raw)
    result = run([{"url": url}], engine, output=tmp_path, offline=True)
    assert result["counts"]["failed"] == 1
    assert "No complete" in result["results"][0]["error"]


def test_database_error_rolls_back_anglers_and_tournament(engine, connection, raw, tmp_path, monkeypatch):
    url = cache(tmp_path, raw)
    from backend.ingestion import batch
    original = batch.import_export
    def fail(connection, export, **kwargs):
        result = original(connection, export, **kwargs)
        # Violate the composite entry FK after the import to prove the entire event rolls back.
        connection.execute(update(Catch).values(angler_id=-1))
        return result
    monkeypatch.setattr(batch, "import_export", fail)
    result = run([{"url": url}], engine, output=tmp_path, offline=True)
    assert result["counts"]["failed"] == 1
    for model in (Tournament, Angler, TournamentEntry, Catch):
        assert connection.scalar(select(func.count()).select_from(model)) == 0


def test_legacy_export_reconstructs_identity_from_matching_raw(raw, tmp_path):
    from backend.ingestion.source import _build_export
    from backend.ingestion.validation import load_export
    data = _build_export(raw, {})
    del data["anglers"]
    for catch in data["catches"]:
        del catch["source_angler_id"]
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(data))
    path.with_suffix(".raw.json").write_text(json.dumps(raw))
    export = load_export(path)
    assert len(export.anglers) == 48
    assert export.catches[0]["source_angler_id"] == "1"
