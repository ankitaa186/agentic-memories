"""
Emotional Memory Service

Handles emotional states, patterns, and context tracking.
Stores in TimescaleDB for time-series emotional data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from src.dependencies.timescale import get_timescale_conn
from src.dependencies.neo4j_client import get_neo4j_driver
from src.dependencies.chroma import get_chroma_client


class EmotionalState(Enum):
    """Emotional state categories"""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    CALM = "calm"
    EXCITEMENT = "excitement"
    ANXIETY = "anxiety"
    CONTENTMENT = "contentment"


@dataclass
class EmotionalMemory:
    """Emotional memory data structure"""
    id: str
    user_id: str
    timestamp: datetime
    emotional_state: str
    valence: float  # -1.0 to 1.0 (negative to positive)
    arousal: float  # 0.0 to 1.0 (calm to excited)
    dominance: Optional[float] = None  # 0.0 to 1.0 (submissive to dominant)
    context: Optional[str] = None
    trigger_event: Optional[str] = None
    intensity: Optional[float] = None  # 0.0 to 1.0
    duration_minutes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EmotionalPattern:
    """Emotional pattern data structure"""
    id: str
    user_id: str
    pattern_type: str  # "daily", "weekly", "seasonal", "triggered"
    start_time: datetime
    end_time: Optional[datetime]
    dominant_emotion: str
    average_valence: float
    average_arousal: float
    frequency: int  # How many times this pattern occurred
    confidence: float  # 0.0 to 1.0
    triggers: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class EmotionalMemoryService:
    """Service for managing emotional memories and patterns"""
    
    def __init__(self):
        self.timescale_conn = get_timescale_conn()
        self.neo4j_driver = get_neo4j_driver()
        self.chroma_client = get_chroma_client()
        self.collection_name = "emotional_memories"
    
    def record_emotional_state(self, user_id: str, emotional_state: str,
                             valence: float, arousal: float,
                             context: Optional[str] = None,
                             trigger_event: Optional[str] = None,
                             intensity: Optional[float] = None,
                             dominance: Optional[float] = None) -> str:
        """
        Record a new emotional state
        
        Args:
            user_id: User ID
            emotional_state: Emotional state name
            valence: Valence score (-1.0 to 1.0)
            arousal: Arousal score (0.0 to 1.0)
            context: Optional context description
            trigger_event: Optional triggering event
            intensity: Optional intensity score (0.0 to 1.0)
            dominance: Optional dominance score (0.0 to 1.0)
            
        Returns:
            str: Memory ID
        """
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Calculate intensity if not provided
        if intensity is None:
            intensity = self._calculate_intensity(valence, arousal)
        
        # Create emotional memory
        memory = EmotionalMemory(
            id=memory_id,
            user_id=user_id,
            timestamp=timestamp,
            emotional_state=emotional_state,
            valence=valence,
            arousal=arousal,
            dominance=dominance,
            context=context,
            trigger_event=trigger_event,
            intensity=intensity,
            metadata={"recorded_at": timestamp.isoformat()}
        )
        
        # Store in TimescaleDB
        self._store_emotional_memory(memory)
        
        # Update emotional patterns
        self._update_emotional_patterns(user_id, memory)
        
        # Store in ChromaDB for semantic search
        self._store_in_chroma(memory)
        
        return memory_id
    
    def _store_emotional_memory(self, memory: EmotionalMemory) -> None:
        """Store emotional memory in TimescaleDB"""
        if not self.timescale_conn:
            raise Exception("TimescaleDB connection not available")
        
        try:
            with self.timescale_conn.cursor() as cur:
                import json
                cur.execute("""
                    INSERT INTO emotional_memories (
                        id, user_id, timestamp, emotional_state, valence, arousal,
                        dominance, context, trigger_event, intensity, duration_minutes, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    memory.id,
                    memory.user_id,
                    memory.timestamp,
                    memory.emotional_state,
                    memory.valence,
                    memory.arousal,
                    memory.dominance,
                    memory.context,
                    memory.trigger_event,
                    memory.intensity,
                    memory.duration_minutes,
                    json.dumps(memory.metadata) if memory.metadata else None
                ))
            # Commit the transaction
            self.timescale_conn.commit()
        except Exception as e:
            # Rollback on error
            self.timescale_conn.rollback()
            print(f"Error storing emotional memory in TimescaleDB: {e}")
            raise
    
    def _store_in_chroma(self, memory: EmotionalMemory) -> None:
        """Store emotional memory in ChromaDB for semantic search"""
        if not self.chroma_client:
            return
        
        try:
            # Create searchable text
            search_text = f"{memory.emotional_state} {memory.context or ''} {memory.trigger_event or ''}"
            
            # Get embeddings
            from src.services.embedding_utils import get_embeddings
            embeddings = get_embeddings([search_text])
            if not embeddings:
                return
            
            # Prepare metadata
            metadata = {
                "user_id": memory.user_id,
                "emotional_state": memory.emotional_state,
                "valence": memory.valence,
                "arousal": memory.arousal,
                "intensity": memory.intensity or 0.0,
                "timestamp": memory.timestamp.isoformat(),
                "context": memory.context or "",
                "trigger_event": memory.trigger_event or ""
            }
            
            # Store in ChromaDB
            collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name
            )
            
            collection.upsert(
                embeddings=embeddings,
                documents=[search_text],
                metadatas=[metadata],
                ids=[memory.id]
            )
            
        except Exception as e:
            print(f"Error storing emotional memory in ChromaDB: {e}")
    
    def _calculate_intensity(self, valence: float, arousal: float) -> float:
        """Calculate emotional intensity from valence and arousal"""
        # Intensity is the distance from neutral (0, 0.5) in valence-arousal space
        valence_distance = abs(valence)
        arousal_distance = abs(arousal - 0.5)
        
        # Combine distances (normalized)
        intensity = (valence_distance + arousal_distance) / 1.5
        return min(intensity, 1.0)
    
    def _update_emotional_patterns(self, user_id: str, memory: EmotionalMemory) -> None:
        """Update emotional patterns based on new memory"""
        if not self.timescale_conn:
            return
        
        try:
            # Get recent emotional states (last 24 hours)
            recent_states = self._get_recent_emotional_states(user_id, hours=24)
            
            # Analyze for patterns
            patterns = self._analyze_emotional_patterns(recent_states)
            
            # Store/update patterns
            for pattern in patterns:
                self._store_emotional_pattern(pattern)
                
        except Exception as e:
            print(f"Error updating emotional patterns: {e}")
    
    def _get_recent_emotional_states(self, user_id: str, hours: int) -> List[EmotionalMemory]:
        """Get recent emotional states for pattern analysis"""
        if not self.timescale_conn:
            return []
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, timestamp, emotional_state, valence, arousal,
                           dominance, context, trigger_event, intensity, duration_minutes, metadata
                    FROM emotional_memories
                    WHERE user_id = %s AND timestamp >= %s
                    ORDER BY timestamp DESC
                """, (user_id, datetime.now(timezone.utc) - timedelta(hours=hours)))
                
                rows = cur.fetchall()
                states = []
                
                for row in rows:
                    states.append(EmotionalMemory(
                        id=row['id'],
                        user_id=row['user_id'],
                        timestamp=row['timestamp'],
                        emotional_state=row['emotional_state'],
                        valence=row['valence'],
                        arousal=row['arousal'],
                        dominance=row['dominance'],
                        context=row['context'],
                        trigger_event=row['trigger_event'],
                        intensity=row['intensity'],
                        duration_minutes=row['duration_minutes'],
                        metadata=row['metadata']
                    ))
                
                return states
                
        except Exception as e:
            print(f"Error getting recent emotional states: {e}")
            return []
    
    def _analyze_emotional_patterns(self, states: List[EmotionalMemory]) -> List[EmotionalPattern]:
        """Analyze emotional states for patterns"""
        if len(states) < 3:  # Need at least 3 states for pattern analysis
            return []
        
        patterns = []
        
        # Group by emotional state
        state_groups = {}
        for state in states:
            if state.emotional_state not in state_groups:
                state_groups[state.emotional_state] = []
            state_groups[state.emotional_state].append(state)
        
        # Find dominant patterns
        for emotional_state, state_list in state_groups.items():
            if len(state_list) >= 3:  # Pattern threshold
                # Calculate averages
                avg_valence = sum(s.valence for s in state_list) / len(state_list)
                avg_arousal = sum(s.arousal for s in state_list) / len(state_list)
                
                # Calculate confidence based on consistency
                valence_variance = sum((s.valence - avg_valence) ** 2 for s in state_list) / len(state_list)
                arousal_variance = sum((s.arousal - avg_arousal) ** 2 for s in state_list) / len(state_list)
                confidence = 1.0 - (valence_variance + arousal_variance) / 2.0
                
                # Extract triggers
                triggers = []
                for state in state_list:
                    if state.trigger_event and state.trigger_event not in triggers:
                        triggers.append(state.trigger_event)
                
                pattern = EmotionalPattern(
                    id=str(uuid.uuid4()),
                    user_id=state_list[0].user_id,
                    pattern_type="triggered",
                    start_time=min(s.timestamp for s in state_list),
                    end_time=max(s.timestamp for s in state_list),
                    dominant_emotion=emotional_state,
                    average_valence=avg_valence,
                    average_arousal=avg_arousal,
                    frequency=len(state_list),
                    confidence=max(confidence, 0.0),
                    triggers=triggers if triggers else None,
                    metadata={"analyzed_at": datetime.now(timezone.utc).isoformat()}
                )
                
                patterns.append(pattern)
        
        return patterns
    
    def _store_emotional_pattern(self, pattern: EmotionalPattern) -> None:
        """Store emotional pattern in TimescaleDB"""
        if not self.timescale_conn:
            return
        
        try:
            with self.timescale_conn.cursor() as cur:
                # Check if pattern already exists
                cur.execute("""
                    SELECT id FROM emotional_patterns 
                    WHERE user_id = %s AND pattern_type = %s AND dominant_emotion = %s
                """, (pattern.user_id, pattern.pattern_type, pattern.dominant_emotion))
                
                existing = cur.fetchone()
                
                if existing:
                    # Update existing pattern
                    cur.execute("""
                        UPDATE emotional_patterns SET
                            end_time = %s,
                            average_valence = %s,
                            average_arousal = %s,
                            frequency = %s,
                            confidence = %s,
                            triggers = %s,
                            metadata = %s
                        WHERE id = %s
                    """, (
                        pattern.end_time,
                        pattern.average_valence,
                        pattern.average_arousal,
                        pattern.frequency,
                        pattern.confidence,
                        pattern.triggers,
                        pattern.metadata,
                        existing['id']
                    ))
                else:
                    # Insert new pattern
                    cur.execute("""
                        INSERT INTO emotional_patterns (
                            id, user_id, pattern_type, start_time, end_time,
                            dominant_emotion, average_valence, average_arousal,
                            frequency, confidence, triggers, metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        pattern.id,
                        pattern.user_id,
                        pattern.pattern_type,
                        pattern.start_time,
                        pattern.end_time,
                        pattern.dominant_emotion,
                        pattern.average_valence,
                        pattern.average_arousal,
                        pattern.frequency,
                        pattern.confidence,
                        pattern.triggers,
                        pattern.metadata
                    ))
            
            # Commit the transaction
            self.timescale_conn.commit()
                    
        except Exception as e:
            # Rollback on error
            self.timescale_conn.rollback()
            print(f"Error storing emotional pattern: {e}")
    
    def get_emotional_state_history(self, user_id: str, hours: int = 24) -> List[EmotionalMemory]:
        """Get emotional state history for a user"""
        return self._get_recent_emotional_states(user_id, hours)
    
    def get_emotional_patterns(self, user_id: str) -> List[EmotionalPattern]:
        """Get emotional patterns for a user"""
        if not self.timescale_conn:
            return []
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, pattern_type, start_time, end_time,
                           dominant_emotion, average_valence, average_arousal,
                           frequency, confidence, triggers, metadata
                    FROM emotional_patterns
                    WHERE user_id = %s
                    ORDER BY confidence DESC, frequency DESC
                """, (user_id,))
                
                rows = cur.fetchall()
                patterns = []
                
                for row in rows:
                    patterns.append(EmotionalPattern(
                        id=row['id'],
                        user_id=row['user_id'],
                        pattern_type=row['pattern_type'],
                        start_time=row['start_time'],
                        end_time=row['end_time'],
                        dominant_emotion=row['dominant_emotion'],
                        average_valence=row['average_valence'],
                        average_arousal=row['average_arousal'],
                        frequency=row['frequency'],
                        confidence=row['confidence'],
                        triggers=row['triggers'],
                        metadata=row['metadata']
                    ))
                
                return patterns
                
        except Exception as e:
            print(f"Error getting emotional patterns: {e}")
            return []
    
    def get_current_emotional_state(self, user_id: str) -> Optional[EmotionalMemory]:
        """Get the most recent emotional state for a user"""
        recent_states = self._get_recent_emotional_states(user_id, hours=1)
        return recent_states[0] if recent_states else None
    
    def predict_emotional_response(self, user_id: str, trigger_event: str) -> Optional[Dict[str, float]]:
        """
        Predict emotional response to a trigger event based on patterns
        
        Args:
            user_id: User ID
            trigger_event: Event that might trigger emotional response
            
        Returns:
            Dict with predicted valence, arousal, and confidence
        """
        patterns = self.get_emotional_patterns(user_id)
        
        # Find patterns triggered by similar events
        relevant_patterns = []
        for pattern in patterns:
            if pattern.triggers and any(trigger_event.lower() in trigger.lower() 
                                     for trigger in pattern.triggers):
                relevant_patterns.append(pattern)
        
        if not relevant_patterns:
            return None
        
        # Weight by confidence and frequency
        total_weight = sum(p.confidence * p.frequency for p in relevant_patterns)
        if total_weight == 0:
            return None
        
        # Calculate weighted averages
        predicted_valence = sum(p.average_valence * p.confidence * p.frequency 
                              for p in relevant_patterns) / total_weight
        predicted_arousal = sum(p.average_arousal * p.confidence * p.frequency 
                              for p in relevant_patterns) / total_weight
        
        # Calculate overall confidence
        avg_confidence = sum(p.confidence for p in relevant_patterns) / len(relevant_patterns)
        
        return {
            "predicted_valence": predicted_valence,
            "predicted_arousal": predicted_arousal,
            "confidence": avg_confidence,
            "based_on_patterns": len(relevant_patterns)
        }
