"""Gmail hook implementation leveraging Google APIs when configured."""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from ..base import HookEvent, PollingHook, WebhookEnvelope


class GmailHook(PollingHook):
    API_BASE = "https://gmail.googleapis.com/gmail/v1/users"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("agentic_memories.hooks.gmail")

    async def poll_once(self) -> list[HookEvent]:
        events: list[HookEvent] = []
        consent_map = self.manager.list_consent(self.settings.name)
        for user_id, consent in consent_map.items():
            events.extend(self._consume_seed_messages(user_id, consent))
            token_info = consent.get("tokens") or consent.get("oauth")
            if token_info and token_info.get("access_token"):
                api_events = await self._poll_gmail_api(user_id, token_info)
                events.extend(api_events)
        return events

    def _consume_seed_messages(self, user_id: str, consent: Dict[str, Any]) -> list[HookEvent]:
        seeds: List[Dict[str, Any]] = list(consent.get("seed_messages") or [])
        if not seeds:
            return []
        events: list[HookEvent] = []
        for message in seeds:
            occurred = self._parse_datetime(message.get("internalDate"))
            event = HookEvent(
                event_id=str(message.get("id") or uuid.uuid4()),
                user_id=user_id,
                category="email",
                source="gmail",
                payload=message,
                occurred_at=occurred,
                metadata={"seed": True},
            )
            events.append(event)
        consent.pop("seed_messages", None)
        self.manager.save_consent(self.settings.name, user_id, consent)
        return events

    async def _poll_gmail_api(self, user_id: str, token_info: Dict[str, Any]) -> list[HookEvent]:
        access_token = token_info.get("access_token")
        gmail_user = token_info.get("gmail_user", "me")
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"maxResults": 25, "labelIds": ["INBOX"], "q": "newer_than:1d"}
        state = self.manager.load_state(self.settings.name, user_id, default={})
        if state.get("page_token"):
            params["pageToken"] = state["page_token"]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.API_BASE}/{gmail_user}/messages", headers=headers, params=params)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            self.logger.debug("gmail api poll skipped | reason=%s", exc)
            return []

        messages = body.get("messages") or []
        next_page = body.get("nextPageToken")
        if next_page:
            state["page_token"] = next_page
            self.manager.save_state(self.settings.name, user_id, state)
        events: list[HookEvent] = []
        for message in messages:
            msg_id = message.get("id")
            if not msg_id:
                continue
            detail = await self._fetch_message_detail(gmail_user, msg_id, headers)
            if not detail:
                continue
            occurred = self._parse_datetime(detail.get("internalDate"))
            events.append(
                HookEvent(
                    event_id=str(msg_id),
                    user_id=user_id,
                    category="email",
                    source="gmail",
                    payload=detail,
                    occurred_at=occurred,
                    metadata={"thread_id": detail.get("threadId")},
                )
            )
        return events

    async def _fetch_message_detail(self, gmail_user: str, message_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.API_BASE}/{gmail_user}/messages/{message_id}",
                    headers=headers,
                    params={"format": "full"},
                )
                resp.raise_for_status()
                data = resp.json()
                return self._flatten_message_payload(data)
        except Exception as exc:
            self.logger.debug("gmail message fetch failed | message_id=%s | reason=%s", message_id, exc)
            return {}

    def _flatten_message_payload(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload") or {}
        headers = payload.get("headers") or []
        header_map = {h.get("name"): h.get("value") for h in headers if isinstance(h, dict)}
        parts = payload.get("parts") or []
        body_text = ""
        for part in parts:
            mime = part.get("mimeType", "")
            if mime.startswith("text/") and part.get("body", {}).get("data"):
                encoded = part.get("body", {}).get("data")
                try:
                    body_text = base64.urlsafe_b64decode(encoded + "==").decode("utf-8", errors="ignore")
                except Exception:
                    body_text = encoded
                break
        flattened = {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "snippet": message.get("snippet"),
            "internalDate": message.get("internalDate"),
            "subject": header_map.get("Subject"),
            "from": header_map.get("From"),
            "to": header_map.get("To"),
            "cc": header_map.get("Cc"),
            "bcc": header_map.get("Bcc"),
            "body": body_text,
            "labels": message.get("labelIds"),
        }
        flattened["raw_headers"] = header_map
        return flattened

    def transform_webhook(self, envelope: WebhookEnvelope):
        payload = envelope.payload or {}
        history_id = payload.get("historyId")
        if not history_id:
            return None
        state = self.manager.load_state(self.settings.name, envelope.user_id, default={})
        state["last_history_id"] = history_id
        self.manager.save_state(self.settings.name, envelope.user_id, state)
        return HookEvent(
            event_id=str(envelope.event_id or history_id),
            user_id=envelope.user_id,
            category="email",
            source="gmail_webhook",
            payload=payload,
            occurred_at=envelope.occurred_at or datetime.now(timezone.utc),
            metadata={"webhook": True},
        )

    def _parse_datetime(self, value: Any) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
            if isinstance(value, str) and value.isdigit():
                return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            pass
        return datetime.now(timezone.utc)


__all__ = ["GmailHook"]
