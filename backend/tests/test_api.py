import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.adapters.database import Base, make_engine
from app.api import create_app
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text


class TestVerifier:
    def verify(self, token):
        if token != "valid":
            raise HTTPException(401, "Invalid test token")
        return {"sub": "fictional-family"}


@pytest.fixture(scope="module")
def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Integration tests require a disposable PostgreSQL TEST_DATABASE_URL.")
    if not url.endswith("/family_test"):
        pytest.fail("Integration tests only run against the disposable family_test database.")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    yield url, engine
    engine.dispose()
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous


@pytest.fixture
def client(database):
    url, engine = database
    with engine.begin() as connection:
        for table in ("task_completions", "task_assignments", "all_day_notices", "tasks"):
            connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text("DELETE FROM events"))
        connection.execute(text("DELETE FROM members"))
    app = create_app(url, TestVerifier())
    with TestClient(app, headers={"Authorization": "Bearer valid"}) as client:
        yield client
    app.state.engine.dispose()


def test_anonymous_requests_fail_before_data_access(client):
    client.headers.pop("Authorization")
    assert client.get("/api/v1/members").status_code == 401
    assert (
        client.post("/api/v1/members", json={"name": "Alex", "color": "#abcdef"}).status_code == 401
    )


def test_member_filter_event_lifecycle_and_persistence(client):
    first = client.post("/api/v1/members", json={"name": " Alex ", "color": "#ABCDEF"})
    assert first.status_code == 201
    member_id = first.json()["id"]
    other = client.post("/api/v1/members", json={"name": "Sam", "color": "#4775be"}).json()["id"]
    event_data = {
        "member_id": member_id,
        "title": "Clase",
        "starts_at": "2026-10-07T09:00:00+02:00",
        "ends_at": "2026-10-07T10:00:00+02:00",
    }
    event = client.post("/api/v1/events", json=event_data)
    assert event.status_code == 201
    event_id = event.json()["id"]
    query = {"start": "2026-10-05T00:00:00Z", "end": "2026-10-12T00:00:00Z"}
    assert len(client.get("/api/v1/events", params=query).json()) == 1
    assert client.get("/api/v1/events", params=query | {"member_id": other}).json() == []
    changed = {
        "title": "Clase movida",
        "starts_at": "2026-10-08T09:00:00Z",
        "ends_at": "2026-10-08T11:00:00Z",
    }
    assert client.put(f"/api/v1/events/{event_id}", json=changed).status_code == 200
    stored = client.get("/api/v1/events", params=query).json()[0]
    assert stored["title"] == "Clase movida" and stored["member_id"] == member_id
    assert stored["starts_at"] == "2026-10-08T09:00:00Z"
    assert client.delete(f"/api/v1/events/{event_id}").status_code == 204
    assert client.get("/api/v1/events", params=query).json() == []
    assert client.delete(f"/api/v1/events/{event_id}").status_code == 404


def test_rejects_invalid_dates_unknown_member_and_assignee_change(client):
    member_id = client.post("/api/v1/members", json={"name": "Alex", "color": "#abcdef"}).json()[
        "id"
    ]
    data = {
        "member_id": member_id,
        "title": "Clase",
        "starts_at": "2026-10-07T09:00:00Z",
        "ends_at": "2026-10-07T10:00:00Z",
    }
    assert (
        client.post("/api/v1/events", json=data | {"ends_at": data["starts_at"]}).status_code == 422
    )
    assert (
        client.post("/api/v1/events", json=data | {"starts_at": "2026-10-07T09:00:00"}).status_code
        == 422
    )
    assert client.post("/api/v1/events", json=data | {"member_id": str(uuid4())}).status_code == 404
    event = client.post("/api/v1/events", json=data).json()
    assert client.put(f"/api/v1/events/{event['id']}", json=data).status_code == 422


