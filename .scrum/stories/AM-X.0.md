# Story AM-X.0 — Honor `ttl_seconds` for all layers

**Epic:** AM-X (Memory Primitives)
**Status:** implemented
**Priority:** P0
**Author:** Disha (refined from Parminder's epic notes)
**Architect approval:** Parminder (2026-05-08; amended 2026-05-08 after 3-Parminder deep audit; re-acked 2026-05-08 GREEN)
**Estimate:** ~5 LOC + tests; <1 hour
**Build order:** 1st (per Parminder's recommended order)

## User need
When a caller passes `ttl_seconds` on `POST /v1/memories/direct`, the system honors it regardless of which layer the memory lands in. Today it's silently dropped for `semantic` / `long-term` / typed layers — only `short-term` reads the field. This is a 5-LOC fix that immediately makes per-fact TTL real for the existing API surface.

## Acceptance criteria
- [x] AC1: A semantic memory written with `ttl_seconds=86400` has `ttl_epoch` populated. Concrete tolerance: assert `ttl_epoch == now + 86400 ± 5s` (`time.time()` granularity is sub-second on Linux; ±5s gives generous slack for slow CI).
- [x] AC2: A long-term memory written with `ttl_seconds` set has `ttl_epoch` populated.
- [x] AC3: A memory written *without* `ttl_seconds` keeps the existing per-layer default behavior: semantic/long-term remain immortal (no `ttl_epoch`); short-term continues to use `get_default_short_term_ttl_seconds()`.
- [x] AC4: No existing caller breaks. Existing tests in `tests/unit/test_app_store.py` and `tests/unit/test_memories_router.py` (and any direct-memory unit tests) pass unchanged.
- [x] AC5: New unit test covers: `ttl_seconds` honored on `semantic`, `ttl_seconds` honored on `long-term`, `ttl_seconds=None` keeps semantic/long-term immortal, `ttl_seconds=None` keeps short-term using the configured default.
- [x] AC6: OpenAPI description for `DirectMemoryRequest.ttl_seconds` updated to clarify it is honored across all layers; remove any wording that implies it only applies to `short-term`.
- [x] AC7: CHANGELOG / release-note entry added calling out behavior change: memories written via `POST /v1/memories/direct` with `ttl_seconds` set on a non-`short-term` layer now expire after `ttl_seconds`; previously the value was silently dropped and those memories were immortal. Existing callers who relied on the silent-drop must explicitly omit `ttl_seconds` to preserve immortality.
- [x] AC8: Update the LLM-extraction prompt docstring at `src/services/prompts.py:113` (and any v2/v3 mirrors) to remove the "short-term only" qualifier on `ttl`. Current text reads `"ttl": 86400 | null,  // Optional: seconds (for short-term only)` — that "(for short-term only)" clause is now stale and must be removed/rephrased to reflect all-layers honoring.

## Files to touch
- `/Users/ankit/dev/agentic-memories/src/routers/memories.py:450-457` — replace the `if body.layer == "short-term"` gate. Logic becomes:
  - If `body.ttl_seconds is not None`: use it.
  - Else if `body.layer == "short-term"`: use `get_default_short_term_ttl_seconds()`.
  - Else: `ttl_seconds = None`.
- `/Users/ankit/dev/agentic-memories/src/schemas.py` — update the `DirectMemoryRequest.ttl_seconds` field description.
- `/Users/ankit/dev/agentic-memories/src/services/prompts.py:113` — remove the "(for short-term only)" qualifier on the `ttl` field comment in the LLM extraction prompt; check for any v2/v3 mirrors and update those too (per AC8).
- `CHANGELOG.md` (or equivalent release-notes file) — append the behavior-change note (per AC7).
- `tests/unit/` — add the AC5 test file (suggested name `test_direct_memory_ttl.py`).

## Out of scope
- PATCH endpoint (AM-X.1).
- Filtered retrieve (AM-X.2).
- Faster sweeper (AM-X.3).

## Architect notes (Parminder)
- Trivial substrate-aligning change. No schema migration. No new dependency. The `_ttl_epoch_from_ttl` helper at `src/services/storage.py:30-34` and the metadata builder at `src/services/storage.py:53-54` already populate `ttl_epoch` whenever `memory.ttl is not None` — we just need to stop dropping the value before constructing the `Memory`.
- Single highest-value fix in the epic. Ship first.

## Open-question resolutions baked in
- TTL contract: **soft** ("eligible for eviction after T, may linger up to one sweep cycle"). OpenAPI description updates in AC6 should reflect this.
