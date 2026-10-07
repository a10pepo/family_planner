from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.database import IconRow
from app.domain.icons import CustomIcon


def to_icon(row: IconRow) -> CustomIcon:
    return CustomIcon(row.id, row.name, row.image_data)


class SqlIconRepository:
    def __init__(self, session: Session):
        self.session = session

    def icons(self) -> list[CustomIcon]:
        return [
            to_icon(row)
            for row in self.session.scalars(
                select(IconRow).order_by(IconRow.created_at, IconRow.id)
            )
        ]

    def icon(self, icon_id: UUID) -> CustomIcon | None:
        row = self.session.get(IconRow, icon_id)
        return to_icon(row) if row else None

    def add_icon(self, icon: CustomIcon) -> CustomIcon:
        self.session.add(
            IconRow(
                id=icon.id, name=icon.name, image_data=icon.image_data, created_at=datetime.now(UTC)
            )
        )
        self.session.flush()
        return icon
