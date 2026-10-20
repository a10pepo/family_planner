import logging
from contextlib import contextmanager
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from app.domain.calendar import Category, Event, Member
from app.domain.family import FamilyEvent, FamilyIcon
from app.mcp_server import create_mcp_app
from fastapi import HTTPException
from fastapi.testclient import TestClient

READ_SCOPE = "https://family-planner-preview.example/mcp/calendar.read"
WRITE_SCOPE = "https://family-planner-preview.example/mcp/calendar.write"
RESOURCE = "https://family-planner-preview.example/mcp"


class TokenVerifier:
    def __init__(self, claims=None):
        self.claims = claims or {
            "sub": "family-user-123",
            "aud": RESOURCE,
            "scope": f"{READ_SCOPE} {WRITE_SCOPE}",
        }

    def verify(self, token):
        if token != "valid":
            raise HTTPException(401, "Invalid token")
        return self.claims


class CalendarRepository:
    def __init__(self):
        self.member_id = uuid4()
        self.member_data = Member(self.member_id, "Sample Parent", "#abcdef", "synthetic-photo")
        self.other_member = Member(uuid4(), "Sample Child", "#fedcba")
        self.archived_member = Member(uuid4(), "Archived Sample", "#123456", active=False)
        self.events_by_id = {}

    def members(self, include_archived=False):
        members = [self.member_data, self.other_member, self.archived_member]
        return members if include_archived else [member for member in members if member.active]

    def member(self, member_id, include_archived=False):
        return next(
            (member for member in self.members(include_archived) if member.id == member_id),
            None,
        )

    def icon(self, icon_id):
        return object() if str(icon_id) == "11111111-1111-4111-8111-111111111111" else None

    def events(self, start, end, member_id):
        return [
            event
            for event in self.events_by_id.values()
            if event.starts_at < end
            and event.ends_at > start
            and (member_id is None or event.member_id == member_id)
        ]

    def event(self, event_id):
        return self.events_by_id.get(event_id)

    def save_event(self, event):
        self.events_by_id[event.id] = event
        return event

    def remove_event(self, event_id):
        self.events_by_id.pop(event_id, None)


class RecurrenceRepository:
    def __init__(self):
        self.series_by_id = {}
        self.exceptions_by_key = {}

    def series(self, member_id=None):
        return [
            item
            for item in self.series_by_id.values()
            if member_id is None or item.member_id == member_id
        ]

    def get_series(self, series_id):
        return self.series_by_id.get(series_id)

    def save_series(self, series):
        self.series_by_id[series.id] = series
        return series

    def delete_series(self, series_id):
        self.series_by_id.pop(series_id, None)
        for key in [key for key in self.exceptions_by_key if key[0] == series_id]:
            self.exceptions_by_key.pop(key)

    def exceptions(self, series_id):
        return [item for item in self.exceptions_by_key.values() if item.series_id == series_id]

    def save_exception(self, exception):
        key = (exception.series_id, exception.occurrence_date, exception.occurrence_time)
        self.exceptions_by_key[key] = exception
        return exception

    def delete_exception(self, series_id, occurrence_date, occurrence_time):
        self.exceptions_by_key.pop((series_id, occurrence_date, occurrence_time), None)


class FamilyRepository:
    def __init__(self, calendar):
        self.calendar = calendar
        self.events_by_id = {}

    def icon(self, icon_id):
        return self.calendar.icon(icon_id)

    def events(self, start, end):
        return sorted(
            (event for event in self.events_by_id.values() if start <= event.day < end),
            key=lambda event: (event.day, event.title, event.id),
        )

    def event(self, event_id):
        return self.events_by_id.get(event_id)

    def save(self, event):
        self.events_by_id[event.id] = event
        return event

    def remove(self, event_id):
        self.events_by_id.pop(event_id, None)


