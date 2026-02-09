"""
Unified Memory Ingestion LangGraph

A comprehensive LangGraph that handles the entire memory ingestion pipeline:
1. Worthiness check
2. Memory extraction
3. Classification & enrichment (including sentiment analysis)
4. Parallel storage to multiple backends (episodic, emotional, procedural, portfolio)
5. ChromaDB persistence
6. Result aggregation

This replaces the previous separation between extraction and routing.
"""

from __future__ import annotations

import hashlib
import logging
import time
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from src.schemas import TranscriptRequest
from src.services.prompts_v3 import WORTHINESS_PROMPT_V3, EXTRACTION_PROMPT_V3
from src.services.extract_utils import _call_llm_json
from src.services.memory_context import format_memories_for_llm_context, get_relevant_existing_memories
from src.services.storage import upsert_memories
from src.models import Memory
from src.services.embedding_utils import generate_embedding
from src.config import get_default_short_term_ttl_seconds
from src.services.profile_extraction import ProfileExtractor
from src.services.profile_storage import ProfileStorageService

logger = logging.getLogger("agentic_memories.unified_graph")

SHORT_TERM_TTL_SECONDS = get_default_short_term_ttl_seconds()


# ============================================================================
# Sentiment Analysis Prompt
# ============================================================================

SENTIMENT_ANALYSIS_PROMPT = """You are a sentiment and emotion classifier.

Analyze the emotional content of the provided text and return a JSON object with:
- "has_emotional_content": boolean (true if emotions are present)
- "valence": float from -1.0 (very negative) to 1.0 (very positive)
- "arousal": float from 0.0 (calm) to 1.0 (excited/intense)
- "dominant_emotion": string (e.g., "joy", "sadness", "anger", "fear", "surprise", "neutral")
- "emotional_keywords": list of strings (words that indicate emotion)

Example:
Input: "I'm so excited about learning Python!"
Output: {
  "has_emotional_content": true,
  "valence": 0.8,
  "arousal": 0.7,
  "dominant_emotion": "joy",
  "emotional_keywords": ["excited"]
}

Return ONLY valid JSON."""


# ============================================================================
# State Definition
# ============================================================================

class IngestionState(Dict[str, Any]):
	"""
	State for the unified ingestion graph
	
	Fields:
	- request: TranscriptRequest
	- user_id: str
	- history: List[Dict]
	- existing_memories: List[Dict]
	- worthy: bool
	- extracted_items: List[Dict]
	- memories: List[Memory]
	- memory_ids: List[str]
	- classifications: List[Dict]
	- profile_extractions: List[Dict]
	- storage_results: Dict[str, Any]
	- metrics: Dict[str, Any]
	- errors: List[str]
	"""
	pass


# ============================================================================
# Graph Nodes
# ============================================================================

def node_init(state: IngestionState) -> IngestionState:
	"""Initialize the ingestion pipeline"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("ingestion_init", input={
		"user_id": state.get("user_id"),
		"history_length": len(state.get("history", []))
	})
	
	state["t_start"] = time.perf_counter()
	state["metrics"] = {}
	state["errors"] = []
	state["storage_results"] = {
		"episodic_stored": 0,
		"emotional_stored": 0,
		"procedural_stored": 0,
		"portfolio_stored": 0,
		"chromadb_stored": 0,
		"profile_fields_stored": 0
	}
	
	logger.info("[graph.init] user_id=%s history_length=%s", 
	           state.get("user_id"), len(state.get("history", [])))
	
	end_span(output={"initialized": True})
	return state


def node_worthiness(state: IngestionState) -> IngestionState:
	"""Check if the conversation is worth extracting memories from"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("worthiness_check", input={
		"history_count": len(state.get("history", []))
	})
	
	history = state.get("history", [])
	# Convert Message objects to dicts for JSON serialization
	history_dicts = [{"role": m.role, "content": m.content} if hasattr(m, 'role') else m for m in history]
	# Process ALL messages to capture initial profile information
	payload = {"history": history_dicts}
	
	resp = _call_llm_json(WORTHINESS_PROMPT_V3, payload)
	worthy = bool(resp and resp.get("worthy", False))
	
	state["worthy"] = worthy
	state["metrics"]["worthiness_check_ms"] = int((time.perf_counter() - state["t_start"]) * 1000)
	
	logger.info("[graph.worthiness] user_id=%s worthy=%s", state.get("user_id"), worthy)
	
	end_span(output={"worthy": worthy})
	return state


def node_extract(state: IngestionState) -> IngestionState:
	"""Extract memories from the conversation using LLM"""
	from src.services.tracing import start_span, end_span
	
	# Get existing memories for context
	user_id = state.get("user_id")
	request = state.get("request")
	existing_memories = get_relevant_existing_memories(request)
	state["existing_memories"] = existing_memories
	
	_span = start_span("memory_extraction", input={
		"user_id": user_id,
		"existing_memories_count": len(existing_memories)
	})
	
	existing_context = format_memories_for_llm_context(existing_memories)
	
	# Convert Message objects to dicts for JSON serialization
	history = state["history"]
	history_dicts = [{"role": m.role, "content": m.content} if hasattr(m, 'role') else m for m in history]

	# Create enhanced payload with existing memory context
	# Process ALL messages to capture initial profile information
	payload = {
		"history": history_dicts,
		"existing_memories_context": existing_context
	}
	
	# Enhanced extraction prompt with context (using V3 prompt with emotional/narrative support)
	enhanced_prompt = f"{EXTRACTION_PROMPT_V3}\n\n{existing_context}\n\nBased on the existing memories above, extract only NEW information that adds value."
	
	items = _call_llm_json(enhanced_prompt, payload, expect_array=True) or []
	state["extracted_items"] = items
	state["metrics"]["extraction_ms"] = int((time.perf_counter() - state["t_start"]) * 1000)
	
	logger.info("[graph.extract] user_id=%s items_extracted=%s", user_id, len(items))
	
	end_span(output={"items_extracted": len(items)})
	return state


