"""Extract personal memories from conversation, then recall through a new MCP connection.

Uses real LLM and embedding requests. Extracted records remain for inspection.
Use a dedicated demo user; the output identifies that user's scope.
"""

import argparse
import asyncio
import uuid
from contextlib import asynccontextmanager

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

HISTORY = [
    {"role": "assistant", "content": "What helps you unwind after a busy day?"},
    {
        "role": "user",
        "content": (
            "Evening walks help me unwind. I usually take a quiet route by the water "
            "rather than a busy street. I have kept that habit for years."
        ),
    },
    {"role": "assistant", "content": "What do you enjoy doing when you get home?"},
    {
        "role": "user",
        "content": "I like making herbal tea and reading a novel. I avoid coffee in the evening.",
    },
]


@asynccontextmanager
async def connect(url):
    # Extraction can involve several provider calls; allow a bounded five minutes.
    async with httpx.AsyncClient(timeout=300) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as client:
                await client.initialize()
                yield client


async def call(client, tool, arguments):
    result = await client.call_tool(tool, arguments)
    envelope = result.structuredContent
    if result.isError or not isinstance(envelope, dict):
        raise RuntimeError(f"{tool} failed: {envelope or result.content}")
    if envelope.get("status_code", 500) >= 400:
        raise RuntimeError(f"{tool} failed: {envelope}")
    return envelope["body"]


async def demo(url, user_id):
    print(f"Demo user: {user_id}")
    print("SESSION 1 / store_transcript")
    for message in HISTORY:
        print(f"{message['role']}: {message['content']}")
    async with connect(url) as client:
        stored = await call(
            client,
            "store_transcript",
            {"body": {"user_id": user_id, "history": HISTORY}},
        )
        memories = stored.get("memories") or []
        ids = set(stored.get("ids") or [])
        if not ids or not memories:
            raise RuntimeError(
                "No new memories extracted. Worthiness, deduplication, and model "
                "output can change the result; inspect the pipeline before retrying."
            )
        print(f"\nEXTRACTION: {len(ids)} memories returned by the pipeline.")
        for memory in memories:
            print(f"EXTRACTED [{memory['layer']}]: {memory['content']}")
    print("\nConnection closed. Opening a new MCP connection.")
    async with connect(url) as client:
        print("SESSION 2 / retrieve")
        print("Query: How do I like to unwind in the evening?")
        recalled = await call(
            client,
            "retrieve",
            {
                "query": {
                    "user_id": user_id,
                    "query": "How do I like to unwind in the evening?",
                    "limit": 10,
                }
            },
        )
        matches = [item for item in recalled["results"] if item["id"] in ids]
        if not matches:
            raise RuntimeError(
                "The new connection did not recall any extracted memories"
            )
        for item in matches:
            print(f"RECALLED [{item['layer']}]: {item['content']}")
        print("PASS: recalled pipeline-extracted memories through a new connection.")
    print(
        "Demo records remain for inspection; this script does not delete extracted data."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080/mcp")
    parser.add_argument("--user-id", default=f"readme_extraction_{uuid.uuid4().hex}")
    arguments = parser.parse_args()
    asyncio.run(demo(arguments.url, arguments.user_id))
