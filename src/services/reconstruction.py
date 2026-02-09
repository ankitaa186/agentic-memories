"""
Reconstruction Service

Builds coherent narratives by weaving together retrieved memories
and filling gaps using an LLM. Uses hybrid retrieval for context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.services.hybrid_retrieval import (
    HybridRetrievalService,
    RetrievalQuery,
    RetrievalResult,
)
from src.services.extract_utils import _call_llm_json


@dataclass
class Narrative:
    user_id: str
    text: str
    sources: List[Dict[str, Any]]
    summary: Optional[str] = None


class ReconstructionService:
    """Construct narratives and fill gaps across memory types."""

    def __init__(self) -> None:
        self.retrieval = HybridRetrievalService()

    def build_narrative(
        self,
        user_id: str,
        *,
        query: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 100,
        prefetched_memories: Optional[List[Dict[str, Any]]] = None,
        summaries: Optional[List[Dict[str, Any]]] = None,
        persona: Optional[str] = None,
    ) -> Narrative:
        from src.services.tracing import start_span, end_span
        
        span = start_span("narrative_generation", input={
            "user_id": user_id,
            "query": query[:100] if query else None,
            "has_time_range": time_range is not None,
            "limit": limit
        })
        
        try:
            payload_memories: List[Dict[str, Any]] = []
            memory_index: Dict[str, Dict[str, Any]] = {}
            results: List[RetrievalResult] = []

            if prefetched_memories is not None:
                for item in prefetched_memories:
                    if not isinstance(item, dict):
                        continue
                    mem_id = item.get("id")
                    if not mem_id:
                        continue
                    meta = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
                    relevance = float(item.get("score", 0.0) or 0.0)
                    importance = meta.get("importance", item.get("importance", 0.5) or 0.5)
                    try:
                        importance_val = float(importance)
                    except Exception:
                        importance_val = 0.5
                    payload_memories.append(
                        {
                            "id": mem_id,
                            "type": meta.get("type", "semantic"),
                            "content": item.get("content", ""),
                            "relevance": relevance,
                            "recency": float(meta.get("recency", 0.5) if isinstance(meta.get("recency"), (int, float)) else 0.5),
                            "importance": importance_val,
                            "meta": meta,
                        }
                    )
                    memory_index[mem_id] = {
                        "id": mem_id,
                        "type": meta.get("type", "semantic"),
                        "content": item.get("content", ""),
                        "meta": meta,
                    }
            else:
                rq = RetrievalQuery(
                    user_id=user_id,
                    query_text=query,
                    time_range=time_range,
                    limit=max(1, min(limit, 100)),
                )
                results = self.retrieval.retrieve_memories(rq)
                for r in results:
                    meta = r.metadata or {}
                    payload_memories.append(
                        {
                            "id": r.memory_id,
                            "type": r.memory_type,
                            "content": r.content,
                            "relevance": r.relevance_score,
                            "recency": r.recency_score,
                            "importance": r.importance_score,
                            "meta": meta,
                        }
                    )
                    memory_index[r.memory_id] = {
                        "id": r.memory_id,
                        "type": r.memory_type,
                        "content": r.content,
                        "meta": meta,
                    }

            # Shape a compact payload for the LLM
            payload = {
                "user_id": user_id,
                "query": query or "",
                "time_range": [r.isoformat() for r in time_range] if time_range else None,
                "persona": persona,
                "summaries": summaries or [],
                "memories": payload_memories,
            }

            SYSTEM_PROMPT = (
                "You are a narrator that composes a concise, coherent narrative from a user's memories. "
                "Goals: (1) weave relevant events and states into a short story; (2) maintain timeline; "
                "(3) preserve important factual details; (4) avoid speculation beyond the provided memories; "
                "(5) include finance-related highlights if present. Return STRICT JSON: {\n"
                "  \"narrative\": string,\n  \"summary\": string | null,\n  \"source_ids\": string[]\n}"
            )

            resp = _call_llm_json(SYSTEM_PROMPT, payload)
            if not isinstance(resp, dict):
                resp = {"narrative": "", "summary": None, "source_ids": []}

            source_ids = set(resp.get("source_ids") or [])
            sources = [memory_index[sid] for sid in source_ids if sid in memory_index]

            narrative = Narrative(
                user_id=user_id,
                text=str(resp.get("narrative") or "").strip(),
                summary=(resp.get("summary") if isinstance(resp.get("summary"), str) else None),
                sources=sources,
            )
            
            end_span(output={
                "sources_count": len(sources),
                "narrative_length": len(narrative.text),
                "memories_retrieved": len(payload_memories)
            })
            
            return narrative
            
        except Exception as e:
            end_span(output={"error": str(e)}, level="ERROR")
            from src.services.tracing import trace_error
            trace_error(e, metadata={
                "user_id": user_id,
                "context": "narrative_generation"
            })
            raise


