from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.adapters.database import Base, SqlCalendarRepository
from app.domain.daily import Frequency, Notice, NoticeIcon, Task, TaskIcon


class NoticeRow(Base):
    __tablename__ = "all_day_notices"
    __table_args__ = (
        CheckConstraint("icon IN ('uniform', 'tracksuit', 'trip', 'other')", name="notice_icon"),
        Index("notice_member_day", "member_id", "day"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id"))
    day: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(80))
    icon: Mapped[str] = mapped_column(String(20))


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("icon IN ('tooth', 'backpack', 'bed', 'other')", name="task_icon"),
        CheckConstraint("frequency IN ('daily', 'once')", name="task_frequency"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    icon: Mapped[str] = mapped_column(String(20))
    frequency: Mapped[str] = mapped_column(String(12))
    starts_on: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assignments: Mapped[list["TaskAssignmentRow"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="TaskAssignmentRow.member_id"
    )


class TaskAssignmentRow(Base):
    __tablename__ = "task_assignments"
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id"), primary_key=True)


class TaskCompletionRow(Base):
    __tablename__ = "task_completions"
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    completed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def to_notice(row: NoticeRow) -> Notice:
    return Notice(row.id, row.member_id, row.day, row.title, NoticeIcon(row.icon))


def to_task(row: TaskRow) -> Task:
    return Task(
        row.id,
        row.title,
        TaskIcon(row.icon),
        Frequency(row.frequency),
        row.starts_on,
        [assignment.member_id for assignment in row.assignments],
        row.active,
    )


class SqlDailyRepository:
    def __init__(self, session: Session):
        self.session = session

    def member(self, member_id: UUID):
        return SqlCalendarRepository(self.session).member(member_id)

    def notices(self, day: date) -> list[Notice]:
        rows = self.session.scalars(
            select(NoticeRow).where(NoticeRow.day == day).order_by(NoticeRow.title, NoticeRow.id)
        )
        return [to_notice(row) for row in rows]

    def notice(self, notice_id: UUID) -> Notice | None:
        row = self.session.get(NoticeRow, notice_id)
        return to_notice(row) if row else None

    def save_notice(self, notice: Notice) -> Notice:
        row = self.session.get(NoticeRow, notice.id)
        if row is None:
            row = NoticeRow(id=notice.id, member_id=notice.member_id)
            self.session.add(row)
        row.day, row.title, row.icon = notice.day, notice.title, notice.icon.value
        self.session.flush()
        return notice

    def remove_notice(self, notice_id: UUID) -> None:
        self.session.delete(self.session.get(NoticeRow, notice_id))

    def tasks(self) -> list[Task]:
        rows = self.session.scalars(select(TaskRow).order_by(TaskRow.created_at, TaskRow.id))
        return [to_task(row) for row in rows]

    def task(self, task_id: UUID) -> Task | None:
        row = self.session.get(TaskRow, task_id)
        return to_task(row) if row else None

    def save_task(self, task: Task) -> Task:
        row = self.session.get(TaskRow, task.id)
        if row is None:
            row = TaskRow(id=task.id, created_at=datetime.now(UTC))
            self.session.add(row)
        row.title, row.icon, row.frequency = task.title, task.icon.value, task.frequency.value
        row.starts_on, row.active = task.starts_on, task.active
        existing = {assignment.member_id: assignment for assignment in row.assignments}
        row.assignments = [
            existing.get(member_id) or TaskAssignmentRow(member_id=member_id)
            for member_id in task.member_ids
        ]
        self.session.flush()
        return task

    def completions(self, day: date) -> dict[tuple[UUID, UUID], bool]:
        rows = self.session.scalars(select(TaskCompletionRow).where(TaskCompletionRow.day == day))
        return {(row.task_id, row.member_id): row.completed for row in rows}

    def set_completion(self, task_id: UUID, member_id: UUID, day: date, completed: bool) -> None:
        stamp = datetime.now(UTC)
        statement = insert(TaskCompletionRow).values(
            task_id=task_id, member_id=member_id, day=day, completed=completed, updated_at=stamp
        )
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["task_id", "member_id", "day"],
                set_={"completed": completed, "updated_at": stamp},
            )
        )
