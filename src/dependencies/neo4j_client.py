from __future__ import annotations

from typing import Optional
from neo4j import GraphDatabase, Driver
from src.config import get_neo4j_uri, get_neo4j_user, get_neo4j_password


_driver: Optional[Driver] = None


def get_neo4j_driver() -> Optional[Driver]:
	global _driver
	if _driver is not None:
		return _driver
	uri = get_neo4j_uri() or ""
	user = get_neo4j_user() or ""
	password = get_neo4j_password() or ""
	if not uri:
		return None
	try:
		_driver = GraphDatabase.driver(uri, auth=(user, password))
		return _driver
	except Exception:
		return None


def ping_neo4j() -> tuple[bool, Optional[str]]:
	try:
		driver = get_neo4j_driver()
		if driver is None:
			return (False, "no driver")
		with driver.session() as session:
			val = session.run("RETURN 1 AS ok").single()
			_ = val["ok"] if val else 0
		return (True, None)
	except Exception as exc:
		return (False, str(exc))


