"""
Tracing utilities for Langfuse integration.

Provides request-scoped trace context using contextvars for async-safe operation.
"""
from contextvars import ContextVar
from typing import Optional, Dict, Any

_current_trace: ContextVar[Optional[Any]] = ContextVar('current_trace', default=None)
_current_span: ContextVar[Optional[Any]] = ContextVar('current_span', default=None)


def start_trace(name: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Any]:
	"""Start a new trace for a request.
	
	Args:
		name: Name of the trace (e.g., "store_transcript")
		user_id: User ID for grouping traces
		metadata: Additional metadata to attach to the trace
	
	Returns:
		Trace object if Langfuse is enabled, None otherwise.
	"""
	import logging
	from src.dependencies.langfuse_client import get_langfuse_client
	
	logger = logging.getLogger("agentic_memories.tracing")
	
	client = get_langfuse_client()
	if not client:
		logger.warning("[tracing] Langfuse client not available")
		return None
	
	try:
		trace = client.trace(name=name, user_id=user_id, metadata=metadata or {})
		_current_trace.set(trace)
		logger.info("[tracing] Started trace: name=%s user_id=%s trace_id=%s", name, user_id, trace.id)
		return trace
	except Exception as e:
		logger.error("[tracing] Failed to start trace: %s", e, exc_info=True)
		return None


def get_current_trace() -> Optional[Any]:
	"""Get the current trace from context.
	
	Returns:
		Current trace object or None.
	"""
	return _current_trace.get()


def start_span(name: str, metadata: Optional[Dict[str, Any]] = None, input: Optional[Dict[str, Any]] = None) -> Optional[Any]:
	"""Start a new span within the current trace or parent span.
	
	Args:
		name: Name of the span (e.g., "worthiness_check")
		metadata: Additional metadata
		input: Input data for the span
	
	Returns:
		Span object if trace exists, None otherwise.
	"""
	import logging
	logger = logging.getLogger("agentic_memories.tracing")
	
	trace = get_current_trace()
	if not trace:
		return None
	
	try:
		# Get current parent span (if any) to create nested hierarchy
		parent_span = _current_span.get()
		
		# Create span as child of parent span, or directly under trace
		if parent_span:
			span = parent_span.span(name=name, metadata=metadata or {}, input=input)
			logger.debug("[tracing] Started nested span: %s (parent: %s)", name, parent_span.id if hasattr(parent_span, 'id') else 'unknown')
		else:
			span = trace.span(name=name, metadata=metadata or {}, input=input)
			logger.debug("[tracing] Started top-level span: %s", name)
		
		# Don't overwrite parent span - we'll manage the stack manually
		# _current_span.set(span)
		
		return span
	except Exception as e:
		logger.error("[tracing] Failed to start span: %s", e, exc_info=True)
		return None


def end_span(output: Optional[Dict[str, Any]] = None, level: str = "DEFAULT") -> None:
	"""End the current span.
	
	Args:
		output: Output data from the span
		level: Log level (DEFAULT, WARNING, ERROR)
	"""
	span = _current_span.get()
	if span:
		try:
			span.end(output=output, level=level)
		except Exception as e:
			print(f"Failed to end span: {e}")


def trace_error(exception: Exception, metadata: Optional[Dict[str, Any]] = None) -> None:
	"""Record an error event in the current trace.
	
	Args:
		exception: The exception that occurred
		metadata: Additional context about the error
	"""
	trace = get_current_trace()
	if not trace:
		return
	
	try:
		trace.event(
			name="error",
			input={
				"exception_type": type(exception).__name__,
				"message": str(exception)
			},
			metadata=metadata or {},
			level="ERROR"
		)
	except Exception as e:
		print(f"Failed to record error event: {e}")

