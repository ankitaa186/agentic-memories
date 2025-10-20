"""Google Calendar hook implementation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..base import HookEvent, PollingHook, WebhookEnvelope


class GoogleCalendarHook(PollingHook):
    API_BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("agentic_memories.hooks.google_calendar")

    async def poll_once(self) -> list[HookEvent]:
        events: list[HookEvent] = []
        consent_map = self.manager.list_consent(self.settings.name)
        for user_id, consent in consent_map.items():
            events.extend(self._consume_seed_events(user_id, consent))
            token_info = consent.get("tokens") or consent.get("oauth")
            if token_info and token_info.get("access_token"):
                api_events = await self._poll_calendar_api(user_id, token_info)
                events.extend(api_events)
        return events

    def _consume_seed_events(self, user_id: str, consent: Dict[str, Any]) -> list[HookEvent]:
        seeds: List[Dict[str, Any]] = list(consent.get("seed_events") or [])
        if not seeds:
            return []
        events: list[HookEvent] = []
        for raw in seeds:
            occurred = self._parse_datetime(raw.get("start"))
            events.append(
                HookEvent(
                    event_id=str(raw.get("id") or uuid.uuid4()),
                    user_id=user_id,
                    category="calendar",
                    source="google_calendar",
                    payload=raw,
                    occurred_at=occurred,
                    metadata={"seed": True},
                )
            )
        consent.pop("seed_events", None)
        self.manager.save_consent(self.settings.name, user_id, consent)
        return events

    async def _poll_calendar_api(self, user_id: str, token_info: Dict[str, Any]) -> list[HookEvent]:
        access_token = token_info.get("access_token")
        calendar_id = token_info.get("calendar_id", "primary")
        headers = {"Authorization": f"Bearer {access_token}"}
        params: Dict[str, Any] = {
            "maxResults": 50,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeMin": datetime.now(timezone.utc).isoformat(),
        }
        state = self.manager.load_state(self.settings.name, user_id, default={})
        if state.get("sync_token"):
            params = {"maxResults": 50, "syncToken": state["sync_token"]}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.API_BASE}/calendars/{calendar_id}/events",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            self.logger.debug("calendar poll skipped | calendar=%s | reason=%s", calendar_id, exc)
            return []

        events: list[HookEvent] = []
        for item in data.get("items", []):
            if item.get("status") == "cancelled":
                continue
            occurred = self._parse_datetime(item.get("start"))
            events.append(
                HookEvent(
                    event_id=item.get("id", str(uuid.uuid4())),
                    user_id=user_id,
                    category="calendar",
                    source="google_calendar",
                    payload=item,
                    occurred_at=occurred,
                    metadata={"calendar_id": calendar_id},
                )
            )
        if data.get("nextSyncToken"):
            state["sync_token"] = data["nextSyncToken"]
            self.manager.save_state(self.settings.name, user_id, state)
        return events

    def transform_webhook(self, envelope: WebhookEnvelope):
        payload = envelope.payload or {}
        event_id = payload.get("resourceId") or payload.get("id")
        if not event_id:
            return None
        return HookEvent(
            event_id=str(event_id),
            user_id=envelope.user_id,
            category="calendar",
            source="google_calendar_webhook",
            payload=payload,
            occurred_at=envelope.occurred_at or datetime.now(timezone.utc),
            metadata={"webhook": True},
        )

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, dict):
            value = value.get("dateTime") or value.get("date")
        if not value:
            return datetime.now(timezone.utc)
        try:
            if isinstance(value, str):
                if value.endswith("Z"):
                    value = value.replace("Z", "+00:00")
                return datetime.fromisoformat(value)
        except Exception:
            pass
        return datetime.now(timezone.utc)


__all__ = ["GoogleCalendarHook"]
