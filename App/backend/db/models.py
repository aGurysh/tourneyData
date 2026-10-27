"""The current application schema. Apply changes through Alembic migrations."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, Double, ForeignKey, Identity,
    Index, MetaData, Numeric, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


class Tournament(Base):
    __tablename__ = "tournaments"
    __table_args__ = (
        CheckConstraint("weather_latitude BETWEEN -90 AND 90", name="weather_latitude_range"),
        CheckConstraint("weather_longitude BETWEEN -180 AND 180", name="weather_longitude_range"),
        CheckConstraint("(weather_latitude IS NULL) = (weather_longitude IS NULL)", name="weather_coordinates_pair"),
        CheckConstraint("(starts_at IS NULL) = (ends_at IS NULL) AND (ends_at IS NULL OR ends_at > starts_at)", name="duration_valid"),
        CheckConstraint(
            "winning_length_inches >= 0 AND winning_length_inches <> 'NaN'::numeric",
            name="winning_length_nonnegative",
        ),
        CheckConstraint(
            "top_10_percent_length_inches >= 0 AND top_10_percent_length_inches <> 'NaN'::numeric",
            name="top_10_percent_length_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weather_latitude: Mapped[float | None] = mapped_column(Double)
    weather_longitude: Mapped[float | None] = mapped_column(Double)
    source_url: Mapped[str] = mapped_column(Text, unique=True)
    external_id: Mapped[str | None] = mapped_column(Text, unique=True)
    catch_coverage: Mapped[str] = mapped_column(Text, server_default="standings_only")
    winning_length_inches: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    top_10_percent_length_inches: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)


class TournamentLocation(Base):
    __tablename__ = "tournament_locations"
    __table_args__ = (
        Index("ix_tournament_locations_location_id_tournament_id", "location_id", "tournament_id"),
    )

    tournament_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tournaments.id"), primary_key=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("locations.id"), primary_key=True,
    )
    boundary_notes: Mapped[str | None] = mapped_column(Text)


class Species(Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


class Catch(Base):
    __tablename__ = "catches"
    __table_args__ = (
        UniqueConstraint("tournament_id", "external_id", name="uq_catches_tournament_id_external_id"),
        CheckConstraint(
            "length_inches > 0 AND length_inches <> 'NaN'::numeric", name="length_positive",
        ),
        Index("ix_catches_tournament_id_catch_time", "tournament_id", "catch_time"),
        Index("ix_catches_species_id", "species_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tournament_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tournaments.id"))
    angler_name: Mapped[str] = mapped_column(Text)
    catch_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    species_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("species.id"))
    length_inches: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    external_id: Mapped[str | None] = mapped_column(Text)
