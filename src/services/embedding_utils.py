"""
Embedding utilities for memory extraction and retrieval.
"""

from __future__ import annotations

import os
from typing import List, Optional

from src.config import get_embedding_model_name


EMBEDDING_MODEL = get_embedding_model_name()


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding for text using OpenAI.
    Uses Langfuse OpenAI wrapper for auto-instrumentation.

    Args:
            text: Input text to generate embedding for

    Returns:
            Embedding vector

    Raises:
            RuntimeError: If OPENAI_API_KEY is not configured or API call fails
    """
    from src.config import is_langfuse_enabled

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or api_key.strip() == "":
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set OPENAI_API_KEY environment variable."
        )

    try:
        # Use Langfuse OpenAI wrapper for auto-instrumentation if enabled
        if is_langfuse_enabled():
            try:
                from langfuse.openai import OpenAI  # type: ignore
            except ImportError:
                from openai import OpenAI  # type: ignore
        else:
            from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        embedding = list(resp.data[0].embedding)
        return embedding
    except Exception as e:
        from src.services.tracing import trace_error

        trace_error(
            e,
            metadata={
                "model": EMBEDDING_MODEL,
                "context": "embedding_generation",
            },
        )
        raise RuntimeError(
            f"OpenAI embedding generation failed: {e}. "
            "Check your API key and billing at https://platform.openai.com/account/billing"
        ) from e


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch helper to generate embeddings for a list of texts.
    Always returns a list of vectors (never None entries).
    """
    results: List[List[float]] = []
    for t in texts or []:
        vec = generate_embedding(t or "") or []
        results.append(vec)
    return results
