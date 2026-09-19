"""Query relevance shared by vector and procedural-memory retrieval.

Compute cosine from candidate vectors, not ``1 - distance``: existing Chroma
collections can use squared L2 even when their descriptive metadata says cosine.
This also handles non-unit vectors without silently assuming normalization.
"""

import math
from typing import Sequence


def cosine_similarity(query: Sequence[float], candidate: Sequence[float]) -> float:
    if not query or len(query) != len(candidate):
        raise ValueError("missing or incompatible retrieval embeddings")
    if not all(math.isfinite(v) for v in (*query, *candidate)):
        raise ValueError("non-finite retrieval embedding")
    query_norm = math.sqrt(math.fsum(v * v for v in query))
    candidate_norm = math.sqrt(math.fsum(v * v for v in candidate))
    if not query_norm or not candidate_norm:
        raise ValueError("zero retrieval embedding")
    score = math.fsum(a * b for a, b in zip(query, candidate))
    return max(-1.0, min(1.0, score / (query_norm * candidate_norm)))
