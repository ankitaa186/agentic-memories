# Tech Spec: Epic 10 - Direct Memory API for Explicit Memory Management

**Epic ID:** 10
**Document Version:** 1.0
**Generated:** 2025-12-29
**Status:** Ready for Implementation

---

## 1. Overview

This tech spec provides implementation guidance for Epic 10: Direct Memory API, which enables Annie (or any LLM client) to **explicitly store and delete memories** with sub-3-second latency, bypassing the slow LangGraph ingestion pipeline.

### 1.1 Problem Statement

The existing ingestion pipeline (`unified_ingestion_graph.py`) is designed for passive learning with 60-100s latency and no delete capability. Annie requires:
- **Fast Store** - Direct memory storage in < 3s (vs 60-100s)
- **Explicit Delete** - Remove specific memories by ID
- **Full Retrieval Support** - Stored memories must be retrievable via existing endpoints

### 1.2 Solution Summary

Implement a Direct Memory API with two endpoints:
1. `POST /v1/memories/direct` - Store pre-formatted memories
2. `DELETE /v1/memories/{memory_id}` - Delete memories from all storage backends

**Design Decision:** Unified API with optional fields for type-aware routing to typed tables (episodic, emotional, procedural).

---

## 2. Objectives and Scope

### 2.1 In Scope

| Capability | Description |
|------------|-------------|
| Direct Store (ChromaDB) | Store memories directly via `upsert_memories()` |
| Typed Table Routing | Optional fields route to episodic/emotional/procedural tables |
| Memory Deletion | Cross-storage deletion using metadata flags |
| Pydantic Schemas | Request/response models with validation |
| Unit Tests | >80% code coverage for memories router |
| Integration Tests | End-to-end store/retrieve/delete lifecycle |
| Documentation | OpenAPI schema and API contracts update |

### 2.2 Out of Scope

- Batch memory operations
- Memory update/patch endpoint (use delete + store)
- Semantic deduplication on direct store
- Pipeline bypass for compaction (existing system continues)

### 2.3 Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| ChromaDB | Infrastructure | Available (existing) |
| TimescaleDB | Infrastructure | Available (existing) |
| `upsert_memories()` | Function | Available in `storage.py` |
| `generate_embedding()` | Function | Available in `embedding_utils.py` |

---

## 3. System Architecture Alignment

### 3.1 Storage Architecture

```
DirectMemoryRequest
    │
    ▼
Always → ChromaDB (via upsert_memories)
    │
    ├── If event_timestamp → episodic_memories (TimescaleDB)
    ├── If emotional_state → emotional_memories (TimescaleDB)
    └── If skill_name → procedural_memories (PostgreSQL)
    │
    ▼
Store metadata flags: stored_in_episodic, stored_in_emotional, stored_in_procedural
```

### 3.2 Deletion Architecture

```
DELETE /v1/memories/{memory_id}
    │
    ▼
1. Get memory metadata from ChromaDB (includes stored_in_* flags)
    │
    ▼
2. Delete from ChromaDB (always)
    │
    ├── If stored_in_episodic → DELETE FROM episodic_memories
    ├── If stored_in_emotional → DELETE FROM emotional_memories
    └── If stored_in_procedural → DELETE FROM procedural_memories
    │
    ▼
4. Return success with deletion status per backend
```

### 3.3 Existing Code Reuse

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| `upsert_memories()` | `src/services/storage.py` | Direct call - pure ChromaDB write |
| `generate_embedding()` | `src/services/embedding_utils.py` | Generate embeddings for content |
| `_standard_collection_name()` | `src/services/retrieval.py` | Get correct ChromaDB collection |
| `get_timescale_conn()` | `src/dependencies/timescale.py` | PostgreSQL/TimescaleDB connections |
| `get_chroma_client()` | `src/dependencies/chroma.py` | ChromaDB client |

---

## 4. Detailed Design

### 4.1 New Router: `src/routers/memories.py`

