"""Add school, homework, and uniform task icons."""

from alembic import op

revision = "007_task_icons"
down_revision = "006_recurring_events"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("task_icon", "tasks", type_="check")
    op.create_check_constraint(
        "task_icon",
        "tasks",
        "icon IN ('school', 'homework', 'uniform', 'tooth', 'backpack', 'bed', 'other')",
    )


def downgrade():
    op.drop_constraint("task_icon", "tasks", type_="check")
    op.create_check_constraint(
        "task_icon", "tasks", "icon IN ('tooth', 'backpack', 'bed', 'other')"
    )
