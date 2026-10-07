from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.domain.calendar import Event, Member


class Base(DeclarativeBase):
    pass


class MemberRow(Base):
    __tablename__ = "members"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="event_positive_duration"),
        Index("event_member_dates", "member_id", "starts_at", "ends_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id"))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def make_engine(url: str):
    return create_engine(url, pool_pre_ping=True)


def to_event(row: EventRow) -> Event:
    return Event(row.id, row.member_id, row.title, row.starts_at, row.ends_at)


class SqlCalendarRepository:
    def __init__(self, session: Session):
        self.session = session

    def members(self) -> list[Member]:
        rows = self.session.scalars(select(MemberRow).order_by(MemberRow.created_at, MemberRow.id))
        return [Member(row.id, row.name, row.color) for row in rows]

    def member(self, member_id: UUID) -> Member | None:
        row = self.session.get(MemberRow, member_id)
        return Member(row.id, row.name, row.color) if row else None

    def add_member(self, member: Member) -> Member:
        self.session.add(
            MemberRow(
                id=member.id, name=member.name, color=member.color, created_at=datetime.now(UTC)
            )
        )
        self.session.flush()
        return member

    def events(self, start: datetime, end: datetime, member_id: UUID | None) -> list[Event]:
        query = select(EventRow).where(EventRow.starts_at < end, EventRow.ends_at > start)
        if member_id is not None:
            query = query.where(EventRow.member_id == member_id)
        return [to_event(row) for row in self.session.scalars(query.order_by(EventRow.starts_at))]

    def event(self, event_id: UUID) -> Event | None:
        row = self.session.get(EventRow, event_id)
        return to_event(row) if row else None

    def save_event(self, event: Event) -> Event:
        now = datetime.now(UTC)
        row = self.session.get(EventRow, event.id)
        if row is None:
            row = EventRow(id=event.id, member_id=event.member_id, created_at=now)
            self.session.add(row)
        row.title, row.starts_at, row.ends_at = event.title, event.starts_at, event.ends_at
        row.updated_at = now
        self.session.flush()
        return event

    def remove_event(self, event_id: UUID) -> None:
        row = self.session.get(EventRow, event_id)
        if row:
            self.session.delete(row)
