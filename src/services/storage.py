from __future__ import annotations

from typing import Any, Dict, List, Optional

import hashlib
import time
import uuid
import json
from datetime import datetime, timezone

import logging
from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.models import Memory
from src.services._constants import SYSTEM_MANAGED_FIELDS
from src.services.retrieval import _standard_collection_name


COLLECTION_NAME = "memories"
logger = logging.getLogger("agentic_memories.storage")

# NOTE: Keep the SYSTEM_MANAGED_FIELDS list in `src/services/_constants.py` in
# sync with the keys written by `_build_metadata` below. AM-X.1's PATCH router
# (router-level guard, AC8) and `update_chroma_record` (storage-level guard,
# AC20) both protect these from caller-supplied overrides. AM-X.2's
# `metadata_filter` validator (AC4) also rejects them as filter keys.


def init_chroma_collection(name: str = COLLECTION_NAME) -> Any:
    client = get_chroma_client()
    if client is None:
        raise RuntimeError("Chroma client not available")
    # V2 client exposes get_or_create_collection; avoid legacy create_collection
    return client.get_or_create_collection(name)  # type: ignore[attr-defined]


def _ttl_epoch_from_ttl(ttl_seconds: Optional[int]) -> Optional[int]:
    if ttl_seconds is None:
        return None
    return int(time.time()) + int(ttl_seconds)


def _build_metadata(memory: Memory) -> Dict[str, Any]:
    content_hash = hashlib.sha256(memory.content.strip().lower().encode()).hexdigest()
    meta: Dict[str, Any] = {
        "user_id": memory.user_id,
        "layer": memory.layer,
        "type": memory.type,
        "timestamp": memory.timestamp.isoformat(),
        "confidence": memory.confidence,
        "relevance_score": memory.relevance_score,
        "usage_count": memory.usage_count,
        "importance": memory.importance,
        "content_hash": content_hash,
        "persona_tags": json.dumps(memory.persona_tags or []),
        "tags": json.dumps(memory.metadata.get("tags", [])),  # Serialize list to string
    }
    if memory.emotional_signature:
        meta["emotional_signature"] = json.dumps(memory.emotional_signature)
    if memory.ttl is not None:
        meta["ttl_epoch"] = _ttl_epoch_from_ttl(memory.ttl)
    # Pass-through all metadata fields not already in meta
    for key, value in memory.metadata.items():
        if key in meta or key == "tags":  # tags already handled above
            continue
        if value is None:
            continue
        if isinstance(value, (list, dict)):
            meta[key] = json.dumps(value)
        elif isinstance(value, (str, int, float, bool)):
            meta[key] = value
        else:
            meta[key] = str(value)  # Coerce unsupported types for ChromaDB
    return meta


def upsert_memories(user_id: str, memories: List[Memory]) -> List[str]:
    if not memories:
        logger.info("[storage.upsert] user_id=%s count=%s (noop)", user_id, 0)
        return []
    for m in memories:
        if m.user_id != user_id:
            raise ValueError("user_id mismatch in memories")

    ids: List[str] = []
    documents: List[str] = []
    embeddings: List[List[float]] = []
    metadatas: List[Dict[str, Any]] = []

    for m in memories:
        mem_id = m.id or f"mem_{uuid.uuid4().hex[:12]}"
        ids.append(mem_id)
        documents.append(m.content)

        # Ensure embedding is properly handled
        embedding = m.embedding or []
        if not embedding:
            # Generate embedding if missing
            try:
                from src.services.embedding_utils import generate_embedding

                embedding = generate_embedding(m.content) or []
            except Exception as exc:
                logger.warning(
                    "[storage.upsert.embedding_error] user_id=%s id=%s error=%s",
                    user_id,
                    mem_id,
                    exc,
                )
                embedding = []

        embeddings.append(embedding)
        metadatas.append(_build_metadata(m))
    logger.info("[storage.upsert.prepare] user_id=%s ids=%s", user_id, len(ids))

    # Use standard collection naming to ensure consistency with retrieval
    collection_name = _standard_collection_name()
    collection = init_chroma_collection(collection_name)

    # Chroma upsert
    collection.upsert(
        ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
    )  # type: ignore[attr-defined]
    logger.info(
        "[storage.upsert.done] user_id=%s count=%s collection=%s",
        user_id,
        len(ids),
        collection_name,
    )

    # Record user activity for compaction scheduler
    try:
        redis = get_redis_client()
        if redis is not None:
            day_key = datetime.now(timezone.utc).strftime("%Y%m%d")
            redis.sadd(f"recent_users:{day_key}", user_id)
            redis.sadd("all_users", user_id)
    except Exception:
        pass

    return ids


