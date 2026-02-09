from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Dict, List, Sequence, Tuple

from src.memory_orchestrator import (
    AdaptiveMemoryOrchestrator,
    MemoryInjectionSource,
    MessageEvent,
    MessageRole,
)
from src.memory_orchestrator.policies import IngestionPolicy, RetrievalPolicy
from src.models import Memory


class PersistRecorder:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Sequence[str]]] = []
        self.memories: List[str] = []

    def __call__(self, user_id: str, memories: Sequence[Memory]) -> Sequence[str]:
        ids = [
            f"mem-{len(self.calls) + index}"
            for index, _ in enumerate(memories, start=1)
        ]
        self.calls.append((user_id, ids))
        self.memories.extend(
            [memory.metadata.get("aggregation", "single") for memory in memories]
        )
        return ids


def _no_retrieval(*_args, **_kwargs):
    return [], 0


def _make_event(idx: int, metadata: Dict[str, str] | None = None) -> MessageEvent:
    metadata = metadata or {"user_id": "user-1"}
    return MessageEvent(
        conversation_id="conv-1",
        message_id=f"m-{idx}",
        role=MessageRole.USER,
        content=f"message {idx}",
        metadata=metadata,
    )


def test_ingestion_batches_scale_with_volume() -> None:
    recorder = PersistRecorder()
    policy = IngestionPolicy(
        low_volume_cutoff=2,
        high_volume_cutoff=4,
        low_volume_batch_size=1,
        medium_volume_batch_size=2,
        high_volume_batch_size=3,
        flush_interval=timedelta(days=1),
        max_buffer_size=10,
    )

    orchestrator = AdaptiveMemoryOrchestrator(
        ingestion_policy=policy,
        retrieval_policy=RetrievalPolicy(min_similarity=1.0),
        persist_fn=recorder,
        search_fn=_no_retrieval,
    )

    async def scenario() -> None:
        for idx in range(5):
            await orchestrator.stream_message(_make_event(idx))
        await orchestrator.flush()

    asyncio.run(scenario())

    # First two messages stored individually, middle pair batched, final flushed on demand
    assert len(recorder.calls) == 4
    assert recorder.memories[0] == "single"
    assert recorder.memories[1] == "single"
    assert recorder.memories[2] == "batched_transcript"
    assert recorder.memories[3] == "single"


def test_retrieval_injections_respect_cooldown() -> None:
    injections: List[Tuple[str, MemoryInjectionSource]] = []

    def listener(injection):
        injections.append((injection.memory_id, injection.source))

    def search_stub(*_args, **_kwargs):
        return (
            [
                {
                    "id": "memory-1",
                    "content": "prior context",
                    "score": 0.1,
                    "metadata": {"layer": "long-term"},
                }
            ],
            1,
        )

    orchestrator = AdaptiveMemoryOrchestrator(
        ingestion_policy=IngestionPolicy(
            low_volume_cutoff=0,
            high_volume_cutoff=0,
            low_volume_batch_size=1,
            medium_volume_batch_size=1,
            high_volume_batch_size=1,
            flush_interval=timedelta(days=1),
            max_buffer_size=5,
        ),
        retrieval_policy=RetrievalPolicy(
            min_similarity=0.2,
            max_injections_per_message=1,
            reinjection_cooldown_turns=3,
        ),
        persist_fn=PersistRecorder(),
        search_fn=search_stub,
    )

    async def scenario() -> None:
        sub = orchestrator.subscribe_injections(listener, conversation_id="conv-1")
        try:
            await orchestrator.stream_message(_make_event(0))
            await orchestrator.stream_message(_make_event(1))
        finally:
            sub.close()
        await orchestrator.shutdown()

    asyncio.run(scenario())

    assert len(injections) == 1
    memory_id, source = injections[0]
    assert memory_id == "memory-1"
    assert source is MemoryInjectionSource.LONG_TERM


def test_fetch_memories_formats_results_without_state() -> None:
    def search_stub(user_id: str, query: str, _filters, limit: int, offset: int):
        assert user_id == "user-42"
        assert query == "reminder"
        assert limit == 2
        assert offset == 0
        return (
            [
                {
                    "id": "memory-1",
                    "content": "remember to hydrate",
                    "score": 0.1,
                    "metadata": {"layer": "short-term"},
                },
                {
                    "id": "memory-2",
                    "content": "schedule meeting",
                    "score": 0.2,
                    "metadata": {"layer": "semantic"},
                },
            ],
            2,
        )

    orchestrator = AdaptiveMemoryOrchestrator(
        persist_fn=PersistRecorder(),
        search_fn=search_stub,
        retrieval_policy=RetrievalPolicy(min_similarity=0.2),
    )

    async def scenario() -> List[str]:
        injections = await orchestrator.fetch_memories(
            conversation_id="conv-42",
            query="reminder",
            metadata={"user_id": "user-42"},
            limit=2,
        )
        return [item.memory_id for item in injections]

    memory_ids = asyncio.run(scenario())

    assert memory_ids == ["memory-1", "memory-2"]


def test_scoped_subscription_filters_other_conversations() -> None:
    captured: List[str] = []

    def listener(injection):
        captured.append(injection.metadata.get("conversation_id", ""))

    def search_stub(user_id: str, _query: str, _filters, _limit: int, _offset: int):
        return (
            [
                {
                    "id": f"mem-{user_id}",
                    "content": "context",
                    "score": 0.1,
                    "metadata": {"layer": "semantic"},
                }
            ],
            1,
        )

    orchestrator = AdaptiveMemoryOrchestrator(
        persist_fn=PersistRecorder(),
        search_fn=search_stub,
        retrieval_policy=RetrievalPolicy(min_similarity=0.1),
    )

    async def scenario() -> None:
        subscription = orchestrator.subscribe_injections(
            listener, conversation_id="conv-a"
        )
        try:
            await orchestrator.stream_message(
                MessageEvent(
                    conversation_id="conv-a",
                    message_id="a-1",
                    role=MessageRole.USER,
                    content="hi",
                    metadata={"user_id": "user-a"},
                )
            )
            await orchestrator.stream_message(
                MessageEvent(
                    conversation_id="conv-b",
                    message_id="b-1",
                    role=MessageRole.USER,
                    content="hello",
                    metadata={"user_id": "user-b"},
                )
            )
        finally:
            subscription.close()

    asyncio.run(scenario())

    assert captured == ["conv-a"]
