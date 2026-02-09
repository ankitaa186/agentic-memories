"""
Memory Router Service

Routes extracted memories to appropriate storage layers based on memory type and content.
Coordinates across ChromaDB, TimescaleDB, and PostgreSQL.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from src.models import Memory
from src.services.episodic_memory import EpisodicMemoryService, EpisodicMemory
from src.services.emotional_memory import EmotionalMemoryService
from src.services.procedural_memory import ProceduralMemoryService
from src.services.portfolio_service import PortfolioService

logger = logging.getLogger("agentic_memories.memory_router")


class MemoryRouter:
	"""Routes memories to appropriate storage backends"""
	
	def __init__(self):
		# Initialize all memory services
		try:
			self.episodic_service = EpisodicMemoryService()
		except Exception as e:
			logger.warning(f"Failed to initialize EpisodicMemoryService: {e}")
			self.episodic_service = None
			
		try:
			self.emotional_service = EmotionalMemoryService()
		except Exception as e:
			logger.warning(f"Failed to initialize EmotionalMemoryService: {e}")
			self.emotional_service = None
			
		try:
			self.procedural_service = ProceduralMemoryService()
		except Exception as e:
			logger.warning(f"Failed to initialize ProceduralMemoryService: {e}")
			self.procedural_service = None
			
		try:
			self.portfolio_service = PortfolioService()
		except Exception as e:
			logger.warning(f"Failed to initialize PortfolioService: {e}")
			self.portfolio_service = None
	
	def route_memories(self, user_id: str, memories: List[Memory], memory_ids: List[str]) -> Dict[str, Any]:
		"""
		Route memories to appropriate storage backends
		
		Args:
			user_id: User ID
			memories: List of Memory objects
			memory_ids: List of memory IDs (from ChromaDB)
			
		Returns:
			Dict with routing statistics
		"""
		stats = {
			"episodic_stored": 0,
			"emotional_stored": 0,
			"procedural_stored": 0,
			"portfolio_stored": 0,
			"errors": []
		}
		
		for i, memory in enumerate(memories):
			memory_id = memory_ids[i] if i < len(memory_ids) else None
			
			try:
				# 1. Route to episodic memory if it's an event
				if self._is_episodic(memory):
					success = self._store_episodic(user_id, memory, memory_id)
					if success:
						stats["episodic_stored"] += 1
				
				# 2. Detect and store emotional states
				emotional_data = self._extract_emotional_data(memory)
				if emotional_data and self.emotional_service:
					success = self._store_emotional(user_id, emotional_data, memory_id)
					if success:
						stats["emotional_stored"] += 1
				
				# 3. Route to procedural memory if it's a skill/practice
				if self._is_procedural(memory):
					success = self._store_procedural(user_id, memory, memory_id)
					if success:
						stats["procedural_stored"] += 1
				
				# 4. Route to portfolio service if it contains finance data
				portfolio_meta = memory.metadata.get('portfolio')
				if portfolio_meta and self.portfolio_service:
					success = self._store_portfolio(user_id, portfolio_meta, memory_id)
					if success:
						stats["portfolio_stored"] += 1
						
			except Exception as e:
				error_msg = f"Error routing memory {memory_id}: {str(e)}"
				logger.error(error_msg)
				stats["errors"].append(error_msg)
		
		logger.info(
			"[memory_router] user_id=%s episodic=%d emotional=%d procedural=%d portfolio=%d errors=%d",
			user_id, 
			stats["episodic_stored"],
			stats["emotional_stored"],
			stats["procedural_stored"],
			stats["portfolio_stored"],
			len(stats["errors"])
		)
		
		return stats
	
	def _is_episodic(self, memory: Memory) -> bool:
		"""Determine if a memory should be stored as episodic"""
		# Episodic memories are events with temporal context
		tags = memory.metadata.get('tags', [])
		
		# Event-related tags
		event_tags = {'event', 'meeting', 'conversation', 'activity', 'trip', 'workout'}
		has_event_tag = any(tag in event_tags for tag in tags)
		
		# Short-term memories are often episodic
		is_short_term = memory.layer == "short-term"
		
		# Explicit type memories with context
		is_explicit = memory.type == "explicit"
		
		return has_event_tag or (is_short_term and is_explicit)
	
	def _is_procedural(self, memory: Memory) -> bool:
		"""Determine if a memory should be stored as procedural"""
		tags = memory.metadata.get('tags', [])
		
		# Skill/learning-related tags
		skill_tags = {'skill', 'learning', 'practice', 'technique', 'method', 'process', 'workflow'}
		has_skill_tag = any(tag in skill_tags for tag in tags)
		
		# Learning journal entries
		has_learning_journal = memory.metadata.get('learning_journal') is not None
		
		return has_skill_tag or has_learning_journal
	
	def _extract_emotional_data(self, memory: Memory) -> Optional[Dict[str, Any]]:
		"""Extract emotional indicators from memory"""
		# Simple sentiment detection based on content and tags
		content = memory.content.lower()
		tags = memory.metadata.get('tags', [])
		
		# Emotional keywords
		positive_words = {'happy', 'excited', 'great', 'love', 'amazing', 'wonderful', 'excellent'}
		negative_words = {'sad', 'angry', 'frustrated', 'worried', 'anxious', 'stressed', 'upset'}
		
		has_positive = any(word in content for word in positive_words)
		has_negative = any(word in content for word in negative_words)
		
		# Emotional tags
		emotion_tags = {'emotion', 'feeling', 'mood'}
		has_emotion_tag = any(tag in emotion_tags for tag in tags)
		
		if has_positive or has_negative or has_emotion_tag:
			# Determine valence (-1 to 1)
			valence = 0.0
			if has_positive:
				valence += 0.5
			if has_negative:
				valence -= 0.5
			
			# Default arousal (intensity)
			arousal = 0.5
			if 'excited' in content or 'angry' in content:
				arousal = 0.8
			elif 'calm' in content or 'peaceful' in content:
				arousal = 0.2
			
			return {
				"valence": valence,
				"arousal": arousal,
				"content": memory.content,
				"context": memory.metadata.get('tags', [])
			}
		
		return None
	
	def _store_episodic(self, user_id: str, memory: Memory, memory_id: Optional[str]) -> bool:
		"""Store memory in episodic storage (TimescaleDB + ChromaDB)"""
		if not self.episodic_service:
			return False
		
		from src.services.tracing import start_span, end_span
		import uuid
		
		span = start_span("episodic_memory_storage", input={
			"user_id": user_id,
			"memory_id": memory_id
		})
		
		try:
			episodic_memory = EpisodicMemory(
				id=memory_id or str(uuid.uuid4()),
				user_id=user_id,
				event_type=memory.type,
				event_timestamp=memory.timestamp or datetime.now(timezone.utc),
				content=memory.content,
				location=memory.metadata.get('location'),
				participants=memory.metadata.get('participants'),
				emotional_valence=0.0,  # Will be updated by emotional service
				emotional_arousal=0.0,
				importance_score=memory.confidence,
				tags=memory.metadata.get('tags', []),
				metadata=memory.metadata
			)
			
			success = self.episodic_service.store_memory(episodic_memory)
			
			end_span(output={"success": success})
			return success
			
		except Exception as e:
			end_span(output={"error": str(e)}, level="ERROR")
			logger.error(f"Failed to store episodic memory: {e}")
			return False
	
	def _store_emotional(self, user_id: str, emotional_data: Dict[str, Any], memory_id: Optional[str]) -> bool:
		"""Store emotional state in TimescaleDB"""
		if not self.emotional_service:
			return False
		
		from src.services.tracing import start_span, end_span
		
		span = start_span("emotional_state_storage", input={
			"user_id": user_id,
			"valence": emotional_data.get("valence"),
			"arousal": emotional_data.get("arousal")
		})
		
		try:
			emotional_state = self._classify_emotion(
				emotional_data.get("valence", 0.0),
				emotional_data.get("arousal", 0.5)
			)
			
			# Use the record_emotional_state method
			# Context should be actual content text, not stringified tags/context list
			context_value = emotional_data.get("content", "")
			if not context_value:
				# Fallback: join context list items if content is empty
				ctx = emotional_data.get("context", [])
				context_value = ", ".join(ctx) if isinstance(ctx, list) else str(ctx)

			success = self.emotional_service.record_emotional_state(
				user_id=user_id,
				emotional_state=emotional_state,
				valence=emotional_data.get("valence", 0.0),
				arousal=emotional_data.get("arousal", 0.5),
				context=context_value,
				trigger_event=emotional_data.get("trigger", "")
			)
			
			end_span(output={"success": success})
			return success
			
		except Exception as e:
			end_span(output={"error": str(e)}, level="ERROR")
			logger.error(f"Failed to store emotional state: {e}")
			return False
	
	def _classify_emotion(self, valence: float, arousal: float) -> str:
		"""Classify emotion based on valence and arousal"""
		if valence > 0.3:
			if arousal > 0.6:
				return "excited"
			else:
				return "happy"
		elif valence < -0.3:
			if arousal > 0.6:
				return "angry"
			else:
				return "sad"
		else:
			if arousal > 0.6:
				return "anxious"
			else:
				return "neutral"
	
	def _store_procedural(self, user_id: str, memory: Memory, memory_id: Optional[str]) -> bool:
		"""Store procedural memory in PostgreSQL"""
		if not self.procedural_service:
			return False
		
		from src.services.tracing import start_span, end_span
		
		span = start_span("procedural_memory_storage", input={
			"user_id": user_id,
			"memory_id": memory_id
		})
		
		try:
			learning_journal = memory.metadata.get('learning_journal') or {}
			skill_name = learning_journal.get('topic') or memory.content[:100]
			proficiency_level = learning_journal.get('progress_level', 'beginner')
			
			# Use the practice_skill method
			success = self.procedural_service.practice_skill(
				user_id=user_id,
				skill_name=skill_name,
				proficiency_level=proficiency_level,
				success_rate=memory.confidence,
				notes=memory.content
			)
			
			end_span(output={"success": success})
			return success
			
		except Exception as e:
			end_span(output={"error": str(e)}, level="ERROR")
			logger.error(f"Failed to store procedural memory: {e}")
			return False
	
	def _store_portfolio(self, user_id: str, portfolio_meta: Dict[str, Any], memory_id: Optional[str]) -> bool:
		"""Store portfolio data in PostgreSQL"""
		if not self.portfolio_service:
			return False
		
		try:
			self.portfolio_service.upsert_holding_from_memory(
				user_id=user_id,
				portfolio_metadata=portfolio_meta,
				memory_id=memory_id
			)
			return True
		except Exception as e:
			logger.error(f"Failed to store portfolio data: {e}")
			return False

