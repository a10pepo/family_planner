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
