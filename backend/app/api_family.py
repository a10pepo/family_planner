from collections.abc import Iterator
from dataclasses import asdict
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.adapters.family import SqlFamilyRepository
from app.domain.family import FamilyIcon, FamilyPlanner


class FamilyEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    title: str = Field(min_length=1, max_length=80)
    icon: FamilyIcon = FamilyIcon.BIRTHDAY
    custom_icon_id: UUID | None = None


class FamilyEventOutput(FamilyEventInput):
    id: UUID


def install_family_routes(app: FastAPI, engine, guarded):
    def family() -> Iterator[FamilyPlanner]:
        with Session(engine) as session, session.begin():
            yield FamilyPlanner(SqlFamilyRepository(session))

    use_family = Annotated[FamilyPlanner, Depends(family)]

    @app.get(
        "/api/v1/family-events",
        response_model=list[FamilyEventOutput],
        dependencies=guarded,
        tags=["family-events"],
    )
    def events(start: date, end: date, service: use_family):
        return [asdict(item) for item in service.list_events(start, end)]

    @app.post(
        "/api/v1/family-events",
        response_model=FamilyEventOutput,
        status_code=201,
        dependencies=guarded,
        tags=["family-events"],
    )
    def add_event(data: FamilyEventInput, service: use_family):
        return asdict(service.save(data.day, data.title, data.icon, data.custom_icon_id))

    @app.put(
        "/api/v1/family-events/{event_id}",
        response_model=FamilyEventOutput,
        dependencies=guarded,
        tags=["family-events"],
    )
    def update_event(event_id: UUID, data: FamilyEventInput, service: use_family):
        return asdict(
            service.save(
                data.day,
                data.title,
                data.icon,
                data.custom_icon_id,
                event_id,
                "custom_icon_id" in data.model_fields_set,
            )
        )

    @app.delete(
        "/api/v1/family-events/{event_id}",
        status_code=204,
        dependencies=guarded,
        tags=["family-events"],
    )
    def remove_event(event_id: UUID, service: use_family):
        service.remove(event_id)
        return Response(status_code=204)
