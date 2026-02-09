from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import hashlib
import json

import logging
from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_embedding_model_name
from src.services.embedding_utils import generate_embedding


COLLECTION_NAME = "memories"
logger = logging.getLogger("agentic_memories.retrieval")


def _embedding_dim_from_model(model: str) -> int:
    name = (model or "").lower()
    if "text-embedding-3-large" in name:
        return 3072
    if "text-embedding-3-small" in name:
        return 1536
    # Default to 3072 if unknown
    return 3072


def _standard_collection_name() -> str:
    # Prefer actual embedding dimension to align with storage collections
    try:
        probe = generate_embedding("dimension-probe") or []
        dim = len(probe)
    except Exception:
        dim = 0
    if dim <= 0:
        model = get_embedding_model_name()
        dim = _embedding_dim_from_model(model)
    return f"{COLLECTION_NAME}_{dim}"


def _get_collection() -> Any:
    client = get_chroma_client()
    if client is None:
        raise RuntimeError("Chroma client not available")

    # Ensure Chroma is healthy before making requests
    if not client.health_check():
        raise RuntimeError("Chroma database is not available or not ready")

    return client.get_collection(_standard_collection_name())  # type: ignore[attr-defined]


def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _keyword_score(query: str, doc: str) -> float:
    q_tokens = set(query.lower().split())
    d_tokens = set(doc.lower().split())
    if not q_tokens or not d_tokens:
        return 0.0
    return len(q_tokens & d_tokens) / len(q_tokens)


def _hybrid_score(semantic: float, keyword: float) -> float:
    return 0.8 * semantic + 0.2 * keyword


def search_memories(
    user_id: str,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    filters = filters or {}
    redis = get_redis_client()
    use_cache = redis is not None and (filters.get("layer") == "short-term")
    logger.info(
        "[retrieve] user_id=%s query_len=%s filters=%s limit=%s offset=%s use_cache=%s",
        user_id,
        len(query or ""),
        list(filters.keys()),
        limit,
        offset,
        use_cache,
    )

    cache_key = None
    if use_cache:
        ns = redis.get(f"mem:ns:{user_id}") or "0"
        cache_key = f"mem:srch:{user_id}:{_hash_query(query)}:v{ns}"
        cached = redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            logger.info(
                "[retrieve.cache.hit] user_id=%s key=%s count=%s",
                user_id,
                cache_key,
                len(data.get("results", [])),
            )
            return data["results"], data.get("total", len(data["results"]))

    try:
        collection = _get_collection()
        logger.info(
            "[retrieve.chroma] collection=%s where_keys=%s",
            getattr(collection, "name", "?"),
            [],
        )
    except RuntimeError as e:
        # Chroma is not available, return empty results
        logger.warning("Chroma not available: %s", e)
        return [], 0

    # Basic metadata filter
    where: Dict[str, Any] = {"user_id": user_id}
    if "layer" in filters and filters["layer"]:
        where["layer"] = filters["layer"]
    if "type" in filters and filters["type"]:
        where["type"] = filters["type"]
    # tags filter (best-effort; stored as JSON string)
    # Note: ChromaDB v2 may not support $contains, so we'll skip tags filtering for now
    # if "tags" in filters and filters["tags"]:
    #     where["tags"] = {"$contains": json.dumps(filters["tags"])[:256]}

    if not query or query.strip() == "":
        # Metadata-only fetch via v2 get
        semantic_results = collection.get(
            where=where, limit=limit + offset, offset=offset
        )  # type: ignore[attr-defined]
        ids = semantic_results.get("ids", [])
        docs = semantic_results.get("documents", [])
        metas = semantic_results.get("metadatas", [])
        scores = [0.0] * len(ids)
    else:
        # Semantic query
        emb = generate_embedding(query) or []
        semantic_results = collection.query(  # type: ignore[attr-defined]
            query_embeddings=[emb], n_results=limit + offset, where=where
        )
        ids = semantic_results.get("ids", [[]])[0]
        docs = semantic_results.get("documents", [[]])[0]
        scores = semantic_results.get("distances", [[]])[0]
        metas = semantic_results.get("metadatas", [[]])[0]

    items: List[Dict[str, Any]] = []
    for i, mem_id in enumerate(ids):
        if i >= len(docs) or i >= len(metas) or i >= len(scores):
            continue
        semantic_sim = 1.0 - float(scores[i]) if scores else 0.0
        k_score = _keyword_score(query, docs[i])
        final = _hybrid_score(semantic_sim, k_score)
        meta = metas[i] or {}
        if not isinstance(meta, dict):
            meta = {"raw": meta}
        if isinstance(meta, dict):
            persona_raw = meta.get("persona_tags")
            if isinstance(persona_raw, str):
                try:
                    meta["persona_tags"] = json.loads(persona_raw)
                except Exception:
                    meta["persona_tags"] = []
            emotional_raw = meta.get("emotional_signature")
            if isinstance(emotional_raw, str):
                try:
                    meta["emotional_signature"] = json.loads(emotional_raw)
                except Exception:
                    meta["emotional_signature"] = {}
            if "importance" in meta:
                try:
                    meta["importance"] = float(meta["importance"])
                except Exception:
                    meta["importance"] = 0.0
        item = {
            "id": mem_id,
            "content": docs[i],
            "score": final,
            "metadata": meta,
            "importance": (meta or {}).get("importance"),
            "persona_tags": (meta or {}).get("persona_tags"),
            "emotional_signature": (meta or {}).get("emotional_signature"),
        }
        items.append(item)

    # Sort by final score and paginate
    persona_filter = filters.get("persona") or filters.get("persona_tags")
    if persona_filter:
        if isinstance(persona_filter, str):
            target = {persona_filter}
        elif isinstance(persona_filter, list):
            target = {str(tag) for tag in persona_filter}
        else:
            target = {str(persona_filter)}
        filtered = []
        for item in items:
            tags = item.get("persona_tags") or []
            if isinstance(tags, list) and any(tag in target for tag in tags):
                filtered.append(item)
        items = filtered

    items.sort(key=lambda x: x["score"], reverse=True)
    total = len(items)
    page = items[offset : offset + limit]
    logger.info(
        "[retrieve.results] user_id=%s returned=%s total=%s", user_id, len(page), total
    )

    # Cache short-term
    if use_cache and cache_key and redis is not None:
        redis.setex(cache_key, 180, json.dumps({"results": page, "total": total}))
        logger.info(
            "[retrieve.cache.store] user_id=%s key=%s count=%s ttl=%s",
            user_id,
            cache_key,
            len(page),
            180,
        )

    return page, total
