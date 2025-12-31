# Direct Memory Storage API Design

> **Status**: Draft
> **Author**: Claude Code
> **Date**: 2025-12-27
> **Related**: `annie/docs/design/direct-memory-storage-design.md` (full system design)
> **Epic**: Performance Optimization

---

## 1. Overview

This document specifies the implementation of two new API endpoints in agentic-memories:

1. **`POST /v1/memories/direct`** - Fast direct memory storage (bypasses LangGraph pipeline)
2. **`DELETE /v1/memories/{memory_id}`** - Delete a specific memory by ID

These endpoints enable Annie's LLM to store and delete critical memories with sub-3-second latency, compared to 60-100+ seconds via the existing `/v1/store` endpoint.

### 1.1 Why Direct Storage?

The existing `/v1/store` endpoint runs a full LangGraph pipeline:
- LLM extraction (worthiness check, categorization)
- Multi-layer routing (episodic, emotional, procedural)
- Duplicate detection with semantic similarity

For **explicit critical memories** where the LLM has already determined the content and importance, this pipeline is unnecessary overhead. Direct storage writes pre-formatted memories immediately to ChromaDB and TimescaleDB.

---

## 2. API Specifications

### 2.1 POST `/v1/memories/direct`

Store a pre-formatted memory directly without LLM extraction.

#### Request Schema

```python
# src/schemas.py

class DirectMemoryRequest(BaseModel):
    """Request body for direct memory storage."""

    # Required
    user_id: str = Field(..., description="User identifier")
    content: str = Field(..., max_length=5000, description="Memory content")

    # General fields (always stored in ChromaDB)
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

    # Optional episodic fields → triggers episodic_memories write
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
        description="Who was involved in the event"
    )

    # Optional emotional fields → triggers emotional_memories write
    emotional_state: Optional[str] = Field(
        default=None,
        description="Emotional state (e.g., 'happy', 'anxious') - triggers emotional storage"
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

    # Optional procedural fields → triggers procedural_memories write
    skill_name: Optional[str] = Field(
        default=None,
        description="Skill or procedure name - triggers procedural storage"
    )
    proficiency_level: Optional[str] = Field(
        default=None,
        description="Proficiency level (e.g., 'beginner', 'expert')"
    )
```

#### Response Schema

```python
# src/schemas.py

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
        description="Storage status per backend (chromadb, episodic, emotional, procedural)"
    )
    error_code: Optional[Literal[
        "VALIDATION_ERROR",
        "EMBEDDING_ERROR",
        "STORAGE_ERROR",
        "INTERNAL_ERROR"
    ]] = Field(default=None, description="Error code (on failure)")


class DeleteMemoryResponse(BaseModel):
    """Response for memory deletion."""

    status: Literal["success", "error"]
    deleted: bool = Field(description="True if memory was deleted")
    memory_id: str = Field(description="Requested memory ID")
    storage: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Deletion status per backend (chromadb, episodic, emotional, procedural)"
    )
    message: Optional[str] = Field(
        default=None,
        description="Status or error message"
    )
```

#### Example Request (Basic - ChromaDB only)

```json
{
  "user_id": "0000000000",
  "content": "User is allergic to shellfish - confirmed severe reaction, carries EpiPen",
  "layer": "semantic",
  "type": "explicit",
  "importance": 0.95,
  "confidence": 0.98,
  "persona_tags": ["health", "allergy", "critical", "medical"],
  "metadata": {
    "source": "llm_explicit",
    "conversation_id": "conv_abc123",
    "trigger": "User explicitly stated allergy during health discussion"
  }
}
```

#### Example Request (With Episodic Fields)

```json
{
  "user_id": "0000000000",
  "content": "User got engaged to Sarah at the Golden Gate Bridge",
  "layer": "long-term",
  "type": "explicit",
  "importance": 0.99,
  "confidence": 1.0,
  "persona_tags": ["life_event", "relationship"],
  "event_timestamp": "2025-12-25T18:30:00Z",
  "location": "Golden Gate Bridge, San Francisco",
  "participants": ["Sarah"]
}
```

#### Example Request (With Emotional Fields)

