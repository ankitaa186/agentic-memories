"""Adaptive memory orchestrator implementation."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from src.models import Memory
from src.services.retrieval import search_memories
from src.services.storage import upsert_memories

from .client_api import (
    InjectionListener,
    InjectionSubscription,
    MemoryInjection,
    MemoryOrchestratorClient,
    MessageEvent,
)
from .ingestion import IngestionBatch, IngestionController
from .message_adapter import MessageStreamAdapter
from .policies import IngestionPolicy, RetrievalPolicy
from .retrieval import RetrievalOrchestrator

logger = logging.getLogger("agentic_memories.orchestrator")


PersistFn = Callable[[str, Sequence[Memory]], Sequence[str]]
SearchFn = Callable[[str, str, Optional[Dict[str, object]], int, int], Tuple[List[Dict[str, object]], int]]


class AdaptiveMemoryOrchestrator(MemoryOrchestratorClient):
    """Coordinates ingestion throttling and retrieval injections."""

    def __init__(
        self,
        *,
        ingestion_policy: IngestionPolicy | None = None,
        retrieval_policy: RetrievalPolicy | None = None,
        persist_fn: PersistFn | None = None,
        search_fn: SearchFn | None = None,
    ) -> None:
        self._adapter = MessageStreamAdapter()
        self._ingestion = IngestionController(ingestion_policy)
        self._retrieval = RetrievalOrchestrator(retrieval_policy)
        self._persist = persist_fn or upsert_memories
        self._search = search_fn or search_memories
        self._listeners: List[tuple[InjectionListener, str | None]] = []
        self._lock = asyncio.Lock()
        self._closed = False

    async def stream_message(self, event: MessageEvent) -> None:
        async with self._lock:
            self._ensure_open()
            adapted = self._adapter.adapt(event)
            logger.debug(
                "[orchestrator.stream] conversation=%s role=%s", adapted.conversation_id, adapted.role
            )

            batches = self._ingestion.process(adapted)
            for batch in batches:
                self._persist_batch(batch)

            injections = self._maybe_retrieve(adapted)
        await self._publish(injections)

    async def fetch_memories(
        self,
        *,
        conversation_id: str,
        query: str,
        metadata: Dict[str, str] | None = None,
        limit: int = 6,
        offset: int = 0,
    ) -> List[MemoryInjection]:
        async with self._lock:
            self._ensure_open()

        metadata = metadata or {}
        user_id = metadata.get("user_id") or conversation_id

        try:
            results, _ = self._search(user_id, query, None, limit, offset)
        except Exception:
            logger.exception("[orchestrator.retrieve.error] user=%s", user_id)
            return []

        formatted = self._retrieval.format_results(conversation_id, results)
        return formatted[:limit]

    def subscribe_injections(
        self,
        listener: InjectionListener,
        *,
        conversation_id: str | None = None,
    ) -> InjectionSubscription:
        self._listeners.append((listener, conversation_id))

        def _close() -> None:
            try:
                self._listeners.remove((listener, conversation_id))
            except ValueError:
                pass

        return InjectionSubscription(close=_close)

    async def flush(self) -> None:
        async with self._lock:
            self._ensure_open()
            batches = self._ingestion.flush()
            for batch in batches:
                self._persist_batch(batch)

    async def shutdown(self) -> None:
        async with self._lock:
            if self._closed:
                return
            batches = self._ingestion.flush()
            for batch in batches:
                self._persist_batch(batch)
            self._closed = True
            self._listeners.clear()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Memory orchestrator has been shut down")

    def _persist_batch(self, batch: IngestionBatch) -> None:
        memories = batch.to_memories()
        if not memories:
            logger.debug(
                "[orchestrator.persist.skip] conversation=%s user=%s reason=no_memories",
                batch.conversation_id,
                batch.user_id,
            )
            return
        
        try:
            ids = self._persist(batch.user_id, memories)
            logger.debug(
                "[orchestrator.persist] conversation=%s user=%s count=%s ids=%s",
                batch.conversation_id,
                batch.user_id,
                len(memories),
                list(ids),
            )
        except Exception:
            logger.exception(
                "[orchestrator.persist.error] conversation=%s user=%s", batch.conversation_id, batch.user_id
            )

    def _maybe_retrieve(self, event: MessageEvent) -> List[MemoryInjection]:
        user_id = event.metadata.get("user_id") or event.conversation_id
        try:
            results, _ = self._search(user_id, event.content, None, 6, 0)
        except Exception:
            logger.exception("[orchestrator.retrieve.error] user=%s", user_id)
            return []
        return self._retrieval.consider(event, results)

    async def _publish(self, injections: Iterable[MemoryInjection]) -> None:
        if not injections:
            return
        for injection in injections:
            metadata = injection.metadata or {}
            injection_conversation = metadata.get("conversation_id")
            for listener, scope in list(self._listeners):
                if scope is not None and scope != injection_conversation:
                    continue
                try:
                    maybe_awaitable = listener(injection)
                    if asyncio.iscoroutine(maybe_awaitable):
                        await maybe_awaitable
                except Exception:
                    logger.exception(
                        "[orchestrator.publish.error] listener=%s injection=%s",
                        getattr(listener, "__name__", "<callable>"),
                        injection.memory_id,
                    )


def build_default_orchestrator() -> AdaptiveMemoryOrchestrator:
    """Factory used by services to obtain the adaptive orchestrator."""

    return AdaptiveMemoryOrchestrator()