def node_classify_and_enrich(state: IngestionState) -> IngestionState:
	"""Classify memory types and enrich with sentiment analysis

	V3 Enhancement: Uses emotional_context from extraction output when available,
	reducing redundant LLM calls and providing richer emotional data.
	"""
	from src.services.tracing import start_span, end_span

	_span = start_span("classification_enrichment", input={
		"items_count": len(state.get("extracted_items", []))
	})

	items = state.get("extracted_items", [])
	classifications = []

	for item in items:
		content = str(item.get("content", "")).strip()
		tags = item.get("tags", [])
		layer = item.get("layer", "semantic")

		# V3: Use layer from extraction for classification
		classification = {
			"is_episodic": layer == "episodic" or _is_episodic(item, tags),
			"is_procedural": layer == "procedural" or _is_procedural(item, tags),
			"is_financial": bool(item.get("portfolio")),
			"has_relationship": bool(item.get("relationship")),
			"has_learning": bool(item.get("learning_journal")),
		}

		# V3: Use emotional_context from extraction if available (no extra LLM call needed)
		emotional_context = item.get("emotional_context")
		if emotional_context:
			# Convert V3 emotional_context to sentiment format
			sentiment = {
				"has_emotional_content": True,
				"valence": float(emotional_context.get("valence", 0.0)),
				"arousal": float(emotional_context.get("arousal", 0.5)),
				"dominant_emotion": emotional_context.get("dominant_emotion", "neutral"),
				"importance": float(emotional_context.get("importance", 0.5)),
			}
			classification["sentiment"] = sentiment
			classification["is_emotional"] = layer == "emotional" or emotional_context.get("importance", 0) > 0.7
			logger.debug("[graph.classify] Using V3 emotional_context: valence=%.2f arousal=%.2f emotion=%s",
			            sentiment["valence"], sentiment["arousal"], sentiment["dominant_emotion"])
		elif layer == "emotional" or _might_have_emotion(content, tags):
			# Fallback: LLM-based sentiment analysis if no emotional_context provided
			sentiment = _analyze_sentiment_llm(content)
			classification["sentiment"] = sentiment
			classification["is_emotional"] = sentiment.get("has_emotional_content", False) if sentiment else False
		else:
			classification["is_emotional"] = False
			classification["sentiment"] = None

		classifications.append(classification)
	
	state["classifications"] = classifications
	state["metrics"]["classification_ms"] = int((time.perf_counter() - state["t_start"]) * 1000)
	
	logger.info("[graph.classify] user_id=%s classified=%s emotional=%s episodic=%s procedural=%s",
	           state.get("user_id"),
	           len(classifications),
	           sum(1 for c in classifications if c["is_emotional"]),
	           sum(1 for c in classifications if c["is_episodic"]),
	           sum(1 for c in classifications if c["is_procedural"]))
	
	end_span(output={
		"classified": len(classifications),
		"emotional_count": sum(1 for c in classifications if c["is_emotional"]),
		"episodic_count": sum(1 for c in classifications if c["is_episodic"]),
		"procedural_count": sum(1 for c in classifications if c["is_procedural"])
	})
	
	return state


def _normalize_location_value(location: Any) -> Optional[Dict[str, Any]]:
	"""Normalize location into a consistent dictionary form."""
	if not location:
		return None

	if isinstance(location, dict):
		return location

	if isinstance(location, str):
		return {"place": location}

	if isinstance(location, list):
		normalized: List[str] = []
		for entry in location:
			if isinstance(entry, str):
				normalized.append(entry)
			elif isinstance(entry, dict):
				name = entry.get("name") or entry.get("place") or entry.get("label")
				normalized.append(name or json.dumps(entry, sort_keys=True))
			else:
				normalized.append(str(entry))

		if not normalized:
			return None

		if len(normalized) == 1:
			return {"place": normalized[0]}

		return {"places": normalized}

	return {"place": str(location)}


def _normalize_participants_value(participants: Any) -> Optional[List[str]]:
	"""Normalize participants into a list of string identifiers."""
	if not participants:
		return None

	if isinstance(participants, list):
		normalized: List[str] = []
		for participant in participants:
			if isinstance(participant, str):
				normalized.append(participant)
			elif isinstance(participant, dict):
				name = participant.get("name") or participant.get("label") or participant.get("person")
				normalized.append(name or json.dumps(participant, sort_keys=True))
			else:
				normalized.append(str(participant))

		return normalized or None

	if isinstance(participants, str):
		return [participants]

	return [json.dumps(participants, sort_keys=True)]


