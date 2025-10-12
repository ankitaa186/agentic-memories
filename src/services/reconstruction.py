"""
Reconstruction Service

Builds coherent narratives by weaving together retrieved memories
and filling gaps using an LLM. Uses hybrid retrieval for context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
        limit: int = 25,
    ) -> Narrative:
        from src.services.tracing import start_span, end_span
        
        span = start_span("narrative_generation", input={
            "user_id": user_id,
            "query": query[:100] if query else None,
            "has_time_range": time_range is not None,
            "limit": limit
        })
        
        try:
            rq = RetrievalQuery(
                user_id=user_id,
                query_text=query,
                time_range=time_range,
                limit=max(1, min(limit, 50)),
            )
            results: List[RetrievalResult] = self.retrieval.retrieve_memories(rq)

            # Shape a compact payload for the LLM
            payload = {
                "user_id": user_id,
                "query": query or "",
                "time_range": [r.isoformat() for r in time_range] if time_range else None,
                "memories": [
                    {
                        "id": r.memory_id,
                        "type": r.memory_type,
                        "content": r.content,
                        "relevance": r.relevance_score,
                        "recency": r.recency_score,
                        "importance": r.importance_score,
                        "meta": r.metadata or {},
                    }
                    for r in results
                ],
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
            sources = [
                {
                    "id": r.memory_id,
                    "type": r.memory_type,
                    "content": r.content,
                    "meta": r.metadata or {},
                }
                for r in results
                if r.memory_id in source_ids
            ]

            narrative = Narrative(
                user_id=user_id,
                text=str(resp.get("narrative") or "").strip(),
                summary=(resp.get("summary") if isinstance(resp.get("summary"), str) else None),
                sources=sources,
            )
            
            end_span(output={
                "sources_count": len(sources),
                "narrative_length": len(narrative.text),
                "memories_retrieved": len(results)
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


