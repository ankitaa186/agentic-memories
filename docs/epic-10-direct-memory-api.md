# Epic 10: Direct Memory API for Explicit Memory Management

**Epic ID:** 10
**Author:** Claude Code (with BMad Party Mode analysis)
**Status:** Proposed
**Priority:** P1 (Enables Annie explicit memory control)
**Dependencies:** None (uses existing infrastructure)
**Downstream Dependents:** Annie LLM explicit memory management

---

## Executive Summary

Implement a Direct Memory API that enables Annie (or any LLM client) to **explicitly store and delete memories** with sub-3-second latency, bypassing the slow LangGraph ingestion pipeline. This addresses a critical architectural gap: the current system is append-only with no explicit delete capability.

**Key Capabilities:**
- **Fast Store** - Direct memory storage bypassing LLM extraction pipeline (< 3s vs 60-100s)
- **Explicit Delete** - Remove specific memories by ID from all storage backends
- **Type-Aware Routing** - Optional fields route memories to appropriate typed tables
- **Cross-Storage Consistency** - Delete from ChromaDB + typed TimescaleDB tables

---

## Background & Motivation

### Current Architecture Gap

The existing ingestion pipeline (`unified_ingestion_graph.py`) is designed for **passive learning**:

```
Conversation → LangGraph Pipeline (60-100s) → Extract → Classify → Store
                     ↓
              Append-only (no delete)
```

**Problems:**
1. **No Delete API** - No way to remove incorrect, outdated, or user-requested deletions
2. **High Latency** - 60-100s unacceptable for in-conversation memory operations
3. **No Explicit Control** - LLM cannot directly save critical information

### Annie's Requirements

Annie needs to:
1. **Save critical memories immediately** - "User is allergic to shellfish" stored in < 3s
2. **Delete memories on demand** - User says "Forget that I told you X"
3. **Correct mistakes** - Pipeline extracted wrong info, Annie needs to fix it
4. **Full retrieval support** - Stored memories must be retrievable via existing endpoints

### Deep Dive Analysis Findings

A comprehensive codebase analysis (via BMad Party Mode) revealed:

| Component | Current State | Implication |
|-----------|---------------|-------------|
| `upsert_memories()` | Pure ChromaDB write, no pipeline logic | Safe to reuse for direct storage |
| `semantic_memories` table | Exists but **never read** by retrieval | Do not use - orphaned infrastructure |
| Typed tables (episodic, emotional, procedural) | Written and read by hybrid retrieval | Must write to these for full retrieval support |
| Compaction system | Has deletion patterns for ChromaDB | Can extend patterns for explicit delete |
| `episodic_memory.py:362-375` | Cross-storage delete pattern exists | Reuse for delete endpoint |

---

## Technical Design

### Design Decision: Unified API with Optional Fields (Approach A)

After analysis, we chose **Approach A: Unified endpoint with optional typed fields**:

- Single `POST /v1/memories/direct` endpoint
- Optional fields trigger routing to typed tables
- Metadata flags track which tables contain the memory
- Delete uses flags to clean up all storage locations

**Rationale:**
- Simpler API surface for clients
- Flexible - general memories use minimal fields, typed memories add specific fields
- Consistent with existing Memory model patterns

### Storage Routing Logic

```
DirectMemoryRequest
    ↓
Always → ChromaDB (via upsert_memories)
    ↓
If event_timestamp → episodic_memories (TimescaleDB)
If emotional_state → emotional_memories (TimescaleDB)
If skill_name → procedural_memories (PostgreSQL)
    ↓
Store metadata flags: stored_in_episodic, stored_in_emotional, stored_in_procedural
```

### Delete Logic

```
DELETE /v1/memories/{memory_id}
    ↓
1. Get memory metadata from ChromaDB (includes stored_in_* flags)
    ↓
2. Delete from ChromaDB (always)
    ↓
3. If stored_in_episodic → DELETE FROM episodic_memories
   If stored_in_emotional → DELETE FROM emotional_memories
   If stored_in_procedural → DELETE FROM procedural_memories
    ↓
4. Return success with deletion status per backend
```

---

## API Specifications

### POST `/v1/memories/direct`

Store a pre-formatted memory directly without LLM extraction.

#### Request Schema

