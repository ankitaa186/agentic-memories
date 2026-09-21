"""Opt-in real-backend MCP verification against a temporary loopback API.

Set MCP_LIVE_TESTS=1 and configure local TIMESCALE_DSN, REDIS_URL,
CHROMA_HOST/PORT and OPENAI_API_KEY. No production service is restarted.
Only a fresh random user and a disposable Chroma database are written.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import anyio
import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("MCP_LIVE_TESTS") != "1",
    reason="Opt-in test requires live local backends",
)


@contextmanager
def live_api(tmp_path):
    import chromadb
    from chromadb.config import Settings
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict
    from redis import Redis

    assert conninfo_to_dict(os.environ["TIMESCALE_DSN"])["host"] in {
        "127.0.0.1",
        "localhost",
    }
    assert os.environ["CHROMA_HOST"] in {"127.0.0.1", "localhost"}
    assert httpx.URL(os.environ["REDIS_URL"]).host in {"127.0.0.1", "localhost"}
    uid = "mcp_test_" + uuid4().hex
    database = uid
    admin = chromadb.AdminClient(
        Settings(
            chroma_api_impl="chromadb.api.fastapi.FastAPI",
            chroma_server_host=os.environ["CHROMA_HOST"],
            chroma_server_http_port=int(os.environ["CHROMA_PORT"]),
            anonymized_telemetry=False,
        )
    )
    admin.create_database(database, tenant="default_tenant")
    env = dict(
        os.environ,
        CHROMA_DATABASE=database,
        CHROMA_TENANT="default_tenant",
        SCHEDULED_MAINTENANCE_ENABLED="false",
        LANGFUSE_PUBLIC_KEY="",
        LANGFUSE_SECRET_KEY="",
        CF_ACCESS_AUD="",
        CF_ACCESS_TEAM_DOMAIN="",
        ANONYMIZED_TELEMETRY="false",
    )
    # Reserve a free port; both REST and MCP are served by this single process.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log = (tmp_path / "api.log").open("w")
    process = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "src.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        with httpx.Client(timeout=2) as client:
            for _ in range(100):
                if process.poll() is not None:
                    pytest.fail(
                        "Temporary API exited; inspect the private pytest api.log"
                    )
                try:
                    if client.get(base + "/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("Temporary API did not become ready")
        yield base, uid
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log.close()
        # Fixed table whitelist and exact generated user ID; never truncate/flush.
        assert uid.startswith("mcp_test_") and len(uid) == 41
        with psycopg.connect(os.environ["TIMESCALE_DSN"]) as conn:
            for table in ("scheduled_intents", "portfolio_holdings", "user_profiles"):
                conn.execute(
                    sql.SQL("DELETE FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table)
                    ),
                    (uid,),
                )
            for table in ("scheduled_intents", "portfolio_holdings", "user_profiles"):
                count = conn.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table)
                    ),
                    (uid,),
                ).fetchone()[0]
                assert count == 0
        redis = Redis.from_url(os.environ["REDIS_URL"])
        for key in redis.scan_iter(match=f"*{uid}*"):
            redis.delete(key)
        redis.srem("all_users", uid)
        for key in redis.scan_iter(match="recent_users:*"):
            redis.srem(key, uid)
            assert not redis.sismember(key, uid)
        assert not list(redis.scan_iter(match=f"*{uid}*"))
        assert not redis.sismember("all_users", uid)
        redis.close()
        admin.delete_database(database, tenant="default_tenant")
        assert database not in {
            d["name"] for d in admin.list_databases(tenant="default_tenant")
        }


def test_live_mcp_rest_roundtrips(tmp_path):
    async def exercise(base, uid):
        async with httpx.AsyncClient(base_url=base, timeout=90) as rest:
            async with streamable_http_client(base + "/mcp") as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    discovered = (await session.list_tools()).tools
                    inventory = json.loads(
                        Path("docs/mcp-route-mapping.json").read_text()
                    )
                    assert {t.name for t in discovered} == {
                        r["tool"] for r in inventory
                    }
                    openapi = (await rest.get("/openapi.json")).json()
                    paths = {
                        (method.upper(), path)
                        for path, methods in openapi["paths"].items()
                        for method in methods
                    }
                    assert paths == {
                        (r["method"], r["path"]) for r in inventory if r["source"]
                    }
                    schemas = {r["tool"]: r["inputSchema"] for r in inventory}
                    for tool in discovered:
                        assert tool.inputSchema == schemas[tool.name]
                        Draft202012Validator.check_schema(tool.inputSchema)
                        Draft202012Validator.check_schema(tool.outputSchema)

                    async def invoke(name, arguments=None, expected=200):
                        result = await session.call_tool(name, arguments or {})
                        assert result.structuredContent is not None, result.content
                        payload = result.structuredContent
                        assert payload["status_code"] == expected, payload
                        assert result.isError == (expected >= 400), payload
                        return payload["body"]

                    assert (await invoke("health"))["status"] == "ok"
                    assert (await invoke("me")) == (await rest.get("/v1/me")).json()
                    await invoke("retrieve", {}, expected=422)
                    await invoke(
                        "delete_profile",
                        {"query": {"user_id": uid, "confirmation": "wrong"}},
                        expected=400,
                    )
                    await invoke(
                        "get_intent",
                        {"path": {"intent_id": str(uuid4())}},
                        expected=404,
                    )

                    # Real PostgreSQL create -> read -> update -> delete, with REST parity.
                    holding = await invoke(
                        "add_holding",
                        {
                            "body": {
                                "user_id": uid,
                                "ticker": "MCPTEST",
                                "shares": 2,
                                "avg_price": 10,
                            }
                        },
                        expected=201,
                    )
                    assert holding["created"] is True
                    portfolio = await invoke(
                        "get_portfolio", {"query": {"user_id": uid}}
                    )
                    assert (
                        portfolio
                        == (
                            await rest.get("/v1/portfolio", params={"user_id": uid})
                        ).json()
                    )
                    updated = await invoke(
                        "update_holding",
                        {
                            "path": {"position_key": "MCPTEST"},
                            "body": {"user_id": uid, "shares": 3},
                        },
                    )
                    assert updated["shares"] == 3
                    deleted = await invoke(
                        "delete_holding",
                        {
                            "path": {"position_key": "MCPTEST"},
                            "query": {"user_id": uid},
                        },
                    )
                    assert deleted["deleted"] is True
                    await invoke(
                        "delete_holding",
                        {
                            "path": {"position_key": "MCPTEST"},
                            "query": {"user_id": uid},
                        },
                        expected=404,
                    )

                    # Profile PUT creates a field and preserves structured JSON values.
                    profile_args = {
                        "path": {
                            "category": "preferences",
                            "field_name": "mcp_test_color",
                        },
                        "body": {"user_id": uid, "value": "blue"},
                    }
                    await invoke("update_profile_field", profile_args)
                    profile = await invoke("get_profile", {"query": {"user_id": uid}})
                    assert (
                        profile
                        == (
                            await rest.get("/v1/profile", params={"user_id": uid})
                        ).json()
                    )
                    # Observe real Redis population and mutation invalidation.
                    from redis import Redis

                    with Redis.from_url(os.environ["REDIS_URL"]) as redis:
                        await invoke(
                            "get_profile_completeness",
                            {"query": {"user_id": uid, "details": True}},
                        )
                        assert redis.exists(f"profile_completeness:{uid}")
                        profile_args["body"]["value"] = "green"
                        await invoke("update_profile_field", profile_args)
                        assert not redis.exists(f"profile_completeness:{uid}")
                    await invoke(
                        "delete_profile",
                        {"query": {"user_id": uid, "confirmation": "DELETE"}},
                    )

                    # Intent is far in the future and disabled immediately: no notification is sent.
                    intent = await invoke(
                        "create_intent",
                        {
                            "body": {
                                "user_id": uid,
                                "intent_name": "MCP disposable verification",
                                "trigger_type": "once",
                                "trigger_schedule": {
                                    "trigger_at": (
                                        datetime.now(timezone.utc) + timedelta(days=365)
                                    ).isoformat(),
                                    "timezone": "UTC",
                                },
                                "action_context": "Disposable test, never deliver",
                                "action_type": "notify",
                            }
                        },
                        expected=201,
                    )
                    intent_id = intent["id"]
                    disabled = await invoke(
                        "update_intent",
                        {"path": {"intent_id": intent_id}, "body": {"enabled": False}},
                    )
                    assert disabled["enabled"] is False
                    fetched = await invoke(
                        "get_intent", {"path": {"intent_id": intent_id}}
                    )
                    assert (
                        fetched == (await rest.get(f"/v1/intents/{intent_id}")).json()
                    )
                    claimed = await invoke(
                        "claim_intent", {"path": {"intent_id": intent_id}}
                    )
                    assert claimed["intent"]["id"] == intent_id
                    conflict = await invoke(
                        "claim_intent", {"path": {"intent_id": intent_id}}, expected=409
                    )
                    assert (
                        conflict
                        == (await rest.post(f"/v1/intents/{intent_id}/claim")).json()
                    )
                    # This endpoint records an outcome; it does not send a message.
                    fired = await invoke(
                        "fire_intent",
                        {
                            "path": {"intent_id": intent_id},
                            "body": {"status": "gate_blocked"},
                        },
                    )
                    assert fired["status"] == "gate_blocked"
                    history = await invoke(
                        "get_intent_history", {"path": {"intent_id": intent_id}}
                    )
                    assert len(history) == 1 and history[0]["status"] == "gate_blocked"
                    await invoke(
                        "delete_intent",
                        {"path": {"intent_id": intent_id}},
                        expected=204,
                    )
                    await invoke(
                        "get_intent", {"path": {"intent_id": intent_id}}, expected=404
                    )

                    # Real OpenAI embedding, isolated Chroma database and persisted TTL semantics.
                    memory = await invoke(
                        "store_memory_direct",
                        {
                            "body": {
                                "user_id": uid,
                                "content": "Disposable MCP test: I prefer blue notebooks.",
                                "layer": "semantic",
                                "type": "explicit",
                                "ttl_seconds": 3600,
                            }
                        },
                    )
                    assert memory["status"] == "success", memory
                    memory_id = memory["memory_id"]
                    args = {
                        "path": {"memory_id": memory_id},
                        "query": {"user_id": uid},
                        "body": {
                            "content": "Disposable MCP test: I prefer green notebooks.",
                            "ttl_seconds": None,
                        },
                    }
                    patched = await invoke("patch_memory", args)
                    assert patched["chroma_updated"] is True
                    assert patched["embedding_regenerated"] is True
                    import chromadb

                    chroma = chromadb.HttpClient(
                        host=os.environ["CHROMA_HOST"],
                        port=int(os.environ["CHROMA_PORT"]),
                        tenant="default_tenant",
                        database=uid,
                    )
                    collection = chroma.get_collection(
                        chroma.list_collections()[0].name
                    )
                    assert (
                        "ttl_epoch"
                        not in collection.get(ids=[memory_id])["metadatas"][0]
                    )

                    other = {
                        "path": {"memory_id": memory_id},
                        "query": {"user_id": uid + "_other"},
                        "body": {"importance": 0.9},
                    }
                    error = await invoke("patch_memory", other, expected=403)
                    assert (
                        error
                        == (
                            await rest.patch(
                                f"/v1/memories/{memory_id}",
                                params=other["query"],
                                json=other["body"],
                            )
                        ).json()
                    )
                    denied = await invoke(
                        "delete_memory",
                        {"path": {"memory_id": memory_id}, "query": other["query"]},
                        expected=403,
                    )
                    assert (
                        denied
                        == (
                            await rest.delete(
                                f"/v1/memories/{memory_id}", params=other["query"]
                            )
                        ).json()
                    )
                    recalled = await invoke(
                        "retrieve",
                        {
                            "query": {
                                "user_id": uid,
                                "query": "green notebooks",
                                "limit": 5,
                            }
                        },
                    )
                    assert any(
                        item["id"] == memory_id and "green notebooks" in item["content"]
                        for item in recalled["results"]
                    ), recalled
                    removed = await invoke(
                        "delete_memory",
                        {"path": {"memory_id": memory_id}, "query": {"user_id": uid}},
                    )
                    assert removed["deleted"] is True
                    await invoke("patch_memory", args, expected=404)
                    assert not (await invoke("retrieve", {"query": {"user_id": uid}}))[
                        "results"
                    ]
        # Exiting the official client and the server fixture verifies transport shutdown.

    with live_api(tmp_path) as (base, uid):
        anyio.run(exercise, base, uid)
