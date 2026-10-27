"""Require catch identity after the raw snapshot backfill."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    if not op.get_context().as_sql:
        missing = op.get_bind().scalar(sa.text("SELECT count(*) FROM catches WHERE angler_id IS NULL"))
        if missing:
            raise RuntimeError(f"{missing} catches need angler backfill. Run ingest.py --backfill before upgrading to 0004.")
    op.alter_column("catches", "angler_id", existing_type=sa.BigInteger(), nullable=False)


def downgrade():
    op.alter_column("catches", "angler_id", existing_type=sa.BigInteger(), nullable=True)
