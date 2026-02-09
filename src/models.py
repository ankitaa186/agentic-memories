from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Memory(BaseModel):
    id: Optional[str] = None
    user_id: str
    content: str
    # Extended layers: episodic (time-bound events), procedural (skills), emotional (mood states)
    layer: Literal[
        "short-term", "semantic", "long-term", "episodic", "procedural", "emotional"
    ]
    type: Literal["explicit", "implicit"]
    embedding: Optional[List[float]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    ttl: Optional[int] = None
    usage_count: int = 0
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    persona_tags: List[str] = Field(default_factory=list)
    emotional_signature: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
