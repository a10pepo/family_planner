"""Stateless Streamable HTTP MCP endpoint for calendar event operations."""

from __future__ import annotations

import json
import logging
import os
import time as monotonic_time
from dataclasses import asdict
from datetime import date, datetime, time
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4
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
logger = logging.getLogger("family_planner.mcp.diagnostics")


def _argument_types(tool_name: str, arguments: Any) -> dict[str, str]:
    """Return argument names and JSON types without logging their values."""
    allowed = {
        "list_members": set(),
        "list_events": {"start", "end", "member_id"},
        "save_event": {
            "event_id",
            "member_id",
            "title",
            "starts_at",
            "ends_at",
            "category",
            "custom_icon_id",
        },
    }.get(tool_name, set())
    if not isinstance(arguments, dict):
        return {"arguments": _json_type(arguments)}
    types = {key: _json_type(value) for key, value in arguments.items() if key in allowed}
    unknown_count = sum(key not in allowed for key in arguments)
    if unknown_count:
        types["unknown_fields"] = f"count:{unknown_count}"
    return types


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _diagnostic_log(enabled: bool, event: str, **fields: Any) -> None:
    if enabled:
        logger.info("%s", json.dumps({"event": event, **fields}, separators=(",", ":")))


def _audience_diagnostics(audience: Any, resource_url: str) -> dict[str, Any]:
    values = audience if isinstance(audience, list) else [audience]
    string_values = [value for value in values if isinstance(value, str)]
    expected = urlsplit(resource_url)
    parsed_values = []
    for value in string_values:
        try:
            parsed_values.append(urlsplit(value))
        except ValueError:
            continue
    return {
        "audience_claim_present": audience is not None,
        "audience_claim_type": _json_type(audience),
        "audience_element_types": sorted({_json_type(value) for value in values})
        if isinstance(audience, list)
        else [],
        "audience_matches_resource": resource_url in string_values,
        "audience_host_matches_resource": any(
            value.scheme == expected.scheme and value.netloc == expected.netloc
            for value in parsed_values
        ),
        "audience_path_matches_resource": any(
            value.path == expected.path for value in parsed_values
        ),
    }


class ListEventsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: AwareDatetime
    end: AwareDatetime
    member_id: UUID | None = None


class ListMembersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