def test_overlapping_events_and_database_constraints(client, database):
    member_id = client.post("/api/v1/members", json={"name": "Alex", "color": "#abcdef"}).json()[
        "id"
    ]
    data = {
        "member_id": member_id,
        "title": "Viaje",
        "starts_at": "2026-10-04T22:00:00Z",
        "ends_at": "2026-10-05T09:00:00Z",
    }
    client.post("/api/v1/events", json=data)
    assert (
        len(
            client.get(
                "/api/v1/events",
                params={"start": "2026-10-05T00:00:00Z", "end": "2026-10-06T00:00:00Z"},
            ).json()
        )
        == 1
    )
    _, engine = database
    with engine.connect() as connection:
        assert not compare_metadata(MigrationContext.configure(connection), Base.metadata)


def test_openapi_contract_has_not_drifted():
    app = create_app("postgresql+psycopg://unused:unused@localhost/unused", TestVerifier())
    root = Path(__file__).resolve().parents[2]
    path = Path(os.getenv("API_CONTRACT_PATH", str(root / "docs/openapi.json")))
    assert app.openapi() == json.loads(path.read_text())
    assert "OAuth2AuthorizationCodeBearer" in app.openapi()["components"]["securitySchemes"]
    app.state.engine.dispose()


def test_categories_are_validated_and_preserved_by_legacy_updates(client):
    member_id = client.post("/api/v1/members", json={"name": "Demo", "color": "#dcebe2"}).json()[
        "id"
    ]
    data = {
        "title": "Médico",
        "starts_at": "2026-10-07T09:00:00Z",
        "ends_at": "2026-10-07T10:00:00Z",
    }
    created = client.post(
        "/api/v1/events", json=data | {"member_id": member_id, "category": "medical"}
    )
    assert created.status_code == 201 and created.json()["category"] == "medical"
    event_id = created.json()["id"]
    assert client.put(f"/api/v1/events/{event_id}", json=data).json()["category"] == "medical"
    assert (
        client.put(f"/api/v1/events/{event_id}", json=data | {"category": "friends"}).json()[
            "category"
        ]
        == "friends"
    )
    assert (
        client.put(f"/api/v1/events/{event_id}", json=data | {"category": "invalid"}).status_code
        == 422
    )
    default = client.post("/api/v1/events", json=data | {"member_id": member_id})
    assert default.json()["category"] == "other"


def test_category_migration_preserves_existing_events(database):
    _, engine = database
    with engine.begin() as connection:
        for table in ("task_completions", "task_assignments", "all_day_notices", "tasks"):
            connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text("DELETE FROM events"))
        connection.execute(text("DELETE FROM members"))
    command.downgrade(Config("alembic.ini"), "001_calendar")
    member_id, event_id = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO members (id, name, color, created_at) "
                    "VALUES (:id, 'Legacy', '#abcdef', now())"
                ),
                {"id": member_id},
            )
            connection.execute(
                text(
                    "INSERT INTO events (id, member_id, title, starts_at, ends_at, "
                    "created_at, updated_at) VALUES (:id, :member, 'Existing', now(), "
                    "now() + interval '1 hour', now(), now())"
                ),
                {"id": event_id, "member": member_id},
            )
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT id, title, category FROM events WHERE id = :id"), {"id": event_id}
            ).one()
            assert row.id == event_id and row.title == "Existing" and row.category == "other"
    finally:
        command.upgrade(Config("alembic.ini"), "head")


def test_demo_has_four_profiles_and_does_not_overwrite_existing_data(client, database):
    from app.demo import DEMO_MEMBERS, seed_demo

    _, engine = database
    assert seed_demo(engine, "Europe/Madrid")
    members = client.get("/api/v1/members").json()
    assert [member["name"] for member in members] == [name for name, _ in DEMO_MEMBERS]
    ids = [member["id"] for member in members]
    assert len(client.get("/api/v1/tasks").json()) == 3
    for task in client.get("/api/v1/tasks").json():
        client.delete(f"/api/v1/tasks/{task['id']}")
    assert not seed_demo(engine, "Europe/Madrid")
    assert client.get("/api/v1/tasks").json() == []  # Archived demo routines stay archived.
    assert [member["id"] for member in client.get("/api/v1/members").json()] == ids
    client.post("/api/v1/members", json={"name": "Personal", "color": "#abcdef"})
    with pytest.raises(ValueError, match="ajenos a la demo"):
        seed_demo(engine, "Europe/Madrid", replace_test_fixtures=True)
    assert len(client.get("/api/v1/members").json()) == 5


