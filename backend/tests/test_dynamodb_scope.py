import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import app.adapters.dynamodb as dynamodb
from app.adapters.dynamodb import (
    DynamoAccess,
    DynamoCalendarRepository,
    DynamoFamilyRepository,
    DynamoRecurrenceRepository,
)
from app.adapters.storage import DynamoStorage
from app.domain.calendar import Category, Event
from app.domain.family import FamilyEvent, FamilyIcon
from app.domain.recurrence import expand_series


class FakeClient:
    def __init__(self):
        self.transactions = []

    def transact_write_items(self, **kwargs):
        self.transactions.append(kwargs["TransactItems"])


class FakeTable:
    name = "family-planner-preview"

    def __init__(self):
        self.meta = SimpleNamespace(client=FakeClient())
        self.items = []

    def get_item(self, **_kwargs):
        return {}

    def put_item(self, **kwargs):
        self.items.append(kwargs["Item"])


def test_family_and_index_partitions_are_derived_from_cognito_sub():
    first = DynamoAccess(FakeTable(), "cognito-family-one")
    second = DynamoAccess(FakeTable(), "cognito-family-two")
    day = date(2026, 10, 10)
    member_id = uuid4()

    assert first.family_pk == "FAMILY#cognito-family-one"
    assert first.family_pk != second.family_pk
    assert first.member_index_pk(member_id) != second.member_index_pk(member_id)
    assert first.day_index_pk(day) != second.day_index_pk(day)
    assert first.completion_day_index_pk(day) != second.completion_day_index_pk(day)


def test_event_put_and_member_condition_share_the_authenticated_partition(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    access = DynamoAccess(table, "family-alpha")
    member_id = uuid4()
    event = Event(
        uuid4(),
        member_id,
        "Colegio",
        datetime(2026, 10, 10, 7, tzinfo=UTC),
        datetime(2026, 10, 10, 12, tzinfo=UTC),
        Category.SCHOOL,
    )

    DynamoCalendarRepository(access).save_event(event)

    condition, put = table.meta.client.transactions[0]
    assert condition["ConditionCheck"]["Key"]["pk"] == "FAMILY#family-alpha"
    assert put["Put"]["Item"]["pk"] == "FAMILY#family-alpha"
    assert put["Put"]["Item"]["gsi1pk"] == "FAMILY#family-alpha"


def test_family_day_index_and_record_use_same_tenant_prefix():
    table = FakeTable()
    access = DynamoAccess(table, "family-beta")
    day = date(2026, 10, 10)
    event = FamilyEvent(uuid4(), day, "Paseo", FamilyIcon.OTHER)

    DynamoFamilyRepository(access).save(event)

    item = table.items[0]
    assert item["pk"] == "FAMILY#family-beta"
    assert item["gsi1pk"] == f"FAMILY#family-beta#DAY#{day.isoformat()}"


def test_event_transaction_uses_injected_low_level_client(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    transaction_client = FakeClient()
    access = DynamoAccess(table, "family-low-level", transaction_client)
    member_id = uuid4()
    event = Event(
        uuid4(),
        member_id,
        "Colegio",
        datetime(2026, 10, 10, 7, tzinfo=UTC),
        datetime(2026, 10, 10, 12, tzinfo=UTC),
        Category.SCHOOL,
    )

    DynamoCalendarRepository(access).save_event(event)

    assert transaction_client.transactions
    assert table.meta.client.transactions == []


def test_dynamo_storage_uses_plain_client_for_transactions(monkeypatch):
    resource_table = FakeTable()
    transaction_client = FakeClient()
    fake_boto3 = SimpleNamespace(
        resource=lambda *_args, **_kwargs: SimpleNamespace(Table=lambda _name: resource_table),
        client=lambda *_args, **_kwargs: transaction_client,
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    storage = DynamoStorage("family-planner-preview", "eu-west-1")
    with storage.repositories("family-alpha") as repositories:
        assert repositories.calendar.access.client is transaction_client
        assert repositories.calendar.access.table is resource_table


def test_recurring_series_normalizes_dynamodb_numbers_before_expansion():
    series = DynamoRecurrenceRepository._series(
        {
            "id": str(uuid4()),
            "member_id": str(uuid4()),
            "title": "Clase",
            "start_date": "2026-10-13",
            "start_time": "09:00:00",
            "duration_minutes": Decimal(30),
            "timezone": "Europe/Madrid",
            "frequency": "weekly",
            "interval": Decimal(1),
            "weekdays": [Decimal(1)],
            "end_mode": "count",
            "occurrence_count": Decimal(1),
            "category": "other",
        }
    )

    events = expand_series(
        series,
        datetime(2026, 10, 13, tzinfo=UTC),
        datetime(2026, 10, 14, tzinfo=UTC),
        [],
    )

    assert len(events) == 1
    assert (events[0].ends_at - events[0].starts_at).total_seconds() == 30 * 60


def test_recurring_exception_normalizes_dynamodb_override_duration():
    exception = DynamoRecurrenceRepository._exception(
        {
            "series_id": str(uuid4()),
            "occurrence_date": "2026-10-13",
            "occurrence_time": "09:00:00",
            "cancelled": False,
            "override_duration_minutes": Decimal(45),
            "has_icon_override": False,
        }
    )

    assert exception.override_duration_minutes == 45
    assert type(exception.override_duration_minutes) is int
