from __future__ import annotations

from typing import Optional
from psycopg import connect, Connection
from psycopg.rows import dict_row
from src.config import get_timescale_dsn


_conn: Optional[Connection] = None


def get_timescale_conn() -> Optional[Connection]:
	global _conn
	if _conn is not None:
		return _conn
	dsn = get_timescale_dsn()
	if not dsn:
		return None
	try:
		_conn = connect(dsn, row_factory=dict_row)
		return _conn
	except Exception:
		return None


def ping_timescale() -> tuple[bool, Optional[str]]:
	try:
		conn = get_timescale_conn()
		if conn is None:
			return (False, "no connection")
		with conn.cursor() as cur:
			cur.execute("SELECT 1;")
			_ = cur.fetchone()
		return (True, None)
	except Exception as exc:
		return (False, str(exc))