def test_demo_can_replace_only_known_test_fixtures(client, database):
    from app.demo import seed_demo

    _, engine = database
    client.post("/api/v1/members", json={"name": "Alex 12345", "color": "#abcdef"})
    assert seed_demo(engine, "Europe/Madrid", replace_test_fixtures=True)
    assert len(client.get("/api/v1/members").json()) == 4


def test_profiles_photo_validation_and_name_only_update(client):
    from test_photos import synthetic_photo

    member = client.post("/api/v1/members", json={"name": "Alex", "color": "#abcdef"}).json()
    path = f"/api/v1/members/{member['id']}"
    changed = client.put(path, json={"name": " Alex nuevo ", "photo_data": synthetic_photo()})
    assert changed.status_code == 200
    photo = changed.json()["photo_data"]
    assert photo.startswith("data:image/jpeg;base64,")
    assert changed.json()["name"] == "Alex nuevo" and changed.json()["color"] == "#abcdef"
    assert client.put(path, json={"name": "Renamed"}).json()["photo_data"] == photo
    assert client.get("/api/v1/members").json()[0]["photo_data"] == photo
    assert client.put(path, json={"name": "Bad", "photo_data": "bad"}).status_code == 422
    assert client.get("/api/v1/members").json()[0]["name"] == "Renamed"
    assert (
        client.put(path, json={"name": "Renamed", "photo_data": None}).json()["photo_data"] is None
    )
    assert client.put(f"/api/v1/members/{uuid4()}", json={"name": "Unknown"}).status_code == 404


def test_all_day_notice_lifecycle_is_date_scoped(client):
    member_id = client.post("/api/v1/members", json={"name": "Alex", "color": "#abcdef"}).json()[
        "id"
    ]
    data = {"member_id": member_id, "title": "Uniforme", "day": "2026-10-07", "icon": "uniform"}
    created = client.post("/api/v1/notices", json=data)
    assert created.status_code == 201
    notice_id = created.json()["id"]
    assert client.get("/api/v1/notices", params={"day": "2026-10-07"}).json() == [created.json()]
    assert client.get("/api/v1/notices", params={"day": "2026-10-08"}).json() == []
    assert (
        client.post("/api/v1/notices", json=data | {"member_id": str(uuid4())}).status_code == 404
    )
    assert client.post("/api/v1/notices", json=data | {"icon": "invalid"}).status_code == 422
    update = {"title": "Excursión", "day": "2026-10-08", "icon": "trip"}
    assert client.put(f"/api/v1/notices/{notice_id}", json=update).json()["icon"] == "trip"
    assert client.get("/api/v1/notices", params={"day": "2026-10-07"}).json() == []
    assert client.delete(f"/api/v1/notices/{notice_id}").status_code == 204
    assert client.delete(f"/api/v1/notices/{notice_id}").status_code == 404


