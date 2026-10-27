"""Create tournament, waterbody, species, and catch tables.

This migration is a fixed historical snapshot, independent of future ORM models.
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("catch_coverage", sa.Text(), server_default="standings_only", nullable=False),
        sa.Column("winning_length_inches", sa.Numeric(12, 2), nullable=True),
        sa.Column("top_10_percent_length_inches", sa.Numeric(12, 2), nullable=True),
        sa.CheckConstraint(
            "winning_length_inches >= 0 AND winning_length_inches <> 'NaN'::numeric",
            name=op.f("ck_tournaments_winning_length_nonnegative"),
        ),
        sa.CheckConstraint(
            "top_10_percent_length_inches >= 0 AND top_10_percent_length_inches <> 'NaN'::numeric",
            name=op.f("ck_tournaments_top_10_percent_length_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tournaments")),
        sa.UniqueConstraint("source_url", name=op.f("uq_tournaments_source_url")),
        sa.UniqueConstraint("external_id", name=op.f("uq_tournaments_external_id")),
    )
    op.create_table(
        "locations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
    )
    op.create_table(
        "species",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_species")),
        sa.UniqueConstraint("name", name=op.f("uq_species_name")),
    )
    op.create_table(
        "tournament_locations",
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("boundary_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], name=op.f("fk_tournament_locations_tournament_id_tournaments")),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], name=op.f("fk_tournament_locations_location_id_locations")),
        sa.PrimaryKeyConstraint("tournament_id", "location_id", name=op.f("pk_tournament_locations")),
    )
    op.create_index("ix_tournament_locations_location_id_tournament_id", "tournament_locations", ["location_id", "tournament_id"])
    op.create_table(
        "catches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("angler_name", sa.Text(), nullable=False),
        sa.Column("catch_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("species_id", sa.BigInteger(), nullable=True),
        sa.Column("length_inches", sa.Numeric(6, 2), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.CheckConstraint("length_inches > 0 AND length_inches <> 'NaN'::numeric", name=op.f("ck_catches_length_positive")),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], name=op.f("fk_catches_tournament_id_tournaments")),
        sa.ForeignKeyConstraint(["species_id"], ["species.id"], name=op.f("fk_catches_species_id_species")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catches")),
        sa.UniqueConstraint("tournament_id", "external_id", name=op.f("uq_catches_tournament_id_external_id")),
    )
    op.create_index("ix_catches_tournament_id_catch_time", "catches", ["tournament_id", "catch_time"])
    op.create_index("ix_catches_species_id", "catches", ["species_id"])


def downgrade() -> None:
    op.drop_table("catches")
    op.drop_table("tournament_locations")
    op.drop_table("species")
    op.drop_table("locations")
    op.drop_table("tournaments")
