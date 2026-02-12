"""Retrieval orchestration logic for the adaptive orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .client_api import (
    MemoryInjection,
    MemoryInjectionChannel,
    MemoryInjectionSource,
    MessageEvent,
    MessageRole,
)
from .policies import RetrievalPolicy


@dataclass(slots=True)
class _ConversationRetrievalState:
    turn_index: int = 0
    injected_turns: Dict[str, int] = field(default_factory=dict)

    def advance(self) -> None:
        self.turn_index += 1

    def record_injection(self, memory_id: str) -> None:
        self.injected_turns[memory_id] = self.turn_index

    def prune(self, max_age: int) -> None:
        cutoff = self.turn_index - max_age
        to_remove = [mid for mid, turn in self.injected_turns.items() if turn <= cutoff]
        for mid in to_remove:
            self.injected_turns.pop(mid, None)

    def recently_injected(self, memory_id: str, cooldown: int) -> bool:
        turn = self.injected_turns.get(memory_id)
        if turn is None:
            return False
        return (self.turn_index - turn) < cooldown


class RetrievalOrchestrator:
    """Determines which memories to inject back into the conversation."""

    def __init__(self, policy: RetrievalPolicy | None = None) -> None:
        self._policy = policy or RetrievalPolicy()
        self._states: Dict[str, _ConversationRetrievalState] = {}

    def _state_for(self, conversation_id: str) -> _ConversationRetrievalState:
        state = self._states.get(conversation_id)
        if state is None:
            state = _ConversationRetrievalState()
            self._states[conversation_id] = state
        return state

    def consider(
        self,
        event: MessageEvent,
        retrieval_results: List[Dict[str, object]],
    ) -> List[MemoryInjection]:
        state = self._state_for(event.conversation_id)
        state.advance()
        state.prune(self._policy.reinjection_cooldown_turns)

        if event.role is not MessageRole.USER:
            return []

        injections: List[MemoryInjection] = []

        for result in retrieval_results:
            memory_id = str(result.get("id"))
            if not memory_id or state.recently_injected(
                memory_id, self._policy.reinjection_cooldown_turns
            ):
                continue

            injection = self._build_injection(event.conversation_id, result)
            if injection is None:
                continue

            injections.append(injection)
            state.record_injection(memory_id)

            if len(injections) >= self._policy.max_injections_per_message:
                break

        return injections

    def format_results(
        self, conversation_id: str, retrieval_results: List[Dict[str, object]]
    ) -> List[MemoryInjection]:
        """Convert raw retrieval results into injection payloads without state updates."""

        injections: List[MemoryInjection] = []
        for result in retrieval_results:
            injection = self._build_injection(conversation_id, result)
            if injection is not None:
                injections.append(injection)
        return injections

    def _build_injection(
        self, conversation_id: str, result: Dict[str, object]
    ) -> MemoryInjection | None:
        memory_id = str(result.get("id"))
        if not memory_id:
            return None

        try:
            raw_score = float(result.get("score", 0.0))
            # Apply the same score transformation as the traditional retrieve endpoint
            # ChromaDB returns distance scores (lower is better), so we invert them
            score = 1.0 - raw_score
        except (TypeError, ValueError):
            score = 0.0

        if score < self._policy.min_similarity:
            return None

        metadata = result.get("metadata") or {}
        layer = (
            str(metadata.get("layer", "semantic"))
            if isinstance(metadata, dict)
            else "semantic"
        )
        source = _source_from_layer(layer)

        return MemoryInjection(
            memory_id=memory_id,
            content=str(result.get("content", "")),
            source=source,
            channel=MemoryInjectionChannel.INLINE,
            score=score,
            metadata={"layer": layer, "conversation_id": conversation_id},
        )


def _source_from_layer(layer: str) -> MemoryInjectionSource:
    normalized = layer.lower()
    if normalized in {"short-term", "short_term"}:
        return MemoryInjectionSource.SHORT_TERM
    if normalized in {"long-term", "long_term"}:
        return MemoryInjectionSource.LONG_TERM
    if normalized == "semantic":
        return MemoryInjectionSource.LONG_TERM
    return MemoryInjectionSource.SYSTEM
