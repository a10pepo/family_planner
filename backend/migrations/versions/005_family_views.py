"""Family all-day events and reversible profile archive; preserves existing history."""

import sqlalchemy as sa
from alembic import op

revision = "005_family_views"
down_revision = "004_reusable_icons"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "members", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.create_table(
        "family_all_day_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("icon", sa.String(20), nullable=False),
        sa.Column("custom_icon_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "icon IN ('birthday', 'celebration', 'trip', 'other')", name="family_event_icon"
        ),
        sa.ForeignKeyConstraint(
            ["custom_icon_id"], ["custom_icons.id"], name="family_all_day_events_custom_icon"
        ),
    )
    op.create_index("family_event_day", "family_all_day_events", ["day"])


def downgrade():
    op.drop_table("family_all_day_events")
    op.drop_column("members", "active")
