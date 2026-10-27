"""Add source-identified anglers and tournament participation; backfill before 0004."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    op.create_table("anglers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("external_id", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_observed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("tournament_entries",
        sa.Column("tournament_id", sa.BigInteger(), sa.ForeignKey("tournaments.id"), primary_key=True),
        sa.Column("angler_id", sa.BigInteger(), sa.ForeignKey("anglers.id"), primary_key=True),
        sa.Column("angler_name", sa.Text(), nullable=False))
    op.create_index("ix_tournament_entries_angler_id", "tournament_entries", ["angler_id"])
    op.add_column("catches", sa.Column("angler_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_catches_angler_id", "catches", ["angler_id"])
    op.create_foreign_key("fk_catches_tournament_id_angler_id_tournament_entries", "catches", "tournament_entries",
                          ["tournament_id", "angler_id"], ["tournament_id", "angler_id"])


def downgrade():
    op.drop_constraint("fk_catches_tournament_id_angler_id_tournament_entries", "catches", type_="foreignkey")
    op.drop_index("ix_catches_angler_id", "catches")
    op.drop_column("catches", "angler_id")
    op.drop_table("tournament_entries")
    op.drop_table("anglers")
