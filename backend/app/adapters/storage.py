from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class RepositoryBundle:
    calendar: Any
    daily: Any
    family: Any
    icons: Any
    recurrence: Any


class SqlStorage:
    def __init__(self, database_url: str):
        from sqlalchemy import text
        from sqlalchemy.orm import Session

        from app.adapters.daily import SqlDailyRepository
        from app.adapters.database import SqlCalendarRepository, make_engine
        from app.adapters.family import SqlFamilyRepository
        from app.adapters.icons import SqlIconRepository
        from app.adapters.recurrence import SqlRecurrenceRepository

        self._text = text
        self._session = Session
        self.engine = make_engine(database_url)
        self._calendar_repository = SqlCalendarRepository
        self._daily_repository = SqlDailyRepository
        self._family_repository = SqlFamilyRepository
        self._icon_repository = SqlIconRepository
        self._recurrence_repository = SqlRecurrenceRepository

    @contextmanager
    def repositories(self) -> Iterator[RepositoryBundle]:
        with self._session(self.engine) as session, session.begin():
            yield RepositoryBundle(
                self._calendar_repository(session),
                self._daily_repository(session),
                self._family_repository(session),
                self._icon_repository(session),
                self._recurrence_repository(session),
            )

    def health(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(self._text("SELECT 1 FROM members LIMIT 1"))


class DynamoStorage:
    def __init__(self, table_name: str, region_name: str | None = None):
        import boto3

        from app.adapters.dynamodb import (
            DynamoAccess,
            DynamoCalendarRepository,
            DynamoDailyRepository,
            DynamoFamilyRepository,
            DynamoIconRepository,
            DynamoRecurrenceRepository,
        )

        table = boto3.resource("dynamodb", region_name=region_name).Table(table_name)
        self.table = table
        self.bundle = RepositoryBundle(
            DynamoCalendarRepository(DynamoAccess(table)),
            DynamoDailyRepository(DynamoAccess(table)),
            DynamoFamilyRepository(DynamoAccess(table)),
            DynamoIconRepository(DynamoAccess(table)),
            DynamoRecurrenceRepository(DynamoAccess(table)),
        )

    @contextmanager
    def repositories(self) -> Iterator[RepositoryBundle]:
        yield self.bundle

    def health(self) -> None:
        self.table.load()


def configured_storage(database_url: str | None = None):
    from os import environ

    if environ.get("STORAGE_BACKEND", "postgresql") == "dynamodb":
        return DynamoStorage(environ["DYNAMODB_TABLE"], environ.get("AWS_REGION"))
    return SqlStorage(database_url or environ["DATABASE_URL"])