```json
{
  "user_id": "0000000000",
  "content": "User expressed frustration about work-life balance",
  "layer": "semantic",
  "type": "implicit",
  "importance": 0.7,
  "emotional_state": "frustrated",
  "valence": -0.6,
  "arousal": 0.7
}
```

#### Example Request (With Procedural Fields)

```json
{
  "user_id": "0000000000",
  "content": "User learned how to use options trading for hedging",
  "layer": "semantic",
  "type": "explicit",
  "importance": 0.8,
  "skill_name": "options_hedging",
  "proficiency_level": "intermediate"
}
```

#### Example Response (Success - Basic)

```json
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true
  }
}
```

#### Example Response (Success - With Typed Storage)

```json
{
  "status": "success",
  "memory_id": "mem_a1b2c3d4e5f6",
  "message": "Memory stored successfully",
  "storage": {
    "chromadb": true,
    "episodic": true
  }
}
```

#### Example Response (Error)

```json
{
  "status": "error",
  "memory_id": null,
  "message": "Missing required field: content",
  "error_code": "VALIDATION_ERROR"
}
```

---

### 2.2 DELETE `/v1/memories/{memory_id}`

Delete a specific memory by ID.

#### Request

```
DELETE /v1/memories/{memory_id}?user_id={user_id}
```

**Path Parameters:**
- `memory_id` (string, UUID, required): ID of memory to delete

**Query Parameters:**
- `user_id` (string, required): User ID for authorization

#### Example Request

```
DELETE /v1/memories/a1b2c3d4-e5f6-7890-abcd-ef1234567890?user_id=0000000000
```

#### Example Response (Success)

```json
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

#### Example Response (Not Found)

```json
{
  "status": "error",
  "deleted": false,
  "memory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Memory not found"
}
```

#### Example Response (Unauthorized)

```json
{
  "status": "error",
  "deleted": false,
  "memory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Unauthorized: memory belongs to different user"
}
```

---

## 3. Implementation

### 3.1 Storage Routing Logic

```python
# Storage routing based on optional fields:

# 1. Always store in ChromaDB with tracking metadata
upsert_memories(user_id, [memory])

# 2. Conditional typed table storage
if body.event_timestamp:
    store_to_episodic_memories(memory)

if body.emotional_state:
    store_to_emotional_memories(memory)

if body.skill_name:
    store_to_procedural_memories(memory)

