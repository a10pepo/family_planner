import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import app.adapters.dynamodb as dynamodb
import pytest
from app.adapters.dynamodb import (
    DynamoAccess,
    DynamoCalendarRepository,
    DynamoFamilyRepository,
    DynamoRecurrenceRepository,
)
from app.adapters.storage import DynamoStorage
from app.domain.calendar import Category, Event, InvalidInput
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
        self.item = None
        self.records = {}

    def get_item(self, **kwargs):
        key = kwargs.get("Key")
        record_key = (key["pk"], key["sk"]) if key else None
        if record_key in self.records:
            return {"Item": self.records[record_key]}
        if self.item and kwargs.get("Key") == {"pk": self.item["pk"], "sk": self.item["sk"]}:
            return {"Item": self.item}
        return {}

    def query(self, **_kwargs):
        return {"Items": getattr(self, "query_items", [])}

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


def test_family_event_delete_is_transactional_and_conditioned_on_family_event_type(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    access = DynamoAccess(table, "family-delete-test")
    event_id = uuid4()

    DynamoFamilyRepository(access).remove(event_id)

    [delete] = table.meta.client.transactions[0]
    operation = delete["Delete"]
    assert operation["Key"] == {
        "pk": "FAMILY#family-delete-test",
        "sk": f"FAMILY_EVENT#{event_id}",
    }
    assert operation["ConditionExpression"] == "attribute_exists(pk) AND #type = :type"
    assert operation["ExpressionAttributeValues"] == {":type": "family_event"}


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


def test_series_deletion_uses_family_partition_and_checks_item_type_and_exact_keys(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    access = DynamoAccess(table, "family-delete")
    series_id = uuid4()
    exception_sk = f"EXCEPTION#{series_id}#2026-10-20#09:00:00.000000"
    table.query_items = [
        {"pk": access.family_pk, "sk": exception_sk, "type": "exception"},
    ]
    series_sk = f"SERIES#{series_id}"
    table.records[(access.family_pk, series_sk)] = {
        "pk": access.family_pk,
        "sk": series_sk,
        "type": "series",
    }
    access.query = lambda _pk, _prefix, _index=None: table.query_items

    DynamoRecurrenceRepository(access).delete_series(series_id)

    exception_batch, series_batch = table.meta.client.transactions
    condition_check = exception_batch[0]["ConditionCheck"]
    exception_delete = exception_batch[1]["Delete"]
    series_delete = series_batch[0]["Delete"]
    assert condition_check["Key"] == {
        "pk": access.family_pk,
        "sk": f"SERIES#{series_id}",
    }
    assert "#type = :series" in condition_check["ConditionExpression"]
    assert exception_delete["Key"] == {"pk": access.family_pk, "sk": exception_sk}
    assert "#type = :exception" in exception_delete["ConditionExpression"]
    assert "begins_with(sk, :exception_prefix)" in exception_delete["ConditionExpression"]
    assert exception_delete["ExpressionAttributeValues"][":exception_prefix"] == (
        f"EXCEPTION#{series_id}#"
    )
    assert series_delete["Key"] == {"pk": access.family_pk, "sk": f"SERIES#{series_id}"}
    assert "#type = :series" in series_delete["ConditionExpression"]
    assert all(
        operation.get("Delete", {}).get("TableName") == table.name
        for operation in [exception_batch[1], series_batch[0]]
    )


def test_exception_deletion_checks_family_series_and_exception_type_and_key(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    access = DynamoAccess(table, "family-restore")
    series_id = uuid4()
    day = date(2026, 10, 20)
    exception_sk = f"EXCEPTION#{series_id}#2026-10-20#00:00:00.000000"
    table.item = {"pk": access.family_pk, "sk": exception_sk, "type": "exception"}
    series_sk = f"SERIES#{series_id}"
    table.records[(access.family_pk, series_sk)] = {
        "pk": access.family_pk,
        "sk": series_sk,
        "type": "series",
    }

    DynamoRecurrenceRepository(access).delete_exception(series_id, day, datetime.min.time())

    parent_check, exception_delete = table.meta.client.transactions[0]
    assert parent_check["ConditionCheck"]["Key"] == {
        "pk": access.family_pk,
        "sk": f"SERIES#{series_id}",
    }
    assert "#type = :series" in parent_check["ConditionCheck"]["ConditionExpression"]
    delete = exception_delete["Delete"]
    assert delete["Key"]["pk"] == access.family_pk
    assert delete["Key"]["sk"] == (f"EXCEPTION#{series_id}#2026-10-20#00:00:00.000000")
    assert "#type = :exception" in delete["ConditionExpression"]
    assert "sk = :exception_key" in delete["ConditionExpression"]


def test_series_deletion_rejects_unexpected_exception_item_type_before_transaction(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    access = DynamoAccess(table, "family-invalid-delete")
    series_id = uuid4()
    series_sk = f"SERIES#{series_id}"
    table.records[(access.family_pk, series_sk)] = {
        "pk": access.family_pk,
        "sk": series_sk,
        "type": "series",
    }
    table.query_items = [
        {
            "pk": access.family_pk,
            "sk": f"EXCEPTION#{series_id}#2026-10-20#09:00:00.000000",
            "type": "event",
        }
    ]
    access.query = lambda _pk, _prefix, _index=None: table.query_items

    with pytest.raises(InvalidInput, match="no identifica una excepción"):
        DynamoRecurrenceRepository(access).delete_series(series_id)
    assert table.meta.client.transactions == []


def test_series_deletion_rejects_wrong_item_type_at_series_key(monkeypatch):
    monkeypatch.setattr(dynamodb, "_serialize", lambda item: item)
    table = FakeTable()
    access = DynamoAccess(table, "family-invalid-series")
    series_id = uuid4()
    series_sk = f"SERIES#{series_id}"
    table.records[(access.family_pk, series_sk)] = {
        "pk": access.family_pk,
        "sk": series_sk,
        "type": "event",
    }

    with pytest.raises(InvalidInput, match="no identifica una serie"):
        DynamoRecurrenceRepository(access).delete_series(series_id)
    assert table.meta.client.transactions == []
