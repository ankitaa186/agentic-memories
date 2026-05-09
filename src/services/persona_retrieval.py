from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional

from src.services.hybrid_retrieval import HybridRetrievalService, RetrievalQuery
from src.services.retrieval import search_memories
from src.services.persona_state import PersonaState, PersonaStateStore
from src.services.summary_manager import SummaryManager


PERSONA_WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    # Core personas (general-purpose)
    "identity": {"semantic": 0.5, "temporal": 0.2, "importance": 0.2, "emotional": 0.1},
    "relationships": {
        "semantic": 0.3,
        "temporal": 0.2,
        "importance": 0.2,
        "emotional": 0.3,
    },
    "health": {
        "semantic": 0.25,
        "temporal": 0.25,
        "importance": 0.25,
        "emotional": 0.25,
    },
    "finance": {"semantic": 0.3, "temporal": 0.3, "importance": 0.3, "emotional": 0.1},
    "creativity": {
        "semantic": 0.4,
        "temporal": 0.15,
        "importance": 0.25,
        "emotional": 0.2,
    },
    # Annie companion personas
    # - partner: Intimate companion with deep emotional bond, pattern recognition, mirror work
    "partner": {
        "semantic": 0.25,
        "temporal": 0.25,
        "importance": 0.15,
        "emotional": 0.35,
    },
    # - guide: Wise mentor for decisions, goals, accountability, transformation
    "guide": {"semantic": 0.3, "temporal": 0.25, "importance": 0.3, "emotional": 0.15},
    # - strategist: Financial advisor for investments, portfolio, wealth planning
    "strategist": {
        "semantic": 0.25,
        "temporal": 0.3,
        "importance": 0.35,
        "emotional": 0.1,
    },
    # - expert: Technical peer for DIY, cooking, smart home, domain knowledge
    "expert": {"semantic": 0.5, "temporal": 0.15, "importance": 0.2, "emotional": 0.15},
    # - friend: Casual warm companion for everyday moments
    "friend": {"semantic": 0.3, "temporal": 0.25, "importance": 0.15, "emotional": 0.3},
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


def _apply_x2_filters_to_hybrid(
    hybrid_results: List[Any], x2_filters: Dict[str, Any]
) -> List[Any]:
    """Apply X.2 retrieve filters to hybrid-service results in Python.

    The hybrid service does not natively honor X.2's ``created_*`` /
    ``expires_*`` / ``kind`` / ``metadata_filter`` predicates, so for the
    persona-path AC19 to hold end-to-end, we must post-filter hybrid
    results against the same predicate set the where-clause builder
    enforces at the Chroma layer for ``search_memories``.

    Inputs are assumed already-validated:
    - ``created_after`` / ``created_before`` are UTC-normalized ISO strings
      (lex-comparable against the stored ``timestamp`` field).
    - ``expires_after`` / ``expires_before`` are epoch ints. Records WITHOUT
      a ``ttl_epoch`` are excluded by any ``expires_*`` filter (X.2 AC21).
    - ``metadata_filter`` is a ``{key: [values]}`` dict pre-validated.
    """

    out: List[Any] = []
    created_after = x2_filters.get("created_after")
    created_before = x2_filters.get("created_before")
    expires_after = x2_filters.get("expires_after")
    expires_before = x2_filters.get("expires_before")
    kind = x2_filters.get("kind")
    metadata_filter = x2_filters.get("metadata_filter") or {}

    for result in hybrid_results:
        meta = getattr(result, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}
        ts = meta.get("timestamp")
        if isinstance(ts, str):
            if created_after is not None and ts < created_after:
                continue
            if created_before is not None and ts >= created_before:
                continue
        else:
            if created_after is not None or created_before is not None:
                continue
        ttl_epoch = meta.get("ttl_epoch")
        if expires_after is not None or expires_before is not None:
            # X.2 AC21: expires_* filters records WITH a TTL only.
            if ttl_epoch is None:
                continue
            try:
                ttl_int = int(ttl_epoch)
            except (TypeError, ValueError):
                continue
            if expires_after is not None and ttl_int < int(expires_after):
                continue
            if expires_before is not None and ttl_int >= int(expires_before):
                continue
        if kind is not None and str(meta.get("kind", "")) != str(kind):
            continue
        skip = False
        for mk, mv_list in metadata_filter.items():
            # Same single-valued constraint as `_build_where_clause`.
            target = mv_list[0] if isinstance(mv_list, list) else mv_list
            if str(meta.get(mk, "")) != str(target):
                skip = True
                break
        if skip:
            continue
        out.append(result)
    return out


