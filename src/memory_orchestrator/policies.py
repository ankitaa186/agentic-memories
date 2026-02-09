"""Policy objects that govern ingestion throttling and retrieval heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class IngestionPolicy:
    """Thresholds that shape batching behaviour for message ingestion."""

    low_volume_cutoff: int = 3
    """Number of conversation messages before we start batching."""

    high_volume_cutoff: int = 8
    """Past this many messages we aggressively batch to control costs."""

    low_volume_batch_size: int = 3
    medium_volume_batch_size: int = 8
    high_volume_batch_size: int = 12

    flush_interval: timedelta = timedelta(seconds=120)
    """Maximum time between writes even if a batch target is not reached."""

    max_buffer_size: int = 20
    """Safety cap to prevent unbounded growth when downstream storage is slow."""


@dataclass(frozen=True)
class RetrievalPolicy:
    """Controls when and how memories are surfaced back to the chatbot."""

    min_similarity: float = 0.15
    """Minimum hybrid score required to inject a memory."""

    max_injections_per_message: int = 3
    reinjection_cooldown_turns: int = 6

    lookback_messages: int = 4
    """How many prior turns we keep when crafting retrieval queries."""
