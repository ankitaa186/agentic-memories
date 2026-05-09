from __future__ import annotations

from typing import Any, Dict

import logging

from src.services.compaction_graph import run_compaction_graph


logger = logging.getLogger("agentic_memories.forget")


def run_compaction_for_user(
    user_id: str, skip_reextract: bool = True, skip_consolidate: bool = False
) -> Dict[str, Any]:
    """Run LangGraph-based compaction for a single user and return summary metrics.

    Args:
            user_id: User to compact
            skip_reextract: If True, skip expensive LLM re-extraction (default True)
            skip_consolidate: If True, skip memory consolidation (default False - runs by default)
    """
    try:
        final = run_compaction_graph(
            user_id, skip_reextract=skip_reextract, skip_consolidate=skip_consolidate
        )
        metrics = final.get("metrics", {})
        logger.info("[forget.compact] user_id=%s metrics=%s", user_id, metrics)
        return {"user_id": user_id, **metrics}
    except Exception as exc:
        logger.info("[forget.compact.error] user_id=%s %s", user_id, exc)
        return {"user_id": user_id, "error": str(exc)}
