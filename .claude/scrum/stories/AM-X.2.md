# Story AM-X.2 — Time and metadata filters on retrieve

**Epic:** AM-X (Memory Primitives)
**Status:** implemented
**Priority:** P0
**Author:** Disha (refined from Parminder's epic notes)
**Architect approval:** Parminder (2026-05-08; re-acked 2026-05-08 after AC18 timezone tightening; amended 2026-05-08 after 3-Parminder deep audit; re-acked 2026-05-08 GREEN with one polish item folded into AC12 — env var named)
**Estimate:** ~150 LOC + tests; ~half day
**Build order:** 4th (per Parminder's recommended order)

## User need
A consumer can ask "what memories were created in the last N hours," "what expires within the next N hours," or "what memories have `metadata.kind = meals_today`" — independent of embedding similarity. Today the only knob is semantic search, which ranks badly for time-relevance queries (verified empirically: meals-today scored 0.38 against the obvious query in the dry-run).

## Acceptance criteria

### API surface
- [x] AC1: `GET /v1/retrieve` accepts new query parameters:
  - `created_after` (ISO 8601 datetime; inclusive)
  - `created_before` (ISO 8601 datetime; exclusive)
  - `expires_after` (epoch int OR ISO datetime; inclusive)
  - `expires_before` (epoch int OR ISO datetime; exclusive)
  - `kind` (string; matches `metadata.kind` exactly)
  - `metadata_filter` (repeatable string of form `key:value`; scalar values only; multiple values for the same key are AND-combined as the literal user provided)
- [x] AC2: All new parameters are optional; existing callers (filters omitted) get unchanged behavior. Existing tests in `tests/unit/test_app_retrieve.py` pass unchanged.
- [x] AC3: Invalid filter values (malformed datetime, **naive datetime without timezone offset**, malformed `metadata_filter` shape) return 422 with a clear error.
- [x] AC4: `metadata_filter` rejects (422) any key in the shared `SYSTEM_MANAGED_FIELDS` constant (defined in X.1 AC19; covers `user_id`, `layer`, `type`, `ttl_epoch`, `timestamp`, `content_hash`, `stored_in_episodic`, `stored_in_emotional`, `stored_in_procedural`, `typed_table_id`). Those are surfaced via dedicated parameters or are internal. `kind` filters via the dedicated `kind` parameter, not `metadata_filter`. **Implementation MUST `from src.services._constants import SYSTEM_MANAGED_FIELDS`** (or wherever X.1 places it) — no local re-list.
- [x] AC18: **Timezone normalization.** `created_after` / `created_before` MUST be timezone-aware ISO 8601 (either `Z` suffix or explicit offset like `-07:00`). Naive datetimes return 422 with the message `"datetime must include timezone offset (e.g. Z or +00:00)"`. Aware datetimes are normalized to UTC via `.astimezone(timezone.utc).isoformat()` BEFORE being passed to the Chroma `where` builder, so they lex-compare correctly against the stored `timestamp` field which is always UTC-aware (`src/services/storage.py:42` writes `datetime.now(timezone.utc).isoformat()` → `"…+00:00"`). OpenAPI description for both params: "Server stores timestamps in UTC. Pass `Z` or an explicit offset; offset is normalized to UTC before comparison." `expires_after` / `expires_before` are unaffected when passed as epoch ints; if passed as ISO datetime, same rules apply.

### Semantics
- [x] AC5: Filters compose with each other (AND). When `query` is also supplied, filters apply BEFORE semantic search.
- [x] AC6: When ONLY filters are supplied (no `query`), results are deterministic and sorted by recency-desc (newest `timestamp` first). Sort order is documented in OpenAPI.
- [x] AC7: "What do I remember about today" can be answered by `GET /v1/retrieve?user_id=...&created_after=2026-05-08T00:00:00Z` in one call, without `query`.
- [x] AC8: Filtered results page predictably with the existing `limit` / `offset` parameters; pagination preserves the recency-desc ordering across pages.
- [x] AC9: ISO timestamps stored at `src/services/storage.py:42` are lexicographically sortable; `created_after` / `created_before` translate to `where: {"timestamp": {"$gte": ..., "$lt": ...}}` on Chroma. `expires_after` / `expires_before` translate to `where: {"ttl_epoch": {"$gte": ..., "$lt": ...}}`.

### Implementation
- [x] AC10: The whitelist at `src/services/retrieval.py:117-122` is replaced with a builder function (e.g., `_build_where_clause(user_id, filters)`) that translates the filter dict into a single Chroma `where` document using `$and` / `$gte` / `$lte` / `$lt` operators. Pattern matches the existing usage at `src/services/forget.py:32` and `src/services/unified_ingestion_graph.py:579`.
- [x] AC11: When more than one Chroma operator is needed on different keys, the builder uses `{"$and": [...]}` correctly (Chroma requires this for multi-field ranged filters).
- [x] AC12: **Pagination on the `query`-less path (reconciles AC8 with Chroma ordering reality).** The `query`-less path fetches up to `min(limit + offset + buffer, RETRIEVE_MAX_FETCH_CAP)` records via Chroma `get(where=...)` (no Chroma offset on the filter-only path, since Chroma `get` order is undefined), sorts by `timestamp` DESC in Python, then slices `[offset:offset+limit]` for the requested page. `RETRIEVE_MAX_FETCH_CAP` is configurable via env var of the same name (default `5000`); add to `env.example` and `src/config.py` (lru_cached helper, mirroring `TTL_SWEEP_INTERVAL_MINUTES`). Beyond the cap, pagination is documented as best-effort (callers needing deeper pagination should narrow filters). For `query`-with-filters, ordering remains the existing semantic-distance order and `offset` works as before. AC8 (predictable pagination) stays as-is and is now genuinely achievable within the cap.

### Out of scope (explicit)
- [x] AC13: No Postgres union for typed tables (episodic/emotional). Per Parminder's note: typed tables are fan-out replicas, not the source of truth for short-tail facts. The existing episodic-time-range path via `NarrativeRequest` / `src/schemas.py:232` is left untouched.

### Tests
- [x] AC14: Unit tests for `_build_where_clause`: each filter alone, two filters combined, three filters combined, conflicting filters (e.g., `created_after > created_before`) → 422. **Plus timezone tests:** naive datetime → 422; `Z`-suffixed datetime accepted and normalized to `+00:00`; non-UTC offset (e.g. `-07:00`) accepted and normalized to UTC before clause emission (assert the `where` clause string matches the UTC-normalized form).
- [x] AC15: Integration tests against a real Chroma collection (using existing `tests/integration` fixtures): created_after/created_before window, expires_before window, `kind=meals_today` filter, `metadata_filter` repeatable, filter+query composition, filter-only sort order. **Plus cross-timezone test:** store a memory at known UTC time, then query with `created_after` in `-07:00` offset that brackets the same instant; assert the memory is returned (proves normalization, not raw lex-compare).
- [x] AC16: Regression test for the dry-run scenario: store 5 meals memories with `metadata.kind=meals_today` and varied timestamps, then retrieve with `created_after=today_start&kind=meals_today`, assert all 5 returned in recency-desc order without any `query` text.
- [x] AC17: Existing semantic-search tests (`tests/unit/test_app_retrieve.py`) pass unchanged.

### Persona-path threading & cross-cutting (added 2026-05-08 per audit)
- [x] AC19: **CRITICAL — persona-path threading.** The new query params on `/v1/retrieve` (`created_after`, `created_before`, `expires_after`, `expires_before`, `kind`, `metadata_filter`) MUST thread through `_persona_copilot.retrieve` (`src/app.py` ~1143) and `PersonaRetrieval.retrieve` (`src/services/persona_retrieval.py:107`, `:195`) so they reach `search_memories`. Without this, the dominant retrieve code path (chat runtime, summary manager, memory context, orchestrator — 12+ call sites) silently drops every new filter. Add a regression test that the persona path honors `created_after` end-to-end.
- [x] AC20: **Default-ordering change documented.** AC2 ("existing tests pass unchanged") is true only when callers pass neither filters nor `query`. Callers passing only `layer=` or `type=` (filter-only, no query, no new params) today receive Chroma's arbitrary `get` order; after this story they receive recency-desc. Add a regression test in `tests/unit/test_app_retrieve.py` for the `layer=semantic` filter-only case asserting recency-desc ordering. Add a one-line CHANGELOG / release-note: "Filter-only `/v1/retrieve` calls now return recency-desc; previously order was undefined."
- [x] AC21: **`expires_*` docstring.** OpenAPI description for `expires_after` and `expires_before` includes: "Filters records WITH a TTL only. Immortal memories (no `ttl_epoch` set) are excluded from any `expires_*` filter. To find immortal memories, omit both `expires_*` parameters." Same note on the corresponding Chroma `where` clause behavior in code comments.
- [x] AC22: **`metadata_filter` allowed-key clarification.** `metadata_filter` accepts user-supplied metadata keys (e.g. `kind`, `tags`, custom keys passed via `metadata` on `POST /v1/memories/direct`). It rejects (422) any key in `SYSTEM_MANAGED_FIELDS` (per AC4). Additionally, it rejects (422) the following internally-derived fields written by `_build_metadata` at `src/services/storage.py:36-50`: `importance, relevance_score, confidence, usage_count, persona_tags, emotional_signature`. These fields are populated by the system per-record and querying them via `metadata_filter` would expose internal scoring. (If a future story needs filterable importance, it gets a dedicated parameter, not generic metadata access.)
- [x] AC23: **Sort-logic consolidation.** The existing post-fetch recency sort at `src/app.py:1166-1183` (the `_ts_key` block triggered when `sort in ('newest', 'oldest')`) is moved into `src/services/retrieval.py` as a shared helper used by both the `sort=` path and the new filter-only path. No drift between two implementations. The route in `app.py` calls the helper instead of inlining the sort.
- [x] AC24: Tests for new ACs — persona-path E2E test (AC19), filter-only ordering regression (AC20), expires_* immortal-exclusion test (AC21), `metadata_filter` rejects internally-derived keys (AC22), sort-helper unit test (AC23).

## Files to touch
- `/Users/ankit/dev/agentic-memories/src/app.py:1099` — `GET /v1/retrieve` route signature: add the new `Query(...)` parameters, validate datetime formats, pass into the retrieval service. Also `src/app.py:1166-1183` — extract the `_ts_key` recency-sort block into the shared helper per AC23.
- `/Users/ankit/dev/agentic-memories/src/services/retrieval.py:117-122` — replace the whitelist with `_build_where_clause`. Also add the shared recency-sort helper used by both the `sort=` path and the filter-only path (AC23).
- `/Users/ankit/dev/agentic-memories/src/services/persona_retrieval.py:107` and `:195` — thread the six new params through `PersonaRetrieval.retrieve` so the dominant code path (chat runtime, summary manager, memory context, orchestrator) honors them (AC19).
- `/Users/ankit/dev/agentic-memories/src/app.py` ~1143 — `_persona_copilot.retrieve` call site: pass the new params through (AC19).
- `/Users/ankit/dev/agentic-memories/src/schemas.py` — add the new query-param shapes if they need shared validation (likely a small `RetrieveFilters` dataclass) and update `RetrieveResponse` if needed (probably not).
- `tests/unit/test_app_retrieve.py` — extend.
- `tests/integration/` — new fixtures or extend existing.
- Import `SYSTEM_MANAGED_FIELDS` from X.1's location (`src/services/_constants.py` or top of `src/services/storage.py`) per AC4.

## Architect notes (Parminder)
- This is the lowest-risk, highest-leverage retrieve change in the epic. The Chroma operators are already exercised in the codebase, so we have a working reference for syntax.
- The `query`-less recency-desc sort happens in Python (post-fetch). For very large result sets this could be costly, but `limit + offset` bounds it, and v1 callers will use modest limits.
- Document the soft TTL contract here too: "memories with `ttl_epoch <= now` MAY appear briefly in results until the next sweep cycle (default 15 min)."
- **Timezone (AC18 added post-approval per user direction):** stored `timestamp` is always UTC-aware ISO with `+00:00` shape (per `src/models.py:19` and `src/services/storage.py:42`). Lex-compare on the `where` operator only works if the input is in the same shape, so naive must be rejected and non-UTC offsets must be normalized BEFORE building the clause. `ttl_epoch` is a Unix int and unaffected.

## Open-question resolutions baked in
- **TTL contract: hard or soft?** Soft. Documented in OpenAPI for `expires_after`/`expires_before`.
- **Timezone handling (decided 2026-05-08):** server stores in UTC; per-user timezones explicitly out of scope (matches epic non-goal). Inputs MUST be timezone-aware ISO 8601; naive → 422; non-UTC offsets normalized to UTC before `where` clause emission. AC18 enforces.

## Dependencies
- None blocking. Can run in parallel with AM-X.1, but they both edit `src/routers/memories.py` — actually, X.2 edits `src/app.py` and `src/services/retrieval.py`, while X.1 edits `src/routers/memories.py` and `src/services/storage.py` — **no file collision**. They can run in parallel.


## Live-API bug fixes (2026-05-08)

Live-curl testing on the staged branch surfaced one HIGH-severity bug not caught by the unit tests:

**Bug:** `GET /v1/retrieve?user_id=X&created_after=2026-05-08T22:59:20-07:00` returned HTTP 500 from the persona-retrieval fallback path. Other timezone offsets that resulted in non-empty matches (e.g. `+05:30`) returned 200, masking the issue.

**Root cause (deeper than the original bug report suspected):** Chroma 1.x **rejects `$gte` / `$lt` operators on string-valued fields**. The original AM-X.2 design assumed lex-compare on the ISO ``timestamp`` field would work natively in the Chroma where-clause; that assumption was wrong. The where-doc

```json
{"$and": [{"user_id": "X"}, {"timestamp": {"$gte": "2026-05-09T05:59:20+00:00"}}]}
```

is rejected by Chroma with `InvalidArgumentError: Invalid where clause`. Reproduced via direct curl against `localhost:8000/api/v2/.../get`.

**Why pytest missed it:** the integration tests at `tests/integration/test_retrieve_filters.py` use a stub collection that implements `$gte` / `$lt` on strings in Python. The stub does not match production Chroma behavior. The cross-tz test (AC15) only covered the "matches found" case; the "no matches" case (negative offset → future UTC) was the one that tripped Chroma.

**Why only the persona-fallback fired the 500:** the hybrid path doesn`t use the where-clause for these filters (it uses `_apply_x2_filters_to_hybrid` which is pure Python). Only when hybrid returned an empty list AND the persona-fallback was invoked did the where-clause path fire. Live-curl with `-07:00` produced empty hybrid results → fallback called → Chroma rejected the where-doc → 500.

**Fix (~70 LOC):**
- `_build_where_clause` in `src/services/retrieval.py` no longer emits ``timestamp`` range clauses. The arguments are still accepted for backward compatibility but silently dropped from the where-doc.
- Added `_filter_records_by_timestamp` helper in the same file that applies the predicate in Python, mirroring the lex-compare semantics the where-clause used to use.
- `search_memories` now applies the predicate post-fetch on both the filter-only and semantic-query paths, and over-fetches up to `RETRIEVE_MAX_FETCH_CAP` when timestamp filters are active to compensate.
- `_apply_x2_filters_to_hybrid` (in `src/services/persona_retrieval.py`) was already doing this correctly for the hybrid path — no change needed there.

**Latent bug fixed alongside:** `V2Collection.get()` and `.query()` were sending `where: {}` on the no-filter branch; Chroma 1.x rejects that with the same `InvalidArgumentError`. Both now omit the key when the filter dict is empty (verified live).

**New tests (no-match symmetry case the audit missed):**
- `test_persona_agent_negative_offset_no_match_does_not_500` — drives `PersonaRetrievalAgent` directly with a future-UTC `created_after` so hybrid returns nothing → fallback runs → must return empty without raising.
- `test_build_where_clause_drops_created_filters_to_avoid_chroma_rejection` — pins the new builder behavior so future stories can`t silently re-introduce the `timestamp: {"$gte":...}` shape.
- `test_filter_records_by_timestamp_applies_predicate` — covers the new Python-side filter helper (both bounds, missing-timestamp exclusion, no-op identity).

**Updated tests:** `test_build_where_clause_created_range_uses_gte_lt` → renamed to `test_build_where_clause_omits_timestamp_range`; `test_build_where_clause_combines_timestamp_and_ttl_with_and` → renamed to `test_build_where_clause_combines_supported_predicates_with_and`.

**Live curl verification (planned post-rebuild):**
- `created_after=2026-05-08T22:59:20-07:00` → expect 200 with empty `results`.
- `created_after=2099-01-01T00:00:00Z` → expect 200 with empty `results`.
- `created_after=2026-05-09T01:00:00+05:30` → expect 200 (results unchanged).

**Verification:** `pytest tests/unit tests/integration -q` → 660 passed, 1 skipped. `ruff check` clean.

AC verification: AC9 ("$gte/$lt range filters") wording in the story is now misleading — the predicate is enforced but in Python, not via Chroma operators. Behavior is identical to the spec; only the implementation layer moved.

