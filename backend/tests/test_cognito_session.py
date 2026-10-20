import app.api as api
from fastapi.testclient import TestClient


def _client(monkeypatch, cognito_request):
    monkeypatch.setenv("APP_ORIGIN", "https://calendar.example")
    monkeypatch.setenv("OAUTH_PROVIDER", "cognito")
    monkeypatch.setenv("OAUTH_ISSUER", "https://cognito.example")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "web-client")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setattr(api, "_cognito_auth_request", cognito_request)
    app = api.create_app(storage=object())
    return TestClient(app, base_url="https://calendar.example")


def _tokens():
    return {"AuthenticationResult": {"AccessToken": "short-lived-access", "ExpiresIn": 900}}


def test_session_endpoint_sets_http_only_cookie_and_returns_only_access_token(monkeypatch):
    calls = []

    def cognito_request(region, target, body):
        calls.append((region, target, body))
        return _tokens()

    client = _client(monkeypatch, cognito_request)
    response = client.post(
        "/api/v1/auth/session",
        headers={"Origin": "https://calendar.example"},
        json={"refresh_token": "refresh-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "short-lived-access", "expires_in": 900}
    cookie = response.headers["set-cookie"]
    assert "family_planner_refresh=refresh-secret" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie and "Max-Age=86400" in cookie
    assert calls == [
        (
            "eu-west-1",
            "InitiateAuth",
            {
                "AuthFlow": "REFRESH_TOKEN_AUTH",
                "ClientId": "web-client",
                "AuthParameters": {"REFRESH_TOKEN": "refresh-secret"},
            },
        )
    ]


def test_refresh_uses_cookie_and_clears_it_when_cognito_rejects_token(monkeypatch):
    client = _client(monkeypatch, lambda *_: _tokens())
    success = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://calendar.example"},
        cookies={"family_planner_refresh": "refresh-secret"},
    )
    assert success.status_code == 200
    assert success.json() == {"access_token": "short-lived-access", "expires_in": 900}

    def expired(*_):
        raise api.CognitoAuthError

    client = _client(monkeypatch, expired)
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://calendar.example"},
        cookies={"family_planner_refresh": "expired-token"},
    )
    assert response.status_code == 401
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_logout_revokes_refresh_token_and_clears_cookie(monkeypatch):
    calls = []
    client = _client(monkeypatch, lambda *args: calls.append(args) or {})
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://calendar.example"},
        cookies={"family_planner_refresh": "refresh-secret"},
    )
    assert response.status_code == 204
    assert calls == [
        (
            "eu-west-1",
            "RevokeToken",
            {"ClientId": "web-client", "Token": "refresh-secret"},
        )
    ]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_session_endpoints_reject_cross_origin_requests(monkeypatch):
    client = _client(monkeypatch, lambda *_: _tokens())
    response = client.post("/api/v1/auth/refresh", headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403
