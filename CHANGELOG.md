# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- **AM-X.2 — Time and metadata filters on `GET /v1/retrieve`.** New optional
  query parameters: `created_after`, `created_before`, `expires_after`,
  `expires_before`, `kind`, and repeatable `metadata_filter` (`key:value`).
  Datetime parameters MUST be timezone-aware ISO 8601 (Z suffix or explicit
  offset); naive datetimes return 422. Aware datetimes are normalized to UTC
  before being compared against the stored UTC `metadata.timestamp`. The
  `expires_*` parameters filter records WITH a TTL only — immortal memories
  are excluded. The `metadata_filter` parameter rejects system-managed and
  internally-derived keys with 422.

### Changed (behavior)

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
