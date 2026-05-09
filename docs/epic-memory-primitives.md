# Epic AM-X: Memory Primitives — Update, Time-Window Filtering, and Real Eviction

**Status:** draft
**Owner:** _TBD (handoff: fenny → david)_
**Priority:** P0
**Effort estimate:** 2 days for MVP slice (4 days for full epic)
**Repo:** `agentic-memories`
**Architect:** parminder
**Author of PRD frame:** disha
**Related:** annie-in-a-bottle Epic 5, Story 5.2 (Daily Context Scratchpad — blocked on this)

---

## Origin

This epic was produced from a live dry-run pressure-test against the running `agentic-memories` service. Annie was role-played storing real meals data via `POST /v1/memories/direct` while we observed: what TTLs the LLM picks per-fact, which queries succeed, where the substrate forces fragile workarounds. Three substrate-level gaps surfaced. This epic closes them.

The dry-run revealed two items we initially got wrong, both corrected from code review (parminder):

1. `body.ttl_seconds` **is already** a top-level field on `DirectMemoryRequest`. We were sending `metadata.ttl_hours` (custom name); the system silently honored `ttl_seconds` only and fell back to the per-layer default for short-term (~60d). Per-fact TTL plumbing exists; the gap is that `ttl_seconds` is **silently ignored for non-short-term layers** (`src/routers/memories.py:450-457`).
2. An eviction sweeper **does exist** (`src/services/forget.py:24` `ttl_cleanup()`, scheduled in `src/app.py:264-279` via APScheduler). It just runs **once a day** at 00:00 UTC inside the daily compaction graph. So a TTL of 12h can drift up to ~24h past expiry. Cadence is the real bug, not absence.

Net: the substrate is closer to "Disha's per-fact-TTL model already works" than the original dry-run suggested. Most of the gap is API surface, not core mechanism.

---

## Problem statement

Annie cannot reliably hold context that spans more than a single conversation turn without either polluting her permanent memory or losing the context entirely. Real facts she needs to track have wildly different time horizons — what she ate today (hours), what she's debugging (days), a house hunt (weeks), a trip in March (months) — but the substrate forces her into one of two bad patterns: stuff short-tail facts into permanent storage and slowly poison recall, or work around the missing primitives by deleting and re-creating memories whenever a rolling fact updates. The substrate is missing primitives, not features.

## Why now

The Daily Context Scratchpad story (annie-in-a-bottle Epic 5, Story 5.2) is blocked on this. Building a one-off Redis bucket system in `annie-in-a-bottle` would solve the symptom while leaving the substrate brittle for any future middle-tier work. Investing in primitives in `agentic-memories` once unblocks 5.2 and any future strategy (per-fact TTL, scratchpad-style anchoring, both layered) without rework.

## Goals

- A rolling fact can be updated in place without losing its memory ID, history, or referential integrity.
- Consumers can query memories by time window (created/expires within N hours) and by metadata fields, **independent of embedding similarity** — embedding rank is wrong for "what's recent and relevant" (verified: meals-today scored 0.38 against the obvious query).
- Per-fact TTL is honored end-to-end across all layers, not silently dropped when not `short-term`.
- Expired memories actually evict on a fast-enough cadence that a 12h TTL means roughly 12h, not "up to 12h + ~24h drift."
- The three gaps surfaced in the dry-run are no longer reproducible by a follow-up dry-run script.

## Non-goals

- **Not** building a scratchpad in this epic. Scratchpad is a thin policy on top of these primitives and lives in the consumer (`annie/voice/`).
- **Not** redesigning the embedding pipeline.
- **Not** adding semantic clustering or pattern crystallization. The dry-run identified pattern-crystallization (promote repeated short-tail facts into permanent insights) as the *real* missing tier neither approach handles, but it's a separate follow-up epic.
- **Not** changing the ChromaDB schema or breaking existing `/v1/memories/direct` callers.
- **Not** supporting per-user timezones in v1. Server-local fine.
- **Not** building a `GET /v1/memories/active` convenience endpoint in the substrate (recommended to live in the consumer — see AM-X.5).