def _merge_request_metadata(base_metadata: Dict[str, Any], request: Optional[TranscriptRequest]) -> None:
	"""Merge request-level metadata into the memory metadata without clobbering core fields."""
	if not request or not getattr(request, "metadata", None):
		return

	request_metadata = request.metadata
	if not isinstance(request_metadata, dict):
		logger.warning("[graph.build_memories] request.metadata is not a dict: %s", type(request_metadata))
		return

	request_meta_copy = dict(request_metadata)
	request_tags = request_meta_copy.pop("tags", None)

	for key, value in request_meta_copy.items():
		if key in base_metadata and isinstance(base_metadata[key], dict) and isinstance(value, dict):
			base_metadata[key] = {**base_metadata[key], **value}
		else:
			base_metadata[key] = value

	if request_tags:
		existing_tags = list(base_metadata.get("tags", []))
		if isinstance(request_tags, str):
			new_tags = [request_tags]
		elif isinstance(request_tags, (list, tuple, set)):
			new_tags = list(request_tags)
		else:
			new_tags = [str(request_tags)]
		combined = list(dict.fromkeys(existing_tags + new_tags))
		base_metadata["tags"] = combined


def node_build_memories(state: IngestionState) -> IngestionState:
	"""Build Memory objects from extracted items"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("build_memory_objects", input={
		"items_count": len(state.get("extracted_items", []))
	})
	
	items = state.get("extracted_items", [])
	memories: List[Memory] = []
	
	request = state.get("request")

	for item in items:
		content = str(item.get("content", "")).strip()
		if not content:
			continue

		mtype = item.get("type", "explicit")
		layer = item.get("layer", "semantic")
		ttl = item.get("ttl")
		if layer == "short-term" and not ttl:
			ttl = SHORT_TERM_TTL_SECONDS
		confidence = float(item.get("confidence", 0.7))
		tags = item.get("tags") or []

		metadata: Dict[str, Any] = {
			"source": "extraction_llm",
			"tags": tags,
		}

		# Include all optional structured objects from the extractor output
		optional_fields = [
			"project",
			"relationship",
			"learning_journal",
			"portfolio",
			"temporal",
			"entities",
			"episodic_context",
			"emotional_context",
			"behavioral_pattern",
			"narrative_markers",
			"consolidation_hints",
			"skill_context",
			"semantic_stability",
			"confidence_breakdown",
			"inferrable_context",
		]

		for field in optional_fields:
			value = item.get(field)
			if value:
				metadata[field] = value

		# Derive spatial/participant context for episodic storage
		episodic_context = metadata.get("episodic_context")
		location = _normalize_location_value(
			metadata.get("location") or (episodic_context or {}).get("location")
		)
		participants = _normalize_participants_value(
			metadata.get("participants") or (episodic_context or {}).get("participants")
		)

		entities = metadata.get("entities")
		if not location and isinstance(entities, dict):
			location = _normalize_location_value(entities.get("places"))
		if not participants and isinstance(entities, dict):
			participants = _normalize_participants_value(entities.get("people"))

		if location:
			metadata["location"] = location
		if participants:
			metadata["participants"] = participants

		_merge_request_metadata(metadata, request)

		# Generate memory ID upfront so it's available for profile extraction
		# This ensures profile_sources.source_memory_id is properly populated
		memory_id = f"mem_{uuid.uuid4().hex[:12]}"

		embedding = generate_embedding(content)
		memory = Memory(
			id=memory_id,
			user_id=state["user_id"],
			content=content,
			layer=layer,
			type=mtype,
			embedding=embedding,
			confidence=confidence,
			ttl=ttl,
			metadata=metadata,
		)
		memories.append(memory)
	
	state["memories"] = memories
	state["metrics"]["build_memories_ms"] = int((time.perf_counter() - state["t_start"]) * 1000)
	
	logger.info("[graph.build_memories] user_id=%s memories_built=%s", 
	           state.get("user_id"), len(memories))
	
	end_span(output={"memories_built": len(memories)})
	return state


def node_dedup_check(state: IngestionState) -> IngestionState:
	"""Remove duplicate memories before storage using content hash and semantic similarity.

	Two-pass dedup:
	1. **Exact match** — content_hash lookup in ChromaDB metadata (fast, zero tolerance).
	2. **Semantic match** — cosine-distance query against existing user embeddings.
	   Collection uses cosine distance so values are `1 - cosine_similarity`.
	   Threshold 0.08 ≈ cosine similarity > 0.92, catching LLM paraphrases.

	Also filters classifications to stay aligned with the memories list so that
	downstream zip(memories, classifications) remains correct.
	"""
	from src.services.tracing import start_span, end_span
	from src.services.retrieval import _standard_collection_name
	from src.dependencies.chroma import get_chroma_client

	# Cosine distance threshold: 0.20 ≈ cosine similarity 0.80
	# Tuned from real paraphrase measurements:
	#   - dist 0.05: identical text, trivial word swap          → catch
	#   - dist 0.19: "about 3 cups every morning" vs
	#                 "three cups each morning"                 → catch (same fact)
	#   - dist 0.25: same topic, genuinely new detail           → allow
	# Compaction (0.85 cosine) catches anything this misses.
	SEMANTIC_DISTANCE_THRESHOLD = 0.15

	_span = start_span("dedup_check", input={
		"memories_count": len(state.get("memories", []))
	})

	memories = state.get("memories", [])
	classifications = state.get("classifications", [])
	user_id = state.get("user_id")

	if not memories:
		state["metrics"]["duplicates_avoided"] = 0
		end_span(output={"duplicates_avoided": 0})
		return state

	duplicates_avoided = 0
	hash_dupes = 0
	semantic_dupes = 0
	keep_indices: List[int] = []

	try:
		client = get_chroma_client()
		if client is None:
			raise RuntimeError("Chroma client not available")
		collection_name = _standard_collection_name()
		collection = client.get_or_create_collection(collection_name)

		for idx, memory in enumerate(memories):
			content_hash = hashlib.sha256(memory.content.strip().lower().encode()).hexdigest()
			memory.metadata["content_hash"] = content_hash

			is_duplicate = False
			match_type = None

			# --- Pass 1: exact content_hash match (fast metadata lookup) ---
			try:
				hash_results = collection.get(
					where={"$and": [
						{"user_id": user_id},
						{"content_hash": content_hash},
					]},
					limit=1,
				)
				if hash_results and hash_results.get("ids") and len(hash_results["ids"]) > 0:
					is_duplicate = True
					match_type = "exact_hash"
					hash_dupes += 1
			except Exception as exc:
				logger.debug("[graph.dedup_check.hash_query_error] user_id=%s error=%s", user_id, exc)

			# --- Pass 2: semantic similarity (embedding cosine distance) ---
			if not is_duplicate and memory.embedding:
				try:
					results = collection.query(
						query_embeddings=[memory.embedding],
						n_results=3,
						where={"user_id": user_id},
					)
					distances = results.get("distances", [[]])
					documents = results.get("documents", [[]])
					if distances and distances[0]:
						for i, dist in enumerate(distances[0]):
							# Cosine distance: 1 - cosine_sim. Lower = more similar.
							if dist < SEMANTIC_DISTANCE_THRESHOLD:
								is_duplicate = True
								match_type = "semantic"
								semantic_dupes += 1
								existing_doc = documents[0][i] if documents and documents[0] and i < len(documents[0]) else ""
								logger.info(
									"[graph.dedup_check.semantic_match] user_id=%s dist=%.4f "
									"new='%s' existing='%s'",
									user_id, dist,
									memory.content[:60], (existing_doc or "")[:60],
								)
								break
				except Exception as exc:
					logger.warning("[graph.dedup_check.query_error] user_id=%s error=%s", user_id, exc)

			if is_duplicate:
				duplicates_avoided += 1
				logger.info("[graph.dedup_check.duplicate] user_id=%s match=%s hash=%s content=%s",
				           user_id, match_type, content_hash[:12], memory.content[:80])
			else:
				keep_indices.append(idx)

	except Exception as exc:
		logger.warning("[graph.dedup_check.error] user_id=%s error=%s — passing all memories through", user_id, exc)
		keep_indices = list(range(len(memories)))

	state["memories"] = [memories[i] for i in keep_indices]
	# Keep classifications aligned with memories (they are built 1:1 with extracted_items
	# which maps 1:1 to memories after build_memories filters empty content)
	if classifications:
		state["classifications"] = [classifications[i] for i in keep_indices if i < len(classifications)]

	state["metrics"]["duplicates_avoided"] = duplicates_avoided

	logger.info("[graph.dedup_check] user_id=%s input=%s output=%s duplicates_avoided=%s (hash=%s semantic=%s)",
	           user_id, len(memories), len(state["memories"]),
	           duplicates_avoided, hash_dupes, semantic_dupes)

	end_span(output={
		"duplicates_avoided": duplicates_avoided,
		"hash_dupes": hash_dupes,
		"semantic_dupes": semantic_dupes,
		"memories_remaining": len(state["memories"]),
	})
	return state


def node_extract_profile(state: IngestionState) -> IngestionState:
	"""Extract profile information from memories using LLM"""
	from src.services.tracing import start_span, end_span

	_span = start_span("extract_profile", input={
		"memories_count": len(state.get("memories", []))
	})

	memories = state.get("memories", [])
	user_id = state.get("user_id")

	if not memories:
		logger.info("[graph.extract_profile] user_id=%s no_memories", user_id)
		state["profile_extractions"] = []
		end_span(output={"extractions": 0})
		return state

	try:
		extractor = ProfileExtractor()
		extractions = extractor.extract_from_memories(user_id, memories)

		state["profile_extractions"] = extractions

		logger.info("[graph.extract_profile] user_id=%s extractions=%s", user_id, len(extractions))

		end_span(output={"extractions": len(extractions)})
	except Exception as e:
		error_msg = f"Profile extraction failed: {str(e)}"
		state["errors"].append(error_msg)
		state["profile_extractions"] = []
		logger.error("[graph.extract_profile] %s", error_msg, exc_info=True)

		end_span(output={"error": str(e)}, level="ERROR")

		from src.services.tracing import trace_error
		trace_error(e, metadata={"context": "profile_extraction", "user_id": user_id})

	return state


def node_store_profile(state: IngestionState) -> IngestionState:
	"""Store profile extractions in PostgreSQL"""
	from src.services.tracing import start_span, end_span

	_span = start_span("store_profile", input={
		"extractions_count": len(state.get("profile_extractions", []))
	})

	extractions = state.get("profile_extractions", [])
	user_id = state.get("user_id")

	if not extractions:
		logger.info("[graph.store_profile] user_id=%s no_extractions", user_id)
		end_span(output={"stored": 0})
		return state

	try:
		storage = ProfileStorageService()
		fields_updated = storage.store_profile_extractions(user_id, extractions)

		state["storage_results"]["profile_fields_stored"] = fields_updated

		logger.info("[graph.store_profile] user_id=%s fields_stored=%s", user_id, fields_updated)

		end_span(output={"stored": fields_updated})
	except Exception as e:
		error_msg = f"Profile storage failed: {str(e)}"
		state["errors"].append(error_msg)
		logger.error("[graph.store_profile] %s", error_msg, exc_info=True)

		end_span(output={"error": str(e)}, level="ERROR")

		from src.services.tracing import trace_error
		trace_error(e, metadata={"context": "profile_storage", "user_id": user_id})

	return state


def node_store_chromadb(state: IngestionState) -> IngestionState:
	"""Store memories in ChromaDB (vector database)"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("store_chromadb", input={
		"memories_count": len(state.get("memories", []))
	})
	
	memories = state.get("memories", [])
	user_id = state.get("user_id")
	
	try:
		ids = upsert_memories(user_id, memories)
		state["memory_ids"] = ids
		state["storage_results"]["chromadb_stored"] = len(ids)
		
		logger.info("[graph.chromadb] user_id=%s stored=%s", user_id, len(ids))
		
		end_span(output={"stored": len(ids)})
	except Exception as e:
		error_msg = f"ChromaDB storage failed: {str(e)}"
		state["errors"].append(error_msg)
		logger.error("[graph.chromadb] %s", error_msg)
		
		end_span(output={"error": str(e)}, level="ERROR")
		
		from src.services.tracing import trace_error
		trace_error(e, metadata={"context": "chromadb_storage", "user_id": user_id})
	
	return state


