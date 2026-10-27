from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from alembic import command
import pytest
from sqlalchemy import delete, insert, inspect, select
from sqlalchemy.exc import IntegrityError

from backend.db.models import Catch, Location, Species, Tournament, TournamentLocation


def add_tournament(connection, suffix="1", **values):
    fields = dict(
        name="Test tournament", date=date(2026, 10, 26),
        timezone="America/New_York", source_url=f"https://example.test/{suffix}",
    )
    fields.update(values)
    return connection.scalar(insert(Tournament).values(**fields).returning(Tournament.id))


def add_catch(connection, tournament_id, **values):
    fields = dict(
        tournament_id=tournament_id, angler_name="Test Angler",
        catch_time=datetime(2026, 10, 26, 8, 30, tzinfo=timezone(timedelta(hours=-4))),
        length_inches=Decimal("19.25"),
    )
    fields.update(values)
    return connection.scalar(insert(Catch).values(**fields).returning(Catch.id))


def test_migration_round_trip_and_model_agreement(migrated_database):
    connection, config = migrated_database
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(connection).get_table_names() == ["alembic_version"]
    connection.commit()
    command.upgrade(config, "head")
    command.check(config)
    assert set(inspect(connection).get_table_names()) == {
        "alembic_version", "tournaments", "locations", "species",
        "tournament_locations", "catches",
    }
    connection.commit()


def test_decimal_timestamp_and_optional_fields(connection):
    tournament_id = add_tournament(connection)
    catch_id = add_catch(connection, tournament_id)
    row = connection.execute(select(Catch.__table__).where(Catch.id == catch_id)).one()
    assert row.length_inches == Decimal("19.25")
    assert isinstance(row.length_inches, Decimal)
    assert row.catch_time == datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc)
    assert row.catch_time.utcoffset() == timedelta(0)
    assert row.species_id is None
    assert row.external_id is None
    assert connection.scalar(select(Tournament.catch_coverage)) == "standings_only"


def test_source_id_is_unique_per_tournament_but_missing_ids_are_allowed(connection):
    first = add_tournament(connection)
    second = add_tournament(connection, "2")
    add_catch(connection, first, external_id="source-fish-1")
    add_catch(connection, second, external_id="source-fish-1")
    add_catch(connection, first)
    add_catch(connection, first)
    with pytest.raises(IntegrityError), connection.begin_nested():
        add_catch(connection, first, external_id="source-fish-1")


@pytest.mark.parametrize("length", ["0", "-1", "NaN"])
def test_invalid_catch_length_is_rejected(connection, length):
    tournament_id = add_tournament(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        add_catch(connection, tournament_id, length_inches=Decimal(length))


@pytest.mark.parametrize("field", ["winning_length_inches", "top_10_percent_length_inches"])
@pytest.mark.parametrize("length", ["-1", "NaN"])
def test_invalid_standings_length_is_rejected(connection, field, length):
    with pytest.raises(IntegrityError), connection.begin_nested():
        add_tournament(connection, **{field: Decimal(length)})


def test_standings_lengths_allow_zero_and_unknown(connection):
    add_tournament(connection, winning_length_inches=Decimal("0.00"))
    row = connection.execute(select(Tournament.__table__)).one()
    assert row.winning_length_inches == Decimal("0.00")
    assert row.top_10_percent_length_inches is None


def test_orphans_and_implicit_parent_deletion_are_rejected(connection):
    with pytest.raises(IntegrityError), connection.begin_nested():
        add_catch(connection, -1)
    tournament_id = add_tournament(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        add_catch(connection, tournament_id, species_id=-1)
    species_id = connection.scalar(insert(Species).values(name="Smallmouth Bass").returning(Species.id))
    add_catch(connection, tournament_id, species_id=species_id)
    for model, row_id in [(Tournament, tournament_id), (Species, species_id)]:
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(delete(model).where(model.id == row_id))


def test_multi_water_events_and_duplicate_links(connection):
    tournament_id = add_tournament(connection)
    # Names intentionally need not be globally unique.
    ids = [connection.scalar(insert(Location).values(name="Spring Creek").returning(Location.id)) for _ in range(2)]
    for location_id in ids:
        connection.execute(insert(TournamentLocation).values(tournament_id=tournament_id, location_id=location_id))
    add_catch(connection, tournament_id)
    assert len(connection.execute(select(TournamentLocation)).all()) == 2
    assert len(connection.execute(select(Catch)).all()) == 1
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(insert(TournamentLocation).values(tournament_id=tournament_id, location_id=ids[0]))
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(delete(Location).where(Location.id == ids[0]))


def test_tournament_and_species_uniqueness(connection):
    add_tournament(connection, external_id="event-1")
    for suffix, values in [("1", {}), ("2", {"external_id": "event-1"})]:
        with pytest.raises(IntegrityError), connection.begin_nested():
            add_tournament(connection, suffix, **values)
    connection.execute(insert(Species).values(name="Largemouth Bass"))
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(insert(Species).values(name="Largemouth Bass"))


def test_query_indexes_exist(connection):
    inspector = inspect(connection)
    assert {index["name"] for index in inspector.get_indexes("catches")} >= {
        "ix_catches_tournament_id_catch_time", "ix_catches_species_id",
    }
    assert "ix_tournament_locations_location_id_tournament_id" in {
        index["name"] for index in inspector.get_indexes("tournament_locations")
    }
