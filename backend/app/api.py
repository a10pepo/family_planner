import os
from collections.abc import Iterator
from dataclasses import asdict
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.database import SqlCalendarRepository, make_engine
from app.adapters.oauth import OAuthVerifier
from app.domain.calendar import Calendar, Category, InvalidInput, MissingEntity


class MemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class MemberOutput(MemberInput):
    id: UUID


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    category: Category | None = None


class EventInput(EventUpdate):
    member_id: UUID
    category: Category = Category.OTHER


class EventOutput(EventInput):
    id: UUID


def create_app(database_url: str | None = None, verifier=None) -> FastAPI:
    origin = os.getenv("APP_ORIGIN", "http://localhost:8080").rstrip("/")
    issuer = f"{origin}/auth/realms/family"
    zone = os.getenv("FAMILY_TIMEZONE", "Europe/Madrid")
    ZoneInfo(zone)
    engine = make_engine(database_url or os.environ["DATABASE_URL"])
    auth = verifier or OAuthVerifier(
        issuer,
        os.getenv(
            "OAUTH_JWKS_URL",
            "http://identity:8080/auth/realms/family/protocol/openid-connect/certs",
        ),
    )
    oauth = OAuth2AuthorizationCodeBearer(
        authorizationUrl=f"{issuer}/protocol/openid-connect/auth",
        tokenUrl=f"{issuer}/protocol/openid-connect/token",
    )
    app = FastAPI(
        title="Family Planner API",
        version="1.0.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
        redoc_url=None,
        swagger_ui_init_oauth={
            "clientId": "family-planner",
            "usePkceWithAuthorizationCodeGrant": True,
        },
    )
    app.state.engine = engine

    def authenticated(token: Annotated[str, Depends(oauth)]):
        return auth.verify(token)

    def calendar() -> Iterator[Calendar]:
        with Session(engine) as session, session.begin():
            yield Calendar(SqlCalendarRepository(session))

    @app.exception_handler(InvalidInput)
    async def invalid_input(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(MissingEntity)
    async def missing_entity(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.get("/api/health", tags=["system"])
    def health():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM members LIMIT 1"))
        except Exception as exc:
            raise HTTPException(503, "La base de datos aún no está disponible.") from exc
        return {"status": "ok"}

    @app.get("/api/v1/config", tags=["system"])
    def config():
        return {
            "timezone": zone,
            "oauth_url": f"{origin}/auth",
            "realm": "family",
            "client_id": "family-planner",
        }

    guarded = [Depends(authenticated)]
    use_calendar = Annotated[Calendar, Depends(calendar)]

    @app.get(
        "/api/v1/members", response_model=list[MemberOutput], dependencies=guarded, tags=["members"]
    )
    def list_members(service: use_calendar):
        return [asdict(member) for member in service.repository.members()]

    @app.post(
        "/api/v1/members",
        response_model=MemberOutput,
        status_code=201,
        dependencies=guarded,
        tags=["members"],
    )
    def add_member(data: MemberInput, service: use_calendar):
        return asdict(service.add_member(data.name, data.color))

    @app.get(
        "/api/v1/events", response_model=list[EventOutput], dependencies=guarded, tags=["events"]
    )
    def list_events(
        start: AwareDatetime,
        end: AwareDatetime,
        service: use_calendar,
        member_id: UUID | None = None,
    ):
        return [asdict(event) for event in service.list_events(start, end, member_id)]

    @app.post(
        "/api/v1/events",
        response_model=EventOutput,
        status_code=201,
        dependencies=guarded,
        tags=["events"],
    )
    def add_event(data: EventInput, service: use_calendar):
        return asdict(
            service.create_event(
                data.member_id, data.title, data.starts_at, data.ends_at, data.category
            )
        )

    @app.put(
        "/api/v1/events/{event_id}",
        response_model=EventOutput,
        dependencies=guarded,
        tags=["events"],
    )
    def update_event(event_id: UUID, data: EventUpdate, service: use_calendar):
        return asdict(
            service.update_event(event_id, data.title, data.starts_at, data.ends_at, data.category)
        )

    @app.delete("/api/v1/events/{event_id}", status_code=204, dependencies=guarded, tags=["events"])
    def delete_event(event_id: UUID, service: use_calendar):
        service.delete_event(event_id)
        return Response(status_code=204)

    return app
