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
    skipped_count = 0
    error_count = 0
    
    for c in candidates:
        mid = c.get("id")
        content = c.get("content", "")
        metadata = c.get("metadata", {})
        
        # Validate candidate structure
        if not mid:
            logger.warning("[graph.reextract.skip] user_id=%s reason=missing_id", user_id)
            skipped_count += 1
            continue
            
        if not content or not content.strip():
            logger.warning("[graph.reextract.skip] user_id=%s id=%s reason=empty_content", user_id, mid)
            skipped_count += 1
            continue
        
        # Create extraction request
        req = TranscriptRequest(user_id=user_id, history=[Message(role="user", content=content)])
        
        try:
            result = extract_from_transcript(req)
            if result.memories and len(result.memories) > 0:
                # Validate that new memories have proper structure
                valid_memories = []
                for mem in result.memories:
                    if mem.content and mem.content.strip():
                        valid_memories.append(mem)
                    else:
                        logger.warning("[graph.reextract.skip_memory] user_id=%s id=%s reason=empty_extracted_content", user_id, mid)
                
                if valid_memories:
                    new_mems.extend(valid_memories)
                    delete_ids.append(mid)
                    logger.debug("[graph.reextract.success] user_id=%s id=%s extracted=%s", user_id, mid, len(valid_memories))
                else:
                    logger.warning("[graph.reextract.skip] user_id=%s id=%s reason=no_valid_memories", user_id, mid)
                    skipped_count += 1
            else:
                logger.warning("[graph.reextract.skip] user_id=%s id=%s reason=no_memories_extracted", user_id, mid)
                skipped_count += 1
                
        except Exception as exc:
            logger.error("[graph.reextract.error] user_id=%s id=%s error=%s", user_id, mid, exc)
            error_count += 1
            continue
    
    logger.info("[graph.reextract.summary] user_id=%s processed=%s new_memories=%s delete_ids=%s skipped=%s errors=%s", 
                user_id, len(candidates), len(new_mems), len(delete_ids), skipped_count, error_count)
    
    return {"new_memories": new_mems, "delete_ids": delete_ids}