```python
class DirectMemoryRequest(BaseModel):
    """Request body for direct memory storage."""

    # === REQUIRED ===
    user_id: str = Field(..., description="User identifier")
    content: str = Field(..., max_length=5000, description="Memory content")

    # === GENERAL FIELDS (always stored in ChromaDB) ===
    layer: Literal["short-term", "semantic", "long-term"] = Field(
        default="semantic",
        description="Memory layer"
    )
    type: Literal["explicit", "implicit"] = Field(
        default="explicit",
        description="Memory type"
    )
    importance: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Importance score (0.0-1.0)"
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)"
    )
    persona_tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Persona tags (max 10)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )

    # === OPTIONAL EPISODIC FIELDS ===
    # If provided, memory is also stored in episodic_memories table
    event_timestamp: Optional[datetime] = Field(
        default=None,
        description="When the event occurred (triggers episodic storage)"
    )
    location: Optional[str] = Field(
        default=None,
        description="Where the event occurred"
    )
    participants: Optional[List[str]] = Field(
        default=None,
        description="People involved in the event"
    )
    event_type: Optional[str] = Field(
        default=None,
        description="Category of event"
    )

    # === OPTIONAL EMOTIONAL FIELDS ===
    # If provided, memory is also stored in emotional_memories table
    emotional_state: Optional[str] = Field(
        default=None,
        description="Emotional state (triggers emotional storage)"
    )
    valence: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Emotional valence (-1.0 negative to 1.0 positive)"
    )
    arousal: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Emotional arousal (0.0 calm to 1.0 excited)"
    )
    trigger_event: Optional[str] = Field(
        default=None,
        description="What triggered the emotional state"
    )

    # === OPTIONAL PROCEDURAL FIELDS ===
    # If provided, memory is also stored in procedural_memories table
    skill_name: Optional[str] = Field(
        default=None,
        description="Skill name (triggers procedural storage)"
    )
    proficiency_level: Optional[str] = Field(
        default=None,
        description="Skill level: beginner, intermediate, advanced, expert"
    )
```

#### Response Schema

```python
class DirectMemoryResponse(BaseModel):
    """Response for direct memory storage."""

    status: Literal["success", "error"]
    memory_id: Optional[str] = Field(
        default=None,
        description="UUID of stored memory (on success)"
    )
    message: str = Field(description="Status message")
    storage: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Storage status per backend"
    )
    error_code: Optional[Literal[
        "VALIDATION_ERROR",
        "EMBEDDING_ERROR",
        "STORAGE_ERROR",
        "INTERNAL_ERROR"
    ]] = Field(default=None, description="Error code (on failure)")
```

#### Example: General Memory

```json
// Request
POST /v1/memories/direct
{
  "user_id": "0000000000",
  "content": "User is allergic to shellfish - confirmed severe reaction, carries EpiPen",
  "layer": "semantic",
  "type": "explicit",
  "importance": 0.95,
  "confidence": 0.98,
  "persona_tags": ["health", "allergy", "critical", "medical"]
}

// Response
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true
  }
}
```

#### Example: Episodic Memory

```json
// Request
POST /v1/memories/direct
{
  "user_id": "0000000000",
  "content": "User attended daughter's graduation ceremony at Stanford",
  "layer": "long-term",
  "type": "explicit",
  "importance": 0.9,
  "event_timestamp": "2025-06-15T14:00:00Z",
  "location": "Stanford University, CA",
  "participants": ["daughter Sarah", "wife Maria"],
  "event_type": "family_milestone"
}

// Response
{
  "status": "success",
  "memory_id": "mem_f7g8h9i0j1k2",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "episodic": true
  }
}
```

#### Example: Emotional Memory

```json
// Request
POST /v1/memories/direct
{
  "user_id": "0000000000",
  "content": "User expressed frustration about job search taking too long",
  "layer": "semantic",
  "type": "explicit",
  "emotional_state": "frustrated",
  "valence": -0.6,
  "arousal": 0.7,
  "trigger_event": "Another job rejection email"
}

// Response
{
  "status": "success",
  "memory_id": "mem_l3m4n5o6p7q8",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "emotional": true
  }
}
```

---

### DELETE `/v1/memories/{memory_id}`

Delete a specific memory by ID from all storage backends.

#### Request

```
DELETE /v1/memories/{memory_id}?user_id={user_id}
```

**Path Parameters:**
- `memory_id` (string, required): ID of memory to delete

**Query Parameters:**
- `user_id` (string, required): User ID for authorization

#### Response Schema