def node_store_episodic(state: IngestionState) -> IngestionState:
	"""Store episodic memories in TimescaleDB + ChromaDB

	V3 Enhancement: Uses emotional_context from extraction for richer emotional data,
	including importance scoring and dominant emotion.
	"""
	from src.services.tracing import start_span, end_span

	_span = start_span("store_episodic", input={"user_id": state.get("user_id")})

	memories = state.get("memories", [])
	_memory_ids = state.get("memory_ids", [])
	classifications = state.get("classifications", [])
	_extracted_items = state.get("extracted_items", [])
	user_id = state.get("user_id")

	stored_count = 0

	try:
		from src.services.episodic_memory import EpisodicMemoryService, EpisodicMemory
		import uuid

		service = EpisodicMemoryService()

		for i, (memory, classification) in enumerate(zip(memories, classifications)):
			if not classification.get("is_episodic"):
				continue

			# Generate a proper UUID for episodic storage (different from ChromaDB mem_xxx ID)
			episodic_id = str(uuid.uuid4())

			# V3: Get emotional_context from extraction OR classification sentiment
			sentiment = classification.get("sentiment") or {}
			emotional_valence = float(sentiment.get("valence", 0.0))
			emotional_arousal = float(sentiment.get("arousal", 0.0))

			# V3: Use importance from emotional_context if available, else confidence
			importance = float(sentiment.get("importance", memory.confidence))

			# Also check metadata for emotional_context (V3 extraction output)
			emotional_context = memory.metadata.get("emotional_context") or {}
			if emotional_context:
				emotional_valence = float(emotional_context.get("valence", emotional_valence))
				emotional_arousal = float(emotional_context.get("arousal", emotional_arousal))
				importance = float(emotional_context.get("importance", importance))

			if sentiment or emotional_context:
				logger.debug("[graph.episodic] V3 emotional data: valence=%.2f arousal=%.2f importance=%.2f emotion=%s",
				            emotional_valence, emotional_arousal, importance,
				            sentiment.get("dominant_emotion") or emotional_context.get("dominant_emotion", "unknown"))

			episodic_memory = EpisodicMemory(
				id=episodic_id,
				user_id=user_id,
				event_type=memory.type,
				event_timestamp=memory.timestamp or datetime.now(timezone.utc),
				content=memory.content,
				location=memory.metadata.get('location'),
				participants=memory.metadata.get('participants'),
				emotional_valence=emotional_valence,
				emotional_arousal=emotional_arousal,
				importance_score=importance,
				tags=memory.metadata.get('tags', []),
				metadata=memory.metadata
			)
			
			if service.store_memory(episodic_memory):
				stored_count += 1
		
		state["storage_results"]["episodic_stored"] = stored_count
		logger.info("[graph.episodic] user_id=%s stored=%s", user_id, stored_count)
		
		end_span(output={"stored": stored_count})
	except Exception as e:
		error_msg = f"Episodic storage failed: {str(e)}"
		state["errors"].append(error_msg)
		logger.error("[graph.episodic] %s", error_msg)
		
		end_span(output={"error": str(e)}, level="ERROR")
	
	return state


