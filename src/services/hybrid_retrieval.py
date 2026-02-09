"""
Hybrid Retrieval and Ranking Service

Combines multiple retrieval strategies (semantic, temporal, emotional, procedural)
with intelligent ranking and fusion algorithms.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)
from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.dependencies.chroma import get_chroma_client
from src.services.episodic_memory import EpisodicMemoryService
from src.services.emotional_memory import EmotionalMemoryService
from src.services.procedural_memory import ProceduralMemoryService
from src.services.embedding_utils import get_embeddings


def _deserialize_metadata_lists(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Deserialize JSON-stringified lists back to Python lists.

    ChromaDB only supports primitive types in metadata, so lists are
    serialized to JSON strings on storage. This function reverses that.
    """
    if not metadata:
        return metadata

    list_fields = ['persona_tags', 'tags', 'topics', 'people_mentioned', 'participants']
    for field in list_fields:
        if field in metadata and isinstance(metadata[field], str):
            try:
                metadata[field] = json.loads(metadata[field])
            except (json.JSONDecodeError, ValueError):
                pass  # Keep as string if not valid JSON
    return metadata


class RetrievalStrategy(Enum):
    """Retrieval strategy types"""
    SEMANTIC = "semantic"
    TEMPORAL = "temporal"
    EMOTIONAL = "emotional"
    PROCEDURAL = "procedural"
    HYBRID = "hybrid"


@dataclass
class RetrievalResult:
    """Retrieval result with ranking information"""
    memory_id: str
    memory_type: str  # "episodic", "emotional", "procedural", "semantic"
    content: str
    relevance_score: float  # 0.0 to 1.0
    recency_score: float    # 0.0 to 1.0
    importance_score: float # 0.0 to 1.0
    emotional_relevance: Optional[float] = None
    temporal_relevance: Optional[float] = None
    semantic_similarity: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RetrievalQuery:
    """Retrieval query with context and preferences"""
    user_id: str
    query_text: Optional[str] = None
    memory_types: Optional[List[str]] = None  # ["episodic", "emotional", "procedural"]
    time_range: Optional[Tuple[datetime, datetime]] = None
    emotional_context: Optional[Dict[str, float]] = None  # {"valence": 0.5, "arousal": 0.3}
    importance_threshold: Optional[float] = None
    limit: int = 10
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    weight_overrides: Optional[Dict[str, float]] = None


