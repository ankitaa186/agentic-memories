# MCP interface (preferred agent integration)

**MCP is the preferred integration for agents; direct REST remains a supported alternative.**

[Documentation](README.md) · [Setup](guides/getting-started.md) · [Cross-session example](../examples/README.md)

Deploy a build containing the MCP interface before configuring clients. Your deployment
revision determines availability; source documentation is not a deployment record.

The existing FastAPI process serves Streamable HTTP at **`http://localhost:8080/mcp`** (substitute the existing server's host/port). Start the API with its normal configuration and command. There is no additional process or listening port. `uv sync --locked` installs the SDK; Docker uses the regenerated `requirements.txt`.

## Start with conversation extraction

For a personal companion, use `store_transcript` to submit conversation turns. The
pipeline evaluates worthiness, extracts and organizes memories, checks for duplicates,
and builds profile context where applicable. Then use `retrieve` to recall useful context.
[Run the extraction example](../examples/README.md) or read [the pipeline guide](guides/memory.md#conversation-extraction).

`store_memory_direct` is an advanced bypass for applications that already produce
memory records; it does not exercise conversation extraction.

## Connect and use

Configure an MCP client's **Streamable HTTP / HTTP** server URL as `http://localhost:8080/mcp`. This is not a stdio or legacy SSE endpoint. No trailing slash is needed. The transport accepts JSON responses; clients must send `Accept: application/json, text/event-stream` and `Content-Type: application/json`. The official SDK handles initialization and protocol headers:

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("http://localhost:8080/mcp") as (read, write, _):
        async with ClientSession(read, write) as client:
            await client.initialize()
            print([tool.name for tool in (await client.list_tools()).tools])
            result = await client.call_tool("retrieve", {
                "query": {"user_id": "alice", "query": "preferences", "limit": 5}
            })
            print(result.structuredContent)

asyncio.run(main())
```

For credentials, create an `httpx.AsyncClient(headers={"Authorization": "Bearer ..."})` and pass it as `http_client=` to `streamable_http_client`. Cloudflare assertion headers and cookies are also forwarded per request. Never put credentials into tool arguments.

Arguments follow the REST contract: `path` holds URL placeholders, `query` holds query parameters, and `body` is the JSON request body. Discovery includes nested model schemas, enums, defaults, bounds, descriptions and required fields. Omit optional arguments to retain server defaults. Explicit JSON null remains null in bodies (important for PATCH); null query arguments are omitted. Arrays in query parameters become repeated keys.

Examples of calls:

```json
{"name":"store_transcript","arguments":{"body":{"user_id":"alice","history":[{"role":"user","content":"I prefer tea"}]}}}
{"name":"patch_memory","arguments":{"path":{"memory_id":"memory-id"},"query":{"user_id":"alice"},"body":{"importance":0.8}}}
{"name":"delete_intent","arguments":{"path":{"intent_id":"b476792f-c710-447b-82d3-58a8d8bbc820"}}}
{"name":"compact_single_user","arguments":{"query":{"user_id":"alice","skip_reextract":true}}}
```

## Results, errors and mutation semantics

Every call returns the same envelope in both `structuredContent` and JSON text content:

```json
{"status_code":200,"body":{"status":"ok"},"content_type":"application/json"}
```

The body is the existing REST response after FastAPI serialization. Lists remain lists inside `body`; a 204 response has `body: null`; documentation HTML remains a string. HTTP errors set MCP `isError: true` and retain the REST status and error body. Unknown tools return 404. Tool-schema errors return 422 with locations and messages; REST model validators still run and retain their original errors. A REST 200 response that reports a domain failure inside its body stays a 200 MCP result: callers must inspect that body just as REST callers do.

Reads are annotated read-only. Write, delete, claim, ingestion and maintenance tools are conservatively marked potentially destructive and non-idempotent. No automatic retry occurs in the adapter. Confirmation flags such as portfolio/profile deletion parameters remain required by the underlying route. Disconnection does not guarantee rollback of a mutation already started. Tool annotations are client hints, not an authorization mechanism.

The orchestrator routes named `stream_*` actually return bounded JSON response models in this API; MCP returns those models as one tool result. This transport is stateless: it does not issue session IDs, persist credentials, provide resumable events, or open a server event stream. GET and DELETE on `/mcp` return 405; all protocol messages use POST. REST DELETE operations remain available as MCP tools. Framework-generated HEAD aliases and CORS OPTIONS/preflight are HTTP mechanics, not separate tools. All four framework GET documentation endpoints are exposed. `/mcp` itself is not recursively exposed as a tool.

Path arguments must be single literal segments: dot traversal, slash, backslash, percent, question mark and fragment marker are rejected with 422 so arguments cannot select another route. Normal IDs and option position keys are supported. The existing REST URLs remain available for unusual legacy identifiers containing those characters.

## Access controls and hosting

The adapter invokes the same FastAPI ASGI pipeline in-process. This preserves route dependencies, middleware, threadpool execution, business/service code, user-ID checks, response models and exception handlers without duplicating logic or making a loopback network request. Caller headers and cookies are forwarded, apart from HTTP framing and MCP transport headers. Each call has its own HTTP client, so credentials cannot leak between callers.

The current API does **not** enforce global authentication. `/v1/me` optionally verifies Cloudflare Access identity and treats missing/invalid credentials as anonymous. Other routes retain explicit user-ID scoping and existing ownership checks (for example memory PATCH/DELETE), rather than binding user IDs to that optional identity. Intent-by-ID and administrative maintenance routes retain their existing access semantics. MCP does not add a new identity policy or OAuth authorization server.

**Apply the same external access controls to `/mcp` as to the REST API, including administrative operations.** A proxy that only protects `/v1/*` does not protect `/mcp`. Per-URL proxy roles must be enforced at the MCP endpoint or in shared application authorization; a proxy cannot infer a tool's REST destination from the MCP URL. This matters especially for `compact_all_users`, intent claim/fire, and destructive deletion tools. The interface intentionally does not silently hide them.

DNS-rebinding protection permits loopback hosts/origins by default. For remote access explicitly configure comma-separated allowlists, for example:

```dotenv
MCP_ALLOWED_HOSTS=memories.example.com,memories.example.com:443
MCP_ALLOWED_ORIGINS=https://memories.example.com
```

Use actual API hostnames for hosts and actual browser origins for origins. Existing FastAPI CORS rules still apply, so browser clients must also have an allowed UI origin (such as `UI_ORIGIN`). Non-browser MCP clients normally omit Origin. Do not disable proxy authentication when configuring host allowlists: host checks are not authentication.

## Coverage and implementation

All **39 application operations and 4 framework documentation endpoints** are mapped below. The machine-readable [route inventory](mcp-route-mapping.json) also captures parameters (including transport-owned auth parameters), body and response references, self-contained tool input schemas, annotations, source files and additional explicit handler/helper status codes. Response `$ref` entries resolve against `/openapi.json`; application errors not declared in OpenAPI still pass through unchanged, including 400 validation/business errors, 403 ownership denial, 404 absence, 409 claim conflicts, 422 input errors, and 500/503 backend failures. Handler status inventory is static, not an exhaustive list of downstream service exceptions.

Regenerate after route/model changes with `uv run python -m scripts.export_mcp_inventory`. Discovery is generated at app construction, after REST registration, and the coverage test checks the mapping against all registered FastAPI operations. Add new routers before `install_mcp(app)`.

| Method | REST path | MCP tool |
|---|---|---|
| GET | `/v1/profile` | `get_profile` |
| DELETE | `/v1/profile` | `delete_profile` |
| GET | `/v1/profile/completeness` | `get_profile_completeness` |
| GET | `/v1/profile/{category}` | `get_profile_category` |
| PUT | `/v1/profile/{category}/{field_name}` | `update_profile_field` |
| DELETE | `/v1/profile/{category}/{field_name}` | `delete_profile_field` |
| GET | `/v1/portfolio` | `get_portfolio` |
| DELETE | `/v1/portfolio` | `clear_portfolio` |
| POST | `/v1/portfolio/holding` | `add_holding` |
| PUT | `/v1/portfolio/holding/{position_key}` | `update_holding` |
| DELETE | `/v1/portfolio/holding/{position_key}` | `delete_holding` |
| POST | `/v1/intents` | `create_intent` |
| GET | `/v1/intents` | `list_intents` |
| GET | `/v1/intents/pending` | `get_pending_intents` |
| POST | `/v1/intents/{intent_id}/fire` | `fire_intent` |
| POST | `/v1/intents/{intent_id}/claim` | `claim_intent` |
| GET | `/v1/intents/{intent_id}/history` | `get_intent_history` |
| GET | `/v1/intents/{intent_id}` | `get_intent` |
| PUT | `/v1/intents/{intent_id}` | `update_intent` |
| DELETE | `/v1/intents/{intent_id}` | `delete_intent` |
| POST | `/v1/memories/direct` | `store_memory_direct` |
| PATCH | `/v1/memories/{memory_id}` | `patch_memory` |
| DELETE | `/v1/memories/{memory_id}` | `delete_memory` |
| POST | `/v1/orchestrator/message` | `stream_orchestrator_message` |
| POST | `/v1/orchestrator/retrieve` | `fetch_orchestrator_memories` |
| POST | `/v1/orchestrator/transcript` | `stream_orchestrator_transcript` |
| GET | `/health` | `health` |
| GET | `/v1/me` | `me` |
| GET | `/health/full` | `health_full` |
| POST | `/v1/store` | `store_transcript` |
| GET | `/v1/retrieve` | `retrieve` |
| POST | `/v1/retrieve` | `retrieve_persona` |
| POST | `/v1/retrieve/structured` | `retrieve_structured` |
| POST | `/v1/narrative` | `narrative` |
| POST | `/v1/forget` | `forget` |
| POST | `/v1/maintenance` | `maintenance` |
| GET | `/v1/portfolio/summary` | `portfolio_summary` |
| POST | `/v1/maintenance/compact_all` | `compact_all_users` |
| POST | `/v1/maintenance/compact` | `compact_single_user` |
| GET | `/openapi.json` | `get_openapi` |
| GET | `/docs` | `get_docs` |
| GET | `/redoc` | `get_redoc` |
| GET | `/docs/oauth2-redirect` | `get_docs_oauth2_redirect` |

## SDK compatibility and verification

The results below are a historical verification snapshot for the MCP implementation.
See the report for scope and rerun checks for your selected revision.

This change uses the official Python SDK's maintained v1 line (`mcp>=1.28,<2`, locked to **1.30.0**). v2 is the current stable line, but v1 continues receiving critical/security fixes; retaining v1 avoids introducing the v2 HTTP client/transport migration into this older API stack. This is an explicit compatibility choice, not a claim that v1 is the latest major version. See the [official release guidance](https://pypi.org/project/mcp/), [v1 dependency metadata](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/pyproject.toml), and [official stateless embedding example](https://github.com/modelcontextprotocol/python-sdk/blob/v1.26.0/examples/servers/simple-streamablehttp-stateless/mcp_simple_streamablehttp_stateless/server.py).

Python remains 3.12, FastAPI 0.111.0 and Starlette 0.37.2. HTTPX increases from 0.27.0 to 0.27.2, Uvicorn from 0.30.1 to 0.31.1, and SSE-Starlette is constrained to 2.1.3 for this stack. `uv.lock` and Docker requirements are synchronized. MCP's session manager runs inside the existing FastAPI lifespan; orchestrator shutdown remains in a finally block.

Run protocol and REST regression checks:

```bash
uv run pytest tests/unit tests/integration/test_intents_api.py tests/test_orchestrator_api.py tests/memory_orchestrator
uv run ruff check src/mcp_interface.py tests/unit/test_mcp_interface.py scripts/export_mcp_inventory.py src/app.py
```

The MCP tests exercise discovery/coverage, SDK client interoperability, schema validation, host/origin restrictions, per-call identity, ingestion, deletion/204/404, memory ownership, operational calls and lifespan. MCP tests use mocked backend services; a live Chroma/Postgres/Redis/LLM deployment is not needed for these checks.

Verified on Python 3.12.3: **840 regression tests passed**, with one existing database-dependent skip. The focused MCP suite contains 12 passing tests. A separate **live backend test passed** against a temporary loopback Uvicorn process sharing one port for MCP and REST, using PostgreSQL, ChromaDB, Redis and real OpenAI embeddings. It covered portfolio/profile/intent CRUD, intent claim conflicts and execution history, memory create/patch/semantic retrieval/delete, ownership errors, null-TTL persistence and Redis cache invalidation. Disposable records, cache entries and the Chroma database were removed.

See [the verification report](MCP-verification.md) for exact commands, coverage and remaining gaps. No existing API service was restarted or deployed. The README, integration guides and project description lead with MCP; historical deferred-MCP plans are explicitly identified as historical. The earlier documentation refresh is retained, including portfolio options, schema and recent-enhancement guidance.