class Storage:
    def __init__(self):
        self.calendar = CalendarRepository()
        self.family = FamilyRepository(self.calendar)
        self.recurrence = RecurrenceRepository()
        self.family_ids = []

    @contextmanager
    def repositories(self, family_id):
        self.family_ids.append(family_id)
        yield type(
            "Repositories",
            (),
            {
                "calendar": self.calendar,
                "family": self.family,
                "recurrence": self.recurrence,
            },
        )()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OAUTH_ISSUER", "https://cognito.example/user-pool")
    monkeypatch.setenv("MCP_OAUTH_CLIENT_ID", "mcp-client")
    monkeypatch.setenv("MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("MCP_SCOPE_READ", READ_SCOPE)
    monkeypatch.setenv("MCP_SCOPE_WRITE", WRITE_SCOPE)
    monkeypatch.setenv("MCP_AUTHORIZATION_ENDPOINT", "https://cognito.example/oauth2/authorize")
    monkeypatch.setenv("MCP_TOKEN_ENDPOINT", "https://cognito.example/oauth2/token")
    storage = Storage()
    app = create_mcp_app(storage=storage, verifier=TokenVerifier())
    with TestClient(app) as test_client:
        test_client.storage = storage
        yield test_client


def rpc(method, request_id=1, params=None):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def test_resource_metadata_describes_resource_and_scopes(client):
    response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    assert response.json() == {
        "resource": RESOURCE,
        "authorization_servers": ["https://family-planner-preview.example"],
        "scopes_supported": [READ_SCOPE, WRITE_SCOPE],
        "bearer_methods_supported": ["header"],
    }


def test_authorization_server_metadata_adapts_cognito_for_codex_pkce(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    assert response.json() == {
        "issuer": "https://family-planner-preview.example",
        "authorization_endpoint": "https://cognito.example/oauth2/authorize",
        "token_endpoint": "https://cognito.example/oauth2/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["openid", READ_SCOPE, WRITE_SCOPE],
        "authorization_response_iss_parameter_supported": False,
    }


def test_missing_token_returns_metadata_challenge(client):
    response = client.post("/mcp", json=rpc("initialize"))
    assert response.status_code == 401
    assert (
        'resource_metadata="https://family-planner-preview.example/.well-known/oauth-protected-resource/mcp"'
        in response.headers["www-authenticate"]
    )


def test_preview_diagnostics_log_argument_types_without_values(client, monkeypatch, caplog):
    monkeypatch.setenv("APP_ENVIRONMENT", "preview")
    monkeypatch.setenv("MCP_DIAGNOSTIC_LOGS", "true")
    app = create_mcp_app(storage=client.storage, verifier=TokenVerifier())
    start = "2026-10-20T10:00:00+02:00"
    end = "2026-10-20T11:00:00+02:00"
    member_id = str(uuid4())

    with caplog.at_level(logging.INFO, logger="family_planner.mcp.diagnostics"):
        response = TestClient(app).post(
            "/mcp",
            headers={"Authorization": "Bearer valid"},
            json=rpc(
                "tools/call",
                params={
                    "name": "list_events",
                    "arguments": {"start": start, "end": end, "member_id": member_id},
                },
            ),
        )

    assert response.status_code == 200
    assert '"event":"mcp_http_received"' in caplog.text
    assert '"event":"mcp_tool_completed"' in caplog.text
    assert '"start":"string"' in caplog.text
    assert '"end":"string"' in caplog.text
    assert '"member_id":"string"' in caplog.text
    assert start not in caplog.text
    assert end not in caplog.text
    assert member_id not in caplog.text


def test_preview_diagnostics_are_disabled_outside_preview(client, monkeypatch, caplog):
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("MCP_DIAGNOSTIC_LOGS", "true")
    app = create_mcp_app(storage=client.storage, verifier=TokenVerifier())

    with caplog.at_level(logging.INFO, logger="family_planner.mcp.diagnostics"):
        response = TestClient(app).post(
            "/mcp", headers={"Authorization": "Bearer valid"}, json=rpc("ping")
        )

    assert response.status_code == 200
    assert "mcp_http_received" not in caplog.text


def test_initialize_and_tools_are_scoped(client):
    headers = {"Authorization": "Bearer valid"}
    initialized = client.post("/mcp", headers=headers, json=rpc("initialize"))
    assert initialized.status_code == 200
    assert initialized.json()["result"]["protocolVersion"] == "2025-11-25"
    tools = client.post("/mcp", headers=headers, json=rpc("tools/list")).json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "list_members",
        "list_events",
        "list_event_series",
        "list_family_events",
        "save_event",
        "save_event_series",
        "save_occurrence_exception",
        "delete_event_series",
        "delete_occurrence_exception",
        "save_family_event",
        "delete_family_event",
    }


def test_list_members_uses_read_scope_and_returns_only_active_identity_fields(client):
    read_only = create_mcp_app(
        storage=client.storage,
        verifier=TokenVerifier({"sub": "family-user-123", "aud": RESOURCE, "scope": READ_SCOPE}),
    )
    read_client = TestClient(read_only)
    headers = {"Authorization": "Bearer valid"}
    tools = read_client.post("/mcp", headers=headers, json=rpc("tools/list")).json()["result"][
        "tools"
    ]
    assert {tool["name"] for tool in tools} == {
        "list_members",
        "list_events",
        "list_event_series",
        "list_family_events",
    }

    response = read_client.post(
        "/mcp",
        headers=headers,
        json=rpc("tools/call", params={"name": "list_members", "arguments": {}}),
    )

    assert response.status_code == 200
    members = response.json()["result"]["structuredContent"]
    assert members == [
        {
            "id": str(client.storage.calendar.member_id),
            "name": "Sample Parent",
            "active": True,
        },
        {
            "id": str(client.storage.calendar.other_member.id),
            "name": "Sample Child",
            "active": True,
        },
    ]
    assert "synthetic-photo" not in response.text
    assert "color" not in response.text
    assert client.storage.family_ids == ["family-user-123"]


def test_list_members_rejects_arguments(client):
    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer valid"},
        json=rpc(
            "tools/call",
            params={"name": "list_members", "arguments": {"include_archived": True}},
        ),
    )

    assert response.json()["result"]["isError"] is True
    error_text = response.json()["result"]["content"][0]["text"].lower()
    assert "extra inputs are not permitted" in error_text


