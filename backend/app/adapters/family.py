from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.adapters.database import Base, SqlCalendarRepository
from app.domain.family import FamilyEvent, FamilyIcon


class FamilyEventRow(Base):
    __tablename__ = "family_all_day_events"
    __table_args__ = (
        CheckConstraint(
            "icon IN ('birthday', 'celebration', 'trip', 'other')", name="family_event_icon"
        ),
        Index("family_event_day", "day"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(80))
    icon: Mapped[str] = mapped_column(String(20))
    custom_icon_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("custom_icons.id", name="family_all_day_events_custom_icon"), nullable=True
    )


def to_event(row: FamilyEventRow) -> FamilyEvent:
    return FamilyEvent(row.id, row.day, row.title, FamilyIcon(row.icon), row.custom_icon_id)


class SqlFamilyRepository:
    def __init__(self, session: Session):
        self.session = session

    def icon(self, icon_id: UUID):
        return SqlCalendarRepository(self.session).icon(icon_id)

    def events(self, start: date, end: date) -> list[FamilyEvent]:
        query = select(FamilyEventRow).where(FamilyEventRow.day >= start, FamilyEventRow.day < end)
        return [
            to_event(row)
            for row in self.session.scalars(
                query.order_by(FamilyEventRow.day, FamilyEventRow.title, FamilyEventRow.id)
            )
        ]

    def event(self, event_id: UUID) -> FamilyEvent | None:
        row = self.session.get(FamilyEventRow, event_id)
        return to_event(row) if row else None

    def save(self, event: FamilyEvent) -> FamilyEvent:
        row = self.session.get(FamilyEventRow, event.id)
        if row is None:
            row = FamilyEventRow(id=event.id)
            self.session.add(row)
        row.day, row.title, row.icon = event.day, event.title, event.icon.value
        row.custom_icon_id = event.custom_icon_id
        self.session.flush()
        return event

    def remove(self, event_id: UUID):
        self.session.delete(self.session.get(FamilyEventRow, event_id))