**Purpose:** Direct memory storage and deletion endpoints.

**Key Functions:**

| Function | Purpose | Returns |
|----------|---------|---------|
| `store_memory_direct()` | POST endpoint for direct storage | `DirectMemoryResponse` |
| `delete_memory()` | DELETE endpoint for removal | `DeleteMemoryResponse` |
| `_store_episodic()` | Helper for episodic table insert | None |
| `_store_emotional()` | Helper for emotional table insert | None |
| `_store_procedural()` | Helper for procedural table insert | None |
| `_delete_from_episodic()` | Helper for episodic table delete | None |
| `_delete_from_emotional()` | Helper for emotional table delete | None |
| `_delete_from_procedural()` | Helper for procedural table delete | None |

### 4.2 Pydantic Schemas

**File:** `src/schemas.py` (additions)

```python
class DirectMemoryRequest(BaseModel):
    """Request body for direct memory storage."""

    # Required
    user_id: str
    content: str = Field(..., max_length=5000)

    # General fields (always stored in ChromaDB)
    layer: Literal["short-term", "semantic", "long-term"] = "semantic"
    type: Literal["explicit", "implicit"] = "explicit"
    importance: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    persona_tags: List[str] = Field(default_factory=list, max_length=10)
    metadata: Optional[Dict[str, Any]] = None

    # Optional episodic fields
    event_timestamp: Optional[datetime] = None
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    event_type: Optional[str] = None

    # Optional emotional fields
    emotional_state: Optional[str] = None
    valence: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    arousal: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    trigger_event: Optional[str] = None

    # Optional procedural fields
    skill_name: Optional[str] = None
    proficiency_level: Optional[str] = None

class DirectMemoryResponse(BaseModel):
    """Response for direct memory storage."""
    status: Literal["success", "error"]
    memory_id: Optional[str] = None
    message: str
    storage: Optional[Dict[str, bool]] = None
    error_code: Optional[Literal[
        "VALIDATION_ERROR",
        "EMBEDDING_ERROR",
        "STORAGE_ERROR",
        "INTERNAL_ERROR"
    ]] = None

class DeleteMemoryResponse(BaseModel):
    """Response for memory deletion."""
    status: Literal["success", "error"]
    deleted: bool
    memory_id: str
    storage: Optional[Dict[str, bool]] = None
    message: Optional[str] = None
```

### 4.3 Memory ID Format

Consistent with existing pipeline pattern in `storage.py`:
```python
memory_id = f"mem_{uuid.uuid4().hex[:12]}"
```

### 4.4 Metadata Flags

Stored in ChromaDB metadata for efficient delete lookup:
```python
metadata = {
    "source": "direct_api",
    "stored_in_episodic": bool,
    "stored_in_emotional": bool,
    "stored_in_procedural": bool,
    "user_id": str  # For authorization
}
```

### 4.5 Error Handling

| Error Code | Condition | HTTP Status |
|------------|-----------|-------------|
| `VALIDATION_ERROR` | Invalid request body | 400 |
| `EMBEDDING_ERROR` | Embedding generation failed | 500 |
| `STORAGE_ERROR` | ChromaDB write failed | 500 |
| `INTERNAL_ERROR` | Unexpected exception | 500 |
| - | Memory not found | 404 |
| - | Unauthorized (wrong user) | 403 |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Direct store p95 latency | < 3 seconds | Timer in endpoint |
| Delete p95 latency | < 1 second | Timer in endpoint |
| Embedding generation | < 2 seconds | OpenAI API call |
| ChromaDB write | < 500ms | `upsert_memories()` |
| Typed table write | < 200ms | PostgreSQL INSERT |

### 5.2 Reliability

- **ChromaDB Required:** Direct store fails if ChromaDB unavailable (source of truth)
- **Typed Tables Best-Effort:** Failures logged but don't fail the request
- **Delete Idempotent:** Returns success if memory already deleted

