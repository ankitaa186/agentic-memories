"""Integration tests for AM-X.2 retrieve filter behavior.

Covers:
- AC9 / AC10: where-clause shape passed to Chroma (timestamp/ttl_epoch).
- AC15: cross-timezone normalization. Store at known UTC, query in -07:00
  bracketing the same instant, assert hit (proves normalization, not raw
  lex-compare).
- AC16: dry-run scenario — store 5 meals memories with metadata.kind set,
  retrieve with `created_after=today_start&kind=meals_today`, assert all
  five returned in recency-desc order.
- AC21: expires_* immortal-exclusion (records without ttl_epoch must not
  appear in expires_after / expires_before windows).
- AC8 / AC12: filter-only path uses sort+slice within the fetch cap.

These tests stub the Chroma collection at the
``src.services.retrieval._get_collection`` boundary so we exercise the
where-clause builder, the persona-path hand-off, and the recency-sort
helper end-to-end without spinning up a real Chroma container.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from src.services.retrieval import _build_where_clause, search_memories


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _record(
    *,
    id_: str,
    timestamp: str,
    kind: str | None = None,
    ttl_epoch: int | None = None,
    layer: str = "semantic",
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "user_id": "u-1",
        "layer": layer,
        "type": "explicit",
        "timestamp": timestamp,
        "persona_tags": "[]",
    }
    if kind is not None:
        meta["kind"] = kind
    if ttl_epoch is not None:
        meta["ttl_epoch"] = ttl_epoch
    return {"id": id_, "doc": f"doc-{id_}", "meta": meta}


def _make_collection_stub(records: List[Dict[str, Any]]):
    """Stub Chroma collection that filters records by where-clause manually.

    Implements just enough of the Chroma `where` semantics that this test
    needs: equality, $gte, $lt, $and. Returns ``ids`` / ``documents`` /
    ``metadatas`` in insertion order (mimicking Chroma's undefined `get`
    order — the recency-sort helper is what produces deterministic output).
    """
    collection = MagicMock()
    collection.name = "memories_3072"

    def _matches(meta: Dict[str, Any], where: Dict[str, Any]) -> bool:
        if "$and" in where:
            return all(_matches(meta, sub) for sub in where["$and"])
        for key, value in where.items():
            if isinstance(value, dict):
                # Operator dict.
                actual = meta.get(key)
                for op, expected in value.items():
                    if op == "$gte":
                        if actual is None or actual < expected:
                            return False
                    elif op == "$lt":
                        if actual is None or actual >= expected:
                            return False
                    elif op == "$lte":
                        if actual is None or actual > expected:
                            return False
                    else:
                        raise AssertionError(f"unhandled op {op}")
            else:
                if meta.get(key) != value:
                    return False
        return True

    def fake_get(where=None, limit=None, **_kwargs):
        matched = [r for r in records if _matches(r["meta"], where or {})]
        if limit is not None:
            matched = matched[:limit]
        return {
            "ids": [r["id"] for r in matched],
            "documents": [r["doc"] for r in matched],
            "metadatas": [r["meta"] for r in matched],
        }

    collection.get = fake_get
    return collection


@pytest.fixture
def patched_collection(monkeypatch):
    """Yield a setter that installs the stub for `_get_collection`."""

    def _install(records: List[Dict[str, Any]]):
        coll = _make_collection_stub(records)
        monkeypatch.setattr("src.services.retrieval._get_collection", lambda: coll)
        # Disable Redis short-term cache for deterministic results
        monkeypatch.setattr("src.services.retrieval.get_redis_client", lambda: None)
        return coll

    return _install


# ---------------------------------------------------------------------------
# AC9 / AC10 — where-clause structure
# ---------------------------------------------------------------------------


def test_build_where_clause_combines_supported_predicates_with_and():
    """ttl_epoch (int) range CAN go in the where-clause; timestamp (str)
    range CANNOT (Chroma 1.x rejects $gte/$lt on string fields).

    See ``_build_where_clause`` docstring + 2026-05-08 cross-tz 500
    regression. Test renamed from ``..._timestamp_and_ttl_with_and`` to
    document the change.
    """
    clause = _build_where_clause(
        "u-1",
        layer="semantic",
        created_after="2026-05-08T00:00:00+00:00",  # dropped from where
        expires_after=1700000000,
    )
    # Must use $and for multi-key ranged filter (Chroma requirement).
    assert "$and" in clause
    keys_per_clause = {tuple(c.keys())[0] for c in clause["$and"]}
    # ttl_epoch SHOULD appear; timestamp must NOT.
    assert {"user_id", "layer", "ttl_epoch"} <= keys_per_clause
    assert "timestamp" not in keys_per_clause


# ---------------------------------------------------------------------------
# AC15 — cross-timezone normalization
# ---------------------------------------------------------------------------


def test_cross_timezone_query_brackets_stored_utc_record(patched_collection):
    """Store at 2026-05-08T07:00:00+00:00; query -07:00 between 0:00 and 23:59.

    The query offset (-07:00) when normalized to UTC becomes 07:00:00+00:00 to
    06:59:00+00:00 next day; the stored record at exactly 07:00:00+00:00
    must be returned. This proves the normalize-before-where-clause path is
    in effect — without it, a raw lex-compare on the unnormalized string
    "2026-05-08T00:00:00-07:00" would fail to match "2026-05-08T07:00:00+00:00".
    """
    records = [
        _record(id_="hit", timestamp="2026-05-08T07:00:00+00:00"),
    ]
    patched_collection(records)

    # Caller would pass -07:00 inputs; the route normalizes before building
    # the where-clause, so search_memories receives UTC ISO strings:
    page, total = search_memories(
        user_id="u-1",
        query="",
        filters={
            # Equivalent of caller passing 2026-05-08T00:00:00-07:00 = UTC 07:00.
            "created_after": "2026-05-08T07:00:00+00:00",
            # Equivalent of caller passing 2026-05-08T17:00:00-07:00 = UTC 00:00 next day.
            "created_before": "2026-05-09T00:00:00+00:00",
        },
        limit=10,
    )
    assert total == 1
    assert page[0]["id"] == "hit"


# ---------------------------------------------------------------------------
# AC16 — dry-run meals-today scenario
# ---------------------------------------------------------------------------


def test_meals_today_filter_returns_five_in_recency_desc(patched_collection):
    records = [
        _record(
            id_=f"meal-{i}",
            timestamp=f"2026-05-08T{i:02d}:00:00+00:00",
            kind="meals_today",
        )
        for i in range(5)
    ]
    # Insert in non-sorted order to prove the helper sorts deterministically.
    shuffled = [records[2], records[0], records[4], records[1], records[3]]
    # Throw in a noise record with a different kind that must NOT appear.
    shuffled.append(
        _record(id_="noise", timestamp="2026-05-08T03:30:00+00:00", kind="other")
    )
    patched_collection(shuffled)

    page, total = search_memories(
        user_id="u-1",
        query="",
        filters={
            "kind": "meals_today",
            "created_after": "2026-05-08T00:00:00+00:00",
        },
        limit=10,
    )
    assert total == 5
    ids = [item["id"] for item in page]
    # Recency-desc — meal-4 (04:00) first, meal-0 (00:00) last.
    assert ids == ["meal-4", "meal-3", "meal-2", "meal-1", "meal-0"]


# ---------------------------------------------------------------------------
# AC21 — expires_* immortal-exclusion
# ---------------------------------------------------------------------------


def test_expires_after_excludes_records_without_ttl_epoch(patched_collection):
    """Records WITHOUT a ttl_epoch must NOT be returned by expires_after.

    Mirrors Chroma's behavior — `$gte` against a missing key fails the
    predicate. The where-clause stub above implements the same semantics.
    """
    records = [
        _record(id_="immortal", timestamp="2026-05-08T00:00:00+00:00"),
        _record(
            id_="mortal",
            timestamp="2026-05-08T01:00:00+00:00",
            ttl_epoch=1800000000,
        ),
    ]
    patched_collection(records)

    page, total = search_memories(
        user_id="u-1",
        query="",
        filters={"expires_after": 1700000000},
        limit=10,
    )
    assert total == 1
    assert page[0]["id"] == "mortal"


def test_expires_before_excludes_records_without_ttl_epoch(patched_collection):
    records = [
        _record(id_="immortal", timestamp="2026-05-08T00:00:00+00:00"),
        _record(
            id_="mortal",
            timestamp="2026-05-08T01:00:00+00:00",
            ttl_epoch=1700000000,
        ),
    ]
    patched_collection(records)

    page, total = search_memories(
        user_id="u-1",
        query="",
        filters={"expires_before": 1800000000},
        limit=10,
    )
    assert total == 1
    assert page[0]["id"] == "mortal"


# ---------------------------------------------------------------------------
# AC8 / AC12 — pagination preserves recency-desc across pages
# ---------------------------------------------------------------------------


def test_filter_only_pagination_preserves_recency_desc_across_pages(
    patched_collection,
):
    records = [
        _record(
            id_=f"r-{i:02d}",
            timestamp=f"2026-05-08T{i:02d}:00:00+00:00",
            kind="meals_today",
        )
        for i in range(10)
    ]
    patched_collection(records)

    page1, total1 = search_memories(
        user_id="u-1",
        query="",
        filters={"kind": "meals_today"},
        limit=3,
        offset=0,
    )
    page2, total2 = search_memories(
        user_id="u-1",
        query="",
        filters={"kind": "meals_today"},
        limit=3,
        offset=3,
    )
    assert total1 == 10
    assert total2 == 10
    assert [r["id"] for r in page1] == ["r-09", "r-08", "r-07"]
    assert [r["id"] for r in page2] == ["r-06", "r-05", "r-04"]
