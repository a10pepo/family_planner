"""Configure trusted HTTPS for the local Family Planner network address."""

import argparse
import ipaddress
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN_LOCAL = "http://localhost:8080"
LOCAL_ADMIN = "http://localhost:8080/auth"


def read_env(path: Path) -> tuple[dict[str, str], list[str]]:
    lines = path.read_text().splitlines()
    values = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values, lines


def write_env(path: Path, lines: list[str], updates: dict[str, str]) -> None:
    remaining = updates.copy()
    output = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0]
            if key == "APP_BIND_ADDRESS":
                continue
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text("\n".join(output) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def run_openssl(*arguments: str) -> None:
    try:
        subprocess.run(
            ["openssl", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "No se encontró openssl. Instálalo en este ordenador y vuelve a intentarlo."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip().splitlines()
        message = detail[-1] if detail else "error"
        raise SystemExit(f"OpenSSL no pudo generar el certificado: {message}") from exc


def create_certificates(directory: Path, host: str) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    ca_key = directory / "lan-ca.key"
    ca_cert = directory / "lan-ca.crt"
    server_key = directory / "lan-server.key"
    server_cert = directory / "lan-server.crt"
    ca_config = directory / ".lan-ca.cnf"
    server_config = directory / ".lan-server.cnf"
    csr = directory / ".lan-server.csr"

    if ca_key.exists() != ca_cert.exists():
        raise SystemExit(
            "El certificado y la clave de la CA local no coinciden; no se sobrescriben."
        )
    if not ca_key.exists():
        ca_config.write_text(
            "[req]\nprompt = no\ndistinguished_name = dn\nx509_extensions = ca_ext\n"
            "[dn]\nCN = Family Planner Local CA\n"
            "[ca_ext]\nbasicConstraints = critical,CA:TRUE\n"
            "keyUsage = critical,keyCertSign,cRLSign\nsubjectKeyIdentifier = hash\n"
        )
        run_openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-sha256",
            "-days",
            "3650",
            "-keyout",
            str(ca_key),
            "-out",
            str(ca_cert),
            "-config",
            str(ca_config),
        )

    server_config.write_text(
        "[req]\nprompt = no\ndistinguished_name = dn\n"
        f"[dn]\nCN = {host}\n"
        "[server_ext]\nbasicConstraints = critical,CA:FALSE\n"
        "keyUsage = critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage = serverAuth\n"
        f"subjectAltName = IP:{host}\nsubjectKeyIdentifier = hash\n"
        "authorityKeyIdentifier = keyid,issuer\n"
    )
    run_openssl(
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-keyout",
        str(server_key),
        "-out",
        str(csr),
        "-config",
        str(server_config),
    )
    run_openssl(
        "x509",
        "-req",
        "-in",
        str(csr),
        "-CA",
        str(ca_cert),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-out",
        str(server_cert),
        "-days",
        "397",
        "-sha256",
        "-extfile",
        str(server_config),
        "-extensions",
        "server_ext",
    )
    os.chmod(ca_key, 0o600)
    os.chmod(ca_cert, 0o644)
    # The unprivileged nginx container reads this file through a read-only bind mount.
    os.chmod(server_key, 0o644)
    os.chmod(server_cert, 0o644)
    ca_config.unlink(missing_ok=True)
    server_config.unlink(missing_ok=True)
    csr.unlink(missing_ok=True)


def keycloak_request(url: str, *, method: str = "GET", data=None, headers=None):
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(
            "No se pudo actualizar Keycloak. Comprueba que Docker Compose está activo y que "
            "la consola local responde en http://localhost:8080."
        ) from exc
    return body


def update_keycloak_client(values: dict[str, str], host: str, origin: str) -> None:
    try:
        form = urllib.parse.urlencode(
            {
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": values["KC_ADMIN_USERNAME"],
                "password": values["KC_ADMIN_PASSWORD"],
            }
        ).encode()
    except KeyError as exc:
        raise SystemExit(
            "Faltan credenciales de administrador en .env; no se cambia OAuth."
        ) from exc
    token = json.loads(
        keycloak_request(
            f"{LOCAL_ADMIN}/realms/master/protocol/openid-connect/token",
            method="POST",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    )["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}
    client_url = f"{LOCAL_ADMIN}/admin/realms/family/clients?clientId=family-planner"
    clients = json.loads(keycloak_request(client_url, headers=auth_header))
    if len(clients) != 1:
        raise SystemExit(
            "No se encontró un único cliente OAuth familiar; no se cambia la configuración."
        )
    client = clients[0]
    lan_http_origin = f"http://{host}:8080"
    stale_uris = {f"{lan_http_origin}/", f"{lan_http_origin}/api/docs/oauth2-redirect"}
    redirects = [uri for uri in client.get("redirectUris", []) if uri not in stale_uris]
    client["redirectUris"] = list(
        dict.fromkeys([*redirects, f"{origin}/", f"{origin}/api/docs/oauth2-redirect"])
    )
    origins = [uri for uri in client.get("webOrigins", []) if uri != lan_http_origin]
    client["webOrigins"] = list(dict.fromkeys([*origins, origin]))
    attributes = client.setdefault("attributes", {})
    logout = [
        uri
        for uri in attributes.get("post.logout.redirect.uris", "").split("##")
        if uri and uri != f"{lan_http_origin}/"
    ]
    if f"{origin}/" not in logout:
        logout.append(f"{origin}/")
    attributes["post.logout.redirect.uris"] = "##".join(logout)
    headers = {**auth_header, "Content-Type": "application/json"}
    keycloak_request(
        f"{LOCAL_ADMIN}/admin/realms/family/clients/{client['id']}",
        method="PUT",
        data=json.dumps(client).encode(),
        headers=headers,
    )


def update_realm_import(path: Path, host: str, origin: str) -> None:
    if not path.exists():
        return
    realm = json.loads(path.read_text())
    client = next(
        (item for item in realm.get("clients", []) if item.get("clientId") == "family-planner"),
        None,
    )
    if client is None:
        raise SystemExit("No se encontró family-planner en el archivo local de Keycloak.")
    lan_http_origin = f"http://{host}:8080"
    stale_uris = {f"{lan_http_origin}/", f"{lan_http_origin}/api/docs/oauth2-redirect"}
    redirects = [uri for uri in client.get("redirectUris", []) if uri not in stale_uris]
    client["redirectUris"] = list(
        dict.fromkeys([*redirects, f"{origin}/", f"{origin}/api/docs/oauth2-redirect"])
    )
    client["webOrigins"] = list(
        dict.fromkeys(
            [uri for uri in client.get("webOrigins", []) if uri != lan_http_origin] + [origin]
        )
    )
    attributes = client.setdefault("attributes", {})
    logout = [
        uri
        for uri in attributes.get("post.logout.redirect.uris", "").split("##")
        if uri and uri != f"{lan_http_origin}/"
    ]
    if f"{origin}/" not in logout:
        logout.append(f"{origin}/")
    attributes["post.logout.redirect.uris"] = "##".join(logout)
    path.write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n")
    os.chmod(path, 0o644)


def configure(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise SystemExit("Indica la IPv4 privada del ordenador.") from exc
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or not address.is_private
        or address.is_loopback
        or address.is_link_local
    ):
        raise SystemExit(
            "Indica la IPv4 privada del ordenador, no localhost ni una dirección pública."
        )
    host = str(address)
    env_path = ROOT / ".env"
    realm_path = ROOT / ".local" / "family-realm.json"
    if not env_path.exists():
        raise SystemExit(
            "Primero prepara la instalación con scripts/setup.py y arranca Docker Compose."
        )
    values, lines = read_env(env_path)
    origin = f"https://{host}:8443"

    create_certificates(ROOT / ".local", host)
    update_keycloak_client(values, host, origin)
    update_realm_import(realm_path, host, origin)
    write_env(
        env_path,
        lines,
        {
            "APP_ORIGIN": origin,
            "LAN_BIND_ADDRESS": host,
            "LAN_TLS_PORT": "8443",
        },
    )
    print(f"Origen OAuth actualizado: {origin}")
    print("CA pública para confiar en la tablet: .local/lan-ca.crt")
    print("Ahora ejecuta: docker compose -f compose.yaml -f compose.lan-tls.yaml up -d")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="IPv4 privada del ordenador en la LAN.")
    configure(parser.parse_args().host)
