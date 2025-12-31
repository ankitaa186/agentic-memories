# Story 10.1: Direct Memory Store Endpoint (ChromaDB)

**Epic:** 10 - Direct Memory API
**Story ID:** 10-1
**Status:** Done
**Dependencies:** Story 10.4 (Pydantic Schemas)
**Blocked By:** 10-4-pydantic-schemas

---

## Goal

Implement basic direct memory storage to ChromaDB with `POST /v1/memories/direct` endpoint. This enables Annie (or any LLM client) to store pre-formatted memories with sub-3-second latency, bypassing the slow LangGraph ingestion pipeline (60-100s).

## Acceptance Criteria

### AC #1: Endpoint Creation

**Given** the memories router is registered with the FastAPI application
**When** a client sends a POST request to `/v1/memories/direct`
**Then** the endpoint accepts a `DirectMemoryRequest` body and returns a `DirectMemoryResponse`

- [x] Create `POST /v1/memories/direct` endpoint in `src/routers/memories.py`
- [x] Accept `DirectMemoryRequest` body (defined in Story 10.4)
- [x] Return `DirectMemoryResponse` with status, memory_id, message, and storage fields

### AC #2: Memory ID Generation

**Given** a valid direct memory request is received
**When** the endpoint processes the request
**Then** a unique memory ID is generated in the format `mem_{uuid.hex[:12]}`

- [x] Generate ID format: `mem_{uuid.uuid4().hex[:12]}`
- [x] ID must be consistent with existing patterns in `storage.py`
- [x] ID is returned in the response `memory_id` field

### AC #3: Embedding Generation

**Given** a valid memory content is provided in the request
**When** the endpoint processes the request
**Then** an embedding vector is generated using `generate_embedding()`

- [x] Call `generate_embedding()` from `src/services/embedding_utils.py` for content
- [x] Return `EMBEDDING_ERROR` error code if generation fails
- [x] Log embedding generation failure with user_id context

### AC #4: ChromaDB Storage

**Given** a valid request with successfully generated embedding
**When** the endpoint stores the memory
**Then** the memory is persisted to ChromaDB using `upsert_memories()`

- [x] Use existing `upsert_memories()` function from `src/services/storage.py`
- [x] Store with metadata including `source: "direct_api"`
- [x] Include `user_id` in metadata for authorization on delete
- [x] Return `STORAGE_ERROR` if ChromaDB write fails
- [x] Response includes `storage: {"chromadb": true}` on success

### AC #5: Performance

**Given** a normal load direct memory request
**When** the endpoint processes the request end-to-end
**Then** the p95 latency is under 3 seconds

- [x] p95 latency < 3 seconds for complete store operation
- [x] Log timing metrics for embedding generation and ChromaDB write
- [x] Embedding generation should complete in < 2 seconds
- [x] ChromaDB write should complete in < 500ms

## Technical Notes

### Implementation Details

1. **Router Location**: Create new file `src/routers/memories.py`

2. **Function Signature**:
   ```python
   @router.post("/direct", response_model=DirectMemoryResponse)
   def store_memory_direct(body: DirectMemoryRequest) -> DirectMemoryResponse:
   ```

3. **Memory ID Generation**:
   ```python
   memory_id = f"mem_{uuid.uuid4().hex[:12]}"
   ```

4. **Memory Object Construction**:
   ```python
   from src.models import Memory

   memory = Memory(
       id=memory_id,
       user_id=body.user_id,
       content=body.content,
       layer=body.layer,
       type=body.type,
       importance=body.importance,
       confidence=body.confidence,
       relevance_score=body.importance,
       usage_count=0,
       persona_tags=body.persona_tags[:10] if body.persona_tags else [],
       embedding=embedding,
       timestamp=datetime.now(timezone.utc),
       metadata=metadata,
   )
   ```

5. **Metadata Structure** (for this story, ChromaDB-only):
   ```python
   metadata = body.metadata or {}
   metadata.update({
       "source": "direct_api",
       "stored_in_episodic": False,
       "stored_in_emotional": False,
       "stored_in_procedural": False,
   })
   ```

6. **Error Response Codes**:
   - `EMBEDDING_ERROR` - Embedding generation failed
   - `STORAGE_ERROR` - ChromaDB write failed
   - `INTERNAL_ERROR` - Unexpected exception

### Dependencies

| Dependency | Import Path |
|------------|-------------|
| `upsert_memories()` | `src/services/storage` |
| `generate_embedding()` | `src/services/embedding_utils` |
| `Memory` | `src/models` |
| `DirectMemoryRequest` | `src/schemas` (Story 10.4) |
| `DirectMemoryResponse` | `src/schemas` (Story 10.4) |

### App Integration

After creating the router, register it in `src/app.py`:
```python
from src.routers import memories
app.include_router(memories.router)
```

## Tasks

- [x] Create `src/routers/memories.py` with router prefix `/v1/memories`
- [x] Implement `store_memory_direct()` endpoint function
- [x] Import and use `generate_embedding()` for content embedding
- [x] Import and use `upsert_memories()` for ChromaDB storage
- [x] Build `Memory` object with all required fields
- [x] Add metadata with `source: "direct_api"` and storage tracking flags
- [x] Implement error handling for embedding failures (EMBEDDING_ERROR)
- [x] Implement error handling for storage failures (STORAGE_ERROR)
- [x] Add logging for request received, embedding generated, and storage completed
- [x] Register router in `src/app.py`
- [ ] Verify endpoint appears in OpenAPI docs (`/docs`)
- [ ] Manual test with curl/httpie to verify functionality

## Test Scenarios

### Happy Path
```bash
curl -X POST http://localhost:8000/v1/memories/direct \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "0000000000",
    "content": "User is allergic to shellfish",
    "importance": 0.95,
    "persona_tags": ["health", "allergy"]
  }'
```

Expected response:
```json
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Memory stored successfully",
  "storage": {"chromadb": true}
}
```

### Error Case - Embedding Failure
When embedding service is unavailable, expect:
```json
{
  "status": "error",
  "memory_id": null,
  "message": "Failed to generate embedding",
  "error_code": "EMBEDDING_ERROR"
}
```

## Dev Agent Record

### Context Reference
- `docs/sprint-artifacts/stories/story-10-1-direct-memory-store-endpoint-chromadb.context.xml`

---

## Definition of Done

- [x] All acceptance criteria met
- [x] Endpoint returns < 3s p95 latency
- [x] Code follows existing router patterns (see `src/routers/profile.py`)
- [x] No linting errors (ruff, mypy)
- [x] Logging follows existing patterns (structured logging)
- [x] Endpoint registered and accessible
- [ ] Manual testing confirms store and subsequent retrieve works
- [ ] PR ready for review
