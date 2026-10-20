import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.domain.calendar import Category, Member
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
        self.member_data = Member(self.member_id, "Demo", "#abcdef")
        self.events_by_id = {}

    def members(self, include_archived=False):
        return [self.member_data]

    def member(self, member_id, include_archived=False):
        return self.member_data if member_id == self.member_id else None

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
    def series(self, member_id=None):
        return []

    def exceptions(self, series_id):
        return []


class Storage:
    def __init__(self):
        self.calendar = CalendarRepository()
        self.family_ids = []

    @contextmanager
    def repositories(self, family_id):
        self.family_ids.append(family_id)
        yield type(
            "Repositories", (), {"calendar": self.calendar, "recurrence": RecurrenceRepository()}
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
    assert {tool["name"] for tool in tools} == {"list_events", "save_event"}


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


def test_save_event_rejects_member_change_and_invalid_interval(client):
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

    event_id = uuid4()
    moved = client.post(
        "/mcp",
        headers=headers,
        json=rpc(
            "tools/call",
            params={
                "name": "save_event",
                "arguments": {
                    "event_id": str(event_id),
                    "member_id": str(client.storage.calendar.member_id),
                    "title": "Evento",
                    "starts_at": "2026-10-15T10:00:00Z",
                    "ends_at": "2026-10-15T11:00:00Z",
                },
            },
        ),
    )
    assert moved.json()["result"]["isError"] is True
    assert "no se puede cambiar" in moved.json()["result"]["content"][0]["text"]
