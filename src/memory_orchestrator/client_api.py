"""Public interfaces that chatbot clients use to interact with the memory orchestrator.

The goal of this module is to make the orchestrator feel like a simple, streaming
extension point: clients forward message events as they happen and receive memory
injections over callback hooks.  The orchestrator hides the ingestion throttling,
batching, and retrieval scheduling complexity described in the proposal.

Example usage
-------------

.. code-block:: python

    orchestrator: MemoryOrchestratorClient = build_memory_orchestrator()

    async def on_injection(injection: MemoryInjection) -> None:
        await chatbot.push_memory(injection.content)

    subscription = orchestrator.subscribe_injections(on_injection)

    for event in conversation_stream():
        await orchestrator.stream_message(event)

    await orchestrator.flush()
    subscription.close()

The concrete implementation returned by ``build_memory_orchestrator`` is free to
run background workers, schedule ingestion batches, and coordinate retrieval
queries – none of which the client has to know about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Awaitable, Callable, Dict, Optional, Protocol, runtime_checkable


class MessageRole(str, Enum):
    """Role of a chat participant for a streamed message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass(slots=True)
class MessageEvent:
    """Canonical representation of a single chat turn forwarded by the client.

    Attributes
    ----------
    conversation_id:
        Stable identifier for the chat session; allows the orchestrator to keep
        per-conversation state.
    message_id:
        Optional per-message identifier supplied by the client to aid
        idempotency.  If omitted the orchestrator will assign its own.
    role:
        Role of the participant that produced the message.
    content:
        The raw text payload.
    timestamp:
        Wall-clock timestamp captured by the client; defaults to ``datetime.utcnow``.
    metadata:
        Arbitrary client-supplied metadata (channel identifiers, tenant
        information, etc.).
    """

    conversation_id: str
    content: str
    role: MessageRole
    message_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(default_factory=dict)


class MemoryInjectionSource(str, Enum):
    """Identifies the origin or rationale for an injected memory."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SAFETY = "safety"
    PERSONALIZATION = "personalization"
    SYSTEM = "system"


class MemoryInjectionChannel(str, Enum):
    """Specifies how the memory should be surfaced to the chatbot runtime."""

    INLINE = "inline"
    TOOL = "tool"
    SIDE_CHANNEL = "side_channel"


@dataclass(slots=True)
class MemoryInjection:
    """Memory payload emitted back to the chatbot client."""

    memory_id: str
    content: str
    source: MemoryInjectionSource
    channel: MemoryInjectionChannel = MemoryInjectionChannel.INLINE
    score: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)


InjectionListener = Callable[[MemoryInjection], Awaitable[None] | None]


@dataclass(slots=True)
class InjectionSubscription:
    """Handle returned to the client so it can stop receiving injections."""

    close: Callable[[], None]


@runtime_checkable
class MemoryOrchestratorClient(Protocol):
    """Minimal interface presented to chatbot runtimes."""

    async def stream_message(self, event: MessageEvent) -> None:
        """Forward a single message event to the orchestrator."""

    def subscribe_injections(
        self,
        listener: InjectionListener,
        *,
        conversation_id: str | None = None,
    ) -> InjectionSubscription:
        """Register a listener that will receive memory injections.

        Parameters
        ----------
        listener:
            Callback that receives ``MemoryInjection`` payloads.
        conversation_id:
            Optional conversation scope. When provided the orchestrator will only
            deliver injections produced for the matching conversation, preventing
            cross-session leakage when multiple chat sessions run concurrently.
        """

    async def flush(self) -> None:
        """Ensure queued ingestions and retrieval work complete."""

    async def shutdown(self) -> None:
        """Release resources allocated by the orchestrator implementation."""
