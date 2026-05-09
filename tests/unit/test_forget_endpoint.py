"""Unit tests for AM-X.3: `POST /v1/forget` real wiring.

Covers:
- AC7: real counts are returned and the endpoint no longer lies about
  `jobs_enqueued` (the response is `chroma_deleted`/`timescale_deleted`/
  `dry_run`/`jobs_requested`).
- AC8: `dry_run=True` reports the count it WOULD delete via a `where`-only
  `get` and does NOT call `col.delete` or `ttl_cleanup_timescale`.
- AC15: dry-run does not delete (assertion on zero deletes performed).
- AC16: `body.jobs` is echoed back as `jobs_requested` on the response.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_forget_real_counts(api_client, monkeypatch):
    """AC7: `/v1/forget` returns real counts from `ttl_cleanup` and
    `ttl_cleanup_timescale`, not the legacy `jobs_enqueued` stub."""
    # Patch the late-imported sweep targets via the source module.
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup", lambda grace_seconds=0: 11
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: 4,
    )

    resp = api_client.post("/v1/forget", json={"scopes": ["short-term"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chroma_deleted"] == 11
    assert body["timescale_deleted"] == 4
    assert body["dry_run"] is False
    assert body["jobs_requested"] == []
    # The legacy stub field must not leak through the new response shape.
    assert "jobs_enqueued" not in body


def test_forget_echoes_jobs_as_jobs_requested(api_client, monkeypatch):
    """AC16: `body.jobs` is echoed back on the response under
    `jobs_requested` for caller debuggability — even though the endpoint
    currently ignores the field."""
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup", lambda grace_seconds=0: 0
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: 0,
    )

    resp = api_client.post(
        "/v1/forget",
        json={"jobs": ["ttl_cleanup", "compaction"], "scopes": []},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs_requested"] == ["ttl_cleanup", "compaction"]


def test_forget_dry_run_does_not_delete(api_client, monkeypatch):
    """AC8/AC15: with `dry_run=True`, the endpoint reports the count it
    WOULD delete (via a `where`-only `get`) and does NOT call `col.delete`
    or `ttl_cleanup_timescale`."""
    fake_col = MagicMock()
    fake_col.get.return_value = {
        "ids": ["m1", "m2", "m3"],
        "metadatas": [
            {"ttl_epoch": 100},
            {"ttl_epoch": 200},
            {"ttl_epoch": 300},
        ],
    }
    fake_col.delete.return_value = None

    monkeypatch.setattr("src.services.compaction_ops._get_collection", lambda: fake_col)

    timescale_calls = []

    def _ts(grace_seconds=0):
        timescale_calls.append(grace_seconds)
        return 99

    monkeypatch.setattr("src.services.compaction_ops.ttl_cleanup_timescale", _ts)
    # If something bypasses dry_run, ttl_cleanup would call delete on the
    # fake collection — guard rail.
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup",
        lambda grace_seconds=0: pytest.fail(
            "ttl_cleanup must NOT run when dry_run=True"
        ),
    )

    resp = api_client.post("/v1/forget", json={"dry_run": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    # AC8: returns the would-delete count.
    assert body["chroma_deleted"] == 3
    # Timescale dry-run is out of scope — we report 0 and do not call it.
    assert body["timescale_deleted"] == 0
    assert timescale_calls == []
    # AC15: hard assertion that no Chroma delete fired.
    fake_col.delete.assert_not_called()


def test_forget_response_schema_is_stable(api_client, monkeypatch):
    """AC7: the response has the four documented keys and nothing else
    surprising — guards against a future regression that would re-add
    the lying `jobs_enqueued` field."""
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup", lambda grace_seconds=0: 0
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: 0,
    )

    resp = api_client.post("/v1/forget", json={})
    body = resp.json()
    assert set(body.keys()) == {
        "chroma_deleted",
        "timescale_deleted",
        "dry_run",
        "jobs_requested",
    }
