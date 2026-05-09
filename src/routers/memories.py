"""
Direct Memory API Router (Story 10.1, 10.2, 10.3)

Provides direct memory storage and deletion endpoints that bypass the slow LangGraph
ingestion pipeline, enabling sub-3-second latency for pre-formatted memories.

Story 10.2 adds typed table storage for episodic, emotional, and procedural memories.
Story 10.3 adds cross-storage memory deletion via DELETE /v1/memories/{memory_id}.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.config import get_default_short_term_ttl_seconds
from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.models import Memory
from src.schemas import (
    DeleteMemoryResponse,
    DirectMemoryRequest,
    DirectMemoryResponse,
    PatchMemoryRequest,
    PatchMemoryResponse,
    PatchMemoryTypedTableUpdated,
    _Unset,
)
from src.services._constants import SYSTEM_MANAGED_FIELDS
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name
from src.services.storage import (
    _update_emotional_row,
    _update_episodic_row,
    _update_procedural_row,
    get_chroma_record,
    update_chroma_record,
    upsert_memories,
)

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
                    json.dumps(body.location)
                    if body.location
                    else None,  # JSONB column
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


def _rollback_typed_tables(
    typed_table_id: str,
    user_id: str,
    stored_in_episodic: bool,
    stored_in_emotional: bool,
    stored_in_procedural: bool,
) -> None:
    """
    Rollback typed table inserts when ChromaDB storage fails.

    This ensures consistency by removing orphaned rows from typed tables
    when the primary ChromaDB storage fails. Best-effort cleanup - failures
    are logged but don't raise exceptions.

    Args:
        typed_table_id: The UUID used for typed table primary keys
        user_id: The user ID for logging context
        stored_in_episodic: Whether episodic insert succeeded
        stored_in_emotional: Whether emotional insert succeeded
        stored_in_procedural: Whether procedural insert succeeded
    """
    if stored_in_episodic:
        try:
            _delete_from_episodic(typed_table_id, user_id)
            logger.info(
                "[memories._rollback_typed_tables] user_id=%s typed_table_id=%s episodic_rolled_back",
                user_id,
                typed_table_id,
            )
        except Exception as exc:
            logger.warning(
                "[memories._rollback_typed_tables] user_id=%s typed_table_id=%s episodic_rollback_failed error=%s",
                user_id,
                typed_table_id,
                exc,
            )

    if stored_in_emotional:
        try:
            _delete_from_emotional(typed_table_id, user_id)
            logger.info(
                "[memories._rollback_typed_tables] user_id=%s typed_table_id=%s emotional_rolled_back",
                user_id,
                typed_table_id,
            )
        except Exception as exc:
            logger.warning(
                "[memories._rollback_typed_tables] user_id=%s typed_table_id=%s emotional_rollback_failed error=%s",
                user_id,
                typed_table_id,
                exc,
            )

    if stored_in_procedural:
        try:
            _delete_from_procedural(typed_table_id, user_id)
            logger.info(
                "[memories._rollback_typed_tables] user_id=%s typed_table_id=%s procedural_rolled_back",
                user_id,
                typed_table_id,
            )
        except Exception as exc:
            logger.warning(
                "[memories._rollback_typed_tables] user_id=%s typed_table_id=%s procedural_rollback_failed error=%s",
                user_id,
                typed_table_id,
                exc,
            )


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
    metadata.update(
        {
            "source": "direct_api",
            "typed_table_id": typed_table_id,  # UUID for typed table lookups
            "stored_in_episodic": stored_in_episodic,
            "stored_in_emotional": stored_in_emotional,
            "stored_in_procedural": stored_in_procedural,
        }
    )

    # Resolve the per-record TTL.
    # - If the caller passes `ttl_seconds`, honor it on ANY layer (AM-X.0). The
    #   downstream metadata builder (`src/services/storage.py:_build_metadata`)
    #   writes `ttl_epoch` whenever `memory.ttl is not None`, regardless of layer,
    #   and the soft-TTL sweep evicts on `ttl_epoch <= now`.
    # - If the caller omits `ttl_seconds`, preserve the existing per-layer
    #   defaults: short-term gets `get_default_short_term_ttl_seconds()`;
    #   semantic / long-term / typed layers stay immortal (ttl=None).
    if body.ttl_seconds is not None:
        ttl_seconds = body.ttl_seconds
    elif body.layer == "short-term":
        ttl_seconds = get_default_short_term_ttl_seconds()
    else:
        ttl_seconds = None

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
        ttl=ttl_seconds,
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
        # Rollback typed table inserts to avoid orphaned rows
        _rollback_typed_tables(
            typed_table_id,
            body.user_id,
            stored_in_episodic,
            stored_in_emotional,
            stored_in_procedural,
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
        # Rollback typed table inserts to avoid orphaned rows
        _rollback_typed_tables(
            typed_table_id,
            body.user_id,
            stored_in_episodic,
            stored_in_emotional,
            stored_in_procedural,
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
# Patch Memory Endpoint (AM-X.1)
# =============================================================================


# Layers that store rows in typed Postgres tables. Flips into or out of these
# layers are rejected with 422 in v1 (AC11). The non-typed set is the
# allowed-flip-targets set.
_TYPED_LAYERS = frozenset({"episodic", "procedural", "emotional"})
_NON_TYPED_LAYERS = frozenset({"short-term", "semantic", "long-term"})


def _content_hash(content: str) -> str:
    """Compute the same content_hash used by `_build_metadata` (storage.py).

    Kept locally so PATCH can short-circuit embedding regen without re-reading
    the storage helper. If `_build_metadata`'s formula ever changes, update
    both places.
    """
    return hashlib.sha256(content.strip().lower().encode()).hexdigest()


def _shallow_merge_metadata(
    existing: Dict[str, Any],
    patch: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply the AM-X.1 shallow-merge semantics with `__delete__` sentinel.

    - Keys in `patch` with value `"__delete__"` are removed from `existing`.
    - All other keys in `patch` overwrite `existing`.
    - Keys absent from `patch` are preserved from `existing`.

    Returns a new dict; does not mutate inputs. The caller is responsible for
    ensuring no SYSTEM_MANAGED_FIELDS key is present in `patch`
    (AC8 router-level guard).
    """
    merged = dict(existing)
    for key, value in patch.items():
        if value == "__delete__":
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def _validate_patch_metadata(patch_metadata: Dict[str, Any]) -> None:
    """Reject patch metadata that touches system-managed keys (AC8).

    The router-level guard. `update_chroma_record` enforces a defense-in-depth
    strip (AC20), but we want to surface caller errors as 422 here rather than
    silently dropping the keys.
    """
    bad = sorted(set(patch_metadata.keys()) & SYSTEM_MANAGED_FIELDS)
    if bad:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "system_managed_metadata_keys",
                "message": (
                    "The following metadata keys are system-managed and cannot "
                    "be set or deleted via PATCH: "
                    + ", ".join(bad)
                    + ". See SYSTEM_MANAGED_FIELDS in src/services/_constants.py."
                ),
                "fields": bad,
            },
        )


