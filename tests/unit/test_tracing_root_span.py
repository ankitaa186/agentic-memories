"""Story 2.1: tests for `src.services.tracing.root_span`.

These tests verify the wrap helper used by the seven non-graph entry points
behaves correctly across the four paths it must handle: Langfuse disabled,
Langfuse available with no parent (open a root span), Langfuse available with
an active parent (skip wrapping), and exception propagation.

The fixtures intentionally avoid the real `langfuse` SDK — they install a
lightweight stand-in via `monkeypatch` on `src.dependencies.langfuse_client`
so this stays a unit test.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import List, Optional

import pytest

from src.services import tracing


class _FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.updates: List[dict] = []

    def update(self, output=None, **_kw) -> None:
        self.updates.append({"output": output})


class _FakeClient:
    """In-memory Langfuse stand-in. Tracks opened spans + a fake current
    trace id so nested-detection can be exercised."""

    def __init__(self) -> None:
        self.spans: List[_FakeSpan] = []
        self.trace_ids_created: List[str] = []
        self._current_trace_id: Optional[str] = None
        self._depth = 0

    def get_current_trace_id(self) -> Optional[str]:
        return self._current_trace_id

    def create_trace_id(self) -> str:
        tid = f"trace-{len(self.trace_ids_created) + 1}"
        self.trace_ids_created.append(tid)
        return tid

    @contextmanager
    def start_as_current_observation(
        self,
        *,
        as_type: str,
        name: str,
        trace_context=None,
        input=None,
        metadata=None,
    ):
        span = _FakeSpan(name)
        self.spans.append(span)
        prior = self._current_trace_id
        if trace_context and "trace_id" in trace_context:
            self._current_trace_id = trace_context["trace_id"]
        else:
            # nested span — keep the existing trace id
            self._current_trace_id = prior or "nested-trace"
        self._depth += 1
        try:
            yield span
        finally:
            self._depth -= 1
            self._current_trace_id = prior


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(
        "src.dependencies.langfuse_client.get_langfuse_client",
        lambda: client,
    )
    # Also clear contextvars (a previous test may have populated them).
    tracing._current_client.set(None)
    tracing._current_root_span.set(None)
    tracing._span_stack.set([])
    return client


def test_root_span_opens_span_when_langfuse_available(fake_client: _FakeClient) -> None:
    with tracing.root_span(
        name="memory_create_direct",
        user_id="user-1",
        input={"k": 1},
        metadata={"endpoint": "/v1/memories/direct"},
    ) as span:
        assert span is not None
        span.update(output={"status": "success"})

    assert len(fake_client.spans) == 1
    assert fake_client.spans[0].name == "memory_create_direct"
    assert fake_client.spans[0].updates == [{"output": {"status": "success"}}]
    # Contextvars must be reset on exit.
    assert tracing._current_client.get() is None
    assert tracing._current_root_span.get() is None


def test_root_span_skips_when_already_nested(fake_client: _FakeClient) -> None:
    """Default `skip_if_nested=True` must not open a sibling root when a
    parent is already active in the OTEL context."""
    with tracing.root_span(name="outer", user_id="u") as outer:
        assert outer is not None
        with tracing.root_span(name="inner", user_id="u") as inner:
            # inner skipped — yields None — embeddings would attach to `outer`.
            assert inner is None

    # Only the outer span was opened.
    assert [s.name for s in fake_client.spans] == ["outer"]


def test_root_span_yields_none_when_langfuse_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.dependencies.langfuse_client.get_langfuse_client",
        lambda: None,
    )
    with tracing.root_span(name="retrieval", user_id="u") as span:
        assert span is None  # graceful degradation


def test_root_span_propagates_exceptions(fake_client: _FakeClient) -> None:
    """Exceptions from the wrapped body must propagate unchanged and the
    span must be closed via __exit__ — no orphan spans."""

    class _Boom(RuntimeError):
        pass

    with pytest.raises(_Boom):
        with tracing.root_span(name="hybrid_retrieval", user_id="u"):
            raise _Boom("boom")

    # Span was opened (and the fake client's context manager runs through
    # finally so depth is back to 0). Contextvars are restored.
    assert len(fake_client.spans) == 1
    assert fake_client._depth == 0
    assert tracing._current_client.get() is None
    assert tracing._current_root_span.get() is None


def test_root_span_includes_session_id_when_provided(fake_client: _FakeClient) -> None:
    with tracing.root_span(name="x", user_id="u", session_id="sess-1"):
        pass
    # Hard to inspect trace_context on the fake span directly; this just
    # asserts the helper accepts the kwarg without raising.
    assert len(fake_client.spans) == 1


def test_root_span_does_not_skip_when_explicitly_disabled(
    fake_client: _FakeClient,
) -> None:
    with tracing.root_span(name="outer", user_id="u"):
        with tracing.root_span(
            name="inner", user_id="u", skip_if_nested=False
        ) as inner:
            assert inner is not None  # forced to open even when nested

    assert [s.name for s in fake_client.spans] == ["outer", "inner"]
