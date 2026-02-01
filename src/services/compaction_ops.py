from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging
from datetime import datetime, timedelta, timezone

from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name


logger = logging.getLogger("agentic_memories.compaction_ops")


def _get_collection() -> Any:
	client = get_chroma_client()
	if client is None:
		raise RuntimeError("Chroma client not available")
	# Use standard collection name with proper dimension suffix
	return client.get_collection(_standard_collection_name())  # type: ignore[attr-defined]


def ttl_cleanup() -> int:
	"""Delete expired short-term docs based on ttl_epoch metadata.
	Returns number of deletions attempted.
	"""
	col = _get_collection()
	now_epoch = int(datetime.now(timezone.utc).timestamp())
	try:
		res = col.get(where={"ttl_epoch": {"$lte": now_epoch}}, include=["metadatas"])  # type: ignore[attr-defined]
		ids = res.get("ids", [])
		flat_ids = ids if isinstance(ids, list) else []
		if flat_ids:
			col.delete(ids=flat_ids)  # type: ignore[attr-defined]
			logger.info("[forget.ttl] deleted=%s", len(flat_ids))
			return len(flat_ids)
		return 0
	except Exception as exc:
		logger.info("[forget.ttl.error] %s", exc)
		return 0


def simple_deduplicate(user_id: str, similarity_threshold: float = 0.85, limit: int = 10000) -> Dict[str, int]:
	"""Naive per-user dedup: compare embeddings and remove near-duplicates.

	Threshold lowered from 0.90 to 0.80 (Story 4.3) to catch semantic duplicates
	that are worded differently (e.g., "User likes Buffett" vs "User admires Buffett").

	Returns stats dict with 'scanned' and 'removed' counts.
	"""
	col = _get_collection()
	try:
		res = col.get(where={"user_id": user_id}, limit=limit, include=["documents", "metadatas"])  # type: ignore[attr-defined]
		ids = res.get("ids", [])
		docs = res.get("documents", [])
		N = len(ids)
		if N <= 1:
			return {"scanned": N, "removed": 0}
		embs: List[List[float]] = []
		for doc in docs:
			try:
				embs.append(generate_embedding(doc) or [])
			except Exception:
				embs.append([])
		removed: List[str] = []
		for i in range(N):
			if ids[i] in removed:
				continue
			for j in range(i + 1, N):
				if ids[j] in removed:
					continue
				a = embs[i]
				b = embs[j]
				if not a or not b or len(a) != len(b):
					continue
				dot = sum(x * y for x, y in zip(a, b))
				na = sum(x * x for x in a) ** 0.5
				nb = sum(y * y for y in b) ** 0.5
				if na <= 0 or nb <= 0:
					continue
				cos = dot / (na * nb)
				if cos >= similarity_threshold:
					removed.append(ids[j])
		if removed:
			col.delete(ids=removed)  # type: ignore[attr-defined]
			logger.info("[forget.dedup] user_id=%s removed=%s of %s", user_id, len(removed), N)
		return {"scanned": N, "removed": len(removed)}
	except Exception as exc:
		logger.info("[forget.dedup.error] user_id=%s %s", user_id, exc)
		return {"scanned": 0, "removed": 0}


def deduplicate_episodic(user_id: str, limit: int = 1000) -> Dict[str, int]:
	"""Deduplicate episodic_memories for a user by exact content match.

	Groups rows by identical content, keeps the row with the highest
	importance_score in each group, and deletes the rest.

	Returns stats dict with 'scanned' and 'removed' counts.
	"""
	conn = get_timescale_conn()
	if not conn:
		logger.warning("[forget.dedup_episodic] no TimescaleDB connection")
		return {"scanned": 0, "removed": 0}

	try:
		with conn.cursor() as cur:
			# Find duplicate IDs to delete: for each group of identical content,
			# keep the row with the highest importance_score (tie-break by newest timestamp).
			cur.execute("""
				WITH ranked AS (
					SELECT id, content,
					       ROW_NUMBER() OVER (
					           PARTITION BY content
					           ORDER BY importance_score DESC NULLS LAST,
					                    event_timestamp DESC
					       ) AS rn
					FROM episodic_memories
					WHERE user_id = %s
					ORDER BY event_timestamp DESC
					LIMIT %s
				)
				SELECT id FROM ranked WHERE rn > 1
			""", (user_id, limit))
			rows = cur.fetchall()
			delete_ids = [row["id"] for row in rows]

			# Count total scanned
			cur.execute("""
				SELECT COUNT(*) AS cnt FROM episodic_memories
				WHERE user_id = %s
			""", (user_id,))
			scanned = cur.fetchone()["cnt"]

			if delete_ids:
				cur.execute("""
					DELETE FROM episodic_memories WHERE id = ANY(%s)
				""", (delete_ids,))

			conn.commit()

		logger.info("[forget.dedup_episodic] user_id=%s scanned=%s removed=%s",
		           user_id, scanned, len(delete_ids))
		return {"scanned": scanned, "removed": len(delete_ids)}
	except Exception as exc:
		if conn:
			conn.rollback()
		logger.error("[forget.dedup_episodic.error] user_id=%s %s", user_id, exc)
		return {"scanned": 0, "removed": 0}
	finally:
		if conn:
			release_timescale_conn(conn)


