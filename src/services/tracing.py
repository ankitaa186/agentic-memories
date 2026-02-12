"""
Tracing utilities for Langfuse integration.

Provides request-scoped trace context using contextvars for async-safe operation.
Updated for Langfuse SDK v3 API.
"""

from contextvars import ContextVar
from typing import Optional, Dict, Any

_current_client: ContextVar[Optional[Any]] = ContextVar("current_client", default=None)
_current_root_span: ContextVar[Optional[Any]] = ContextVar(
    "current_root_span", default=None
)
_span_stack: ContextVar[list] = ContextVar("span_stack", default=[])


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
