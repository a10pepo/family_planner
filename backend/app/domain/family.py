from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.calendar import InvalidInput, MissingEntity, clean_text


class FamilyIcon(StrEnum):
    BIRTHDAY = "birthday"
    CELEBRATION = "celebration"
    TRIP = "trip"
    OTHER = "other"


@dataclass(frozen=True)
class FamilyEvent:
    id: UUID
    day: date
    title: str
    icon: FamilyIcon
    custom_icon_id: UUID | None = None


class FamilyRepository(Protocol):
    def events(self, start: date, end: date) -> list[FamilyEvent]: ...
    def event(self, event_id: UUID) -> FamilyEvent | None: ...
    def save(self, event: FamilyEvent) -> FamilyEvent: ...
    def remove(self, event_id: UUID) -> None: ...
    def icon(self, icon_id: UUID): ...


class FamilyPlanner:
    def __init__(self, repository: FamilyRepository):
        self.repository = repository

    def list_events(self, start: date, end: date) -> list[FamilyEvent]:
        if end <= start:
            raise InvalidInput("El final debe ser posterior al inicio.")
        return self.repository.events(start, end)

    def save(
        self,
        day: date,
        title: str,
        icon: str,
        custom_icon_id: UUID | None = None,
        event_id: UUID | None = None,
        replace_custom_icon: bool = False,
    ) -> FamilyEvent:
        previous = self.repository.event(event_id) if event_id else None
        if event_id and previous is None:
            raise MissingEntity("No existe el evento familiar.")
        reference = (
            custom_icon_id if previous is None or replace_custom_icon else previous.custom_icon_id
        )
        if reference is not None and self.repository.icon(reference) is None:
            raise MissingEntity("No existe el icono.")
        try:
            selected = FamilyIcon(icon)
        except ValueError as exc:
            raise InvalidInput("El icono del evento familiar no es válido.") from exc
        return self.repository.save(
            FamilyEvent(event_id or uuid4(), day, clean_text(title, 80), selected, reference)
        )

    def remove(self, event_id: UUID):
        if self.repository.event(event_id) is None:
            raise MissingEntity("No existe el evento familiar.")
        self.repository.remove(event_id)
