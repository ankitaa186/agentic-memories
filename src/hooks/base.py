"""Base classes shared by hook implementations."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .settings import HookSettings


@dataclass(slots=True)
class HookEvent:
    """A normalized event emitted by an external system hook."""

    event_id: str
    user_id: str
    category: str
    source: str
    payload: Dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        """Return the global deduplication key."""

        return f"hook:{self.source}:{self.category}:{self.event_id}"


@dataclass(slots=True)
class WebhookEnvelope:
    """Data received from an external webhook callback."""

    user_id: str
    event_id: Optional[str]
    payload: Dict[str, Any]
    occurred_at: Optional[datetime] = None
    headers: Dict[str, Any] = field(default_factory=dict)


class HookError(RuntimeError):
    """Base class for hook related failures."""


class Hook(ABC):
    """Base class for all hook integrations."""

    def __init__(
        self,
        settings: HookSettings,
        *,
        manager: "HookManagerProtocol",
    ) -> None:
        from .pipeline import NormalizationPipeline  # Local import to avoid cycle

        self.settings = settings
        self.manager = manager
        self.pipeline: NormalizationPipeline = manager.pipeline
        self.logger = logging.getLogger(f"agentic_memories.hooks.{settings.name}")
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        """Start the hook background worker if applicable."""

        if self._running:
            return
        self._running = True
        await self.on_start()
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run_wrapper())
        self.logger.info("started hook")

    async def stop(self) -> None:
        """Stop the hook background worker."""

        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.on_stop()
        self.logger.info("stopped hook")

    async def on_start(self) -> None:  # pragma: no cover - default noop
        """Hook-specific startup logic."""

    async def on_stop(self) -> None:  # pragma: no cover - default noop
        """Hook-specific shutdown logic."""

    async def _run_wrapper(self) -> None:
        try:
            await self.run()
        except asyncio.CancelledError:  # pragma: no cover - cooperative shutdown
            pass
        except Exception as exc:  # pragma: no cover - log unexpected failures
            self.logger.exception("hook crashed: %s", exc)

    async def run(self) -> None:
        """Background task executed while the hook is running."""

        # Default hooks do not require a background worker.
        await asyncio.sleep(0)

    async def emit(self, event: HookEvent) -> None:
        """Send an event to the normalization pipeline."""

        await self.pipeline.process(event)

    def transform_webhook(self, envelope: WebhookEnvelope) -> Optional[HookEvent]:
        """Convert a webhook envelope into a :class:`HookEvent`.

        Hooks that rely on incoming callbacks should override this method.
        """

        return None


class PollingHook(Hook):
    """Convenience base class for poll-based hooks."""

    async def run(self) -> None:  # pragma: no cover - exercised through subclasses
        interval = max(5, int(self.settings.poll_interval_seconds))
        backoff = max(5, int(self.settings.error_backoff_seconds))
        self.logger.debug("polling hook started | interval=%ss", interval)
        while self._running:
            try:
                events = await self.poll_once()
                if events:
                    self.logger.debug("poll produced %s events", len(events))
                    for event in events:
                        await self.emit(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.exception("poll failed: %s", exc)
                await asyncio.sleep(backoff)
                continue
            await asyncio.sleep(interval)

    @abstractmethod
    async def poll_once(self) -> list[HookEvent]:
        """Retrieve new events from the external system."""


class HookManagerProtocol(ABC):  # pragma: no cover - typing helper
    """Minimal protocol used by hooks to avoid circular imports."""

    @property
    @abstractmethod
    def pipeline(self) -> "NormalizationPipeline":
        raise NotImplementedError

    @abstractmethod
    def get_consent(self, hook_name: str, user_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_consent(self, hook_name: str) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def load_state(self, hook_name: str, user_id: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_state(self, hook_name: str, user_id: str, state: Dict[str, Any]) -> None:
        raise NotImplementedError


__all__ = [
    "Hook",
    "HookEvent",
    "HookError",
    "WebhookEnvelope",
    "PollingHook",
]