# 3. Store tracking flags in ChromaDB metadata for efficient deletion
metadata = {
    ...existing_fields...,
    "stored_in_episodic": bool(body.event_timestamp),
    "stored_in_emotional": bool(body.emotional_state),
    "stored_in_procedural": bool(body.skill_name),
}
```

### 3.2 New Router: `src/routers/memories.py`

```python
"""
Direct memory storage and deletion endpoints.
Bypasses LangGraph pipeline for fast, explicit memory operations.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from src.schemas import DirectMemoryRequest, DirectMemoryResponse, DeleteMemoryResponse
from src.models import Memory
from src.services.storage import upsert_memories, COLLECTION_NAME
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name
from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn

logger = logging.getLogger("agentic_memories.memories")

router = APIRouter(prefix="/v1/memories", tags=["memories"])


@router.post("/direct", response_model=DirectMemoryResponse)
def store_memory_direct(body: DirectMemoryRequest) -> DirectMemoryResponse:
    """
    Store a pre-formatted memory directly without LLM extraction.

    Storage routing:
    - Always stores in ChromaDB
    - Conditionally stores to typed tables based on optional fields:
      - event_timestamp → episodic_memories
      - emotional_state → emotional_memories
      - skill_name → procedural_memories

    Performance target: < 3 seconds p95
    """
    from src.services.tracing import start_trace

    # Start trace
    trace = start_trace(
        name="store_memory_direct",
        user_id=body.user_id,
        metadata={
            "layer": body.layer,
            "importance": body.importance,
            "endpoint": "/v1/memories/direct"
        }
    )

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

        # Build metadata with tracking flags for efficient deletion
        memory_metadata = body.metadata or {}
        memory_metadata.update({
            "stored_in_episodic": store_episodic,
            "stored_in_emotional": store_emotional,
            "stored_in_procedural": store_procedural,
        })

        # Build Memory object
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
            metadata=memory_metadata,
        )

        # Track storage results
        storage_results = {}

        # 1. Always store in ChromaDB
        try:
            upsert_memories(body.user_id, [memory])
            storage_results["chromadb"] = True
        except Exception as e:
            logger.error(
                f"[memories.direct] ChromaDB storage failed: {e}",
                extra={"user_id": body.user_id, "memory_id": memory_id}
            )
            storage_results["chromadb"] = False

        # 2. Conditionally store to typed tables
        if store_episodic:
            try:
                _store_to_episodic(memory_id, body)
                storage_results["episodic"] = True
            except Exception as e:
                logger.error(f"[memories.direct] Episodic storage failed: {e}")
                storage_results["episodic"] = False

        if store_emotional:
            try:
                _store_to_emotional(memory_id, body)
                storage_results["emotional"] = True
            except Exception as e:
                logger.error(f"[memories.direct] Emotional storage failed: {e}")
                storage_results["emotional"] = False

        if store_procedural:
            try:
                _store_to_procedural(memory_id, body)
                storage_results["procedural"] = True
            except Exception as e:
                logger.error(f"[memories.direct] Procedural storage failed: {e}")
                storage_results["procedural"] = False

        # Success if ChromaDB succeeded (typed tables are best-effort)
        if storage_results.get("chromadb"):
            logger.info(
                "[memories.direct] Memory stored successfully",
                extra={
                    "user_id": body.user_id,
                    "memory_id": memory_id,
                    **storage_results
                }
            )

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
        logger.exception(
            f"[memories.direct] Unexpected error: {e}",
            extra={"user_id": body.user_id}
        )
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
    Delete a specific memory by ID.

    Deletion logic:
    1. Get metadata from ChromaDB to determine where memory exists
    2. Delete from ChromaDB (always)
    3. Delete from typed tables based on stored_in_* flags
    """
    from src.services.tracing import start_trace

    trace = start_trace(
        name="delete_memory",
        user_id=user_id,
        metadata={
            "memory_id": memory_id,
            "endpoint": f"/v1/memories/{memory_id}"
        }
    )

    try:
        # 1. Get metadata from ChromaDB to determine storage locations
        client = get_chroma_client()
        collection = client.get_or_create_collection(_standard_collection_name())
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

        # Track deletion results
        storage_results = {}

        # 2. Delete from ChromaDB (always)
        try:
            collection.delete(ids=[memory_id])
            storage_results["chromadb"] = True
        except Exception as e:
            logger.error(f"[memories.delete] ChromaDB deletion failed: {e}")
            storage_results["chromadb"] = False

        # 3. Delete from typed tables based on stored flags
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

        # Success if ChromaDB deleted (typed tables are best-effort)
        if storage_results.get("chromadb"):
            logger.info(
                "[memories.delete] Memory deleted successfully",
                extra={"user_id": user_id, "memory_id": memory_id, **storage_results}
            )
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


# =============================================================================
# Helper Functions for Typed Table Storage
# =============================================================================

def _store_to_episodic(memory_id: str, body: DirectMemoryRequest) -> None:
    """Store memory to episodic_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO episodic_memories (
                    id, user_id, content, event_timestamp, location,
                    participants, importance, confidence
                ) VALUES (
                    %(id)s, %(user_id)s, %(content)s, %(event_timestamp)s,
                    %(location)s, %(participants)s, %(importance)s, %(confidence)s
                ) ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    event_timestamp = EXCLUDED.event_timestamp
                """,
                {
                    "id": memory_id,
                    "user_id": body.user_id,
                    "content": body.content,
                    "event_timestamp": body.event_timestamp,
                    "location": body.location,
                    "participants": body.participants or [],
                    "importance": body.importance,
                    "confidence": body.confidence
                }
            )
            conn.commit()
    finally:
        release_timescale_conn(conn)


