# Deployment and upgrades

[Documentation](../README.md) / Operations

## Local and production configuration

Start with [env.example](../../env.example). Embeddings currently require OpenAI;
extraction can use OpenAI or xAI. Optional tracing sends data to the configured tracing
service. Account for those data flows when choosing a deployment.

`make start` uses the configured environment. `ENV=prod` enables the production Compose
override, including Loki logging requirements. See the production configuration and
[alerting guide](../operations/ALERTING.md) before selecting that mode.

## Remote access

Protect **both `/mcp` and the REST routes** with your external access controls. The
application does not enforce global authentication, and supplied user IDs are not a
complete authorization system. MCP includes administrative tools; a proxy policy on
`/v1/*` alone does not constrain a tool call delivered through `/mcp`.

For a real deployment, replace these example domains with your own:

```dotenv
MCP_ALLOWED_HOSTS=memories.example.com,memories.example.com:443
MCP_ALLOWED_ORIGINS=https://memories.example.com
```

Browser clients also need an allowed FastAPI CORS origin. Configure transport allowlists
and access control separately. See [MCP hosting](../MCP.md#access-controls-and-hosting).

## Upgrade deliberately

1. Read [CHANGELOG.md](../../CHANGELOG.md) and the release's migration notes.
2. Back up the persistent stores and confirm your recovery procedure.
3. Check out the reviewed release or commit and install its locked dependencies if needed.
4. Inspect and apply pending migrations with the [migration tools](../../migrations/README.md).
   Options support requires migration 025; do not assume an API rebuild applies migrations.
5. Rebuild only the API when the change does not require other services to change:

   ```bash
   make service-update ENV=prod
   ```

6. Verify `/health/full`, MCP initialization/discovery, and representative read/write flows.

The API-only update target preserves the running database/UI containers. It does not
upgrade their schemas or guarantee that an older image can use the new schema. An image
rollback and a schema rollback require separate compatibility checks.

## Health and diagnostics

```bash
curl --fail http://localhost:8080/health/full
make logs SERVICE=api
docker compose ps
```

`checks.timescale_pool` exposes connection-pool statistics when available. For MCP,
use the [example](../../examples/README.md) or the [verification suite](../MCP-verification.md).
The example performs a small real write and embedding calls, then removes its record.

## Releases and deployments

A GitHub release identifies a source version; it does not mean your server has been
upgraded. Maintain your own deployed commit/image record and post-deployment checks.
See [release preparation](../releases/README.md) for the repository's publishing process.
