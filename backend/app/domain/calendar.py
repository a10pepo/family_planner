from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4


class InvalidInput(ValueError):
    pass


class MissingEntity(LookupError):
    pass


class Category(StrEnum):
    SCHOOL = "school"
    ACTIVITIES = "activities"
    MEDICAL = "medical"
    FRIENDS = "friends"
    OTHER = "other"


def validate_category(value: str) -> Category:
    try:
        return Category(value)
    except ValueError as exc:
        raise InvalidInput("La categoría del evento no es válida.") from exc


@dataclass(frozen=True)
class Member:
    id: UUID
    name: str
    color: str
    photo_data: str | None = None


@dataclass(frozen=True)
class Event:
    id: UUID
    member_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    category: Category = Category.OTHER
    custom_icon_id: UUID | None = None


class CalendarRepository(Protocol):
    def icon(self, icon_id: UUID): ...
    def members(self) -> list[Member]: ...
    def member(self, member_id: UUID) -> Member | None: ...
    def add_member(self, member: Member) -> Member: ...
    def save_member(self, member: Member) -> Member: ...
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

    def update_member(
        self,
        member_id: UUID,
        name: str,
        photo_data: str | None = None,
        replace_photo: bool = False,
    ) -> Member:
        previous = self.repository.member(member_id)
        if previous is None:
            raise MissingEntity("No existe el integrante.")
        return self.repository.save_member(
            Member(
                previous.id,
                clean_text(name, 80),
                previous.color,
                photo_data if replace_photo else previous.photo_data,
            )
        )

    def create_event(
        self,
        member_id: UUID,
        title: str,
        start: datetime,
        end: datetime,
        category: str = Category.OTHER,
        custom_icon_id: UUID | None = None,
    ) -> Event:
        if self.repository.member(member_id) is None:
            raise MissingEntity("No existe el integrante.")
        if custom_icon_id is not None and self.repository.icon(custom_icon_id) is None:
            raise MissingEntity("No existe el icono.")
        start, end = validate_interval(start, end)
        return self.repository.save_event(
            Event(
                uuid4(),
                member_id,
                clean_text(title, 200),
                start,
                end,
                validate_category(category),
                custom_icon_id,
            )
        )

    def update_event(
        self,
        event_id: UUID,
        title: str,
        start: datetime,
        end: datetime,
        category: str | None = None,
        custom_icon_id: UUID | None = None,
        replace_custom_icon: bool = False,
    ) -> Event:
        previous = self.repository.event(event_id)
        if previous is None:
            raise MissingEntity("No existe el evento.")
        reference = custom_icon_id if replace_custom_icon else previous.custom_icon_id
        if reference is not None and self.repository.icon(reference) is None:
            raise MissingEntity("No existe el icono.")
        start, end = validate_interval(start, end)
        return self.repository.save_event(
            Event(
                event_id,
                previous.member_id,
                clean_text(title, 200),
                start,
                end,
                previous.category if category is None else validate_category(category),
                reference,
            )
        )

    def delete_event(self, event_id: UUID) -> None:
        if self.repository.event(event_id) is None:
            raise MissingEntity("No existe el evento.")
        self.repository.remove_event(event_id)

    def list_events(self, start: datetime, end: datetime, member_id: UUID | None) -> list[Event]:
        start, end = validate_interval(start, end)
        return self.repository.events(start, end, member_id)