def test_invalid_params_return_json_rpc_error_instead_of_server_error(client):
    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer valid"},
        json={"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": "invalid"},
    )
    assert response.status_code == 200
    assert response.json()["error"]["code"] == -32602


def test_wrong_resource_audience_is_rejected(client):
    app = create_mcp_app(
        storage=client.storage,
        verifier=TokenVerifier(
            {"sub": "family-user-123", "aud": "https://other.example/mcp", "scope": READ_SCOPE}
        ),
    )
    response = TestClient(app).post(
        "/mcp", headers={"Authorization": "Bearer valid"}, json=rpc("tools/list")
    )
    assert response.status_code == 401


def test_audience_rejection_logs_only_safe_claim_metadata(client, monkeypatch, caplog):
    monkeypatch.setenv("APP_ENVIRONMENT", "preview")
    monkeypatch.setenv("MCP_DIAGNOSTIC_LOGS", "true")
    wrong_audience = "https://old.example/mcp"
    app = create_mcp_app(
        storage=client.storage,
        verifier=TokenVerifier(
            {"sub": "family-user-123", "aud": wrong_audience, "scope": READ_SCOPE}
        ),
    )

    with caplog.at_level(logging.INFO, logger="family_planner.mcp.diagnostics"):
        response = TestClient(app).post(
            "/mcp", headers={"Authorization": "Bearer valid"}, json=rpc("initialize")
        )

    assert response.status_code == 401
    assert '"audience_claim_present":true' in caplog.text
    assert '"audience_claim_type":"string"' in caplog.text
    assert '"audience_element_types":[]' in caplog.text
    assert '"audience_matches_resource":false' in caplog.text
    assert '"audience_host_matches_resource":false' in caplog.text
    assert '"audience_path_matches_resource":true' in caplog.text
    assert wrong_audience not in caplog.text


