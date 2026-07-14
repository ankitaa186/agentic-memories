"""Unit tests for Story H-1: PG connection-leak hotfix (incident 2026-07-12).

Postgres saturated at max_connections=100 for ~24h because pooled connections
were leaked on failure/cleanup paths. These tests pin the three release fixes:

- Test A (Fix 2): `release_timescale_conn` always returns the connection to the
  pool even when `conn.rollback()` raises on a broken connection. Fails against
  the pre-fix code, where rollback and putconn shared one try/except.
- Test B (Fix 1): `_temporal_retrieval` releases the pooled connection exactly
  once on both the happy and error paths.
- Test C (Fix 3): `_store_in_timescale` releases the pooled connection exactly
  once on both the happy and error paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Test A (Fix 2): release_timescale_conn always putconn, even if rollback raises
# =============================================================================


def test_release_still_putconn_when_rollback_raises(monkeypatch):
    """A broken connection whose rollback() raises must STILL be returned to the
    pool. Pre-fix, rollback and putconn shared one try/except, so a raising
    rollback skipped putconn and leaked the connection (incident 2026-07-12).
    """
    from src.dependencies import timescale

    mock_pool = MagicMock()
    monkeypatch.setattr(timescale, "get_timescale_pool", lambda: mock_pool)

    conn = MagicMock()
    conn.rollback.side_effect = Exception("connection already closed")

    timescale.release_timescale_conn(conn)

    conn.rollback.assert_called_once()
    mock_pool.putconn.assert_called_once_with(conn)


# =============================================================================
# Test B (Fix 1): _temporal_retrieval releases conn once on happy + error paths
# =============================================================================


def _make_temporal_service():
    """Build a HybridRetrievalService without running __init__ (which would
    construct Chroma + sub-service clients). `_temporal_retrieval` only relies
    on `self._calculate_recency_score`, which is stateless."""
    from src.services.hybrid_retrieval import HybridRetrievalService

    return object.__new__(HybridRetrievalService)


def _temporal_query():
    from src.services.hybrid_retrieval import RetrievalQuery

    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 12, tzinfo=timezone.utc)
    return RetrievalQuery(user_id="u1", time_range=(start, end))


def test_temporal_retrieval_releases_conn_on_happy_path(monkeypatch):
    from src.services import hybrid_retrieval

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchall.return_value = []

    release = MagicMock()
    monkeypatch.setattr(hybrid_retrieval, "get_timescale_conn", lambda: conn)
    monkeypatch.setattr(hybrid_retrieval, "release_timescale_conn", release)

    service = _make_temporal_service()
    results = service._temporal_retrieval(_temporal_query())

    assert results == []
    conn.commit.assert_called_once()
    release.assert_called_once_with(conn)


def test_temporal_retrieval_releases_conn_on_error_path(monkeypatch):
    from src.services import hybrid_retrieval

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.execute.side_effect = Exception("query boom")

    release = MagicMock()
    monkeypatch.setattr(hybrid_retrieval, "get_timescale_conn", lambda: conn)
    monkeypatch.setattr(hybrid_retrieval, "release_timescale_conn", release)

    service = _make_temporal_service()
    # Error is swallowed and logged; the method returns [] (no propagation).
    results = service._temporal_retrieval(_temporal_query())

    assert results == []
    release.assert_called_once_with(conn)


# =============================================================================
# Test C (Fix 3): _store_in_timescale releases conn once on happy + error paths
# =============================================================================


def _make_episodic_service():
    """Build an EpisodicMemoryService without running __init__ (which would
    construct a Chroma client). `_store_in_timescale` uses no instance state."""
    from src.services.episodic_memory import EpisodicMemoryService

    return object.__new__(EpisodicMemoryService)


def _episodic_memory():
    from src.services.episodic_memory import EpisodicMemory

    return EpisodicMemory(
        id="mem_1",
        user_id="u1",
        event_timestamp=datetime(2026, 7, 12, tzinfo=timezone.utc),
        event_type="note",
        content="hello",
    )


def test_store_in_timescale_releases_conn_on_happy_path(monkeypatch):
    from src.services import episodic_memory

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    release = MagicMock()
    monkeypatch.setattr(episodic_memory, "get_timescale_conn", lambda: conn)
    monkeypatch.setattr(episodic_memory, "release_timescale_conn", release)

    service = _make_episodic_service()
    service._store_in_timescale(_episodic_memory())

    conn.commit.assert_called_once()
    release.assert_called_once_with(conn)


def test_store_in_timescale_releases_conn_on_error_path(monkeypatch):
    from src.services import episodic_memory

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.execute.side_effect = Exception("insert boom")

    release = MagicMock()
    monkeypatch.setattr(episodic_memory, "get_timescale_conn", lambda: conn)
    monkeypatch.setattr(episodic_memory, "release_timescale_conn", release)

    service = _make_episodic_service()
    # _store_in_timescale re-raises so store_memory can report the failure.
    with pytest.raises(Exception, match="insert boom"):
        service._store_in_timescale(_episodic_memory())

    conn.rollback.assert_called_once()
    release.assert_called_once_with(conn)
