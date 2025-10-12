from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.dependencies.timescale import get_timescale_conn
from src.dependencies.neo4j_client import get_neo4j_driver
from src.dependencies.chroma import get_chroma_client


logger = logging.getLogger(__name__)


class StorageOrchestrator:
	"""Facade for cross-store operations.

	This orchestrates writes/reads across Timescale/Postgres, Chroma, and Neo4j.
	It is intentionally minimal; production concerns like retries/transactions
	should be layered in as features roll out.
	"""

	def __init__(self) -> None:
		self._timescale = get_timescale_conn()
		self._neo4j = get_neo4j_driver()
		self._chroma = get_chroma_client()

	def insert_episode(self, episode: Dict[str, Any]) -> Optional[str]:
		"""Insert an episodic memory row into Timescale.

		Returns the logical id (UUID string) if present, otherwise None.
		"""
		conn = self._timescale
		if conn is None:
			logger.info("[orchestrator] timescale not configured; skip episode insert")
			return episode.get("id")
		try:
			with conn.cursor() as cur:
				cur.execute(
					"""
					INSERT INTO episodic_memories (
						id, user_id, event_timestamp, event_type, content,
						location, participants, emotional_valence, emotional_arousal,
						sensory_context, causal_chain, significance_score, replay_count,
						last_recalled, decay_factor
					) VALUES (
						%(id)s, %(user_id)s, %(event_timestamp)s, %(event_type)s, %(content)s,
						%(location)s, %(participants)s, %(emotional_valence)s, %(emotional_arousal)s,
						%(sensory_context)s, %(causal_chain)s, %(significance_score)s, %(replay_count)s,
						%(last_recalled)s, %(decay_factor)s
					) ON CONFLICT DO NOTHING
					""",
					episode,
				)
				conn.commit()
			return episode.get("id")
		except Exception as exc:
			logger.info("[orchestrator] insert_episode failed: %s", exc)
			return episode.get("id")

	def upsert_chroma(self, _id: str, embedding: Optional[list[float]], metadata: Dict[str, Any]) -> None:
		client = self._chroma
		if client is None:
			logger.info("[orchestrator] chroma not configured; skip upsert")
			return
		try:
			col = None
			# Prefer existing collection helper if available via retrieval utils
			for c in client.list_collections():
				if hasattr(c, "name") and c.name:
					col = c
					break
			if col is None:
				logger.info("[orchestrator] no chroma collections found; skip upsert")
				return
			# Upsert is supported by chromadb
			col.upsert(ids=[_id], embeddings=[embedding] if embedding else None, metadatas=[metadata])
		except Exception as exc:
			logger.info("[orchestrator] chroma upsert failed: %s", exc)

	def create_episode_node(self, episode_id: str, properties: Dict[str, Any]) -> None:
		drv = self._neo4j
		if drv is None:
			logger.info("[orchestrator] neo4j not configured; skip node create")
			return
		try:
			with drv.session() as session:
				session.run(
					"MERGE (e:Episode {id: $id}) SET e += $props",
					{"id": episode_id, "props": properties},
				)
		except Exception as exc:
			logger.info("[orchestrator] neo4j create node failed: %s", exc)

	def link_related_memories(self, episode_id: str, relationships: Dict[str, Any]) -> None:
		drv = self._neo4j
		if drv is None:
			return
		try:
			led_to = relationships.get("led_to") or []
			with drv.session() as session:
				for tgt in led_to:
					session.run(
						"""
						MERGE (a:Episode {id: $src})
						MERGE (b:Episode {id: $dst})
						MERGE (a)-[:LED_TO]->(b)
						""",
						{"src": episode_id, "dst": tgt},
					)
		except Exception as exc:
			logger.info("[orchestrator] neo4j link failed: %s", exc)

	def update_semantic_knowledge(self, facts: list[Dict[str, Any]]) -> None:
		conn = self._timescale
		if conn is None:
			return
		# Depending on deployment, semantic_memories may live in the same DSN
		try:
			with conn.cursor() as cur:
				for f in facts or []:
					cur.execute(
						"""
						INSERT INTO semantic_memories (
							id, user_id, content, category, subcategory, confidence,
							source_episodes, learned_date, last_accessed, access_count,
							decay_rate, reinforcement_threshold
						) VALUES (
							%(id)s, %(user_id)s, %(content)s, %(category)s, %(subcategory)s, %(confidence)s,
							%(source_episodes)s, %(learned_date)s, %(last_accessed)s, %(access_count)s,
							%(decay_rate)s, %(reinforcement_threshold)s
						) ON CONFLICT (id) DO UPDATE SET
							content = EXCLUDED.content,
							confidence = EXCLUDED.confidence,
							last_accessed = EXCLUDED.last_accessed,
							access_count = GREATEST(semantic_memories.access_count, EXCLUDED.access_count)
						""",
						f,
					)
				conn.commit()
		except Exception as exc:
			logger.info("[orchestrator] update_semantic_knowledge failed: %s", exc)

	def record_emotional_state(self, state: Dict[str, Any]) -> None:
		conn = self._timescale
		if conn is None:
			return
		try:
			with conn.cursor() as cur:
				cur.execute(
					"""
					INSERT INTO emotional_memories (
						user_id, timestamp, emotion_vector, triggers, intensity, duration,
						coping_strategies, resolution, linked_episodes
					) VALUES (
						%(user_id)s, %(timestamp)s, %(emotion_vector)s, %(triggers)s, %(intensity)s, %(duration)s,
						%(coping_strategies)s, %(resolution)s, %(linked_episodes)s
					)
					""",
					state,
				)
				conn.commit()
		except Exception as exc:
			logger.info("[orchestrator] record_emotional_state failed: %s", exc)


