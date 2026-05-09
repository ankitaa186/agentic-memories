# Story AM-X.1 — Update primitive: `PATCH /v1/memories/{memory_id}`

**Epic:** AM-X (Memory Primitives)
**Status:** implemented
**Priority:** P0
**Author:** Disha (refined from Parminder's epic notes)
**Architect approval:** Parminder (2026-05-08; amended 2026-05-08 after 3-Parminder deep audit; re-acked 2026-05-08 GREEN with one polish item folded into AC13 — partial-failure HTTP status)
**Estimate:** ~350 LOC + tests; ~1 day (LOC bumped from ~250 after audit — typed-table fan-out needs 3 NEW `_update_*` helpers; `_rollback_typed_tables` (DELETE-only) and `_store_*` (INSERT-only) cannot be reused for UPDATE.)
**Build order:** 3rd (per Parminder's recommended order)

## User need
A consumer can modify the content, metadata, importance, layer, or TTL of an existing memory by ID without the delete-and-recreate workaround. The current workaround loses `memory_id` continuity, races against concurrent reads, and is fragile.

## Acceptance criteria

### Identity & immutability
- [x] AC1: Updating a memory preserves its `id` and `created_at`/original `timestamp`.
- [x] AC2: Immutable fields (any attempt to change them returns 422 with a clear error): `id`, `user_id`, `created_at`/`timestamp`, `typed_table_id`.
- [x] AC3: A `user_id` mismatch between the call's authorization context and the stored record returns 403.
- [x] AC4: Updating a non-existent or already-deleted ID returns 404 with a clear error.

### Mutable fields
- [x] AC5: Any subset of `{content, metadata, layer, importance, ttl_seconds}` can be supplied; partial updates are valid (omitted fields unchanged).
- [x] AC6: When `content` changes, the embedding is regenerated and the search index reflects the new content on the next retrieve.
- [x] AC7: Idempotency: when the new `content` produces the same `content_hash` as the stored one, embedding regen is **skipped** (no Chroma `update` of `embeddings=`, just metadata update if any). Response surfaces `embedding_regenerated: bool`.
- [x] AC8: Metadata semantics are **shallow merge**, not replace. A sentinel value `"__delete__"` removes a key. System-managed fields (the shared `SYSTEM_MANAGED_FIELDS` constant — see AC19) cannot be set or deleted via PATCH metadata; attempts return 422.
- [x] AC9: When `ttl_seconds` is supplied, `ttl_epoch` is recomputed from `now()` (not from `created_at`); semantics match AM-X.0 (honored on all layers). Setting `ttl_seconds: null` (explicit JSON null, distinguishable from omitted) clears the TTL.

### Layer changes
- [x] AC10: A layer change *between non-typed layers* (e.g., `short-term` ↔ `semantic` ↔ `long-term`) is allowed.
- [x] AC11: A layer flip *into or out of* a typed-storage layer (e.g., `semantic` → `episodic`) returns 422 in v1 with an explicit error message: "layer flip into/out of typed-storage layer not supported in v1; delete and recreate."

### Typed-table fan-out
- [x] AC12: If the stored record has any `stored_in_*: true` flag, the PATCH issues a best-effort UPDATE on the typed-table row by `typed_table_id`. Supported fields on typed tables in MVP:
  - **episodic**: `content`, `importance` (→ `importance_score`), `metadata`.
  - **emotional**: `content` (→ `context` column), `metadata`. **`importance` is silently skipped on emotional fan-out** because the table has no `importance_score` column; the value still lands in Chroma metadata which is the source of truth.
  - **procedural**: `content` (→ `context` column), `metadata`. **`importance` is silently skipped on procedural fan-out** for the same reason as emotional.
  Anything else affecting typed tables returns 422. (Reconciled 2026-05-08 post-Harpreet review: original AC text said importance → 422 for emotional/procedural; implementation is silent-skip + Chroma-as-SoT, consistent with the broader best-effort fan-out pattern. AC text now matches implementation; storage-helper docstrings updated to match.)
- [x] AC13: Typed-table update follows the existing best-effort fan-out pattern from `_rollback_typed_tables` / DELETE — partial failures log warnings but do not roll back the Chroma update. Response shape splits each surface into its own flag so clients can detect partial failures: `{chroma_updated: bool, typed_table_updated: {episodic: bool, emotional: bool, procedural: bool} | null, embedding_regenerated: bool, embedding_regen_duration_ms: int, warnings: [str]}`. `typed_table_updated` is `null` when the record has no `stored_in_*` flags set (i.e., no typed-table fan-out applies). **HTTP status on partial failure:** 200 with warnings populated (matches the existing DELETE fan-out pattern); NOT 207 multi-status. Caller inspects per-surface flags to detect partial drift.

### Concurrency & observability
- [x] AC14: Embedding regen is **synchronous** for v1. (Open-question 3 resolved.) The response includes `embedding_regen_duration_ms` (0 when skipped) so we can monitor and decide later whether to flip async.
- [x] AC15: A retrieve immediately following a PATCH returns the new content (after any embedding regen).
- [x] AC16: PATCH does not race destructively with the eviction sweeper from AM-X.3 — the sweeper's 60s grace window covers this case.

### Tests
- [x] AC17: Unit + integration coverage for: identity preservation, immutable-field rejection, 403 on user mismatch, 404 on missing, partial updates of each mutable field, embedding-regen-on-content-change, content-hash-skip, shallow metadata merge, `__delete__` sentinel, system-managed-field protection, `ttl_seconds` recompute, explicit-null-clears-ttl, allowed/disallowed layer flips, typed-table fan-out happy path, typed-table fan-out partial failure, sweeper-grace-window race coverage.
- [x] AC18: At least one E2E test that round-trips the "Annie updates her meals at lunch" scenario: store → retrieve → patch → retrieve, asserting `memory_id` continuity and content freshness.

### Defense-in-depth & cross-story alignment
- [x] AC19: **Shared `SYSTEM_MANAGED_FIELDS` constant.** Both X.1's PATCH protection list (router level + storage level) AND X.2's `metadata_filter` rejection list import from a single new module-level constant `SYSTEM_MANAGED_FIELDS` (recommended location: `src/services/_constants.py` or top of `src/services/storage.py`). The constant enumerates: `user_id, layer, type, ttl_epoch, timestamp, content_hash, stored_in_episodic, stored_in_emotional, stored_in_procedural, typed_table_id`. A unit test asserts the constant is not duplicated in either X.1 or X.2 code paths.
- [x] AC20: **Storage-layer defensive guard.** `update_chroma_record` (or whatever helper PATCH uses to call Chroma's `collection.update`) MUST strip system-managed keys before writing — defense-in-depth on top of the router-level AC8 protection. The list is the shared `SYSTEM_MANAGED_FIELDS` constant from AC19. This guards against future internal callers reusing the helper without router-level validation.
- [x] AC21: **Explicit-null E2E test.** An E2E test sends raw JSON `{"ttl_seconds": null}` over the wire (using `httpx.AsyncClient` against the running app, NOT a Pydantic-constructed request) and asserts the stored Chroma metadata has `ttl_epoch` removed. Mirrors the auto-memory pitfall on Pydantic key-name handling — the sentinel scheme must survive the JSON-to-Pydantic round-trip in production.
- [x] AC22: **Retry semantics on partial typed-table failure.** When PATCH receives identical content (same `content_hash`) but the previous request had a typed-table partial failure (`typed_table_updated: false` for one or more tables), the retry MUST re-attempt the typed-table UPDATE even though embed-regen is correctly skipped. Caller should not be required to send different content to recover from partial failure. Implementation: PATCH always issues typed-table UPDATEs when applicable, regardless of `content_hash`; only the embedding write is short-circuited.
- [x] AC23: Tests for AC19/AC20/AC22 — dedicated unit tests for the constant's single-source-of-truth invariant, the storage-helper guard (call helper directly with a system-managed key in payload, assert it's stripped), and the partial-failure retry path (mock typed-table call to fail once, then succeed; PATCH twice with same content; assert second call retries the typed-table UPDATE).

## Files to touch
- `/Users/ankit/dev/agentic-memories/src/routers/memories.py` — new `@router.patch("/{memory_id}")` handler placed near the existing `DELETE` at line 718. Reuse `_rollback_typed_tables`-style fan-out for typed-table updates.
- `/Users/ankit/dev/agentic-memories/src/schemas.py` — new `PatchMemoryRequest` and `PatchMemoryResponse`. `PatchMemoryRequest` uses `Optional[...]` for each mutable field; for `ttl_seconds`, use a sentinel (e.g., a module-level `UNSET` constant or `Field(default=...)` discriminator) so explicit-null is distinguishable from "omitted".
- `/Users/ankit/dev/agentic-memories/src/services/storage.py` — extract a small `update_chroma_record(...)` helper if the router would otherwise grow too large; it must use Chroma's `collection.update(ids=, documents=, embeddings=, metadatas=)` (NOT delete+recreate). Helper MUST strip `SYSTEM_MANAGED_FIELDS` keys from incoming metadata as defense-in-depth (AC20). Plus 3 NEW `_update_*` helpers for typed-table UPDATE fan-out (episodic/emotional/procedural) — `_rollback_typed_tables` (DELETE-only) and `_store_*` (INSERT-only) cannot be reused.
- `/Users/ankit/dev/agentic-memories/src/services/_constants.py` (new) OR top of `src/services/storage.py` — define `SYSTEM_MANAGED_FIELDS` constant per AC19. Imported by both X.1 PATCH router/storage code and X.2 `metadata_filter` validator.
- `tests/unit/test_memories_router.py` — most ACs.
- `tests/integration/test_direct_memory_api.py` — fan-out + retrieve-after-patch.
- `tests/e2e/` — Annie meals round-trip.

## Out of scope
- Async embedding regen (revisit if p95 > 500ms — Open Q3).
- Soft-delete / tombstone undo (Open Q1: hard-delete stays).
- Bulk PATCH.
- Layer flips into/out of typed storage (deferred; 422 in v1).

## Architect notes (Parminder)
- The Chroma `collection.update()` API is the load-bearing detail — it preserves `memory_id` continuity, which is the whole point of this story over delete+recreate.
- The shallow-merge + `__delete__` sentinel matches what callers expect from PATCH semantics in REST. Replace-semantics would silently nuke `stored_in_*` flags on every PATCH; do not do that.
- The system-managed-field protection list (AC8) MUST stay in sync with `_build_metadata` in `src/services/storage.py:36-60`. Add a comment in both files cross-referencing each other.

## Open-question resolutions baked in
- **PATCH embedding regen — sync or async?** Sync. (Open Q3.) AC7+AC14 surface duration so we can revisit.
- **TTL contract: hard or soft?** Soft. AC9 wording reflects "expires in roughly N seconds" not "definitely gone after N seconds".

## Dependencies
- AM-X.0 (to share the all-layers TTL semantics for the `ttl_seconds` field on PATCH).
- AM-X.3: X.1's AC16 (PATCH-vs-sweeper race) is covered by X.3's grace window. X.1 SHOULD ship after X.3 to satisfy AC16; if shipped before, AC16 is verified once X.3 lands. Build order remains 3rd.


## Live-API bug fixes (2026-05-08)

Live-curl testing on the staged branch surfaced one BLOCKER bug not caught by the unit tests:

**Bug:** `V2Collection` (the custom Chroma v2 wrapper at `src/dependencies/chroma.py:187`) did not implement an `update()` method. Every PATCH `/v1/memories/{id}` returned HTTP 200 but with `chroma_updated: false` and warning `"chroma_update_failed: V2Collection object has no attribute update"`. The actual Chroma write failed 100% of the time.

**Why pytest missed it:** `tests/unit/test_memories_patch.py:54` mocks the collection with `MagicMock`, which auto-creates any attribute accessed. The integration tests at `tests/integration/test_direct_memory_api.py:814` (`TestPatchMemoryFanoutAndRetrieve`) also stubbed `update_chroma_record` directly so the wrapper layer was never exercised.

**Fix (~50 LOC):**
- Added `V2Collection.update(ids, documents=None, embeddings=None, metadatas=None)` in `src/dependencies/chroma.py`, mirroring the existing `upsert` HTTP pattern (POST `{collection_id}/update`, same metadata coercion for list/dict values). Signature matches the canonical chromadb `Collection.update` shape.
- Also fixed a latent bug while I was there: `V2Collection.get()` was sending `where: {}` on the no-filter branch, which Chroma 1.x rejects with `InvalidArgumentError`. Same in `V2Collection.query()`. Both now omit the key when the filter dict is empty.

**New tests:**
- `tests/integration/test_chroma_wrapper.py` (NEW, 5 tests) — exercises `V2Collection.update` against real Chroma at `localhost:8000` (skips cleanly when unreachable). Covers document-only / metadata-only / both / list-metadata coercion / empty-ids rejection.
- `tests/integration/test_direct_memory_api.py::TestPatchMemoryRealChromaSmoke::test_patch_round_trip_real_chroma` (NEW, 1 test) — does NOT mock `update_chroma_record`; seeds a record via the real `V2Collection.upsert`, calls `update_chroma_record`, reads back via `get_chroma_record`, asserts content + content_hash changed. Discovers the standard collection name + dim at runtime so it works against any Chroma deployment.

**Verification:** `pytest tests/unit tests/integration -q` → 660 passed, 1 skipped. `ruff check` clean.

AC verification: all 23 ACs still pass. AC13 (chroma_updated flag) was technically not satisfied in production despite the test mock saying it was — now resolved.


### Bug #3 — `__delete__` metadata sentinel was silently no-op (AC8)

**Live curl repro:** PATCH with `{"metadata": {"foo": "__delete__"}}` returned HTTP 200 + `chroma_updated: true` + no warnings, but the `foo` key remained in the persisted Chroma metadata.

**Root cause:** Chroma's `/update` endpoint does a SHALLOW MERGE on metadata — sending a metadatas payload without a key preserves the stored value. The router's `_shallow_merge_metadata` correctly *removed* the key from the merged dict, but the resulting dict-without-the-key was then sent to Chroma, which interpreted absence-of-key as "no change" and kept the old value. Verified live with a direct `/api/v2/.../update` curl probe on 2026-05-08: `metadatas: [{baz: 42}]` left `foo: "bar"` in place; `metadatas: [{foo: null}]` removed `foo`. So the wire-level fix is to send `key: null` for deleted keys.

**Fix (~30 LOC):**
- `src/services/storage.py:update_chroma_record` — added `delete_keys: Optional[List[str]] = None` parameter. When provided, each key is set to `None` in the metadata payload (overriding any value from `metadata` / `internal_metadata`), which Chroma's `/update` endpoint interprets as deletion.
- `src/routers/memories.py:patch_memory` — track `__delete__` sentinels in a `delete_keys: List[str]` list and pass it through to `update_chroma_record`. The existing `_shallow_merge_metadata` is preserved as-is because typed-table fan-out (JSONB `||` merge) wants the key absent, not null.

### Bug #4 — `ttl_seconds: null` did not clear `ttl_epoch` (AC9)

**Live curl repro:** PATCH with `{"ttl_seconds": null}` returned HTTP 200 + `chroma_updated: true`, but the `ttl_epoch` key remained at its old value in the persisted record.

**Root cause:** Same Chroma shallow-merge gotcha as Bug #3. The router correctly used the `_Unset` sentinel scheme to distinguish `ttl_seconds: null` from omitted, and then did `internal_metadata.pop("ttl_epoch", None)`. But pop-from-dict is the wrong primitive: it just doesn't include `ttl_epoch` in the payload, and Chroma then preserves the existing value. The schema-level Pydantic test at `tests/unit/test_memories_patch.py:707` was passing because it verified the *parsed model state*, not the *persistence outcome*.

**Fix (~6 LOC, in the same change as Bug #3):**
- `src/routers/memories.py:patch_memory` — when `ttl_seconds` is explicit-null, also append `"ttl_epoch"` to the `delete_keys` list (in addition to popping from `internal_metadata`, which keeps the dict consumed by other paths clean).

**New tests (live, no mocks of the storage helper):**
- `tests/integration/test_direct_memory_api.py::TestPatchMemoryRealChromaSmoke::test_patch_metadata_delete_sentinel_removes_key_in_chroma` — seeds a record with `foo: "bar", baz: 42` via real `V2Collection.upsert`, PATCHes via the real HTTP router (`TestClient`), asserts `foo` is absent and `baz` survives in the read-back.
- `tests/integration/test_direct_memory_api.py::TestPatchMemoryRealChromaSmoke::test_patch_ttl_seconds_null_clears_ttl_epoch_in_chroma` — seeds with `ttl_epoch=now+7200`, PATCHes raw `{"ttl_seconds": null}` JSON via TestClient, asserts `ttl_epoch` key is absent in read-back.

**Verification:** `pytest tests/unit tests/integration -q` → 560 passed, 1 skipped (560/560 of the unit+integration suite; the skipped one is unrelated). `ruff check` clean. The 2 new live-Chroma tests both PASS.

**Cross-cutting takeaway:** All four live-API PATCH bugs (Bugs #1, #2, #3, #4) shared the same blind spot — pytest mocks of the storage helper / model layer never exercised the wire-level Chroma update path. The `TestPatchMemoryRealChromaSmoke` class is the right place to add future live-API regression tests; mocked unit tests verify *intent* but cannot verify *persistence*.

