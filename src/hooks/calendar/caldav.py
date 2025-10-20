"""CalDAV/ICS polling hook."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import httpx

from ..base import HookEvent, PollingHook


class CalDAVHook(PollingHook):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("agentic_memories.hooks.caldav")

    async def poll_once(self) -> list[HookEvent]:
        events: list[HookEvent] = []
        consent_map = self.manager.list_consent(self.settings.name)
        for user_id, consent in consent_map.items():
            events.extend(self._consume_seed_events(user_id, consent))
            config = self._merge_config(consent)
            if not config:
                continue
            ics_events = await self._fetch_ics_events(user_id, config)
            events.extend(ics_events)
        return events

    def _consume_seed_events(self, user_id: str, consent: Dict[str, Any]) -> list[HookEvent]:
        seeds: List[Dict[str, Any]] = list(consent.get("seed_events") or [])
        if not seeds:
            return []
        events = [
            HookEvent(
                event_id=str(event.get("id") or uuid.uuid4()),
                user_id=user_id,
                category="calendar",
                source="caldav",
                payload=event,
                occurred_at=self._parse_datetime(event.get("start")),
                metadata={"seed": True},
            )
            for event in seeds
        ]
        consent.pop("seed_events", None)
        self.manager.save_consent(self.settings.name, user_id, consent)
        return events

    def _merge_config(self, consent: Dict[str, Any]) -> Dict[str, Any]:
        base = dict(self.settings.config)
        dynamic = consent.get("credentials") or consent.get("config") or {}
        base.update(dynamic)
        return base

    async def _fetch_ics_events(self, user_id: str, config: Dict[str, Any]) -> list[HookEvent]:
        url = config.get("ics_url") or config.get("url")
        if not url:
            return []
        auth = None
        username = config.get("username")
        password = config.get("password")
        if username and password:
            auth = (username, password)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, auth=auth)
                response.raise_for_status()
                body = response.text
        except Exception as exc:
            self.logger.debug("caldav fetch failed | url=%s | reason=%s", url, exc)
            return []
        events = []
        for payload in self._parse_ics(body):
            events.append(
                HookEvent(
                    event_id=payload.get("uid", str(uuid.uuid4())),
                    user_id=user_id,
                    category="calendar",
                    source="caldav",
                    payload=payload,
                    occurred_at=self._parse_datetime(payload.get("start")),
                    metadata={"ics_url": url},
                )
            )
        return events

    def _parse_ics(self, body: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}
        in_event = False
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line == "BEGIN:VEVENT":
                in_event = True
                current = {}
                continue
            if line == "END:VEVENT" and in_event:
                events.append(current)
                in_event = False
                continue
            if not in_event or ":" not in line:
                continue
            key, value = self._split_ics_line(line)
            if key == "DTSTART":
                current["start"] = value
            elif key == "DTEND":
                current["end"] = value
            elif key == "SUMMARY":
                current["summary"] = value
            elif key == "LOCATION":
                current["location"] = value
            elif key == "UID":
                current["uid"] = value
            elif key == "DESCRIPTION":
                current["description"] = value
        return events

    def _split_ics_line(self, line: str) -> Tuple[str, str]:
        key, value = line.split(":", 1)
        if ";" in key:
            key = key.split(";", 1)[0]
        return key, value

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, dict):
            value = value.get("dateTime") or value.get("date")
        if not value:
            return datetime.now(timezone.utc)
        try:
            if isinstance(value, str):
                if value.endswith("Z"):
                    value = value.replace("Z", "+00:00")
                if "T" in value:
                    return datetime.fromisoformat(value)
                return datetime.fromisoformat(value + "T00:00:00+00:00")
        except Exception:
            pass
        return datetime.now(timezone.utc)


__all__ = ["CalDAVHook"]
