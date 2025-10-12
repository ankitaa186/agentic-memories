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
	from src.dependencies.langfuse_client import get_langfuse_client
	
	client = get_langfuse_client()
	if not client:
		return None
	
	try:
		trace = client.trace(name=name, user_id=user_id, metadata=metadata or {})
		_current_trace.set(trace)
		return trace
	except Exception as e:
		print(f"Failed to start trace: {e}")
		return None


def get_current_trace() -> Optional[Any]:
	"""Get the current trace from context.
	
	Returns:
		Current trace object or None.
	"""
	return _current_trace.get()


def start_span(name: str, metadata: Optional[Dict[str, Any]] = None, input: Optional[Dict[str, Any]] = None) -> Optional[Any]:
	"""Start a new span within the current trace.
	
	Args:
		name: Name of the span (e.g., "worthiness_check")
		metadata: Additional metadata
		input: Input data for the span
	
	Returns:
		Span object if trace exists, None otherwise.
	"""
	trace = get_current_trace()
	if not trace:
		return None
	
	try:
		span = trace.span(name=name, metadata=metadata or {}, input=input)
		_current_span.set(span)
		return span
	except Exception as e:
		print(f"Failed to start span: {e}")
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

