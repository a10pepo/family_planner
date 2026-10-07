"""Optional photos, all-day notices and per-person daily task states."""

import sqlalchemy as sa
from alembic import op

revision = "003_profiles_daily_tasks"
down_revision = "002_event_category"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("members", sa.Column("photo_data", sa.Text(), nullable=True))
    op.create_table(
        "all_day_notices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("icon", sa.String(20), nullable=False),
        sa.CheckConstraint("icon IN ('uniform', 'tracksuit', 'trip', 'other')", name="notice_icon"),
    )
    op.create_index("notice_member_day", "all_day_notices", ["member_id", "day"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("icon", sa.String(20), nullable=False),
        sa.Column("frequency", sa.String(12), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("icon IN ('tooth', 'backpack', 'bed', 'other')", name="task_icon"),
        sa.CheckConstraint("frequency IN ('daily', 'once')", name="task_frequency"),
    )
    op.create_table(
        "task_assignments",
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), primary_key=True),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("members.id"), primary_key=True),
    )
    op.create_table(
        "task_completions",
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), primary_key=True),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("members.id"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("task_completions")
    op.drop_table("task_assignments")
    op.drop_table("tasks")
    op.drop_index("notice_member_day", "all_day_notices")
    op.drop_table("all_day_notices")
    op.drop_column("members", "photo_data")
