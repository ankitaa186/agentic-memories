"""Utilities for normalizing client-supplied chat events."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Callable, Dict
from uuid import uuid4

from .client_api import MessageEvent


class MessageStreamAdapter:
    """Ensures inbound events follow orchestrator expectations.

    The adapter assigns a message identifier when the client omits one and coerces
    metadata keys/values into strings so downstream persistence layers can safely
    serialize them.  It also fills a timestamp when a client forgets to provide
    one (some SDKs omit timestamps for assistant turns).
    """

    def __init__(self, message_id_factory: Callable[[], str] | None = None) -> None:
        self._message_id_factory = message_id_factory or (lambda: uuid4().hex)

    def adapt(self, event: MessageEvent) -> MessageEvent:
        message_id = event.message_id or self._message_id_factory()

        # ``metadata`` is declared as Dict[str, str]; coerce eagerly to avoid
        # surprises once we persist the event into JSON stores.
        metadata: Dict[str, str] = {}
        for key, value in (event.metadata or {}).items():
            metadata[str(key)] = str(value)

        timestamp = event.timestamp or datetime.utcnow()

        return replace(
            event, message_id=message_id, metadata=metadata, timestamp=timestamp
        )