def _store_to_emotional(memory_id: str, body: DirectMemoryRequest) -> None:
    """Store memory to emotional_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO emotional_memories (
                    id, user_id, content, emotional_state, valence, arousal,
                    importance, confidence
                ) VALUES (
                    %(id)s, %(user_id)s, %(content)s, %(emotional_state)s,
                    %(valence)s, %(arousal)s, %(importance)s, %(confidence)s
                ) ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    emotional_state = EXCLUDED.emotional_state
                """,
                {
                    "id": memory_id,
                    "user_id": body.user_id,
                    "content": body.content,
                    "emotional_state": body.emotional_state,
                    "valence": body.valence,
                    "arousal": body.arousal,
                    "importance": body.importance,
                    "confidence": body.confidence
                }
            )
            conn.commit()
    finally:
        release_timescale_conn(conn)


def _store_to_procedural(memory_id: str, body: DirectMemoryRequest) -> None:
    """Store memory to procedural_memories table."""
    conn = get_timescale_conn()
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO procedural_memories (
                    id, user_id, content, skill_name, proficiency_level,
                    importance, confidence
                ) VALUES (
                    %(id)s, %(user_id)s, %(content)s, %(skill_name)s,
                    %(proficiency_level)s, %(importance)s, %(confidence)s
                ) ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    proficiency_level = EXCLUDED.proficiency_level
                """,
                {
                    "id": memory_id,
                    "user_id": body.user_id,
                    "content": body.content,
                    "skill_name": body.skill_name,
                    "proficiency_level": body.proficiency_level,
                    "importance": body.importance,
                    "confidence": body.confidence
                }
            )
            conn.commit()
    finally:
        release_timescale_conn(conn)


# =============================================================================
# Helper Functions for Typed Table Deletion
# =============================================================================

def _delete_from_episodic(memory_id: str, user_id: str) -> None:
    """Delete memory from episodic_memories table."""
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
    """Delete memory from emotional_memories table."""
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
    """Delete memory from procedural_memories table."""
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

### 3.3 Register Router in `src/app.py`

Add to the router imports and registration:

```python
# Add import
from src.routers import profile, portfolio, intents, memories

# Add router registration (after existing routers)
app.include_router(memories.router)
```

### 3.3 Add Schemas to `src/schemas.py`

Add the `DirectMemoryRequest`, `DirectMemoryResponse`, and `DeleteMemoryResponse` classes as shown in Section 2.

---

## 4. Design Decisions

Based on review with Annie team (2025-12-27, updated 2025-12-29):

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TimescaleDB Write | Skip semantic_memories | Use typed tables (episodic, emotional, procedural) instead |
| Schema | Extended with optional fields | Add episodic/emotional/procedural fields to trigger routing |
| Storage Routing | ChromaDB + conditional typed tables | Always ChromaDB, optional typed tables based on fields |
| Delete Logic | Check metadata flags | Use `stored_in_*` flags for efficient targeted deletion |
| Metadata Tracking | Add stored_in_* flags | Makes deletion efficient - no need to query all tables |
| Transaction Atomicity | Best-effort for store | ChromaDB required, typed tables best-effort |
| Collection Name | "memories" | Matches main pipeline in `storage.py` |
| Embedding Timeout | None | Trust OpenAI (~500ms typical) |
| Tag Limit | 10 tags max | Sufficient flexibility for complex memories |
| Delete Success | ChromaDB required | Typed table deletion is best-effort |
| Performance Threshold | 3s | Safe buffer for cold starts/network variance |

### Key Changes from Original Design

| Section | Original | Updated |
|---------|----------|---------|
| TimescaleDB write | semantic_memories table | Skip - use typed tables instead |
| Schema | Basic fields only | Add optional episodic/emotional/procedural fields |
| Routing | ChromaDB + semantic_memories | ChromaDB + conditional typed tables |
| Delete | Try all tables | Check metadata flags, delete from relevant tables |
| Metadata | Basic | Add stored_in_* flags for delete tracking |

---

## 5. Testing

### 5.1 Unit Tests

Create `tests/test_memories_router.py`:

```python
"""Tests for direct memory storage and deletion endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.app import app


client = TestClient(app)