### 5.3 Observability

| Log Point | Level | Content |
|-----------|-------|---------|
| Request received | INFO | user_id, content length |
| Embedding generated | DEBUG | duration_ms |
| ChromaDB stored | INFO | memory_id |
| Typed table stored | INFO | table_name, memory_id |
| Error | ERROR | error_code, message, traceback |

### 5.4 Security

| Concern | Mitigation |
|---------|------------|
| User isolation | Verify `user_id` matches memory owner on delete |
| Content injection | Pydantic validation, max_length=5000 |
| No auth (MVP) | Relies on `user_id` parameter (consistent with existing APIs) |

---

## 6. Dependencies and Integrations

### 6.1 Internal Dependencies

| Component | Usage |
|-----------|-------|
| `src/services/storage.py::upsert_memories()` | ChromaDB storage |
| `src/services/embedding_utils.py::generate_embedding()` | Embedding generation |
| `src/services/retrieval.py::_standard_collection_name()` | Collection name |
| `src/dependencies/chroma.py::get_chroma_client()` | ChromaDB client |
| `src/dependencies/timescale.py::get_timescale_conn()` | PostgreSQL connection |
| `src/models.py::Memory` | Memory dataclass |

### 6.2 External Dependencies

| Service | Usage | Fallback |
|---------|-------|----------|
| OpenAI API | Embedding generation | Return EMBEDDING_ERROR |
| ChromaDB | Vector storage | Fail request |
| TimescaleDB | Typed tables | Log error, continue |

### 6.3 App Integration

**File:** `src/app.py`

```python
# Add import
from src.routers import memories

# Add router registration
app.include_router(memories.router)
```

---

## 7. Acceptance Criteria and Traceability

### Story 10.1: Direct Memory Store Endpoint (ChromaDB)

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | `POST /v1/memories/direct` endpoint created | Integration test |
| AC2 | Memory ID format: `mem_{uuid.hex[:12]}` | Unit test |
| AC3 | Embedding generated via `generate_embedding()` | Unit test with mock |
| AC4 | ChromaDB storage via `upsert_memories()` | Integration test |
| AC5 | p95 latency < 3 seconds | Performance test |

### Story 10.2: Typed Table Storage

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | Optional episodic/emotional/procedural fields in schema | Unit test |
| AC2 | event_timestamp → episodic_memories | Integration test |
| AC3 | emotional_state → emotional_memories | Integration test |
| AC4 | skill_name → procedural_memories | Integration test |
| AC5 | Metadata flags stored in ChromaDB | Unit test |

### Story 10.3: Delete Memory Endpoint

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | `DELETE /v1/memories/{memory_id}` endpoint created | Integration test |
| AC2 | User authorization verified | Unit test |
| AC3 | ChromaDB deletion performed | Integration test |
| AC4 | Typed tables deleted based on flags | Integration test |
| AC5 | Not found returns 404 | Unit test |

### Story 10.4: Pydantic Schemas

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | `DirectMemoryRequest` with all fields | Schema validation test |
| AC2 | `DirectMemoryResponse` with error codes | Schema validation test |
| AC3 | `DeleteMemoryResponse` schema | Schema validation test |
| AC4 | OpenAPI docs generated | Manual verification |

### Story 10.5: Unit Tests

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | Store minimal fields test | pytest |
| AC2 | Store all optional fields test | pytest |
| AC3 | Embedding failure handling | pytest with mock |
| AC4 | Delete success/not found/unauthorized | pytest |
| AC5 | >80% code coverage | pytest-cov |

### Story 10.6: Integration Tests

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | Store → Retrieve → Delete lifecycle | pytest with TestClient |
| AC2 | Typed memory retrieval via hybrid retrieval | pytest |
| AC3 | Performance < 3s store, < 1s delete | pytest with timing |

### Story 10.7: Documentation Update

