# Documentation

Agentic Memories provides biomimetic memory for personal AI companions. Start with MCP
to extract experiences and preferences from conversations, using self-hosted storage.
REST is a supported alternative.

## Start here

1. [Set up the service](guides/getting-started.md).
2. [Run the cross-session memory example](../examples/README.md).
3. [Connect an MCP client](MCP.md).
4. [Understand memory and retention](guides/memory.md).

## Integration and reference

| Guide | Use it for |
| --- | --- |
| [MCP](MCP.md) | Transport, credentials, tools, inputs, and errors |
| [Tool inventory](mcp-route-mapping.json) | Machine-readable route mapping and input schemas |
| [REST API](api-contracts-server.md) | HTTP contracts; live `/docs` and `/openapi.json` expose current schemas |
| [Portfolio](portfolio-api.md) | Equity/options records and lifecycle semantics |
| [Data models](data-models-server.md) | Storage schemas and migration references |
| [Application integration](internal/CHATBOT_INTEGRATION_GUIDE.md) | Detailed orchestration patterns; MCP is preferred |

## Operate and develop

- [Architecture](guides/architecture.md): how the current interfaces and stores fit together.
- [Deployment and upgrades](guides/operations.md): configuration, health, migrations, access controls.
- [Migrations](../migrations/README.md): schema upgrades and rollback tooling.
- [Verification](MCP-verification.md): tested scenarios and known gaps.
- [Contributing](../CONTRIBUTING.md): development and test commands.
- [Changelog](../CHANGELOG.md), [releases](releases/README.md), and [roadmap](ROADMAP.md).
- [Graphics](assets/README.md): visual sources, generation prompt, and maintenance.

## Historical design and implementation records

The original [architecture proposal](architecture.md), [PRD](PRD.md), [epics](epics.md),
`docs/sprint-artifacts/`, and most of `docs/internal/` record design intent or work at
specific points in time. They may include superseded plans, deferred capabilities,
and old verification results. Their presence does not mean every feature is shipped.
Use the guides above and the current code for integration decisions.

The [June–September 2026 review](recent-enhancements-2026-09.md) preserves the commit
evidence for that period without assigning retrospective release versions.
