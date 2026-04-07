from __future__ import annotations

from typing import Any, Dict, List, Tuple

import logging
import os
import time as _time
from datetime import datetime, timedelta, timezone

import numpy as np

from src.dependencies.chroma import get_chroma_client
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.services.embedding_utils import generate_embedding
from src.services.retrieval import _standard_collection_name


def _get_episodic_ttl_config() -> Tuple[float, int]:
    """Read episodic TimescaleDB TTL thresholds from environment.

    Returns (score_lt, age_days). A row is eligible for deletion when
    `importance_score < score_lt AND event_timestamp < now() - age_days`.

    Defaults (0.6 / 180d) were chosen empirically: in the live corpus they
    target the bottom ~8% of records — primarily low-confidence
    conversation summaries the upstream summarizer marked at 0.5 — while
    leaving mid-tier and high-importance records untouched. Override via
    env vars when tuning retention pressure.
    """
    try:
        score_lt = float(os.getenv("TIMESCALE_TTL_EPISODIC_SCORE_LT", "0.6"))
    except ValueError:
        score_lt = 0.6
    try:
        age_days = int(os.getenv("TIMESCALE_TTL_EPISODIC_AGE_DAYS", "180"))
    except ValueError:
        age_days = 180
    if age_days < 1:
        age_days = 1
    return score_lt, age_days


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


