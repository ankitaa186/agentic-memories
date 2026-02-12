"""TimescaleDB / PostgreSQL connection management with connection pooling."""

from typing import Optional
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config import get_timescale_dsn


_pool: Optional[ConnectionPool] = None


def get_timescale_pool() -> Optional[ConnectionPool]:
    """
    Get the connection pool singleton.
    Initialize on first call with proper pool configuration.
    """
    global _pool
    if _pool is not None:
        return _pool

    dsn = get_timescale_dsn()
    if not dsn:
        return None

    try:
        # Create connection pool with sensible defaults
        _pool = ConnectionPool(
            dsn,
            min_size=2,  # Keep 2 connections alive
            max_size=10,  # Max 10 concurrent connections
            kwargs={"row_factory": dict_row},
            open=True,  # Open pool immediately
        )
        return _pool
    except Exception as e:
        print(f"Failed to create connection pool: {e}")
        return None


def get_timescale_conn() -> Optional[Connection]:
    """
    Get a connection from the pool.

    IMPORTANT: Caller MUST manage transaction with commit()/rollback()
    Example:
            conn = get_timescale_conn()
            try:
                    with conn.cursor() as cur:
                            cur.execute(...)
                    conn.commit()
            except Exception as e:
                    conn.rollback()
                    raise
    """
    pool = get_timescale_pool()
    if not pool:
        return None

    try:
        return pool.getconn()
    except Exception as e:
        print(f"Failed to get connection from pool: {e}")
        return None


def release_timescale_conn(conn: Connection):
    """
    Return a connection back to the pool.
    Services should call this after completing their transaction.

    Note: Always rollback before returning to ensure clean transaction state.
    This prevents 'connection in INTRANS state' warnings from the pool.
    If the caller already committed, rollback is a no-op.
    """
    pool = get_timescale_pool()
    if pool and conn:
        try:
            conn.rollback()  # Ensure clean transaction state before returning to pool
            pool.putconn(conn)
        except Exception as e:
            print(f"Failed to return connection to pool: {e}")


def ping_timescale() -> tuple[bool, Optional[str]]:
    conn = None
    try:
        conn = get_timescale_conn()
        if not conn:
            return False, "Connection unavailable"

        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            return bool(result), None
    except Exception as exc:
        return False, str(exc)
    finally:
        if conn:
            release_timescale_conn(conn)
