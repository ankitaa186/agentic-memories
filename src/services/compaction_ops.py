from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging
from datetime import datetime, timezone

from src.dependencies.chroma import get_chroma_client
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name


logger = logging.getLogger("agentic_memories.compaction_ops")


def _get_collection() -> Any:
	client = get_chroma_client()
	if client is None:
		raise RuntimeError("Chroma client not available")
	# Use standard collection name with proper dimension suffix
	return client.get_collection(_standard_collection_name())  # type: ignore[attr-defined]


def ttl_cleanup() -> int:
	"""Delete expired short-term docs based on ttl_epoch metadata.
	Returns number of deletions attempted.
	"""
	col = _get_collection()
	now_epoch = int(datetime.now(timezone.utc).timestamp())
	try:
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


def simple_deduplicate(user_id: str, similarity_threshold: float = 0.85, limit: int = 10000) -> Dict[str, int]:
	"""Naive per-user dedup: compare embeddings and remove near-duplicates.

	Threshold lowered from 0.90 to 0.80 (Story 4.3) to catch semantic duplicates
	that are worded differently (e.g., "User likes Buffett" vs "User admires Buffett").

	Returns stats dict with 'scanned' and 'removed' counts.
	"""
	col = _get_collection()
	try:
		res = col.get(where={"user_id": user_id}, limit=limit, include=["documents", "metadatas"])  # type: ignore[attr-defined]
		ids = res.get("ids", [])
		docs = res.get("documents", [])
		N = len(ids)
		if N <= 1:
			return {"scanned": N, "removed": 0}
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
				a = embs[i]
				b = embs[j]
				if not a or not b or len(a) != len(b):
					continue
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
			logger.info("[forget.dedup] user_id=%s removed=%s of %s", user_id, len(removed), N)
		return {"scanned": N, "removed": len(removed)}
	except Exception as exc:
		logger.info("[forget.dedup.error] user_id=%s %s", user_id, exc)
		return {"scanned": 0, "removed": 0}