def increment_usage_count(ids: List[str]) -> None:
    # Optionally: implement as metadata updates in Chroma if supported by client, else no-op placeholder
    try:
        # We don't know the dimension here; skip increment to avoid collection mismatch complexities
        return
    except Exception:
        return


def get_chroma_record(memory_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single Chroma record by id, returning ``{"id", "document",
    "metadata"}`` or ``None`` if the record does not exist.

    Used by AM-X.1 PATCH to read the current state before applying a partial
    update (so the caller can compute content_hash, detect typed-table flags,
    and verify ownership).
    """
    collection_name = _standard_collection_name()
    collection = init_chroma_collection(collection_name)
    try:
        result = collection.get(ids=[memory_id], include=["documents", "metadatas"])  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error(
            "[storage.get_chroma_record] memory_id=%s error=%s", memory_id, exc
        )
        raise

    ids = result.get("ids", []) or []
    if not ids or memory_id not in ids:
        return None
    idx = ids.index(memory_id)
    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []
    document = documents[idx] if idx < len(documents) else None
    metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
    return {"id": memory_id, "document": document, "metadata": dict(metadata)}


def update_chroma_record(
    memory_id: str,
    *,
    document: Optional[str] = None,
    embedding: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    internal_metadata: Optional[Dict[str, Any]] = None,
    delete_keys: Optional[List[str]] = None,
) -> None:
    """Apply a partial update to a Chroma record using ``collection.update``.

    Preserves ``memory_id`` continuity (does NOT delete-and-recreate). Only the
    fields that are not ``None`` are passed through to Chroma.

    AC20 defense-in-depth: any keys in ``metadata`` that overlap with
    ``SYSTEM_MANAGED_FIELDS`` are stripped before writing. ``internal_metadata``
    is the trusted/internal-callers escape hatch (e.g., the router writes
    server-computed ``ttl_epoch``, ``layer``, ``content_hash`` here) and is
    NOT subject to the strip.

    The router-level guard in PATCH already rejects such inputs with a 422,
    but this ensures any future internal caller of this helper cannot bypass
    the protection by accident.

    Key removal semantics: Chroma's ``/update`` endpoint does a SHALLOW MERGE,
    not a replace — sending ``metadatas`` without a key leaves the stored
    value intact. To DELETE a metadata key in Chroma, the wire payload must
    include ``"key": null``. Pass the keys to delete via ``delete_keys``;
    they are sent as ``None`` values in the metadata payload (which the
    Chroma server interprets as "remove this key"). Verified live against
    Chroma 1.x on 2026-05-08 — both ``foo: null`` and the merge-without-key
    behavior were confirmed via direct ``/update`` curl probes.

    Args:
        memory_id: The Chroma id to update (must already exist).
        document: New document content, or ``None`` to leave unchanged.
        embedding: New embedding vector, or ``None`` to leave unchanged.
        metadata: Caller-supplied metadata (already shallow-merged with
            existing). System-managed keys are stripped before writing.
        internal_metadata: Trusted, server-computed metadata (e.g.,
            ``ttl_epoch``, ``content_hash``, ``layer``). Merged with the
            caller's ``metadata`` after the strip; takes precedence on key
            collisions.
        delete_keys: List of metadata keys to REMOVE from the Chroma record.
            Sent as ``None`` values to Chroma's ``/update`` endpoint, which
            interprets ``key: null`` as deletion. Trusted path — system-managed
            keys are NOT stripped here (the PATCH router uses this to clear
            ``ttl_epoch`` when ``ttl_seconds: null`` is supplied).
    """
    collection_name = _standard_collection_name()
    collection = init_chroma_collection(collection_name)

    kwargs: Dict[str, Any] = {"ids": [memory_id]}
    if document is not None:
        kwargs["documents"] = [document]
    if embedding is not None:
        kwargs["embeddings"] = [embedding]

    final_metadata: Optional[Dict[str, Any]] = None
    if metadata is not None or internal_metadata is not None or delete_keys:
        cleaned: Dict[str, Any] = {}
        if metadata is not None:
            cleaned = {
                k: v for k, v in metadata.items() if k not in SYSTEM_MANAGED_FIELDS
            }
        if internal_metadata is not None:
            cleaned.update(internal_metadata)
        if delete_keys:
            # Explicit None signals key deletion to Chroma's /update endpoint.
            # Applied LAST so it overrides any value the caller may have set
            # for the same key in metadata or internal_metadata.
            for k in delete_keys:
                cleaned[k] = None
        final_metadata = cleaned
        kwargs["metadatas"] = [final_metadata]

    collection.update(**kwargs)  # type: ignore[attr-defined]
    logger.info(
        "[storage.update_chroma_record] memory_id=%s document=%s embedding=%s metadata_keys=%s delete_keys=%s",
        memory_id,
        document is not None,
        embedding is not None,
        sorted(final_metadata.keys()) if final_metadata is not None else None,
        sorted(delete_keys) if delete_keys else None,
    )


# =============================================================================
# Typed-table UPDATE helpers (AM-X.1 PATCH fan-out)
#
# These helpers are partial-update analogs of the INSERT helpers in
# `src/routers/memories.py:_store_*` and the DELETE helpers `_delete_from_*`.
# We need NEW helpers because:
#   - `_store_*` requires the full DirectMemoryRequest payload (INSERT is total).
#   - `_rollback_typed_tables` only does DELETE.
# Supported PATCH fields per typed table (per AC12):
#   - episodic / procedural: content, importance (-> importance_score), metadata
#   - emotional: content (-> context), metadata
#     (importance is not a column on emotional_memories.)
# Anything else triggers an AC12 422 in the router; these helpers ignore unknown
# fields rather than fail (defense-in-depth: they emit only valid SET clauses).
#
# Best-effort semantics (AC13): each helper returns ``True`` on success,
# ``False`` on any failure (logged, swallowed). The router exposes per-table
# flags in the response, mirroring the DELETE fan-out pattern.
# =============================================================================


def _update_episodic_row(
    typed_table_id: str,
    user_id: str,
    *,
    content: Optional[str] = None,
    importance: Optional[float] = None,
    metadata_update: Optional[Dict[str, Any]] = None,
) -> bool:
    """Apply a partial update to an episodic_memories row.

    Returns True on success (including no-op when no fields supplied). Returns
    False on database error or when the row does not exist.
    """
    set_clauses: List[str] = []
    params: List[Any] = []
    if content is not None:
        set_clauses.append("content = %s")
        params.append(content)
    if importance is not None:
        set_clauses.append("importance_score = %s")
        params.append(importance)
    if metadata_update is not None:
        # JSONB shallow-merge using ||. NULL || x = NULL in Postgres, so coalesce.
        set_clauses.append("metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb")
        params.append(json.dumps(metadata_update))

    if not set_clauses:
        return True  # no-op

    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[storage._update_episodic_row] memory_id=%s connection_unavailable",
            typed_table_id,
        )
        return False
    try:
        sql = f"UPDATE episodic_memories SET {', '.join(set_clauses)} WHERE id = %s AND user_id = %s"
        params.append(typed_table_id)
        params.append(user_id)
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            updated = cur.rowcount
        conn.commit()
        if updated == 0:
            logger.warning(
                "[storage._update_episodic_row] memory_id=%s user_id=%s no_row_matched",
                typed_table_id,
                user_id,
            )
            return False
        logger.info(
            "[storage._update_episodic_row] memory_id=%s user_id=%s rows_updated=%d",
            typed_table_id,
            user_id,
            updated,
        )
        return True
    except Exception as exc:
        logger.error(
            "[storage._update_episodic_row] memory_id=%s error=%s",
            typed_table_id,
            exc,
            exc_info=True,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        release_timescale_conn(conn)


def _update_emotional_row(
    typed_table_id: str,
    user_id: str,
    *,
    content: Optional[str] = None,
    metadata_update: Optional[Dict[str, Any]] = None,
) -> bool:
    """Apply a partial update to an emotional_memories row.

    Note: emotional_memories has no ``importance_score`` column. The router
    does NOT 422 on importance for emotional fan-out; instead, importance still
    lands in the Chroma metadata (the source of truth) and is silently skipped
    on the typed-table propagation. Caller-visible: ``typed_table_updated.emotional``
    reflects whether content/metadata changes (if any) propagated; importance
    alone with no other fields produces a no-op typed-table call.
    """
    set_clauses: List[str] = []
    params: List[Any] = []
    if content is not None:
        # On emotional_memories, "context" stores the content per _store_emotional.
        set_clauses.append("context = %s")
        params.append(content)
    if metadata_update is not None:
        set_clauses.append("metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb")
        params.append(json.dumps(metadata_update))

    if not set_clauses:
        return True

    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[storage._update_emotional_row] memory_id=%s connection_unavailable",
            typed_table_id,
        )
        return False
    try:
        sql = f"UPDATE emotional_memories SET {', '.join(set_clauses)} WHERE id = %s AND user_id = %s"
        params.append(typed_table_id)
        params.append(user_id)
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            updated = cur.rowcount
        conn.commit()
        if updated == 0:
            logger.warning(
                "[storage._update_emotional_row] memory_id=%s user_id=%s no_row_matched",
                typed_table_id,
                user_id,
            )
            return False
        logger.info(
            "[storage._update_emotional_row] memory_id=%s user_id=%s rows_updated=%d",
            typed_table_id,
            user_id,
            updated,
        )
        return True
    except Exception as exc:
        logger.error(
            "[storage._update_emotional_row] memory_id=%s error=%s",
            typed_table_id,
            exc,
            exc_info=True,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        release_timescale_conn(conn)


def _update_procedural_row(
    typed_table_id: str,
    user_id: str,
    *,
    content: Optional[str] = None,
    metadata_update: Optional[Dict[str, Any]] = None,
) -> bool:
    """Apply a partial update to a procedural_memories row.

    procedural_memories.context stores the content per _store_procedural; we
    follow the same convention here. procedural_memories has NO
    ``importance_score`` column (see migrations/postgres/001_procedural_memories.up.sql).
    The router does NOT 422 on importance for procedural fan-out; importance lands
    in the Chroma metadata (the source of truth) and is silently skipped on the
    typed-table propagation, mirroring the emotional behavior.
    """
    set_clauses: List[str] = []
    params: List[Any] = []
    if content is not None:
        set_clauses.append("context = %s")
        params.append(content)
    if metadata_update is not None:
        set_clauses.append("metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb")
        params.append(json.dumps(metadata_update))

    if not set_clauses:
        return True

    conn = get_timescale_conn()
    if not conn:
        logger.error(
            "[storage._update_procedural_row] memory_id=%s connection_unavailable",
            typed_table_id,
        )
        return False
    try:
        sql = f"UPDATE procedural_memories SET {', '.join(set_clauses)} WHERE id = %s AND user_id = %s"
        params.append(typed_table_id)
        params.append(user_id)
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            updated = cur.rowcount
        conn.commit()
        if updated == 0:
            logger.warning(
                "[storage._update_procedural_row] memory_id=%s user_id=%s no_row_matched",
                typed_table_id,
                user_id,
            )
            return False
        logger.info(
            "[storage._update_procedural_row] memory_id=%s user_id=%s rows_updated=%d",
            typed_table_id,
            user_id,
            updated,
        )
        return True
    except Exception as exc:
        logger.error(
            "[storage._update_procedural_row] memory_id=%s error=%s",
            typed_table_id,
            exc,
            exc_info=True,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        release_timescale_conn(conn)