def deduplicate_emotional(user_id: str, limit: int = 1000) -> Dict[str, int]:
	"""Deduplicate emotional_memories for a user.

	Groups rows by (emotional_state, trigger_event) within a 1-hour time window.
	Keeps the row with the highest intensity in each group, deletes the rest.

	Returns stats dict with 'scanned' and 'removed' counts.
	"""
	conn = get_timescale_conn()
	if not conn:
		logger.warning("[forget.dedup_emotional] no TimescaleDB connection")
		return {"scanned": 0, "removed": 0}

	try:
		with conn.cursor() as cur:
			# Fetch emotional memories ordered by timestamp
			cur.execute("""
				SELECT id, emotional_state, trigger_event, intensity, timestamp
				FROM emotional_memories
				WHERE user_id = %s
				ORDER BY timestamp DESC
				LIMIT %s
			""", (user_id, limit))
			rows = cur.fetchall()
			scanned = len(rows)

			if scanned <= 1:
				conn.commit()
				return {"scanned": scanned, "removed": 0}

			# Group by (emotional_state, trigger_event) within 1-hour windows
			# For each group, keep the row with the highest intensity
			delete_ids = []
			groups: Dict[str, List[Dict]] = {}

			for row in rows:
				state = row.get("emotional_state") or ""
				trigger = row.get("trigger_event") or ""
				ts = row.get("timestamp")
				# Create a bucket key: state + trigger + hour-rounded timestamp
				if ts:
					hour_bucket = ts.replace(minute=0, second=0, microsecond=0).isoformat()
				else:
					hour_bucket = "none"
				group_key = f"{state}|{trigger}|{hour_bucket}"

				if group_key not in groups:
					groups[group_key] = []
				groups[group_key].append(row)

			for group_key, group_rows in groups.items():
				if len(group_rows) <= 1:
					continue
				# Sort by intensity descending, keep the first
				group_rows.sort(key=lambda r: float(r.get("intensity") or 0), reverse=True)
				for row in group_rows[1:]:
					delete_ids.append(row["id"])

			if delete_ids:
				cur.execute("""
					DELETE FROM emotional_memories WHERE id = ANY(%s)
				""", (delete_ids,))

			conn.commit()

		logger.info("[forget.dedup_emotional] user_id=%s scanned=%s removed=%s",
		           user_id, scanned, len(delete_ids))
		return {"scanned": scanned, "removed": len(delete_ids)}
	except Exception as exc:
		if conn:
			conn.rollback()
		logger.error("[forget.dedup_emotional.error] user_id=%s %s", user_id, exc)
		return {"scanned": 0, "removed": 0}
	finally:
		if conn:
			release_timescale_conn(conn)


def ttl_cleanup_timescale() -> int:
	"""TTL-based cleanup of stale TimescaleDB memories.

	- Episodic: delete where importance_score < 0.3 AND older than 90 days
	- Emotional: delete where intensity < 0.2 AND older than 60 days

	Returns total number of rows deleted.
	"""
	conn = get_timescale_conn()
	if not conn:
		logger.warning("[forget.ttl_timescale] no TimescaleDB connection")
		return 0

	total_deleted = 0
	try:
		with conn.cursor() as cur:
			# Episodic TTL: low importance + old
			cutoff_episodic = datetime.now(timezone.utc) - timedelta(days=90)
			cur.execute("""
				DELETE FROM episodic_memories
				WHERE importance_score < 0.3
				  AND event_timestamp < %s
			""", (cutoff_episodic,))
			episodic_deleted = cur.rowcount

			# Emotional TTL: low intensity + old
			cutoff_emotional = datetime.now(timezone.utc) - timedelta(days=60)
			cur.execute("""
				DELETE FROM emotional_memories
				WHERE intensity < 0.2
				  AND timestamp < %s
			""", (cutoff_emotional,))
			emotional_deleted = cur.rowcount

			conn.commit()

		total_deleted = episodic_deleted + emotional_deleted
		logger.info("[forget.ttl_timescale] episodic_deleted=%s emotional_deleted=%s total=%s",
		           episodic_deleted, emotional_deleted, total_deleted)
		return total_deleted
	except Exception as exc:
		if conn:
			conn.rollback()
		logger.error("[forget.ttl_timescale.error] %s", exc)
		return 0
	finally:
		if conn:
			release_timescale_conn(conn)

