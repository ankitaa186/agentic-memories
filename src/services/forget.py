from __future__ import annotations

from typing import Any, Dict, List

import logging
from datetime import datetime, timezone
from src.dependencies.chroma import get_chroma_client
from src.services.embedding_utils import generate_embedding

from src.services.compaction_graph import run_compaction_graph


logger = logging.getLogger("agentic_memories.forget")


def _get_collection() -> Any:
    client = get_chroma_client()
    if client is None:
        raise RuntimeError("Chroma client not available")
    # Best-effort default collection name; rely on v2 client to list/get
    return client.get_collection("memories")  # type: ignore[attr-defined]


def ttl_cleanup() -> int:
    """Delete expired short-term docs based on ttl_epoch metadata.
    Returns number of deletions attempted.
    """
    col = _get_collection()
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    try:
        # Fetch candidates with ttl_epoch <= now (server-side filter if supported)
        res = col.get(where={"ttl_epoch": {"$lte": now_epoch}}, include=["metadatas"])  # type: ignore[attr-defined]
        ids = res.get("ids", [])
        flat_ids = ids if isinstance(ids, list) else []
        if flat_ids:
            col.delete(ids=flat_ids)  # type: ignore[attr-defined]
            logger.info("[forget.ttl] deleted=%s", len(flat_ids))
            return len(flat_ids)
        return 0
    except Exception as exc:
        logger.info("[forget.ttl.error] %s", exc)
        return 0


def simple_deduplicate(
    user_id: str, similarity_threshold: float = 0.88, limit: int = 10000
) -> Dict[str, int]:
    """Naive per-user dedup: compare each doc embedding to others and remove near-duplicates.
    Returns stats dict.
    """
    col = _get_collection()
    try:
        res = col.get(
            where={"user_id": user_id}, limit=limit, include=["documents", "metadatas"]
        )  # type: ignore[attr-defined]
        ids = res.get("ids", [])
        docs = res.get("documents", [])
        _metas = res.get("metadatas", [])
        N = len(ids)
        if N <= 1:
            return {"scanned": N, "removed": 0}
        # Pre-compute embeddings
        embs: List[List[float]] = []
        for doc in docs:
            try:
                embs.append(generate_embedding(doc) or [])
            except Exception:
                embs.append([])
        removed: List[str] = []
        for i in range(N):
            if ids[i] in removed:
                continue
            for j in range(i + 1, N):
                if ids[j] in removed:
                    continue
                # Cosine similarity
                a = embs[i]
                b = embs[j]
                if not a or not b or len(a) != len(b):
                    continue
                # compute dot / (||a||*||b||)
                dot = sum(x * y for x, y in zip(a, b))
                na = sum(x * x for x in a) ** 0.5
                nb = sum(y * y for y in b) ** 0.5
                if na <= 0 or nb <= 0:
                    continue
                cos = dot / (na * nb)
                if cos >= similarity_threshold:
                    removed.append(ids[j])
        if removed:
            col.delete(ids=removed)  # type: ignore[attr-defined]
            logger.info(
                "[forget.dedup] user_id=%s removed=%s of %s", user_id, len(removed), N
            )
        return {"scanned": N, "removed": len(removed)}
    except Exception as exc:
        logger.info("[forget.dedup.error] user_id=%s %s", user_id, exc)
        return {"scanned": 0, "removed": 0}


def run_compaction_for_user(
    user_id: str, skip_reextract: bool = True, skip_consolidate: bool = False
) -> Dict[str, Any]:
    """Run LangGraph-based compaction for a single user and return summary metrics.

    Args:
            user_id: User to compact
            skip_reextract: If True, skip expensive LLM re-extraction (default True)
            skip_consolidate: If True, skip memory consolidation (default False - runs by default)
    """
    try:
        final = run_compaction_graph(
            user_id, skip_reextract=skip_reextract, skip_consolidate=skip_consolidate
        )
        metrics = final.get("metrics", {})
        logger.info("[forget.compact] user_id=%s metrics=%s", user_id, metrics)
        return {"user_id": user_id, **metrics}
    except Exception as exc:
        logger.info("[forget.compact.error] user_id=%s %s", user_id, exc)
        return {"user_id": user_id, "error": str(exc)}