| AC | Description | Test Method |
|----|-------------|-------------|
| AC1 | OpenAPI schema complete | FastAPI /docs |
| AC2 | `docs/api-contracts-server.md` updated | Manual review |
| AC3 | `docs/architecture.md` updated | Manual review |

---

## 8. Test Strategy

### 8.1 Unit Tests

**File:** `tests/unit/test_memories_router.py`

```python
# Test categories:
# - test_store_memory_minimal_fields
# - test_store_memory_with_episodic_fields
# - test_store_memory_with_emotional_fields
# - test_store_memory_with_procedural_fields
# - test_store_memory_embedding_failure
# - test_store_memory_chromadb_failure
# - test_delete_memory_success
# - test_delete_memory_not_found
# - test_delete_memory_unauthorized
# - test_delete_memory_cross_storage
```

### 8.2 Integration Tests

**File:** `tests/integration/test_direct_memory_api.py`

```python
# Test categories:
# - test_store_and_retrieve_lifecycle
# - test_store_and_delete_lifecycle
# - test_episodic_memory_in_hybrid_retrieval
# - test_emotional_memory_in_hybrid_retrieval
# - test_performance_under_3_seconds
```

### 8.3 Test Fixtures

```python
@pytest.fixture
def sample_direct_memory_request():
    return {
        "user_id": "test_user_123",
        "content": "User prefers morning meetings before 10am",
        "layer": "semantic",
        "type": "explicit",
        "importance": 0.85,
        "persona_tags": ["preferences", "scheduling"]
    }

@pytest.fixture
def sample_episodic_memory_request():
    return {
        "user_id": "test_user_123",
        "content": "User attended team offsite in Lake Tahoe",
        "event_timestamp": "2025-06-15T09:00:00Z",
        "location": "Lake Tahoe, CA",
        "participants": ["team", "manager"],
        "event_type": "work_event"
    }
```

---

## 9. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ChromaDB unavailable | High | Low | Return clear error, no partial writes |
| Embedding API timeout | Medium | Medium | 30s timeout, return EMBEDDING_ERROR |
| Orphaned typed table entries | Low | Low | Metadata flags ensure cleanup |
| ID collision | Low | Very Low | UUID with 12-char hex = 281 trillion combinations |

---

## 10. Implementation Order

| Order | Story | Dependencies |
|-------|-------|--------------|
| 1 | 10.4 Pydantic Schemas | None |
| 2 | 10.1 Direct Store (ChromaDB) | 10.4 |
| 3 | 10.2 Typed Table Storage | 10.1 |
| 4 | 10.3 Delete Endpoint | 10.1 |
| 5 | 10.5 Unit Tests | 10.1-10.4 |
| 6 | 10.6 Integration Tests | 10.5 |
| 7 | 10.7 Documentation | 10.1-10.4 |

---

## 11. File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/routers/memories.py` | Direct memory endpoints |
| `tests/unit/test_memories_router.py` | Unit tests |
| `tests/integration/test_direct_memory_api.py` | Integration tests |

### Modified Files

| File | Changes |
|------|---------|
| `src/schemas.py` | Add DirectMemoryRequest, DirectMemoryResponse, DeleteMemoryResponse |
| `src/app.py` | Import and register memories router |
| `docs/api-contracts-server.md` | Document new endpoints |
| `docs/architecture.md` | Document storage routing logic |

---

## 12. Success Criteria Summary

1. Annie can store a memory via `POST /v1/memories/direct` in < 3 seconds
2. Stored memories are retrievable via existing `/v1/retrieve` endpoint
3. Annie can delete memories via `DELETE /v1/memories/{memory_id}`
4. Deleted memories no longer appear in retrieval results
5. Episodic memories appear in time-based hybrid retrieval
6. Emotional memories appear in emotional retrieval
7. All operations respect user_id authorization
8. OpenAPI documentation complete
9. >80% unit test coverage

---

**Document History:**
- 2025-12-29: Initial version (Claude Code)
