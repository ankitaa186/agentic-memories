from __future__ import annotations

from typing import Any, Dict, List, Optional

import hashlib
import time
import uuid
import json

import logging
from src.dependencies.chroma import get_chroma_client
from src.models import Memory
from src.services.retrieval import _standard_collection_name


COLLECTION_NAME = "memories"
logger = logging.getLogger("agentic_memories.storage")


def init_chroma_collection(name: str = COLLECTION_NAME) -> Any:
	client = get_chroma_client()
	if client is None:
		raise RuntimeError("Chroma client not available")
	# V2 client exposes get_or_create_collection; avoid legacy create_collection
	return client.get_or_create_collection(name)  # type: ignore[attr-defined]


def _ttl_epoch_from_ttl(ttl_seconds: Optional[int]) -> Optional[int]:
	if ttl_seconds is None:
		return None
	return int(time.time()) + int(ttl_seconds)



def _build_metadata(memory: Memory) -> Dict[str, Any]:
	content_hash = hashlib.sha256(memory.content.strip().lower().encode()).hexdigest()
	meta: Dict[str, Any] = {
		"user_id": memory.user_id,
		"layer": memory.layer,
		"type": memory.type,
		"timestamp": memory.timestamp.isoformat(),
		"confidence": memory.confidence,
		"relevance_score": memory.relevance_score,
		"usage_count": memory.usage_count,
		"importance": memory.importance,
		"content_hash": content_hash,
		"persona_tags": json.dumps(memory.persona_tags or []),
		"tags": json.dumps(memory.metadata.get("tags", [])),  # Serialize list to string
	}
	if memory.emotional_signature:
		meta["emotional_signature"] = json.dumps(memory.emotional_signature)
	if memory.ttl is not None:
		meta["ttl_epoch"] = _ttl_epoch_from_ttl(memory.ttl)
	# Pass-through all metadata fields not already in meta
	for key, value in memory.metadata.items():
		if key in meta or key == "tags":  # tags already handled above
			continue
		if value is None:
			continue
		if isinstance(value, (list, dict)):
			meta[key] = json.dumps(value)
		elif isinstance(value, (str, int, float, bool)):
			meta[key] = value
		else:
			meta[key] = str(value)  # Coerce unsupported types for ChromaDB
	return meta


def upsert_memories(user_id: str, memories: List[Memory]) -> List[str]:
	if not memories:
		logger.info("[storage.upsert] user_id=%s count=%s (noop)", user_id, 0)
		return []
	for m in memories:
		if m.user_id != user_id:
			raise ValueError("user_id mismatch in memories")

	ids: List[str] = []
	documents: List[str] = []
	embeddings: List[List[float]] = []
	metadatas: List[Dict[str, Any]] = []

	for m in memories:
		mem_id = m.id or f"mem_{uuid.uuid4().hex[:12]}"
		ids.append(mem_id)
		documents.append(m.content)
		
		# Ensure embedding is properly handled
		embedding = m.embedding or []
		if not embedding:
			# Generate embedding if missing
			try:
				from src.services.embedding_utils import generate_embedding
				embedding = generate_embedding(m.content) or []
			except Exception as exc:
				logger.warning("[storage.upsert.embedding_error] user_id=%s id=%s error=%s", user_id, mem_id, exc)
				embedding = []
		
		embeddings.append(embedding)
		metadatas.append(_build_metadata(m))
	logger.info("[storage.upsert.prepare] user_id=%s ids=%s", user_id, len(ids))

	# Use standard collection naming to ensure consistency with retrieval
	collection_name = _standard_collection_name()
	collection = init_chroma_collection(collection_name)

	# Chroma upsert
	collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)  # type: ignore[attr-defined]
	logger.info("[storage.upsert.done] user_id=%s count=%s collection=%s", user_id, len(ids), collection_name)
	return ids


def increment_usage_count(ids: List[str]) -> None:
	# Optionally: implement as metadata updates in Chroma if supported by client, else no-op placeholder
	try:
		# We don't know the dimension here; skip increment to avoid collection mismatch complexities
		return
	except Exception:
		return


