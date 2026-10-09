"""Pure recurrence rules for family calendar event series."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.calendar import Category, Event, InvalidInput


class Frequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EndMode(StrEnum):
    NEVER = "never"
    DATE = "date"
    COUNT = "count"


@dataclass(frozen=True)
class EventSeries:
    id: UUID
    member_id: UUID
    title: str
    start_date: date
    start_time: time
    duration_minutes: int
    timezone: str
    frequency: Frequency
    interval: int
    weekdays: tuple[int, ...]
    end_mode: EndMode
    end_date: date | None
    occurrence_count: int | None
    category: Category
    custom_icon_id: UUID | None = None


@dataclass(frozen=True)
class EventException:
    series_id: UUID
    occurrence_date: date
    occurrence_time: time
    cancelled: bool = False
    override_start_time: time | None = None
    override_duration_minutes: int | None = None
    override_title: str | None = None
    override_category: Category | None = None
    has_icon_override: bool = False
    override_custom_icon_id: UUID | None = None


def validate_series(series: EventSeries) -> EventSeries:
    if not series.title.strip() or len(series.title.strip()) > 200:
        raise InvalidInput("El título debe tener entre 1 y 200 caracteres.")
    if not 1 <= series.interval <= 365:
        raise InvalidInput("El intervalo debe estar entre 1 y 365.")
    if not 1 <= series.duration_minutes <= 10080:
        raise InvalidInput("La duración debe estar entre 1 minuto y 7 días.")
    if series.start_time.utcoffset() is not None:
        raise InvalidInput("La hora de inicio debe ser una hora local sin desplazamiento UTC.")
    try:
        ZoneInfo(series.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidInput("La zona horaria no es válida.") from exc
    if series.frequency == Frequency.WEEKLY:
        days = series.weekdays or (series.start_date.weekday(),)
        if any(day < 0 or day > 6 for day in days) or len(set(days)) != len(days):
            raise InvalidInput("Selecciona días de la semana válidos.")
        series = EventSeries(**{**series.__dict__, "weekdays": tuple(sorted(days))})
    elif series.weekdays:
        raise InvalidInput("Los días de la semana solo aplican a la repetición semanal.")
    if series.end_mode == EndMode.DATE:
        if series.end_date is None or series.end_date < series.start_date:
            raise InvalidInput("La fecha final debe ser igual o posterior al inicio.")
        if series.occurrence_count is not None:
            raise InvalidInput("La fecha final no puede combinarse con un número de eventos.")
    elif series.end_mode == EndMode.COUNT:
        if series.occurrence_count is None or not 1 <= series.occurrence_count <= 10000:
            raise InvalidInput("El número de eventos debe estar entre 1 y 10000.")
        if series.end_date is not None:
            raise InvalidInput("El número de eventos no puede combinarse con una fecha final.")
    elif series.end_date is not None or series.occurrence_count is not None:
        raise InvalidInput("Una serie sin fecha final no debe incluir un límite.")
    return series


def is_occurrence(series: EventSeries, day: date) -> bool:
    series = validate_series(series)
    if not _matches(series, day):
        return False
    if series.end_mode == EndMode.DATE and day > series.end_date:
        return False
    if series.end_mode == EndMode.COUNT and _occurrence_ordinal(series, day) > (
        series.occurrence_count or 0
    ):
        return False
    return True


def _matches(series: EventSeries, day: date) -> bool:
    offset = (day - series.start_date).days
    if offset < 0:
        return False
    if series.frequency == Frequency.DAILY:
        return offset % series.interval == 0
    if series.frequency == Frequency.WEEKLY:
        start_week = series.start_date - timedelta(days=series.start_date.weekday())
        week = (day - start_week).days // 7
        return week % series.interval == 0 and day.weekday() in series.weekdays
    months = (day.year - series.start_date.year) * 12 + day.month - series.start_date.month
    return months >= 0 and months % series.interval == 0 and day.day == series.start_date.day


def _occurrence_ordinal(series: EventSeries, day: date) -> int:
    """One-based occurrence number, without scanning dates before the requested range."""
    if series.frequency == Frequency.DAILY:
        return (day - series.start_date).days // series.interval + 1
    if series.frequency == Frequency.MONTHLY:
        return (
            (day.year - series.start_date.year) * 12 + day.month - series.start_date.month
        ) // series.interval + 1
    days = series.weekdays
    start_week = series.start_date - timedelta(days=series.start_date.weekday())
    target_week = (day - start_week).days // 7
    total = 0
    for week in range(0, target_week + 1, series.interval):
        for weekday in days:
            candidate = start_week + timedelta(weeks=week, days=weekday)
            if series.start_date <= candidate <= day:
                total += 1
    return total


def expand_series(
    series: EventSeries,
    range_start: datetime,
    range_end: datetime,
    exceptions: list[EventException],
) -> list[Event]:
    """Expand occurrences intersecting an aware instant range in the series' local zone."""
    series = validate_series(series)
    zone = ZoneInfo(series.timezone)
    local_start, local_end = range_start.astimezone(zone).date(), range_end.astimezone(zone).date()
    first = max(series.start_date, local_start - timedelta(days=7))
    last = local_end
    by_date = {(item.occurrence_date, item.occurrence_time): item for item in exceptions}
    output: list[Event] = []
    day = first
    while day <= last:
        if _matches(series, day):
            if series.end_mode == EndMode.DATE and day > series.end_date:
                break
            if series.end_mode == EndMode.COUNT and _occurrence_ordinal(series, day) > (
                series.occurrence_count or 0
            ):
                day += timedelta(days=1)
                continue
            exception = by_date.get((day, series.start_time))
            if not (exception and exception.cancelled):
                local_time = (
                    exception.override_start_time
                    if exception and exception.override_start_time
                    else series.start_time
                )
                duration = (
                    exception.override_duration_minutes
                    if exception and exception.override_duration_minutes
                    else series.duration_minutes
                )
                starts = datetime.combine(day, local_time, zone)
                # Keep wall-clock time where valid. A spring-forward gap has no
                # local instant, so that day's occurrence is skipped. For a
                # repeated fall-back time, zoneinfo's fold=0 selects its first
                # (earlier) offset consistently.
                roundtrip = starts.astimezone(ZoneInfo("UTC")).astimezone(zone)
                if roundtrip.replace(tzinfo=None) != starts.replace(tzinfo=None):
                    day += timedelta(days=1)
                    continue
                ends = starts + timedelta(minutes=duration)
                if exception:
                    if exception.override_title:
                        title = exception.override_title
                    else:
                        title = series.title
                    category = exception.override_category or series.category
                    icon_id = (
                        exception.override_custom_icon_id
                        if exception.has_icon_override
                        else series.custom_icon_id
                    )
                else:
                    title, category, icon_id = series.title, series.category, series.custom_icon_id
                start_utc, end_utc = (
                    starts.astimezone(ZoneInfo("UTC")),
                    ends.astimezone(ZoneInfo("UTC")),
                )
                if start_utc < range_end.astimezone(
                    ZoneInfo("UTC")
                ) and end_utc > range_start.astimezone(ZoneInfo("UTC")):
                    output.append(
                        Event(
                            id=uuid5(
                                series.id, f"{day.isoformat()}T{series.start_time.isoformat()}"
                            ),
                            member_id=series.member_id,
                            title=title,
                            starts_at=start_utc,
                            ends_at=end_utc,
                            category=category,
                            custom_icon_id=icon_id,
                            recurring_series_id=series.id,
                            occurrence_date=day,
                            occurrence_time=series.start_time,
                        )
                    )
        day += timedelta(days=1)
    return output
