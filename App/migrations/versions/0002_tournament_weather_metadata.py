"""Add source weather coordinates and tournament duration."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tournaments", sa.Column("starts_at", sa.DateTime(timezone=True)))
    op.add_column("tournaments", sa.Column("ends_at", sa.DateTime(timezone=True)))
    op.add_column("tournaments", sa.Column("weather_latitude", sa.Double()))
    op.add_column("tournaments", sa.Column("weather_longitude", sa.Double()))
    for name, expression in (
        ("weather_latitude_range", "weather_latitude BETWEEN -90 AND 90"),
        ("weather_longitude_range", "weather_longitude BETWEEN -180 AND 180"),
        ("weather_coordinates_pair", "(weather_latitude IS NULL) = (weather_longitude IS NULL)"),
        ("duration_valid", "(starts_at IS NULL) = (ends_at IS NULL) AND (ends_at IS NULL OR ends_at > starts_at)"),
    ):
        op.create_check_constraint(op.f(f"ck_tournaments_{name}"), "tournaments", expression)


def downgrade() -> None:
    for name in ("duration_valid", "weather_coordinates_pair", "weather_longitude_range", "weather_latitude_range"):
        op.drop_constraint(op.f(f"ck_tournaments_{name}"), "tournaments", type_="check")
    for name in ("weather_longitude", "weather_latitude", "ends_at", "starts_at"):
        op.drop_column("tournaments", name)
