"""
Langfuse client singleton for tracing and observability.
"""

from typing import Optional, Any
import atexit

from src.config import (
    get_langfuse_public_key,
    get_langfuse_secret_key,
    get_langfuse_host,
    is_langfuse_enabled,
)

_langfuse_client: Optional[Any] = None


def get_langfuse_client() -> Optional[Any]:
    """Get or create the singleton Langfuse client.

    Returns:
            Langfuse client if enabled and configured, None otherwise.
    """
    global _langfuse_client

    if not is_langfuse_enabled():
        return None

    if _langfuse_client is None:
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=get_langfuse_public_key(),
                secret_key=get_langfuse_secret_key(),
                host=get_langfuse_host(),
                flush_at=10,  # Batch size - send after 10 traces
                flush_interval=1.0,  # Flush every second
            )

            # Ensure traces are flushed on app shutdown
            atexit.register(
                lambda: _langfuse_client.flush() if _langfuse_client else None
            )

        except ImportError:
            # Langfuse not installed, graceful degradation
            return None
        except Exception as e:
            # Log error but don't crash the app
            print(f"Failed to initialize Langfuse client: {e}")
            return None

    return _langfuse_client


def ping_langfuse() -> bool:
    """Check if Langfuse client is available and functional.

    Returns:
            True if client is available, False otherwise.
    """
    client = get_langfuse_client()
    return client is not None
