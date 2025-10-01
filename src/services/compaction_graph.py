from __future__ import annotations

from typing import Any, Dict, List

import logging
import json
import time as _time

from langgraph.graph import StateGraph, END  # type: ignore

from src.services.compaction_ops import ttl_cleanup, simple_deduplicate
from src.services.compaction_ops import _get_collection  # type: ignore
from src.services.embedding_utils import generate_embedding
from src.services.storage import upsert_memories
from src.models import Memory
from src.services.extraction import extract_from_transcript
from src.schemas import TranscriptRequest, Message


logger = logging.getLogger("agentic_memories.compaction_graph")


def _fetch_user_memories(user_id: str, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
	"""Fetch a batch of user memories with ids, content, and metadata.
	Best-effort using v2 collection get.
	"""
	col = _get_collection()
	res = col.get(where={"user_id": user_id}, limit=limit, offset=offset, include=["documents", "metadatas"])  # type: ignore[attr-defined]
	ids = res.get("ids", [])
	docs = res.get("documents", [])
	metas = res.get("metadatas", [])
	items: List[Dict[str, Any]] = []
	for i, mid in enumerate(ids or []):
		if i >= len(docs) or i >= len(metas):
			continue
		items.append({"id": mid, "content": docs[i], "metadata": metas[i]})
	return items


def _reextract_memories(user_id: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-run the store/extraction pipeline per memory content to reclassify and normalize.
    Returns dict with keys: new_memories (List[Memory]), delete_ids (List[str]).
    """
    new_mems: List[Memory] = []
    delete_ids: List[str] = []
    for c in candidates:
        mid = c.get("id")
        content = c.get("content", "")
        if not content:
            continue
        req = TranscriptRequest(user_id=user_id, history=[Message(role="user", content=content)])
        try:
            result = extract_from_transcript(req)
            if result.memories:
                new_mems.extend(result.memories)
                delete_ids.append(mid)
        except Exception as exc:
            logger.info("[graph.reextract.error] user_id=%s id=%s %s", user_id, mid, exc)
            continue
    return {"new_memories": new_mems, "delete_ids": delete_ids}


def build_compaction_graph() -> StateGraph:
	graph = StateGraph(dict)

	def node_init(state: Dict[str, Any]) -> Dict[str, Any]:
		# Ensure required keys
		state.setdefault("metrics", {})
		state["t0"] = _time.perf_counter()
		logger.info("[graph.init] user_id=%s limit=%s", state.get("user_id"), state.get("limit"))
		return state

	def node_ttl(state: Dict[str, Any]) -> Dict[str, Any]:
		# Global TTL cleanup (idempotent)
		_t = _time.perf_counter()
		deleted = ttl_cleanup()
		state["metrics"]["ttl_deleted"] = state["metrics"].get("ttl_deleted", 0) + int(deleted or 0)
		logger.info("[graph.ttl] deleted=%s latency_ms=%s", deleted, int((_time.perf_counter() - _t) * 1000))
		return state

	def node_dedup(state: Dict[str, Any]) -> Dict[str, Any]:
		user_id = state.get("user_id")
		lim = int(state.get("limit") or 500)
		_t = _time.perf_counter()
		stats = simple_deduplicate(str(user_id), limit=lim)
		state["metrics"].update({
			"dedup_scanned": stats.get("scanned", 0),
			"dedup_removed": stats.get("removed", 0),
		})
		logger.info("[graph.dedup] user_id=%s stats=%s latency_ms=%s", user_id, stats, int((_time.perf_counter() - _t) * 1000))
		return state

	def node_load(state: Dict[str, Any]) -> Dict[str, Any]:
		user_id = str(state.get("user_id"))
		limit = int(state.get("limit") or 200)
		_t = _time.perf_counter()
		cands = _fetch_user_memories(user_id, limit=limit)
		state["candidates"] = cands
		logger.info("[graph.load] user_id=%s loaded=%s latency_ms=%s", user_id, len(cands), int((_time.perf_counter() - _t) * 1000))
		return state

	def node_reextract(state: Dict[str, Any]) -> Dict[str, Any]:
		user_id = str(state.get("user_id"))
		_t = _time.perf_counter()
		out = _reextract_memories(user_id, state.get("candidates", []))
		state["reextract"] = out
		logger.info(
			"[graph.reextract] user_id=%s new=%s delete=%s latency_ms=%s",
			user_id,
			len(out.get("new_memories", [])),
			len(out.get("delete_ids", [])),
			int((_time.perf_counter() - _t) * 1000),
		)
		return state

	def node_apply(state: Dict[str, Any]) -> Dict[str, Any]:
		user_id = str(state.get("user_id"))
		_t = _time.perf_counter()
		out = state.get("reextract", {}) or {}
		new_mems: List[Memory] = list(out.get("new_memories", []))
		delete_ids: List[str] = list(out.get("delete_ids", []))
		if new_mems:
			# Upsert in chunks to avoid payload limits
			chunk = 500
			for i in range(0, len(new_mems), chunk):
				upsert_memories(user_id, new_mems[i:i+chunk])
		if delete_ids:
			try:
				col = _get_collection()
				col.delete(ids=list(set(delete_ids)))  # type: ignore[attr-defined]
			except Exception as exc:
				logger.info("[graph.apply.delete.error] %s", exc)
		state["metrics"]["applied_upserts"] = len(new_mems)
		state["metrics"]["applied_deletes"] = len(set(delete_ids))
		logger.info(
			"[graph.apply] user_id=%s upserts=%s deletes=%s latency_ms=%s",
			user_id,
			len(new_mems),
			len(set(delete_ids)),
			int((_time.perf_counter() - _t) * 1000),
		)
		return state

	graph.add_node("init", node_init)
	graph.add_node("ttl", node_ttl)
	graph.add_node("dedup", node_dedup)
	graph.add_node("load", node_load)
	graph.add_node("reextract", node_reextract)
	graph.add_node("apply", node_apply)
	graph.set_entry_point("init")
	graph.add_edge("init", "ttl")
	graph.add_edge("ttl", "dedup")
	graph.add_edge("dedup", "load")
	graph.add_edge("load", "reextract")
	graph.add_edge("reextract", "apply")
	graph.add_edge("apply", END)
	return graph


def run_compaction_graph(user_id: str, *, dry_run: bool = False, limit: int = 10000) -> Dict[str, Any]:
	"""Run the minimal compaction graph for a single user and return the final state."""
	graph = build_compaction_graph()
	_t0 = _time.perf_counter()
	initial = {"user_id": user_id, "dry_run": dry_run, "limit": limit}
	final: Dict[str, Any] = graph.compile().invoke(initial)  # type: ignore
	final.setdefault("metrics", {})
	final["metrics"]["duration_ms"] = int((_time.perf_counter() - _t0) * 1000)
	logger.info("[graph.done] user_id=%s metrics=%s", user_id, final.get("metrics"))
	return final


