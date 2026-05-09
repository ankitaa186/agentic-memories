"""
Tracing utilities for Langfuse integration.

Provides request-scoped trace context using contextvars for async-safe operation.
Updated for Langfuse SDK v3 API.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Dict, Any, Iterator

_current_client: ContextVar[Optional[Any]] = ContextVar("current_client", default=None)
_current_root_span: ContextVar[Optional[Any]] = ContextVar(
    "current_root_span", default=None
)
_span_stack: ContextVar[list] = ContextVar("span_stack", default=[])


@contextmanager
def root_span(
    name: str,
    user_id: str,
    *,
    input: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    skip_if_nested: bool = True,
) -> Iterator[Optional[Any]]:
    """Open a Langfuse root span for a non-graph entry point (Story 2.1).

    Mirrors the canonical wrap pattern at
    ``src/services/unified_ingestion_graph.py:1428-1452`` but as a reusable
    helper so the seven non-graph entry points stay consistent.

    Behaviour:
      * Skips wrapping (yields ``None``) when Langfuse is disabled, the SDK
        is unavailable, or initialisation fails. The caller's body still runs.
      * When ``skip_if_nested`` is true (default) and a Langfuse span is
        already active in the current OTEL context — i.e.
        ``client.get_current_trace_id()`` returns a non-None trace id — yields
        ``None`` so the caller's embedding observations attach to the
        existing parent rather than a new sibling root.
      * On the happy path, yields the span object so callers can attach
        ``span.update(output={...})`` before exit. The span auto-closes via
        the ``with`` context manager so exceptions propagate untouched and
        no leaks accumulate.
      * Populates ``_current_client`` and ``_current_root_span`` contextvars
        so existing nested ``start_span(...)`` callers (compaction graph
        nodes, etc.) keep nesting under this root.

    Args:
        name: Span name shown in the Langfuse UI (e.g. ``"retrieval"``).
        user_id: User id for ``trace_context``. Required.
        input: Optional small dict captured as span input.
        metadata: Optional small dict captured as span metadata.
        session_id: Optional Langfuse session id. If omitted no session is
            sent (mirrors Parminder's guidance — don't fabricate one).
        skip_if_nested: When True (default), do nothing if a parent span is
            already active in this OTEL context.

    Yields:
        The Langfuse span object on success, ``None`` otherwise.
    """
    import logging

    logger = logging.getLogger("agentic_memories.tracing")

    try:
        from src.dependencies.langfuse_client import get_langfuse_client
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[tracing.root_span] langfuse import failed: %s", exc)
        yield None
        return

    client = get_langfuse_client()
    if client is None:
        # Langfuse disabled / unavailable — degrade gracefully.
        yield None
        return

    # Nested-detection: don't open a sibling root when we're already inside
    # one. The langfuse.openai wrapper auto-attaches via OTEL context, so the
    # embedding observation will nest under the existing parent.
    if skip_if_nested:
        try:
            existing_trace_id = client.get_current_trace_id()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[tracing.root_span] get_current_trace_id failed: %s", exc)
            existing_trace_id = None
        if existing_trace_id is not None:
            yield None
            return

    trace_context: Dict[str, Any]
    try:
        trace_id = client.create_trace_id()
        trace_context = {"trace_id": trace_id, "user_id": user_id}
        if session_id:
            trace_context["session_id"] = session_id
    except Exception as exc:
        logger.warning(
            "[tracing.root_span] create_trace_id failed: %s — running without trace",
            exc,
        )
        yield None
        return

    try:
        cm = client.start_as_current_observation(
            as_type="span",
            name=name,
            trace_context=trace_context,
            input=input or {},
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning(
            "[tracing.root_span] start_as_current_observation failed (name=%s): %s",
            name,
            exc,
        )
        yield None
        return

    # Populate contextvars so existing nested start_span(...) callers (which
    # check _current_client/_current_root_span) keep working under this root.
    client_token = _current_client.set(client)
    root_token = _current_root_span.set((cm, None))
    stack_token = _span_stack.set([])

    try:
        with cm as span:
            # Refresh contextvar with the actual span (replacing the
            # placeholder we set above so end_trace-style helpers can find it).
            _current_root_span.set((cm, span))
            yield span
    finally:
        _current_client.reset(client_token)
        _current_root_span.reset(root_token)
        _span_stack.reset(stack_token)


def start_trace(
    name: str, user_id: str, metadata: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """Start a new trace for a request using Langfuse v3 API.

    Args:
            name: Name of the trace (e.g., "store_transcript")
            user_id: User ID for grouping traces
            metadata: Additional metadata to attach to the trace

    Returns:
            Root span object if Langfuse is enabled, None otherwise.
    """
    import logging
    from src.dependencies.langfuse_client import get_langfuse_client

    logger = logging.getLogger("agentic_memories.tracing")

    client = get_langfuse_client()
    if not client:
        logger.warning("[tracing] Langfuse client not available")
        return None

    try:
        # Generate trace ID upfront (v3 API)
        trace_id = client.create_trace_id()

        # Create root observation which implicitly creates a trace (v3 API)
        # start_as_current_observation returns a context manager, call __enter__ to get the span
        context_manager = client.start_as_current_observation(
            as_type="span",
            name=name,
            trace_context={
                "trace_id": trace_id,
                "user_id": user_id,
                "session_id": f"session_{user_id}",
            },
            metadata=metadata or {},
        )
        root_span = context_manager.__enter__()

        # Store in context vars (keep context_manager for proper cleanup)
        _current_client.set(client)
        _current_root_span.set((context_manager, root_span))
        _span_stack.set([])

        logger.info(
            "[tracing] Started trace: name=%s user_id=%s trace_id=%s",
            name,
            user_id,
            trace_id,
        )
        return root_span
    except Exception as e:
        logger.error("[tracing] Failed to start trace: %s", e, exc_info=True)
        return None


def get_current_trace() -> Optional[Any]:
    """Get the current root span (trace) from context.

    Returns:
            Current root span object or None.
    """
    root = _current_root_span.get()
    if root and isinstance(root, tuple):
        return root[1]  # Return the span, not the context manager
    return root


def start_span(
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
    input: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Start a new span within the current trace using Langfuse v3 API.

    Args:
            name: Name of the span (e.g., "worthiness_check")
            metadata: Additional metadata
            input: Input data for the span

    Returns:
            Span object if trace exists, None otherwise.
    """
    import logging

    logger = logging.getLogger("agentic_memories.tracing")

    client = _current_client.get()
    root_span = _current_root_span.get()
    if not client or not root_span:
        return None

    try:
        # Create nested span using v3 API (inherits from current OTEL context)
        # start_as_current_observation returns a context manager, call __enter__ to get the span
        context_manager = client.start_as_current_observation(
            as_type="span",
            name=name,
            metadata=metadata or {},
            input=input,
        )
        span = context_manager.__enter__()

        # Push to stack for proper nesting (store tuple of context_manager and span)
        stack = _span_stack.get()
        stack.append((context_manager, span))
        _span_stack.set(stack)

        logger.debug("[tracing] Started span: %s", name)
        return span
    except Exception as e:
        logger.error("[tracing] Failed to start span: %s", e, exc_info=True)
        return None


