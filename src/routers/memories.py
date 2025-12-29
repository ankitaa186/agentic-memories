"""
Direct Memory API Router (Story 10.1, 10.2, 10.3)

Provides direct memory storage and deletion endpoints that bypass the slow LangGraph
ingestion pipeline, enabling sub-3-second latency for pre-formatted memories.

Story 10.2 adds typed table storage for episodic, emotional, and procedural memories.
Story 10.3 adds cross-storage memory deletion via DELETE /v1/memories/{memory_id}.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.models import Memory
from src.schemas import DeleteMemoryResponse, DirectMemoryRequest, DirectMemoryResponse
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name
from src.services.storage import upsert_memories

logger = logging.getLogger("agentic_memories.memories")

router = APIRouter(prefix="/v1/memories", tags=["memories"])


# =============================================================================
# Typed Table Storage Helper Functions (Story 10.2)
# =============================================================================


def _store_episodic(memory_id: str, body: DirectMemoryRequest) -> bool:
    """
    Store memory in episodic_memories table.

    Args:
        memory_id: The memory ID to use as primary key
        body: DirectMemoryRequest with episodic fields

    Returns:
        bool: True if storage succeeded, False otherwise
    """
    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[memories._store_episodic] memory_id=%s connection_unavailable",
            memory_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            # Build metadata JSON
            metadata = dict(body.metadata) if body.metadata else {}
            metadata["source"] = "direct_api"

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
                    body.event_type,
                    body.content,
                    json.dumps(body.location) if body.location else None,  # JSONB column
                    body.participants,  # TEXT[] array
                    body.importance,
                    body.persona_tags if body.persona_tags else None,  # TEXT[] array
                    json.dumps(metadata) if metadata else None,
                ),
            )
        conn.commit()
        logger.info(
            "[memories._store_episodic] memory_id=%s stored_successfully",
            memory_id,
        )
        return True
    except Exception as exc:
        logger.error(
            "[memories._store_episodic] memory_id=%s error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_timescale_conn(conn)


def _store_emotional(memory_id: str, body: DirectMemoryRequest) -> bool:
    """
    Store memory in emotional_memories table.

    Args:
        memory_id: The memory ID to use as primary key
        body: DirectMemoryRequest with emotional fields

    Returns:
        bool: True if storage succeeded, False otherwise
    """
    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[memories._store_emotional] memory_id=%s connection_unavailable",
            memory_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            # Build metadata JSON
            metadata = dict(body.metadata) if body.metadata else {}
            metadata["source"] = "direct_api"

            # Apply defaults per story spec
            valence = body.valence if body.valence is not None else 0.0
            arousal = body.arousal if body.arousal is not None else 0.5

            cur.execute(
                """
                INSERT INTO emotional_memories (
                    id, user_id, timestamp, emotional_state, valence, arousal,
                    context, trigger_event, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    memory_id,
                    body.user_id,
                    datetime.now(timezone.utc),  # Use current timestamp
                    body.emotional_state,
                    valence,
                    arousal,
                    body.content,  # Use content as context
                    body.trigger_event,
                    json.dumps(metadata) if metadata else None,
                ),
            )
        conn.commit()
        logger.info(
            "[memories._store_emotional] memory_id=%s stored_successfully",
            memory_id,
        )
        return True
    except Exception as exc:
        logger.error(
            "[memories._store_emotional] memory_id=%s error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_timescale_conn(conn)


def _store_procedural(memory_id: str, body: DirectMemoryRequest) -> bool:
    """
    Store memory in procedural_memories table with UPSERT logic.

    Args:
        memory_id: The memory ID to use as primary key
        body: DirectMemoryRequest with procedural fields

    Returns:
        bool: True if storage succeeded, False otherwise
    """
    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[memories._store_procedural] memory_id=%s connection_unavailable",
            memory_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            # Build metadata JSON
            metadata = dict(body.metadata) if body.metadata else {}
            metadata["source"] = "direct_api"

            # Apply defaults per story spec
            proficiency_level = body.proficiency_level or "beginner"

            cur.execute(
                """
                INSERT INTO procedural_memories (
                    id, user_id, skill_name, proficiency_level, context, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    proficiency_level = EXCLUDED.proficiency_level,
                    context = EXCLUDED.context,
                    metadata = EXCLUDED.metadata
                """,
                (
                    memory_id,
                    body.user_id,
                    body.skill_name,
                    proficiency_level,
                    body.content,  # Use content as context
                    json.dumps(metadata) if metadata else None,
                ),
            )
        conn.commit()
        logger.info(
            "[memories._store_procedural] memory_id=%s stored_successfully",
            memory_id,
        )
        return True
    except Exception as exc:
        logger.error(
            "[memories._store_procedural] memory_id=%s error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_timescale_conn(conn)


@router.post("/direct", response_model=DirectMemoryResponse)
def store_memory_direct(body: DirectMemoryRequest) -> DirectMemoryResponse:
    """
    Store a memory directly to ChromaDB without LLM extraction.

    This endpoint provides fast memory storage (sub-3s p95 latency) for clients
    that have already formatted their memories. Bypasses the full ingestion
    pipeline which can take 60-100 seconds.

    Story 10.2: If type-specific fields are provided (event_timestamp, emotional_state,
    skill_name), the memory is also routed to the corresponding typed table
    (episodic_memories, emotional_memories, procedural_memories).

    Returns:
        DirectMemoryResponse with status, memory_id, and storage confirmation.
    """
    start_time = time.perf_counter()

    # Determine typed storage routing (Story 10.2)
    store_episodic = body.event_timestamp is not None
    store_emotional = body.emotional_state is not None
    store_procedural = body.skill_name is not None

    logger.info(
        "[memories.direct] user_id=%s content_length=%d importance=%.2f "
        "store_episodic=%s store_emotional=%s store_procedural=%s",
        body.user_id,
        len(body.content),
        body.importance,
        store_episodic,
        store_emotional,
        store_procedural,
    )

    # Generate unique memory IDs
    # ChromaDB uses mem_XXXX format, typed tables need proper UUID
    memory_uuid = uuid.uuid4()
    memory_id = f"mem_{memory_uuid.hex[:12]}"  # For ChromaDB
    typed_table_id = str(memory_uuid)  # Full UUID for typed tables

    # Generate embedding
    embed_start = time.perf_counter()
    try:
        embedding = generate_embedding(body.content)
        embed_elapsed_ms = int((time.perf_counter() - embed_start) * 1000)
        logger.info(
            "[memories.direct] user_id=%s memory_id=%s embedding_generated latency_ms=%d dim=%d",
            body.user_id,
            memory_id,
            embed_elapsed_ms,
            len(embedding) if embedding else 0,
        )
    except Exception as exc:
        logger.error(
            "[memories.direct] user_id=%s embedding_failed error=%s",
            body.user_id,
            exc,
            exc_info=True,
        )
        return DirectMemoryResponse(
            status="error",
            memory_id=None,
            message="Failed to generate embedding",
            error_code="EMBEDDING_ERROR",
        )

    if embedding is None:
        logger.error(
            "[memories.direct] user_id=%s embedding_returned_none",
            body.user_id,
        )
        return DirectMemoryResponse(
            status="error",
            memory_id=None,
            message="Failed to generate embedding",
            error_code="EMBEDDING_ERROR",
        )

    # Track typed table storage results (Story 10.2)
    # Initialize to False - will be updated after successful storage
    stored_in_episodic = False
    stored_in_emotional = False
    stored_in_procedural = False

    # Store to typed tables BEFORE ChromaDB (best-effort, failures logged but don't fail request)
    # Note: typed tables use UUID format, ChromaDB uses mem_XXXX format
    if store_episodic:
        stored_in_episodic = _store_episodic(typed_table_id, body)
        if not stored_in_episodic:
            logger.warning(
                "[memories.direct] user_id=%s memory_id=%s episodic_storage_failed (best-effort)",
                body.user_id,
                memory_id,
            )

    if store_emotional:
        stored_in_emotional = _store_emotional(typed_table_id, body)
        if not stored_in_emotional:
            logger.warning(
                "[memories.direct] user_id=%s memory_id=%s emotional_storage_failed (best-effort)",
                body.user_id,
                memory_id,
            )

    if store_procedural:
        stored_in_procedural = _store_procedural(typed_table_id, body)
        if not stored_in_procedural:
            logger.warning(
                "[memories.direct] user_id=%s memory_id=%s procedural_storage_failed (best-effort)",
                body.user_id,
                memory_id,
            )

    # Build metadata with source tracking and typed storage flags (Story 10.2 - AC #3)
    metadata = dict(body.metadata) if body.metadata else {}
    metadata.update({
        "source": "direct_api",
        "typed_table_id": typed_table_id,  # UUID for typed table lookups
        "stored_in_episodic": stored_in_episodic,
        "stored_in_emotional": stored_in_emotional,
        "stored_in_procedural": stored_in_procedural,
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
        metadata=metadata,
    )

    # Store to ChromaDB (required for success - source of truth)
    storage_start = time.perf_counter()
    try:
        stored_ids = upsert_memories(body.user_id, [memory])
        storage_elapsed_ms = int((time.perf_counter() - storage_start) * 1000)
        logger.info(
            "[memories.direct] user_id=%s memory_id=%s chromadb_storage_completed latency_ms=%d",
            body.user_id,
            memory_id,
            storage_elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "[memories.direct] user_id=%s memory_id=%s chromadb_storage_failed error=%s",
            body.user_id,
            memory_id,
            exc,
            exc_info=True,
        )
        return DirectMemoryResponse(
            status="error",
            memory_id=None,
            message="Failed to store memory in ChromaDB",
            error_code="STORAGE_ERROR",
        )

    if not stored_ids:
        logger.error(
            "[memories.direct] user_id=%s memory_id=%s chromadb_storage_returned_empty",
            body.user_id,
            memory_id,
        )
        return DirectMemoryResponse(
            status="error",
            memory_id=None,
            message="Failed to store memory in ChromaDB",
            error_code="STORAGE_ERROR",
        )

    total_elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info(
        "[memories.direct] user_id=%s memory_id=%s success total_latency_ms=%d "
        "episodic=%s emotional=%s procedural=%s",
        body.user_id,
        memory_id,
        total_elapsed_ms,
        stored_in_episodic,
        stored_in_emotional,
        stored_in_procedural,
    )

    # Build storage status response (Story 10.2 - AC #4)
    storage_status: Dict[str, bool] = {"chromadb": True}
    if store_episodic:
        storage_status["episodic"] = stored_in_episodic
    if store_emotional:
        storage_status["emotional"] = stored_in_emotional
    if store_procedural:
        storage_status["procedural"] = stored_in_procedural

    return DirectMemoryResponse(
        status="success",
        memory_id=memory_id,
        message="Memory stored successfully",
        storage=storage_status,
    )


# =============================================================================
# Typed Table Deletion Helper Functions (Story 10.3)
# =============================================================================


def _delete_from_episodic(memory_id: str, user_id: str) -> bool:
    """
    Delete memory from episodic_memories table.

    Args:
        memory_id: The memory ID to delete
        user_id: The user ID for logging

    Returns:
        bool: True if deletion succeeded or row didn't exist, False on error
    """
    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[memories._delete_from_episodic] memory_id=%s connection_unavailable",
            memory_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM episodic_memories WHERE id = %s",
                (memory_id,),
            )
            deleted_count = cur.rowcount
        conn.commit()
        logger.info(
            "[memories._delete_from_episodic] memory_id=%s user_id=%s rows_deleted=%d",
            memory_id,
            user_id,
            deleted_count,
        )
        return True
    except Exception as exc:
        logger.error(
            "[memories._delete_from_episodic] memory_id=%s error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_timescale_conn(conn)


def _delete_from_emotional(memory_id: str, user_id: str) -> bool:
    """
    Delete memory from emotional_memories table.

    Args:
        memory_id: The memory ID to delete
        user_id: The user ID for logging

    Returns:
        bool: True if deletion succeeded or row didn't exist, False on error
    """
    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[memories._delete_from_emotional] memory_id=%s connection_unavailable",
            memory_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM emotional_memories WHERE id = %s",
                (memory_id,),
            )
            deleted_count = cur.rowcount
        conn.commit()
        logger.info(
            "[memories._delete_from_emotional] memory_id=%s user_id=%s rows_deleted=%d",
            memory_id,
            user_id,
            deleted_count,
        )
        return True
    except Exception as exc:
        logger.error(
            "[memories._delete_from_emotional] memory_id=%s error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_timescale_conn(conn)


def _delete_from_procedural(memory_id: str, user_id: str) -> bool:
    """
    Delete memory from procedural_memories table.

    Args:
        memory_id: The memory ID to delete
        user_id: The user ID for logging

    Returns:
        bool: True if deletion succeeded or row didn't exist, False on error
    """
    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[memories._delete_from_procedural] memory_id=%s connection_unavailable",
            memory_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM procedural_memories WHERE id = %s",
                (memory_id,),
            )
            deleted_count = cur.rowcount
        conn.commit()
        logger.info(
            "[memories._delete_from_procedural] memory_id=%s user_id=%s rows_deleted=%d",
            memory_id,
            user_id,
            deleted_count,
        )
        return True
    except Exception as exc:
        logger.error(
            "[memories._delete_from_procedural] memory_id=%s error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            release_timescale_conn(conn)


# =============================================================================
# Delete Memory Endpoint (Story 10.3)
# =============================================================================


@router.delete("/{memory_id}", response_model=DeleteMemoryResponse)
def delete_memory(
    memory_id: str,
    user_id: str = Query(..., description="User ID for authorization"),
) -> DeleteMemoryResponse:
    """
    Delete a memory from all storage backends.

    This endpoint performs cross-storage deletion:
    1. Gets memory metadata from ChromaDB to find stored_in_* flags and verify user_id
    2. Authorization check: compare request user_id with metadata user_id
    3. Delete from typed tables based on metadata flags (best-effort)
    4. Delete from ChromaDB (required for success)

    Args:
        memory_id: The memory ID to delete (path parameter)
        user_id: The user ID for authorization (query parameter)

    Returns:
        DeleteMemoryResponse with deletion status per backend

    Raises:
        HTTPException 403: If user_id doesn't match memory owner
    """
    start_time = time.perf_counter()

    logger.info(
        "[memories.delete] memory_id=%s user_id=%s starting",
        memory_id,
        user_id,
    )

    # Get ChromaDB client and collection
    chroma_client = get_chroma_client()
    if chroma_client is None:
        logger.error(
            "[memories.delete] memory_id=%s chromadb_client_unavailable",
            memory_id,
        )
        return DeleteMemoryResponse(
            status="error",
            deleted=False,
            memory_id=memory_id,
            message="ChromaDB client unavailable",
        )

    try:
        collection_name = _standard_collection_name()
        collection = chroma_client.get_collection(collection_name)
    except Exception as exc:
        logger.error(
            "[memories.delete] memory_id=%s collection_error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        return DeleteMemoryResponse(
            status="error",
            deleted=False,
            memory_id=memory_id,
            message="Failed to access ChromaDB collection",
        )

    # Step 1: Get memory metadata from ChromaDB
    try:
        result = collection.get(ids=[memory_id], include=["metadatas"])
        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])
    except Exception as exc:
        logger.error(
            "[memories.delete] memory_id=%s get_metadata_error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        return DeleteMemoryResponse(
            status="error",
            deleted=False,
            memory_id=memory_id,
            message="Failed to retrieve memory metadata",
        )

    # Check if memory exists
    if not ids or memory_id not in ids:
        logger.warning(
            "[memories.delete] memory_id=%s not_found",
            memory_id,
        )
        return DeleteMemoryResponse(
            status="error",
            deleted=False,
            memory_id=memory_id,
            message="Memory not found",
        )

    # Get metadata for authorization and typed table flags
    idx = ids.index(memory_id)
    metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}

    # Step 2: Authorization check
    memory_user_id = metadata.get("user_id")
    if memory_user_id and memory_user_id != user_id:
        logger.warning(
            "[memories.delete] memory_id=%s unauthorized request_user=%s memory_user=%s",
            memory_id,
            user_id,
            memory_user_id,
        )
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: memory belongs to different user",
        )

    # Extract typed table flags and ID from metadata
    stored_in_episodic = metadata.get("stored_in_episodic", False)
    stored_in_emotional = metadata.get("stored_in_emotional", False)
    stored_in_procedural = metadata.get("stored_in_procedural", False)
    typed_table_id = metadata.get("typed_table_id")  # UUID for typed table lookups

    logger.info(
        "[memories.delete] memory_id=%s typed_table_id=%s stored_in_episodic=%s stored_in_emotional=%s stored_in_procedural=%s",
        memory_id,
        typed_table_id,
        stored_in_episodic,
        stored_in_emotional,
        stored_in_procedural,
    )

    # Step 3: Delete from typed tables (best-effort)
    # Use typed_table_id (UUID) for typed table deletions
    storage_status: Dict[str, bool] = {}

    if stored_in_episodic and typed_table_id:
        episodic_deleted = _delete_from_episodic(typed_table_id, user_id)
        storage_status["episodic"] = episodic_deleted
        if not episodic_deleted:
            logger.warning(
                "[memories.delete] memory_id=%s episodic_deletion_failed (best-effort)",
                memory_id,
            )

    if stored_in_emotional and typed_table_id:
        emotional_deleted = _delete_from_emotional(typed_table_id, user_id)
        storage_status["emotional"] = emotional_deleted
        if not emotional_deleted:
            logger.warning(
                "[memories.delete] memory_id=%s emotional_deletion_failed (best-effort)",
                memory_id,
            )

    if stored_in_procedural and typed_table_id:
        procedural_deleted = _delete_from_procedural(typed_table_id, user_id)
        storage_status["procedural"] = procedural_deleted
        if not procedural_deleted:
            logger.warning(
                "[memories.delete] memory_id=%s procedural_deletion_failed (best-effort)",
                memory_id,
            )

    # Step 4: Delete from ChromaDB (required for success)
    try:
        collection.delete(ids=[memory_id])
        storage_status["chromadb"] = True
        chromadb_deleted = True
        logger.info(
            "[memories.delete] memory_id=%s chromadb_deleted",
            memory_id,
        )
    except Exception as exc:
        logger.error(
            "[memories.delete] memory_id=%s chromadb_deletion_error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        storage_status["chromadb"] = False
        chromadb_deleted = False

    # Step 5: Build response
    total_elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    if chromadb_deleted:
        logger.info(
            "[memories.delete] memory_id=%s user_id=%s success total_latency_ms=%d storage=%s",
            memory_id,
            user_id,
            total_elapsed_ms,
            storage_status,
        )
        return DeleteMemoryResponse(
            status="success",
            deleted=True,
            memory_id=memory_id,
            storage=storage_status,
            message="Memory deleted successfully",
        )
    else:
        logger.error(
            "[memories.delete] memory_id=%s user_id=%s failed total_latency_ms=%d storage=%s",
            memory_id,
            user_id,
            total_elapsed_ms,
            storage_status,
        )
        return DeleteMemoryResponse(
            status="error",
            deleted=False,
            memory_id=memory_id,
            storage=storage_status,
            message="Failed to delete from ChromaDB",
        )
