from datetime import datetime, timezone

import pytest

from src.services.persona_retrieval import PersonaRetrievalResult
from src.services.retrieval import (
    INTERNAL_METADATA_FIELDS,
    NAIVE_DATETIME_MSG,
    _build_where_clause,
    _coerce_expires_value,
    _normalize_iso_datetime,
    _parse_metadata_filter_pairs,
    sort_by_recency,
)
from src.services._constants import SYSTEM_MANAGED_FIELDS


def test_retrieve_uses_persona_results(api_client, monkeypatch):
    persona_result = PersonaRetrievalResult(
        persona="identity",
        items=[
            {
                "id": "mem-1",
                "content": "Call mom",
                "score": 0.9,
                "metadata": {
                    "layer": "semantic",
                    "type": "explicit",
                    "persona_tags": ["identity"],
                    "emotional_signature": {"mood": "calm"},
                    "importance": 0.7,
                },
            }
        ],
        weight_profile={"semantic": 0.5},
        source="hybrid",
    )

    monkeypatch.setattr(
        "src.app._persona_copilot.retrieve", lambda **_: {"identity": persona_result}
    )

    def search_stub(**_):
        raise AssertionError("search_memories should not be called")

    monkeypatch.setattr("src.app.search_memories", search_stub)
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve", params={"user_id": "user-123", "query": "call"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["pagination"]["total"] == 1
    assert data["results"][0]["persona_tags"] == ["identity"]
    assert data["results"][0]["emotional_signature"] == {"mood": "calm"}
    assert data["results"][0]["importance"] == 0.7


def test_retrieve_falls_back_to_semantic_search(api_client, monkeypatch):
    monkeypatch.setattr("src.app._persona_copilot.retrieve", lambda **_: {})

    fallback_items = [
        {
            "id": "mem-42",
            "content": "Review quarterly goals",
            "score": 0.8,
            "metadata": {
                "layer": "semantic",
                "type": "explicit",
                "persona_tags": ["identity"],
            },
        }
    ]
    monkeypatch.setattr("src.app.search_memories", lambda **_: (fallback_items, 1))
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve", params={"user_id": "user-123", "query": "goals", "limit": 1}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["pagination"]["total"] == 1
    assert data["results"][0]["id"] == "mem-42"
    assert data["results"][0]["layer"] == "semantic"


# ---------------------------------------------------------------------------
# AM-X.2 — datetime normalization (AC18) and validation (AC3, AC14)
# ---------------------------------------------------------------------------


def test_normalize_iso_datetime_accepts_z_suffix():
    out = _normalize_iso_datetime("2026-05-08T00:00:00Z", "created_after")
    assert out == "2026-05-08T00:00:00+00:00"


def test_normalize_iso_datetime_accepts_explicit_offset_and_normalizes_to_utc():
    # 2026-05-08T00:00:00-07:00 == 2026-05-08T07:00:00+00:00
    out = _normalize_iso_datetime("2026-05-08T00:00:00-07:00", "created_after")
    assert out == "2026-05-08T07:00:00+00:00"


def test_normalize_iso_datetime_rejects_naive():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _normalize_iso_datetime("2026-05-08T00:00:00", "created_after")
    assert exc.value.status_code == 422
    assert NAIVE_DATETIME_MSG in exc.value.detail


def test_normalize_iso_datetime_rejects_garbage():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _normalize_iso_datetime("not a datetime", "created_after")
    assert exc.value.status_code == 422


def test_coerce_expires_value_accepts_int_epoch():
    assert _coerce_expires_value(1700000000, "expires_after") == 1700000000


def test_coerce_expires_value_accepts_iso_datetime_and_returns_epoch():
    val = _coerce_expires_value("2026-05-08T00:00:00Z", "expires_after")
    assert isinstance(val, int)
    assert val == int(datetime(2026, 5, 8, 0, 0, 0, tzinfo=timezone.utc).timestamp())


def test_coerce_expires_value_rejects_naive_iso():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _coerce_expires_value("2026-05-08T00:00:00", "expires_after")


def test_coerce_expires_value_accepts_numeric_string():
    assert _coerce_expires_value("1700000000", "expires_after") == 1700000000


# ---------------------------------------------------------------------------
# AM-X.2 — _build_where_clause (AC10, AC11)
# ---------------------------------------------------------------------------


def test_build_where_clause_user_only_returns_flat_dict():
    clause = _build_where_clause("u-1")
    assert clause == {"user_id": "u-1"}


