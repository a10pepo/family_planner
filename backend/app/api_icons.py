from collections.abc import Iterator
from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.adapters.photos import normalize_icon
from app.domain.icons import IconLibrary


class IconInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    image_data: str = Field(min_length=1, max_length=2_800_000)


class IconOutput(IconInput):
    id: UUID


def install_icon_routes(app: FastAPI, storage, guarded):
    def library() -> Iterator[IconLibrary]:
        with storage.repositories() as repositories:
            yield IconLibrary(repositories.icons)

    use_library = Annotated[IconLibrary, Depends(library)]

    @app.get("/api/v1/icons", response_model=list[IconOutput], dependencies=guarded, tags=["icons"])
    def icons(service: use_library):
        return [asdict(icon) for icon in service.repository.icons()]

    @app.post(
        "/api/v1/icons",
        response_model=IconOutput,
        status_code=201,
        dependencies=guarded,
        tags=["icons"],
    )
    def add_icon(data: IconInput, service: use_library):
        return asdict(service.add(data.name, normalize_icon(data.image_data)))