def _validate_layer_flip(current_layer: Optional[str], new_layer: str) -> None:
    """Enforce AC10/AC11: flips between non-typed layers allowed; flips
    into/out of typed-storage layers return 422.
    """
    if current_layer == new_layer:
        return
    if current_layer in _TYPED_LAYERS or new_layer in _TYPED_LAYERS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "layer_flip_unsupported",
                "message": (
                    "layer flip into/out of typed-storage layer not supported "
                    "in v1; delete and recreate."
                ),
                "current_layer": current_layer,
                "new_layer": new_layer,
            },
        )
    if new_layer not in _NON_TYPED_LAYERS:
        # Defense-in-depth — schema's Literal already constrains this set.
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_layer",
                "message": f"Unsupported layer for PATCH: {new_layer!r}",
            },
        )


@router.patch("/{memory_id}", response_model=PatchMemoryResponse)
def patch_memory(
    memory_id: str,
    body: PatchMemoryRequest,
    user_id: str = Query(..., description="User ID for authorization"),
) -> PatchMemoryResponse:
    """Partial update of a memory record (AM-X.1).

    Mutates `content`, `metadata`, `layer`, `importance`, `ttl_seconds` on an
    existing memory by id. Preserves the memory id and original `timestamp`
    (AC1). Embedding regen is synchronous when `content` changes (AC6, AC14)
    and skipped when the new content hashes to the same value as stored (AC7).

    See `.claude/scrum/stories/AM-X.1.md` for the full AC list.
    """
    start_time = time.perf_counter()
    warnings: List[str] = []

    logger.info("[memories.patch] memory_id=%s user_id=%s starting", memory_id, user_id)

    # ---- Step 1: Read current Chroma record ---------------------------------
    chroma_client = get_chroma_client()
    if chroma_client is None:
        logger.error(
            "[memories.patch] memory_id=%s chromadb_client_unavailable", memory_id
        )
        raise HTTPException(status_code=503, detail="ChromaDB client unavailable")

    try:
        record = get_chroma_record(memory_id)
    except Exception as exc:
        logger.error(
            "[memories.patch] memory_id=%s get_record_error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve memory metadata"
        )

    if record is None:
        logger.warning("[memories.patch] memory_id=%s not_found", memory_id)
        raise HTTPException(status_code=404, detail="Memory not found")

    existing_metadata: Dict[str, Any] = record["metadata"] or {}

    # ---- Step 2: Authorization (AC3) ----------------------------------------
    memory_user_id = existing_metadata.get("user_id")
    if memory_user_id and memory_user_id != user_id:
        logger.warning(
            "[memories.patch] memory_id=%s unauthorized request_user=%s memory_user=%s",
            memory_id,
            user_id,
            memory_user_id,
        )
        raise HTTPException(
            status_code=403,
            detail="Unauthorized: memory belongs to different user",
        )

    # ---- Step 3: Validate patch metadata (AC8) ------------------------------
    if body.metadata is not None:
        _validate_patch_metadata(body.metadata)

    # ---- Step 4: Layer flip validation (AC10/AC11) --------------------------
    current_layer: Optional[str] = existing_metadata.get("layer")
    if body.layer is not None:
        _validate_layer_flip(current_layer, body.layer)

    # ---- Step 5: Content / content_hash (AC6/AC7) ---------------------------
    new_content: Optional[str] = body.content
    content_hash_changed = False
    new_content_hash: Optional[str] = None
    if new_content is not None:
        existing_hash = existing_metadata.get("content_hash")
        new_content_hash = _content_hash(new_content)
        if existing_hash != new_content_hash:
            content_hash_changed = True

    # ---- Step 6: Build merged metadata --------------------------------------
    # Track keys that must be REMOVED from the Chroma record. Chroma's
    # /update endpoint does a shallow merge, so omitting a key from the
    # metadatas payload preserves the stored value — only an explicit
    # `key: null` removes it. update_chroma_record handles the wire-level
    # serialization of this list.
    delete_keys: List[str] = []

    if body.metadata is not None:
        # `__delete__` sentinels: drop from the merged dict AND mark for
        # deletion in Chroma. The shallow-merge alone is insufficient for
        # the Chroma round-trip (the omitted key would persist in storage),
        # but it keeps the dict consumed by the typed-table fan-out clean
        # (where the JSONB || merge ignores absent keys, which is the
        # desired behavior for that path).
        for k, v in body.metadata.items():
            if v == "__delete__":
                delete_keys.append(k)
        merged_caller_metadata = _shallow_merge_metadata(
            {
                k: v
                for k, v in existing_metadata.items()
                if k not in SYSTEM_MANAGED_FIELDS
            },
            body.metadata,
        )
    else:
        merged_caller_metadata = {
            k: v for k, v in existing_metadata.items() if k not in SYSTEM_MANAGED_FIELDS
        }

    # Internal/system-managed fields the router itself recomputes/preserves.
    # `update_chroma_record` writes these via the internal_metadata escape
    # hatch (not subject to the AC20 strip). We START from the existing
    # system-managed values, then mutate per the request.
    internal_metadata: Dict[str, Any] = {
        k: existing_metadata[k] for k in SYSTEM_MANAGED_FIELDS if k in existing_metadata
    }

    # Layer change updates layer in internal metadata.
    if body.layer is not None:
        internal_metadata["layer"] = body.layer

    # Content change updates the content_hash in internal metadata.
    if new_content is not None:
        internal_metadata["content_hash"] = new_content_hash

    # ---- Step 7: TTL handling (AC9) -----------------------------------------
    ttl_supplied = not isinstance(body.ttl_seconds, _Unset)
    if ttl_supplied:
        ttl_value = body.ttl_seconds  # may be None or int
        if ttl_value is None:
            # Explicit null clears the TTL. Popping from internal_metadata
            # alone is insufficient because Chroma /update merges (the old
            # ttl_epoch persists). Stage the key for deletion via the
            # storage-layer delete_keys path so Chroma receives `ttl_epoch:
            # null` and removes the field.
            internal_metadata.pop("ttl_epoch", None)
            if "ttl_epoch" not in delete_keys:
                delete_keys.append("ttl_epoch")
        else:
            # Reject bools explicitly — `bool` is a subclass of `int` in
            # Python, so isinstance(True, int) is True, and a payload like
            # {"ttl_seconds": true} would coerce to a 1-second TTL. (PR #62
            # review #7.)
            if (
                isinstance(ttl_value, bool)
                or not isinstance(ttl_value, int)
                or ttl_value < 1
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "invalid_ttl_seconds",
                        "message": "ttl_seconds must be a positive integer or null",
                    },
                )
            internal_metadata["ttl_epoch"] = int(time.time()) + int(ttl_value)

    # Importance lives in CALLER metadata in Chroma (it's not in
    # SYSTEM_MANAGED_FIELDS — see _build_metadata), so write it there.
    if body.importance is not None:
        merged_caller_metadata["importance"] = body.importance

    # ---- Step 8: Embedding (AC6/AC7/AC14) -----------------------------------
    embedding_regenerated = False
    embedding_regen_duration_ms = 0
    new_embedding: Optional[List[float]] = None
    if new_content is not None and content_hash_changed:
        embed_start = time.perf_counter()
        try:
            generated = generate_embedding(new_content)
        except Exception as exc:
            logger.error(
                "[memories.patch] memory_id=%s embedding_failed error=%s",
                memory_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "embedding_failed",
                    "message": "Failed to generate embedding for new content",
                },
            )
        if not generated:
            logger.error(
                "[memories.patch] memory_id=%s embedding_returned_empty", memory_id
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "embedding_failed",
                    "message": "Embedding service returned empty vector",
                },
            )
        new_embedding = list(generated)
        embedding_regenerated = True
        embedding_regen_duration_ms = int((time.perf_counter() - embed_start) * 1000)
        logger.info(
            "[memories.patch] memory_id=%s embedding_regenerated latency_ms=%d",
            memory_id,
            embedding_regen_duration_ms,
        )

    # ---- Step 9: Apply Chroma update ----------------------------------------
    chroma_updated = False
    try:
        update_chroma_record(
            memory_id,
            document=new_content if new_content is not None else None,
            embedding=new_embedding,  # None when content unchanged
            metadata=merged_caller_metadata,
            internal_metadata=internal_metadata,
            delete_keys=delete_keys or None,
        )
        chroma_updated = True
    except Exception as exc:
        logger.error(
            "[memories.patch] memory_id=%s chroma_update_failed error=%s",
            memory_id,
            exc,
            exc_info=True,
        )
        # Hard failure: Chroma is the source of truth. Do not attempt
        # typed-table fan-out if Chroma failed.
        return PatchMemoryResponse(
            status="error",
            memory_id=memory_id,
            chroma_updated=False,
            typed_table_updated=None,
            embedding_regenerated=embedding_regenerated,
            embedding_regen_duration_ms=embedding_regen_duration_ms,
            warnings=[f"chroma_update_failed: {exc}"],
            message="Failed to update Chroma record",
        )

    # ---- Step 10: Typed-table fan-out (AC12/AC13/AC22) ----------------------
    stored_in_episodic = bool(existing_metadata.get("stored_in_episodic"))
    stored_in_emotional = bool(existing_metadata.get("stored_in_emotional"))
    stored_in_procedural = bool(existing_metadata.get("stored_in_procedural"))
    typed_table_id = existing_metadata.get("typed_table_id")
    has_any_typed = stored_in_episodic or stored_in_emotional or stored_in_procedural

    typed_flags: Optional[PatchMemoryTypedTableUpdated] = None
    if has_any_typed and typed_table_id:
        # Build the typed-table metadata patch (a sub-dict of caller metadata
        # that excludes immortal-by-convention top-level fields). For typed
        # tables we apply the same `body.metadata` shallow merge — `__delete__`
        # sentinels mean key removal in JSONB too. Strip the `__delete__`
        # sentinel out for typed tables (their metadata column doesn't have
        # the same merge semantics; for now we send shallow overrides only and
        # ignore the deletion sentinel — AC12 doesn't mandate JSONB
        # key-deletion).
        typed_metadata_update: Optional[Dict[str, Any]] = None
        if body.metadata is not None:
            typed_metadata_update = {
                k: v for k, v in body.metadata.items() if v != "__delete__"
            }
            if not typed_metadata_update:
                typed_metadata_update = None

        typed_flags = PatchMemoryTypedTableUpdated(
            episodic=False, emotional=False, procedural=False
        )

        # AC22: typed-table UPDATE is ALWAYS attempted when applicable,
        # regardless of content_hash skip. Only embedding write is
        # short-circuited by the hash check above.

        if stored_in_episodic:
            try:
                ok = _update_episodic_row(
                    typed_table_id,
                    user_id,
                    content=new_content,
                    importance=body.importance,
                    metadata_update=typed_metadata_update,
                )
            except Exception as exc:
                logger.warning(
                    "[memories.patch] memory_id=%s episodic_fanout_exception=%s",
                    memory_id,
                    exc,
                )
                ok = False
            typed_flags.episodic = ok
            if not ok:
                warnings.append("episodic_table_update_failed")

        if stored_in_emotional:
            try:
                ok = _update_emotional_row(
                    typed_table_id,
                    user_id,
                    content=new_content,
                    metadata_update=typed_metadata_update,
                )
            except Exception as exc:
                logger.warning(
                    "[memories.patch] memory_id=%s emotional_fanout_exception=%s",
                    memory_id,
                    exc,
                )
                ok = False
            typed_flags.emotional = ok
            if not ok:
                warnings.append("emotional_table_update_failed")

        if stored_in_procedural:
            try:
                ok = _update_procedural_row(
                    typed_table_id,
                    user_id,
                    content=new_content,
                    metadata_update=typed_metadata_update,
                )
            except Exception as exc:
                logger.warning(
                    "[memories.patch] memory_id=%s procedural_fanout_exception=%s",
                    memory_id,
                    exc,
                )
                ok = False
            typed_flags.procedural = ok
            if not ok:
                warnings.append("procedural_table_update_failed")

    total_elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info(
        "[memories.patch] memory_id=%s success total_latency_ms=%d "
        "embedding_regenerated=%s typed_flags=%s warnings=%d",
        memory_id,
        total_elapsed_ms,
        embedding_regenerated,
        typed_flags.model_dump() if typed_flags else None,
        len(warnings),
    )

    return PatchMemoryResponse(
        status="success",
        memory_id=memory_id,
        chroma_updated=chroma_updated,
        typed_table_updated=typed_flags,
        embedding_regenerated=embedding_regenerated,
        embedding_regen_duration_ms=embedding_regen_duration_ms,
        warnings=warnings,
        message="Memory updated successfully"
        if not warnings
        else "Memory updated with warnings",
    )


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
