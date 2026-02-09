"""Adaptive ingestion controller used by the orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.models import Memory
from src.schemas import TranscriptRequest, Message
from src.config import is_llm_configured

from .client_api import MessageEvent
from .policies import IngestionPolicy

logger = logging.getLogger("agentic_memories.orchestrator")


@dataclass(slots=True)
class IngestionBatch:
    """Group of message events that should be persisted together."""

    user_id: str
    conversation_id: str
    events: List[MessageEvent]
    aggregated: bool

    def to_memories(self) -> List[Memory]:
        """Convert the batch into normalized Memory instances using unified ingestion graph."""
        # Fallback to raw storage if LLM not configured
        if not is_llm_configured():
            return [self._to_raw_memory()]

        # Convert MessageEvent list to Message list for TranscriptRequest
        history: List[Message] = []
        for event in self.events:
            # Convert MessageRole enum to string, filter out TOOL role (not supported by Message schema)
            role_str = event.role.value
            if role_str == "tool":
                # Skip tool messages or convert to assistant - tool role not in Message schema
                role_str = "assistant"

            # Only include supported roles with non-empty content
            if (
                role_str in ("user", "assistant", "system")
                and event.content
                and event.content.strip()
            ):
                history.append(Message(role=role_str, content=event.content))

        if not history:
            # No valid messages to process
            return []

        # Build metadata preserving orchestrator context
        metadata = {
            "conversation_id": self.conversation_id,
            "message_ids": [
                event.message_id for event in self.events if event.message_id
            ],
            "message_roles": [event.role.value for event in self.events],
            "batch_size": len(self.events),
            "source": "orchestrator",
        }
        if self.aggregated:
            metadata["aggregation"] = "batched_transcript"

        # Create TranscriptRequest
        request = TranscriptRequest(
            user_id=self.user_id,
            history=history,
            metadata=metadata,
        )

        # Run unified ingestion graph
        try:
            from src.services.unified_ingestion_graph import run_unified_ingestion

            final_state = run_unified_ingestion(request)
            memories = final_state.get("memories", [])

            # Enrich memories with orchestrator metadata
            for memory in memories:
                if memory.metadata:
                    memory.metadata.update(
                        {
                            "conversation_id": self.conversation_id,
                            "orchestrator_batch": True,
                        }
                    )
                else:
                    memory.metadata = {
                        "conversation_id": self.conversation_id,
                        "orchestrator_batch": True,
                    }

            return memories
        except Exception as e:
            # Log error and fallback to raw storage
            logger.warning(
                "[orchestrator.ingestion.fallback] conversation=%s error=%s falling back to raw",
                self.conversation_id,
                e,
                exc_info=True,
            )
            return [self._to_raw_memory()]

    def _to_raw_memory(self) -> Memory:
        """Fallback: Convert the batch into a raw Memory instance (legacy behavior)."""
        transcript_lines = [
            f"{event.role.value}: {event.content}" for event in self.events
        ]
        content = "\n".join(transcript_lines)

        metadata = {
            "conversation_id": self.conversation_id,
            "message_ids": [
                event.message_id for event in self.events if event.message_id
            ],
            "message_roles": [event.role.value for event in self.events],
            "batch_size": len(self.events),
            "source": "orchestrator_raw",
        }
        if self.aggregated:
            metadata["aggregation"] = "batched_transcript"

        first = self.events[0]
        return Memory(
            user_id=self.user_id,
            content=content,
            layer="short-term",
            type="explicit",
            timestamp=first.timestamp,
            metadata=metadata,
        )


@dataclass(slots=True)
class _ConversationState:
    """Tracks ingestion information for a single conversation."""

    user_id: str
    total_messages: int = 0
    pending: List[MessageEvent] = field(default_factory=list)
    last_flush_timestamp: Optional[datetime] = None

    def append(self, event: MessageEvent) -> None:
        self.pending.append(event)
        self.total_messages += 1

    def drain(self, aggregated: bool) -> IngestionBatch:
        events = list(self.pending)
        self.pending.clear()
        batch = IngestionBatch(
            user_id=self.user_id,
            conversation_id=events[0].conversation_id,
            events=events,
            aggregated=aggregated,
        )
        self.last_flush_timestamp = events[-1].timestamp
        return batch


class IngestionController:
    """Manages batching heuristics for message ingestion."""

    def __init__(self, policy: IngestionPolicy | None = None) -> None:
        self._policy = policy or IngestionPolicy()
        self._states: Dict[str, _ConversationState] = {}

    def _state_for(self, event: MessageEvent) -> _ConversationState:
        user_id = event.metadata.get("user_id") or event.conversation_id
        state = self._states.get(event.conversation_id)
        if state is None:
            state = _ConversationState(user_id=user_id)
            self._states[event.conversation_id] = state
        return state

    def process(self, event: MessageEvent) -> List[IngestionBatch]:
        state = self._state_for(event)
        state.append(event)

        batches: List[IngestionBatch] = []
        target_size = self._target_batch_size(state)

        if len(state.pending) >= target_size:
            batches.append(state.drain(aggregated=target_size > 1))
        elif len(state.pending) >= self._policy.max_buffer_size:
            batches.append(state.drain(aggregated=True))
        else:
            # Check if this event is sufficiently far from the last flush to force a write
            # For single-message conversations (last_flush is None), check time since first pending message
            last_flush = state.last_flush_timestamp
            if state.pending:
                if last_flush is not None:
                    # Normal case: check time since last flush
                    time_since_flush = event.timestamp - last_flush
                    if time_since_flush >= self._policy.flush_interval:
                        batches.append(state.drain(aggregated=len(state.pending) > 1))
                else:
                    # First message case: check time since first pending message
                    # This ensures single-message conversations are persisted after flush_interval
                    first_pending = state.pending[0]
                    time_since_first = event.timestamp - first_pending.timestamp
                    if time_since_first >= self._policy.flush_interval:
                        batches.append(state.drain(aggregated=len(state.pending) > 1))

        return batches

    def flush(self) -> List[IngestionBatch]:
        batches: List[IngestionBatch] = []
        for conversation_id, state in list(self._states.items()):
            if state.pending:
                batches.append(state.drain(aggregated=len(state.pending) > 1))
            if not state.pending:
                self._states.pop(conversation_id, None)
        return batches

    def _target_batch_size(self, state: _ConversationState) -> int:
        if state.total_messages <= self._policy.low_volume_cutoff:
            return self._policy.low_volume_batch_size
        if state.total_messages <= self._policy.high_volume_cutoff:
            return self._policy.medium_volume_batch_size
        return self._policy.high_volume_batch_size
