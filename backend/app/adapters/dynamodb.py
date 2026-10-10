"""DynamoDB repositories for the single-family AWS runtime."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer

from app.domain.calendar import Category, Event, InvalidInput, Member, MissingEntity
from app.domain.daily import Frequency, Notice, NoticeIcon, Task, TaskIcon
from app.domain.family import FamilyEvent, FamilyIcon
from app.domain.icons import CustomIcon
from app.domain.recurrence import EndMode, EventException, EventSeries
from app.domain.recurrence import Frequency as SeriesFrequency

FAMILY_PK = "FAMILY#default"
_SERIALIZER = TypeSerializer()


def _date(value: date) -> str:
    return value.isoformat()


def _time(value: time) -> str:
    return value.isoformat(timespec="microseconds")


def _datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _uuid(value: UUID | None) -> str | None:
    return str(value) if value else None


def _serialize(item: dict[str, Any]) -> dict[str, Any]:
    return {key: _SERIALIZER.serialize(value) for key, value in item.items()}


class DynamoAccess:
    def __init__(self, table):
        self.table = table
        self.client = table.meta.client

    def get(self, pk: str, sk: str) -> dict[str, Any] | None:
        return self.table.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True).get("Item")

    def query(self, pk: str, prefix: str, index: str | None = None) -> list[dict[str, Any]]:
        args: dict[str, Any] = {
            "KeyConditionExpression": Key("pk").eq(pk) & Key("sk").begins_with(prefix),
        }
        if index:
            args["IndexName"] = index
            args["KeyConditionExpression"] = Key("gsi1pk" if index == "by-day" else "gsi2pk").eq(pk)
            sort_key = "gsi1sk" if index == "by-day" else "gsi2sk"
            if prefix:
                args["KeyConditionExpression"] &= Key(sort_key).begins_with(prefix)
        results: list[dict[str, Any]] = []
        while True:
            page = self.table.query(**args)
            results.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                return results
            args["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def query_range(
        self,
        index: str,
        partition_key: str,
        sort_key_name: str,
        sort_prefix: str,
        lower_bound: str,
    ) -> list[dict[str, Any]]:
        args: dict[str, Any] = {
            "IndexName": index,
            "KeyConditionExpression": Key("gsi1pk").eq(partition_key)
            & Key(sort_key_name).between(f"{sort_prefix}{lower_bound}", f"{sort_prefix}~"),
        }
        results: list[dict[str, Any]] = []
        while True:
            page = self.table.query(**args)
            results.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                return results
            args["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def transact_member_put(
        self,
        member_id: UUID,
        item: dict[str, Any],
        condition: str,
        values: dict[str, Any] | None = None,
    ) -> None:
        operations = [
            {
                "ConditionCheck": {
                    "TableName": self.table.name,
                    "Key": _serialize({"pk": FAMILY_PK, "sk": f"MEMBER#{member_id}"}),
                    "ConditionExpression": "attribute_exists(pk) AND #active = :active",
                    "ExpressionAttributeNames": {"#active": "active"},
                    "ExpressionAttributeValues": _serialize({":active": True}),
                }
            },
            {
                "Put": {
                    "TableName": self.table.name,
                    "Item": _serialize(item),
                    "ConditionExpression": condition,
                    **(
                        {
                            "ExpressionAttributeValues": _serialize(values),
                        }
                        if values
                        else {}
                    ),
                }
            },
        ]
        self.client.transact_write_items(TransactItems=operations)


class DynamoCalendarRepository:
    def __init__(self, access: DynamoAccess):
        self.access = access

    def icon(self, icon_id: UUID):
        row = self.access.get(FAMILY_PK, f"ICON#{icon_id}")
        return CustomIcon(UUID(row["id"]), row["name"], row["image_data"]) if row else None

    def members(self, include_archived: bool = False) -> list[Member]:
        rows = self.access.query(FAMILY_PK, "MEMBER#")
        members = [
            Member(UUID(row["id"]), row["name"], row["color"], row.get("photo_data"), row["active"])
            for row in rows
            if include_archived or row["active"]
        ]
        created = {row["id"]: row.get("created_at", "") for row in rows}
        return sorted(members, key=lambda member: created.get(str(member.id), ""))

    def member(self, member_id: UUID, include_archived: bool = False) -> Member | None:
        row = self.access.get(FAMILY_PK, f"MEMBER#{member_id}")
        if not row or (not row["active"] and not include_archived):
            return None
        return Member(
            UUID(row["id"]), row["name"], row["color"], row.get("photo_data"), row["active"]
        )

    def add_member(self, member: Member) -> Member:
        item = {
            "pk": FAMILY_PK,
            "sk": f"MEMBER#{member.id}",
            "type": "member",
            "id": str(member.id),
            "name": member.name,
            "color": member.color,
            "active": True,
            "created_at": _datetime(datetime.now(UTC)),
        }
        self.access.table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
        )
        return member

    def save_member(self, member: Member) -> Member:
        previous = self.access.get(FAMILY_PK, f"MEMBER#{member.id}")
        if previous is None:
            raise MissingEntity("No existe el integrante.")
        item = {
            **previous,
            "name": member.name,
            "color": member.color,
            "active": member.active,
        }
        if member.photo_data is None:
            item.pop("photo_data", None)
        else:
            item["photo_data"] = member.photo_data
        self.access.table.put_item(
            Item=item,
            ConditionExpression="attribute_exists(pk) AND attribute_exists(sk)",
        )
        return member

    def events(self, start: datetime, end: datetime, member_id: UUID | None) -> list[Event]:
        rows = self.access.query_range(
            "by-calendar-end", FAMILY_PK, "gsi1sk", "EVENT_END#", _datetime(start)
        )
        members = {member.id for member in self.members()}
        events = [
            self._event(row)
            for row in rows
            if row["member_id"] in {str(value) for value in members}
            and datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00")) > start
            and datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00")) < end
            and (member_id is None or row["member_id"] == str(member_id))
        ]
        return sorted(events, key=lambda event: event.starts_at)

    @staticmethod
    def _event(row: dict[str, Any]) -> Event:
        return Event(
            UUID(row["id"]),
            UUID(row["member_id"]),
            row["title"],
            datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00")),
            datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00")),
            Category(row["category"]),
            UUID(row["custom_icon_id"]) if row.get("custom_icon_id") else None,
        )

    def event(self, event_id: UUID) -> Event | None:
        row = self.access.get(FAMILY_PK, f"EVENT#{event_id}")
        return self._event(row) if row and self.member(UUID(row["member_id"])) else None

    def save_event(self, event: Event) -> Event:
        key = {"pk": FAMILY_PK, "sk": f"EVENT#{event.id}"}
        previous = self.access.get(**key)
        item = {
            **key,
            "type": "event",
            "id": str(event.id),
            "member_id": str(event.member_id),
            "title": event.title,
            "starts_at": _datetime(event.starts_at),
            "ends_at": _datetime(event.ends_at),
            "category": event.category.value,
            "gsi1pk": FAMILY_PK,
            "gsi1sk": f"EVENT_END#{_datetime(event.ends_at)}#{event.id}",
            "updated_at": _datetime(datetime.now(UTC)),
        }
        if event.custom_icon_id:
            item["custom_icon_id"] = str(event.custom_icon_id)
        self.access.transact_member_put(
            event.member_id,
            item,
            "attribute_exists(pk)" if previous else "attribute_not_exists(pk)",
        )
        return event

    def remove_event(self, event_id: UUID) -> None:
        row = self.access.get(FAMILY_PK, f"EVENT#{event_id}")
        if not row:
            return
        operations = [
            {
                "ConditionCheck": {
                    "TableName": self.access.table.name,
                    "Key": _serialize({"pk": FAMILY_PK, "sk": f"MEMBER#{row['member_id']}"}),
                    "ConditionExpression": "attribute_exists(pk) AND #active = :active",
                    "ExpressionAttributeNames": {"#active": "active"},
                    "ExpressionAttributeValues": _serialize({":active": True}),
                }
            },
            {
                "Delete": {
                    "TableName": self.access.table.name,
                    "Key": _serialize({"pk": FAMILY_PK, "sk": f"EVENT#{event_id}"}),
                    "ConditionExpression": "attribute_exists(pk)",
                }
            },
        ]
        self.access.client.transact_write_items(TransactItems=operations)


class DynamoDailyRepository:
    def __init__(self, access: DynamoAccess):
        self.access = access
        self.calendar = DynamoCalendarRepository(access)

    def icon(self, icon_id: UUID):
        return self.calendar.icon(icon_id)

    def member(self, member_id: UUID):
        return self.calendar.member(member_id)

    def notices(self, day: date) -> list[Notice]:
        rows = self.access.query(f"DAY#{_date(day)}", "NOTICE#", "by-day")
        return [self._notice(row) for row in rows if self.member(UUID(row["member_id"]))]

    @staticmethod
    def _notice(row: dict[str, Any]) -> Notice:
        return Notice(
            UUID(row["id"]),
            UUID(row["member_id"]),
            date.fromisoformat(row["day"]),
            row["title"],
            NoticeIcon(row["icon"]),
            UUID(row["custom_icon_id"]) if row.get("custom_icon_id") else None,
        )

    def notice(self, notice_id: UUID) -> Notice | None:
        row = self.access.get(FAMILY_PK, f"NOTICE#{notice_id}")
        return self._notice(row) if row and self.member(UUID(row["member_id"])) else None

    def save_notice(self, notice: Notice) -> Notice:
        previous = self.access.get(FAMILY_PK, f"NOTICE#{notice.id}")
        item = {
            "pk": FAMILY_PK,
            "sk": f"NOTICE#{notice.id}",
            "type": "notice",
            "id": str(notice.id),
            "member_id": str(notice.member_id),
            "day": _date(notice.day),
            "title": notice.title,
            "icon": notice.icon.value,
            "gsi1pk": f"DAY#{_date(notice.day)}",
            "gsi1sk": f"NOTICE#{notice.member_id}#{notice.id}",
        }
        if notice.custom_icon_id:
            item["custom_icon_id"] = str(notice.custom_icon_id)
        self.access.transact_member_put(
            notice.member_id,
            item,
            "attribute_exists(pk)" if previous else "attribute_not_exists(pk)",
        )
        return notice

    def remove_notice(self, notice_id: UUID) -> None:
        self.access.table.delete_item(Key={"pk": FAMILY_PK, "sk": f"NOTICE#{notice_id}"})

    def tasks(self) -> list[Task]:
        rows = self.access.query(FAMILY_PK, "TASK#")
        return [self._task(row) for row in rows]

    @staticmethod
    def _task(row: dict[str, Any]) -> Task:
        return Task(
            UUID(row["id"]),
            row["title"],
            TaskIcon(row["icon"]),
            Frequency(row["frequency"]),
            date.fromisoformat(row["starts_on"]),
            [UUID(member) for member in row["member_ids"]],
            row["active"],
            UUID(row["custom_icon_id"]) if row.get("custom_icon_id") else None,
        )

    def task(self, task_id: UUID) -> Task | None:
        row = self.access.get(FAMILY_PK, f"TASK#{task_id}")
        return self._task(row) if row else None

    def save_task(self, task: Task) -> Task:
        if len(task.member_ids) > 99:
            raise InvalidInput("Una tarea no puede asignarse a más de 99 integrantes en AWS.")
        previous = self.access.get(FAMILY_PK, f"TASK#{task.id}")
        item = {
            "pk": FAMILY_PK,
            "sk": f"TASK#{task.id}",
            "type": "task",
            "id": str(task.id),
            "title": task.title,
            "icon": task.icon.value,
            "frequency": task.frequency.value,
            "starts_on": _date(task.starts_on),
            "member_ids": [str(member_id) for member_id in task.member_ids],
            "active": task.active,
            "created_at": previous.get("created_at", _datetime(datetime.now(UTC)))
            if previous
            else _datetime(datetime.now(UTC)),
        }
        if task.custom_icon_id:
            item["custom_icon_id"] = str(task.custom_icon_id)
        operations = []
        for member_id in task.member_ids:
            member = self.access.get(FAMILY_PK, f"MEMBER#{member_id}")
            retained_archived = (
                member
                and not member["active"]
                and previous
                and str(member_id) in previous["member_ids"]
            )
            if not member or (not member["active"] and not retained_archived):
                raise MissingEntity("No existe alguno de los integrantes activos.")
            operations.append(
                {
                    "ConditionCheck": {
                        "TableName": self.access.table.name,
                        "Key": _serialize({"pk": FAMILY_PK, "sk": f"MEMBER#{member_id}"}),
                        "ConditionExpression": "attribute_exists(pk) AND #active = :active",
                        "ExpressionAttributeNames": {"#active": "active"},
                        "ExpressionAttributeValues": _serialize({":active": not retained_archived}),
                    }
                }
            )
        operations.append(
            {
                "Put": {
                    "TableName": self.access.table.name,
                    "Item": _serialize(item),
                    "ConditionExpression": (
                        "attribute_not_exists(pk)" if previous is None else "attribute_exists(pk)"
                    ),
                }
            }
        )
        self.access.client.transact_write_items(TransactItems=operations)
        return task

    def completions(self, day: date) -> dict[tuple[UUID, UUID], bool]:
        rows = self.access.query(f"TASKDAY#{_date(day)}", "", "by-completion-day")
        return {(UUID(row["task_id"]), UUID(row["member_id"])): row["completed"] for row in rows}

    def set_completion(self, task_id: UUID, member_id: UUID, day: date, completed: bool) -> None:
        task = self.access.get(FAMILY_PK, f"TASK#{task_id}")
        member = self.access.get(FAMILY_PK, f"MEMBER#{member_id}")
        if not task or not task["active"] or str(member_id) not in task["member_ids"]:
            raise MissingEntity("La tarea ya no está asignada a un integrante activo.")
        if not member or not member["active"]:
            raise MissingEntity("No existe un integrante activo con ese identificador.")
        item = {
            "pk": f"MEMBER#{member_id}",
            "sk": f"COMPLETION#{_date(day)}#{task_id}",
            "type": "completion",
            "task_id": str(task_id),
            "member_id": str(member_id),
            "day": _date(day),
            "completed": completed,
            "gsi2pk": f"TASKDAY#{_date(day)}",
            "gsi2sk": f"MEMBER#{member_id}#TASK#{task_id}",
            "updated_at": _datetime(datetime.now(UTC)),
        }
        self.access.client.transact_write_items(
            TransactItems=[
                {
                    "ConditionCheck": {
                        "TableName": self.access.table.name,
                        "Key": _serialize({"pk": FAMILY_PK, "sk": f"TASK#{task_id}"}),
                        "ConditionExpression": (
                            "attribute_exists(pk) AND #active = :active "
                            "AND contains(member_ids, :member)"
                        ),
                        "ExpressionAttributeNames": {"#active": "active"},
                        "ExpressionAttributeValues": _serialize(
                            {":active": True, ":member": str(member_id)}
                        ),
                    }
                },
                {
                    "ConditionCheck": {
                        "TableName": self.access.table.name,
                        "Key": _serialize({"pk": FAMILY_PK, "sk": f"MEMBER#{member_id}"}),
                        "ConditionExpression": "attribute_exists(pk) AND #active = :active",
                        "ExpressionAttributeNames": {"#active": "active"},
                        "ExpressionAttributeValues": _serialize({":active": True}),
                    }
                },
                {"Put": {"TableName": self.access.table.name, "Item": _serialize(item)}},
            ]
        )


class DynamoFamilyRepository:
    def __init__(self, access: DynamoAccess):
        self.access = access
        self.calendar = DynamoCalendarRepository(access)

    def icon(self, icon_id: UUID):
        return self.calendar.icon(icon_id)

    def events(self, start: date, end: date) -> list[FamilyEvent]:
        result: list[FamilyEvent] = []
        day = start
        while day < end:
            rows = self.access.query(f"DAY#{_date(day)}", "FAMILY_EVENT#", "by-day")
            result.extend(self._event(row) for row in rows)
            day = date.fromordinal(day.toordinal() + 1)
        return sorted(result, key=lambda item: (item.day, item.title, item.id))

    @staticmethod
    def _event(row: dict[str, Any]) -> FamilyEvent:
        return FamilyEvent(
            UUID(row["id"]),
            date.fromisoformat(row["day"]),
            row["title"],
            FamilyIcon(row["icon"]),
            UUID(row["custom_icon_id"]) if row.get("custom_icon_id") else None,
        )

    def event(self, event_id: UUID) -> FamilyEvent | None:
        row = self.access.get(FAMILY_PK, f"FAMILY_EVENT#{event_id}")
        return self._event(row) if row else None

    def save(self, event: FamilyEvent) -> FamilyEvent:
        previous = self.access.get(FAMILY_PK, f"FAMILY_EVENT#{event.id}")
        item = {
            "pk": FAMILY_PK,
            "sk": f"FAMILY_EVENT#{event.id}",
            "type": "family_event",
            "id": str(event.id),
            "day": _date(event.day),
            "title": event.title,
            "icon": event.icon.value,
            "gsi1pk": f"DAY#{_date(event.day)}",
            "gsi1sk": f"FAMILY_EVENT#{event.title}#{event.id}",
        }
        if event.custom_icon_id:
            item["custom_icon_id"] = str(event.custom_icon_id)
        self.access.table.put_item(
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(pk)" if previous is None else "attribute_exists(pk)"
            ),
        )
        return event

    def remove(self, event_id: UUID) -> None:
        self.access.table.delete_item(Key={"pk": FAMILY_PK, "sk": f"FAMILY_EVENT#{event_id}"})


class DynamoIconRepository:
    def __init__(self, access: DynamoAccess):
        self.access = access

    def icons(self) -> list[CustomIcon]:
        rows = self.access.query(FAMILY_PK, "ICON#")
        return [CustomIcon(UUID(row["id"]), row["name"], row["image_data"]) for row in rows]

    def icon(self, icon_id: UUID) -> CustomIcon | None:
        row = self.access.get(FAMILY_PK, f"ICON#{icon_id}")
        return CustomIcon(UUID(row["id"]), row["name"], row["image_data"]) if row else None

    def add_icon(self, icon: CustomIcon) -> CustomIcon:
        self.access.table.put_item(
            Item={
                "pk": FAMILY_PK,
                "sk": f"ICON#{icon.id}",
                "type": "icon",
                "id": str(icon.id),
                "name": icon.name,
                "image_data": icon.image_data,
                "created_at": _datetime(datetime.now(UTC)),
            },
            ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
        )
        return icon


class DynamoRecurrenceRepository:
    def __init__(self, access: DynamoAccess):
        self.access = access
        self.calendar = DynamoCalendarRepository(access)

    def series(
        self, member_id: UUID | None = None, include_archived: bool = False
    ) -> list[EventSeries]:
        if member_id:
            rows = self.access.query(f"MEMBER#{member_id}", "SERIES#", "by-member")
        else:
            rows = self.access.query(FAMILY_PK, "SERIES#")
        series = [self._series(row) for row in rows]
        return sorted(
            [item for item in series if include_archived or self.calendar.member(item.member_id)],
            key=lambda item: (item.start_date, item.start_time),
        )

    @staticmethod
    def _series(row: dict[str, Any]) -> EventSeries:
        return EventSeries(
            UUID(row["id"]),
            UUID(row["member_id"]),
            row["title"],
            date.fromisoformat(row["start_date"]),
            time.fromisoformat(row["start_time"]),
            row["duration_minutes"],
            row["timezone"],
            SeriesFrequency(row["frequency"]),
            row["interval"],
            tuple(row["weekdays"]),
            EndMode(row["end_mode"]),
            date.fromisoformat(row["end_date"]) if row.get("end_date") else None,
            row.get("occurrence_count"),
            Category(row["category"]),
            UUID(row["custom_icon_id"]) if row.get("custom_icon_id") else None,
        )

    def get_series(self, series_id: UUID) -> EventSeries | None:
        row = self.access.get(FAMILY_PK, f"SERIES#{series_id}")
        if not row or not self.calendar.member(UUID(row["member_id"])):
            return None
        return self._series(row)

    def save_series(self, series: EventSeries) -> EventSeries:
        previous = self.access.get(FAMILY_PK, f"SERIES#{series.id}")
        item = {
            "pk": FAMILY_PK,
            "sk": f"SERIES#{series.id}",
            "type": "series",
            "id": str(series.id),
            "member_id": str(series.member_id),
            "title": series.title,
            "start_date": _date(series.start_date),
            "start_time": _time(series.start_time),
            "duration_minutes": series.duration_minutes,
            "timezone": series.timezone,
            "frequency": series.frequency.value,
            "interval": series.interval,
            "weekdays": list(series.weekdays),
            "end_mode": series.end_mode.value,
            "category": series.category.value,
            "gsi2pk": f"MEMBER#{series.member_id}",
            "gsi2sk": f"SERIES#{_date(series.start_date)}#{_time(series.start_time)}#{series.id}",
        }
        if series.end_date:
            item["end_date"] = _date(series.end_date)
        if series.occurrence_count:
            item["occurrence_count"] = series.occurrence_count
        if series.custom_icon_id:
            item["custom_icon_id"] = str(series.custom_icon_id)
        self.access.transact_member_put(
            series.member_id,
            item,
            "attribute_exists(pk)" if previous else "attribute_not_exists(pk)",
        )
        return series

    def delete_series(self, series_id: UUID) -> None:
        for row in self.access.query(f"SERIES#{series_id}", "EXCEPTION#"):
            self.access.table.delete_item(Key={"pk": row["pk"], "sk": row["sk"]})
        self.access.table.delete_item(Key={"pk": FAMILY_PK, "sk": f"SERIES#{series_id}"})

    def exceptions(self, series_id: UUID) -> list[EventException]:
        rows = self.access.query(f"SERIES#{series_id}", "EXCEPTION#")
        return [self._exception(row) for row in rows]

    @staticmethod
    def _exception(row: dict[str, Any]) -> EventException:
        return EventException(
            UUID(row["series_id"]),
            date.fromisoformat(row["occurrence_date"]),
            time.fromisoformat(row["occurrence_time"]),
            row["cancelled"],
            time.fromisoformat(row["override_start_time"])
            if row.get("override_start_time")
            else None,
            row.get("override_duration_minutes"),
            row.get("override_title"),
            Category(row["override_category"]) if row.get("override_category") else None,
            row["has_icon_override"],
            UUID(row["override_custom_icon_id"]) if row.get("override_custom_icon_id") else None,
        )

    def save_exception(self, exception: EventException) -> EventException:
        sk = f"EXCEPTION#{_date(exception.occurrence_date)}#{_time(exception.occurrence_time)}"
        item = {
            "pk": f"SERIES#{exception.series_id}",
            "sk": sk,
            "type": "exception",
            "series_id": str(exception.series_id),
            "occurrence_date": _date(exception.occurrence_date),
            "occurrence_time": _time(exception.occurrence_time),
            "cancelled": exception.cancelled,
            "has_icon_override": exception.has_icon_override,
        }
        for key, value in (
            (
                "override_start_time",
                _time(exception.override_start_time) if exception.override_start_time else None,
            ),
            ("override_duration_minutes", exception.override_duration_minutes),
            ("override_title", exception.override_title),
            (
                "override_category",
                exception.override_category.value if exception.override_category else None,
            ),
            ("override_custom_icon_id", _uuid(exception.override_custom_icon_id)),
        ):
            if value is not None:
                item[key] = value
        self.access.client.transact_write_items(
            TransactItems=[
                {
                    "ConditionCheck": {
                        "TableName": self.access.table.name,
                        "Key": _serialize({"pk": FAMILY_PK, "sk": f"SERIES#{exception.series_id}"}),
                        "ConditionExpression": "attribute_exists(pk)",
                    }
                },
                {"Put": {"TableName": self.access.table.name, "Item": _serialize(item)}},
            ]
        )
        return exception

    def delete_exception(
        self, series_id: UUID, occurrence_date: date, occurrence_time: time
    ) -> None:
        sk = f"EXCEPTION#{_date(occurrence_date)}#{_time(occurrence_time)}"
        self.access.table.delete_item(Key={"pk": f"SERIES#{series_id}", "sk": sk})
