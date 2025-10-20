"""Registry of available hook implementations."""

from __future__ import annotations

from typing import Dict, Optional, Type

from .base import Hook
from .email.gmail import GmailHook
from .email.imap import IMAPHook
from .calendar.google_calendar import GoogleCalendarHook
from .calendar.caldav import CalDAVHook


_REGISTRY: Dict[str, Type[Hook]] = {
    "gmail": GmailHook,
    "imap": IMAPHook,
    "google_calendar": GoogleCalendarHook,
    "caldav": CalDAVHook,
}


def resolve(kind: str) -> Optional[Type[Hook]]:
    return _REGISTRY.get(kind)


__all__ = ["resolve"]