def test_read_and_save_events_use_authenticated_family_and_domain(client):
    headers = {"Authorization": "Bearer valid"}
    start = datetime(2026, 10, 15, 10, tzinfo=UTC)
    end = datetime(2026, 10, 15, 11, tzinfo=UTC)
    saved = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "member_id": str(client.storage.calendar.member_id),
                    "title": "Médico",
                    "starts_at": start.isoformat(),
                    "ends_at": end.isoformat(),
                    "category": "medical",
                },
            },
        ),
    )
    event_data = saved.json()["result"]["structuredContent"]
    assert saved.status_code == 200
    assert event_data["title"] == "Médico"
    assert event_data["category"] == Category.MEDICAL.value

    listed = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "list_events",
                "arguments": {"start": start.isoformat(), "end": end.isoformat()},
            },
        ),
    )
    assert listed.json()["result"]["structuredContent"][0]["id"] == event_data["id"]
    assert client.storage.family_ids == ["family-user-123", "family-user-123"]

    updated = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "event_id": event_data["id"],
                    "title": "Médico movido",
                    "starts_at": start.isoformat(),
                    "ends_at": end.isoformat(),
                },
            },
        ),
    )
    assert updated.json()["result"]["structuredContent"]["title"] == "Médico movido"
    assert updated.json()["result"]["structuredContent"]["category"] == Category.MEDICAL.value


def test_list_events_filters_title_case_insensitively_and_category(client):
    headers = {"Authorization": "Bearer valid"}
    start = "2026-10-15T10:00:00Z"
    end = "2026-10-15T11:00:00Z"
    member_id = str(client.storage.calendar.member_id)
    other_member_id = str(client.storage.calendar.other_member.id)

    def create_event(member, title, category):
        return client.post(
            "/mcp",
            headers=headers,
            json=rpc(
                "tools/call",
                params={
                    "name": "save_event",
                    "arguments": {
                        "member_id": member,
                        "title": title,
                        "starts_at": start,
                        "ends_at": end,
                        "category": category,
                    },
                },
            ),
        )

    first = create_event(member_id, "EDEM Sesión 1", "activities")
    create_event(member_id, "Reunión EDEM", "friends")
    create_event(other_member_id, "EDEM Sesión 2", "activities")

    response = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "list_events",
                "arguments": {
                    "start": "2026-10-15T09:00:00Z",
                    "end": "2026-10-15T12:00:00Z",
                    "member_id": member_id,
                    "title": "  edem sesión ",
                    "category": "activities",
                },
            },
        ),
    )

    assert first.status_code == 200
    assert response.status_code == 200
    events = response.json()["result"]["structuredContent"]
    assert len(events) == 1
    assert events[0]["title"] == "EDEM Sesión 1"
    assert events[0]["member_id"] == member_id
    assert events[0]["category"] == "activities"


@pytest.mark.parametrize(
    ("filters", "error_fragment"),
    [
        ({"title": "   "}, "filtro de título"),
        ({"category": "unknown"}, "input should be"),
    ],
)
def test_list_events_rejects_invalid_title_or_category_filters(client, filters, error_fragment):
    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer valid"},
        json=rpc(
            "tools/call",
            params={
                "name": "list_events",
                "arguments": {
                    "start": "2026-10-15T09:00:00Z",
                    "end": "2026-10-15T12:00:00Z",
                    **filters,
                },
            },
        ),
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is True
    assert error_fragment in result["content"][0]["text"].lower()


def test_write_scope_is_required_for_save(client):
    read_only = create_mcp_app(
        storage=client.storage,
        verifier=TokenVerifier({"sub": "family-user-123", "aud": RESOURCE, "scope": READ_SCOPE}),
    )
    response = TestClient(read_only).post(
        "/mcp",
        headers={"Authorization": "Bearer valid"},
        json=rpc("tools/call", params={"name": "save_event", "arguments": {}}),
    )
    assert response.status_code == 403
    assert "insufficient_scope" in response.headers["www-authenticate"]