def test_build_where_clause_layer_and_type_uses_and():
    clause = _build_where_clause("u-1", layer="semantic", type_="explicit")
    assert "$and" in clause
    flat = clause["$and"]
    assert {"user_id": "u-1"} in flat
    assert {"layer": "semantic"} in flat
    assert {"type": "explicit"} in flat


def test_build_where_clause_omits_timestamp_range():
    """Chroma 1.x rejects $gte/$lt on string fields, so created_* filters
    are NOT pushed into the where-clause. They are applied in Python by
    ``search_memories`` post-fetch (see ``_filter_records_by_timestamp``).

    Live-curl regression test for the 2026-05-08 cross-tz 500.
    """
    clause = _build_where_clause(
        "u-1",
        created_after="2026-05-08T00:00:00+00:00",
        created_before="2026-05-09T00:00:00+00:00",
    )
    # When only user_id remains (timestamp dropped), the builder collapses
    # to the flat single-clause form.
    assert clause == {"user_id": "u-1"}
    # Sanity: ensure ``timestamp`` does not appear anywhere.
    assert "timestamp" not in str(clause)


def test_build_where_clause_expires_range_uses_int_epoch():
    clause = _build_where_clause(
        "u-1", expires_after=1700000000, expires_before=1800000000
    )
    assert "$and" in clause
    ttl_clause = next(c for c in clause["$and"] if "ttl_epoch" in c)
    assert ttl_clause["ttl_epoch"] == {"$gte": 1700000000, "$lt": 1800000000}


def test_build_where_clause_kind_and_metadata_filter():
    clause = _build_where_clause(
        "u-1",
        kind="meals_today",
        metadata_filter={"tags": ["dinner"]},
    )
    assert "$and" in clause
    parts = clause["$and"]
    assert {"kind": "meals_today"} in parts
    assert {"tags": "dinner"} in parts


def test_build_where_clause_metadata_filter_conflicting_values_raises():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _build_where_clause("u-1", metadata_filter={"tags": ["dinner", "breakfast"]})
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# AM-X.2 — metadata_filter parser (AC4, AC22)
# ---------------------------------------------------------------------------


def test_metadata_filter_parser_accepts_user_keys():
    out = _parse_metadata_filter_pairs(["tags:dinner", "source:annie"])
    assert out == {"tags": ["dinner"], "source": ["annie"]}


def test_metadata_filter_parser_rejects_system_managed_keys():
    from fastapi import HTTPException

    for key in SYSTEM_MANAGED_FIELDS:
        with pytest.raises(HTTPException) as exc:
            _parse_metadata_filter_pairs([f"{key}:foo"])
        assert exc.value.status_code == 422


def test_metadata_filter_parser_rejects_internal_fields():
    from fastapi import HTTPException

    for key in INTERNAL_METADATA_FIELDS:
        with pytest.raises(HTTPException) as exc:
            _parse_metadata_filter_pairs([f"{key}:0.5"])
        assert exc.value.status_code == 422


def test_metadata_filter_parser_rejects_kind_directs_to_dedicated_param():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_metadata_filter_pairs(["kind:meals_today"])
    assert exc.value.status_code == 422
    assert "dedicated `kind` query parameter" in exc.value.detail


def test_metadata_filter_parser_rejects_malformed_entry():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _parse_metadata_filter_pairs(["no_colon_here"])


# ---------------------------------------------------------------------------
# AM-X.2 — sort_by_recency helper (AC23)
# ---------------------------------------------------------------------------


def test_sort_by_recency_newest_first():
    records = [
        {"id": "a", "metadata": {"timestamp": "2026-05-01T00:00:00+00:00"}},
        {"id": "b", "metadata": {"timestamp": "2026-05-08T00:00:00+00:00"}},
        {"id": "c", "metadata": {"timestamp": "2026-05-04T00:00:00+00:00"}},
    ]
    sorted_records = sort_by_recency(records, newest_first=True)
    assert [r["id"] for r in sorted_records] == ["b", "c", "a"]


def test_sort_by_recency_oldest_first():
    records = [
        {"id": "a", "metadata": {"timestamp": "2026-05-01T00:00:00+00:00"}},
        {"id": "b", "metadata": {"timestamp": "2026-05-08T00:00:00+00:00"}},
        {"id": "c", "metadata": {"timestamp": "2026-05-04T00:00:00+00:00"}},
    ]
    sorted_records = sort_by_recency(records, newest_first=False)
    assert [r["id"] for r in sorted_records] == ["a", "c", "b"]