---

## Stories

Each story below has a user-need framing and acceptance criteria (disha). The architect notes (parminder) underneath each give file paths and complexity estimates. David should plan against the parminder notes; user-facing acceptance is the contract.

### AM-X.0 — Honor `ttl_seconds` for all layers (the 5-LOC fix)

**User need:** When a caller passes `ttl_seconds` on a memory write, the system honors it regardless of which layer the memory lands in. Today it's silently dropped for `semantic` / `long-term` / typed layers — only `short-term` reads the field.

**Acceptance criteria:**
- A semantic memory written with `ttl_seconds=86400` expires in roughly one day, not "never."
- A long-term memory written with `ttl_seconds` set has `ttl_epoch` populated.
- A memory written without `ttl_seconds` keeps the existing per-layer default behavior (semantic/long-term immortal; short-term uses configured default).
- No existing caller breaks: writes that don't pass `ttl_seconds` behave identically.

**Architect notes (parminder):**
- File: `src/routers/memories.py:450-457`. Currently gates on `layer == "short-term"`. Remove the gate; if `ttl_seconds` is set, populate `ttl_epoch` regardless of layer.
- ~5 LOC. Trivial.
- This is the single highest-value fix in the epic — restores the per-fact-TTL story for the *existing* API surface without a single new endpoint.

---

### AM-X.1 — Update primitive: `PATCH /v1/memories/{memory_id}`

**User need:** A consumer can modify the content, metadata, importance, or TTL of an existing memory by ID without delete-and-recreate. Today's "update meals at lunch" workaround loses memory_id continuity, races against concurrent reads, and is fragile.

**Acceptance criteria:**
- Updating a memory preserves its ID and `created_at` timestamp.
- Either content, metadata, layer, importance, or `ttl_seconds` can be changed in a single call; partial updates are valid.
- If `content` changes, the embedding is regenerated and the search index reflects the new content on the next retrieve. Idempotency: same content twice is detected via `content_hash` and skips embedding regen.
- Metadata semantics are **shallow merge**, not replace. A sentinel value (e.g. `"__delete__"`) drops a key. Prevents losing system-managed fields like `stored_in_episodic` or `typed_table_id`.
- Updating a non-existent or deleted ID returns a clear, non-200 response (404).
- A `user_id` mismatch between the call and the stored record returns 403.
- Updates are observable: a follow-up retrieve returns the new content, not the old.

**Architect notes (parminder):**
- File: new handler in `src/routers/memories.py` near the existing DELETE at line 718.
- Use Chroma's native `collection.update(ids=, documents=, embeddings=, metadatas=)` — no delete+recreate. **Memory_id continuity preserved.**
- Immutable fields: `id`, `user_id` (mismatch → 403), `created_at` / original `timestamp`, `typed_table_id`.
- Layer flips into typed-storage layers (semantic → episodic) are messy at update time — return 422 in v1.
- Typed-table fan-out: if `stored_in_episodic` etc. is set, issue UPDATE on the row by `typed_table_id`. MVP supports `content`, `importance_score`, `metadata` only on typed tables; everything else 422.
- ~250 LOC + tests. ~1 day.

---

### AM-X.2 — Time and metadata filters on retrieve

**User need:** A consumer can ask "what memories were created in the last N hours," "what expires within the next N hours," or "what memories have `metadata.kind = meals_today`" — independent of embedding similarity. Today the only knob is semantic search, which ranks badly for time-relevance queries (verified empirically).

**Acceptance criteria:**
- `GET /v1/retrieve` accepts: `created_after`, `created_before`, `expires_before`, `expires_after`, `kind` (a metadata convention), and a generic `metadata_filter=key:value` (repeatable, scalar values only).
- Filters compose with each other and with semantic search; using only filters with no `query` returns deterministic, sorted-by-recency results.
- "What do I remember about today" is answerable in one call without relying on embedding similarity.
- Filtered results page predictably with `limit`/`offset`; ordering is documented (recency-desc default).
- Existing callers (filters omitted) get unchanged behavior.

