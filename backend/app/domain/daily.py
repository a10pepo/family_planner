from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.calendar import InvalidInput, Member, MissingEntity, clean_text


class NoticeIcon(StrEnum):
    UNIFORM = "uniform"
    TRACKSUIT = "tracksuit"
    TRIP = "trip"
    OTHER = "other"


class TaskIcon(StrEnum):
    TOOTH = "tooth"
    BACKPACK = "backpack"
    BED = "bed"
    OTHER = "other"


class Frequency(StrEnum):
    DAILY = "daily"
    ONCE = "once"


@dataclass(frozen=True)
class Notice:
    id: UUID
    member_id: UUID
    day: date
    title: str
    icon: NoticeIcon
    custom_icon_id: UUID | None = None


@dataclass(frozen=True)
class Task:
    id: UUID
    title: str
    icon: TaskIcon
    frequency: Frequency
    starts_on: date
    member_ids: list[UUID]
    active: bool = True
    custom_icon_id: UUID | None = None


@dataclass(frozen=True)
class Occurrence:
    task_id: UUID
    member_id: UUID
    day: date
    title: str
    icon: TaskIcon
    completed: bool
    custom_icon_id: UUID | None = None


class DailyRepository(Protocol):
    def icon(self, icon_id: UUID): ...
    def member(self, member_id: UUID) -> Member | None: ...
    def notices(self, day: date) -> list[Notice]: ...
    def notice(self, notice_id: UUID) -> Notice | None: ...
    def save_notice(self, notice: Notice) -> Notice: ...
    def remove_notice(self, notice_id: UUID) -> None: ...
    def tasks(self) -> list[Task]: ...
    def task(self, task_id: UUID) -> Task | None: ...
    def save_task(self, task: Task) -> Task: ...
    def completions(self, day: date) -> dict[tuple[UUID, UUID], bool]: ...
    def set_completion(
        self, task_id: UUID, member_id: UUID, day: date, completed: bool
    ) -> None: ...


def occurs_on(task: Task, day: date) -> bool:
    return (
        task.active
        and day >= task.starts_on
        and (task.frequency == Frequency.DAILY or day == task.starts_on)
    )


class DailyPlanner:
    def __init__(self, repository: DailyRepository):
        self.repository = repository

    def validate_icon(self, icon_id: UUID | None):
        if icon_id is not None and self.repository.icon(icon_id) is None:
            raise MissingEntity("No existe el icono.")

    def create_notice(
        self, member_id: UUID, day: date, title: str, icon: str, custom_icon_id: UUID | None = None
    ) -> Notice:
        if self.repository.member(member_id) is None:
            raise MissingEntity("No existe el integrante.")
        self.validate_icon(custom_icon_id)
        try:
            selected_icon = NoticeIcon(icon)
        except ValueError as exc:
            raise InvalidInput("El icono del aviso no es válido.") from exc
        return self.repository.save_notice(
            Notice(uuid4(), member_id, day, clean_text(title, 80), selected_icon, custom_icon_id)
        )

    def update_notice(
        self,
        notice_id: UUID,
        day: date,
        title: str,
        icon: str,
        custom_icon_id: UUID | None = None,
        replace_custom_icon: bool = False,
    ) -> Notice:
        previous = self.repository.notice(notice_id)
        if previous is None or self.repository.member(previous.member_id) is None:
            raise MissingEntity("No existe el aviso.")
        reference = custom_icon_id if replace_custom_icon else previous.custom_icon_id
        self.validate_icon(reference)
        try:
            selected_icon = NoticeIcon(icon)
        except ValueError as exc:
            raise InvalidInput("El icono del aviso no es válido.") from exc
        return self.repository.save_notice(
            replace(
                previous,
                day=day,
                title=clean_text(title, 80),
                icon=selected_icon,
                custom_icon_id=reference,
            )
        )

    def delete_notice(self, notice_id: UUID) -> None:
        previous = self.repository.notice(notice_id)
        if previous is None or self.repository.member(previous.member_id) is None:
            raise MissingEntity("No existe el aviso.")
        self.repository.remove_notice(notice_id)

    def save_task(
        self,
        title: str,
        icon: str,
        frequency: str,
        starts_on: date,
        member_ids: list[UUID],
        task_id: UUID | None = None,
        custom_icon_id: UUID | None = None,
        replace_custom_icon: bool = False,
    ) -> Task:
        previous = None
        if task_id is not None:
            previous = self.repository.task(task_id)
            if previous is None or not previous.active:
                raise MissingEntity("No existe una tarea activa con ese identificador.")
        reference = (
            custom_icon_id if replace_custom_icon or previous is None else previous.custom_icon_id
        )
        self.validate_icon(reference)
        if not member_ids or len(set(member_ids)) != len(member_ids):
            raise InvalidInput("Selecciona al menos un integrante, sin repetirlo.")
        if any(
            self.repository.member(member_id) is None
            and (previous is None or member_id not in previous.member_ids)
            for member_id in member_ids
        ):
            raise MissingEntity("No existe alguno de los integrantes.")
        try:
            selected_icon, repeat = TaskIcon(icon), Frequency(frequency)
        except ValueError as exc:
            raise InvalidInput("El icono o la frecuencia de la tarea no son válidos.") from exc
        return self.repository.save_task(
            Task(
                task_id or uuid4(),
                clean_text(title, 80),
                selected_icon,
                repeat,
                starts_on,
                member_ids,
                custom_icon_id=reference,
            )
        )

    def archive_task(self, task_id: UUID) -> None:
        task = self.repository.task(task_id)
        if task is None:
            raise MissingEntity("No existe la tarea.")
        self.repository.save_task(replace(task, active=False))

    def occurrences(self, day: date) -> list[Occurrence]:
        completed = self.repository.completions(day)
        return [
            Occurrence(
                task.id,
                member_id,
                day,
                task.title,
                task.icon,
                completed.get((task.id, member_id), False),
                task.custom_icon_id,
            )
            for task in self.repository.tasks()
            if occurs_on(task, day)
            for member_id in task.member_ids
            if self.repository.member(member_id) is not None
        ]

    def complete(self, task_id: UUID, member_id: UUID, day: date, completed: bool) -> Occurrence:
        task = self.repository.task(task_id)
        if task is None:
            raise MissingEntity("No existe la tarea.")
        if member_id not in task.member_ids or not occurs_on(task, day):
            raise InvalidInput("La tarea no está asignada a este integrante en esa fecha.")
        if self.repository.member(member_id) is None:
            raise MissingEntity("No existe un integrante activo con ese identificador.")
        self.repository.set_completion(task_id, member_id, day, completed)
        return Occurrence(
            task.id, member_id, day, task.title, task.icon, completed, task.custom_icon_id
        )
