# Roadmap

This page separates implemented capabilities from directions that still require design,
implementation, and verification. It is not a delivery schedule.

## Available today

- MCP and REST interfaces sharing the application request pipeline.
- Direct memory writes, transcript extraction, updates, deletion, and semantic retrieval.
- Time/metadata filters, configurable retention, and maintenance/consolidation paths.
- Structured profiles, scheduled-intent APIs, and equity/options portfolio records.
- A web UI, container deployment, and optional LLM tracing.

See the [verification report](MCP-verification.md) for the scenarios tested and the remaining gaps.

## Next priorities

- Make clean-install onboarding and MCP client examples reproducible.
- Publish versioned releases with clear migration and compatibility notes.
- Expand retrieval evaluations and publish reproducible quality/latency measurements.
- Improve identity-based authorization and per-tool access controls before making broader enterprise claims.
- Expand integration examples and operational recovery guidance.

## Explorations

Relationship/graph retrieval, additional connectors, and more advanced retention or
prediction features remain possible directions. Historical design documents discuss
these ideas; they are not current product guarantees.

Propose use cases or contribute through [GitHub issues](https://github.com/ankitaa186/agentic-memories/issues).