def test_daily_tasks_completion_and_archive_keep_history(client, database):
    ids = [
        client.post("/api/v1/members", json={"name": name, "color": "#abcdef"}).json()["id"]
        for name in ("Alex", "Sam")
    ]
    data = {
        "title": "Dientes",
        "icon": "tooth",
        "frequency": "daily",
        "starts_on": "2026-10-07",
        "member_ids": ids,
    }
    created = client.post("/api/v1/tasks", json=data)
    assert created.status_code == 201
    task_id = created.json()["id"]
    complete_path = f"/api/v1/tasks/{task_id}/completion"
    mark = {"member_id": ids[0], "day": "2026-10-07", "completed": True}
    assert client.put(complete_path, json=mark).status_code == 200
    assert client.put(complete_path, json=mark).status_code == 200
    states = client.get("/api/v1/task-occurrences", params={"day": "2026-10-07"}).json()
    assert {item["member_id"]: item["completed"] for item in states} == {
        ids[0]: True,
        ids[1]: False,
    }
    assert not any(
        item["completed"]
        for item in client.get("/api/v1/task-occurrences", params={"day": "2026-10-08"}).json()
    )
    assert client.get("/api/v1/task-occurrences", params={"day": "2026-10-06"}).json() == []
    assert client.put(complete_path, json=mark | {"member_id": str(uuid4())}).status_code == 422
    assert client.post("/api/v1/tasks", json=data | {"member_ids": ids[:1] * 2}).status_code == 422
    assert (
        client.post("/api/v1/tasks", json=data | {"member_ids": [str(uuid4())]}).status_code == 404
    )
    # Removing an assignee keeps their mark; reassigning them restores it.
    assert (
        client.put(f"/api/v1/tasks/{task_id}", json=data | {"member_ids": ids[1:]}).status_code
        == 200
    )
    assert client.put(f"/api/v1/tasks/{task_id}", json=data).status_code == 200
    assert any(
        item["completed"]
        for item in client.get("/api/v1/task-occurrences", params={"day": "2026-10-07"}).json()
    )
    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 204
    assert client.get("/api/v1/tasks").json() == []
    assert client.get("/api/v1/task-occurrences", params={"day": "2026-10-07"}).json() == []
    assert client.put(complete_path, json=mark).status_code == 422
    assert client.put(f"/api/v1/tasks/{task_id}", json=data).status_code == 404
    _, engine = database
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM task_completions WHERE completed")
            ).scalar()
            == 1
        )


def test_once_task_and_new_routes_require_auth(client):
    member_id = client.post("/api/v1/members", json={"name": "Alex", "color": "#abcdef"}).json()[
        "id"
    ]
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "Mochila",
            "icon": "backpack",
            "frequency": "once",
            "starts_on": "2026-10-07",
            "member_ids": [member_id],
        },
    ).json()
    assert len(client.get("/api/v1/task-occurrences", params={"day": "2026-10-07"}).json()) == 1
    assert client.get("/api/v1/task-occurrences", params={"day": "2026-10-08"}).json() == []
    path = f"/api/v1/tasks/{created['id']}/completion"
    assert (
        client.put(
            path, json={"member_id": member_id, "day": "2026-10-08", "completed": True}
        ).status_code
        == 422
    )
    client.headers.pop("Authorization")
    for url in (
        "/api/v1/notices?day=2026-10-07",
        "/api/v1/tasks",
        "/api/v1/task-occurrences?day=2026-10-07",
    ):
        assert client.get(url).status_code == 401
    assert client.put(f"/api/v1/members/{member_id}", json={"name": "No"}).status_code == 401
    assert (
        client.put(
            path, json={"member_id": member_id, "day": "2026-10-07", "completed": True}
        ).status_code
        == 401
    )


def test_new_migration_preserves_members_and_categorized_events(database):
    _, engine = database
    with engine.begin() as connection:
        for table in (
            "task_completions",
            "task_assignments",
            "all_day_notices",
            "tasks",
            "events",
            "members",
        ):
            connection.execute(text(f"DELETE FROM {table}"))
    command.downgrade(Config("alembic.ini"), "002_event_category")
    member_id, event_id = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO members (id, name, color, created_at) "
                    "VALUES (:id, 'Legacy', '#abcdef', now())"
                ),
                {"id": member_id},
            )
            connection.execute(
                text(
                    "INSERT INTO events (id, member_id, title, starts_at, ends_at, "
                    "category, created_at, updated_at) VALUES (:id, :member, 'Existing', "
                    "now(), now() + interval '1 hour', 'school', now(), now())"
                ),
                {"id": event_id, "member": member_id},
            )
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT photo_data FROM members WHERE id=:id"), {"id": member_id}
                ).scalar()
                is None
            )
            assert (
                connection.execute(
                    text("SELECT category FROM events WHERE id=:id"), {"id": event_id}
                ).scalar()
                == "school"
            )
            assert not compare_metadata(MigrationContext.configure(connection), Base.metadata)
    finally:
        command.upgrade(Config("alembic.ini"), "head")