class HybridRetrievalService:
    """Service for hybrid memory retrieval and ranking"""

    def __init__(self):
        self.chroma_client = get_chroma_client()
        self.episodic_service = EpisodicMemoryService()
        self.emotional_service = EmotionalMemoryService()
        self.procedural_service = ProceduralMemoryService()
    
    def retrieve_memories(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """
        Retrieve memories using hybrid approach
        
        Args:
            query: RetrievalQuery object with search parameters
            
        Returns:
            List[RetrievalResult]: Ranked list of memories
        """
        from src.services.tracing import start_span, end_span
        
        span = start_span("hybrid_retrieval", input={
            "user_id": query.user_id,
            "has_query": bool(query.query_text),
            "has_time_range": query.time_range is not None,
            "has_emotional_context": query.emotional_context is not None,
            "strategy": query.strategy.value,
            "limit": query.limit
        })
        
        all_results = []
        
        # 1. Semantic retrieval (query) or browse-all (no query)
        if query.query_text:
            semantic_results = self._semantic_retrieval(query)
            all_results.extend(semantic_results)
        else:
            browse_results = self._browse_all(query)
            all_results.extend(browse_results)
        
        # 2. Temporal retrieval (if time range provided)
        if query.time_range:
            temporal_results = self._temporal_retrieval(query)
            all_results.extend(temporal_results)
        
        # 3. Emotional retrieval (if emotional context provided)
        if query.emotional_context:
            emotional_results = self._emotional_retrieval(query)
            all_results.extend(emotional_results)
        
        # 4. Procedural retrieval (if procedural memories requested)
        if not query.memory_types or "procedural" in query.memory_types:
            procedural_results = self._procedural_retrieval(query)
            all_results.extend(procedural_results)
        
        # 5. Deduplicate and rank results
        unique_results = self._deduplicate_results(all_results)
        ranked_results = self._rank_results(unique_results, query)
        
        # 6. Apply filters and limits
        filtered_results = self._apply_filters(ranked_results, query)
        final_results = filtered_results[:query.limit]
        
        end_span(output={
            "total_raw_results": len(all_results),
            "unique_results": len(unique_results),
            "final_count": len(final_results)
        })
        
        return final_results
    
    def _semantic_retrieval(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Perform semantic search across all memory types"""
        results = []
        
        if not query.query_text or not self.chroma_client:
            return results
        
        try:
            # Get query embeddings
            query_embeddings = get_embeddings([query.query_text])
            if not query_embeddings:
                return results
            
            # Use the standard unified collection used by /v1/store
            from src.services.retrieval import _standard_collection_name
            collection_name = _standard_collection_name()
            try:
                collection = self.chroma_client.get_collection(collection_name)
                search_results = collection.query(
                    query_embeddings=query_embeddings,
                    n_results=query.limit,
                    where={"user_id": query.user_id}
                )
                if search_results and search_results.get('ids') and search_results['ids'][0]:
                    for i, memory_id in enumerate(search_results['ids'][0]):
                        distance = search_results['distances'][0][i] if search_results.get('distances') else 0.0
                        similarity = 1.0 - distance
                        metadata = _deserialize_metadata_lists(search_results['metadatas'][0][i] or {})

                        # Extract timestamp and calculate recency score
                        timestamp_str = metadata.get('timestamp')
                        if timestamp_str:
                            try:
                                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                recency = self._calculate_recency_score(timestamp)
                            except (ValueError, TypeError):
                                recency = 0.5
                        else:
                            recency = 0.5

                        # Extract importance from metadata
                        try:
                            importance = float(metadata.get('importance', 0.5))
                        except (ValueError, TypeError):
                            importance = 0.5

                        result = RetrievalResult(
                            memory_id=memory_id,
                            memory_type="semantic",
                            content=search_results['documents'][0][i],
                            relevance_score=similarity,
                            recency_score=recency,
                            importance_score=importance,
                            semantic_similarity=similarity,
                            metadata=metadata
                        )
                        results.append(result)
            except Exception as e:
                logger.error("Error searching collection %s: %s", collection_name, e)
        
        except Exception as e:
            logger.error("Error in semantic retrieval: %s", e)
        
        return results
    
    def _browse_all(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Fetch all memories across every layer when no query text is provided (browse mode)."""
        results = []

        # 1. ChromaDB (semantic / short-term / long-term)
        if self.chroma_client:
            try:
                from src.services.retrieval import _standard_collection_name
                collection_name = _standard_collection_name()
                collection = self.chroma_client.get_collection(collection_name)
                browse_results = collection.get(
                    where={"user_id": query.user_id},
                    limit=query.limit,
                )
                ids = browse_results.get("ids", [])
                docs = browse_results.get("documents", [])
                metas = browse_results.get("metadatas", [])

                for i, memory_id in enumerate(ids):
                    if i >= len(docs) or i >= len(metas):
                        continue
                    metadata = _deserialize_metadata_lists(metas[i] or {})
                    timestamp_str = metadata.get("timestamp")
                    recency = 0.5
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                            recency = self._calculate_recency_score(timestamp)
                        except (ValueError, TypeError):
                            pass
                    try:
                        importance = float(metadata.get("importance", 0.5))
                    except (ValueError, TypeError):
                        importance = 0.5

                    results.append(RetrievalResult(
                        memory_id=memory_id,
                        memory_type=metadata.get("layer", "semantic"),
                        content=docs[i],
                        relevance_score=0.5,
                        recency_score=recency,
                        importance_score=importance,
                        semantic_similarity=0.0,
                        metadata=metadata,
                    ))
            except Exception as e:
                logger.error("Error in browse-all ChromaDB retrieval: %s", e)

        # 2. Episodic memories (TimescaleDB)
        # Build seen_ids from both memory_id AND typed_table_id to avoid duplicates
        # When stored via direct API, ChromaDB has mem_XXXX with typed_table_id metadata
        # pointing to the UUID in the typed table
        seen_ids = {r.memory_id for r in results}
        for r in results:
            typed_id = (r.metadata or {}).get("typed_table_id")
            if typed_id:
                seen_ids.add(typed_id)
        conn = get_timescale_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, content, event_timestamp, importance_score,
                               emotional_valence, emotional_arousal, location, participants, tags, metadata
                        FROM episodic_memories
                        WHERE user_id = %s
                        ORDER BY event_timestamp DESC
                        LIMIT %s
                    """, (query.user_id, query.limit))
                    for row in cur.fetchall():
                        mid = str(row["id"])
                        if mid in seen_ids:
                            continue
                        seen_ids.add(mid)
                        recency = self._calculate_recency_score(row["event_timestamp"]) if row.get("event_timestamp") else 0.5
                        meta = row.get("metadata") or {}
                        if row.get("event_timestamp"):
                            meta["timestamp"] = row["event_timestamp"].isoformat()
                        meta["layer"] = "episodic"
                        meta["emotional_valence"] = row.get("emotional_valence")
                        meta["emotional_arousal"] = row.get("emotional_arousal")
                        results.append(RetrievalResult(
                            memory_id=mid,
                            memory_type="episodic",
                            content=row["content"] or "",
                            relevance_score=0.5,
                            recency_score=recency,
                            importance_score=float(row.get("importance_score") or 0.5),
                            semantic_similarity=0.0,
                            metadata=meta,
                        ))
                conn.commit()

                # 3. Emotional memories (TimescaleDB)
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, context, timestamp, valence, arousal, intensity, emotional_state
                        FROM emotional_memories
                        WHERE user_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """, (query.user_id, query.limit))
                    for row in cur.fetchall():
                        mid = str(row["id"])
                        if mid in seen_ids:
                            continue
                        seen_ids.add(mid)
                        recency = self._calculate_recency_score(row["timestamp"]) if row.get("timestamp") else 0.5
                        meta = {
                            "layer": "emotional",
                            "timestamp": row["timestamp"].isoformat() if row.get("timestamp") else None,
                            "emotional_valence": row.get("valence"),
                            "emotional_arousal": row.get("arousal"),
                            "dominant_emotion": row.get("emotional_state"),
                        }
                        results.append(RetrievalResult(
                            memory_id=mid,
                            memory_type="emotional",
                            content=row["context"] or "",
                            relevance_score=0.5,
                            recency_score=recency,
                            importance_score=float(row.get("intensity") or 0.5),
                            semantic_similarity=0.0,
                            metadata=meta,
                        ))
                conn.commit()
            except Exception as e:
                logger.error("Error in browse-all TimescaleDB retrieval: %s", e)
            finally:
                release_timescale_conn(conn)

        return results

    def _temporal_retrieval(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Retrieve memories by time range"""
        results = []
        
        if not query.time_range:
            return results
        
        conn = get_timescale_conn()
        if not conn:
            return results
        
        start_time, end_time = query.time_range
        
        try:
            with conn.cursor() as cur:
                # Search episodic memories
                cur.execute("""
                    SELECT id, content, event_timestamp, importance_score, emotional_valence, emotional_arousal
                    FROM episodic_memories
                    WHERE user_id = %s AND event_timestamp BETWEEN %s AND %s
                    ORDER BY event_timestamp DESC
                """, (query.user_id, start_time, end_time))
                
                episodic_rows = cur.fetchall()
                
                for row in episodic_rows:
                    # Calculate temporal relevance (closer to query time = higher score)
                    time_diff = abs((row['event_timestamp'] - start_time).total_seconds())
                    max_diff = (end_time - start_time).total_seconds()
                    temporal_relevance = 1.0 - (time_diff / max_diff) if max_diff > 0 else 1.0
                    
                    result = RetrievalResult(
                        memory_id=row['id'],
                        memory_type="episodic",
                        content=row['content'],
                        relevance_score=temporal_relevance,
                        recency_score=self._calculate_recency_score(row['event_timestamp']),
                        importance_score=row['importance_score'] or 0.5,
                        temporal_relevance=temporal_relevance,
                        metadata={
                            "timestamp": row['event_timestamp'].isoformat(),
                            "emotional_valence": row['emotional_valence'],
                            "emotional_arousal": row['emotional_arousal']
                        }
                    )
                    results.append(result)
                
                # Search emotional memories
                cur.execute("""
                    SELECT id, context, timestamp, valence, arousal, intensity
                    FROM emotional_memories
                    WHERE user_id = %s AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp DESC
                """, (query.user_id, start_time, end_time))
                
                emotional_rows = cur.fetchall()
                
                for row in emotional_rows:
                    time_diff = abs((row['timestamp'] - start_time).total_seconds())
                    max_diff = (end_time - start_time).total_seconds()
                    temporal_relevance = 1.0 - (time_diff / max_diff) if max_diff > 0 else 1.0
                    
                    result = RetrievalResult(
                        memory_id=row['id'],
                        memory_type="emotional",
                        content=row['context'] or "",
                        relevance_score=temporal_relevance,
                        recency_score=self._calculate_recency_score(row['timestamp']),
                        importance_score=row['intensity'] or 0.5,
                        temporal_relevance=temporal_relevance,
                        metadata={
                            "timestamp": row['timestamp'].isoformat(),
                            "valence": row['valence'],
                            "arousal": row['arousal'],
                            "intensity": row['intensity']
                        }
                    )
                    results.append(result)
            
            # Commit read-only transaction before releasing
            conn.commit()
                    
        except Exception as e:
            logger.error("Error in temporal retrieval: %s", e)
        
        return results
    
    def _emotional_retrieval(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Retrieve memories based on emotional context"""
        results = []
        
        if not query.emotional_context:
            return results
        
        conn = get_timescale_conn()
        if not conn:
            return results
        
        try:
            target_valence = query.emotional_context.get('valence', 0.0)
            target_arousal = query.emotional_context.get('arousal', 0.5)
            
            with conn.cursor() as cur:
                # Search emotional memories with similar emotional state
                cur.execute("""
                    SELECT id, context, timestamp, valence, arousal, intensity, emotional_state
                    FROM emotional_memories
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (query.user_id,))
                
                emotional_rows = cur.fetchall()
                
                for row in emotional_rows:
                    # Calculate emotional similarity
                    valence_diff = abs(row['valence'] - target_valence)
                    arousal_diff = abs(row['arousal'] - target_arousal)
                    emotional_similarity = 1.0 - (valence_diff + arousal_diff) / 2.0
                    
                    if emotional_similarity > 0.3:  # Threshold for emotional relevance
                        result = RetrievalResult(
                            memory_id=row['id'],
                            memory_type="emotional",
                            content=row['context'] or "",
                            relevance_score=emotional_similarity,
                            recency_score=self._calculate_recency_score(row['timestamp']),
                            importance_score=row['intensity'] or 0.5,
                            emotional_relevance=emotional_similarity,
                            metadata={
                                "timestamp": row['timestamp'].isoformat(),
                                "valence": row['valence'],
                                "arousal": row['arousal'],
                                "intensity": row['intensity'],
                                "emotional_state": row['emotional_state']
                            }
                        )
                        results.append(result)
                
                # Search episodic memories with emotional context
                cur.execute("""
                    SELECT id, content, event_timestamp, emotional_valence, emotional_arousal, importance_score
                    FROM episodic_memories
                    WHERE user_id = %s 
                    AND emotional_valence IS NOT NULL 
                    AND emotional_arousal IS NOT NULL
                    ORDER BY event_timestamp DESC
                    LIMIT 50
                """, (query.user_id,))
                
                episodic_rows = cur.fetchall()
                
                for row in episodic_rows:
                    valence_diff = abs(row['emotional_valence'] - target_valence)
                    arousal_diff = abs(row['emotional_arousal'] - target_arousal)
                    emotional_similarity = 1.0 - (valence_diff + arousal_diff) / 2.0
                    
                    if emotional_similarity > 0.3:
                        result = RetrievalResult(
                            memory_id=row['id'],
                            memory_type="episodic",
                            content=row['content'],
                            relevance_score=emotional_similarity,
                            recency_score=self._calculate_recency_score(row['event_timestamp']),
                            importance_score=row['importance_score'] or 0.5,
                            emotional_relevance=emotional_similarity,
                            metadata={
                                "timestamp": row['event_timestamp'].isoformat(),
                                "valence": row['emotional_valence'],
                                "arousal": row['emotional_arousal']
                            }
                        )
                        results.append(result)
            
            # Commit read-only transaction before releasing
            conn.commit()
                        
        except Exception as e:
            logger.error("Error in emotional retrieval: %s", e)
        finally:
            if conn:
                release_timescale_conn(conn)
        
        return results
    
    def _procedural_retrieval(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Retrieve procedural memories"""
        results = []
        
        try:
            # Get user's skills
            skills = self.procedural_service.get_skills(query.user_id)
            
            for skill in skills:
                # Calculate relevance based on recent practice and success
                recency_score = self._calculate_recency_score(skill.last_practiced) if skill.last_practiced else 0.0
                importance_score = skill.success_rate or 0.5
                
                # Create searchable content
                content = f"{skill.skill_name}: {' '.join(skill.steps or [])}"
                if skill.context:
                    content += f" (Context: {skill.context})"
                
                result = RetrievalResult(
                    memory_id=skill.id,
                    memory_type="procedural",
                    content=content,
                    relevance_score=0.7,  # Base relevance for skills
                    recency_score=recency_score,
                    importance_score=importance_score,
                    metadata={
                        "skill_name": skill.skill_name,
                        "proficiency_level": skill.proficiency_level,
                        "practice_count": skill.practice_count,
                        "success_rate": skill.success_rate,
                        "last_practiced": skill.last_practiced.isoformat() if skill.last_practiced else None,
                        "context": skill.context,
                        "tags": skill.tags
                    }
                )
                results.append(result)
                
        except Exception as e:
            logger.error("Error in procedural retrieval: %s", e)
        
        return results
    
    def _calculate_recency_score(self, timestamp: datetime) -> float:
        """Calculate recency score based on timestamp"""
        if not timestamp:
            return 0.0
        
        now = datetime.now(timezone.utc)
        time_diff = (now - timestamp).total_seconds()
        
        # Exponential decay: more recent = higher score
        # Score drops to 0.5 after 7 days, 0.1 after 30 days
        decay_rate = 0.1  # Adjust for desired decay curve
        recency_score = 1.0 / (1.0 + decay_rate * time_diff / 86400)  # 86400 seconds = 1 day
        
        return min(recency_score, 1.0)
    
    def _deduplicate_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Remove duplicate results based on memory_id and typed_table_id.

        When memories are stored via direct API with typed fields (episodic, emotional, procedural),
        they get stored in BOTH ChromaDB (with mem_ prefix) AND the typed TimescaleDB table (with UUID).
        The ChromaDB entry's metadata contains 'typed_table_id' pointing to the typed table entry.

        This deduplication ensures we don't return both entries for the same logical memory.
        We prefer the ChromaDB entry (mem_ prefix) as it has richer metadata.
        """
        seen_ids = set()
        seen_typed_ids = set()  # Track typed_table_ids we've seen
        unique_results = []

        for result in results:
            # Check if this is a typed table entry that we've already seen via ChromaDB
            if result.memory_id in seen_typed_ids:
                continue

            if result.memory_id not in seen_ids:
                seen_ids.add(result.memory_id)

                # If this result has a typed_table_id, track it to skip the typed table duplicate
                typed_table_id = (result.metadata or {}).get("typed_table_id")
                if typed_table_id:
                    seen_typed_ids.add(typed_table_id)

                unique_results.append(result)

        return unique_results
    
    def _rank_results(self, results: List[RetrievalResult], query: RetrievalQuery) -> List[RetrievalResult]:
        """Rank results using hybrid scoring"""
        for result in results:
            # Calculate composite score
            composite_score = self._calculate_composite_score(result, query)
            result.relevance_score = composite_score
        
        # Sort by composite score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return results
    
    def _calculate_composite_score(self, result: RetrievalResult, query: RetrievalQuery) -> float:
        """Calculate composite relevance score"""
        # Base weights
        semantic_weight = 0.4
        temporal_weight = 0.3
        importance_weight = 0.2
        emotional_weight = 0.1
        
        # Adjust weights based on query strategy
        if query.strategy == RetrievalStrategy.SEMANTIC:
            semantic_weight = 0.7
            temporal_weight = 0.1
            importance_weight = 0.1
            emotional_weight = 0.1
        elif query.strategy == RetrievalStrategy.TEMPORAL:
            semantic_weight = 0.1
            temporal_weight = 0.7
            importance_weight = 0.1
            emotional_weight = 0.1
        elif query.strategy == RetrievalStrategy.EMOTIONAL:
            semantic_weight = 0.1
            temporal_weight = 0.1
            importance_weight = 0.1
            emotional_weight = 0.7
        
        # Apply persona or caller overrides when provided
        if query.weight_overrides:
            semantic_weight = query.weight_overrides.get("semantic", semantic_weight)
            temporal_weight = query.weight_overrides.get("temporal", temporal_weight)
            importance_weight = query.weight_overrides.get("importance", importance_weight)
            emotional_weight = query.weight_overrides.get("emotional", emotional_weight)
            total = semantic_weight + temporal_weight + importance_weight + emotional_weight
            if total > 0:
                semantic_weight /= total
                temporal_weight /= total
                importance_weight /= total
                emotional_weight /= total

        # Calculate weighted score
        score = 0.0
        
        # Semantic similarity
        if result.semantic_similarity is not None:
            score += semantic_weight * result.semantic_similarity
        else:
            score += semantic_weight * 0.5  # Default if no semantic score
        
        # Temporal relevance
        if result.temporal_relevance is not None:
            score += temporal_weight * result.temporal_relevance
        else:
            score += temporal_weight * result.recency_score
        
        # Importance
        score += importance_weight * result.importance_score
        
        # Emotional relevance
        if result.emotional_relevance is not None:
            score += emotional_weight * result.emotional_relevance
        else:
            score += emotional_weight * 0.5  # Default if no emotional score
        
        return min(score, 1.0)
    
    def _apply_filters(self, results: List[RetrievalResult], query: RetrievalQuery) -> List[RetrievalResult]:
        """Apply filters to results"""
        filtered_results = results
        
        # Filter by memory types
        if query.memory_types:
            filtered_results = [r for r in filtered_results if r.memory_type in query.memory_types]
        
        # Filter by importance threshold
        if query.importance_threshold is not None:
            filtered_results = [r for r in filtered_results if r.importance_score >= query.importance_threshold]
        
        return filtered_results
    
    def get_memory_context(self, user_id: str, memory_id: str, 
                          context_window: int = 5) -> List[RetrievalResult]:
        """
        Get contextual memories around a specific memory
        
        Args:
            user_id: User ID
            memory_id: Target memory ID
            context_window: Number of memories before/after to retrieve
            
        Returns:
            List[RetrievalResult]: Contextual memories
        """
        conn = get_timescale_conn()
        if not conn:
            return []
        
        try:
            # Get the target memory timestamp
            target_timestamp = None
            
            with conn.cursor() as cur:
                # Try episodic memories first
                cur.execute("""
                    SELECT event_timestamp FROM episodic_memories 
                    WHERE id = %s AND user_id = %s
                """, (memory_id, user_id))
                
                row = cur.fetchone()
                if row:
                    target_timestamp = row['event_timestamp']
                else:
                    # Try emotional memories
                    cur.execute("""
                        SELECT timestamp FROM emotional_memories 
                        WHERE id = %s AND user_id = %s
                    """, (memory_id, user_id))
                    
                    row = cur.fetchone()
                    if row:
                        target_timestamp = row['timestamp']
            
            if not target_timestamp:
                return []
            
            # Get memories around the target timestamp
            time_range = timedelta(hours=24)  # 24-hour window
            start_time = target_timestamp - time_range
            end_time = target_timestamp + time_range
            
            context_query = RetrievalQuery(
                user_id=user_id,
                time_range=(start_time, end_time),
                limit=context_window * 2
            )
            
            context_results = self.retrieve_memories(context_query)
            
            # Sort by temporal proximity to target
            context_results.sort(key=lambda x: abs(
                datetime.fromisoformat(x.metadata.get('timestamp', '')) - target_timestamp
            ) if x.metadata and x.metadata.get('timestamp') else float('inf')
            )
            
            return context_results[:context_window]
            
        except Exception as e:
            logger.error("Error getting memory context: %s", e)
            return []
        finally:
            if conn:
                release_timescale_conn(conn)
    
    def get_related_memories(self, user_id: str, memory_id: str,
                           similarity_threshold: float = 0.7) -> List[RetrievalResult]:
        """
        Get memories related to a specific memory.

        Note: Graph-based relationship queries were removed as part of Neo4j removal.
        This method now returns an empty list. Future implementations could use
        semantic similarity via ChromaDB or temporal proximity via TimescaleDB.

        Args:
            user_id: User ID
            memory_id: Target memory ID
            similarity_threshold: Minimum similarity threshold

        Returns:
            List[RetrievalResult]: Empty list (graph relationships not available)
        """
        # Neo4j graph relationships removed - return empty list
        # Future: implement using ChromaDB semantic similarity or TimescaleDB temporal queries
        return []
