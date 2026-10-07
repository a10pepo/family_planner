"""Explicit, idempotent demo seed. Ordinary family installations are never seeded."""

import argparse
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.adapters.daily import (
    NoticeRow,
    SqlDailyRepository,
    TaskAssignmentRow,
    TaskCompletionRow,
    TaskRow,
)
from app.adapters.database import EventRow, MemberRow, SqlCalendarRepository, make_engine
from app.domain.calendar import Calendar, Category
from app.domain.daily import DailyPlanner

DEMO_MEMBERS = (
    ("Laura (Mamá)", "#dcebe2"),
    ("Pedro (Papá)", "#dce6f3"),
    ("Jaime (Tete)", "#f4e7cf"),
    ("Lucía (Teta)", "#eadff0"),
)
DEMO_EVENTS = (
    (0, "Revisión médica", 10, 1, Category.MEDICAL),
    (0, "Café con amigas", 17.5, 1, Category.FRIENDS),
    (1, "Desayuno tranquilo", 8, 1, Category.OTHER),
    (1, "Recoger a los peques", 14, 1, Category.SCHOOL),
    (2, "Colegio", 9, 5, Category.SCHOOL),
    (2, "Fútbol", 16, 1, Category.ACTIVITIES),
    (3, "Colegio", 9, 5, Category.SCHOOL),
    (3, "Cumpleaños de una amiga", 17, 1.5, Category.FRIENDS),
)


def seed_demo(engine, zone: str, replace_test_fixtures: bool = False) -> bool:
    with Session(engine) as session, session.begin():
        # Serialize concurrent bootstrap attempts so the demo cannot be duplicated.
        session.execute(text("LOCK TABLE members IN EXCLUSIVE MODE"))
        names = list(session.scalars(select(MemberRow.name)))
        if names and not replace_test_fixtures:
            # Upgrade only a recognized synthetic demo, once; archived tasks also count.
            if (
                len(names) == 4
                and set(names) == {name for name, _ in DEMO_MEMBERS}
                and not session.scalar(select(TaskRow.id).limit(1))
            ):
                people = {
                    person.name: person for person in SqlCalendarRepository(session).members()
                }
                seed_daily(session, zone, [people[name] for name, _ in DEMO_MEMBERS])
            return False
        if replace_test_fixtures:
            demo_names = {name for name, _ in DEMO_MEMBERS}
            if any(
                name not in demo_names and not re.fullmatch(r"(?:Alex|Sam) \d+", name)
                for name in names
            ):
                raise ValueError(
                    "La base contiene perfiles ajenos a la demo; no se cambia ningún dato."
                )
            for model in (TaskCompletionRow, TaskAssignmentRow, NoticeRow, TaskRow):
                session.execute(delete(model))
            session.execute(delete(EventRow))
            session.execute(delete(MemberRow))
        calendar = Calendar(SqlCalendarRepository(session))
        people = [calendar.add_member(name, color) for name, color in DEMO_MEMBERS]
        today = datetime.now(ZoneInfo(zone)).replace(hour=0, minute=0, second=0, microsecond=0)
        for index, title, hour, duration, category in DEMO_EVENTS:
            start = today + timedelta(hours=hour)
            calendar.create_event(
                people[index].id, title, start, start + timedelta(hours=duration), category
            )
        seed_daily(session, zone, people)
    return True


def seed_daily(session, zone, people):
    service = DailyPlanner(SqlDailyRepository(session))
    today = datetime.now(ZoneInfo(zone)).date()
    children = [people[2].id, people[3].id]
    for title, icon in (
        ("Lavarse los dientes", "tooth"),
        ("Hacer la cama", "bed"),
        ("Hacer la mochila", "backpack"),
    ):
        service.save_task(title, icon, "daily", today, children)
    service.create_notice(children[0], today, "Día de uniforme", "uniform")
    service.create_notice(children[1], today, "Día de chándal", "tracksuit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace-test-fixtures", action="store_true")
    args = parser.parse_args()
    if os.getenv("DEMO_MODE") != "1":
        if args.replace_test_fixtures:
            raise SystemExit("La sustitución solo está disponible con DEMO_MODE=1.")
        return
    engine = make_engine(os.environ["DATABASE_URL"])
    try:
        added = seed_demo(
            engine, os.getenv("FAMILY_TIMEZONE", "Europe/Madrid"), args.replace_test_fixtures
        )
        print("Demo de cuatro integrantes preparada." if added else "Demo existente conservada.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
