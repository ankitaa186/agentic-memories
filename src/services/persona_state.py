from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import threading

from src.dependencies.redis_client import get_redis_client


@dataclass
class PersonaState:
    """Represents the active persona context for a user session."""

    user_id: str
    active_personas: List[str] = field(default_factory=list)
    forced_persona: Optional[str] = None
    mood: Optional[str] = None
    goals: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "active_personas": self.active_personas,
            "forced_persona": self.forced_persona,
            "mood": self.mood,
            "goals": self.goals,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonaState":
        updated_raw = data.get("updated_at")
        if isinstance(updated_raw, str):
            try:
                updated_at = datetime.fromisoformat(updated_raw)
            except ValueError:
                updated_at = datetime.now(timezone.utc)
        elif isinstance(updated_raw, datetime):
            updated_at = updated_raw
        else:
            updated_at = datetime.now(timezone.utc)
        return cls(
            user_id=data.get("user_id", ""),
            active_personas=list(data.get("active_personas") or []),
            forced_persona=data.get("forced_persona"),
            mood=data.get("mood"),
            goals=dict(data.get("goals") or {}),
            updated_at=updated_at,
        )


class PersonaStateStore:
    """Persists persona state to Redis with in-memory fallback."""

    def __init__(self, ttl_seconds: int = 3600):
        self._redis = get_redis_client()
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cache: Dict[str, PersonaState] = {}

    def _key(self, user_id: str) -> str:
        return f"persona:state:{user_id}"

    def get_state(self, user_id: str) -> PersonaState:
        """Return the current state, defaulting to an empty persona profile."""

        if not user_id:
            raise ValueError("user_id is required for persona state")

        key = self._key(user_id)
        if self._redis is not None:
            raw = self._redis.get(key)
            if raw:
                try:
                    payload = json.loads(raw)
                    state = PersonaState.from_dict(payload)
                    # Ensure canonical user_id even if payload missing
                    state.user_id = user_id or state.user_id
                    return state
                except Exception:
                    # Fall through to cache
                    pass

        with self._lock:
            state = self._cache.get(user_id)
            if state is None:
                state = PersonaState(user_id=user_id)
                self._cache[user_id] = state
            return state

    def update_state(self, user_id: str, **updates: Any) -> PersonaState:
        """Merge updates into the persona state and persist them."""

        state = self.get_state(user_id)
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.updated_at = datetime.now(timezone.utc)

        if self._redis is not None:
            payload = json.dumps(state.to_dict())
            self._redis.setex(self._key(user_id), self._ttl, payload)
        else:
            with self._lock:
                self._cache[user_id] = state
        return state

    def clear_state(self, user_id: str) -> None:
        if self._redis is not None:
            self._redis.delete(self._key(user_id))
        with self._lock:
            self._cache.pop(user_id, None)