def test_save_event_can_reassign_member_and_rejects_invalid_interval(client):
    headers = {"Authorization": "Bearer valid"}
    bad = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "member_id": str(client.storage.calendar.member_id),
                    "title": "Evento",
                    "starts_at": "2026-10-15T10:00:00Z",
                    "ends_at": "2026-10-15T09:00:00Z",
                },
            },
        ),
    )
    assert bad.json()["result"]["isError"] is True
    assert "posterior" in bad.json()["result"]["content"][0]["text"]

    created = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "member_id": str(client.storage.calendar.member_id),
                    "title": "Evento",
                    "starts_at": "2026-10-15T10:00:00Z",
                    "ends_at": "2026-10-15T11:00:00Z",
                },
            },
        ),
    )
    event_id = created.json()["result"]["structuredContent"]["id"]

    moved = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "event_id": event_id,
                    "member_id": str(client.storage.calendar.other_member.id),
                    "title": "Evento",
                    "starts_at": "2026-10-15T10:00:00Z",
                    "ends_at": "2026-10-15T11:00:00Z",
                },
            },
        ),
    )
    assert moved.json()["result"]["structuredContent"]["member_id"] == str(
        client.storage.calendar.other_member.id
    )

    invalid_member = str(uuid4())
    rejected = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "event_id": event_id,
                    "member_id": invalid_member,
                    "title": "Evento editado",
                    "starts_at": "2026-10-15T10:00:00Z",
                    "ends_at": "2026-10-15T11:00:00Z",
                },
            },
        ),
    )
    assert rejected.json()["result"]["isError"] is True
    assert (
        client.storage.calendar.event(UUID(event_id)).member_id
        == client.storage.calendar.other_member.id
    )


def test_family_event_tools_list_create_update_and_delete(client):
    headers = {"Authorization": "Bearer valid"}
    custom_icon_id = UUID("11111111-1111-4111-8111-111111111111")
    before_range = FamilyEvent(uuid4(), date(2026, 10, 7), "Before", FamilyIcon.OTHER)
    inside_range = FamilyEvent(
        uuid4(), date(2026, 10, 8), "Birthday", FamilyIcon.BIRTHDAY, custom_icon_id
    )
    client.storage.family.save(before_range)
    client.storage.family.save(inside_range)

    listed = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "list_family_events",
                "arguments": {"start": "2026-10-08", "end": "2026-10-09"},
            },
        ),
    ).json()["result"]["structuredContent"]
    assert listed == [
        {
            "id": str(inside_range.id),
            "day": "2026-10-08",
            "title": "Birthday",
            "icon": "birthday",
            "custom_icon_id": str(custom_icon_id),
        }
    ]

    created = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_family_event",
                "arguments": {
                    "day": "2026-10-10",
                    "title": "Celebration",
                    "icon": "celebration",
                },
            },
        ),
    ).json()["result"]["structuredContent"]
    created_id = UUID(created["id"])
    assert created["day"] == "2026-10-10"
    assert created["icon"] == "celebration"
    assert created["custom_icon_id"] is None

    updated = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_family_event",
                "arguments": {
                    "event_id": str(inside_range.id),
                    "day": "2026-10-11",
                    "title": "Updated birthday",
                    "icon": "other",
                },
            },
        ),
    ).json()["result"]["structuredContent"]
    assert updated["id"] == str(inside_range.id)
    assert updated["day"] == "2026-10-11"
    assert updated["custom_icon_id"] == str(custom_icon_id)

    deleted = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={"name": "delete_family_event", "arguments": {"event_id": str(created_id)}},
        ),
    ).json()["result"]["structuredContent"]
    assert deleted == {"id": str(created_id), "deleted": True}
    assert client.storage.family.event(created_id) is None
    assert client.storage.calendar.event(created_id) is None

    punctual_id = uuid4()
    client.storage.calendar.save_event(
        Event(
            punctual_id,
            client.storage.calendar.member_id,
            "Timed event",
            datetime(2026, 10, 12, 10, tzinfo=UTC),
            datetime(2026, 10, 12, 11, tzinfo=UTC),
        )
    )
    wrong_kind_delete = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={"name": "delete_family_event", "arguments": {"event_id": str(punctual_id)}},
        ),
    ).json()["result"]
    assert wrong_kind_delete["isError"] is True
    assert client.storage.calendar.event(punctual_id) is not None