# ---------------------------------------------------------------------------
# AM-X.2 — route-level: AC2 (existing behavior unchanged), AC3 (422), AC18,
# AC19 (persona-path threading), AC20 (filter-only recency-desc default)
# ---------------------------------------------------------------------------


def test_retrieve_route_rejects_naive_created_after(api_client, monkeypatch):
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params={"user_id": "user-123", "created_after": "2026-05-08T00:00:00"},
    )
    assert response.status_code == 422
    assert NAIVE_DATETIME_MSG in response.json()["detail"]


def test_retrieve_route_rejects_metadata_filter_on_system_key(api_client, monkeypatch):
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params=[
            ("user_id", "user-123"),
            ("metadata_filter", "user_id:other"),
        ],
    )
    assert response.status_code == 422


def test_retrieve_route_rejects_metadata_filter_on_internal_key(
    api_client, monkeypatch
):
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params=[
            ("user_id", "user-123"),
            ("metadata_filter", "importance:0.5"),
        ],
    )
    assert response.status_code == 422


def test_retrieve_route_rejects_inverted_created_range(api_client, monkeypatch):
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)
    response = api_client.get(
        "/v1/retrieve",
        params={
            "user_id": "user-123",
            "created_after": "2026-05-09T00:00:00Z",
            "created_before": "2026-05-08T00:00:00Z",
        },
    )
    assert response.status_code == 422


def test_retrieve_route_threads_created_after_through_persona_copilot(
    api_client, monkeypatch
):
    """AC19: the new query params reach `_persona_copilot.retrieve`.

    This is the audit's #1 finding — without threading, half the consumers
    silently drop every X.2 filter. Capture the kwargs and assert
    ``metadata_filters`` carries the UTC-normalized ``created_after``.
    """
    captured: dict = {}

    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr("src.app._persona_copilot.retrieve", fake_retrieve)
    monkeypatch.setattr("src.app.search_memories", lambda **_: ([], 0))
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params={
            "user_id": "user-123",
            "created_after": "2026-05-08T00:00:00-07:00",  # -> 07:00:00 UTC
        },
    )
    assert response.status_code == 200, response.text
    metadata_filters = captured.get("metadata_filters") or {}
    assert metadata_filters.get("created_after") == "2026-05-08T07:00:00+00:00"


def test_retrieve_route_filter_only_returns_recency_desc(api_client, monkeypatch):
    """AC20: filter-only ?layer=semantic returns recency-desc (newest first).

    Previously, this case received Chroma's arbitrary `get` order. Now it
    auto-applies the recency sort.
    """
    persona_result = PersonaRetrievalResult(
        persona="identity",
        items=[
            {
                "id": "old",
                "content": "older",
                "score": 0.0,
                "metadata": {
                    "layer": "semantic",
                    "timestamp": "2026-05-01T00:00:00+00:00",
                    "persona_tags": ["identity"],
                },
            },
            {
                "id": "new",
                "content": "newer",
                "score": 0.0,
                "metadata": {
                    "layer": "semantic",
                    "timestamp": "2026-05-08T00:00:00+00:00",
                    "persona_tags": ["identity"],
                },
            },
            {
                "id": "mid",
                "content": "middle",
                "score": 0.0,
                "metadata": {
                    "layer": "semantic",
                    "timestamp": "2026-05-04T00:00:00+00:00",
                    "persona_tags": ["identity"],
                },
            },
        ],
        weight_profile={"semantic": 0.5},
        source="hybrid",
    )
    monkeypatch.setattr(
        "src.app._persona_copilot.retrieve", lambda **_: {"identity": persona_result}
    )
    monkeypatch.setattr("src.app.search_memories", lambda **_: ([], 0))
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params={"user_id": "user-123", "layer": "semantic"},
    )
    assert response.status_code == 200, response.text
    ids = [r["id"] for r in response.json()["results"]]
    assert ids == ["new", "mid", "old"]


def test_retrieve_route_filter_only_kind_threads_through(api_client, monkeypatch):
    """AC1+AC19: `kind=` reaches the persona path's metadata_filters dict."""
    captured: dict = {}

    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr("src.app._persona_copilot.retrieve", fake_retrieve)
    monkeypatch.setattr("src.app.search_memories", lambda **_: ([], 0))
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params={"user_id": "user-123", "kind": "meals_today"},
    )
    assert response.status_code == 200, response.text
    assert (captured.get("metadata_filters") or {}).get("kind") == "meals_today"