```python
class DeleteMemoryResponse(BaseModel):
    """Response for memory deletion."""

    status: Literal["success", "error"]
    deleted: bool = Field(description="True if memory was deleted")
    memory_id: str = Field(description="Requested memory ID")
    storage: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Deletion status per backend"
    )
    message: Optional[str] = Field(
        default=None,
        description="Status or error message"
    )
```

#### Example: Successful Deletion

```
DELETE /v1/memories/mem_a1b2c3d4e5f6?user_id=0000000000

{
  "status": "success",
  "deleted": true,
  "memory_id": "mem_a1b2c3d4e5f6",
  "storage": {
    "chromadb": true,
    "episodic": true
  }
}
```

#### Example: Not Found

```
DELETE /v1/memories/mem_nonexistent?user_id=0000000000

{
  "status": "error",
  "deleted": false,
  "memory_id": "mem_nonexistent",
  "message": "Memory not found"
}
```

#### Example: Unauthorized

```
DELETE /v1/memories/mem_a1b2c3d4e5f6?user_id=wrong_user

{
  "status": "error",
  "deleted": false,
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Unauthorized: memory belongs to different user"
}
```

---

## Implementation

### New Router: `src/routers/memories.py`

```python
"""
Direct memory storage and deletion endpoints.
Bypasses LangGraph pipeline for fast, explicit memory operations.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.schemas import (
    DirectMemoryRequest,
    DirectMemoryResponse,
    DeleteMemoryResponse
)
from src.models import Memory
from src.services.storage import upsert_memories
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name
from src.services.episodic_memory import EpisodicMemoryService
from src.services.emotional_memory import EmotionalMemoryService
from src.services.procedural_memory import ProceduralMemoryService
from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn

logger = logging.getLogger("agentic_memories.memories")

router = APIRouter(prefix="/v1/memories", tags=["memories"])


@router.post("/direct", response_model=DirectMemoryResponse)
def store_memory_direct(body: DirectMemoryRequest) -> DirectMemoryResponse:
    """
    Store a pre-formatted memory directly without LLM extraction.

    Designed for explicit critical memories where the LLM has already
    determined the content, importance, and classification.

    Performance target: < 3 seconds p95
    """
    try:
        # Generate memory ID
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"

        # Generate embedding
        embedding = generate_embedding(body.content)
        if embedding is None:
            logger.error(
                "[memories.direct] Embedding generation failed",
                extra={"user_id": body.user_id}
            )
            return DirectMemoryResponse(
                status="error",
                message="Failed to generate embedding",
                error_code="EMBEDDING_ERROR"
            )

        # Determine which typed tables to store in
        store_episodic = body.event_timestamp is not None
        store_emotional = body.emotional_state is not None
        store_procedural = body.skill_name is not None

        # Build metadata with storage tracking flags
        metadata = body.metadata or {}
        metadata.update({
            "source": "direct_api",
            "stored_in_episodic": store_episodic,
            "stored_in_emotional": store_emotional,
            "stored_in_procedural": store_procedural,
        })

        # Build Memory object for ChromaDB
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

        storage_results = {}

        # 1. Always store in ChromaDB
        try:
            upsert_memories(body.user_id, [memory])
            storage_results["chromadb"] = True
        except Exception as e:
            logger.error(f"[memories.direct] ChromaDB storage failed: {e}")
            storage_results["chromadb"] = False

        # 2. Conditionally store in episodic_memories
        if store_episodic:
            try:
                _store_episodic(memory_id, body)
                storage_results["episodic"] = True
            except Exception as e:
                logger.error(f"[memories.direct] Episodic storage failed: {e}")
                storage_results["episodic"] = False

        # 3. Conditionally store in emotional_memories
        if store_emotional:
            try:
                _store_emotional(memory_id, body)
                storage_results["emotional"] = True
            except Exception as e:
                logger.error(f"[memories.direct] Emotional storage failed: {e}")
                storage_results["emotional"] = False

        # 4. Conditionally store in procedural_memories
        if store_procedural:
            try:
                _store_procedural(memory_id, body)
                storage_results["procedural"] = True
            except Exception as e:
                logger.error(f"[memories.direct] Procedural storage failed: {e}")
                storage_results["procedural"] = False

        # Success if ChromaDB succeeded (source of truth for retrieval)
        if storage_results.get("chromadb"):
            return DirectMemoryResponse(
                status="success",
                memory_id=memory_id,
                message="Memory stored successfully",
                storage=storage_results
            )
        else:
            return DirectMemoryResponse(
                status="error",
                message="ChromaDB storage failed",
                error_code="STORAGE_ERROR",
                storage=storage_results
            )

    except Exception as e:
        logger.exception(f"[memories.direct] Unexpected error: {e}")
        return DirectMemoryResponse(
            status="error",
            message=f"Internal error: {str(e)}",
            error_code="INTERNAL_ERROR"
        )


@router.delete("/{memory_id}", response_model=DeleteMemoryResponse)
def delete_memory(
    memory_id: str,
    user_id: str = Query(..., description="User ID for authorization")
) -> DeleteMemoryResponse:
    """
    Delete a specific memory by ID from all storage backends.

    Uses metadata flags to determine which typed tables contain the memory.
    """
    try:
        client = get_chroma_client()
        if client is None:
            return DeleteMemoryResponse(
                status="error",
                deleted=False,
                memory_id=memory_id,
                message="ChromaDB not available"
            )

        # 1. Get memory metadata to determine storage locations
        collection_name = _standard_collection_name()
        collection = client.get_or_create_collection(collection_name)

        result = collection.get(ids=[memory_id], include=["metadatas"])

        if not result["ids"]:
            return DeleteMemoryResponse(
                status="error",
                deleted=False,
                memory_id=memory_id,
                message="Memory not found"
            )

        metadata = result["metadatas"][0] if result["metadatas"] else {}

        # Verify user ownership
        if metadata.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: memory belongs to different user"
            )

        storage_results = {}

        # 2. Delete from ChromaDB
        try:
            collection.delete(ids=[memory_id])
            storage_results["chromadb"] = True
        except Exception as e:
            logger.error(f"[memories.delete] ChromaDB deletion failed: {e}")
            storage_results["chromadb"] = False

        # 3. Delete from typed tables based on metadata flags
        if metadata.get("stored_in_episodic"):
            try:
                _delete_from_episodic(memory_id, user_id)
                storage_results["episodic"] = True
            except Exception as e:
                logger.error(f"[memories.delete] Episodic deletion failed: {e}")
                storage_results["episodic"] = False

        if metadata.get("stored_in_emotional"):
            try:
                _delete_from_emotional(memory_id, user_id)
                storage_results["emotional"] = True
            except Exception as e:
                logger.error(f"[memories.delete] Emotional deletion failed: {e}")
                storage_results["emotional"] = False

        if metadata.get("stored_in_procedural"):
            try:
                _delete_from_procedural(memory_id, user_id)
                storage_results["procedural"] = True
            except Exception as e:
                logger.error(f"[memories.delete] Procedural deletion failed: {e}")
                storage_results["procedural"] = False

        # Success if ChromaDB succeeded
        if storage_results.get("chromadb"):
            return DeleteMemoryResponse(
                status="success",
                deleted=True,
                memory_id=memory_id,
                storage=storage_results
            )
        else:
            return DeleteMemoryResponse(
                status="error",
                deleted=False,
                memory_id=memory_id,
                message="ChromaDB deletion failed",
                storage=storage_results
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[memories.delete] Unexpected error: {e}")
        return DeleteMemoryResponse(
            status="error",
            deleted=False,
            memory_id=memory_id,
            message=f"Internal error: {str(e)}"
        )


# === Helper Functions for Typed Table Storage ===

def _store_episodic(memory_id: str, body: DirectMemoryRequest) -> None:
    """Store memory in episodic_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        raise Exception("TimescaleDB not available")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO episodic_memories (
                    id, user_id, event_timestamp, event_type, content,
                    location, participants, importance_score, tags, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    memory_id,
                    body.user_id,
                    body.event_timestamp,
                    body.event_type or "general",
                    body.content,
                    body.location,
                    body.participants,
                    body.importance,
                    body.persona_tags,
                    body.metadata or {}
                )
            )
        conn.commit()
    finally:
        release_timescale_conn(conn)


def _store_emotional(memory_id: str, body: DirectMemoryRequest) -> None:
    """Store memory in emotional_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        raise Exception("TimescaleDB not available")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO emotional_memories (
                    id, user_id, timestamp, emotional_state, valence,
                    arousal, context, trigger_event, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    memory_id,
                    body.user_id,
                    datetime.now(timezone.utc),
                    body.emotional_state,
                    body.valence or 0.0,
                    body.arousal or 0.5,
                    body.content,
                    body.trigger_event,
                    body.metadata or {}
                )
            )
        conn.commit()
    finally:
        release_timescale_conn(conn)


def _store_procedural(memory_id: str, body: DirectMemoryRequest) -> None:
    """Store memory in procedural_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        raise Exception("TimescaleDB not available")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO procedural_memories (
                    id, user_id, skill_name, proficiency_level, context, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    proficiency_level = EXCLUDED.proficiency_level,
                    context = EXCLUDED.context
                """,
                (
                    memory_id,
                    body.user_id,
                    body.skill_name,
                    body.proficiency_level or "beginner",
                    body.content,
                    body.metadata or {}
                )
            )
        conn.commit()
    finally:
        release_timescale_conn(conn)


# === Helper Functions for Typed Table Deletion ===

def _delete_from_episodic(memory_id: str, user_id: str) -> None:
    """Delete from episodic_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM episodic_memories WHERE id = %s AND user_id = %s",
                (memory_id, user_id)
            )
        conn.commit()
    finally:
        release_timescale_conn(conn)


def _delete_from_emotional(memory_id: str, user_id: str) -> None:
    """Delete from emotional_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM emotional_memories WHERE id = %s AND user_id = %s",
                (memory_id, user_id)
            )
        conn.commit()
    finally:
        release_timescale_conn(conn)


def _delete_from_procedural(memory_id: str, user_id: str) -> None:
    """Delete from procedural_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM procedural_memories WHERE id = %s AND user_id = %s",
                (memory_id, user_id)
            )
        conn.commit()
    finally:
        release_timescale_conn(conn)
```

