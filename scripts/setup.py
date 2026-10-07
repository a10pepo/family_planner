"""Create local-only OAuth configuration; never overwrite existing credentials."""

import argparse
import getpass
import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(test: bool = False) -> None:
    env_path = ROOT / ".env"
    realm_path = ROOT / ".local" / "family-realm.json"
    if env_path.exists() or realm_path.exists():
        raise SystemExit("Ya existe configuración local. No se sobrescriben credenciales.")
    if test:
        username, password = "test-family", "Fictional-test-password-42"
    else:
        username = input("Usuario de la cuenta familiar: ").strip()
        password = getpass.getpass("Contraseña familiar (mínimo 12 caracteres): ")
        if password != getpass.getpass("Repite la contraseña: "):
            raise SystemExit("Las contraseñas no coinciden.")
    if not username or len(username) > 80 or len(password) < 12:
        raise SystemExit("Indica un usuario (1–80 caracteres) y una contraseña de al menos 12.")
    origin = "http://localhost:8080"
    realm = {
        "realm": "family",
        "enabled": True,
        "displayName": "Nuestra familia",
        "sslRequired": "none",
        "registrationAllowed": False,
        "resetPasswordAllowed": False,
        "loginWithEmailAllowed": False,
        "internationalizationEnabled": True,
        "supportedLocales": ["es"],
        "defaultLocale": "es",
        "bruteForceProtected": True,
        "failureFactor": 5,
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 2592000,
        "ssoSessionMaxLifespan": 2592000,
        "roles": {"realm": [{"name": "family-app"}]},
        "clients": [
            {
                "clientId": "family-planner",
                "name": "Family Planner",
                "enabled": True,
                "publicClient": True,
                "standardFlowEnabled": True,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": [f"{origin}/", f"{origin}/api/docs/oauth2-redirect"],
                "webOrigins": [origin],
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "post.logout.redirect.uris": f"{origin}/",
                },
                "protocolMappers": [
                    {
                        "name": "family-api-audience",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-audience-mapper",
                        "config": {
                            "included.custom.audience": "family-api",
                            "access.token.claim": "true",
                            "id.token.claim": "false",
                        },
                    }
                ],
            }
        ],
        "users": [
            {
                "username": username,
                "firstName": "Cuenta",
                "lastName": "familiar",
                "email": "family@example.invalid",
                "emailVerified": False,
                "requiredActions": [],
                "enabled": True,
                "realmRoles": ["family-app"],
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            }
        ],
    }
    realm_path.parent.mkdir(mode=0o700, exist_ok=True)
    realm_path.write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n")
    # The private parent directory protects this file on the host; Keycloak's
    # unprivileged container user must be able to read the bind-mounted import.
    os.chmod(realm_path, 0o644)
    values = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "KC_ADMIN_USERNAME": "local-admin",
        "KC_ADMIN_PASSWORD": secrets.token_urlsafe(32),
        "APP_ORIGIN": origin,
        "FAMILY_TIMEZONE": "Europe/Madrid",
        "DEMO_MODE": "1" if test else "0",
    }
    env_path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    os.chmod(env_path, 0o600)
    print("Configuración creada. Ejecuta: docker compose up --build -d")
    print("Accede a http://localhost:8080 con la cuenta familiar que has configurado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test", action="store_true", help="Crear una cuenta ficticia para pruebas."
    )
    parser.add_argument(
        "--demo", action="store_true", help="Crear la demo local con cuatro perfiles ilustrados."
    )
    args = parser.parse_args()
    prepare(args.test or args.demo)