class TestStoreMemoryDirect:
    """Tests for POST /v1/memories/direct"""

    def test_store_success_minimal(self):
        """Test storing memory with minimal required fields."""
        with patch("src.routers.memories.generate_embedding") as mock_embed:
            with patch("src.routers.memories.upsert_memories") as mock_upsert:
                with patch("src.routers.memories._store_to_timescale") as mock_ts:
                    mock_embed.return_value = [0.1] * 1536
                    mock_ts.return_value = True

                    response = client.post("/v1/memories/direct", json={
                        "user_id": "test_user",
                        "content": "Test memory content"
                    })

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"
                    assert data["memory_id"] is not None
                    assert data["storage"]["chromadb"] is True

    def test_store_success_all_fields(self):
        """Test storing memory with all optional fields."""
        with patch("src.routers.memories.generate_embedding") as mock_embed:
            with patch("src.routers.memories.upsert_memories") as mock_upsert:
                with patch("src.routers.memories._store_to_timescale") as mock_ts:
                    mock_embed.return_value = [0.1] * 1536
                    mock_ts.return_value = True

                    response = client.post("/v1/memories/direct", json={
                        "user_id": "test_user",
                        "content": "User is allergic to shellfish",
                        "layer": "semantic",
                        "type": "explicit",
                        "importance": 0.95,
                        "confidence": 0.98,
                        "persona_tags": ["health", "allergy"],
                        "metadata": {
                            "source": "llm_explicit",
                            "conversation_id": "conv_123"
                        }
                    })

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"

    def test_store_embedding_failure(self):
        """Test handling of embedding generation failure."""
        with patch("src.routers.memories.generate_embedding") as mock_embed:
            mock_embed.return_value = None

            response = client.post("/v1/memories/direct", json={
                "user_id": "test_user",
                "content": "Test memory"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert data["error_code"] == "EMBEDDING_ERROR"

    def test_store_validation_error(self):
        """Test validation of required fields."""
        response = client.post("/v1/memories/direct", json={
            "user_id": "test_user"
            # Missing required 'content' field
        })

        assert response.status_code == 422  # Pydantic validation error


class TestDeleteMemory:
    """Tests for DELETE /v1/memories/{memory_id}"""

    def test_delete_success(self):
        """Test successful memory deletion."""
        with patch("src.routers.memories._delete_from_chromadb") as mock_chroma:
            with patch("src.routers.memories._delete_from_timescale") as mock_ts:
                mock_chroma.return_value = (True, False)
                mock_ts.return_value = (True, False)

                response = client.delete(
                    "/v1/memories/test-memory-id?user_id=test_user"
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["deleted"] is True

    def test_delete_not_found(self):
        """Test deletion of non-existent memory."""
        with patch("src.routers.memories._delete_from_chromadb") as mock_chroma:
            with patch("src.routers.memories._delete_from_timescale") as mock_ts:
                mock_chroma.return_value = (False, True)
                mock_ts.return_value = (False, True)

                response = client.delete(
                    "/v1/memories/nonexistent-id?user_id=test_user"
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "error"
                assert data["deleted"] is False
                assert "not found" in data["message"].lower()

    def test_delete_missing_user_id(self):
        """Test deletion without user_id parameter."""
        response = client.delete("/v1/memories/test-memory-id")

        assert response.status_code == 422  # Missing required query param
```

### 5.2 Integration Tests

Create `tests/integration/test_memories_e2e.py`:

```python
"""End-to-end integration tests for memory operations."""

import pytest
from fastapi.testclient import TestClient

from src.app import app


client = TestClient(app)


@pytest.mark.integration
class TestMemoryLifecycle:
    """Test full store -> retrieve -> delete lifecycle."""

    def test_store_retrieve_delete_lifecycle(self):
        """Test complete memory lifecycle."""
        user_id = "integration_test_user"

        # 1. Store memory
        store_response = client.post("/v1/memories/direct", json={
            "user_id": user_id,
            "content": "Integration test memory - should be deleted",
            "importance": 0.5,
            "persona_tags": ["test"]
        })

        assert store_response.status_code == 200
        store_data = store_response.json()
        assert store_data["status"] == "success"
        memory_id = store_data["memory_id"]

        # 2. Verify memory exists via retrieve
        retrieve_response = client.get(
            f"/v1/retrieve?user_id={user_id}&query=integration test"
        )
        assert retrieve_response.status_code == 200
        results = retrieve_response.json()["results"]
        assert any(r["id"] == memory_id for r in results)

        # 3. Delete memory
        delete_response = client.delete(
            f"/v1/memories/{memory_id}?user_id={user_id}"
        )
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert delete_data["status"] == "success"
        assert delete_data["deleted"] is True

        # 4. Verify memory no longer exists
        retrieve_after = client.get(
            f"/v1/retrieve?user_id={user_id}&query=integration test"
        )
        results_after = retrieve_after.json()["results"]
        assert not any(r["id"] == memory_id for r in results_after)
```

### 5.3 Performance Tests

Create `tests/performance/test_direct_memory_latency.py`:

```python
"""Performance tests for direct memory storage latency."""

import pytest
import time
from fastapi.testclient import TestClient

from src.app import app


client = TestClient(app)


@pytest.mark.performance
class TestDirectMemoryPerformance:
    """Performance benchmarks for direct memory operations."""

    def test_store_latency_under_3_seconds(self):
        """Verify direct storage completes in under 3 seconds."""
        start = time.perf_counter()

        response = client.post("/v1/memories/direct", json={
            "user_id": "perf_test_user",
            "content": "Performance test memory",
            "importance": 0.5
        })

        elapsed = time.perf_counter() - start

        assert response.status_code == 200
        assert elapsed < 3.0, f"Storage took {elapsed:.2f}s, exceeds 3s target"

    def test_delete_latency_under_1_second(self):
        """Verify deletion completes in under 1 second."""
        # First store a memory
        store_response = client.post("/v1/memories/direct", json={
            "user_id": "perf_test_user",
            "content": "Memory to delete for perf test"
        })
        memory_id = store_response.json()["memory_id"]

        # Time the deletion
        start = time.perf_counter()

        response = client.delete(
            f"/v1/memories/{memory_id}?user_id=perf_test_user"
        )

        elapsed = time.perf_counter() - start

        assert response.status_code == 200
        assert elapsed < 1.0, f"Deletion took {elapsed:.2f}s, exceeds 1s target"
```

---

## 6. Rollout Plan

### Phase 1: Implementation (Day 1)

1. Add schemas to `src/schemas.py`
2. Create `src/routers/memories.py`
3. Register router in `src/app.py`
4. Add unit tests

### Phase 2: Testing (Day 2)

1. Run full test suite
2. Manual testing with Postman/curl
3. Integration tests against local stack

### Phase 3: Deploy (Day 3)

1. Deploy to staging
2. Validate with Annie dev environment
3. Monitor latency metrics
4. Deploy to production

---

## 7. Monitoring

### Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| `store_direct_latency_p95` | < 2s | > 3s |
| `store_direct_error_rate` | < 1% | > 5% |
| `delete_latency_p95` | < 500ms | > 1s |
| `delete_error_rate` | < 1% | > 5% |
| `storage_consistency` | 100% | < 99% |

### Log Patterns

```
# Successful storage
[memories.direct] Memory stored successfully user_id=X memory_id=Y chromadb=true timescale=true

# Storage failure
[memories.direct] Storage failed in all backends user_id=X

# Successful deletion
[memories.delete] Memory deleted successfully user_id=X memory_id=Y

# Deletion not found
[memories.delete] Memory not found user_id=X memory_id=Y
```

---

## 8. Appendix

### A. Existing Patterns Referenced

- **Storage**: `src/services/storage.py` - `upsert_memories()` function
- **Embedding**: `src/services/embedding_utils.py` - `generate_embedding()` function
- **Retrieval**: `src/services/retrieval.py` - `_standard_collection_name()` function
- **Router Pattern**: `src/routers/profile.py`, `src/routers/portfolio.py`
- **Schema Pattern**: `src/schemas.py` - Pydantic models with Field() defaults

### B. Dependencies

- FastAPI router
- Pydantic v2 schemas
- ChromaDB client
- TimescaleDB/PostgreSQL
- OpenAI embeddings (existing)
- Langfuse tracing (existing)