**Architect notes (parminder):**
- Files: `src/app.py:1099` (route), `src/services/retrieval.py:117-122` (the `where`-dict whitelist).
- Replace the whitelist with a builder that translates filters into Chroma `where` operators (`$gte`, `$lte`, `$and`). Chroma already supports these — verified used in `src/services/forget.py:32` and `src/services/unified_ingestion_graph.py:579`.
- ISO timestamps stored at `src/services/storage.py:42` are lexicographically sortable — `$gte` / `$lte` work directly.
- `ttl_epoch` is already an int — no conversion needed.
- **No Postgres union needed for MVP** — typed tables (episodic/emotional) are fan-out replicas, not the source of truth for short-tail facts. Episodic-time-range queries already have a path in `NarrativeRequest` / `src/schemas.py:232` — leave that alone.
- ~150 LOC + tests. Half a day.

---

### AM-X.3 — Fast eviction sweeper

**User need:** A memory whose TTL has elapsed is no longer returned by retrieve within minutes, not "up to 24 hours past expiry." Today a 12-hour TTL can effectively last 36 hours because the sweeper only fires once daily inside the compaction graph.

**Acceptance criteria:**
- A memory whose TTL has elapsed is no longer returned by retrieve within one sweep cycle (≤ 15 min, configurable).
- The sweep cadence is configurable and documented.
- Sweeper failures are observable (logs/metrics) and do not corrupt non-expired data.
- Sweeper does not race destructively with active writes — a memory updated at the moment of expiry is not deleted out from under the writer.
- Daily compaction continues to run as-is; this is an additive job.

**Architect notes (parminder):**
- File: `src/app.py` `_start_scheduler` (around line 264).
- Add an APScheduler job `ttl_sweep` running every 15 minutes that calls `src/services/forget.py:ttl_cleanup()` + `ttl_cleanup_timescale()` directly. Cheap — single Chroma `where` query each.
- Daily compaction stays unchanged — keep the LangGraph path for the heavier compaction work.
- Bonus cleanup: `POST /v1/forget` at `src/app.py:1685-1687` is currently a **stub that lies** — returns `jobs_enqueued` without enqueueing anything. Either delete the route or wire it to `ttl_cleanup()`. Recommendation: wire it. ~10 LOC.
- ~20 LOC for the new job. Half a day with tests.

---

### AM-X.4 — Active-context convenience query (decision, not story)

**User need:** A single call returns "what's currently relevant for this user," ranked by recency × importance × proximity-to-expiry, so the prompt builder doesn't reassemble the same query every turn.

**Architect's decision (parminder, recorded here per epic protocol):**

**Do not build this in `agentic-memories`.** Reasons:
1. "Active" means different things in different prompt frames (chat vs. journal vs. desire-evaluation). Annie's prompt layer already composes context per-state — the consumer owns that, not the substrate.
2. Ranking by `recency × importance × proximity-to-expiry` is policy that will iterate weekly. It does not belong in a backend that other clients consume.
3. Once AM-X.2 lands, the consumer call is one HTTP request and ~5 lines of formatting.

**Action:** record as decided in epic; build the consumer-side composer in annie-in-a-bottle (Story 5.2 follow-up).

---

## Dependencies and risks

- **Embedding regeneration on content update (AM-X.1)** — adds latency to PATCH; we'll do it synchronously for MVP and surface duration in the response. Async is a follow-up if measurements justify it.
- **Chroma metadata-filter performance at scale (AM-X.2)** — Chroma's `where` is fast for typical sizes but degrades if the filter is highly selective on a low-cardinality field. Acceptable for v1; revisit if memory count per user crosses ~100k.
- **Postgres / typed-table coordination on update (AM-X.1)** — typed-table updates are best-effort fan-out, same model as the existing DELETE. Document partial-failure semantics. Episodic/emotional tables get content/importance/metadata only; layer flips return 422.
- **Sweeper-vs-active-write race (AM-X.3)** — sweeper queries `ttl_epoch <= now` and deletes by ID; an in-flight update that bumps `ttl_seconds` lands in Chroma before the sweeper's delete. Add a 60-second grace window in the sweeper (`ttl_epoch <= now - 60`) to eliminate the race entirely.
- **`/v1/forget` stub (AM-X.3 bonus)** — currently lies. Wire it or remove it; do not let it stay.

