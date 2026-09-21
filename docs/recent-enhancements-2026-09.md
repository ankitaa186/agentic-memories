# Recent enhancements: June 21–September 21, 2026

Reviewed `main` through `47dab51d67efa1699e3bdd9f0a8ff305d96e09df` against the current implementation. The four commits below comprise the local history in this window. A GitHub search found no merged pull requests in the same window. This inventory describes code on `main`, not verified production deployments or tagged releases. Older capabilities such as direct memory writes, TTL support, metadata filters, profiles, and scheduled intents predate this review window.

| Date | Commit | Change |
| --- | --- | --- |
| July 13 | [dfe3383](https://github.com/ankitaa186/agentic-memories/commit/dfe338320dfc24c02766b2519218e9be5773c6e4) | PostgreSQL connection cleanup and pool statistics |
| July 13 | [7bdd5b7](https://github.com/ankitaa186/agentic-memories/commit/7bdd5b70ccd5b1441815421e7d14822668d430a6) | Internal scrum workspace moved to `.scrum/`; no runtime changes |
| August 6 | [d394fe8](https://github.com/ankitaa186/agentic-memories/commit/d394fe8d1c41be33c3e711e27916c44552746c9d) | Options positions and migration 025 |
| September 18 | [47dab51](https://github.com/ankitaa186/agentic-memories/commit/47dab51d67efa1699e3bdd9f0a8ff305d96e09df) | Retrieval relevance, procedural recall, deduplication, API-only update target |

## Subsequent MCP integration

The MCP implementation in this revision is separate from the `main` history inventory above. Agent clients should now start with [MCP at `/mcp`](MCP.md): same process/port as FastAPI, 43 discoverable tools covering every application operation and framework documentation endpoint. REST remains supported. This is an implementation/documentation update, not a claim of production deployment; proxy access controls must also cover `/mcp`.

## Retrieval relevance

Ordinary text queries using hybrid or semantic retrieval, without a time range or emotional context, now sort by measured cosine similarity. Baseline semantic search also calculates cosine from the returned embeddings. The code does not assume that `1 - distance` represents cosine similarity: an existing Chroma collection may use squared L2 distance even if descriptive metadata says cosine.

- Persona tags, recency, importance, and fixed skill relevance no longer promote unrelated matches above stronger text matches. Explicit persona filters still apply.
- SQL-only procedural memories remain searchable: skill text is embedded on demand. The process-local LRU cache holds at most 256 entries and keys on user, skill ID, content, and model. Retrieval still reads current skill records, so deleted skills are not resurrected from cached vectors.
- Invalid/unavailable candidate vectors are skipped instead of receiving an invented relevance score.
- Vector and typed-table copies are deduplicated using normalized string IDs and `typed_table_id` links.
- Explicit temporal/emotional retrieval retains composite scoring. Browse requests remain distinct; baseline filter-only retrieval orders by recency.
- The baseline Redis search namespace is now `cosine-v2`, avoiding reuse of the previous ranking cache.

This scoring update requires no database migration or stored-memory rewrite. It reranks candidates returned by the existing index; it does not rebuild that index or promise exhaustive global cosine search.

**Known scope limitation:** the [orchestrator injection adapter](../src/memory_orchestrator/retrieval.py) still transforms the core search score with `1 - score`. Its injection scores and threshold gating are not covered by the September correction; do not treat them as measured cosine similarity. This documentation review records the mismatch without changing runtime code.

Implementation: [similarity](../src/services/similarity.py), [baseline retrieval](../src/services/retrieval.py), [hybrid retrieval](../src/services/hybrid_retrieval.py), [persona retrieval](../src/services/persona_retrieval.py). Regression coverage: [relevance tests](../tests/unit/test_retrieval_relevance.py).

## Portfolio options

The [portfolio API guide](portfolio-api.md) documents equity/options CRUD, OCC-style identity, immutable contract terms, partial updates, lifecycle close, active/inactive views, and supplied collateral totals. Supported option actions represent long/short puts and calls, including records used for cash-secured puts and covered calls. The API records positions; it does not verify strategy backing or execute trades.

[Migration 025](../migrations/postgres/025_options_support.up.sql) is required. Its rollback deletes option rows. No other commit in this review window adds a database migration.

## Connection reliability and observation

Temporal retrieval and episodic storage now return connections in `finally` blocks. The release helper attempts `putconn()` even if rollback fails, preventing that failure from bypassing pool return.

`GET /health/full` includes `checks.timescale_pool`: the pool's `get_stats()` dictionary, `null` without a pool, or an error object if statistics fail. This is informational and does not affect overall health. Observe pool availability and waiting requests over repeated samples when diagnosing saturation; the endpoint does not itself alert or repair the pool.

Implementation: [Timescale dependency](../src/dependencies/timescale.py), [episodic storage](../src/services/episodic_memory.py), [health endpoint](../src/app.py). Regression coverage: [connection cleanup tests](../tests/unit/test_conn_leak_hotfix.py).

## Update the API container

From a configured checkout:

```bash
make service-update ENV=prod
```

The [Makefile](../Makefile) builds `api`, then runs Compose `up -d --no-deps api`, using the production override when `ENV=prod`. It recreates the API without recreating dependency containers or removing their volumes. It does not run the migration manager; apply required schema migrations separately. Use `ENV=dev` for the base Compose configuration.

For an upgrade that includes options support, review and apply pending migrations with the [migration manager](../migrations/README.md), then update the API and inspect `/health/full`. These instructions do not imply that migrations or container updates were performed during this documentation review.