def build_compaction_graph() -> StateGraph:
	graph = StateGraph(dict)

	def node_init(state: Dict[str, Any]) -> Dict[str, Any]:
		from src.services.tracing import start_span, end_span
		
		span = start_span("compaction_init", input={
			"user_id": state.get("user_id"),
			"limit": state.get("limit"),
			"dry_run": state.get("dry_run")
		})
		
		# Ensure required keys
		state.setdefault("metrics", {})
		state["t0"] = _time.perf_counter()
		logger.info("[graph.init] user_id=%s limit=%s", state.get("user_id"), state.get("limit"))
		
		end_span(output={"initialized": True})
		return state

	def node_ttl(state: Dict[str, Any]) -> Dict[str, Any]:
		from src.services.tracing import start_span, end_span
		
		span = start_span("compaction_ttl_cleanup", input={})
		
		# Global TTL cleanup (idempotent)
		_t = _time.perf_counter()
		deleted = ttl_cleanup()
		state["metrics"]["ttl_deleted"] = state["metrics"].get("ttl_deleted", 0) + int(deleted or 0)
		latency_ms = int((_time.perf_counter() - _t) * 1000)
		logger.info("[graph.ttl] deleted=%s latency_ms=%s", deleted, latency_ms)
		
		end_span(output={"deleted": deleted, "latency_ms": latency_ms})
		return state

	def node_dedup(state: Dict[str, Any]) -> Dict[str, Any]:
		from src.services.tracing import start_span, end_span
		
		user_id = state.get("user_id")
		lim = int(state.get("limit") or 500)
		
		span = start_span("compaction_deduplication", input={
			"user_id": user_id,
			"limit": lim
		})
		
		_t = _time.perf_counter()
		stats = simple_deduplicate(str(user_id), limit=lim)
		state["metrics"].update({
			"dedup_scanned": stats.get("scanned", 0),
			"dedup_removed": stats.get("removed", 0),
		})
		latency_ms = int((_time.perf_counter() - _t) * 1000)
		logger.info("[graph.dedup] user_id=%s stats=%s latency_ms=%s", user_id, stats, latency_ms)
		
		end_span(output={
			"scanned": stats.get("scanned", 0),
			"removed": stats.get("removed", 0),
			"latency_ms": latency_ms
		})
		return state

	def node_load(state: Dict[str, Any]) -> Dict[str, Any]:
		from src.services.tracing import start_span, end_span
		
		user_id = str(state.get("user_id"))
		limit = int(state.get("limit") or 200)
		
		span = start_span("compaction_load_memories", input={
			"user_id": user_id,
			"limit": limit
		})
		
		_t = _time.perf_counter()
		cands = _fetch_user_memories(user_id, limit=limit)
		state["candidates"] = cands
		
		# Safety check: if no candidates, skip re-extraction
		if not cands:
			logger.info("[graph.load.empty] user_id=%s no_candidates_found", user_id)
			state["skip_reextract"] = True
		else:
			state["skip_reextract"] = False
		
		latency_ms = int((_time.perf_counter() - _t) * 1000)
		logger.info("[graph.load] user_id=%s loaded=%s latency_ms=%s", user_id, len(cands), latency_ms)
		
		end_span(output={
			"loaded_count": len(cands),
			"skip_reextract": state["skip_reextract"],
			"latency_ms": latency_ms
		})
		return state

	def node_reextract(state: Dict[str, Any]) -> Dict[str, Any]:
		from src.services.tracing import start_span, end_span
		
		user_id = str(state.get("user_id"))
		
		span = start_span("compaction_reextract", input={
			"user_id": user_id,
			"candidates_count": len(state.get("candidates", [])),
			"skip": state.get("skip_reextract", False)
		})
		
		_t = _time.perf_counter()
		
		# Skip if no candidates were loaded
		if state.get("skip_reextract", False):
			logger.info("[graph.reextract.skip] user_id=%s no_candidates", user_id)
			state["reextract"] = {"new_memories": [], "delete_ids": []}
			end_span(output={"skipped": True})
			return state
		
		out = _reextract_memories(user_id, state.get("candidates", []))
		state["reextract"] = out
		latency_ms = int((_time.perf_counter() - _t) * 1000)
		logger.info(
			"[graph.reextract] user_id=%s new=%s delete=%s latency_ms=%s",
			user_id,
			len(out.get("new_memories", [])),
			len(out.get("delete_ids", [])),
			latency_ms,
		)
		
		end_span(output={
			"new_memories_count": len(out.get("new_memories", [])),
			"delete_ids_count": len(out.get("delete_ids", [])),
			"latency_ms": latency_ms
		})
		return state

	def node_apply(state: Dict[str, Any]) -> Dict[str, Any]:
		from src.services.tracing import start_span, end_span
		
		user_id = str(state.get("user_id"))
		dry_run = state.get("dry_run", False)
		out = state.get("reextract", {}) or {}
		new_mems: List[Memory] = list(out.get("new_memories", []))
		delete_ids: List[str] = list(set(out.get("delete_ids", [])))
		
		span = start_span("compaction_apply", input={
			"user_id": user_id,
			"dry_run": dry_run,
			"new_memories_count": len(new_mems),
			"delete_ids_count": len(delete_ids)
		})
		
		_t = _time.perf_counter()
		
		upserted_count = 0
		deleted_count = 0
		
		if dry_run:
			logger.info("[graph.apply.dry_run] user_id=%s would_upsert=%s would_delete=%s", 
					   user_id, len(new_mems), len(delete_ids))
		else:
			# Transaction safety: Only proceed if we have both new memories and delete IDs
			# OR if we only have one type of operation
			if new_mems and delete_ids:
				# Both operations: try upsert first, then delete only if upsert succeeds
				try:
					# Upsert in chunks to avoid payload limits
					chunk = 500
					for i in range(0, len(new_mems), chunk):
						upsert_memories(user_id, new_mems[i:i+chunk])
					upserted_count = len(new_mems)
					
					# Only delete after successful upsert
					col = _get_collection()
					col.delete(ids=delete_ids)  # type: ignore[attr-defined]
					deleted_count = len(delete_ids)
					logger.info("[graph.apply.success] user_id=%s upserted=%s deleted=%s", 
							   user_id, upserted_count, deleted_count)
				except Exception as exc:
					logger.error("[graph.apply.error] user_id=%s upserted=%s failed=%s error=%s", 
								user_id, upserted_count, exc)
					# Don't delete if upsert failed
			elif new_mems:
				# Only upsert
				try:
					chunk = 500
					for i in range(0, len(new_mems), chunk):
						upsert_memories(user_id, new_mems[i:i+chunk])
					upserted_count = len(new_mems)
				except Exception as exc:
					logger.error("[graph.apply.upsert.error] user_id=%s error=%s", user_id, exc)
			elif delete_ids:
				# Only delete
				try:
					col = _get_collection()
					col.delete(ids=delete_ids)  # type: ignore[attr-defined]
					deleted_count = len(delete_ids)
				except Exception as exc:
					logger.error("[graph.apply.delete.error] user_id=%s error=%s", user_id, exc)
		
		state["metrics"]["applied_upserts"] = upserted_count
		state["metrics"]["applied_deletes"] = deleted_count
		latency_ms = int((_time.perf_counter() - _t) * 1000)
		logger.info(
			"[graph.apply] user_id=%s upserts=%s deletes=%s latency_ms=%s dry_run=%s",
			user_id,
			upserted_count,
			deleted_count,
			latency_ms,
			dry_run,
		)
		
		end_span(output={
			"upserted": upserted_count,
			"deleted": deleted_count,
			"dry_run": dry_run,
			"latency_ms": latency_ms
		})
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
	from src.services.tracing import start_trace
	
	# Start a trace for this compaction job
	trace = start_trace(
		name="compaction_job",
		user_id=user_id,
		metadata={
			"dry_run": dry_run,
			"limit": limit,
			"trigger": "manual"
		}
	)
	
	graph = build_compaction_graph()
	_t0 = _time.perf_counter()
	initial = {"user_id": user_id, "dry_run": dry_run, "limit": limit}
	final: Dict[str, Any] = graph.compile().invoke(initial)  # type: ignore
	final.setdefault("metrics", {})
	final["metrics"]["duration_ms"] = int((_time.perf_counter() - _t0) * 1000)
	logger.info("[graph.done] user_id=%s metrics=%s", user_id, final.get("metrics"))
	
	# Update trace with final metrics
	if trace:
		try:
			trace.update(output=final.get("metrics", {}))
		except Exception:
			pass
	
	return final


