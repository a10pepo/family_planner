"""Stateless Streamable HTTP MCP endpoint for calendar event operations."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime, time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from app.adapters.oauth import OAuthVerifier
from app.adapters.storage import configured_storage
from app.domain.calendar import Calendar, Category, InvalidInput, MissingEntity
from app.domain.recurrence import expand_series

PROTOCOL_VERSION = "2025-11-25"
MCP_PATH = "/mcp"


class ListEventsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: AwareDatetime
    end: AwareDatetime
    member_id: UUID | None = None


class SaveEventArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID | None = None
    member_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    category: Category | None = None
    custom_icon_id: UUID | None = None


def _json_value(value: Any) -> Any:
    if isinstance(value, (UUID, date, datetime, time)):
        return value.isoformat() if not isinstance(value, UUID) else str(value)
    if isinstance(value, Category):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _event_value(event) -> dict[str, Any]:
    return _json_value(asdict(event))


def _tool_result(value: Any) -> dict[str, Any]:
    payload = json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":"))
    return {"content": [{"type": "text", "text": payload}], "structuredContent": value}


def _error_response(request_id: Any, code: int, message: str, data: Any = None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def create_mcp_app(storage=None, verifier=None) -> FastAPI:
    """Create the MCP app with injectable storage and token verifier for tests."""
    issuer = os.getenv("OAUTH_ISSUER", "")
    jwks_url = os.getenv("OAUTH_JWKS_URL", f"{issuer}/.well-known/jwks.json")
    client_id = os.getenv("MCP_OAUTH_CLIENT_ID", "")
    resource_url = os.getenv("MCP_RESOURCE_URL", "")
    scope_read = os.getenv("MCP_SCOPE_READ", "")
    scope_write = os.getenv("MCP_SCOPE_WRITE", "")
    authorization_endpoint = os.getenv("MCP_AUTHORIZATION_ENDPOINT", "")
    token_endpoint = os.getenv("MCP_TOKEN_ENDPOINT", "")
    timezone = os.getenv("FAMILY_TIMEZONE", "Europe/Madrid")
    ZoneInfo(timezone)

    storage = storage or configured_storage()
    verifier = verifier or OAuthVerifier(
        issuer,
        jwks_url,
        audience=client_id,
        provider="cognito",
        required_group="",
    )

    app = FastAPI(title="Family Planner MCP", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.storage = storage

    root_url = resource_url.removesuffix(MCP_PATH)
    metadata_url = f"{root_url}/.well-known/oauth-protected-resource/mcp"
    scopes = [scope for scope in (scope_read, scope_write) if scope]

    @app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
    @app.get("/mcp/.well-known/oauth-protected-resource", include_in_schema=False)
    def protected_resource_metadata():
        return {
            "resource": resource_url,
            "authorization_servers": [root_url],
            "scopes_supported": scopes,
            "bearer_methods_supported": ["header"],
        }

    @app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
    def authorization_server_metadata():
        return {
            "issuer": root_url,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["openid", *scopes],
            "authorization_response_iss_parameter_supported": False,
        }

    def authenticate(authorization: str | None, required_scope: str | None = None) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=401,
                detail="Se requiere iniciar sesión para acceder al calendario.",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer resource_metadata="{metadata_url}", resource="{resource_url}"'
                    )
                },
            )
        token = authorization[7:].strip()
        try:
            claims = verifier.verify(token)
        except HTTPException as exc:
            if exc.status_code == 503:
                raise
            raise HTTPException(
                status_code=401,
                detail="El token no es válido para este calendario.",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="invalid_token", resource_metadata="{metadata_url}", '
                        f'resource="{resource_url}"'
                    )
                },
            ) from exc

        audience = claims.get("aud")
        if resource_url not in (audience if isinstance(audience, list) else [audience]):
            raise HTTPException(
                status_code=401,
                detail="El token no fue emitido para este endpoint MCP.",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="invalid_token", resource_metadata="{metadata_url}", '
                        f'resource="{resource_url}"'
                    )
                },
            )

        granted = set(claims.get("scope", "").split())
        if required_scope and required_scope not in granted:
            raise HTTPException(
                status_code=403,
                detail="El token no tiene permiso para esta operación.",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="insufficient_scope", scope="{required_scope}", '
                        f'resource_metadata="{metadata_url}", resource="{resource_url}"'
                    )
                },
            )
        if not any(scope in granted for scope in scopes):
            raise HTTPException(
                status_code=403,
                detail="El token no tiene permisos de calendario.",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="insufficient_scope", scope="{scope_read}", '
                        f'resource_metadata="{metadata_url}", resource="{resource_url}"'
                    )
                },
            )
        return claims

    @app.post(MCP_PATH, include_in_schema=False)
    async def mcp_endpoint(request: Request, authorization: str | None = Header(default=None)):
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(_error_response(None, -32700, "Parse error"), status_code=400)
        if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
            return JSONResponse(_error_response(None, -32600, "Invalid Request"), status_code=400)
        request_id = body.get("id")
        method = body.get("method")
        if not isinstance(method, str):
            return JSONResponse(
                _error_response(request_id, -32600, "Invalid Request"), status_code=400
            )
        params = body.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return JSONResponse(
                _error_response(request_id, -32602, "Invalid params"), status_code=200
            )

        required_scope = None
        if method == "tools/call":
            tool_name = params.get("name")
            required_scope = scope_read if tool_name == "list_events" else scope_write
        try:
            claims = authenticate(authorization, required_scope)
        except HTTPException as exc:
            return JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers=exc.headers,
            )

        if method == "notifications/initialized" or (
            method.startswith("notifications/") and request_id is None
        ):
            return Response(status_code=202)
        if method == "ping":
            result = {}
        elif method == "initialize":
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": requested if requested == PROTOCOL_VERSION else PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "family-planner", "version": "1.0.0"},
                "instructions": (
                    "Consulta eventos por rango. Usa save_event para crear o editar; "
                    "nunca borres eventos."
                ),
            }
        elif method == "tools/list":
            granted = set(claims.get("scope", "").split())
            tools = []
            if scope_read in granted:
                tools.append(
                    {
                        "name": "list_events",
                        "description": (
                            "Lee eventos del calendario familiar dentro de un rango temporal."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string", "format": "date-time"},
                                "end": {"type": "string", "format": "date-time"},
                                "member_id": {"type": "string", "format": "uuid"},
                            },
                            "required": ["start", "end"],
                            "additionalProperties": False,
                        },
                    }
                )
            if scope_write in granted:
                tools.append(
                    {
                        "name": "save_event",
                        "description": "Crea un evento o edita uno existente. No elimina eventos.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "event_id": {
                                    "anyOf": [
                                        {"type": "string", "format": "uuid"},
                                        {"type": "null"},
                                    ]
                                },
                                "member_id": {
                                    "anyOf": [
                                        {"type": "string", "format": "uuid"},
                                        {"type": "null"},
                                    ]
                                },
                                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                                "starts_at": {"type": "string", "format": "date-time"},
                                "ends_at": {"type": "string", "format": "date-time"},
                                "category": {
                                    "anyOf": [
                                        {
                                            "type": "string",
                                            "enum": [category.value for category in Category],
                                        },
                                        {"type": "null"},
                                    ]
                                },
                                "custom_icon_id": {
                                    "anyOf": [
                                        {"type": "string", "format": "uuid"},
                                        {"type": "null"},
                                    ]
                                },
                            },
                            "required": ["title", "starts_at", "ends_at"],
                            "additionalProperties": False,
                        },
                    }
                )
            result = {"tools": tools}
        elif method == "tools/call":
            if not isinstance(params.get("name"), str):
                return JSONResponse(
                    _error_response(request_id, -32602, "Invalid params"), status_code=200
                )
            result = await _call_tool(params["name"], params.get("arguments", {}), claims, storage)
        else:
            return JSONResponse(_error_response(request_id, -32601, "Method not found"))

        if request_id is None:
            return Response(status_code=202)
        return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})

    return app


async def _call_tool(name: str, arguments: Any, claims: dict, storage) -> dict[str, Any]:
    try:
        if not isinstance(arguments, dict):
            raise ValueError("Los argumentos deben ser un objeto JSON.")
        if name == "list_events":
            data = ListEventsArguments.model_validate(arguments)
            with storage.repositories(claims["sub"]) as repositories:
                service = Calendar(repositories.calendar)
                recurring = repositories.recurrence
                punctual = service.list_events(data.start, data.end, data.member_id)
                for series in recurring.series(data.member_id):
                    punctual.extend(
                        expand_series(series, data.start, data.end, recurring.exceptions(series.id))
                    )
            events = [
                _event_value(event) for event in sorted(punctual, key=lambda item: item.starts_at)
            ]
            return _tool_result(events)

        if name == "save_event":
            data = SaveEventArguments.model_validate(arguments)
            if data.event_id is None and data.member_id is None:
                raise ValueError("member_id es obligatorio al crear un evento.")
            if data.event_id is not None and data.member_id is not None:
                raise ValueError("member_id no se puede cambiar al editar un evento.")
            with storage.repositories(claims["sub"]) as repositories:
                service = Calendar(repositories.calendar)
                if data.event_id is None:
                    event = service.create_event(
                        data.member_id,
                        data.title,
                        data.starts_at,
                        data.ends_at,
                        data.category or Category.OTHER,
                        data.custom_icon_id,
                    )
                else:
                    event = service.update_event(
                        data.event_id,
                        data.title,
                        data.starts_at,
                        data.ends_at,
                        data.category,
                        data.custom_icon_id,
                        "custom_icon_id" in arguments,
                    )
            return _tool_result(_event_value(event))

        return _tool_error(f"Herramienta MCP desconocida: {name}")
    except ValidationError as exc:
        return _tool_error(
            "Argumentos no válidos: " + "; ".join(error["msg"] for error in exc.errors())
        )
    except (InvalidInput, MissingEntity, ValueError) as exc:
        return _tool_error(str(exc))
