from datetime import date, time
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    Uuid,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.adapters.database import Base, MemberRow
from app.domain.calendar import Category
from app.domain.recurrence import EndMode, EventException, EventSeries, Frequency


class EventSeriesRow(Base):
    __tablename__ = "event_series"
    __table_args__ = (
        Index("event_series_member", "member_id", "start_date"),
        CheckConstraint("frequency IN ('daily', 'weekly', 'monthly')", name="series_frequency"),
        CheckConstraint("end_mode IN ('never', 'date', 'count')", name="series_end_mode"),
        CheckConstraint("interval BETWEEN 1 AND 365", name="series_interval"),
        CheckConstraint("duration_minutes BETWEEN 1 AND 10080", name="series_duration"),
        CheckConstraint(
            "category IN ('school', 'activities', 'medical', 'friends', 'other')",
            name="series_category",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(80))
    frequency: Mapped[str] = mapped_column(String(16))
    interval: Mapped[int] = mapped_column(Integer)
    weekdays: Mapped[list[int]] = mapped_column(JSON)
    end_mode: Mapped[str] = mapped_column(String(16))
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    occurrence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(32))
    custom_icon_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("custom_icons.id"), nullable=True
    )


class EventExceptionRow(Base):
    __tablename__ = "event_exceptions"
    __table_args__ = (
        CheckConstraint(
            "override_duration_minutes IS NULL OR override_duration_minutes BETWEEN 1 AND 10080",
            name="exception_duration",
        ),
    )
    series_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_series.id", ondelete="CASCADE"), primary_key=True
    )
    occurrence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    occurrence_time: Mapped[time] = mapped_column(Time, primary_key=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    override_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    override_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    override_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    has_icon_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_custom_icon_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("custom_icons.id"), nullable=True
    )


def series_from_row(row: EventSeriesRow) -> EventSeries:
    return EventSeries(
        row.id,
        row.member_id,
        row.title,
        row.start_date,
        row.start_time,
        row.duration_minutes,
        row.timezone,
        Frequency(row.frequency),
        row.interval,
        tuple(row.weekdays or []),
        EndMode(row.end_mode),
        row.end_date,
        row.occurrence_count,
        Category(row.category),
        row.custom_icon_id,
    )


def exception_from_row(row: EventExceptionRow) -> EventException:
    category = Category(row.override_category) if row.override_category else None
    return EventException(
        row.series_id,
        row.occurrence_date,
        row.occurrence_time,
        row.cancelled,
        row.override_start_time,
        row.override_duration_minutes,
        row.override_title,
        category,
        row.has_icon_override,
        row.override_custom_icon_id,
    )


class SqlRecurrenceRepository:
    def __init__(self, session: Session):
        self.session = session

    def series(
        self, member_id: UUID | None = None, include_archived: bool = False
    ) -> list[EventSeries]:
        query = (
            select(EventSeriesRow)
            .join(MemberRow)
            .order_by(EventSeriesRow.start_date, EventSeriesRow.start_time)
        )
        if not include_archived:
            query = query.where(MemberRow.active)
        if member_id:
            query = query.where(EventSeriesRow.member_id == member_id)
        return [series_from_row(row) for row in self.session.scalars(query)]

    def get_series(self, series_id: UUID) -> EventSeries | None:
        row = self.session.get(EventSeriesRow, series_id)
        if row is None:
            return None
        member = self.session.get(MemberRow, row.member_id)
        return series_from_row(row) if member and member.active else None

    def save_series(self, series: EventSeries) -> EventSeries:
        row = self.session.get(EventSeriesRow, series.id)
        if row is None:
            row = EventSeriesRow(id=series.id)
            self.session.add(row)
        row.member_id, row.title = series.member_id, series.title
        row.start_date, row.start_time = series.start_date, series.start_time
        row.duration_minutes, row.timezone = series.duration_minutes, series.timezone
        row.frequency, row.interval, row.weekdays = (
            series.frequency.value,
            series.interval,
            list(series.weekdays),
        )
        row.end_mode, row.end_date = series.end_mode.value, series.end_date
        row.occurrence_count, row.category = series.occurrence_count, series.category.value
        row.custom_icon_id = series.custom_icon_id
        self.session.flush()
        return series

    def delete_series(self, series_id: UUID) -> None:
        row = self.session.get(EventSeriesRow, series_id)
        if row:
            self.session.delete(row)
            self.session.flush()

    def exceptions(self, series_id: UUID) -> list[EventException]:
        rows = self.session.scalars(
            select(EventExceptionRow).where(EventExceptionRow.series_id == series_id)
        )
        return [exception_from_row(row) for row in rows]

    def save_exception(self, exception: EventException) -> EventException:
        key = (exception.series_id, exception.occurrence_date, exception.occurrence_time)
        row = self.session.get(EventExceptionRow, key)
        if row is None:
            row = EventExceptionRow(
                series_id=exception.series_id,
                occurrence_date=exception.occurrence_date,
                occurrence_time=exception.occurrence_time,
            )
            self.session.add(row)
        row.cancelled = exception.cancelled
        row.override_start_time = exception.override_start_time
        row.override_duration_minutes = exception.override_duration_minutes
        row.override_title = exception.override_title
        row.override_category = (
            exception.override_category.value if exception.override_category else None
        )
        row.has_icon_override = exception.has_icon_override
        row.override_custom_icon_id = exception.override_custom_icon_id
        self.session.flush()
        return exception

    def delete_exception(
        self, series_id: UUID, occurrence_date: date, occurrence_time: time
    ) -> None:
        row = self.session.get(EventExceptionRow, (series_id, occurrence_date, occurrence_time))
        if row:
            self.session.delete(row)
            self.session.flush()
