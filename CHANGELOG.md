# Changelog

User-visible changes, compatibility notes, and upgrade requirements.

Published versions appear in [GitHub Releases](https://github.com/ankitaa186/agentic-memories/releases).
There are no historical versioned releases recorded here yet. See the
[release process](docs/releases/README.md) and [next release draft](docs/releases/v0.2.0-draft.md).

## Unreleased

### Documentation

- Reworked onboarding around persistent context and MCP, with a concise README, a documentation index, focused setup/concept/operations guides, and a runnable cross-session memory example.
- Added a new hero banner, editable workflow/architecture graphics, and release preparation guidance.

### Maintenance

- Aligned Makefile and CI runtime dependency exports with the checked-in requirements by excluding the test dependency group; CI now uses the locked formatter for reproducible checks.

### Added

- Added the preferred MCP agent interface at `/mcp`, using Streamable HTTP in the existing FastAPI process and port. All 39 application operations and four framework documentation endpoints are discoverable tools; REST remains supported.
- Reuses the FastAPI request pipeline for validation, user scoping, credentials, responses and errors; integrates the SDK lifecycle and synchronized dependencies.
- Added [client/configuration guidance](docs/MCP.md), a [route/tool inventory](docs/mcp-route-mapping.json), and protocol/regression tests. Remote deployments must protect `/mcp` with appropriate proxy access controls, including administrative operations.
- Documentation now leads with MCP while retaining REST examples and clearly identifying older deferred-MCP plans. These changes describe this revision, not a tagged release or completed deployment.

## Unversioned baseline

These changes predate the first tagged release. Dates identify work on main, not releases.

### June–September 2026

#### Added

- Equity/options portfolio CRUD, generated OCC-style symbols, position lookup by UUID/symbol/contract key, lifecycle status, grouped responses, and active short-option collateral totals (migration 025; August 6).
- `make service-update` to rebuild and recreate only the API container (September 18).
- Informational `checks.timescale_pool` statistics on `/health/full` (July 13).

#### Fixed

- Pooled PostgreSQL connections now return on temporal-retrieval and episodic-storage cleanup paths, even when rollback fails (July 13).
- Ordinary semantic/hybrid text retrieval ranks by actual cosine similarity, including SQL-only procedural memories, without unrelated persona/age/importance boosts. Bounded owner/content/model-scoped skill embedding caching and normalized IDs preserve recall and deduplication (September 18).

#### Maintenance

- Internal scrum workspace moved from `.claude/scrum/` to `.scrum/`; no runtime feature change (July 13).

See [review and upgrade notes](docs/recent-enhancements-2026-09.md) for commit evidence and migration requirements. These are changes present on `main`, not a claim of a tagged release or deployment.

### Earlier changes

#### Added

- **AM-X.2 — Time and metadata filters on `GET /v1/retrieve`.** New optional
  query parameters: `created_after`, `created_before`, `expires_after`,
  `expires_before`, `kind`, and repeatable `metadata_filter` (`key:value`).
  Datetime parameters MUST be timezone-aware ISO 8601 (Z suffix or explicit
  offset); naive datetimes return 422. Aware datetimes are normalized to UTC
  before being compared against the stored UTC `metadata.timestamp`. The
  `expires_*` parameters filter records WITH a TTL only — immortal memories
  are excluded. The `metadata_filter` parameter rejects system-managed and
  internally-derived keys with 422.

#### Changed (behavior)

- **AM-X.2 — Filter-only `/v1/retrieve` calls now return recency-desc.**
  Previously, callers passing only `layer=` or `type=` (no `query`, no
  `sort=`) received Chroma's arbitrary `get` order. After this change,
  filter-only calls return results sorted by `metadata.timestamp` DESC
  (newest first). Callers that explicitly want a different order can still
  pass `sort=oldest`. Pagination on the filter-only path uses Python-side
  sort+slice within `RETRIEVE_MAX_FETCH_CAP` (default 5000); narrow filters
  for deeper pages.

- **AM-X.0 — `POST /v1/memories/direct` now honors `ttl_seconds` on every layer.**
  Previously, `ttl_seconds` was silently dropped unless the request's `layer`
  was `short-term`; semantic, long-term, and typed-layer records ignored the
  field and were stored as immortal. After this change, any non-null
  `ttl_seconds` is honored regardless of layer (the value is written through
  to `ttl_epoch` in Chroma metadata, and the soft-TTL sweep evicts the record
  approximately `ttl_seconds` after creation).

  **Behavior change for existing callers:** if a caller was passing
  `ttl_seconds` on a non-short-term layer and relying on the silent-drop to
  keep the memory immortal, those memories will now expire. To preserve
  immortality on non-short-term layers, omit `ttl_seconds` from the request
  body. Omission semantics are unchanged: short-term records continue to use
  `SHORT_TERM_TTL_SECONDS` (default 60 days); semantic, long-term, and typed
  layers remain immortal when `ttl_seconds` is omitted.

  See `src/routers/memories.py` (the gate at the resolved-TTL block) and the
  `DirectMemoryRequest.ttl_seconds` OpenAPI description in `src/schemas.py`.