def test_retrieve_route_metadata_filter_threads_through(api_client, monkeypatch):
    """AC1+AC19: `metadata_filter=tags:dinner` reaches the persona path."""
    captured: dict = {}

    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr("src.app._persona_copilot.retrieve", fake_retrieve)
    monkeypatch.setattr("src.app.search_memories", lambda **_: ([], 0))
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params=[
            ("user_id", "user-123"),
            ("metadata_filter", "tags:dinner"),
        ],
    )
    assert response.status_code == 200, response.text
    mf = (captured.get("metadata_filters") or {}).get("metadata_filter") or {}
    assert mf == {"tags": ["dinner"]}


# ---------------------------------------------------------------------------
# AM-X.2 — AC19 / AC24: persona-path E2E. The PersonaRetrievalAgent applies
# the X.2 filters in-Python to hybrid_results so the chat-runtime / summary-
# manager / orchestrator code path honors them.
# ---------------------------------------------------------------------------


def test_persona_agent_applies_x2_filters_to_hybrid_results(monkeypatch):
    """AC19: PersonaRetrievalAgent filters hybrid results by created_after.

    Without this, callers of `_persona_copilot.retrieve` receive memories
    from outside the requested time window — the audit's #1 risk.
    """
    from src.services.persona_retrieval import PersonaRetrievalAgent

    class _FakeHybridResult:
        def __init__(self, memory_id, timestamp, content):
            self.memory_id = memory_id
            self.content = content
            self.relevance_score = 0.9
            self.metadata = {
                "timestamp": timestamp,
                "persona_tags": ["identity"],
            }

    class _FakeHybridService:
        def retrieve_memories(self, _query):
            return [
                _FakeHybridResult("old", "2026-04-01T00:00:00+00:00", "older content"),
                _FakeHybridResult("new", "2026-05-08T00:00:00+00:00", "newer content"),
            ]

    agent = PersonaRetrievalAgent("identity", hybrid_service=_FakeHybridService())
    result = agent.retrieve(
        user_id="u-1",
        query="anything",
        limit=10,
        metadata_filters={"created_after": "2026-05-01T00:00:00+00:00"},
    )
    ids = [item["id"] for item in result.items]
    assert ids == ["new"]
    assert "old" not in ids


def test_persona_agent_excludes_immortals_from_expires_filter(monkeypatch):
    """AC21: expires_* filter excludes records without ttl_epoch."""
    from src.services.persona_retrieval import PersonaRetrievalAgent

    class _Result:
        def __init__(self, memory_id, ttl_epoch):
            self.memory_id = memory_id
            self.content = "x"
            self.relevance_score = 0.9
            self.metadata = {
                "timestamp": "2026-05-08T00:00:00+00:00",
                "persona_tags": ["identity"],
            }
            if ttl_epoch is not None:
                self.metadata["ttl_epoch"] = ttl_epoch

    class _FakeHybridService:
        def retrieve_memories(self, _query):
            return [_Result("immortal", None), _Result("mortal", 1800000000)]

    agent = PersonaRetrievalAgent("identity", hybrid_service=_FakeHybridService())
    result = agent.retrieve(
        user_id="u-1",
        query="",
        limit=10,
        metadata_filters={"expires_after": 1700000000},
    )
    ids = [item["id"] for item in result.items]
    assert ids == ["mortal"]


