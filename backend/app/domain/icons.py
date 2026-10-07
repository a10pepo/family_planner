from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.calendar import clean_text


@dataclass(frozen=True)
class CustomIcon:
    id: UUID
    name: str
    image_data: str


class IconRepository(Protocol):
    def icons(self) -> list[CustomIcon]: ...
    def icon(self, icon_id: UUID) -> CustomIcon | None: ...
    def add_icon(self, icon: CustomIcon) -> CustomIcon: ...


class IconLibrary:
    def __init__(self, repository: IconRepository):
        self.repository = repository

    def add(self, name: str, normalized_image: str) -> CustomIcon:
        return self.repository.add_icon(CustomIcon(uuid4(), clean_text(name, 80), normalized_image))