### Register Router in `src/app.py`

```python
# Add import
from src.routers import profile, portfolio, intents, memories

# Add router registration (after existing routers)
app.include_router(memories.router)
```

---

## Stories Breakdown

### Story 10.1: Direct Memory Store Endpoint (ChromaDB)

**Goal:** Implement basic direct memory storage to ChromaDB.

**Acceptance Criteria:**

**AC #1: Endpoint Creation**
- Create `POST /v1/memories/direct` endpoint
- Accept `DirectMemoryRequest` body
- Return `DirectMemoryResponse`

**AC #2: Memory ID Generation**
- Generate ID format: `mem_{uuid.hex[:12]}`
- Consistent with existing patterns in `storage.py`

**AC #3: Embedding Generation**
- Call `generate_embedding()` for content
- Return EMBEDDING_ERROR if generation fails

**AC #4: ChromaDB Storage**
- Use existing `upsert_memories()` function
- Store with metadata including `source: "direct_api"`

**AC #5: Performance**
- p95 latency < 3 seconds
- Log timing metrics

**Estimated Effort:** 3 hours

---

### Story 10.2: Typed Table Storage (Episodic, Emotional, Procedural)

**Goal:** Add conditional routing to typed TimescaleDB tables.

**Acceptance Criteria:**

**AC #1: Schema Extension**
- Add optional episodic fields to `DirectMemoryRequest`
- Add optional emotional fields
- Add optional procedural fields

