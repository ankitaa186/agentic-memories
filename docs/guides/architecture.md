# Current architecture

[Documentation](../README.md) / Architecture

![Clients, shared application, and backing stores.](../assets/architecture.svg)

## One application, two interfaces

FastAPI serves REST and the Streamable HTTP MCP endpoint at `/mcp` in the same process
and on the same port. The MCP adapter derives tool schemas from registered routes and
invokes the shared ASGI request pipeline in-process. It does not make a network request
back to the REST server. Validation, middleware, responses, and service behavior remain shared.

The MCP session manager is started and stopped by the application's lifespan. Discovery
includes application operations and framework documentation routes; the [inventory](../mcp-route-mapping.json)
is maintained by `scripts/export_mcp_inventory.py`.

## Storage and processing

| Component | Role |
| --- | --- |
| ChromaDB | Memory documents, metadata, vectors, and semantic search |
| PostgreSQL with TimescaleDB | Structured profiles, portfolios, intents, and typed/time-based records |
| Redis | Caching, coordination, and transient state |
| LLM and embedding providers | Conversation extraction, embeddings, and configured generation paths |
| LangGraph | Ingestion and maintenance orchestration |
| Optional Langfuse | LLM tracing and observability |

The main ingestion path evaluates conversation worthiness, extracts and classifies
memories, enriches and embeds them, checks for duplicates, derives profile fields, and
stores the results. Direct writes are an advanced path for known content that bypasses
conversation extraction. Retrieval searches the relevant stores and returns context;
the calling agent decides how to use it. Some operations span multiple stores, so callers
must inspect operation-level status as well as transport success.

## Boundaries

The public MCP endpoint includes maintenance and destructive operations. Host/origin
allowlists protect transport boundaries; they are not authentication. Global identity-based
authorization is not currently enforced by the API. See [deployment guidance](operations.md).

This diagram shows the implemented stack. A knowledge graph/Neo4j layer and broader
enterprise permission models belong to the [roadmap](../ROADMAP.md), not the current diagram.
The older [architecture proposal](../architecture.md) remains a historical design record.
