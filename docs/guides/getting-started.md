# Getting started

[Documentation](../README.md) / Setup

## Requirements

- Git, Make, Bash, curl, Docker, and Docker Compose v2.
- The PostgreSQL client (`psql`) on your host for the startup migration script.
- An OpenAI API key for embeddings. Use OpenAI for extraction, or additionally configure xAI.
- Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/) if running the Python examples or tests locally.

The databases run in containers. On Ubuntu/Debian, install the host migration client
with `sudo apt install postgresql-client`; on macOS, use `brew install libpq` and follow
Homebrew's instructions to add its binaries to PATH.

## Start the local stack

```bash
git clone https://github.com/ankitaa186/agentic-memories.git
cd agentic-memories
make start
```

With no `.env`, the interactive wizard asks for provider configuration. Alternatively,
copy `env.example` to `.env`, edit it locally, then run `make start`. Never commit your keys.

Startup creates the database services, runs pending migrations when `psql` is available,
initializes Chroma, and builds/starts the API and UI. Read the output: skipped migrations
or an unhealthy dependency must be resolved before continuing.

```bash
curl --fail http://localhost:8080/health/full
```

MCP is at `http://localhost:8080/mcp`; the API reference is at
`http://localhost:8080/docs`; the UI is at `http://localhost:3000`.

## Extract memories from a conversation

```bash
uv sync --locked
uv run python examples/mcp_memory.py
```

The [example](../../examples/README.md) submits a short conversation to the extraction
pipeline, prints the extracted memories, then closes the connection and recalls those
records through a new connection. This uses real LLM, embedding, and storage services.
Records remain available under the printed demo user ID for inspection.

## Connect your application

Add an HTTP / Streamable HTTP MCP server in your client and set its URL to
`http://localhost:8080/mcp`. Initialize the connection and discover tools. A client on
another computer needs your server's reachable address and the [remote access configuration](../MCP.md#access-controls-and-hosting).

Your companion must be configured to submit relevant conversations, retrieve context
for later tasks, and use the returned information in its prompt. The extraction
pipeline decides what memories to create from each submitted conversation. A memory tool connection
is not automatic ingestion of every interaction.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| MCP returns 404 | Verify the running build includes MCP and the URL is `/mcp` |
| Host/origin rejected | Configure the actual hostname and browser origin in the MCP allowlists |
| Memory write reports an embedding error | Check the server's OpenAI configuration and provider availability |
| Missing relation / table | Inspect migration output and apply pending migrations |
| Chroma tenant/database missing | Inspect startup initialization and configured tenant/database |
| Port already in use | Check existing services before starting another Compose stack |

Use `make logs SERVICE=api` and `docker compose ps` to inspect your installation.
Do not delete data directories to resolve a migration error. See [operations](operations.md)
and the [migration guide](../../migrations/README.md).
