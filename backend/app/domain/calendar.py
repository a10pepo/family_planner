from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4


class InvalidInput(ValueError):
    pass


class MissingEntity(LookupError):
    pass


@dataclass(frozen=True)
class Member:
    id: UUID
    name: str
    color: str


@dataclass(frozen=True)
class Event:
    id: UUID
    member_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime


class CalendarRepository(Protocol):
    def members(self) -> list[Member]: ...
    def member(self, member_id: UUID) -> Member | None: ...
    def add_member(self, member: Member) -> Member: ...
    def events(self, start: datetime, end: datetime, member_id: UUID | None) -> list[Event]: ...
    def event(self, event_id: UUID) -> Event | None: ...
    def save_event(self, event: Event) -> Event: ...
    def remove_event(self, event_id: UUID) -> None: ...


def clean_text(value: str, limit: int) -> str:
    value = value.strip()
    if not value or len(value) > limit:
        raise InvalidInput(f"El texto debe tener entre 1 y {limit} caracteres.")
    return value


def validate_interval(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.utcoffset() is None or end.utcoffset() is None:
        raise InvalidInput("Las fechas deben incluir zona horaria.")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    if end <= start:
        raise InvalidInput("El final debe ser posterior al inicio.")
    return start, end


class Calendar:
    def __init__(self, repository: CalendarRepository):
        self.repository = repository

    def add_member(self, name: str, color: str) -> Member:
        if (
            len(color) != 7
            or color[0] != "#"
            or any(c not in "0123456789abcdefABCDEF" for c in color[1:])
        ):
            raise InvalidInput("El color debe ser hexadecimal, por ejemplo #2563eb.")
        return self.repository.add_member(Member(uuid4(), clean_text(name, 80), color.lower()))

    def create_event(self, member_id: UUID, title: str, start: datetime, end: datetime) -> Event:
        if self.repository.member(member_id) is None:
            raise MissingEntity("No existe el integrante.")
        start, end = validate_interval(start, end)
        return self.repository.save_event(
            Event(uuid4(), member_id, clean_text(title, 200), start, end)
        )

    def update_event(self, event_id: UUID, title: str, start: datetime, end: datetime) -> Event:
        previous = self.repository.event(event_id)
        if previous is None:
            raise MissingEntity("No existe el evento.")
        start, end = validate_interval(start, end)
        return self.repository.save_event(
            Event(event_id, previous.member_id, clean_text(title, 200), start, end)
        )

    def delete_event(self, event_id: UUID) -> None:
        if self.repository.event(event_id) is None:
            raise MissingEntity("No existe el evento.")
        self.repository.remove_event(event_id)

    def list_events(self, start: datetime, end: datetime, member_id: UUID | None) -> list[Event]:
        start, end = validate_interval(start, end)
        return self.repository.events(start, end, member_id)