def test_retrieve_route_existing_callers_unchanged(api_client, monkeypatch):
    """AC2: existing callers (no new filters, no new params) see no change."""
    persona_result = PersonaRetrievalResult(
        persona="identity",
        items=[
            {
                "id": "mem-1",
                "content": "Hello",
                "score": 0.9,
                "metadata": {
                    "layer": "semantic",
                    "type": "explicit",
                    "persona_tags": ["identity"],
                },
            }
        ],
        weight_profile={"semantic": 0.5},
        source="hybrid",
    )
    monkeypatch.setattr(
        "src.app._persona_copilot.retrieve", lambda **_: {"identity": persona_result}
    )
    monkeypatch.setattr("src.services.tracing.start_trace", lambda **_: None)

    response = api_client.get(
        "/v1/retrieve",
        params={"user_id": "user-123", "query": "hello"},
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 1


# ---------------------------------------------------------------------------
# Cross-tz no-match regression (live-curl bug found 2026-05-08)
#
# The original AM-X.2 design assumed Chroma's $gte/$lt operators worked on
# string fields (ISO timestamps). Live-curl proved otherwise: any `where`
# document carrying ``timestamp: {"$gte": "...iso..."}`` was rejected with
# ``InvalidArgumentError: Invalid where clause`` and a 500 leaked from the
# persona-retrieval fallback path. The fix moves timestamp filtering to
# Python (see `_filter_records_by_timestamp`) and these tests pin the
# behavior so a future story can't silently re-introduce the regression.
# ---------------------------------------------------------------------------


def test_persona_agent_negative_offset_no_match_does_not_500(monkeypatch):
    """Direct unit test on PersonaRetrievalAgent: a negative-offset
    `created_after` that yields no matches must NOT raise.

    This is the live-curl regression: hybrid returned [], then the
    persona-fallback called search_memories which built a where-clause that
    Chroma rejected. With the fix, the where-clause omits ``timestamp``
    and the post-filter applies the predicate; an empty result is fine.

    Directly drives ``PersonaRetrievalAgent.retrieve`` (no FastAPI),
    avoiding the redis-init issue with constructing PersonaCoPilot in tests.
    """
    from src.services.persona_retrieval import PersonaRetrievalAgent

    class _EmptyHybrid:
        def retrieve_memories(self, _query):
            return []

    captured: dict = {}

    def fake_search_memories(*, user_id, query, filters, limit, offset):
        captured.update(filters or {})
        return [], 0

    monkeypatch.setattr(
        "src.services.persona_retrieval.search_memories", fake_search_memories
    )

    agent = PersonaRetrievalAgent("identity", hybrid_service=_EmptyHybrid())
    # The cross-tz value the route would have normalized:
    # 2026-05-08T22:59:20-07:00 -> 2026-05-09T05:59:20+00:00 (future UTC).
    result = agent.retrieve(
        user_id="u-1",
        query="",  # filter-only path
        limit=10,
        metadata_filters={"created_after": "2026-05-09T05:59:20+00:00"},
    )
    # No raise == bug fix is real. Empty result expected.
    assert result.items == []
    # The fallback should have received the filter unchanged so the
    # where-clause builder can decide what to push into Chroma.
    assert captured.get("created_after") == "2026-05-09T05:59:20+00:00"


def test_build_where_clause_drops_created_filters_to_avoid_chroma_rejection():
    """Direct unit assertion: even when both created_* are passed, the
    resulting where-doc must NOT contain a ``timestamp`` key. The Python
    post-filter (``_filter_records_by_timestamp``) is responsible for
    enforcing the predicate.
    """
    from src.services.retrieval import _build_where_clause

    clause = _build_where_clause(
        "u-1",
        layer="semantic",
        created_after="2026-05-08T07:00:00+00:00",
        created_before="2026-05-09T07:00:00+00:00",
        expires_after=1700000000,  # int, allowed in where
    )
    # The resulting clause must include user_id, layer, ttl_epoch — NOT
    # timestamp. Chroma 1.x rejects the latter.
    serialized = repr(clause)
    assert "timestamp" not in serialized
    assert "user_id" in serialized
    assert "ttl_epoch" in serialized


def test_filter_records_by_timestamp_applies_predicate():
    """The Python-side timestamp filter mirrors the predicate the
    where-clause builder used to emit. Verify both bounds and inclusivity.
    """
    from src.services.retrieval import _filter_records_by_timestamp

    records = [
        {"id": "a", "metadata": {"timestamp": "2026-05-07T00:00:00+00:00"}},
        {"id": "b", "metadata": {"timestamp": "2026-05-08T00:00:00+00:00"}},
        {"id": "c", "metadata": {"timestamp": "2026-05-09T00:00:00+00:00"}},
        {"id": "d", "metadata": {}},  # no timestamp -> excluded by any range
    ]
    # >= "2026-05-08" AND < "2026-05-09" -> only "b".
    out = _filter_records_by_timestamp(
        records,
        created_after="2026-05-08T00:00:00+00:00",
        created_before="2026-05-09T00:00:00+00:00",
    )
    assert [r["id"] for r in out] == ["b"]

    # Only created_after -> "b" and "c".
    out2 = _filter_records_by_timestamp(
        records, created_after="2026-05-08T00:00:00+00:00"
    )
    assert [r["id"] for r in out2] == ["b", "c"]

    # Neither -> identity.
    out3 = _filter_records_by_timestamp(records)
    assert out3 == records
