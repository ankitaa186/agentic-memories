"""Normalization pipeline for hook events."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from src.schemas import Message, TranscriptRequest
from src.services.unified_ingestion_graph import run_unified_ingestion
from src.dependencies.redis_client import get_redis_client

from .base import HookEvent


class HookPayload(BaseModel):
    """Normalized payload consumed by the ingestion graph."""

    user_id: str
    category: str
    source: str
    subject: Optional[str] = None
    content: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    def to_transcript_request(self) -> TranscriptRequest:
        history = [Message(role="user", content=self.content)]
        metadata = {
            "hook_category": self.category,
            "hook_source": self.source,
            "hook_occurred_at": self.occurred_at.isoformat(),
            **self.metadata,
        }
        if self.subject:
            metadata.setdefault("subject", self.subject)
        metadata["raw_payload"] = self.raw_payload
        return TranscriptRequest(user_id=self.user_id, history=history, metadata=metadata)


class BaseNormalizer:
    """Convert hook events into :class:`HookPayload` instances."""

    category: str = "generic"

    def matches(self, event: HookEvent) -> bool:
        return event.category == self.category

    def normalize(self, event: HookEvent) -> HookPayload:
        content = json.dumps(event.payload, default=str)
        return HookPayload(
            user_id=event.user_id,
            category=event.category,
            source=event.source,
            content=content,
            occurred_at=event.occurred_at,
            metadata=event.metadata,
            raw_payload=event.payload,
        )


class EmailNormalizer(BaseNormalizer):
    category = "email"

    def normalize(self, event: HookEvent) -> HookPayload:
        payload = event.payload
        subject = payload.get("subject") or payload.get("title")
        sender = payload.get("from") or payload.get("sender")
        recipients = payload.get("to") or payload.get("recipients")
        snippet = payload.get("snippet") or payload.get("body", "")
        body = payload.get("body") or payload.get("text") or payload.get("html", "")
        attachments = payload.get("attachments", [])

        lines = []
        if subject:
            lines.append(f"Email subject: {subject}")
        if sender:
            lines.append(f"From: {sender}")
        if recipients:
            if isinstance(recipients, (list, tuple)):
                rec_str = ", ".join(str(r) for r in recipients)
            else:
                rec_str = str(recipients)
            lines.append(f"To: {rec_str}")
        if snippet and snippet != body:
            lines.append(f"Summary: {snippet}")
        if body:
            lines.append("Body:\n" + str(body))
        if attachments:
            attachment_names = ", ".join(a.get("filename", "attachment") for a in attachments)
            lines.append(f"Attachments: {attachment_names}")

        content = "\n\n".join(lines) if lines else json.dumps(payload, default=str)
        metadata = {**event.metadata}
        metadata.setdefault("thread_id", payload.get("thread_id"))
        metadata.setdefault("message_id", payload.get("id"))
        metadata.setdefault("labels", payload.get("labels"))
        return HookPayload(
            user_id=event.user_id,
            category=event.category,
            source=event.source,
            subject=subject,
            content=content,
            occurred_at=event.occurred_at,
            metadata=metadata,
            raw_payload=payload,
        )


class CalendarNormalizer(BaseNormalizer):
    category = "calendar"

    def normalize(self, event: HookEvent) -> HookPayload:
        payload = event.payload
        title = payload.get("summary") or payload.get("title")
        start = payload.get("start")
        end = payload.get("end")
        attendees = payload.get("attendees") or []
        location = payload.get("location")
        description = payload.get("description")

        attendee_str = ", ".join(a.get("email", str(a)) for a in attendees) if attendees else "None"
        start_text = start.get("dateTime") if isinstance(start, dict) else start
        end_text = end.get("dateTime") if isinstance(end, dict) else end
        lines = [f"Calendar event: {title or payload.get('id', 'untitled event')}" ]
        if start_text:
            lines.append(f"Starts: {start_text}")
        if end_text:
            lines.append(f"Ends: {end_text}")
        lines.append(f"Attendees: {attendee_str}")
        if location:
            lines.append(f"Location: {location}")
        if description:
            lines.append("Description:\n" + str(description))

        metadata = {**event.metadata}
        metadata.setdefault("event_id", payload.get("id"))
        metadata.setdefault("status", payload.get("status"))
        metadata.setdefault("organizer", payload.get("organizer"))
        return HookPayload(
            user_id=event.user_id,
            category=event.category,
            source=event.source,
            subject=title,
            content="\n\n".join(lines),
            occurred_at=event.occurred_at,
            metadata=metadata,
            raw_payload=payload,
        )


class NormalizationPipeline:
    """Deduplicate, normalize, and ingest hook events."""

    def __init__(
        self,
        *,
        redis_client=None,
        normalizers: Optional[list[BaseNormalizer]] = None,
        ingestion_runner: Optional[Callable[[TranscriptRequest], Dict[str, Any]]] = None,
        dedupe_ttl_seconds: int = 86400,
    ) -> None:
        self.logger = logging.getLogger("agentic_memories.hooks.pipeline")
        self.redis = redis_client or get_redis_client()
        self.normalizers = normalizers or [EmailNormalizer(), CalendarNormalizer(), BaseNormalizer()]
        self.ingestion_runner = ingestion_runner or run_unified_ingestion
        self.dedupe_ttl_seconds = dedupe_ttl_seconds
        self._local_seen: set[str] = set()

    async def process(self, event: HookEvent) -> Optional[Dict[str, Any]]:
        if self._is_duplicate(event):
            self.logger.debug("duplicate event skipped | key=%s", event.dedupe_key())
            return None

        normalizer = self._get_normalizer(event)
        payload = normalizer.normalize(event)
        request = payload.to_transcript_request()
        self.logger.info(
            "processing hook event | user_id=%s | category=%s | source=%s",
            event.user_id,
            event.category,
            event.source,
        )
        result = await self._run_ingestion(request)
        return result

    def _get_normalizer(self, event: HookEvent) -> BaseNormalizer:
        for normalizer in self.normalizers:
            if normalizer.matches(event):
                return normalizer
        return BaseNormalizer()

    def _is_duplicate(self, event: HookEvent) -> bool:
        key = event.dedupe_key()
        if self.redis is not None:
            try:
                added = self.redis.setnx(key, event.occurred_at.isoformat())
                if added:
                    self.redis.expire(key, self.dedupe_ttl_seconds)
                    return False
                return True
            except Exception as exc:  # pragma: no cover - redis failures are logged but not fatal
                self.logger.warning("redis dedupe failed: %s", exc)
        if key in self._local_seen:
            return True
        self._local_seen.add(key)
        return False

    async def _run_ingestion(self, request: TranscriptRequest) -> Dict[str, Any]:
        if inspect.iscoroutinefunction(self.ingestion_runner):
            return await self.ingestion_runner(request)  # type: ignore[arg-type]
        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(self.ingestion_runner, request)


__all__ = [
    "HookPayload",
    "NormalizationPipeline",
]
