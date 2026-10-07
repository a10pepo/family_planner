"""Shared image catalog with optional references; preserves activities and marks."""

import sqlalchemy as sa
from alembic import op

revision = "004_reusable_icons"
down_revision = "003_profiles_daily_tasks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "custom_icons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("image_data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table in ("tasks", "all_day_notices", "events"):
        op.add_column(table, sa.Column("custom_icon_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"{table}_custom_icon", table, "custom_icons", ["custom_icon_id"], ["id"]
        )


def downgrade():
    for table in ("tasks", "all_day_notices", "events"):
        op.drop_constraint(f"{table}_custom_icon", table, type_="foreignkey")
        op.drop_column(table, "custom_icon_id")
    op.drop_table("custom_icons")
