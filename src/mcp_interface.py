"""MCP transport over the existing ASGI API, with no second server or network hop.

Using the ASGI pipeline deliberately retains route dependencies, middleware,
threadpool execution, response models and error handlers as the single source of
business behavior. Tool schemas are derived from the same OpenAPI contract.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
import json
import logging
import os
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

logger = logging.getLogger(__name__)
# POST retrieval operations are reads; all other writes are conservatively
# destructive/non-idempotent, including operational jobs and intent claims.
READ_POSTS = {"/v1/retrieve", "/v1/retrieve/structured", "/v1/orchestrator/retrieve"}
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status_code": {"type": "integer"},
        "body": {},
        "content_type": {"type": "string"},
    },
    "required": ["status_code", "body", "content_type"],
    "additionalProperties": False,
}


def _refs(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_refs(v) for v in value]
    if isinstance(value, str) and value.startswith("#/components/schemas/"):
        return value.replace("#/components/schemas/", "#/$defs/", 1)
    return value


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    tool: Tool


def build_operations(app: FastAPI) -> dict[str, Operation]:
    spec = app.openapi()
    operations = {}
    route_names = {
        (r.path, m.lower()): r.name
        for r in app.routes
        if isinstance(r, APIRoute)
        for m in r.methods
    }
    definitions = _refs(spec.get("components", {}).get("schemas", {}))
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue
            props, required = {}, []
            for location in ("path", "query"):
                parameters = [
                    p for p in operation.get("parameters", []) if p["in"] == location
                ]
                if not parameters:
                    continue
                group = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                }
                needed = []
                for param in parameters:
                    schema = deepcopy(param["schema"])
                    if param.get("description"):
                        schema["description"] = param["description"]
                    group["properties"][param["name"]] = schema
                    if param.get("required"):
                        needed.append(param["name"])
                if needed:
                    group["required"] = needed
                    required.append(location)
                props[location] = group
            body = operation.get("requestBody")
            if body:
                props["body"] = deepcopy(body["content"]["application/json"]["schema"])
                if body.get("required"):
                    required.append("body")
            schema = _refs(
                {
                    "type": "object",
                    "properties": props,
                    "additionalProperties": False,
                    "required": required,
                }
            )
            # Include only reachable definitions so discovery stays small.
            pending = [schema]
            used = {}
            while pending:
                value = pending.pop()
                if isinstance(value, dict):
                    ref = value.get("$ref", "")
                    if ref.startswith("#/$defs/"):
                        key = ref.rsplit("/", 1)[1]
                        if key not in used:
                            used[key] = deepcopy(definitions[key])
                            pending.append(used[key])
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
            if used:
                schema["$defs"] = used
            name = route_names[path, method]
            # Endpoint function names are unique in this API; fail on collision.
            if name in operations:
                raise ValueError(f"Duplicate MCP tool name: {name}")
            read = method in {"get", "head", "options"} or path in READ_POSTS
            description = operation.get("description") or operation.get("summary", name)
            description += f"\nREST: {method.upper()} {path}. Returns status_code, body and content_type."
            if not read:
                description += " May mutate data or start operational work; do not retry automatically."
            tool = Tool(
                name=name,
                description=description,
                inputSchema=schema,
                outputSchema=RESULT_SCHEMA,
                annotations=ToolAnnotations(
                    readOnlyHint=read,
                    destructiveHint=not read,
                    idempotentHint=read,
                    openWorldHint=True,
                ),
            )
            operations[name] = Operation(method.upper(), path, tool)
    # Framework documentation endpoints are not in OpenAPI but are still HTTP APIs.
    for name, path in (
        ("get_openapi", app.openapi_url),
        ("get_docs", app.docs_url),
        ("get_redoc", app.redoc_url),
        ("get_docs_oauth2_redirect", app.swagger_ui_oauth2_redirect_url),
    ):
        if path:
            operations[name] = Operation(
                "GET",
                path,
                Tool(
                    name=name,
                    description=f"Read GET {path}; JSON schema or HTML documentation.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                    outputSchema=RESULT_SCHEMA,
                    annotations=ToolAnnotations(
                        readOnlyHint=True,
                        destructiveHint=False,
                        idempotentHint=True,
                        openWorldHint=False,
                    ),
                ),
            )
    return operations


def result(
    status: int, body: Any, content_type: str = "application/json"
) -> CallToolResult:
    payload = {"status_code": status, "body": body, "content_type": content_type}
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structuredContent=payload,
        isError=status >= 400,
    )


class MCPInterface:
    def __init__(self, app: FastAPI):
        self.app = app
        self.operations = build_operations(app)
        self.server = Server("agentic-memories", version="0.1.0")
        hosts = [
            "localhost",
            "127.0.0.1",
            "[::1]",
            "localhost:*",
            "127.0.0.1:*",
            "[::1]:*",
        ]
        hosts.extend(
            x.strip()
            for x in os.getenv("MCP_ALLOWED_HOSTS", "").split(",")
            if x.strip()
        )
        origins = [
            "http://localhost",
            "http://127.0.0.1",
            "http://[::1]",
            "http://localhost:*",
            "http://127.0.0.1:*",
            "http://[::1]:*",
        ]
        origins.extend(
            x.strip()
            for x in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",")
            if x.strip()
        )
        self.security_settings = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        )
        self.session_manager = self._new_session_manager()

        @self.server.list_tools()
        async def list_tools():
            return [op.tool for op in self.operations.values()]

        @self.server.call_tool(validate_input=False)
        async def call_tool(name: str, arguments: dict[str, Any]):
            return await self.invoke(
                name, arguments, self.server.request_context.request
            )

    def _new_session_manager(self):
        return StreamableHTTPSessionManager(
            app=self.server,
            stateless=True,
            json_response=True,
            security_settings=self.security_settings,
        )

    @asynccontextmanager
    async def lifespan(self):
        try:
            async with self.session_manager.run():
                yield
        finally:
            # SDK managers are single-use. ASGI apps can have sequential lifespans
            # (notably TestClient); each must get a fresh manager/task group.
            self.session_manager = self._new_session_manager()

    async def invoke(
        self, name: str, arguments: dict[str, Any], request: Request | None = None
    ):
        operation = self.operations.get(name)
        if operation is None:
            return result(404, {"detail": "Unknown MCP tool"})
        errors = list(
            Draft202012Validator(operation.tool.inputSchema).iter_errors(arguments)
        )
        if errors:
            return result(
                422,
                {
                    "detail": [
                        {"loc": list(e.absolute_path), "msg": e.message} for e in errors
                    ]
                },
            )
        path = operation.path
        for key, value in arguments.get("path", {}).items():
            # ASGI servers decode slashes and normalize dot segments. Refuse path
            # escapes rather than allowing an argument to select another operation.
            value = str(value)
            if value in {".", ".."} or any(c in value for c in "/\\%?#"):
                return result(
                    422, {"detail": "Path parameters must be single literal segments"}
                )
            path = path.replace("{" + key + "}", quote(value, safe=""))
        query = []
        for key, value in arguments.get("query", {}).items():
            if value is not None:
                for item in value if isinstance(value, list) else [value]:
                    query.append(
                        (
                            key,
                            str(item).lower() if isinstance(item, bool) else str(item),
                        )
                    )
        # Credentials belong to the caller's HTTP request, never to tool arguments.
        # Retain all caller headers except framing/transport headers, so future
        # API-key dependencies work without an MCP-specific credential store.
        excluded = {
            "content-length",
            "content-type",
            "accept",
            "connection",
            "transfer-encoding",
            "mcp-session-id",
            "mcp-protocol-version",
            "last-event-id",
        }
        headers = (
            {k: v for k, v in request.headers.items() if k not in excluded}
            if request
            else {}
        )
        client_address = (
            tuple(request.client) if request and request.client else ("127.0.0.1", 0)
        )
        transport = httpx.ASGITransport(
            app=self.app, raise_app_exceptions=False, client=client_address
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            response = await client.request(
                operation.method,
                path,
                params=query,
                headers=headers,
                **({"json": arguments["body"]} if "body" in arguments else {}),
            )
        content_type = response.headers.get("content-type", "")
        if not response.content:
            body = None
        elif "application/json" in content_type:
            body = response.json()
        else:
            body = response.text
        return result(response.status_code, body, content_type)

    async def __call__(self, scope, receive, send):
        # Stateless JSON mode has no server event stream or session to delete.
        if scope["method"] in {"GET", "DELETE"}:
            await Response(status_code=405, headers={"Allow": "POST"})(
                scope, receive, send
            )
            return
        await self.session_manager.handle_request(scope, receive, send)


def install_mcp(app: FastAPI) -> MCPInterface:
    interface = MCPInterface(app)
    # A raw ASGI Route avoids Mount's /mcp -> /mcp/ redirect and nested /mcp/mcp.
    app.router.routes.append(
        Route("/mcp", endpoint=interface, methods=["GET", "POST", "DELETE"])
    )
    return interface
