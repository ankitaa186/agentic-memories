# Hook Integration Framework

Agentic Memories now ships with a pluggable hook framework designed to ingest data from operational systems like email and calendars. Hooks run alongside the API, normalize external payloads, and pipe them into the unified ingestion graph so that contextual memories are created automatically.

## Architecture Overview

* **Hook manager** – Loads configuration from `config/hooks.yml`, manages user consent, tracks polling state, and starts/stops hook workers.
* **Normalization pipeline** – Deduplicates events, transforms raw payloads into `TranscriptRequest` objects, and invokes the LangGraph ingestion pipeline.
* **Connectors** – Polling workers for Gmail/IMAP email accounts and Google Calendar/CalDAV calendars. Each connector can also accept webhook notifications for faster delivery.

All hook activity is observable via standard API logging and Langfuse traces emitted by the ingestion pipeline.

## Configuration

Edit `config/hooks.yml` to enable or disable connectors and adjust polling intervals. Each entry defines:

```yaml
- name: gmail
  kind: gmail
  enabled: true
  poll_interval_seconds: 180
  error_backoff_seconds: 30
  scopes:
    - https://www.googleapis.com/auth/gmail.readonly
```

Override the configuration path by setting `HOOKS_CONFIG_PATH` (see `env.example`).

## Consent Flow

1. Call `POST /v1/hooks/{hook}/consent` with the user ID and connector-specific credentials (OAuth tokens for Gmail/Google Calendar, IMAP login settings, etc.).
2. Optionally provide `seed_messages` or `seed_events` arrays to backfill historical data.
3. Revoke access with `DELETE /v1/hooks/{hook}/consent?user_id=...`.

Consent payloads are stored in PostgreSQL (Timescale DSN). When the database connection is unavailable—such as in quickstart demos—the manager transparently falls back to in-memory storage, but production deployments should rely on the database for durability.

## Webhooks

For systems that support outbound notifications, forward the webhook payload to `POST /v1/hooks/{hook}/events`. Connectors transform webhook envelopes into hook events and push them through the normalization pipeline immediately.

## Implemented Connectors

| Connector | Data Type | Notes |
|-----------|-----------|-------|
| Gmail | Email | OAuth 2.0 polling; optional Gmail push notifications. |
| IMAP | Email | Generic IMAP polling with username/password credentials. |
| Google Calendar | Calendar events | OAuth 2.0 polling; supports Google push notifications. |
| CalDAV | Calendar events | Fetches iCalendar feeds over HTTPS (with basic auth support). |

Additional connectors can be registered via `src/hooks/registry.py`.

## Testing

* Unit tests under `tests/hooks/` cover normalization, deduplication, and manager behavior using mocked ingestion runners.
* The hook manager starts automatically during API boot; shutdown gracefully stops all workers.

For production deployments remember to provision PostgreSQL/Timescale (for consent persistence), Redis (for hook state caching), and supply valid OAuth credentials for Google integrations.