---

## Definition of done

- Each primitive (TTL honor, update, filtered retrieve, sweeper) has tests covering happy path, edge cases, and at least one regression scenario from the dry-run script.
- OpenAPI schema updated and accurate; consumers can regenerate clients against it.
- The three dry-run gaps (no update, no time/metadata filter, no real eviction within minutes) are no longer reproducible. A short follow-up dry-run script (Annie roleplay storing + updating + retrieving meals across a simulated day) passes end-to-end.
- No breaking changes to existing `/v1/memories/direct` callers — existing integrations pass their tests unchanged.
- AM-X.4 (active-context query) recorded as **decided: build in consumer, not substrate.**

---

## Open questions for fenny / david before build

1. **Soft-delete?** Should `DELETE` and the sweeper move to tombstone-with-grace-period to support undo and easier debugging, or stay hard-delete? Today: hard-delete via Chroma. Recommend: stay hard for MVP, file follow-up if user asks for undo.
2. **In-process vs external sweeper?** APScheduler in-process is simplest; an external worker isolates failure and scales horizontally. Recommend: in-process for v1 — service is single-instance and the sweep is cheap.
3. **PATCH embedding regen — sync or async?** Recommend: sync for v1; surface duration in response. Revisit if measurements show > 500ms p95.
4. **TTL contract: hard or soft?** Is "memory definitely gone after T" or "eligible for eviction after T, may linger up to one sweep cycle"? Recommend: **soft contract documented clearly**, with sweep-cycle cadence in the OpenAPI description.

---

## Recommended build order (parminder)

If only 2 days: **AM-X.0 → AM-X.3 → AM-X.1 → AM-X.2.** Reasoning: X.0 is 5 LOC and immediately makes per-fact TTL real for the existing API. X.3 is 20 LOC and makes TTL semantics actually mean something. X.1 (PATCH) is the highest-value new endpoint. X.2 (filters) unblocks the consumer's "today's context" composer. Ship in that order; each is independently shippable.

If 4 days: same order, plus the typed-table update fan-out, `/v1/forget` cleanup, and a hardened follow-up dry-run script.

---

## Files referenced (absolute paths)

- `/Users/ankit/dev/agentic-memories/src/routers/memories.py` — `POST /v1/memories/direct` (line 320), `DELETE` (line 718), TTL gate (lines 450-457)
- `/Users/ankit/dev/agentic-memories/src/services/storage.py` — `_ttl_epoch_from_ttl` (lines 30-34), ISO timestamp (line 42), `content_hash` (line 47)
- `/Users/ankit/dev/agentic-memories/src/services/retrieval.py` — `where`-dict whitelist (lines 117-122)
- `/Users/ankit/dev/agentic-memories/src/services/forget.py` — `ttl_cleanup` (line 24), uses `$lte` (line 32)
- `/Users/ankit/dev/agentic-memories/src/services/compaction_graph.py` — calls `ttl_cleanup` once daily (line 513)
- `/Users/ankit/dev/agentic-memories/src/app.py` — `GET /v1/retrieve` (line 1099), scheduler setup (lines 264-279), `/v1/forget` stub (lines 1685-1687)
- `/Users/ankit/dev/agentic-memories/src/config.py` — `get_default_short_term_ttl_seconds` (line 154)
- `/Users/ankit/dev/agentic-memories/src/schemas.py` — `DirectMemoryRequest`, `NarrativeRequest` (line 232)
