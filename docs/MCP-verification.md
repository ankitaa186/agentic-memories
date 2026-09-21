# MCP verification — September 21, 2026

The implementation and combined documentation were verified in the isolated `feat/complete-mcp-interface` worktree. This report describes local verification, not a production deployment. Client setup and the complete mapping are in [MCP.md](MCP.md).

## Results

| Check | Result |
|---|---|
| Selected regression suite | **840 passed, 1 skipped** in 28.14 seconds |
| Focused MCP tests, included above | **12 passed** |
| Opt-in live backend scenario | **1 passed** in 6.83 seconds |
| Discovery and route inventory | All **39 application operations + 4 documentation endpoints**; exact tool/input-schema parity |
| Documentation examples | Four MCP Python examples parsed; six literal tool calls validated against discovery schemas |
| Documentation mapping | All 43 Markdown mapping rows match the JSON inventory |
| Links | Added local Markdown links and anchors validated |
| Dependencies | Lock check, installed-package compatibility, and requirements export parity passed |
| Code hygiene | Ruff and `git diff --check` passed for changed code/files |

The regression command was:

```bash
uv run pytest tests/unit tests/integration/test_intents_api.py tests/test_orchestrator_api.py tests/memory_orchestrator -q --disable-warnings
```

The skipped case is the pre-existing `tests/unit/test_profile_api.py` test marked as requiring an actual database. Existing Pydantic/deprecation warnings remain. The separate live scenario below exercises actual database-backed profile behavior.

## Protocol and regression coverage

[Protocol tests](../tests/unit/test_mcp_interface.py) exercise initialization, notification handling, discovery, schema validation, unknown tools, bad inputs, malformed JSON, host/origin restrictions, and the official SDK client. Tests compare credentials/identity across calls, ingestion behavior, repeated query parameters, ownership denials, unavailable backends, 204/404 handling, operational calls and repeated application lifespans. Valid Cloudflare token handling is tested with a mocked verifier, including per-call isolation; it is not a live identity-provider test.

[The inventory exporter](../scripts/export_mcp_inventory.py) reproduces [mcp-route-mapping.json](mcp-route-mapping.json) exactly. Framework-generated HEAD and CORS OPTIONS requests are transport mechanics rather than separate tools; `/mcp` is not recursively exposed. The MCP documentation explains these choices.

## Live local verification

[The opt-in live test](../tests/live/test_mcp_live.py) starts **one temporary Uvicorn process on a free loopback port**, then accesses REST and `/mcp` on that same port. It leaves the existing API on port 8080 running unchanged. No handler, storage service or embedding provider is mocked in this scenario.

It uses local PostgreSQL, ChromaDB and Redis, a random `mcp_test_<uuid>` user, a disposable Chroma database, and real OpenAI embeddings. Maintenance scheduling and external tracing are disabled in the temporary process. The intent is scheduled a year ahead and then disabled; reporting a `gate_blocked` execution result does not send a notification.

Verified flows:

- Official SDK initialization/discovery and exact parity with the live OpenAPI operations and stored tool schemas.
- PostgreSQL portfolio create (201), REST/MCP read parity, update, deletion and missing-record 404.
- Profile field creation/update, read parity, Redis completeness cache population/invalidation, confirmation rejection, and confirmed deletion for the disposable user.
- Intent create/read/update/delete, claim success, repeat-claim 409 parity, execution reporting/history, empty 204 and subsequent 404.
- Memory create with a real embedding, content update with embedding regeneration, semantic retrieval of the changed content, deletion and subsequent absence.
- Explicit null TTL removes `ttl_epoch` from the stored Chroma metadata.
- Cross-user memory PATCH/DELETE rejection matches REST's 403 response.
- Application startup, official client shutdown, process shutdown and cleanup.

Cleanup uses exact generated user IDs and a fixed table whitelist. It deletes the disposable database, checks PostgreSQL rows are absent, removes only that user's Redis keys/activity-set membership, and checks removal. Existing user data and running containers are not replaced or cleared. Configuration values and credentials are not committed or printed.

To rerun, export valid local `TIMESCALE_DSN`, `REDIS_URL`, `CHROMA_HOST`, `CHROMA_PORT`, `OPENAI_API_KEY` and `LLM_PROVIDER` configuration through your normal secret-management workflow. PostgreSQL and Chroma must have the existing application schema and default tenant respectively; the configured database role must be able to create/delete the disposable user's rows. Then run:

```bash
MCP_LIVE_TESTS=1 uv run pytest tests/live/test_mcp_live.py -q --disable-warnings
```

The test refuses non-loopback database/cache/Chroma hosts and skips unless explicitly enabled. It makes real embedding API calls and creates temporary test records.

## Remaining gaps

- No production deployment, Cloudflare proxy/browser-CORS deployment check, or valid live Cloudflare identity-token round trip was performed. Protect `/mcp` with appropriate proxy access controls before exposing it remotely.
- Full LLM transcript extraction, narrative generation and every operational tool were not executed against live data. Their routing/schemas are covered and representative service behavior has mocked regression coverage. Global destructive/admin operations such as `compact_all_users` were deliberately not run on existing data.
- No load/soak test or exhaustive multi-worker stress test was performed. The live claim-conflict check verifies sequential conflict behavior, not concurrent-worker throughput.
- This is the maintained MCP v1 SDK integration, locked to 1.30.0; it does not claim MCP SDK v2 feature coverage.


## Follow-up: conversation extraction example (September 21, 2026)

The [main example](../examples/mcp_memory.py) was run against a temporary local API with
real configured LLM extraction, OpenAI embeddings, PostgreSQL, ChromaDB, and Redis.
Four conversation turns produced six classified memories; a new MCP connection
retrieved all six extracted IDs. [The captured output](../examples/mcp-memory-output.txt)
contains actual model-generated memory content, not a fallback direct write.

The verification harness used a disposable Chroma database and exact generated test-user
scope. It removed episodic/emotional/procedural rows, profile rows, and Redis state,
then deleted the disposable database. The public example intentionally retains its
records for inspection; harness cleanup is not a promise made by the script.

This verifies one natural-conversation extraction/recall scenario. It is not an extraction
quality benchmark, a guarantee of identical model output, or exhaustive proof that every
pipeline side effect succeeds. The original report's full-extraction gap is narrowed by
this follow-up; narrative generation, broader conversation coverage, load testing, and
live identity/proxy validation still require separate work.
