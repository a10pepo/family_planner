"""Create the synthetic preview account and populate an empty fixture family."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import date, datetime
from datetime import time as wall_time
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

TEST_USERNAME = "test"
TEST_EMAIL = "test@family-planner.invalid"
MEMBERS = (
    ("Laura (Mamá)", "#dcebe2"),
    ("Pedro (Papá)", "#dce6f3"),
    ("Jaime (Tete)", "#f4e7cf"),
    ("Lucía (Teta)", "#eadff0"),
)
SUBJECTS = (
    ("Lengua", "Matemáticas", "Ciencias"),
    ("Inglés", "Lectura", "Plástica"),
    ("Matemáticas", "Música", "Educación física"),
    ("Ciencias", "Lengua", "Inglés"),
    ("Lectura", "Matemáticas", "Conocimiento del medio"),
)


def aws(region: str, *args: str, payload: dict | None = None, allow_failure: bool = False):
    command = ["aws", *args, "--region", region, "--output", "json"]
    if payload is not None:
        with NamedTemporaryFile(mode="w", encoding="utf-8", prefix="family-planner-secret-") as f:
            os.chmod(f.name, 0o600)
            json.dump(payload, f)
            f.flush()
            command.extend(["--cli-input-json", f"file://{f.name}"])
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
    else:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode and not allow_failure:
        raise RuntimeError(f"AWS CLI operation failed: {' '.join(args[:2])}")
    if completed.returncode:
        return None
    return json.loads(completed.stdout) if completed.stdout.strip() else {}


def strong_password() -> str:
    groups = (
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.digits,
        "!@#$%*-_+",
    )
    chars = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    chars.extend(secrets.choice(alphabet) for _ in range(28))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def put_secret(region: str, secret_arn: str, credentials: dict) -> None:
    aws(
        region,
        "secretsmanager",
        "put-secret-value",
        "--secret-id",
        secret_arn,
        payload={"SecretId": secret_arn, "SecretString": json.dumps(credentials)},
    )


def ensure_credentials(region: str, pool_id: str, secret_arn: str) -> dict:
    secret = aws(
        region,
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_arn,
        allow_failure=True,
    )
    if secret:
        credentials = json.loads(secret["SecretString"])
        password = credentials["password"]
    else:
        password = strong_password()
        credentials = {
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "password": password,
        }
        put_secret(region, secret_arn, credentials)

    current = aws(
        region,
        "cognito-idp",
        "admin-get-user",
        "--user-pool-id",
        pool_id,
        "--username",
        TEST_USERNAME,
        allow_failure=True,
    )
    if current is None:
        aws(
            region,
            "cognito-idp",
            "admin-create-user",
            payload={
                "UserPoolId": pool_id,
                "Username": TEST_USERNAME,
                "UserAttributes": [
                    {"Name": "email", "Value": TEST_EMAIL},
                    {"Name": "email_verified", "Value": "true"},
                ],
                "MessageAction": "SUPPRESS",
            },
        )
    else:
        attributes = {item["Name"]: item["Value"] for item in current.get("UserAttributes", [])}
        if attributes.get("email") != TEST_EMAIL:
            raise RuntimeError(
                "El usuario de preview 'test' ya existe con otros datos; no se modificó."
            )

    if current is None or not secret:
        aws(
            region,
            "cognito-idp",
            "admin-set-user-password",
            payload={
                "UserPoolId": pool_id,
                "Username": TEST_USERNAME,
                "Password": password,
                "Permanent": True,
            },
        )
    return credentials


class PreviewApi:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.token = token

    def request(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(8):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return json.loads(response.read()) if response.status != 204 else None
            except urllib.error.HTTPError as exc:
                raise RuntimeError(
                    f"Preview API respondió HTTP {exc.code} para {method} {path}."
                ) from exc
            except (urllib.error.URLError, TimeoutError):
                if attempt == 7:
                    raise
                time.sleep(min(attempt + 1, 5))


def local_iso(day: date, hour: int, minute: int, zone: ZoneInfo) -> str:
    return datetime.combine(day, wall_time(hour, minute), zone).isoformat()


def month_weekdays(year: int, month: int):
    for number in range(1, monthrange(year, month)[1] + 1):
        day = date(year, month, number)
        if day.weekday() < 5:
            yield day


def seed_calendar(api: PreviewApi, timezone: str) -> None:
    zone = ZoneInfo(timezone)
    today = datetime.now(zone).date()
    start = today.replace(day=1)
    next_month = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    existing = api.request("GET", "/members")
    expected_names = {name for name, _ in MEMBERS}
    existing_names = {member["name"] for member in existing}
    unexpected = existing_names - expected_names
    if unexpected:
        raise RuntimeError(
            "Preview contiene integrantes ajenos a la familia de prueba; no se cambió ningún dato."
        )
    by_name = {member["name"]: member for member in existing}
    for name, color in MEMBERS:
        if name not in by_name:
            member = api.request("POST", "/members", {"name": name, "color": color})
            by_name[name] = member

    events_query = urlencode(
        {
            "start": local_iso(start, 0, 0, zone),
            "end": local_iso(next_month, 0, 0, zone),
        }
    )
    events = api.request("GET", f"/events?{events_query}")
    if events:
        if len(existing_names) == len(expected_names):
            return
        raise RuntimeError(
            "La familia de prueba tiene eventos parciales; no se duplicaron ni sobrescribieron."
        )

    for day in month_weekdays(today.year, today.month):
        subjects = SUBJECTS[day.weekday()]
        for index, child in enumerate(("Jaime (Tete)", "Lucía (Teta)")):
            start_hour = 9
            end_hour = 13 if index else 14
            title = f"Colegio · {', '.join(subjects)}"
            api.request(
                "POST",
                "/events",
                {
                    "member_id": by_name[child]["id"],
                    "title": title,
                    "starts_at": local_iso(day, start_hour, 0, zone),
                    "ends_at": local_iso(day, end_hour, 0, zone),
                    "category": "school",
                },
            )
        if day.weekday() in (1, 3):
            child = "Jaime (Tete)" if day.weekday() == 1 else "Lucía (Teta)"
            title = "Fútbol" if child.startswith("Jaime") else "Música"
            api.request(
                "POST",
                "/events",
                {
                    "member_id": by_name[child]["id"],
                    "title": title,
                    "starts_at": local_iso(day, 17, 0, zone),
                    "ends_at": local_iso(day, 18, 0, zone),
                    "category": "activities",
                },
            )
        if day.weekday() == 2:
            api.request(
                "POST",
                "/events",
                {
                    "member_id": by_name["Laura (Mamá)"]["id"],
                    "title": "Recoger a Jaime y Lucía",
                    "starts_at": local_iso(day, 14, 0, zone),
                    "ends_at": local_iso(day, 14, 30, zone),
                    "category": "other",
                },
            )

    for title, icon in (
        ("Preparar la mochila", "backpack"),
        ("Hacer la cama", "bed"),
        ("Lavarse los dientes", "tooth"),
    ):
        api.request(
            "POST",
            "/tasks",
            {
                "title": title,
                "icon": icon,
                "frequency": "daily",
                "starts_on": start.isoformat(),
                "member_ids": [
                    by_name["Jaime (Tete)"]["id"],
                    by_name["Lucía (Teta)"]["id"],
                ],
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--secret-arn", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--timezone", default="Europe/Madrid")
    args = parser.parse_args()
    credentials = ensure_credentials(args.region, args.user_pool_id, args.secret_arn)
    if credentials.get("fixture_seeded"):
        print("La cuenta y el calendario sintéticos ya estaban preparados.")
        return
    auth = aws(
        args.region,
        "cognito-idp",
        "initiate-auth",
        payload={
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": args.client_id,
            "AuthParameters": {
                "USERNAME": credentials["username"],
                "PASSWORD": credentials["password"],
            },
        },
    )
    token = auth.get("AuthenticationResult", {}).get("AccessToken")
    if not token:
        raise RuntimeError("Cognito no devolvió un token de acceso para preparar preview.")
    seed_calendar(PreviewApi(args.api_url, token), args.timezone)
    credentials["fixture_seeded"] = True
    credentials["fixture_month"] = datetime.now(ZoneInfo(args.timezone)).strftime("%Y-%m")
    put_secret(args.region, args.secret_arn, credentials)
    print("La familia ficticia y el calendario de preview están preparados.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error al preparar la familia ficticia de preview: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
