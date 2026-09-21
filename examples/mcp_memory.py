"""Store and recall one personal preference across separate MCP connections.

Run against a local stack: uv run python examples/mcp_memory.py
Uses real embeddings; removes its own record and sets a fallback one-hour TTL.
"""

import argparse
import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

PREFERENCE = "Evening walks help me unwind. I prefer quiet routes near the water."


@asynccontextmanager
async def connect(url):
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client


async def call(client, tool, arguments):
    result = await client.call_tool(tool, arguments)
    envelope = result.structuredContent
    if result.isError or not isinstance(envelope, dict):
        raise RuntimeError(f"{tool} failed: {envelope or result.content}")
    body = envelope.get("body")
    if envelope.get("status_code", 500) >= 400 or (
        isinstance(body, dict) and body.get("status") == "error"
    ):
        raise RuntimeError(f"{tool} failed: {body}")
    return body


async def demo(url):
    user_id = f"readme_demo_{uuid.uuid4().hex}"
    memory_id = None
    try:
        async with connect(url) as client:
            print("SESSION 1 / store_memory_direct")
            stored = await call(
                client,
                "store_memory_direct",
                {
                    "body": {
                        "user_id": user_id,
                        "content": PREFERENCE,
                        "layer": "semantic",
                        "type": "explicit",
                        "ttl_seconds": 3600,
                    }
                },
            )
            memory_id = stored.get("memory_id")
            if not memory_id or not stored.get("storage", {}).get("chromadb"):
                raise RuntimeError(f"Memory was not persisted: {stored}")
            print(f"Stored: {PREFERENCE}")
        print("Connection closed. Opening a new MCP connection.\n")

        async with connect(url) as client:
            print("SESSION 2 / retrieve")
            print("Query: How do I like to unwind?")
            recalled = await call(
                client,
                "retrieve",
                {
                    "query": {
                        "user_id": user_id,
                        "query": "How do I like to unwind?",
                        "limit": 5,
                    }
                },
            )
            match = next(
                (item for item in recalled["results"] if item["id"] == memory_id),
                None,
            )
            if not match or match["content"] != PREFERENCE:
                raise RuntimeError("The new connection did not recall the demo memory")
            print(f"Recalled: {match['content']}")
            print("PASS: the same preference was recalled through a new connection.")
    finally:
        if memory_id:
            async with connect(url) as client:
                removed = await call(
                    client,
                    "delete_memory",
                    {"path": {"memory_id": memory_id}, "query": {"user_id": user_id}},
                )
                if not removed.get("deleted"):
                    raise RuntimeError(f"Demo cleanup failed: {json.dumps(removed)}")
                remaining = await call(
                    client, "retrieve", {"query": {"user_id": user_id}}
                )
                if remaining["results"]:
                    raise RuntimeError("Demo records remain after cleanup")
                print("CLEANUP: demo memory deleted; no demo memories remain.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080/mcp")
    asyncio.run(demo(parser.parse_args().url))