def simple_deduplicate(
    user_id: str, similarity_threshold: float = 0.85, limit: int = 10000
) -> Dict[str, int]:
    """Per-user dedup: compare embeddings and remove near-duplicates.

    Reuses embeddings stored in ChromaDB instead of re-running the embedding
    model for every memory (which previously dominated runtime — ~6 minutes
    for 765 memories). Falls back to `generate_embedding` only for records
    that are missing an embedding.

    Uses a numpy similarity matrix and a single greedy pass: for each kept
    memory, any later memory with cosine similarity >= threshold is marked
    for deletion. The earlier ID always wins (oldest-by-fetch-order survives).

    Returns stats dict with 'scanned' and 'removed' counts.
    """
    logger.info("[forget.dedup.start] user_id=%s limit=%s", user_id, limit)
    col = _get_collection()
    try:
        _t_fetch = _time.perf_counter()
        res = col.get(
            where={"user_id": user_id},
            limit=limit,
            include=["documents", "metadatas", "embeddings"],
        )  # type: ignore[attr-defined]
        ids = list(res.get("ids", []) or [])
        docs = res.get("documents", []) or []
        raw_embs = res.get("embeddings", []) or []
        N = len(ids)
        has_embeddings = 0
        for i in range(N):
            raw = raw_embs[i] if i < len(raw_embs) else None
            if raw is not None:
                try:
                    if len(list(raw)) > 0:
                        has_embeddings += 1
                except TypeError:
                    pass
        missing_embeddings = N - has_embeddings
        logger.info(
            "[forget.dedup.fetched] user_id=%s count=%s has_embeddings=%s missing_embeddings=%s latency_ms=%s",
            user_id,
            N,
            has_embeddings,
            missing_embeddings,
            int((_time.perf_counter() - _t_fetch) * 1000),
        )
        if N <= 1:
            return {"scanned": N, "removed": 0}

        # Coerce embeddings, regenerating only when missing
        embs: List[List[float]] = []
        regenerated = 0
        for i in range(N):
            raw = raw_embs[i] if i < len(raw_embs) else None
            if raw is not None:
                try:
                    embs.append(list(raw))
                    continue
                except TypeError:
                    pass
            doc = docs[i] if i < len(docs) else ""
            try:
                emb = generate_embedding(doc) if doc else None
                embs.append(list(emb) if emb else [])
                if emb:
                    regenerated += 1
            except Exception:
                embs.append([])

        # Filter to rows with a consistent embedding dimension
        dims = [len(e) for e in embs]
        nonzero = [d for d in dims if d > 0]
        if not nonzero:
            return {"scanned": N, "removed": 0}
        modal_dim = max(set(nonzero), key=nonzero.count)
        keep = [i for i, d in enumerate(dims) if d == modal_dim]
        if len(keep) <= 1:
            return {"scanned": N, "removed": 0}

        kept_ids = [ids[i] for i in keep]
        _t_matrix = _time.perf_counter()
        matrix = np.asarray([embs[i] for i in keep], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms
        logger.info(
            "[forget.dedup.matrix] user_id=%s n=%s dim=%s modal_dim=%s latency_ms=%s",
            user_id,
            matrix.shape[0],
            matrix.shape[1],
            modal_dim,
            int((_time.perf_counter() - _t_matrix) * 1000),
        )

        _t_sim = _time.perf_counter()
        sim = matrix @ matrix.T  # cosine similarity (rows are unit vectors)
        _n_sim = sim.shape[0]
        if _n_sim > 1:
            _iu = np.triu_indices(_n_sim, k=1)
            _off = sim[_iu]
            _max_sim = float(_off.max()) if _off.size > 0 else 0.0
            _mean_sim = float(_off.mean()) if _off.size > 0 else 0.0
        else:
            _max_sim = 0.0
            _mean_sim = 0.0
        logger.info(
            "[forget.dedup.sim] user_id=%s latency_ms=%s max_sim=%.3f mean_sim=%.3f",
            user_id,
            int((_time.perf_counter() - _t_sim) * 1000),
            _max_sim,
            _mean_sim,
        )

        # Greedy single-pass dedup: for each surviving i, drop any j>i above threshold
        n = matrix.shape[0]
        dropped = np.zeros(n, dtype=bool)
        # Mask the lower triangle + diagonal so we only consider j > i
        upper = np.triu(sim >= similarity_threshold, k=1)
        for i in range(n):
            if dropped[i]:
                continue
            dup_js = np.where(upper[i] & ~dropped)[0]
            if dup_js.size > 0:
                dropped[dup_js] = True

        removed = [kept_ids[i] for i in range(n) if dropped[i]]
        if removed:
            col.delete(ids=removed)  # type: ignore[attr-defined]
            logger.info(
                "[forget.dedup] user_id=%s removed=%s of %s regenerated=%s",
                user_id,
                len(removed),
                N,
                regenerated,
            )
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
            cur.execute(
                """
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
			""",
                (user_id, limit),
            )
            rows = cur.fetchall()
            delete_ids = [row["id"] for row in rows]

            # Count total scanned
            cur.execute(
                """
				SELECT COUNT(*) AS cnt FROM episodic_memories
				WHERE user_id = %s
			""",
                (user_id,),
            )
            scanned = cur.fetchone()["cnt"]

            if delete_ids:
                cur.execute(
                    """
					DELETE FROM episodic_memories WHERE id = ANY(%s)
				""",
                    (delete_ids,),
                )

            conn.commit()

        logger.info(
            "[forget.dedup_episodic] user_id=%s scanned=%s removed=%s",
            user_id,
            scanned,
            len(delete_ids),
        )
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
            cur.execute(
                """
				SELECT id, emotional_state, trigger_event, intensity, timestamp
				FROM emotional_memories
				WHERE user_id = %s
				ORDER BY timestamp DESC
				LIMIT %s
			""",
                (user_id, limit),
            )
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
                    hour_bucket = ts.replace(
                        minute=0, second=0, microsecond=0
                    ).isoformat()
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
                group_rows.sort(
                    key=lambda r: float(r.get("intensity") or 0), reverse=True
                )
                for row in group_rows[1:]:
                    delete_ids.append(row["id"])

            if delete_ids:
                cur.execute(
                    """
					DELETE FROM emotional_memories WHERE id = ANY(%s)
				""",
                    (delete_ids,),
                )

            conn.commit()

        logger.info(
            "[forget.dedup_emotional] user_id=%s scanned=%s removed=%s",
            user_id,
            scanned,
            len(delete_ids),
        )
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

    - Episodic: delete where importance_score < TIMESCALE_TTL_EPISODIC_SCORE_LT
                AND older than TIMESCALE_TTL_EPISODIC_AGE_DAYS
                (defaults 0.6 / 180d — see `_get_episodic_ttl_config`)
    - Emotional: delete where intensity < 0.2 AND older than 60 days

    Returns total number of rows deleted.
    """
    conn = get_timescale_conn()
    if not conn:
        logger.warning("[forget.ttl_timescale] no TimescaleDB connection")
        return 0

    score_lt, age_days = _get_episodic_ttl_config()

    total_deleted = 0
    try:
        with conn.cursor() as cur:
            # Episodic TTL: low importance + old (configurable thresholds)
            cutoff_episodic = datetime.now(timezone.utc) - timedelta(days=age_days)
            cur.execute(
                """
				DELETE FROM episodic_memories
				WHERE importance_score < %s
				  AND event_timestamp < %s
			""",
                (score_lt, cutoff_episodic),
            )
            episodic_deleted = cur.rowcount

            # Emotional TTL: low intensity + old
            cutoff_emotional = datetime.now(timezone.utc) - timedelta(days=60)
            cur.execute(
                """
				DELETE FROM emotional_memories
				WHERE intensity < 0.2
				  AND timestamp < %s
			""",
                (cutoff_emotional,),
            )
            emotional_deleted = cur.rowcount

            conn.commit()

        total_deleted = episodic_deleted + emotional_deleted
        logger.info(
            "[forget.ttl_timescale] episodic_deleted=%s emotional_deleted=%s total=%s episodic_score_lt=%.2f episodic_age_days=%s",
            episodic_deleted,
            emotional_deleted,
            total_deleted,
            score_lt,
            age_days,
        )
        return total_deleted
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.error("[forget.ttl_timescale.error] %s", exc)
        return 0
    finally:
        if conn:
            release_timescale_conn(conn)
