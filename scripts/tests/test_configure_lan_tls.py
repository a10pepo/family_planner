import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location(
    "configure_lan_tls", SCRIPT_DIR / "configure_lan_tls.py"
)
configure_lan_tls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure_lan_tls)


def test_write_env_updates_origins_and_removes_http_only_binding(tmp_path):
    path = tmp_path / ".env"
    path.write_text("APP_ORIGIN=http://localhost:8080\nAPP_BIND_ADDRESS=0.0.0.0\nSECRET=value\n")

    configure_lan_tls.write_env(
        path,
        path.read_text().splitlines(),
        {"APP_ORIGIN": "https://192.168.1.25:8443", "LAN_BIND_ADDRESS": "192.168.1.25"},
    )

    contents = path.read_text()
    assert "APP_ORIGIN=https://192.168.1.25:8443" in contents
    assert "LAN_BIND_ADDRESS=192.168.1.25" in contents
    assert "APP_BIND_ADDRESS" not in contents
    assert "SECRET=value" in contents
    assert path.stat().st_mode & 0o777 == 0o600


def test_realm_import_uses_exact_https_origin_and_removes_lan_http(tmp_path):
    path = tmp_path / "family-realm.json"
    path.write_text(
        json.dumps(
            {
                "clients": [
                    {
                        "clientId": "family-planner",
                        "redirectUris": [
                            "http://localhost:8080/",
                            "http://192.168.1.25:8080/",
                        ],
                        "webOrigins": ["http://localhost:8080", "http://192.168.1.25:8080"],
                        "attributes": {"post.logout.redirect.uris": "http://localhost:8080/"},
                    }
                ]
            }
        )
    )

    configure_lan_tls.update_realm_import(path, "192.168.1.25", "https://192.168.1.25:8443")

    client = json.loads(path.read_text())["clients"][0]
    assert client["redirectUris"] == [
        "http://localhost:8080/",
        "https://192.168.1.25:8443/",
        "https://192.168.1.25:8443/api/docs/oauth2-redirect",
    ]
    assert client["webOrigins"] == ["http://localhost:8080", "https://192.168.1.25:8443"]
    assert "http://192.168.1.25:8080/" not in client["attributes"]["post.logout.redirect.uris"]


def test_keycloak_client_update_is_exact_and_removes_http_lan_redirect(monkeypatch):
    updated = {}
    original = {
        "id": "client-id",
        "redirectUris": [
            "http://localhost:8080/",
            "http://192.168.1.25:8080/",
        ],
        "webOrigins": ["http://localhost:8080", "http://192.168.1.25:8080"],
        "attributes": {"post.logout.redirect.uris": "http://localhost:8080/"},
    }

    def request(url, *, method="GET", data=None, headers=None):
        if url.endswith("/protocol/openid-connect/token"):
            return b'{"access_token":"synthetic-token"}'
        if "/clients?clientId=" in url:
            return json.dumps([original]).encode()
        if method == "PUT":
            updated.update(json.loads(data))
            return b""
        raise AssertionError(f"Unexpected Keycloak request: {method} {url}")

    monkeypatch.setattr(configure_lan_tls, "keycloak_request", request)
    configure_lan_tls.update_keycloak_client(
        {"KC_ADMIN_USERNAME": "synthetic", "KC_ADMIN_PASSWORD": "synthetic"},
        "192.168.1.25",
        "https://192.168.1.25:8443",
    )

    assert "http://192.168.1.25:8080/" not in updated["redirectUris"]
    assert "https://192.168.1.25:8443/" in updated["redirectUris"]
    assert updated["webOrigins"] == ["http://localhost:8080", "https://192.168.1.25:8443"]
    assert updated["attributes"]["post.logout.redirect.uris"] == (
        "http://localhost:8080/##https://192.168.1.25:8443/"
    )


@pytest.mark.parametrize("host", ["8.8.8.8", "::1", "127.0.0.1", "169.254.1.2"])
def test_configure_rejects_non_lan_addresses(host):
    with pytest.raises(SystemExit, match="IPv4 privada"):
        configure_lan_tls.configure(host)
