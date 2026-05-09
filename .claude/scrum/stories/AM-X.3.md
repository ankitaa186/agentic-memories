# Story AM-X.3 — Fast eviction sweeper

**Epic:** AM-X (Memory Primitives)
**Status:** implemented
**Priority:** P0
**Author:** Disha (refined from Parminder's epic notes)
**Architect approval:** Parminder (2026-05-08; amended 2026-05-08 after dead-code discovery, re-acked by Parminder; amended 2026-05-08 after 3-Parminder deep audit; re-acked 2026-05-08 GREEN with one polish item folded into AC13 — Redis lock TTL note)
**Estimate:** ~30 LOC (job + `/v1/forget` wiring) + tests; ~half day
**Build order:** 2nd (per Parminder's recommended order)

## User need
A memory whose TTL has elapsed is no longer returned by retrieve within minutes, not "up to 24 hours past expiry." Today a 12h TTL can effectively last 36h because the sweeper only fires once daily inside the compaction graph at 00:00 UTC.

## Acceptance criteria
- [x] AC1: A new APScheduler job named `ttl_sweep` is registered in `_start_scheduler` and runs every 15 minutes by default.
- [x] AC2: Sweep cadence is configurable via env `TTL_SWEEP_INTERVAL_MINUTES` (default `15`); documented in `env.example` and surfaced in OpenAPI for `/v1/forget`.
- [x] AC3: The sweep job calls `ttl_cleanup()` AND `ttl_cleanup_timescale()` from `src/services/compaction_ops.py` (the live copies at `:54` and `:383` respectively, already imported by `src/services/compaction_graph.py:13-14`) — matching what the daily compaction graph does at `src/services/compaction_graph.py:513` and `:521`. (Drift fix: the epic only mentions `ttl_cleanup`; the daily path also runs `ttl_cleanup_timescale` and the new sweeper must too, otherwise short-tail facts in typed Postgres tables linger. Amendment 2026-05-08: retargeted from `forget.py` to `compaction_ops.py` after audit confirmed `forget.py:ttl_cleanup` is dead code with zero callers.)
- [x] AC4: Sweeper failures are observable: a `[sched.ttl_sweep]` log line records `attempted`, `chroma_deleted`, `timescale_deleted`, and any exception with traceback. A failure does NOT corrupt non-expired data and does NOT stop the next scheduled run.
- [x] AC5: Sweep does not race destructively with active writes: query uses a 60-second grace window — `ttl_epoch <= now - 60` instead of `ttl_epoch <= now`. (See risks section of the epic; baked in here.)
- [x] AC6: Daily compaction continues to run as-is at 00:00 UTC — this is purely additive.
- [x] AC7: Bonus cleanup — `POST /v1/forget` at `src/app.py:1685-1687` is wired up to actually call `ttl_cleanup()` + `ttl_cleanup_timescale()` (synchronously, in-process) and return real counts. It must no longer lie about `jobs_enqueued`. Response shape: `{"chroma_deleted": int, "timescale_deleted": int, "dry_run": bool}`.
- [x] AC8: When `body.dry_run is True`, `/v1/forget` reports the count it *would* delete without performing the delete (use a `where`-only `get` to count).
- [x] AC9: Tests:
  - Unit: `ttl_cleanup` with the 60s grace window — a memory whose `ttl_epoch` is `now - 30` is NOT deleted; one whose `ttl_epoch` is `now - 120` IS deleted. Same predicate test for `ttl_cleanup_timescale`. Both functions get `grace_seconds: int = 0` parameter; the default `0` preserves the existing daily-compaction call sites at `compaction_graph.py:513` and `:521` unchanged. The sweeper passes `grace_seconds=60` to **both** (the active-write race applies to Timescale episodic/emotional writes too, not just Chroma) — confirmed by Parminder during 2026-05-08 re-ack.
  - Integration: `/v1/forget` returns real counts and reflects actual ChromaDB state.
  - Scheduler: with `SCHEDULED_MAINTENANCE_ENABLED=true`, the job is registered. (Patch `BackgroundScheduler` for the test.)
- [x] AC10: README or `docs/architecture.md` gets a one-paragraph note about the new sweep cadence and the soft TTL contract.
- [x] AC11: Delete the dead code in `src/services/forget.py`. Verified during the 2026-05-08 backward-compat audit (3 independent passes + Parminder re-verification) that the following are dead — zero callers anywhere in `src/`, `tests/`, `migrations/`, `scripts/`, or top-level files:
  - `forget.py:ttl_cleanup` (lines ~24-42) — zero callers; broken-if-revived (hardcodes `client.get_collection("memories")` instead of `_standard_collection_name()`).
  - `forget.py:simple_deduplicate` (lines ~45-98) — zero callers; same dead-by-the-same-logic story (`compaction_graph` imports the dedup function from `compaction_ops`); also slower naive O(N²) version vs. the live `compaction_ops` numpy/embedding-reuse implementation.
  - `forget.py:_get_collection` (the local helper, ~lines 16-21) — only used by the two dead functions above; remove with them.
  - **Keep** `forget.py:run_compaction_for_user` — it is live and called from 3 sites in `app.py`. Do NOT delete it.
  - Drop now-unused imports from `forget.py` (`get_chroma_client`, `generate_embedding`, `datetime`, etc.) after the deletions. Run `ruff` to confirm clean.
  - Search docs/comments for any remaining `forget.py:ttl_cleanup` or `forget.py:simple_deduplicate` references and update them to point at `compaction_ops.py`.
  - Rationale for cleaning both functions in this story (not deferring): leaving the second dead function creates a future trap where someone imports the wrong-collection version. Cheaper to remove now while we're already in the file. (Per Parminder's re-ack note.)

### Audit-additions (added 2026-05-08 after 3-Parminder deep audit)
- [x] AC12: **APScheduler explicit kwargs.** When registering the `ttl_sweep` job in `_start_scheduler`, pass explicit `coalesce=True, max_instances=1, misfire_grace_time=60` to `add_job`. Defaults inherit but explicit-is-better for self-documenting scheduler behavior. Confirms: a stuck-running sweep silently skips the next tick (no piling up); a missed sweep within 60s grace still runs.
- [x] AC13: **Redis sweep lock.** The sweep job acquires a `ttl_sweep_lock` Redis lock (5-min TTL) before running; if the lock is held (because daily compaction at 00:00 UTC, a manual `/v1/forget` call, or a previous overlapping sweep is in flight) the sweep skips silently and logs `[sched.ttl_sweep] skipped: lock held`. Pattern matches the existing `compaction_lock:daily` at `src/app.py:209-217`. Without this, daily compaction's `node_ttl` and the new sweep both call `ttl_cleanup` against the same predicate at 00:00 UTC — idempotent so no corruption, but per-job log counts double-count, hurting observability. **Code comment note:** the 5-min TTL is fine because `ttl_cleanup`/`ttl_cleanup_timescale` are millisecond-scale operations (single Chroma `where` query + delete; single Postgres `DELETE WHERE`); auto-expiring mid-sweep would only be possible on a degenerately-large dataset. Document this so the next maintainer doesn't tighten the TTL prematurely or worry about lock loss mid-run.
- [x] AC14: **Cache `_standard_collection_name()`.** `src/services/retrieval.py:_standard_collection_name()` currently calls `generate_embedding('dimension-probe')` per-invocation for dimension detection. Add `@lru_cache(maxsize=1)` to it (or to the dimension-probe call within it). The sweeper runs every 15min — without caching, that's ~96 unnecessary embedding-API calls per day for dimension probing. Verify no caller depends on the function NOT being cached (i.e., on dimension changing mid-process). If any does, fall back to a process-local memo within the sweeper job.
- [x] AC15: **Dry-run no-delete assertion.** Integration test for `/v1/forget` with `body.dry_run=True`: store a memory with `ttl_epoch <= now`, call `/v1/forget` with `dry_run=True`, assert response shows `chroma_deleted: 0` (or non-zero count if AC8 returns the would-delete count under a different field name) AND a follow-up `GET /v1/retrieve` still returns the memory. Catches the trivial bug where `dry_run` is accepted but ignored.
- [x] AC16: **`ForgetRequest.jobs` field disposition.** The `jobs` field on `ForgetRequest` (`src/schemas.py:151-157`) is ignored by the new wiring — `/v1/forget` runs `ttl_cleanup + ttl_cleanup_timescale` regardless of `body.jobs`. Decision: keep the field but add a one-line OpenAPI note: "reserved for future use; currently ignored." Non-breaking, leaves room for a future routing knob. Echo the field back in the response shape under `jobs_requested: [str]` for caller debuggability. (Recommended over removal: removal is breaking; keeping with the disclaimer documents the no-op behavior explicitly.)

## Files to touch
- `/Users/ankit/dev/agentic-memories/src/app.py` — `_start_scheduler` (around line 264): add the new job with explicit `coalesce=True, max_instances=1, misfire_grace_time=60` (AC12). `/v1/forget` at lines 1685-1687: wire to real implementation (importing from `src/services/compaction_ops.py`, NOT `forget.py`); echo `body.jobs` back as `jobs_requested` per AC16. The sweep job body acquires `ttl_sweep_lock` Redis lock (5-min TTL) before running per AC13; pattern matches `compaction_lock:daily` at `src/app.py:209-217`.
- `/Users/ankit/dev/agentic-memories/src/services/retrieval.py` — add `@lru_cache(maxsize=1)` to `_standard_collection_name()` (or the dimension-probe call within it) per AC14.
- `/Users/ankit/dev/agentic-memories/src/schemas.py:151-157` — add OpenAPI description note on `ForgetRequest.jobs`: "reserved for future use; currently ignored." Add `jobs_requested: list[str]` to the response shape per AC16.
- `/Users/ankit/dev/agentic-memories/src/services/compaction_ops.py:54` — extend `ttl_cleanup` signature: `def ttl_cleanup(grace_seconds: int = 0) -> int`. Default `0` preserves the existing daily-compaction call site at `compaction_graph.py:513` unchanged.
- `/Users/ankit/dev/agentic-memories/src/services/compaction_ops.py:383` — mirror the change on `ttl_cleanup_timescale` (`grace_seconds: int = 0`); sweeper passes `grace_seconds=60` to it as well (active-write race applies to Timescale, not just Chroma).
- `/Users/ankit/dev/agentic-memories/src/services/forget.py` — DELETE the dead `ttl_cleanup` function (~lines 24-42), the dead `simple_deduplicate` function (~lines 45-98), and the local `_get_collection` helper (~lines 16-21) used only by those two. **Keep** `run_compaction_for_user` (live, called from 3 sites in `app.py`). Drop now-unused imports.
- `/Users/ankit/dev/agentic-memories/src/config.py` — new `get_ttl_sweep_interval_minutes()` helper, lru_cached, default 15.
- `/Users/ankit/dev/agentic-memories/env.example` — document `TTL_SWEEP_INTERVAL_MINUTES`.
- `tests/unit/` — sweeper grace-window test + `/v1/forget` real-counts test.

## Out of scope
- External worker / horizontal-scale sweeper (open-question 2 resolved: in-process for v1).
- Tombstone / soft-delete (open-question 1 resolved: stay hard-delete for MVP).

## Architect notes (Parminder)
- In-process APScheduler is sufficient — service is single-instance and the sweep is cheap (one Chroma `where` per call).
- The 60s grace window is the cleanest fix for the sweeper-vs-active-write race. It costs us 60s of "stale memory still retrievable" which is well within the soft-TTL contract.
- `ttl_cleanup()` already handles the empty-list and exception cases gracefully — keep that pattern in the new code path.

### Amendment 2026-05-08 — dead-code discovery
During the backward-compat audit, three independent David passes confirmed that `src/services/forget.py:24:ttl_cleanup` has zero callers anywhere in the repo. There are two `ttl_cleanup` symbols in the codebase: the dead one in `forget.py` and a separate live one at `src/services/compaction_ops.py:54`. The live copy is what `compaction_graph.py:13-14` imports and what daily compaction at `compaction_graph.py:513` actually calls. `ttl_cleanup_timescale` exists ONLY at `compaction_ops.py:383` — there is no `forget.py` equivalent.

Decision (delete vs delegate): **delete** the `forget.py` copy and **extend** the `compaction_ops.py` copy. Two reasons: (1) zero callers means deletion is risk-free, (2) the dead copy is also broken-if-revived — it hardcodes `client.get_collection("memories")` instead of using `_standard_collection_name()` (the dimension-suffixed convention every other call site uses), so it would silently query the wrong (or non-existent) collection. Keeping it would invite a future bug where someone imports the wrong symbol.

The amendment retargets AC3 and AC9, adds AC11 to delete the dead function, and updates the Files-to-touch list. The build order, estimate, and parallelism plan are unchanged.

## Open-question resolutions baked in
- **Soft-delete?** No. Hard-delete via Chroma. (Open Q1.)
- **In-process vs external sweeper?** In-process. (Open Q2.)
- **TTL contract: hard or soft?** Soft, documented in OpenAPI + README. (Open Q4.)
