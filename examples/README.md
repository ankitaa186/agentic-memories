# Cross-session MCP example

[Set up the service](../docs/guides/getting-started.md), then run from the repository root:

```bash
uv sync --locked
uv run python examples/mcp_memory.py
```

The example stores a personal preference through `store_memory_direct`, closes that MCP
connection, opens a new connection, and retrieves the preference using a semantic query.
It checks the returned ID and content. Finally, it deletes its memory and verifies that
no memories remain for its unique demo user.

It uses real storage and embedding calls. The API server supplies provider credentials;
you do not put keys in the example. A one-hour TTL is set as fallback for interrupted
runs; TTL cleanup is asynchronous. Cleanup failures cause a nonzero exit rather than a
false success message.

Use `--url http://localhost:8080/mcp` to select a different local endpoint. Remote
authenticated deployments may require adapting the client as described in the [MCP guide](../docs/MCP.md).

The demo prints retrieved content, not an LLM-generated answer. A production agent would
include the returned context in its model prompt. Transcript extraction is a separate
path and is not exercised here.

## Recorded output

[The transcript](mcp-memory-output.txt) was captured from a real run of this script.
The [demo graphic](../docs/assets/mcp-demo.svg) summarizes that run. Unique record IDs
are deliberately not printed; all displayed memory content is the fixed example text.