def test_family_event_tools_enforce_scopes_and_strict_arguments(client):
    read_only = TestClient(
        create_mcp_app(
            storage=client.storage,
            verifier=TokenVerifier(
                {"sub": "family-user-123", "aud": RESOURCE, "scope": READ_SCOPE}
            ),
        )
    )
    headers = {"Authorization": "Bearer valid"}
    listed_tools = read_only.post("/mcp", headers=headers, json=rpc("tools/list")).json()["result"][
        "tools"
    ]
    assert "list_family_events" in {tool["name"] for tool in listed_tools}
    assert "save_family_event" not in {tool["name"] for tool in listed_tools}
    assert "delete_family_event" not in {tool["name"] for tool in listed_tools}

    denied = read_only.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={"name": "delete_family_event", "arguments": {"event_id": str(uuid4())}},
        ),
    )
    assert denied.status_code == 403
    assert "insufficient_scope" in denied.headers["www-authenticate"]

    invalid = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_family_event",
                "arguments": {
                    "day": "2026-10-08T00:00:00",
                    "title": "Invalid date",
                    "icon": "birthday",
                    "unexpected": True,
                },
            },
        ),
    ).json()["result"]
    assert invalid["isError"] is True
    assert client.storage.family.events_by_id == {}


def test_mcp_manages_recurring_series_and_occurrence_exceptions_without_touching_punctual_events(
    client,
):
    headers = {"Authorization": "Bearer valid"}
    member_id = str(client.storage.calendar.member_id)
    occurrence_date = "2026-10-20"
    occurrence_time = "09:00:00"
    punctual_event = client.storage.calendar.save_event(
        Event(
            uuid4(),
            client.storage.calendar.member_id,
            "Puntual",
            datetime(2026, 10, 20, 7, tzinfo=UTC),
            datetime(2026, 10, 20, 8, tzinfo=UTC),
        )
    )

    def call(name, arguments):
        return client.post(
            "/mcp",
            headers=headers,
            json=rpc("tools/call", params={"name": name, "arguments": arguments}),
        ).json()["result"]

    created = call(
        "save_event_series",
        {
            "member_id": member_id,
            "title": "Natación",
            "start_date": occurrence_date,
            "start_time": occurrence_time,
            "duration_minutes": 45,
            "timezone": "Europe/Madrid",
            "frequency": "weekly",
            "interval": 1,
            "weekdays": [1],
            "category": "activities",
        },
    )
    assert created["structuredContent"]["title"] == "Natación"
    series_id = created["structuredContent"]["id"]

    listed = call("list_event_series", {})
    assert [item["id"] for item in listed["structuredContent"]] == [series_id]

    updated = call(
        "save_event_series",
        {
            "series_id": series_id,
            "member_id": member_id,
            "title": "Natación cambiada",
            "start_date": occurrence_date,
            "start_time": occurrence_time,
            "duration_minutes": 50,
            "timezone": "Europe/Madrid",
            "frequency": "weekly",
            "interval": 1,
            "weekdays": [1],
            "end_mode": "never",
            "category": "activities",
        },
    )
    assert updated["structuredContent"]["title"] == "Natación cambiada"

    cancelled = call(
        "save_occurrence_exception",
        {
            "series_id": series_id,
            "occurrence_date": occurrence_date,
            "occurrence_time": occurrence_time,
            "cancelled": True,
        },
    )
    assert cancelled["structuredContent"]["cancelled"] is True

    invalid_occurrence = call(
        "save_occurrence_exception",
        {
            "series_id": series_id,
            "occurrence_date": "2026-10-21",
            "occurrence_time": occurrence_time,
            "cancelled": True,
        },
    )
    assert invalid_occurrence["isError"] is True

    restored = call(
        "delete_occurrence_exception",
        {
            "series_id": series_id,
            "occurrence_date": occurrence_date,
            "occurrence_time": occurrence_time,
        },
    )
    assert restored["structuredContent"]["restored"] is True
    assert not client.storage.recurrence.exceptions(UUID(series_id))

    deleted = call("delete_event_series", {"series_id": series_id})
    assert deleted["structuredContent"]["deleted"] is True
    assert client.storage.recurrence.get_series(UUID(series_id)) is None
    assert client.storage.calendar.event(punctual_event.id) == punctual_event


def test_mcp_recurring_mutations_require_write_scope(client):
    read_only = create_mcp_app(
        storage=client.storage,
        verifier=TokenVerifier({"sub": "family-user-123", "aud": RESOURCE, "scope": READ_SCOPE}),
    )
    response = TestClient(read_only).post(
        "/mcp",
        headers={"Authorization": "Bearer valid"},
        json=rpc("tools/call", params={"name": "delete_event_series", "arguments": {}}),
    )
    assert response.status_code == 403
