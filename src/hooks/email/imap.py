"""Generic IMAP hook for email providers."""

from __future__ import annotations

import asyncio
import email
from email.message import Message
import imaplib
import logging
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

from ..base import HookEvent, PollingHook


class IMAPHook(PollingHook):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("agentic_memories.hooks.imap")

    async def poll_once(self) -> list[HookEvent]:
        events: list[HookEvent] = []
        consent_map = self.manager.list_consent(self.settings.name)
        for user_id, consent in consent_map.items():
            events.extend(self._consume_seed_messages(user_id, consent))
            config = self._merge_config(consent)
            if not config:
                continue
            imap_events = await self._poll_imap(user_id, config)
            events.extend(imap_events)
        return events

    def _consume_seed_messages(self, user_id: str, consent: Dict[str, Any]) -> list[HookEvent]:
        seeds: List[Dict[str, Any]] = list(consent.get("seed_messages") or [])
        if not seeds:
            return []
        events = [
            HookEvent(
                event_id=str(message.get("id") or uuid.uuid4()),
                user_id=user_id,
                category="email",
                source="imap",
                payload=message,
                occurred_at=self._parse_datetime(message.get("date")),
                metadata={"seed": True},
            )
            for message in seeds
        ]
        consent.pop("seed_messages", None)
        self.manager.save_consent(self.settings.name, user_id, consent)
        return events

    def _merge_config(self, consent: Dict[str, Any]) -> Dict[str, Any]:
        base = dict(self.settings.config)
        dynamic = consent.get("credentials") or consent.get("config") or {}
        base.update(dynamic)
        return base

    async def _poll_imap(self, user_id: str, config: Dict[str, Any]) -> list[HookEvent]:
        return await asyncio.to_thread(self._poll_imap_sync, user_id, config)

    def _poll_imap_sync(self, user_id: str, config: Dict[str, Any]) -> list[HookEvent]:
        host = config.get("host")
        username = config.get("username")
        password = config.get("password")
        folder = config.get("folder", "INBOX")
        port = int(config.get("port", 993))
        if not host or not username or not password:
            return []
        events: list[HookEvent] = []
        client = None
        try:
            client = imaplib.IMAP4_SSL(host, port)
            client.login(username, password)
            client.select(folder)
            typ, data = client.search(None, "UNSEEN")
            if typ != "OK":
                return []
            ids = data[0].split()
            for msg_id in ids[: config.get("max_messages", 10)]:
                typ, msg_data = client.fetch(msg_id, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                msg_bytes = msg_data[0][1]
                message = email.message_from_bytes(msg_bytes)
                payload = self._extract_message(message)
                payload["id"] = payload.get("message_id") or msg_id.decode()
                events.append(
                    HookEvent(
                        event_id=str(payload["id"]),
                        user_id=user_id,
                        category="email",
                        source="imap",
                        payload=payload,
                        occurred_at=self._parse_datetime(payload.get("date")),
                        metadata={"folder": folder},
                    )
                )
                client.store(msg_id, "+FLAGS", "(\\Seen)")
        except Exception as exc:
            self.logger.debug("imap poll failed | host=%s | reason=%s", host, exc)
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
        return events

    def _extract_message(self, message: Message) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "subject": message.get("Subject"),
            "from": message.get("From"),
            "to": message.get("To"),
            "date": message.get("Date"),
            "message_id": message.get("Message-ID"),
            "body": self._get_body(message),
        }
        return payload

    def _get_body(self, message: Message) -> str:
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                if content_type in {"text/plain", "text/html"}:
                    try:
                        return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                    except Exception:
                        continue
        else:
            try:
                return message.get_payload(decode=True).decode(message.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                return message.get_payload()
        return ""

    def _parse_datetime(self, value: Any) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            if isinstance(value, str):
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
        except Exception:
            pass
        return datetime.now(timezone.utc)


__all__ = ["IMAPHook"]
