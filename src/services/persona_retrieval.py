from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional

from src.services.hybrid_retrieval import HybridRetrievalService, RetrievalQuery
from src.services.retrieval import search_memories
from src.services.persona_state import PersonaState, PersonaStateStore
from src.services.summary_manager import SummaryManager


PERSONA_WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    "identity": {"semantic": 0.5, "temporal": 0.2, "importance": 0.2, "emotional": 0.1},
    "relationships": {"semantic": 0.3, "temporal": 0.2, "importance": 0.2, "emotional": 0.3},
    "health": {"semantic": 0.25, "temporal": 0.25, "importance": 0.25, "emotional": 0.25},
    "finance": {"semantic": 0.3, "temporal": 0.3, "importance": 0.3, "emotional": 0.1},
    "creativity": {"semantic": 0.4, "temporal": 0.15, "importance": 0.25, "emotional": 0.2},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_persona_tags(raw_value: Any) -> List[str]:
    """Return a list of persona tags from metadata or filter values."""

    if raw_value is None:
        return []

    if isinstance(raw_value, list):
        return [str(tag) for tag in raw_value]

    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(tag) for tag in parsed]
        except (TypeError, json.JSONDecodeError):
            # Treat the raw string as a single tag when not JSON.
            return [raw_value]
        return [raw_value]

    return [str(raw_value)]


@dataclass
class PersonaRetrievalResult:
    persona: str
    items: List[Dict[str, Any]]
    weight_profile: Dict[str, float]
    source: str
    summaries: List[Dict[str, Any]] = field(default_factory=list)


class PersonaRetrievalAgent:
    """Wraps retrieval services with persona-specific weighting."""

    def __init__(self, persona: str, hybrid_service: Optional[HybridRetrievalService] = None):
        self.persona = persona
        self.hybrid = hybrid_service or HybridRetrievalService()
        self.weight_profile = PERSONA_WEIGHT_PROFILES.get(persona, PERSONA_WEIGHT_PROFILES["identity"])

    def retrieve(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> PersonaRetrievalResult:
        metadata_filters = metadata_filters or {}
        target_tags = _normalize_persona_tags(metadata_filters.get("persona_tags"))
        persona_requested = bool(target_tags)
        if persona_requested and self.persona not in target_tags:
            target_tags.append(self.persona)

        hybrid_query = RetrievalQuery(
            user_id=user_id,
            query_text=query,
            limit=limit,
            memory_types=None,
            emotional_context=None,
        )
        hybrid_query.weight_overrides = {
            "semantic": self.weight_profile.get("semantic"),
            "temporal": self.weight_profile.get("temporal"),
            "importance": self.weight_profile.get("importance"),
            "emotional": self.weight_profile.get("emotional"),
        }

        hybrid_results = self.hybrid.retrieve_memories(hybrid_query)
        if persona_requested:
            filtered_results = []
            for result in hybrid_results:
                tags = _normalize_persona_tags((result.metadata or {}).get("persona_tags"))
                if any(tag in target_tags for tag in tags):
                    filtered_results.append(result)
            hybrid_results = filtered_results
        else:
            prioritized: List[Any] = []
            remainder: List[Any] = []
            for result in hybrid_results:
                tags = _normalize_persona_tags((result.metadata or {}).get("persona_tags"))
                if self.persona in tags:
                    prioritized.append(result)
                else:
                    remainder.append(result)
            hybrid_results = prioritized + remainder

        # Apply additional metadata filters (layer, type, etc.)
        if metadata_filters:
            for key, value in metadata_filters.items():
                if key == "persona_tags":
                    continue
                if value is None:
                    continue
                filtered_results = []
                for result in hybrid_results:
                    meta = result.metadata or {}
                    meta_value = meta.get(key)
                    if isinstance(value, list):
                        normalized = {str(v) for v in value}
                        if str(meta_value) in normalized:
                            filtered_results.append(result)
                    else:
                        if str(meta_value) == str(value):
                            filtered_results.append(result)
                hybrid_results = filtered_results
        formatted = [
            {
                "id": r.memory_id,
                "content": r.content,
                "score": r.relevance_score,
                "metadata": r.metadata,
            }
            for r in hybrid_results
        ]

        if not formatted:
            # Fall back to baseline search. Only enforce persona filtering when
            # the caller explicitly requested it to preserve backwards
            # compatibility with legacy memories that lack persona tags.
            search_filters = dict(metadata_filters or {})
            if persona_requested:
                search_filters["persona_tags"] = target_tags
            else:
                search_filters.pop("persona_tags", None)
            fallback, _ = search_memories(
                user_id=user_id,
                query=query,
                filters=search_filters,
                limit=limit,
                offset=0,
            )
            if not persona_requested:
                prioritized = []
                remainder = []
                for item in fallback:
                    tags = _normalize_persona_tags((item.get("metadata") or {}).get("persona_tags"))
                    if self.persona in tags:
                        prioritized.append(item)
                    else:
                        remainder.append(item)
                formatted = prioritized + remainder
            else:
                formatted = fallback

        return PersonaRetrievalResult(
            persona=self.persona,
            items=formatted,
            weight_profile=self.weight_profile,
            source="hybrid" if hybrid_results else "semantic",
        )


class PersonaCoPilot:
    """Coordinates persona selection and retrieval orchestration."""

    def __init__(
        self,
        state_store: Optional[PersonaStateStore] = None,
        summary_manager: Optional[SummaryManager] = None,
    ):
        self.state_store = state_store or PersonaStateStore()
        self._agents: Dict[str, PersonaRetrievalAgent] = {}
        self.summary_manager = summary_manager or SummaryManager()

    def _get_agent(self, persona: str) -> PersonaRetrievalAgent:
        if persona not in self._agents:
            self._agents[persona] = PersonaRetrievalAgent(persona)
        return self._agents[persona]

    def _resolve_personas(self, state: PersonaState, forced_persona: Optional[str] = None) -> List[str]:
        if forced_persona:
            return [forced_persona]
        personas = state.active_personas or []
        if not personas:
            personas = ["identity"]
        return personas

    def retrieve(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        persona_context: Optional[Dict[str, Any]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        include_summaries: bool = False,
        granularity: Optional[str] = None,
    ) -> Dict[str, PersonaRetrievalResult]:
        persona_context = persona_context or {}
        forced = persona_context.get("forced_persona")
        if persona_context.get("active_personas"):
            self.state_store.update_state(user_id, active_personas=list(persona_context["active_personas"]))
        if persona_context.get("mood"):
            self.state_store.update_state(user_id, mood=persona_context["mood"])

        state = self.state_store.get_state(user_id)
        personas = self._resolve_personas(state, forced_persona=forced)

        results: Dict[str, PersonaRetrievalResult] = {}
        for persona in personas:
            agent = self._get_agent(persona)
            persona_result = agent.retrieve(
                user_id=user_id,
                query=query,
                limit=limit,
                metadata_filters=metadata_filters,
            )
            if include_summaries:
                tier = self.summary_manager.resolve_tier(granularity)
                persona_result.summaries = self.summary_manager.get_summaries(
                    user_id=user_id,
                    persona=persona,
                    tier=tier,
                )
            results[persona] = persona_result
        return results


__all__ = [
    "PersonaCoPilot",
    "PersonaRetrievalAgent",
    "PersonaRetrievalResult",
    "PersonaStateStore",
    "PersonaState",
]
