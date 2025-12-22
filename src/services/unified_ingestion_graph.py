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

import logging
import time
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from src.schemas import TranscriptRequest
from src.services.prompts import WORTHINESS_PROMPT, EXTRACTION_PROMPT
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
	
	span = start_span("ingestion_init", input={
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
	
	span = start_span("worthiness_check", input={
		"history_count": len(state.get("history", []))
	})
	
	history = state.get("history", [])
	# Convert Message objects to dicts for JSON serialization
	history_dicts = [{"role": m.role, "content": m.content} if hasattr(m, 'role') else m for m in history]
	# Process ALL messages to capture initial profile information
	payload = {"history": history_dicts}
	
	resp = _call_llm_json(WORTHINESS_PROMPT, payload)
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
	
	span = start_span("memory_extraction", input={
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
	
	# Enhanced extraction prompt with context
	enhanced_prompt = f"{EXTRACTION_PROMPT}\n\n{existing_context}\n\nBased on the existing memories above, extract only NEW information that adds value."
	
	items = _call_llm_json(enhanced_prompt, payload, expect_array=True) or []
	state["extracted_items"] = items
	state["metrics"]["extraction_ms"] = int((time.perf_counter() - state["t_start"]) * 1000)
	
	logger.info("[graph.extract] user_id=%s items_extracted=%s", user_id, len(items))
	
	end_span(output={"items_extracted": len(items)})
	return state


def node_classify_and_enrich(state: IngestionState) -> IngestionState:
	"""Classify memory types and enrich with sentiment analysis"""
	from src.services.tracing import start_span, end_span
	
	span = start_span("classification_enrichment", input={
		"items_count": len(state.get("extracted_items", []))
	})
	
	items = state.get("extracted_items", [])
	classifications = []
	
	for item in items:
		content = str(item.get("content", "")).strip()
		tags = item.get("tags", [])
		
		# Basic classification
		classification = {
			"is_episodic": _is_episodic(item, tags),
			"is_procedural": _is_procedural(item, tags),
			"is_financial": bool(item.get("portfolio")),
			"has_relationship": bool(item.get("relationship")),
			"has_learning": bool(item.get("learning_journal")),
		}
		
		# LLM-based sentiment analysis for potential emotional content
		sentiment = None
		if _might_have_emotion(content, tags):
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
	
	span = start_span("build_memory_objects", input={
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


def node_extract_profile(state: IngestionState) -> IngestionState:
	"""Extract profile information from memories using LLM"""
	from src.services.tracing import start_span, end_span

	span = start_span("extract_profile", input={
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

	span = start_span("store_profile", input={
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
	
	span = start_span("store_chromadb", input={
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
	"""Store episodic memories in TimescaleDB + ChromaDB"""
	from src.services.tracing import start_span, end_span
	
	span = start_span("store_episodic", input={"user_id": state.get("user_id")})
	
	memories = state.get("memories", [])
	memory_ids = state.get("memory_ids", [])
	classifications = state.get("classifications", [])
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
			
			episodic_memory = EpisodicMemory(
				id=episodic_id,
				user_id=user_id,
				event_type=memory.type,
				event_timestamp=memory.timestamp or datetime.now(timezone.utc),
				content=memory.content,
				location=memory.metadata.get('location'),
				participants=memory.metadata.get('participants'),
				emotional_valence=0.0,
				emotional_arousal=0.0,
				importance_score=memory.confidence,
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
	
	span = start_span("store_emotional", input={"user_id": state.get("user_id")})
	
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
				context=str(memory.metadata.get('tags', [])),
				trigger_event=memory.content
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
	
	span = start_span("store_procedural", input={"user_id": state.get("user_id")})
	
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
	
	span = start_span("store_portfolio", input={"user_id": state.get("user_id")})
	
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
	
	span = start_span("summarize_storage", input={"user_id": state.get("user_id")})
	
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
	
	span = start_span("ingestion_finalize", input={})
	
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
	"""Determine if a memory should be stored as episodic"""
	event_tags = {'event', 'meeting', 'conversation', 'activity', 'trip', 'workout'}
	has_event_tag = any(tag in event_tags for tag in tags)
	
	layer = item.get("layer", "")
	is_short_term = layer == "short-term"
	
	mtype = item.get("type", "")
	is_explicit = mtype == "explicit"
	
	is_episodic = has_event_tag or (is_short_term and is_explicit)
	
	# Debug logging
	logger.debug("[_is_episodic] tags=%s layer=%s type=%s has_event_tag=%s result=%s", 
	            tags, layer, mtype, has_event_tag, is_episodic)
	
	return is_episodic


def _is_procedural(item: Dict[str, Any], tags: List[str]) -> bool:
	"""Determine if a memory should be stored as procedural"""
	skill_tags = {'skill', 'learning', 'practice', 'technique', 'method', 'process', 'workflow'}
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
	
	span = start_span("ingestion_finalize_early", input={})
	
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
	graph.add_edge("build_memories", "extract_profile")
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
	
	# Use LangChain's native Langfuse callback handler
	if is_langfuse_enabled():
		try:
			from langfuse.callback import CallbackHandler
			
			# Create Langfuse callback handler with proper configuration
			langfuse_handler = CallbackHandler(
				public_key=get_langfuse_public_key(),
				secret_key=get_langfuse_secret_key(),
				host=get_langfuse_host(),
				trace_name="unified_memory_ingestion",
				user_id=request.user_id,
				metadata={
					"history_length": len(request.history),
					"endpoint": "/v1/store"
				},
				version="1.0.0",
				session_id=f"session_{request.user_id}"
			)
			
			logger.info("[unified_graph] Starting with Langfuse callback handler for user_id=%s", request.user_id)
			
			# Run graph with LangChain callback - this will create proper hierarchy
			final_state: Dict[str, Any] = compiled_graph.invoke(
				initial_state,
				config={
					"callbacks": [langfuse_handler],
					"run_name": "unified_memory_ingestion"
				}
			)
			
			# Flush to ensure all traces are sent
			langfuse_handler.flush()
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

