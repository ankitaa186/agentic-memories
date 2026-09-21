"""Exercise MCP JSON-RPC over the real ASGI transport and shared REST handlers."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import anyio
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
import pytest

from src.mcp_interface import RESULT_SCHEMA

HEADERS = {
    "accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


def rpc(client, method, params=None, headers=None):
    response = client.post(
        "/mcp",
        headers={**HEADERS, **(headers or {})},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def call(client, name, arguments=None, headers=None):
    value = rpc(
        client, "tools/call", {"name": name, "arguments": arguments or {}}, headers
    )
    Draft202012Validator(RESULT_SCHEMA).validate(value["structuredContent"])
    assert json.loads(value["content"][0]["text"]) == value["structuredContent"]
    return value


@pytest.fixture
def mcp_client(app_module):
    with TestClient(app_module.app, base_url="http://localhost") as client:
        yield client


def test_discovery_and_complete_route_mapping(mcp_client, app_module):
    initialization = rpc(
        mcp_client,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    )
    assert "tools" in initialization["capabilities"]
    notification = mcp_client.post(
        "/mcp",
        headers=HEADERS,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert notification.status_code == 202
    tools = rpc(mcp_client, "tools/list")["tools"]
    operations = app_module.app.state.mcp.operations
    expected = {
        (method, route.path)
        for route in app_module.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    actual = {(op.method, op.path) for op in operations.values()}
    assert expected <= actual
    assert len(expected) == 39
    assert len(tools) == len(operations) == 43
    assert {t["name"] for t in tools} == set(operations)
    mapping = json.loads(
        (Path(__file__).parents[2] / "docs/mcp-route-mapping.json").read_text()
    )
    assert {(r["method"], r["path"], r["tool"]) for r in mapping} == {
        (op.method, op.path, name) for name, op in operations.items()
    }
    schemas = {row["tool"]: row["inputSchema"] for row in mapping}
    for tool in tools:
        assert tool["inputSchema"] == schemas[tool["name"]]
        Draft202012Validator.check_schema(tool["inputSchema"])
        Draft202012Validator.check_schema(tool["outputSchema"])
        if operations[tool["name"]].method in {"DELETE", "PUT", "PATCH"}:
            assert tool["annotations"]["destructiveHint"]
            assert not tool["annotations"]["readOnlyHint"]
    health = call(mcp_client, "health")
    assert not health["isError"]
    assert health["structuredContent"]["body"]["status"] == "ok"
    assert call(mcp_client, "get_openapi")["structuredContent"]["body"]["paths"]
    assert "<html>" in call(mcp_client, "get_docs")["structuredContent"]["body"]


def test_errors_and_transport(mcp_client):
    for name, args, status in [
        ("unknown", {}, 404),
        ("retrieve", {}, 422),
        ("list_intents", {"query": {"user_id": "u", "limit": 101}}, 422),
        ("get_intent", {"path": {"intent_id": "bad-uuid"}}, 422),
        (
            "get_profile_category",
            {"path": {"category": "../portfolio"}, "query": {"user_id": "u"}},
            422,
        ),
        ("health", {"headers": {"authorization": "forged"}}, 422),
    ]:
        value = call(mcp_client, name, args)
        assert value["isError"]
        assert value["structuredContent"]["status_code"] == status
    assert mcp_client.get("/mcp", headers=HEADERS).status_code == 405
    assert mcp_client.delete("/mcp", headers=HEADERS).status_code == 405
    assert (
        mcp_client.post(
            "/mcp", headers={**HEADERS, "host": "evil.example"}, json={}
        ).status_code
        == 421
    )
    assert (
        mcp_client.post(
            "/mcp", headers={**HEADERS, "origin": "https://evil.example"}, json={}
        ).status_code
        == 403
    )
    response = mcp_client.post(
        "/mcp",
        headers={**HEADERS, "content-type": "application/json"},
        content="invalid json",
    )
    assert response.status_code == 400


def test_identity_is_per_call_and_rest_equivalent(mcp_client, monkeypatch):
    def verify(token):
        if token == "bad":
            raise ValueError("invalid")
        return {"sub": token, "email": token + "@example.com"}

    monkeypatch.setattr("src.app.verify_cf_access_token", verify)
    for headers in [
        {"authorization": "Bearer alice"},
        {"cf-access-jwt-assertion": "bob"},
        {"cookie": "CF_Authorization=carol"},
        {"authorization": "Bearer bad"},
        {},
    ]:
        rest = mcp_client.get("/v1/me", headers=headers)
        mcp = call(mcp_client, "me", headers=headers)
        assert mcp["structuredContent"]["body"] == rest.json()


def test_store_reuses_ingestion_and_user_scoping(mcp_client, monkeypatch, redis_stub):
    ingestion = MagicMock(
        return_value={"memories": [], "memory_ids": [], "storage_results": {}}
    )
    monkeypatch.setattr(
        "src.services.unified_ingestion_graph.run_unified_ingestion", ingestion
    )
    payload = {"user_id": "mcp-user", "history": [{"role": "user", "content": "hello"}]}
    value = call(mcp_client, "store_transcript", {"body": payload})
    assert not value["isError"]
    assert ingestion.call_count == 1
    assert redis_stub.counters["mem:ns:mcp-user"] == 1
    rest = mcp_client.post("/v1/store", json=payload)
    assert value["structuredContent"]["body"] == rest.json()
    monkeypatch.setattr("src.app.is_llm_configured", lambda: False)
    failed = call(mcp_client, "store_transcript", {"body": payload})
    assert failed["isError"]
    assert failed["structuredContent"]["status_code"] == 400


def test_delete_and_not_found_preserve_status(mcp_client, monkeypatch):
    from src.routers import intents

    service = MagicMock()
    service.delete_intent.return_value = SimpleNamespace(success=True)
    monkeypatch.setattr(intents, "get_timescale_conn", lambda: object())
    monkeypatch.setattr(intents, "release_timescale_conn", lambda conn: None)
    monkeypatch.setattr(intents, "IntentService", lambda conn: service)
    args = {"path": {"intent_id": "b476792f-c710-447b-82d3-58a8d8bbc820"}}
    value = call(mcp_client, "delete_intent", args)
    assert value["structuredContent"] == {
        "status_code": 204,
        "body": None,
        "content_type": "",
    }
    assert not value["isError"]
    service.delete_intent.assert_called_once()
    service.delete_intent.return_value = SimpleNamespace(success=False)
    assert (
        call(mcp_client, "delete_intent", args)["structuredContent"]["status_code"]
        == 404
    )


def test_memory_ownership_restriction(mcp_client, monkeypatch):
    from src.routers import memories

    monkeypatch.setattr(memories, "get_chroma_client", lambda: object())
    monkeypatch.setattr(
        memories, "get_chroma_record", lambda mid: {"metadata": {"user_id": "owner"}}
    )
    args = {
        "path": {"memory_id": "memory-1"},
        "query": {"user_id": "other"},
        "body": {"content": "x"},
    }
    value = call(mcp_client, "patch_memory", args)
    rest = mcp_client.patch(
        "/v1/memories/memory-1?user_id=other", json={"content": "x"}
    )
    assert value["isError"]
    assert value["structuredContent"]["status_code"] == rest.status_code == 403
    assert value["structuredContent"]["body"] == rest.json()


def test_operational_endpoint_is_not_omitted(mcp_client, monkeypatch):
    compact = MagicMock(return_value={"deleted": 2})
    monkeypatch.setattr("src.app.run_compaction_for_user", compact)
    value = call(
        mcp_client,
        "compact_single_user",
        {"query": {"user_id": "u", "skip_consolidate": True}},
    )
    assert value["structuredContent"]["body"]["stats"] == {"deleted": 2}
    compact.assert_called_once_with("u", skip_reextract=True, skip_consolidate=True)


def test_lifespan_enters_and_exits_transport(app_module, monkeypatch):
    from contextlib import asynccontextmanager

    events = []

    @asynccontextmanager
    async def run():
        events.append("start")
        try:
            yield
        finally:
            events.append("stop")

    monkeypatch.setattr(app_module.app.state.mcp.session_manager, "run", run)
    with TestClient(app_module.app):
        assert events == ["start"]
    assert events == ["start", "stop"]


def test_official_sdk_client(app_module):
    """Use the SDK client against the ASGI app, without a listening socket."""
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async def exercise():
        async with app_module.app.router.lifespan_context(app_module.app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app)
            ) as client:
                async with streamable_http_client(
                    "http://localhost/mcp", http_client=client
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        assert len((await session.list_tools()).tools) == 43
                        value = await session.call_tool("health", {})
                        assert value.structuredContent["body"]["status"] == "ok"

    anyio.run(exercise)


def test_repeated_app_lifespan(app_module):
    for _ in range(2):
        with TestClient(app_module.app, base_url="http://localhost") as client:
            assert not call(client, "health")["isError"]


def test_retrieve_repeated_query_values(mcp_client, monkeypatch):
    monkeypatch.setattr("src.app._persona_copilot.retrieve", lambda **_: {})
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)
    search = MagicMock(return_value=([], 0))
    monkeypatch.setattr("src.app.search_memories", search)
    args = {
        "query": {"user_id": "alice", "metadata_filter": ["topic:tea", "topic:coffee"]}
    }
    mcp = call(mcp_client, "retrieve", args)
    rest = mcp_client.get(
        "/v1/retrieve",
        params=[
            ("user_id", "alice"),
            ("metadata_filter", "topic:tea"),
            ("metadata_filter", "topic:coffee"),
        ],
    )
    assert mcp["structuredContent"]["status_code"] == rest.status_code
    assert mcp["structuredContent"]["body"] == rest.json()
    assert search.call_count == 2
    assert search.call_args_list[0] == search.call_args_list[1]


def test_backend_unavailable_preserves_rest_error(mcp_client, monkeypatch):
    monkeypatch.setattr("src.routers.memories.get_chroma_client", lambda: None)
    arguments = {
        "path": {"memory_id": "m"},
        "query": {"user_id": "u"},
        "body": {"content": "x"},
    }
    value = call(mcp_client, "patch_memory", arguments)
    assert value["isError"]
    assert value["structuredContent"]["status_code"] == 503
    assert value["structuredContent"]["body"] == {
        "detail": "ChromaDB client unavailable"
    }
