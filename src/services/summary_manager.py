from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid

from src.dependencies.redis_client import get_redis_client
from src.services.retrieval import search_memories


class SummaryTier(str, Enum):
    RAW = "raw"
    EPISODIC = "episodic"
    ARC = "arc"


@dataclass
class SummaryRecord:
    id: str
    user_id: str
    tier: SummaryTier
    persona: str
    text: str
    confidence: float
    freshness: float
    source_ids: List[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tier": self.tier.value,
            "persona": self.persona,
            "text": self.text,
            "confidence": self.confidence,
            "freshness": self.freshness,
            "source_ids": self.source_ids,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SummaryRecord":
        created_raw = payload.get("created_at")
        if isinstance(created_raw, str):
            try:
                created = datetime.fromisoformat(created_raw)
            except ValueError:
                created = datetime.now(timezone.utc)
        elif isinstance(created_raw, datetime):
            created = created_raw
        else:
            created = datetime.now(timezone.utc)
        return cls(
            id=payload.get("id", uuid.uuid4().hex),
            user_id=payload.get("user_id", ""),
            tier=SummaryTier(payload.get("tier", SummaryTier.EPISODIC.value)),
            persona=payload.get("persona", "identity"),
            text=payload.get("text", ""),
            confidence=float(payload.get("confidence", 0.7)),
            freshness=float(payload.get("freshness", 1.0)),
            source_ids=list(payload.get("source_ids") or []),
            created_at=created,
        )


class SummaryStore:
    """Stores summary records in Redis with in-memory fallback."""

    def __init__(self, ttl_seconds: int = 86400):
        self._redis = get_redis_client()
        self._ttl = ttl_seconds
        self._cache: Dict[str, List[SummaryRecord]] = {}

    def _key(self, user_id: str, persona: str, tier: SummaryTier) -> str:
        return f"persona:summary:{user_id}:{persona}:{tier.value}"

    def load(self, user_id: str, persona: str, tier: SummaryTier) -> List[SummaryRecord]:
        key = self._key(user_id, persona, tier)
        if self._redis is not None:
            raw = self._redis.get(key)
            if raw:
                try:
                    payload = json.loads(raw)
                    return [SummaryRecord.from_dict(item) for item in payload]
                except Exception:
                    pass
        return list(self._cache.get(key, []))

    def save(self, user_id: str, persona: str, tier: SummaryTier, records: List[SummaryRecord]) -> None:
        key = self._key(user_id, persona, tier)
        if self._redis is not None:
            payload = json.dumps([record.to_dict() for record in records])
            self._redis.setex(key, self._ttl, payload)
        else:
            self._cache[key] = list(records)


class SummaryManager:
    """Generates and retrieves persona-aware summaries across tiers."""

    def __init__(self, store: Optional[SummaryStore] = None):
        self.store = store or SummaryStore()

    def resolve_tier(self, granularity: str | None) -> SummaryTier:
        if not granularity or granularity == "auto":
            return SummaryTier.EPISODIC
        try:
            return SummaryTier(granularity)
        except ValueError:
            return SummaryTier.EPISODIC

    def get_summaries(
        self,
        user_id: str,
        persona: str,
        tier: SummaryTier,
        limit: int = 3,
        regenerate_if_stale: bool = True,
    ) -> List[Dict[str, Any]]:
        records = self.store.load(user_id, persona, tier)
        if regenerate_if_stale and (not records or self._is_stale(records)):
            records = self._generate(user_id=user_id, persona=persona, tier=tier)
            self.store.save(user_id, persona, tier, records)
        return [record.to_dict() for record in records[:limit]]

    def _is_stale(self, records: List[SummaryRecord]) -> bool:
        if not records:
            return True
        newest = max(record.created_at for record in records)
        age = datetime.now(timezone.utc) - newest
        # Consider stale if older than 24 hours or freshness below threshold
        return age.total_seconds() > 86400 or any(record.freshness < 0.6 for record in records)

    def _generate(self, user_id: str, persona: str, tier: SummaryTier) -> List[SummaryRecord]:
        query = ""  # Blank query to fetch persona scoped memories
        filters = {"persona_tags": [persona]}
        results, _ = search_memories(user_id=user_id, query=query, filters=filters, limit=20, offset=0)
        if not results:
            return []

        top_memories = results[:5]
        source_ids = [item["id"] for item in top_memories]
        # Basic heuristic summary construction
        snippets = [item["content"] for item in top_memories]
        if tier == SummaryTier.RAW:
            text = "\n".join(snippets)
        elif tier == SummaryTier.ARC:
            text = f"Persona {persona} arc: " + " | ".join(snippets)
        else:
            text = f"Recent highlights for {persona}: " + "; ".join(snippets)

        confidence = sum((item.get("score", 0.0) or 0.0) for item in top_memories) / max(len(top_memories), 1)
        freshness = 1.0
        now = datetime.now(timezone.utc)
        record = SummaryRecord(
            id=f"sum_{uuid.uuid4().hex[:10]}",
            user_id=user_id,
            persona=persona,
            tier=tier,
            text=text,
            confidence=float(confidence),
            freshness=freshness,
            source_ids=source_ids,
            created_at=now,
        )
        return [record]


__all__ = ["SummaryManager", "SummaryRecord", "SummaryStore", "SummaryTier"]
