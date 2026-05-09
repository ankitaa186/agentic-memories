"""Unit tests for AM-X.3: fast TTL eviction sweeper.

Covers:
- AC5/AC9: 60-second grace window in `ttl_cleanup` (Chroma) and
  `ttl_cleanup_timescale` (Postgres). Default `grace_seconds=0` preserves
  the existing daily-compaction behavior at `compaction_graph.py:513` and
  `:521`.
- AC1/AC9/AC12: scheduler registers a `ttl_sweep` interval job with the
  explicit `coalesce/max_instances/misfire_grace_time` kwargs.
- AC13: redis lock is acquired before the sweep runs and released after.
- AC14: `_standard_collection_name` is memoized.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


# =============================================================================
# AC5/AC9: ttl_cleanup grace window (Chroma)
# =============================================================================


def _build_chroma_collection_capture():
    """Returns (collection, captured) where `captured["where"]` records the
    most recent `where` arg passed to `col.get`. The collection returns no
    ids by default so `delete` is never invoked.
    """
    captured: dict = {}
    col = MagicMock()

    def _get(where, include=None):  # noqa: ARG001
        captured["where"] = where
        return {"ids": [], "metadatas": []}

    col.get.side_effect = _get
    col.delete.return_value = None
    return col, captured


def test_ttl_cleanup_default_grace_zero_preserves_daily_compaction(monkeypatch):
    """AC9: default `grace_seconds=0` matches the legacy predicate at
    `compaction_graph.py:513` so daily compaction is unchanged."""
    from src.services import compaction_ops

    col, captured = _build_chroma_collection_capture()
    monkeypatch.setattr(compaction_ops, "_get_collection", lambda: col)

    fixed_now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    expected = int(fixed_now.timestamp())
    with patch("src.services.compaction_ops.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = compaction_ops.ttl_cleanup()  # no args == default 0

    assert result == 0
    assert captured["where"] == {"ttl_epoch": {"$lte": expected}}


def test_ttl_cleanup_grace_60_subtracts_seconds_from_now(monkeypatch):
    """AC5: sweeper passes `grace_seconds=60` to protect against active-write
    races. The predicate cutoff must be `now - 60`, not `now`."""
    from src.services import compaction_ops

    col, captured = _build_chroma_collection_capture()
    monkeypatch.setattr(compaction_ops, "_get_collection", lambda: col)

    fixed_now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    expected = int(fixed_now.timestamp()) - 60
    with patch("src.services.compaction_ops.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        compaction_ops.ttl_cleanup(grace_seconds=60)

    assert captured["where"] == {"ttl_epoch": {"$lte": expected}}


def test_ttl_cleanup_with_grace_does_not_delete_recent_expiry(monkeypatch):
    """AC9: a memory whose `ttl_epoch` is `now - 30` (within the 60s grace)
    is NOT deleted by the sweeper."""
    from src.services import compaction_ops

    col = MagicMock()
    fixed_now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    now_epoch = int(fixed_now.timestamp())
    recent_ttl = now_epoch - 30  # within grace window

    def _get(where, include=None):  # noqa: ARG001
        cutoff = where["ttl_epoch"]["$lte"]
        # Caller passes grace_seconds=60 → cutoff = now - 60 < recent_ttl
        if recent_ttl <= cutoff:
            return {"ids": ["mem-recent"], "metadatas": [{"ttl_epoch": recent_ttl}]}
        return {"ids": [], "metadatas": []}

    col.get.side_effect = _get
    col.delete.return_value = None
    monkeypatch.setattr(compaction_ops, "_get_collection", lambda: col)

    with patch("src.services.compaction_ops.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        deleted = compaction_ops.ttl_cleanup(grace_seconds=60)

    assert deleted == 0
    col.delete.assert_not_called()


def test_ttl_cleanup_with_grace_deletes_old_expiry(monkeypatch):
    """AC9: a memory whose `ttl_epoch` is `now - 120` (outside the 60s grace)
    IS deleted by the sweeper."""
    from src.services import compaction_ops

    col = MagicMock()
    fixed_now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    now_epoch = int(fixed_now.timestamp())
    old_ttl = now_epoch - 120  # outside grace window

    def _get(where, include=None):  # noqa: ARG001
        cutoff = where["ttl_epoch"]["$lte"]
        if old_ttl <= cutoff:
            return {"ids": ["mem-old"], "metadatas": [{"ttl_epoch": old_ttl}]}
        return {"ids": [], "metadatas": []}

    col.get.side_effect = _get
    col.delete.return_value = None
    monkeypatch.setattr(compaction_ops, "_get_collection", lambda: col)

    with patch("src.services.compaction_ops.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        deleted = compaction_ops.ttl_cleanup(grace_seconds=60)

    assert deleted == 1
    col.delete.assert_called_once_with(ids=["mem-old"])


# =============================================================================
# AC9: ttl_cleanup_timescale grace window (Postgres)
# =============================================================================


class _FakeCursor:
    """Captures the cutoff timestamps each `DELETE` was issued with.

    Two `cur.execute` calls happen in `ttl_cleanup_timescale`:
      1. episodic delete  (params: (score_lt, cutoff_episodic))
      2. emotional delete (params: (cutoff_emotional,))
    """

    def __init__(self):
        self.calls = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        # Pretend nothing was deleted so the test stays focused on the cutoff.
        self.rowcount = 0


class _FakeConn:
    def __init__(self):
        self._cur = _FakeCursor()

    def cursor(self):
        return self._cur

    def commit(self):
        pass

    def rollback(self):
        pass


def test_ttl_cleanup_timescale_default_preserves_daily_cutoff(monkeypatch):
    """AC9: default `grace_seconds=0` keeps the daily-compaction cutoff
    unchanged (`now - age_days`) at `compaction_graph.py:521`."""
    from src.services import compaction_ops

    fake_conn = _FakeConn()
    monkeypatch.setattr(compaction_ops, "get_timescale_conn", lambda: fake_conn)
    monkeypatch.setattr(compaction_ops, "release_timescale_conn", lambda c: None)
    # Force deterministic config (score_lt=0.6, age_days=180).
    monkeypatch.setattr(compaction_ops, "_get_episodic_ttl_config", lambda: (0.6, 180))

    fixed_now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    with patch("src.services.compaction_ops.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        compaction_ops.ttl_cleanup_timescale()  # no args == default 0

    cur = fake_conn._cur
    assert len(cur.calls) == 2
    _, episodic_params = cur.calls[0]
    _, emotional_params = cur.calls[1]
    assert episodic_params[1] == fixed_now - timedelta(days=180)
    assert emotional_params[0] == fixed_now - timedelta(days=60)


def test_ttl_cleanup_timescale_grace_60_pushes_cutoff_back(monkeypatch):
    """AC9: with `grace_seconds=60`, both cutoffs are pushed back by 60s,
    making the predicate strictly more conservative (fewer deletes)."""
    from src.services import compaction_ops

    fake_conn = _FakeConn()
    monkeypatch.setattr(compaction_ops, "get_timescale_conn", lambda: fake_conn)
    monkeypatch.setattr(compaction_ops, "release_timescale_conn", lambda c: None)
    monkeypatch.setattr(compaction_ops, "_get_episodic_ttl_config", lambda: (0.6, 180))

    fixed_now = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
    with patch("src.services.compaction_ops.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        compaction_ops.ttl_cleanup_timescale(grace_seconds=60)

    cur = fake_conn._cur
    _, episodic_params = cur.calls[0]
    _, emotional_params = cur.calls[1]
    assert episodic_params[1] == fixed_now - timedelta(days=180) - timedelta(seconds=60)
    assert emotional_params[0] == fixed_now - timedelta(days=60) - timedelta(seconds=60)


# =============================================================================
# AC1/AC2/AC12: scheduler registration
# =============================================================================


def test_start_scheduler_registers_ttl_sweep_job(monkeypatch):
    """AC1/AC12: with maintenance enabled, `_start_scheduler` registers a
    `ttl_sweep` interval job with explicit `coalesce/max_instances/
    misfire_grace_time` kwargs and the configured cadence."""
    import src.app as app_module

    monkeypatch.setattr(app_module, "_scheduler", None)
    monkeypatch.setattr(app_module, "is_scheduled_maintenance_enabled", lambda: True)
    monkeypatch.setattr(app_module, "get_ttl_sweep_interval_minutes", lambda: 15)

    fake_scheduler = MagicMock()
    monkeypatch.setattr(
        app_module,
        "BackgroundScheduler",
        MagicMock(return_value=fake_scheduler),
    )

    app_module._start_scheduler()

    # add_job called for both daily_compaction and ttl_sweep.
    assert fake_scheduler.add_job.call_count == 2
    call_kwargs_by_id = {
        kwargs.get("id"): kwargs for _, kwargs in fake_scheduler.add_job.call_args_list
    }
    assert "daily_compaction" in call_kwargs_by_id
    assert "ttl_sweep" in call_kwargs_by_id

    sweep_args, sweep_kwargs = fake_scheduler.add_job.call_args_list[1]
    # Positional: (callable, "interval")
    assert sweep_args[0] == app_module._run_ttl_sweep
    assert sweep_args[1] == "interval"
    assert sweep_kwargs["minutes"] == 15
    assert sweep_kwargs["id"] == "ttl_sweep"
    assert sweep_kwargs["coalesce"] is True
    assert sweep_kwargs["max_instances"] == 1
    assert sweep_kwargs["misfire_grace_time"] == 60
    fake_scheduler.start.assert_called_once()


def test_start_scheduler_disabled_does_not_register(monkeypatch):
    """AC6: scheduler is only started when maintenance is enabled. The
    daily compaction continues to run as-is — this is purely additive."""
    import src.app as app_module

    monkeypatch.setattr(app_module, "_scheduler", None)
    monkeypatch.setattr(app_module, "is_scheduled_maintenance_enabled", lambda: False)
    fake_scheduler_cls = MagicMock()
    monkeypatch.setattr(app_module, "BackgroundScheduler", fake_scheduler_cls)

    app_module._start_scheduler()
    fake_scheduler_cls.assert_not_called()


# =============================================================================
# AC13: redis lock around the sweep
# =============================================================================


def test_run_ttl_sweep_acquires_and_releases_lock(monkeypatch):
    """AC13: the sweep wraps its work in a `ttl_sweep_lock` Redis lock."""
    import src.app as app_module

    fake_lock = MagicMock()
    fake_lock.acquire.return_value = True
    fake_redis = MagicMock()
    fake_redis.lock.return_value = fake_lock

    monkeypatch.setattr(app_module, "get_redis_client", lambda: fake_redis)
    # Patch the late-imported sweep targets via the source module.
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup", lambda grace_seconds=0: 7
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: 3,
    )

    app_module._run_ttl_sweep()

    fake_redis.lock.assert_called_once_with(
        "ttl_sweep_lock", timeout=300, blocking=False
    )
    fake_lock.acquire.assert_called_once()
    fake_lock.release.assert_called_once()


def test_run_ttl_sweep_skips_when_lock_held(monkeypatch):
    """AC13: when the lock is held (e.g., daily compaction at 00:00 UTC is
    already running), the sweep skips silently and does NOT call cleanup."""
    import src.app as app_module

    fake_lock = MagicMock()
    fake_lock.acquire.return_value = False  # held by someone else
    fake_redis = MagicMock()
    fake_redis.lock.return_value = fake_lock
    monkeypatch.setattr(app_module, "get_redis_client", lambda: fake_redis)

    chroma_calls = []
    timescale_calls = []
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup",
        lambda grace_seconds=0: chroma_calls.append(grace_seconds) or 0,
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: timescale_calls.append(grace_seconds) or 0,
    )

    app_module._run_ttl_sweep()

    assert chroma_calls == []
    assert timescale_calls == []
    fake_lock.release.assert_not_called()


def test_run_ttl_sweep_passes_grace_60_to_both_cleanups(monkeypatch):
    """AC9: the sweeper passes `grace_seconds=60` to BOTH `ttl_cleanup` and
    `ttl_cleanup_timescale` — Timescale episodic/emotional writes have the
    same active-write race as Chroma."""
    import src.app as app_module

    monkeypatch.setattr(app_module, "get_redis_client", lambda: None)

    chroma_calls = []
    timescale_calls = []
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup",
        lambda grace_seconds=0: chroma_calls.append(grace_seconds) or 0,
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: timescale_calls.append(grace_seconds) or 0,
    )

    app_module._run_ttl_sweep()

    assert chroma_calls == [60]
    assert timescale_calls == [60]


# =============================================================================
# AC14: _standard_collection_name is memoized
# =============================================================================


def test_standard_collection_name_is_memoized(monkeypatch):
    """AC14: only the first call probes `generate_embedding`. Subsequent
    calls return the cached value without re-hitting the embedding API."""
    from src.services import retrieval

    # Reset the lru_cache for a clean run.
    retrieval._standard_collection_name.cache_clear()

    probe_calls = {"n": 0}

    def _probe(_text):
        probe_calls["n"] += 1
        return [0.0] * 3072

    monkeypatch.setattr(retrieval, "generate_embedding", _probe)

    name_a = retrieval._standard_collection_name()
    name_b = retrieval._standard_collection_name()
    name_c = retrieval._standard_collection_name()

    assert name_a == name_b == name_c == "memories_3072"
    assert probe_calls["n"] == 1, (
        "expected lru_cache(maxsize=1) to memoize the dimension probe"
    )

    # Clean up so we don't leak a 3072-dim probe result into other tests.
    retrieval._standard_collection_name.cache_clear()


# =============================================================================
# AC4: sweeper is observable and resilient
# =============================================================================


def test_run_ttl_sweep_logs_attempted_and_counts(monkeypatch, caplog):
    """AC4: a successful sweep emits a `[sched.ttl_sweep]` log line that
    records `attempted`, `chroma_deleted`, `timescale_deleted`."""
    import logging
    import src.app as app_module

    monkeypatch.setattr(app_module, "get_redis_client", lambda: None)
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup", lambda grace_seconds=0: 4
    )
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: 2,
    )

    with caplog.at_level(logging.INFO, logger="agentic_memories.api"):
        app_module._run_ttl_sweep()

    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "[sched.ttl_sweep]" in text
    assert "chroma_deleted=4" in text
    assert "timescale_deleted=2" in text


def test_run_ttl_sweep_chroma_failure_still_runs_timescale(monkeypatch):
    """AC4: a Chroma exception does not stop Timescale cleanup, and the
    job does not raise out of the scheduler tick."""
    import src.app as app_module

    monkeypatch.setattr(app_module, "get_redis_client", lambda: None)

    def _boom(grace_seconds=0):  # noqa: ARG001
        raise RuntimeError("chroma offline")

    timescale_calls = []
    monkeypatch.setattr("src.services.compaction_ops.ttl_cleanup", _boom)
    monkeypatch.setattr(
        "src.services.compaction_ops.ttl_cleanup_timescale",
        lambda grace_seconds=0: timescale_calls.append(grace_seconds) or 5,
    )

    # Must not raise.
    app_module._run_ttl_sweep()

    assert timescale_calls == [60]


# =============================================================================
# Sanity: config helper
# =============================================================================


def test_get_ttl_sweep_interval_minutes_default(monkeypatch):
    """AC2: the cadence is configurable via `TTL_SWEEP_INTERVAL_MINUTES`
    with a 15-minute default; values below 1 are clamped to 1."""
    from src import config

    config.get_ttl_sweep_interval_minutes.cache_clear()
    monkeypatch.delenv("TTL_SWEEP_INTERVAL_MINUTES", raising=False)
    assert config.get_ttl_sweep_interval_minutes() == 15

    config.get_ttl_sweep_interval_minutes.cache_clear()
    monkeypatch.setenv("TTL_SWEEP_INTERVAL_MINUTES", "5")
    assert config.get_ttl_sweep_interval_minutes() == 5

    config.get_ttl_sweep_interval_minutes.cache_clear()
    monkeypatch.setenv("TTL_SWEEP_INTERVAL_MINUTES", "0")
    assert config.get_ttl_sweep_interval_minutes() == 1

    config.get_ttl_sweep_interval_minutes.cache_clear()
    monkeypatch.setenv("TTL_SWEEP_INTERVAL_MINUTES", "garbage")
    assert config.get_ttl_sweep_interval_minutes() == 15

    config.get_ttl_sweep_interval_minutes.cache_clear()
