# Conversation extraction through MCP

The main example demonstrates Agentic Memories' extraction pipeline: the caller submits
conversation turns, and the service produces the memory records.

[Set up the service](../docs/guides/getting-started.md), then run from the repository root:

```bash
uv sync --locked
uv run python examples/mcp_memory.py
```

It submits a short personal conversation through `store_transcript`, prints the actual
extracted memories and their layers, closes the connection, then opens a new connection
and semantically retrieves those records. It checks that retrieved IDs belong to the
extraction result rather than expecting a fixed LLM paraphrase.

## What the pipeline does

Worthiness assessment → extraction → classification/enrichment → embeddings and duplicate
checks → profile extraction and storage → applicable memory stores.

The demo uses real LLM, embedding, and storage services. The API server supplies provider
credentials. Extraction can take several model calls; the example allows five minutes
for an HTTP response. Wording, classification, and memory count depend on the configured
model. Empty extraction is reported as a failure of this demonstration, not silently
replaced by a direct write. Reusing a user with the same conversation can invoke deduplication.

The script prints retrieved memory content, not a generated companion response. Your
companion would include the returned context in its next model prompt.

## Demo data

The default user ID is unique to each run and printed at startup. Extracted memories and
any derived profile/typed records remain for inspection. This script does not claim to
clean up all extraction side effects or apply a fallback TTL to extracted memories.
Use a dedicated test scope or disposable local environment.

Use `--user-id <dedicated-demo-user>` to choose the scope, or `--url http://localhost:8080/mcp`
to select the endpoint. Remote authentication may require adapting the client as described
in the [MCP guide](../docs/MCP.md).

## Recorded output

[The transcript](mcp-memory-output.txt) captures a real pipeline run. Its extracted content
is model output derived from the fixed sample conversation, not manually supplied records.
The verification run used a temporary API, disposable Chroma database, and unique user;
its separate harness removed typed/profile rows and Redis state afterward. That cleanup
is verification infrastructure, not behavior of the example script.

## Advanced: direct-write example

```bash
uv run python examples/mcp_direct_memory.py
```

Use this path when your application already has a preformatted memory, for example during
an import. It bypasses extraction, writes one known preference, reconnects to retrieve it,
and deletes that record in a `finally` block. A one-hour TTL is a fallback for interruption.
[Recorded direct-write output](mcp-direct-memory-output.txt).