@dataclass
class PersonaRetrievalResult:
    persona: str
    items: List[Dict[str, Any]]
    weight_profile: Dict[str, float]
    source: str
    summaries: List[Dict[str, Any]] = field(default_factory=list)


class PersonaRetrievalAgent:
    """Wraps retrieval services with persona-specific weighting."""

    def __init__(
        self, persona: str, hybrid_service: Optional[HybridRetrievalService] = None
    ):
        self.persona = persona
        self.hybrid = hybrid_service or HybridRetrievalService()
        self.weight_profile = PERSONA_WEIGHT_PROFILES.get(
            persona, PERSONA_WEIGHT_PROFILES["identity"]
        )

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

        # X.2 AC19: thread the new X.2 retrieve filters through the persona
        # path so the dominant retrieve code path (chat runtime, summary
        # manager, memory context, orchestrator — 12+ call sites) honors
        # them. Without this, callers of `_persona_copilot.retrieve` would
        # silently drop every X.2 filter and fall through to unfiltered
        # hybrid retrieval. The hybrid service does not yet honor these
        # filters natively, so we (a) post-filter hybrid results in-Python
        # against the same predicate set used by `_build_where_clause`, and
        # (b) propagate the filters to the `search_memories` fallback below
        # so the where-clause path filters at the Chroma layer.
        x2_filter_keys = (
            "kind",
            "created_after",
            "created_before",
            "expires_after",
            "expires_before",
            "metadata_filter",
        )
        x2_filters: Dict[str, Any] = {
            k: metadata_filters.get(k)
            for k in x2_filter_keys
            if metadata_filters.get(k) not in (None, "", [], {})
        }

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

        # AC19: apply X.2 filters to hybrid_results in-Python BEFORE the
        # persona-tag prioritization step so a filter-mismatched record is
        # never returned even when the embedding query also matched. Avoids
        # a silent regression where chat-runtime retrieve calls would
        # return memories outside the requested time window.
        if x2_filters and hybrid_results:
            hybrid_results = _apply_x2_filters_to_hybrid(hybrid_results, x2_filters)

        if persona_requested:
            filtered_results = []
            for result in hybrid_results:
                tags = _normalize_persona_tags(
                    (result.metadata or {}).get("persona_tags")
                )
                if any(tag in target_tags for tag in tags):
                    filtered_results.append(result)
            hybrid_results = filtered_results
        else:
            prioritized: List[Any] = []
            remainder: List[Any] = []
            for result in hybrid_results:
                tags = _normalize_persona_tags(
                    (result.metadata or {}).get("persona_tags")
                )
                if self.persona in tags:
                    prioritized.append(result)
                else:
                    remainder.append(result)
            hybrid_results = prioritized + remainder

        # Apply additional metadata filters (layer, type, etc.). X.2 keys
        # (created_after, created_before, expires_after, expires_before,
        # kind, metadata_filter) are already applied above via
        # `_apply_x2_filters_to_hybrid`, so skip them here to avoid double
        # application or treating them as bare metadata-equality predicates.
        if metadata_filters:
            for key, value in metadata_filters.items():
                if key == "persona_tags":
                    continue
                if key in x2_filter_keys:
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
            # X.2 AC19: pass X.2 filter keys through (already preserved via
            # metadata_filters) so the where-clause builder filters at the
            # Chroma layer when the hybrid path returned nothing.
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
                    tags = _normalize_persona_tags(
                        (item.get("metadata") or {}).get("persona_tags")
                    )
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

    def _resolve_personas(
        self, state: PersonaState, forced_persona: Optional[str] = None
    ) -> List[str]:
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
            self.state_store.update_state(
                user_id, active_personas=list(persona_context["active_personas"])
            )
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