def node_store_emotional(state: IngestionState) -> IngestionState:
	"""Store emotional states in TimescaleDB"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("store_emotional", input={"user_id": state.get("user_id")})
	
	memories = state.get("memories", [])
	classifications = state.get("classifications", [])
	user_id = state.get("user_id")
	
	stored_count = 0
	
	try:
		from src.services.emotional_memory import EmotionalMemoryService
		
		service = EmotionalMemoryService()
		
		for memory, classification in zip(memories, classifications):
			if not classification.get("is_emotional"):
				continue
			
			sentiment = classification.get("sentiment", {})
			if not sentiment:
				continue
			
			emotional_state = sentiment.get("dominant_emotion", "neutral")
			valence = sentiment.get("valence", 0.0)
			arousal = sentiment.get("arousal", 0.5)
			
			if service.record_emotional_state(
				user_id=user_id,
				emotional_state=emotional_state,
				valence=valence,
				arousal=arousal,
				context=memory.content,  # Use actual memory content, not tags
				trigger_event=", ".join(memory.metadata.get('tags', []))  # Tags as trigger
			):
				stored_count += 1
		
		state["storage_results"]["emotional_stored"] = stored_count
		logger.info("[graph.emotional] user_id=%s stored=%s", user_id, stored_count)
		
		end_span(output={"stored": stored_count})
	except Exception as e:
		error_msg = f"Emotional storage failed: {str(e)}"
		state["errors"].append(error_msg)
		logger.error("[graph.emotional] %s", error_msg)
		
		end_span(output={"error": str(e)}, level="ERROR")
	
	return state


def node_store_procedural(state: IngestionState) -> IngestionState:
	"""Store procedural memories (skills) in PostgreSQL"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("store_procedural", input={"user_id": state.get("user_id")})
	
	memories = state.get("memories", [])
	classifications = state.get("classifications", [])
	user_id = state.get("user_id")
	
	stored_count = 0
	
	try:
		from src.services.procedural_memory import ProceduralMemoryService
		
		service = ProceduralMemoryService()
		
		for memory, classification in zip(memories, classifications):
			if not classification.get("is_procedural"):
				continue
			
			learning_journal = memory.metadata.get('learning_journal') or {}
			skill_name = learning_journal.get('topic') or memory.content[:100]
			
			if service.practice_skill(
				user_id=user_id,
				skill_name=skill_name,
				success_rate=memory.confidence,
				notes=memory.content
			):
				stored_count += 1
		
		state["storage_results"]["procedural_stored"] = stored_count
		logger.info("[graph.procedural] user_id=%s stored=%s", user_id, stored_count)
		
		end_span(output={"stored": stored_count})
	except Exception as e:
		error_msg = f"Procedural storage failed: {str(e)}"
		state["errors"].append(error_msg)
		logger.error("[graph.procedural] %s", error_msg)
		
		end_span(output={"error": str(e)}, level="ERROR")
	
	return state


