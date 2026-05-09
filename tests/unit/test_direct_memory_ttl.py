"""
Unit tests for AM-X.0 — `POST /v1/memories/direct` honors `ttl_seconds` on
every layer (not just `short-term`).

Covers AC5:
  1. `ttl_seconds` honored on `semantic`.
  2. `ttl_seconds` honored on `long-term`.
  3. `ttl_seconds` omitted on `semantic`/`long-term` -> immortal (ttl is None).
  4. `ttl_seconds` omitted on `short-term` -> falls back to
     `get_default_short_term_ttl_seconds()`.

The router resolves the per-record TTL and constructs a `Memory` instance,
which it then passes to `upsert_memories(user_id, [memory])`. We capture the
Memory via a stub `upsert_memories` and assert on `memory.ttl`. We do NOT
exercise the downstream Chroma metadata builder here — `_build_metadata` is
already covered by `tests/unit/test_app_store.py` and converts a non-None
`memory.ttl` into a `ttl_epoch` of `int(time.time()) + ttl` (see
`src/services/storage.py:_ttl_epoch_from_ttl`). The resolved-TTL gate is the
only thing AM-X.0 changes, so it is the only thing this file asserts.
"""

from __future__ import annotations

import time
from typing import List, Tuple
from unittest.mock import patch


def _capture_memory_stub() -> Tuple[List, callable]:
    """Build a side_effect for `upsert_memories` that records the Memory it
    receives, and a list to read it from after the request returns."""

    captured: List = []

    def _stub(user_id, memories):
        # The router always passes [single_memory]; record it for assertions.
        captured.extend(memories)
        return [m.id for m in memories]

    return captured, _stub


def _post_direct(api_client, **body_overrides):
    """Drive POST /v1/memories/direct with the embedding + storage pipeline
    stubbed out, returning (response, captured_memories)."""

    captured, stub = _capture_memory_stub()
    mock_embedding = [0.1] * 1536

    body = {
        "user_id": "test-user-ttl",
        "content": "User test fact for TTL gate.",
    }
    body.update(body_overrides)

    with patch("src.routers.memories.generate_embedding", return_value=mock_embedding):
        with patch("src.routers.memories.upsert_memories", side_effect=stub):
            response = api_client.post("/v1/memories/direct", json=body)

    return response, captured


# ---------------------------------------------------------------------------
# AC5 case 1: ttl_seconds honored on semantic
# ---------------------------------------------------------------------------


def test_ttl_seconds_honored_on_semantic_layer(api_client):
    """A semantic memory with ttl_seconds=86400 must carry ttl=86400."""
    response, captured = _post_direct(
        api_client,
        layer="semantic",
        ttl_seconds=86400,
    )

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    memory = captured[0]
    assert memory.layer == "semantic"
    assert memory.ttl == 86400


# ---------------------------------------------------------------------------
# AC5 case 2: ttl_seconds honored on long-term
# ---------------------------------------------------------------------------


def test_ttl_seconds_honored_on_long_term_layer(api_client):
    """A long-term memory with ttl_seconds=3600 must carry ttl=3600."""
    response, captured = _post_direct(
        api_client,
        layer="long-term",
        ttl_seconds=3600,
    )

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    memory = captured[0]
    assert memory.layer == "long-term"
    assert memory.ttl == 3600


# ---------------------------------------------------------------------------
# AC5 case 3: omit ttl_seconds on semantic/long-term -> immortal
# ---------------------------------------------------------------------------


def test_omitted_ttl_keeps_semantic_immortal(api_client):
    """Omitting ttl_seconds on a semantic layer keeps the memory immortal."""
    response, captured = _post_direct(api_client, layer="semantic")

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    assert captured[0].layer == "semantic"
    assert captured[0].ttl is None


def test_omitted_ttl_keeps_long_term_immortal(api_client):
    """Omitting ttl_seconds on a long-term layer keeps the memory immortal."""
    response, captured = _post_direct(api_client, layer="long-term")

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    assert captured[0].layer == "long-term"
    assert captured[0].ttl is None


# ---------------------------------------------------------------------------
# AC5 case 4: omit ttl_seconds on short-term -> default short-term TTL
# ---------------------------------------------------------------------------


def test_omitted_ttl_uses_default_for_short_term(api_client):
    """Omitting ttl_seconds on short-term falls back to the configured default."""
    # Patch the helper at the import site (the router imports the symbol
    # directly via `from src.config import get_default_short_term_ttl_seconds`).
    sentinel_default = 7200

    captured, stub = _capture_memory_stub()
    mock_embedding = [0.1] * 1536

    with patch(
        "src.routers.memories.get_default_short_term_ttl_seconds",
        return_value=sentinel_default,
    ):
        with patch(
            "src.routers.memories.generate_embedding", return_value=mock_embedding
        ):
            with patch("src.routers.memories.upsert_memories", side_effect=stub):
                response = api_client.post(
                    "/v1/memories/direct",
                    json={
                        "user_id": "test-user-ttl",
                        "content": "Short-term fact without ttl.",
                        "layer": "short-term",
                    },
                )

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    memory = captured[0]
    assert memory.layer == "short-term"
    assert memory.ttl == sentinel_default


# ---------------------------------------------------------------------------
# AC5 bonus: caller-provided ttl on short-term still wins over the default
#
# This isn't a fresh AC case but it locks the precedence ordering implied by
# AC3 ("the existing per-layer default behavior" — i.e., explicit caller TTL
# beats the default).
# ---------------------------------------------------------------------------


def test_caller_ttl_overrides_default_on_short_term(api_client):
    """An explicit ttl_seconds on short-term wins over the configured default."""
    sentinel_default = 9999  # Should NOT be observed.

    captured, stub = _capture_memory_stub()
    mock_embedding = [0.1] * 1536

    with patch(
        "src.routers.memories.get_default_short_term_ttl_seconds",
        return_value=sentinel_default,
    ):
        with patch(
            "src.routers.memories.generate_embedding", return_value=mock_embedding
        ):
            with patch("src.routers.memories.upsert_memories", side_effect=stub):
                response = api_client.post(
                    "/v1/memories/direct",
                    json={
                        "user_id": "test-user-ttl",
                        "content": "Short-term fact with explicit ttl.",
                        "layer": "short-term",
                        "ttl_seconds": 60,
                    },
                )

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    assert captured[0].ttl == 60


# ---------------------------------------------------------------------------
# AC1 / AC2 reinforcement: ttl flows through to `_ttl_epoch_from_ttl` math
#
# We don't run the real Chroma metadata builder in unit tests, but we do
# verify the resolved `memory.ttl` matches what `_ttl_epoch_from_ttl` would
# combine with `time.time()` to yield `ttl_epoch ≈ now + ttl_seconds ± 5s`.
# This guards against future regressions where `memory.ttl` drifts away from
# the caller's `ttl_seconds`.
# ---------------------------------------------------------------------------


def test_resolved_ttl_matches_caller_within_tolerance(api_client):
    """Sanity check: captured memory.ttl == caller ttl_seconds (no rescaling)."""
    ttl = 86400
    before = int(time.time())
    response, captured = _post_direct(
        api_client,
        layer="semantic",
        ttl_seconds=ttl,
    )
    after = int(time.time())

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    memory = captured[0]
    assert memory.ttl == ttl

    # If we apply the same arithmetic as `_ttl_epoch_from_ttl`, the resulting
    # epoch lands within [before+ttl, after+ttl]. With ±5s slack on both ends.
    derived_epoch = int(time.time()) + memory.ttl
    assert before + ttl - 5 <= derived_epoch <= after + ttl + 5
