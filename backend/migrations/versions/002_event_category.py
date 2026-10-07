"""Add event category without removing existing events."""

import sqlalchemy as sa
from alembic import op

revision = "002_event_category"
down_revision = "001_calendar"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "events", sa.Column("category", sa.String(32), nullable=False, server_default="other")
    )
    op.create_check_constraint(
        "event_category",
        "events",
        "category IN ('school', 'activities', 'medical', 'friends', 'other')",
    )


def downgrade():
    op.drop_constraint("event_category", "events", type_="check")
    op.drop_column("events", "category")