def _auth_error(
    status_code: int,
    reason: str,
    detail: str,
    headers: dict[str, str],
    diagnostic_fields: dict[str, Any] | None = None,
):
    error = HTTPException(status_code=status_code, detail=detail, headers=headers)
    error.diagnostic_reason = reason
    error.diagnostic_fields = diagnostic_fields or {}
    return error


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
    diagnostic_logs = (
        os.getenv("APP_ENVIRONMENT") == "preview"
        and os.getenv("MCP_DIAGNOSTIC_LOGS", "false").lower() == "true"
    )

    @app.middleware("http")
    async def log_mcp_http_request(request: Request, call_next):
        if request.url.path != MCP_PATH:
            return await call_next(request)
        diagnostic_id = str(uuid4())
        request.state.mcp_diagnostic_id = diagnostic_id
        started = monotonic_time.perf_counter()
        _diagnostic_log(
            diagnostic_logs,
            "mcp_http_received",
            request_id=diagnostic_id,
            http_method=request.method,
            path=MCP_PATH,
        )
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            _diagnostic_log(
                diagnostic_logs,
                "mcp_http_exception",
                request_id=diagnostic_id,
                exception_type=type(exc).__name__,
            )
            raise
        finally:
            _diagnostic_log(
                diagnostic_logs,
                "mcp_http_completed",
                request_id=diagnostic_id,
                status_code=status_code,
                duration_ms=round((monotonic_time.perf_counter() - started) * 1000, 2),
            )

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
            raise _auth_error(
                status_code=401,
                reason="bearer_missing_or_malformed",
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
                exc.diagnostic_reason = "token_verifier_unavailable"
                raise
            raise _auth_error(
                status_code=401,
                reason="token_verification_failed",
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
            raise _auth_error(
                status_code=401,
                reason="resource_audience_mismatch",
                detail="El token no fue emitido para este endpoint MCP.",
                diagnostic_fields=_audience_diagnostics(audience, resource_url),
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="invalid_token", resource_metadata="{metadata_url}", '
                        f'resource="{resource_url}"'
                    )
                },
            )

        granted = set(claims.get("scope", "").split())
        if required_scope and required_scope not in granted:
            raise _auth_error(
                status_code=403,
                reason="required_scope_missing",
                detail="El token no tiene permiso para esta operación.",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="insufficient_scope", scope="{required_scope}", '
                        f'resource_metadata="{metadata_url}", resource="{resource_url}"'
                    )
                },
            )
        if not any(scope in granted for scope in scopes):
            raise _auth_error(
                status_code=403,
                reason="calendar_scope_missing",
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
        diagnostic_id = request.state.mcp_diagnostic_id
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            _diagnostic_log(
                diagnostic_logs,
                "mcp_request_rejected",
                request_id=diagnostic_id,
                stage="json_parse",
                reason="malformed_json",
                status_code=400,
            )
            return JSONResponse(_error_response(None, -32700, "Parse error"), status_code=400)
        if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
            _diagnostic_log(
                diagnostic_logs,
                "mcp_request_rejected",
                request_id=diagnostic_id,
                stage="json_rpc_validation",
                reason="invalid_request",
                status_code=400,
            )
            return JSONResponse(_error_response(None, -32600, "Invalid Request"), status_code=400)
        request_id = body.get("id")
        method = body.get("method")
        if not isinstance(method, str):
            _diagnostic_log(
                diagnostic_logs,
                "mcp_request_rejected",
                request_id=diagnostic_id,
                stage="json_rpc_validation",
                reason="method_missing_or_invalid",
                status_code=400,
            )
            return JSONResponse(
                _error_response(request_id, -32600, "Invalid Request"), status_code=400
            )
        params = body.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            _diagnostic_log(
                diagnostic_logs,
                "mcp_request_rejected",
                request_id=diagnostic_id,
                stage="json_rpc_validation",
                method=(
                    method
                    if method in {"initialize", "ping", "tools/list", "tools/call"}
                    else "unknown"
                ),
                reason="params_not_object",
                status_code=200,
            )
            return JSONResponse(
                _error_response(request_id, -32602, "Invalid params"), status_code=200
            )

        required_scope = None
        if method == "tools/call":
            tool_name = params.get("name")
            required_scope = (
                scope_read if tool_name in {"list_members", "list_events"} else scope_write
            )
        safe_method = (
            method
            if method
            in {"initialize", "ping", "tools/list", "tools/call", "notifications/initialized"}
            else "unknown"
        )
        safe_tool_name = (
            tool_name
            if method == "tools/call"
            and isinstance(tool_name, str)
            and tool_name in {"list_members", "list_events", "save_event"}
            else None
        )
        _diagnostic_log(
            diagnostic_logs,
            "mcp_rpc_received",
            request_id=diagnostic_id,
            jsonrpc_method=safe_method,
            tool=safe_tool_name,
            argument_types=(
                _argument_types(safe_tool_name, params.get("arguments", {}))
                if safe_tool_name
                else None
            ),
        )
        try:
            claims = authenticate(authorization, required_scope)
        except HTTPException as exc:
            _diagnostic_log(
                diagnostic_logs,
                "mcp_request_rejected",
                request_id=diagnostic_id,
                stage="authentication",
                reason=getattr(exc, "diagnostic_reason", "authentication_failed"),
                status_code=exc.status_code,
                jsonrpc_method=safe_method,
                tool=safe_tool_name,
                **getattr(exc, "diagnostic_fields", {}),
            )
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
                    "Consulta integrantes y eventos por rango. Usa save_event para crear o editar; "
                    "nunca borres eventos."
                ),
            }
        elif method == "tools/list":
            granted = set(claims.get("scope", "").split())
            tools = []
            if scope_read in granted:
                tools.append(
                    {
                        "name": "list_members",
                        "description": (
                            "Lista los integrantes activos con su ID y nombre para identificarlos."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    }
                )
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
                        "description": (
                            "Crea o edita un evento; usa list_members para resolver el integrante. "
                            "No elimina eventos."
                        ),
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
                                    ],
                                    "description": (
                                        "Obligatorio al crear; al editar, si se indica, reasigna "
                                        "el evento a ese integrante activo."
                                    ),
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
                _diagnostic_log(
                    diagnostic_logs,
                    "mcp_request_rejected",
                    request_id=diagnostic_id,
                    stage="tool_validation",
                    reason="tool_name_missing_or_invalid",
                    status_code=200,
                )
                return JSONResponse(
                    _error_response(request_id, -32602, "Invalid params"), status_code=200
                )
            tool_name = safe_tool_name or "unknown"
            _diagnostic_log(
                diagnostic_logs,
                "mcp_tool_started",
                request_id=diagnostic_id,
                tool=tool_name,
                argument_types=_argument_types(tool_name, params.get("arguments", {})),
            )

            def log_tool_error(reason: str, **details: Any) -> None:
                _diagnostic_log(
                    diagnostic_logs,
                    "mcp_tool_rejected",
                    request_id=diagnostic_id,
                    tool=tool_name,
                    reason=reason,
                    **details,
                )

            result = await _call_tool(
                params["name"],
                params.get("arguments", {}),
                claims,
                storage,
                on_error=log_tool_error,
            )
            tool_is_error = bool(result.get("isError"))
            structured_result = result.get("structuredContent")
            _diagnostic_log(
                diagnostic_logs,
                "mcp_tool_completed",
                request_id=diagnostic_id,
                tool=tool_name,
                outcome="error" if tool_is_error else "success",
                result_count=(
                    len(structured_result)
                    if tool_name in {"list_members", "list_events"}
                    and isinstance(structured_result, list)
                    else None
                ),
            )
        else:
            _diagnostic_log(
                diagnostic_logs,
                "mcp_request_rejected",
                request_id=diagnostic_id,
                stage="method_dispatch",
                reason="method_not_found",
                status_code=200,
                jsonrpc_method="unknown",
            )
            return JSONResponse(_error_response(request_id, -32601, "Method not found"))

        if request_id is None:
            return Response(status_code=202)
        return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})

    return app


async def _call_tool(
    name: str, arguments: Any, claims: dict, storage, on_error=None
) -> dict[str, Any]:
    try:
        if not isinstance(arguments, dict):
            raise ValueError("Los argumentos deben ser un objeto JSON.")
        if name == "list_members":
            ListMembersArguments.model_validate(arguments)
            with storage.repositories(claims["sub"]) as repositories:
                members = repositories.calendar.members()
            return _tool_result(
                [
                    {"id": str(member.id), "name": member.name, "active": member.active}
                    for member in members
                ]
            )

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
                        data.member_id,
                    )
            return _tool_result(_event_value(event))

        if on_error:
            on_error("unknown_tool")
        return _tool_error("Herramienta MCP desconocida.")
    except ValidationError as exc:
        if on_error:
            on_error("argument_validation_failed", error_count=len(exc.errors()))
        return _tool_error(
            "Argumentos no válidos: " + "; ".join(error["msg"] for error in exc.errors())
        )
    except (InvalidInput, MissingEntity, ValueError) as exc:
        if on_error:
            on_error("domain_validation_failed", error_type=type(exc).__name__)
        return _tool_error(str(exc))