def node_store_portfolio(state: IngestionState) -> IngestionState:
	"""Store portfolio/financial data in PostgreSQL"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("store_portfolio", input={"user_id": state.get("user_id")})
	
	memories = state.get("memories", [])
	memory_ids = state.get("memory_ids", [])
	classifications = state.get("classifications", [])
	user_id = state.get("user_id")
	
	stored_count = 0
	
	try:
		from src.services.portfolio_service import PortfolioService
		
		service = PortfolioService()
		
		for i, (memory, classification) in enumerate(zip(memories, classifications)):
			if not classification.get("is_financial"):
				continue
			
			portfolio_meta = memory.metadata.get('portfolio')
			if not portfolio_meta:
				continue
			
			memory_id = memory_ids[i] if i < len(memory_ids) else None
			
			service.upsert_holding_from_memory(
				user_id=user_id,
				portfolio_metadata=portfolio_meta,
				memory_id=memory_id
			)
			stored_count += 1
		
		state["storage_results"]["portfolio_stored"] = stored_count
		logger.info("[graph.portfolio] user_id=%s stored=%s", user_id, stored_count)
		
		end_span(output={"stored": stored_count})
	except Exception as e:
		error_msg = f"Portfolio storage failed: {str(e)}"
		state["errors"].append(error_msg)
		logger.error("[graph.portfolio] %s", error_msg)
		
		end_span(output={"error": str(e)}, level="ERROR")
	
	return state


def node_summarize_storage(state: IngestionState) -> IngestionState:
	"""Summarize all storage operations and prepare final metrics"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("summarize_storage", input={"user_id": state.get("user_id")})
	
	storage_results = state.get("storage_results", {})
	
	# Calculate totals
	total_stored = sum([
		storage_results.get("episodic_stored", 0),
		storage_results.get("emotional_stored", 0),
		storage_results.get("procedural_stored", 0),
		storage_results.get("portfolio_stored", 0),
		storage_results.get("chromadb_stored", 0),
		storage_results.get("profile_fields_stored", 0)
	])
	
	# Build summary
	summary = {
		"total_stored": total_stored,
		"breakdown": storage_results,
		"memories_created": len(state.get("memory_ids", [])),
		"errors": len(state.get("errors", []))
	}
	
	state["storage_summary"] = summary
	
	logger.info("[graph.summarize] user_id=%s total_stored=%s breakdown=%s",
	           state.get("user_id"), total_stored, storage_results)
	
	end_span(output=summary)
	
	return state


