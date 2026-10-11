import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from seed_preview import MEMBERS, seed_calendar, strong_password


class FakeApi:
    def __init__(self):
        self.members = []
        self.events = []
        self.created = []

    def request(self, method, path, body=None):
        if method == "GET" and path == "/members":
            return self.members
        if method == "GET" and path.startswith("/events?"):
            return self.events
        if method == "POST" and path == "/members":
            member = {"id": f"member-{len(self.members)}", **body}
            self.members.append(member)
            return member
        if method == "POST" and path == "/events":
            event = {"id": f"event-{len(self.events)}", **body}
            self.events.append(event)
            self.created.append(event)
            return event
        if method == "POST" and path == "/tasks":
            self.created.append({"path": path, **body})
            return body
        raise AssertionError(f"Unexpected request: {method} {path}")


def test_preview_password_has_required_complexity():
    password = strong_password()
    assert len(password) >= 32
    assert any(character.islower() for character in password)
    assert any(character.isupper() for character in password)
    assert any(character.isdigit() for character in password)
    assert any(not character.isalnum() for character in password)


def test_preview_seed_is_for_current_month_and_idempotent():
    api = FakeApi()

    seed_calendar(api, "Europe/Madrid")

    assert {member["name"] for member in api.members} == {name for name, _ in MEMBERS}
    assert all(
        date.fromisoformat(event["starts_at"][:10]).month
        == datetime.now(ZoneInfo("Europe/Madrid")).date().month
        for event in api.events
    )
    seeded_count = len(api.created)
    assert seeded_count > 40

    seed_calendar(api, "Europe/Madrid")

    assert len(api.created) == seeded_count
