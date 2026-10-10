from dataclasses import asdict
from datetime import date, time
from uuid import UUID, uuid4

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field

from app.domain.calendar import Calendar, Category, InvalidInput, MissingEntity
from app.domain.recurrence import (
    EndMode,
    EventException,
    EventSeries,
    Frequency,
    is_occurrence,
    validate_series,
)


class SeriesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UUID
    title: str = Field(min_length=1, max_length=200)
    start_date: date
    start_time: time
    duration_minutes: int = Field(ge=1, le=10080)
    timezone: str = Field(min_length=1, max_length=80)
    frequency: Frequency
    interval: int = Field(ge=1, le=365)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    end_mode: EndMode = EndMode.NEVER
    end_date: date | None = None
    occurrence_count: int | None = Field(default=None, ge=1, le=10000)
    category: Category = Category.OTHER
    custom_icon_id: UUID | None = None


class SeriesOutput(SeriesInput):
    id: UUID


class ExceptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occurrence_date: date
    occurrence_time: time
    cancelled: bool = False
    override_start_time: time | None = None
    override_duration_minutes: int | None = Field(default=None, ge=1, le=10080)
    override_title: str | None = Field(default=None, min_length=1, max_length=200)
    override_category: Category | None = None
    has_icon_override: bool = False
    override_custom_icon_id: UUID | None = None


class ExceptionOutput(ExceptionInput):
    series_id: UUID


def install_recurrence_routes(app: FastAPI, guarded: list, use_calendar):
    @app.get(
        "/api/v1/event-series",
        response_model=list[SeriesOutput],
        dependencies=guarded,
        tags=["events"],
    )
    def list_series(service: use_calendar, member_id: UUID | None = None):
        repo = service.recurrence_repository
        return [asdict(series) for series in repo.series(member_id)]

    @app.post(
        "/api/v1/event-series",
        response_model=SeriesOutput,
        status_code=201,
        dependencies=guarded,
        tags=["events"],
    )
    def create_series(data: SeriesInput, service: use_calendar):
        _validate_references(service, data)
        series = validate_series(
            EventSeries(
                uuid4(),
                data.member_id,
                data.title.strip(),
                data.start_date,
                data.start_time,
                data.duration_minutes,
                data.timezone,
                data.frequency,
                data.interval,
                tuple(data.weekdays),
                data.end_mode,
                data.end_date,
                data.occurrence_count,
                data.category,
                data.custom_icon_id,
            )
        )
        repo = service.recurrence_repository
        return asdict(repo.save_series(series))

    @app.put(
        "/api/v1/event-series/{series_id}",
        response_model=SeriesOutput,
        dependencies=guarded,
        tags=["events"],
    )
    def update_series(series_id: UUID, data: SeriesInput, service: use_calendar):
        repo = service.recurrence_repository
        if repo.get_series(series_id) is None:
            raise MissingEntity("No existe la serie recurrente.")
        _validate_references(service, data)
        series = validate_series(
            EventSeries(
                series_id,
                data.member_id,
                data.title.strip(),
                data.start_date,
                data.start_time,
                data.duration_minutes,
                data.timezone,
                data.frequency,
                data.interval,
                tuple(data.weekdays),
                data.end_mode,
                data.end_date,
                data.occurrence_count,
                data.category,
                data.custom_icon_id,
            )
        )
        return asdict(repo.save_series(series))

    @app.delete(
        "/api/v1/event-series/{series_id}", status_code=204, dependencies=guarded, tags=["events"]
    )
    def delete_series(series_id: UUID, service: use_calendar):
        repo = service.recurrence_repository
        if repo.get_series(series_id) is None:
            raise MissingEntity("No existe la serie recurrente.")
        repo.delete_series(series_id)
        return Response(status_code=204)

    @app.post(
        "/api/v1/event-series/{series_id}/exceptions",
        response_model=ExceptionOutput,
        dependencies=guarded,
        tags=["events"],
    )
    def save_exception(series_id: UUID, data: ExceptionInput, service: use_calendar):
        repo = service.recurrence_repository
        series = repo.get_series(series_id)
        if series is None:
            raise MissingEntity("No existe la serie recurrente.")
        if data.occurrence_time.utcoffset() is not None:
            raise InvalidInput("La hora de la excepción debe ser local, sin desplazamiento UTC.")
        if data.override_start_time and data.override_start_time.utcoffset() is not None:
            raise InvalidInput("La hora alternativa debe ser local, sin desplazamiento UTC.")
        if data.occurrence_time != series.start_time or not is_occurrence(
            series, data.occurrence_date
        ):
            raise InvalidInput("La fecha y hora no corresponden a una ocurrencia de esta serie.")
        if (
            data.has_icon_override
            and data.override_custom_icon_id is not None
            and service.repository.icon(data.override_custom_icon_id) is None
        ):
            raise MissingEntity("No existe el icono.")
        if data.override_category is not None and not isinstance(data.override_category, Category):
            raise InvalidInput("La categoría no es válida.")
        exception = EventException(
            series_id,
            data.occurrence_date,
            data.occurrence_time,
            data.cancelled,
            data.override_start_time,
            data.override_duration_minutes,
            data.override_title,
            data.override_category,
            data.has_icon_override,
            data.override_custom_icon_id,
        )
        return asdict(repo.save_exception(exception))

    @app.delete(
        "/api/v1/event-series/{series_id}/exceptions",
        status_code=204,
        dependencies=guarded,
        tags=["events"],
    )
    def remove_exception(
        series_id: UUID, occurrence_date: date, occurrence_time: time, service: use_calendar
    ):
        repo = service.recurrence_repository
        if repo.get_series(series_id) is None:
            raise MissingEntity("No existe la serie recurrente.")
        repo.delete_exception(series_id, occurrence_date, occurrence_time)
        return Response(status_code=204)


def _validate_references(service: Calendar, data: SeriesInput) -> None:
    if service.repository.member(data.member_id) is None:
        raise MissingEntity("No existe el integrante.")
    if data.custom_icon_id is not None and service.repository.icon(data.custom_icon_id) is None:
        raise MissingEntity("No existe el icono.")