def node_finalize(state: IngestionState) -> IngestionState:
	"""Finalize the ingestion and collect metrics"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("ingestion_finalize", input={})
	
	total_ms = int((time.perf_counter() - state["t_start"]) * 1000)
	state["metrics"]["total_ms"] = total_ms
	
	logger.info("[graph.finalize] user_id=%s total_ms=%s storage_results=%s errors=%d",
	           state.get("user_id"),
	           total_ms,
	           state.get("storage_results"),
	           len(state.get("errors", [])))
	
	end_span(output={
		"total_ms": total_ms,
		"storage_results": state.get("storage_results"),
		"errors_count": len(state.get("errors", []))
	})
	
	return state


# ============================================================================
# Helper Functions
# ============================================================================

def _is_episodic(item: Dict[str, Any], tags: List[str]) -> bool:
	"""Determine if a memory should be stored as episodic

	V3 Enhancement: Also checks for V3's explicit 'episodic' layer classification.
	"""
	# V3: Check if extraction already classified as episodic
	layer = item.get("layer", "")
	if layer == "episodic":
		return True

	# Check for episodic_context from V3 extraction
	if item.get("episodic_context"):
		return True

	event_tags = {'event', 'meeting', 'conversation', 'activity', 'trip', 'workout', 'milestone'}
	has_event_tag = any(tag in event_tags for tag in tags)

	is_short_term = layer == "short-term"

	mtype = item.get("type", "")
	is_explicit = mtype == "explicit"

	is_episodic = has_event_tag or (is_short_term and is_explicit)

	# Debug logging
	logger.debug("[_is_episodic] tags=%s layer=%s type=%s has_event_tag=%s result=%s",
	            tags, layer, mtype, has_event_tag, is_episodic)

	return is_episodic


def _is_procedural(item: Dict[str, Any], tags: List[str]) -> bool:
	"""Determine if a memory should be stored as procedural

	V3 Enhancement: Also checks for V3's explicit 'procedural' layer and skill_context.
	"""
	# V3: Check if extraction already classified as procedural
	layer = item.get("layer", "")
	if layer == "procedural":
		return True

	# Check for skill_context from V3 extraction
	if item.get("skill_context"):
		return True

	skill_tags = {'skill', 'learning', 'practice', 'technique', 'method', 'process', 'workflow', 'breakthrough'}
	has_skill_tag = any(tag in skill_tags for tag in tags)

	has_learning_journal = item.get('learning_journal') is not None

	is_procedural = has_skill_tag or has_learning_journal

	# Debug logging
	logger.debug("[_is_procedural] tags=%s has_skill_tag=%s has_learning_journal=%s result=%s",
	            tags, has_skill_tag, has_learning_journal, is_procedural)

	return is_procedural


def _might_have_emotion(content: str, tags: List[str]) -> bool:
	"""Quick check if content might have emotional content (before LLM call)"""
	content_lower = content.lower()
	
	# Emotional keywords (basic check)
	emotion_words = {
		'happy', 'sad', 'excited', 'angry', 'frustrated', 'worried', 'anxious',
		'stressed', 'love', 'hate', 'fear', 'joy', 'great', 'terrible', 'amazing',
		'awful', 'wonderful', 'horrible', 'fantastic', 'disappointed'
	}
	
	has_emotion_word = any(word in content_lower for word in emotion_words)
	
	# Emotional tags
	emotion_tags = {'emotion', 'feeling', 'mood'}
	has_emotion_tag = any(tag in emotion_tags for tag in tags)
	
	return has_emotion_word or has_emotion_tag


def _analyze_sentiment_llm(content: str) -> Optional[Dict[str, Any]]:
	"""Use LLM to analyze sentiment and emotion"""
	try:
		payload = {"text": content}
		result = _call_llm_json(SENTIMENT_ANALYSIS_PROMPT, payload)
		return result if result else None
	except Exception as e:
		logger.warning("[sentiment_analysis] Failed for content: %s | error=%s", content[:50], e)
		return None


# ============================================================================
# Conditional Edges
# ============================================================================

def decide_after_worthiness(state: IngestionState) -> str:
	"""Decide whether to proceed with extraction or skip"""
	if state.get("worthy", False):
		return "extract"
	else:
		return "finalize_early"


def decide_after_extraction(state: IngestionState) -> str:
	"""Decide whether we have items to process"""
	items = state.get("extracted_items", [])
	if len(items) > 0:
		return "classify"
	else:
		return "finalize_early"




def node_finalize_early(state: IngestionState) -> IngestionState:
	"""Early finalization when nothing to extract"""
	from src.services.tracing import start_span, end_span
	
	_span = start_span("ingestion_finalize_early", input={})
	
	state["memory_ids"] = []
	state["metrics"]["total_ms"] = int((time.perf_counter() - state["t_start"]) * 1000)
	
	logger.info("[graph.finalize_early] user_id=%s reason=%s",
	           state.get("user_id"),
	           "not_worthy" if not state.get("worthy") else "no_items")
	
	end_span(output={"reason": "not_worthy" if not state.get("worthy") else "no_items"})
	
	return state


# ============================================================================
# Graph Construction
# ============================================================================

def build_unified_ingestion_graph() -> StateGraph:
	"""Build the unified memory ingestion graph"""
	graph = StateGraph(dict)
	
	# Add all nodes
	graph.add_node("init", node_init)
	graph.add_node("worthiness", node_worthiness)
	graph.add_node("extract", node_extract)
	graph.add_node("classify", node_classify_and_enrich)
	graph.add_node("build_memories", node_build_memories)
	graph.add_node("dedup_check", node_dedup_check)
	graph.add_node("extract_profile", node_extract_profile)
	graph.add_node("store_profile", node_store_profile)
	graph.add_node("store_chromadb", node_store_chromadb)
	
	# Individual storage nodes (executed sequentially for proper trace hierarchy)
	graph.add_node("store_episodic", node_store_episodic)
	graph.add_node("store_emotional", node_store_emotional)
	graph.add_node("store_procedural", node_store_procedural)
	# graph.add_node("store_portfolio", node_store_portfolio)
	
	# Summary and finalization nodes
	graph.add_node("summarize", node_summarize_storage)
	graph.add_node("finalize", node_finalize)
	graph.add_node("finalize_early", node_finalize_early)
	
	# Set entry point
	graph.set_entry_point("init")
	
	# Build the flow
	graph.add_edge("init", "worthiness")
	graph.add_conditional_edges(
		"worthiness",
		decide_after_worthiness,
		{"extract": "extract", "finalize_early": "finalize_early"}
	)
	graph.add_conditional_edges(
		"extract",
		decide_after_extraction,
		{"classify": "classify", "finalize_early": "finalize_early"}
	)
	graph.add_edge("classify", "build_memories")
	graph.add_edge("build_memories", "dedup_check")
	graph.add_edge("dedup_check", "extract_profile")
	graph.add_edge("extract_profile", "store_profile")
	graph.add_edge("store_profile", "store_chromadb")
	
	# Sequential storage operations (each gets its own span in trace)
	# Note: Kept sequential to avoid LangGraph's multi-value convergence issue
	# Performance impact is minimal (~400ms total for all storage ops)
	graph.add_edge("store_chromadb", "store_episodic")
	graph.add_edge("store_episodic", "store_emotional")
	graph.add_edge("store_emotional", "store_procedural")
	# graph.add_edge("store_procedural", "store_portfolio")
	graph.add_edge("store_procedural", "summarize")
	# Summarize storage results before finalize
	# graph.add_edge("store_portfolio", "summarize")
	graph.add_edge("summarize", "finalize")
	
	# End nodes
	graph.add_edge("finalize", END)
	graph.add_edge("finalize_early", END)
	
	return graph


def run_unified_ingestion(request: TranscriptRequest) -> Dict[str, Any]:
	"""Run the unified ingestion graph with native LangChain/Langfuse tracing"""
	from src.config import is_langfuse_enabled, get_langfuse_public_key, get_langfuse_secret_key, get_langfuse_host

	graph = build_unified_ingestion_graph()
	compiled_graph = graph.compile()

	initial_state = {
		"request": request,
		"user_id": request.user_id,
		"history": request.history,
	}

	# Use LangChain's native Langfuse callback handler with Langfuse v3 context propagation
	if is_langfuse_enabled():
		try:
			from langfuse.langchain import CallbackHandler
			from langfuse import Langfuse

			# Create Langfuse client
			langfuse_client = Langfuse(
				public_key=get_langfuse_public_key(),
				secret_key=get_langfuse_secret_key(),
				host=get_langfuse_host(),
			)

			# Prepare input for tracing
			trace_input = {
				"user_id": request.user_id,
				"history_length": len(request.history),
				"messages": [{"role": m.role, "content": m.content[:200]} for m in request.history[:3]]
			}

			# Generate a trace_id upfront so we can reference it
			trace_id = langfuse_client.create_trace_id()
			logger.info("[unified_graph] Starting with Langfuse trace_id=%s for user_id=%s", trace_id, request.user_id)

			# Use start_as_current_observation as root - this creates a trace implicitly
			# All OpenAI wrapper calls inside will be linked to this trace
			with langfuse_client.start_as_current_observation(
				as_type="span",
				name="unified_memory_ingestion",
				trace_context={
					"trace_id": trace_id,
					"user_id": request.user_id,
					"session_id": f"session_{request.user_id}",
				},
				input=trace_input,
				metadata={
					"endpoint": "/v1/store",
					"history_length": str(len(request.history)),
				},
			) as root_span:
				# Create callback handler - inherits context
				langfuse_handler = CallbackHandler()

				# Run graph with LangChain callback
				final_state: Dict[str, Any] = compiled_graph.invoke(
					initial_state,
					config={
						"callbacks": [langfuse_handler],
						"run_name": "memory_pipeline"
					}
				)

				# Update span with output
				trace_output = {
					"memories_created": len(final_state.get("memory_ids", [])),
					"storage_results": final_state.get("storage_results", {}),
					"total_ms": final_state.get("metrics", {}).get("total_ms", 0),
					"errors": len(final_state.get("errors", []))
				}
				root_span.update(output=trace_output)

			# Flush all traces
			langfuse_client.flush()

			logger.info("[unified_graph] Flushed Langfuse traces")
			
		except ImportError as e:
			logger.warning("[unified_graph] LangChain not available for Langfuse integration: %s. Install langchain-core.", e)
			# Fallback to running without tracing
			final_state: Dict[str, Any] = compiled_graph.invoke(initial_state)
		except Exception as e:
			logger.error("[unified_graph] Langfuse callback failed: %s", e, exc_info=True)
			# Fallback to running without tracing
			final_state: Dict[str, Any] = compiled_graph.invoke(initial_state)
	else:
		logger.info("[unified_graph] Langfuse disabled, running without tracing")
		final_state: Dict[str, Any] = compiled_graph.invoke(initial_state)
	
	logger.info("[unified_graph] completed user_id=%s memories=%s total_ms=%s",
	           request.user_id,
	           len(final_state.get("memory_ids", [])),
	           final_state.get("metrics", {}).get("total_ms", 0))
	
	return final_state

