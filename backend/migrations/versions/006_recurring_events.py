"""Add recurring event series and occurrence exceptions."""

import sqlalchemy as sa
from alembic import op

revision = "006_recurring_events"
down_revision = "005_family_views"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "event_series",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "member_id", sa.Uuid(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("end_mode", sa.String(16), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("custom_icon_id", sa.Uuid(), sa.ForeignKey("custom_icons.id"), nullable=True),
        sa.CheckConstraint("frequency IN ('daily', 'weekly', 'monthly')", name="series_frequency"),
        sa.CheckConstraint("end_mode IN ('never', 'date', 'count')", name="series_end_mode"),
        sa.CheckConstraint("interval BETWEEN 1 AND 365", name="series_interval"),
        sa.CheckConstraint("duration_minutes BETWEEN 1 AND 10080", name="series_duration"),
        sa.CheckConstraint(
            "category IN ('school', 'activities', 'medical', 'friends', 'other')",
            name="series_category",
        ),
    )
    op.create_index("event_series_member", "event_series", ["member_id", "start_date"])
    op.create_table(
        "event_exceptions",
        sa.Column(
            "series_id",
            sa.Uuid(),
            sa.ForeignKey("event_series.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("occurrence_date", sa.Date(), primary_key=True),
        sa.Column("occurrence_time", sa.Time(), primary_key=True),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_start_time", sa.Time(), nullable=True),
        sa.Column("override_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("override_title", sa.String(200), nullable=True),
        sa.Column("override_category", sa.String(32), nullable=True),
        sa.Column("has_icon_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "override_custom_icon_id", sa.Uuid(), sa.ForeignKey("custom_icons.id"), nullable=True
        ),
        sa.CheckConstraint(
            "override_duration_minutes IS NULL OR override_duration_minutes BETWEEN 1 AND 10080",
            name="exception_duration",
        ),
        sa.CheckConstraint(
            "override_category IS NULL OR override_category IN "
            "('school', 'activities', 'medical', 'friends', 'other')",
            name="exception_category",
        ),
    )


def downgrade():
    op.drop_table("event_exceptions")
    op.drop_index("event_series_member", table_name="event_series")
    op.drop_table("event_series")
