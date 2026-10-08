from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

import pytest
from app.domain.calendar import InvalidInput, Member, MissingEntity
from app.domain.daily import DailyPlanner

TODAY = date(2026, 10, 7)


class MemoryDaily:
    def __init__(self):
        self.people = [Member(uuid4(), name, "#abcdef") for name in ("Alex", "Sam")]
        self.routines = {}
        self.alerts = {}
        self.states = {}

    def member(self, member_id):
        return next(
            (person for person in self.people if person.id == member_id and person.active), None
        )

    def task(self, task_id):
        return self.routines.get(task_id)

    def tasks(self):
        return list(self.routines.values())

    def save_task(self, task):
        self.routines[task.id] = task
        return task

    def notice(self, notice_id):
        return self.alerts.get(notice_id)

    def save_notice(self, notice):
        self.alerts[notice.id] = notice
        return notice

    def remove_notice(self, notice_id):
        del self.alerts[notice_id]

    def completions(self, day):
        return {
            (task, person): value
            for (task, person, when), value in self.states.items()
            if when == day
        }

    def set_completion(self, task_id, member_id, day, completed):
        self.states[task_id, member_id, day] = completed


def test_daily_completion_is_independent_per_child_and_day_and_archive_preserves_states():
    repo = MemoryDaily()
    service = DailyPlanner(repo)
    ids = [person.id for person in repo.people]
    task = service.save_task(" Dientes ", "tooth", "daily", TODAY, ids)
    assert service.occurrences(TODAY - timedelta(days=1)) == []
    service.complete(task.id, ids[0], TODAY, True)
    service.complete(task.id, ids[0], TODAY, True)  # Retrying a requested state is idempotent.
    assert [item.completed for item in service.occurrences(TODAY)] == [True, False]
    assert [item.completed for item in service.occurrences(TODAY + timedelta(days=1))] == [
        False,
        False,
    ]
    service.complete(task.id, ids[0], TODAY, False)
    assert not service.occurrences(TODAY)[0].completed
    service.archive_task(task.id)
    assert service.occurrences(TODAY) == [] and repo.states
    with pytest.raises(InvalidInput):
        service.complete(task.id, ids[0], TODAY, True)


def test_once_occurs_only_on_selected_date_and_assignment_edit_preserves_existing_mark():
    repo = MemoryDaily()
    service = DailyPlanner(repo)
    ids = [person.id for person in repo.people]
    task = service.save_task("Mochila", "backpack", "once", TODAY, ids[:1])
    service.complete(task.id, ids[0], TODAY, True)
    service.save_task("Preparar mochila", "backpack", "once", TODAY, ids, task.id)
    assert [item.completed for item in service.occurrences(TODAY)] == [True, False]
    assert service.occurrences(TODAY + timedelta(days=1)) == []
    with pytest.raises(InvalidInput):
        service.complete(task.id, ids[1], TODAY + timedelta(days=1), True)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"icon": "bad"},
        {"frequency": "weekly"},
        {"member_ids": []},
        {"member_ids": [uuid4()]},
    ],
)
def test_invalid_routine_is_not_stored(changes):
    repo = MemoryDaily()
    data = dict(
        title="Cama", icon="bed", frequency="daily", starts_on=TODAY, member_ids=[repo.people[0].id]
    )
    with pytest.raises((InvalidInput, MissingEntity)):
        DailyPlanner(repo).save_task(**(data | changes))
    assert not repo.routines


def test_notices_lifecycle_and_invalid_references():
    repo = MemoryDaily()
    service = DailyPlanner(repo)
    notice = service.create_notice(repo.people[0].id, TODAY, " Uniforme ", "uniform")
    changed = service.update_notice(notice.id, TODAY + timedelta(days=1), "Excursión", "trip")
    assert changed.member_id == notice.member_id and changed.icon == "trip"
    service.delete_notice(notice.id)
    with pytest.raises(MissingEntity):
        service.delete_notice(notice.id)
    with pytest.raises(MissingEntity):
        service.create_notice(uuid4(), TODAY, "Excursión", "trip")
    with pytest.raises(InvalidInput):
        service.create_notice(repo.people[0].id, TODAY, "Excursión", "bad")


def test_archived_member_keeps_assignments_and_marks_without_visible_occurrences():
    repo = MemoryDaily()
    service = DailyPlanner(repo)
    first, other = [person.id for person in repo.people]
    task = service.save_task("Cama", "bed", "daily", TODAY, [first, other])
    service.complete(task.id, first, TODAY, True)
    repo.people[0] = replace(repo.people[0], active=False)
    assert [item.member_id for item in service.occurrences(TODAY)] == [other]
    with pytest.raises(MissingEntity):
        service.complete(task.id, first, TODAY, False)
    service.save_task("Cama editada", "bed", "daily", TODAY, [first, other], task.id)
    with pytest.raises(MissingEntity):
        service.save_task("Nueva", "bed", "daily", TODAY, [first])
    repo.people[0] = replace(repo.people[0], active=True)
    assert service.occurrences(TODAY)[0].completed
