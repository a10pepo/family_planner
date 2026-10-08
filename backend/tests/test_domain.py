from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.domain.calendar import Calendar, InvalidInput, MissingEntity, validate_interval


class MemoryRepository:
    def __init__(self):
        self.people = {}
        self.appointments = {}

    def add_member(self, member):
        self.people[member.id] = member
        return member

    def save_member(self, member):
        self.people[member.id] = member
        return member

    def member(self, member_id, include_archived=False):
        person = self.people.get(member_id)
        return person if person and (person.active or include_archived) else None

    def event(self, event_id):
        return self.appointments.get(event_id)

    def save_event(self, event):
        self.appointments[event.id] = event
        return event

    def remove_event(self, event_id):
        del self.appointments[event_id]


def test_event_lifecycle_preserves_assignee_and_normalizes_time():
    calendar = Calendar(MemoryRepository())
    member = calendar.add_member("  Alex  ", "#ABCDEF")
    start = datetime.fromisoformat("2026-10-25T02:30:00+02:00")
    end = datetime.fromisoformat("2026-10-25T02:15:00+01:00")
    event = calendar.create_event(member.id, "  Colegio  ", start, end)
    assert member.name == "Alex" and member.color == "#abcdef"
    assert event.title == "Colegio" and event.starts_at.tzinfo == UTC
    assert (event.ends_at - event.starts_at).total_seconds() == 2700
    changed = calendar.update_event(event.id, "Clase", event.starts_at, event.ends_at)
    assert changed.id == event.id and changed.member_id == member.id
    calendar.delete_event(event.id)
    with pytest.raises(MissingEntity):
        calendar.delete_event(event.id)


@pytest.mark.parametrize("name,color", [(" ", "#abcdef"), ("A" * 81, "#abcdef"), ("Alex", "red")])
def test_invalid_member_is_not_persisted(name, color):
    repository = MemoryRepository()
    with pytest.raises(InvalidInput):
        Calendar(repository).add_member(name, color)
    assert not repository.people


def test_invalid_interval_and_missing_member():
    now = datetime.now(UTC)
    with pytest.raises(InvalidInput):
        validate_interval(now, now)
    with pytest.raises(InvalidInput):
        validate_interval(datetime(2026, 1, 1), now)
    with pytest.raises(MissingEntity):
        Calendar(MemoryRepository()).create_event(uuid4(), "Evento", now, now)


def test_category_survives_movement_and_can_be_changed():
    calendar = Calendar(MemoryRepository())
    member = calendar.add_member("Demo", "#dcebe2")
    start = datetime.fromisoformat("2026-10-07T09:00:00Z")
    end = datetime.fromisoformat("2026-10-07T10:00:00Z")
    event = calendar.create_event(member.id, "Actividad", start, end, "school")
    assert event.category == "school"
    moved = calendar.update_event(event.id, "Actividad movida", start, end)
    assert moved.category == "school"
    changed = calendar.update_event(event.id, "Actividad", start, end, "friends")
    assert changed.category == "friends"
    with pytest.raises(InvalidInput):
        calendar.update_event(event.id, "Actividad", start, end, "unknown")
    assert calendar.repository.event(event.id).category == "friends"
    with pytest.raises(InvalidInput):
        calendar.create_event(member.id, "Actividad", start, end, "unknown")


def test_member_edit_preserves_id_color_and_optional_photo():
    calendar = Calendar(MemoryRepository())
    member = calendar.add_member("Alex", "#abcdef")
    edited = calendar.update_member(member.id, " New ", "normalized-photo", True)
    assert edited.id == member.id and edited.color == member.color
    assert edited.name == "New" and edited.photo_data == "normalized-photo"
    assert calendar.update_member(member.id, "Name only").photo_data == "normalized-photo"
    assert calendar.update_member(member.id, "New", None, True).photo_data is None
    with pytest.raises(InvalidInput):
        calendar.update_member(member.id, " ")
    with pytest.raises(MissingEntity):
        calendar.update_member(uuid4(), "New")


def test_archiving_member_preserves_identity_and_events_and_restore_is_idempotent():
    calendar = Calendar(MemoryRepository())
    member = calendar.add_member("Alex", "#abcdef")
    start = datetime.fromisoformat("2026-10-08T09:00:00Z")
    end = datetime.fromisoformat("2026-10-08T10:00:00Z")
    event = calendar.create_event(member.id, "Clase", start, end)
    archived = calendar.set_member_active(member.id, False)
    assert archived.id == member.id and not archived.active
    assert calendar.repository.event(event.id) == event
    with pytest.raises(MissingEntity):
        calendar.create_event(member.id, "Nuevo", start, end)
    with pytest.raises(MissingEntity):
        calendar.update_event(event.id, "Nuevo", start, end)
    with pytest.raises(MissingEntity):
        calendar.delete_event(event.id)
    assert calendar.set_member_active(member.id, True) == member
    assert calendar.set_member_active(member.id, True) == member
    with pytest.raises(MissingEntity):
        calendar.set_member_active(uuid4(), False)