**AC #2: Storage Routing**
- If `event_timestamp` provided → store in `episodic_memories`
- If `emotional_state` provided → store in `emotional_memories`
- If `skill_name` provided → store in `procedural_memories`

**AC #3: Metadata Tracking**
- Store flags in ChromaDB metadata:
  - `stored_in_episodic: bool`
  - `stored_in_emotional: bool`
  - `stored_in_procedural: bool`

**AC #4: Response**
- Include storage status per backend in response
- ChromaDB success is required; typed tables are best-effort

**Estimated Effort:** 4 hours

---

### Story 10.3: Delete Memory Endpoint

**Goal:** Implement cross-storage memory deletion.

**Acceptance Criteria:**

**AC #1: Endpoint Creation**
- Create `DELETE /v1/memories/{memory_id}` endpoint
- Require `user_id` query parameter

**AC #2: Authorization**
- Verify memory belongs to requesting user
- Return 403 if unauthorized

**AC #3: ChromaDB Deletion**
- Get memory metadata first (to find storage locations)
- Delete from ChromaDB collection

**AC #4: Typed Table Deletion**
- Check metadata flags for storage locations
- Delete from relevant typed tables

**AC #5: Response**
- Return deletion status per backend
- Return "not found" if memory doesn't exist

**Estimated Effort:** 3 hours

---

### Story 10.4: Pydantic Schemas

**Goal:** Add request/response schemas to `src/schemas.py`.

**Acceptance Criteria:**

**AC #1: DirectMemoryRequest**
- All required and optional fields
- Proper Field() validators (ge, le, max_length)
- Clear descriptions

