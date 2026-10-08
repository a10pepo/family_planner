from collections.abc import Iterator
from dataclasses import asdict
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.adapters.daily import SqlDailyRepository
from app.domain.daily import DailyPlanner, Frequency, NoticeIcon, TaskIcon


class NoticeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    title: str = Field(min_length=1, max_length=80)
    icon: NoticeIcon = NoticeIcon.OTHER
    custom_icon_id: UUID | None = None


class NoticeInput(NoticeUpdate):
    member_id: UUID


class NoticeOutput(NoticeInput):
    id: UUID


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=80)
    icon: TaskIcon = TaskIcon.OTHER
    custom_icon_id: UUID | None = None
    frequency: Frequency = Frequency.DAILY
    starts_on: date
    member_ids: list[UUID] = Field(min_length=1, max_length=100)


class TaskOutput(TaskInput):
    id: UUID
    active: bool


class CompletionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UUID
    day: date
    completed: bool


class OccurrenceOutput(BaseModel):
    task_id: UUID
    member_id: UUID
    day: date
    title: str
    icon: TaskIcon
    completed: bool
    custom_icon_id: UUID | None = None


def install_daily_routes(app: FastAPI, engine, guarded):
    def daily() -> Iterator[DailyPlanner]:
        with Session(engine) as session, session.begin():
            yield DailyPlanner(SqlDailyRepository(session))

    use_daily = Annotated[DailyPlanner, Depends(daily)]

    @app.get(
        "/api/v1/notices", response_model=list[NoticeOutput], dependencies=guarded, tags=["notices"]
    )
    def notices(day: date, service: use_daily):
        return [asdict(notice) for notice in service.repository.notices(day)]

    @app.post(
        "/api/v1/notices",
        response_model=NoticeOutput,
        status_code=201,
        dependencies=guarded,
        tags=["notices"],
    )
    def create_notice(data: NoticeInput, service: use_daily):
        return asdict(
            service.create_notice(
                data.member_id, data.day, data.title, data.icon, data.custom_icon_id
            )
        )

    @app.put(
        "/api/v1/notices/{notice_id}",
        response_model=NoticeOutput,
        dependencies=guarded,
        tags=["notices"],
    )
    def update_notice(notice_id: UUID, data: NoticeUpdate, service: use_daily):
        return asdict(
            service.update_notice(
                notice_id,
                data.day,
                data.title,
                data.icon,
                data.custom_icon_id,
                "custom_icon_id" in data.model_fields_set,
            )
        )

    @app.delete(
        "/api/v1/notices/{notice_id}", status_code=204, dependencies=guarded, tags=["notices"]
    )
    def delete_notice(notice_id: UUID, service: use_daily):
        service.delete_notice(notice_id)
        return Response(status_code=204)

    @app.get("/api/v1/tasks", response_model=list[TaskOutput], dependencies=guarded, tags=["tasks"])
    def tasks(service: use_daily):
        return [
            asdict(task)
            for task in service.repository.tasks()
            if task.active
            and any(
                service.repository.member(member_id) is not None for member_id in task.member_ids
            )
        ]

    @app.post(
        "/api/v1/tasks",
        response_model=TaskOutput,
        status_code=201,
        dependencies=guarded,
        tags=["tasks"],
    )
    def create_task(data: TaskInput, service: use_daily):
        return asdict(
            service.save_task(
                data.title,
                data.icon,
                data.frequency,
                data.starts_on,
                data.member_ids,
                custom_icon_id=data.custom_icon_id,
            )
        )

    @app.put(
        "/api/v1/tasks/{task_id}", response_model=TaskOutput, dependencies=guarded, tags=["tasks"]
    )
    def update_task(task_id: UUID, data: TaskInput, service: use_daily):
        return asdict(
            service.save_task(
                data.title,
                data.icon,
                data.frequency,
                data.starts_on,
                data.member_ids,
                task_id,
                data.custom_icon_id,
                "custom_icon_id" in data.model_fields_set,
            )
        )

    @app.delete("/api/v1/tasks/{task_id}", status_code=204, dependencies=guarded, tags=["tasks"])
    def archive_task(task_id: UUID, service: use_daily):
        service.archive_task(task_id)
        return Response(status_code=204)

    @app.get(
        "/api/v1/task-occurrences",
        response_model=list[OccurrenceOutput],
        dependencies=guarded,
        tags=["tasks"],
    )
    def occurrences(day: date, service: use_daily):
        return [asdict(occurrence) for occurrence in service.occurrences(day)]

    @app.put(
        "/api/v1/tasks/{task_id}/completion",
        response_model=OccurrenceOutput,
        dependencies=guarded,
        tags=["tasks"],
    )
    def complete_task(task_id: UUID, data: CompletionInput, service: use_daily):
        return asdict(service.complete(task_id, data.member_id, data.day, data.completed))
