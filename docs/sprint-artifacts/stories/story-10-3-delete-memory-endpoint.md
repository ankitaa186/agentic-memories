# Story 10.3: Delete Memory Endpoint

**Epic:** 10 - Direct Memory API
**Story ID:** 10-3
**Status:** review
**Dependencies:** Story 10.1 (Direct Store ChromaDB)
**Blocked By:** 10-1-direct-memory-store-endpoint-chromadb

---

## Goal

Implement cross-storage memory deletion via `DELETE /v1/memories/{memory_id}`.

## Acceptance Criteria

### AC #1: Endpoint Creation

**Given** a client sends `DELETE /v1/memories/{memory_id}?user_id={user_id}`
**When** the request is processed
**Then**:

- [x] `memory_id` is accepted as path parameter
- [x] `user_id` is required as query parameter
- [x] Returns `DeleteMemoryResponse`

### AC #2: Authorization

**Given** a memory exists with a specific `user_id` in metadata
**When** a client attempts to delete with a different `user_id`
**Then**:

- [x] Return HTTP 403 Forbidden
- [x] Return message "Unauthorized: memory belongs to different user"
- [x] Do NOT delete from any storage backend

### AC #3: ChromaDB Deletion

**Given** a valid delete request with authorized `user_id`
**When** the endpoint processes the request
**Then**:

- [x] Get memory metadata first (to find `stored_in_*` flags)
- [x] Delete from ChromaDB collection
- [x] Return "Memory not found" if ID doesn't exist

### AC #4: Typed Table Deletion

**Given** memory has `stored_in_*` flags in metadata
**When** the memory is deleted
**Then**:

- [x] If `stored_in_episodic` → DELETE FROM episodic_memories
- [x] If `stored_in_emotional` → DELETE FROM emotional_memories
- [x] If `stored_in_procedural` → DELETE FROM procedural_memories
- [x] Typed table failures are best-effort (log, continue)

### AC #5: Response

**Given** deletion completes
**When** the response is generated
**Then**:

- [x] Return deletion status per backend in `storage` dict
- [x] Return `deleted: true` only if ChromaDB succeeded
- [x] Return appropriate error messages for failures

## Technical Notes

### Implementation Flow
```
DELETE /v1/memories/{memory_id}?user_id={user_id}
    │
    ▼
1. Get memory metadata from ChromaDB (includes stored_in_* flags)
    │
    ▼
2. Verify user_id matches metadata.user_id (403 if not)
    │
    ▼
3. Delete from ChromaDB
    │
    ▼
4. Delete from typed tables based on flags
    │
    ▼
5. Return DeleteMemoryResponse with storage status
```

### Helper Functions
- `_delete_from_episodic(memory_id, user_id)`
- `_delete_from_emotional(memory_id, user_id)`
- `_delete_from_procedural(memory_id, user_id)`

### Error Handling
| Scenario | Response |
|----------|----------|
| Memory not found | status: error, deleted: false, message: "Memory not found" |
| Unauthorized | HTTP 403 |
| ChromaDB delete failed | status: error, deleted: false |
| Typed table failed | Log error, set flag false, continue |

## Tasks

- [x] Add `delete_memory()` endpoint function
- [x] Implement ChromaDB metadata retrieval
- [x] Implement authorization check (compare user_id)
- [x] Implement ChromaDB deletion
- [x] Implement `_delete_from_episodic()` helper
- [x] Implement `_delete_from_emotional()` helper
- [x] Implement `_delete_from_procedural()` helper
- [x] Add conditional typed table deletion based on flags
- [x] Implement response building with storage status
- [x] Add logging for observability

## Definition of Done

- [x] All acceptance criteria met
- [x] Cross-storage deletion works correctly
- [x] Authorization verified (403 for wrong user)
- [x] Best-effort typed table deletion
- [x] No linting errors
- [x] PR ready for review

## Estimated Effort

3 hours

---

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/stories/10-3-delete-memory-endpoint.context.xml`

### Debug Log

**Implementation Plan (2025-12-29):**
1. Add `delete_memory()` DELETE endpoint to memories router with path param and query param
2. Implement ChromaDB metadata retrieval via collection.get(ids=[memory_id])
3. Implement authorization check (compare user_id from request with metadata.user_id)
4. Implement ChromaDB deletion via collection.delete(ids=[memory_id])
5. Implement `_delete_from_episodic()`, `_delete_from_emotional()`, `_delete_from_procedural()` helpers
6. Add conditional typed table deletion based on stored_in_* flags
7. Implement DeleteMemoryResponse building with per-backend storage status
8. Add comprehensive logging for observability

**Note:** Updated V2Collection.get() method in chroma.py to support IDs parameter for fetching by memory ID.

### Completion Notes

**Summary:** Implemented DELETE /v1/memories/{memory_id} endpoint with cross-storage deletion support.

**Key Implementation Details:**
- Endpoint accepts memory_id as path parameter and user_id as required query parameter
- Authorization check compares request user_id with metadata.user_id, returns HTTP 403 on mismatch
- Retrieves stored_in_* flags from ChromaDB metadata to determine which typed tables to clean up
- Typed table deletion (episodic, emotional, procedural) is best-effort - errors are logged but don't fail the request
- ChromaDB deletion is required for success - if it fails, deleted=false is returned
- Response includes per-backend deletion status in storage dict

**Test Results:** All 388 unit tests pass.

### File List

| File | Change Type |
|------|-------------|
| src/routers/memories.py | Modified - Added delete_memory endpoint and helper functions |
| src/dependencies/chroma.py | Modified - Added ids parameter to V2Collection.get() method |

### Change Log

| Date | Change |
|------|--------|
| 2025-12-29 | Implemented DELETE /v1/memories/{memory_id} endpoint with cross-storage deletion |