def end_span(
    span: Optional[Any] = None,
    output: Optional[Dict[str, Any]] = None,
    level: str = "DEFAULT",
) -> None:
    """End a span using Langfuse v3 API.

    Args:
            span: The span to end (if None, pops from stack)
            output: Output data from the span
            level: Log level (DEFAULT, WARNING, ERROR)
    """
    import logging

    logger = logging.getLogger("agentic_memories.tracing")

    try:
        # If span provided directly (legacy), try to end it
        if span and not isinstance(span, tuple):
            if hasattr(span, "update"):
                span.update(output=output, level=level)
            if hasattr(span, "__exit__"):
                span.__exit__(None, None, None)
            return

        # Pop from stack
        stack = _span_stack.get()
        if stack:
            item = stack.pop()
            _span_stack.set(stack)

            # Handle tuple of (context_manager, span)
            if isinstance(item, tuple):
                context_manager, actual_span = item
                if output and hasattr(actual_span, "update"):
                    actual_span.update(output=output, level=level)
                context_manager.__exit__(None, None, None)
            else:
                # Fallback for non-tuple items
                if hasattr(item, "update"):
                    item.update(output=output, level=level)
                if hasattr(item, "__exit__"):
                    item.__exit__(None, None, None)

            logger.debug("[tracing] Ended span from stack")
    except Exception as e:
        logger.error("[tracing] Failed to end span: %s", e)


def trace_error(
    exception: Exception, metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Record an error event in the current trace using Langfuse v3 API.

    Args:
            exception: The exception that occurred
            metadata: Additional context about the error
    """
    import logging

    logger = logging.getLogger("agentic_memories.tracing")

    client = _current_client.get()
    if not client:
        return

    try:
        # Create an error span to record the exception
        # Use context manager properly
        with client.start_as_current_observation(
            as_type="span",
            name="error",
            input={
                "exception_type": type(exception).__name__,
                "message": str(exception),
            },
            metadata=metadata or {},
            level="ERROR",
        ):
            pass  # Span auto-closes on context exit
        logger.debug("[tracing] Recorded error: %s", type(exception).__name__)
    except Exception as e:
        logger.error("[tracing] Failed to record error event: %s", e)


def end_trace(output: Optional[Dict[str, Any]] = None) -> None:
    """End the current trace and flush to Langfuse.

    Args:
            output: Output data for the trace
    """
    import logging

    logger = logging.getLogger("agentic_memories.tracing")

    client = _current_client.get()
    root_item = _current_root_span.get()

    if not client or not root_item:
        return

    try:
        # Handle tuple of (context_manager, span)
        if isinstance(root_item, tuple):
            context_manager, root_span = root_item
            if output and hasattr(root_span, "update"):
                root_span.update(output=output)
            context_manager.__exit__(None, None, None)
        else:
            # Fallback for non-tuple
            if output and hasattr(root_item, "update"):
                root_item.update(output=output)
            if hasattr(root_item, "__exit__"):
                root_item.__exit__(None, None, None)

        # Flush traces to Langfuse
        client.flush()

        # Clear context vars
        _current_client.set(None)
        _current_root_span.set(None)
        _span_stack.set([])

        logger.info("[tracing] Ended and flushed trace")
    except Exception as e:
        logger.error("[tracing] Failed to end trace: %s", e)