**AC #2: DirectMemoryResponse**
- Status, memory_id, message, storage, error_code fields

**AC #3: DeleteMemoryResponse**
- Status, deleted, memory_id, storage, message fields

**AC #4: Documentation**
- OpenAPI schema generation
- Example values in Field() definitions

**Estimated Effort:** 1.5 hours

---

### Story 10.5: Unit Tests

**Goal:** Comprehensive test coverage for direct memory operations.

**Acceptance Criteria:**

**AC #1: Store Tests**
- Test minimal required fields
- Test all optional fields
- Test embedding failure handling
- Test ChromaDB failure handling
- Test typed table storage

**AC #2: Delete Tests**
- Test successful deletion
- Test not found case
- Test unauthorized case
- Test cross-storage deletion

**AC #3: Validation Tests**
- Test field constraints
- Test missing required fields

**AC #4: Coverage**
- >80% code coverage for memories router

**Estimated Effort:** 3 hours

---

### Story 10.6: Integration Tests

**Goal:** End-to-end testing of store/retrieve/delete lifecycle.

**Acceptance Criteria:**

**AC #1: Lifecycle Test**
- Store memory via direct API
- Retrieve via `/v1/retrieve` (verify found)
- Delete via delete endpoint
- Retrieve again (verify not found)

**AC #2: Typed Memory Tests**
- Store episodic memory → verify in time-based retrieval
- Store emotional memory → verify in emotional retrieval
- Store procedural memory → verify in procedural queries

**AC #3: Performance Test**
- Verify direct store < 3s
- Verify delete < 1s

**Estimated Effort:** 2 hours

---

### Story 10.7: Documentation Update

**Goal:** Document new endpoints and update API contracts.

**Acceptance Criteria:**

**AC #1: OpenAPI Schema**
- All endpoints documented
- Request/response examples
- Error codes documented

**AC #2: API Contracts Doc**
- Update `docs/api-contracts-server.md`
- Add direct memory section

**AC #3: Architecture Doc**
- Update `docs/architecture.md`
- Document storage routing logic

**Estimated Effort:** 1.5 hours

---

## Estimated Total Effort

| Story | Effort |
|-------|--------|
| 10.1 Direct Store (ChromaDB) | 3 hours |
| 10.2 Typed Table Storage | 4 hours |
| 10.3 Delete Endpoint | 3 hours |
| 10.4 Pydantic Schemas | 1.5 hours |
| 10.5 Unit Tests | 3 hours |
| 10.6 Integration Tests | 2 hours |
| 10.7 Documentation | 1.5 hours |
| **Total** | **18 hours (~2.5 days)** |

---

## Success Criteria

1. Annie can store a memory via `POST /v1/memories/direct` in < 3 seconds
2. Stored memories are retrievable via existing `/v1/retrieve` endpoint
3. Annie can delete memories via `DELETE /v1/memories/{memory_id}`
4. Deleted memories no longer appear in retrieval results
5. Episodic memories appear in time-based hybrid retrieval
6. Emotional memories appear in emotional retrieval
7. All operations respect user_id authorization
8. OpenAPI documentation complete

---

## Design Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Skip `semantic_memories` table | Yes | Table is never read by retrieval - orphaned infrastructure |
| ChromaDB as source of truth | Yes | All retrieval paths query ChromaDB first |
| Metadata flags for delete | Yes | Efficient - no need to query all tables |
| Best-effort typed storage | Yes | ChromaDB success required; typed tables optional |
| Single unified endpoint | Yes | Simpler API; optional fields for typed routing |
| Same ID format as pipeline | Yes | Consistency with existing `mem_` prefix pattern |

---

## Appendix: Codebase Analysis Summary

This epic was designed after a comprehensive BMad Party Mode analysis with contributions from:

- **Winston (Architect)** - Storage architecture, routing decisions
- **Amelia (Developer)** - Implementation patterns, existing code reuse
- **Mary (Business Analyst)** - Requirements clarification, gap analysis
- **Murat (Test Architect)** - Test strategy, edge cases

**Key Findings:**
1. `upsert_memories()` is a pure ChromaDB write - safe to reuse
2. `semantic_memories` table is write-only, never queried - do not use
3. Typed tables (episodic, emotional, procedural) are read by hybrid retrieval
4. Compaction system has existing deletion patterns to follow
5. Cross-storage delete pattern exists in `episodic_memory.py:362-375`

---

*This epic enables Annie to have explicit control over memory storage and deletion, complementing the existing passive learning pipeline.*
