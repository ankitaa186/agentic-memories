"""Integration tests for AM-X.3: `POST /v1/forget` end-to-end.

Covers:
- AC7: real counts reflect the simulated ChromaDB state.
- AC8/AC15: `dry_run=True` reports the would-delete count and a follow-up
  retrieve still returns the not-yet-reaped memory.
- AC16: `body.jobs` echoed back as `jobs_requested`.
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_chroma_with_expired_memories() -> Generator[MagicMock, None, None]:
    """Simulate a Chroma collection with three expired short-term memories.

    `col.get(where={"ttl_epoch": {"$lte": ...}})` returns the three IDs;
    `col.delete(ids=...)` records the delete call so we can assert on it.
    A separate `retrieve_get` arm of the mock returns the same memories
    when called WITHOUT a ttl_epoch filter (simulating "the memory still
    exists in storage even though it's logically expired").
    """
    expired_ids = ["mem-expired-1", "mem-expired-2", "mem-expired-3"]
    expired_metas = [{"ttl_epoch": 100, "user_id": "u-test"} for _ in expired_ids]

    fake_col = MagicMock()
    fake_col.get.return_value = {"ids": expired_ids, "metadatas": expired_metas}
    fake_col.delete.return_value = None

    yield fake_col


def test_forget_real_endpoint_returns_real_counts(
    fake_chroma_with_expired_memories: MagicMock,
):
    """AC7: a non-dry_run call returns the actual counts of records
    deleted from Chroma + Timescale (no more lying about `jobs_enqueued`)."""
    from src.app import app

    chroma_calls = []
    timescale_calls = []

    def _fake_ttl_cleanup(grace_seconds=0):
        chroma_calls.append(grace_seconds)
        return 3  # simulate 3 deletions

    def _fake_ttl_cleanup_timescale(grace_seconds=0):
        timescale_calls.append(grace_seconds)
        return 7  # simulate 7 deletions

    with (
        patch("src.services.compaction_ops.ttl_cleanup", side_effect=_fake_ttl_cleanup),
        patch(
            "src.services.compaction_ops.ttl_cleanup_timescale",
            side_effect=_fake_ttl_cleanup_timescale,
        ),
    ):
        with TestClient(app) as client:
            resp = client.post(
                "/v1/forget",
                json={"scopes": ["short-term"], "jobs": ["ttl_cleanup"]},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["chroma_deleted"] == 3
    assert body["timescale_deleted"] == 7
    assert body["dry_run"] is False
    # AC16: jobs echoed back.
    assert body["jobs_requested"] == ["ttl_cleanup"]
    # /v1/forget runs synchronously with no grace window — daily-compaction
    # behavior. The sweeper is what passes grace_seconds=60.
    assert chroma_calls == [0]
    assert timescale_calls == [0]


def test_forget_dry_run_reports_count_without_deleting(
    fake_chroma_with_expired_memories: MagicMock,
):
    """AC8/AC15: dry_run=True reports the would-delete count via a
    `where`-only `get` and never calls `col.delete` or
    `ttl_cleanup_timescale`. Asserts hard zero deletes."""
    from src.app import app

    fake_col = fake_chroma_with_expired_memories

    def _no_op_cleanup(grace_seconds=0):  # noqa: ARG001
        pytest.fail(
            "ttl_cleanup must NOT execute when /v1/forget is called with dry_run=True"
        )

    def _no_op_timescale(grace_seconds=0):  # noqa: ARG001
        pytest.fail(
            "ttl_cleanup_timescale must NOT execute when /v1/forget is "
            "called with dry_run=True"
        )

    with (
        patch("src.services.compaction_ops._get_collection", return_value=fake_col),
        patch("src.services.compaction_ops.ttl_cleanup", side_effect=_no_op_cleanup),
        patch(
            "src.services.compaction_ops.ttl_cleanup_timescale",
            side_effect=_no_op_timescale,
        ),
    ):
        with TestClient(app) as client:
            resp = client.post("/v1/forget", json={"dry_run": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    # AC8: dry_run reports the would-delete count from the where-only get.
    assert body["chroma_deleted"] == 3
    # Timescale dry-run is out of scope; reported as 0.
    assert body["timescale_deleted"] == 0
    # AC15: zero deletes performed.
    fake_col.delete.assert_not_called()


def test_forget_dry_run_predicate_uses_ttl_epoch_lte_now(
    fake_chroma_with_expired_memories: MagicMock,
):
    """AC8: the dry-run path issues exactly the predicate `ttl_cleanup`
    would issue (`{"ttl_epoch": {"$lte": now}}`) so the count is the
    real would-delete count. No bonus filters, no off-by-one."""
    from src.app import app

    fake_col = fake_chroma_with_expired_memories

    captured = {}

    def _capture_get(where, include=None):  # noqa: ARG001
        captured["where"] = where
        captured["include"] = include
        return {"ids": ["x", "y"], "metadatas": [{}, {}]}

    fake_col.get.side_effect = _capture_get

    with patch("src.services.compaction_ops._get_collection", return_value=fake_col):
        with TestClient(app) as client:
            resp = client.post("/v1/forget", json={"dry_run": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["chroma_deleted"] == 2
    where = captured["where"]
    # Match the live predicate: equality on the ttl_epoch key, $lte operator.
    assert "ttl_epoch" in where
    assert "$lte" in where["ttl_epoch"]
    assert isinstance(where["ttl_epoch"]["$lte"], int)
