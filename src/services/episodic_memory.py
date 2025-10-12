"""
Episodic Memory Service

Handles episodic memories - time-stamped events with emotional context.
Stores in TimescaleDB for time-series optimization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from src.dependencies.timescale import get_timescale_conn, release_timescale_conn
from src.dependencies.neo4j_client import get_neo4j_driver
from src.dependencies.chroma import get_chroma_client
from src.services.embedding_utils import get_embeddings
from src.config import get_worthy_threshold


@dataclass
class EpisodicMemory:
    """Episodic memory data structure"""
    id: str
    user_id: str
    event_timestamp: datetime
    event_type: str
    content: str
    location: Optional[str] = None
    participants: Optional[List[str]] = None
    emotional_valence: Optional[float] = None  # -1.0 to 1.0
    emotional_arousal: Optional[float] = None    # 0.0 to 1.0
    importance_score: Optional[float] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class EpisodicMemoryService:
    """Service for managing episodic memories"""
    
    def __init__(self):
        self.timescale_conn = get_timescale_conn()
        self.neo4j_driver = get_neo4j_driver()
        self.chroma_client = get_chroma_client()
        self.collection_name = "episodic_memories"
    
    def store_memory(self, memory: EpisodicMemory) -> bool:
        """
        Store an episodic memory across all storage systems
        
        Args:
            memory: EpisodicMemory object to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # 1. Store in TimescaleDB (primary storage)
            self._store_in_timescale(memory)
            
            # 2. Store in Neo4j (relationships)
            self._store_in_neo4j(memory)
            
            # 3. Store in ChromaDB (vector search)
            self._store_in_chroma(memory)
            
            return True
            
        except Exception as e:
            print(f"Error storing episodic memory: {e}")
            return False
    
    def _store_in_timescale(self, memory: EpisodicMemory) -> None:
        """Store memory in TimescaleDB"""
        import json
        
        conn = get_timescale_conn()
        if not conn:
            raise Exception("TimescaleDB connection not available")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO episodic_memories (
                        id, user_id, event_timestamp, event_type, content,
                        location, participants, emotional_valence, emotional_arousal,
                        importance_score, tags, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    memory.id,
                    memory.user_id,
                    memory.event_timestamp,
                    memory.event_type,
                    memory.content,
                    json.dumps(memory.location) if memory.location else None,
                    memory.participants if memory.participants else None,  # TEXT[] array, not JSON
                    memory.emotional_valence,
                    memory.emotional_arousal,
                    memory.importance_score,
                    memory.tags if memory.tags else None,  # TEXT[] array, not JSON
                    json.dumps(memory.metadata) if memory.metadata else None
                ))
            conn.commit()  # Explicit commit
            release_timescale_conn(conn)  # Return to pool
        except Exception as e:
            if conn:
                conn.rollback()  # Rollback on error
                release_timescale_conn(conn)
            print(f"Error storing episodic memory in TimescaleDB: {e}")
            raise
    
    def _store_in_neo4j(self, memory: EpisodicMemory) -> None:
        """Store memory relationships in Neo4j"""
        if not self.neo4j_driver:
            raise Exception("Neo4j connection not available")
        
        with self.neo4j_driver.session() as session:
            # Create episode node
            session.run("""
                MERGE (e:Episode {id: $id, user_id: $user_id})
                SET e.event_type = $event_type,
                    e.content = $content,
                    e.timestamp = $timestamp,
                    e.importance_score = $importance_score
            """, {
                "id": memory.id,
                "user_id": memory.user_id,
                "event_type": memory.event_type,
                "content": memory.content,
                "timestamp": memory.event_timestamp.isoformat(),
                "importance_score": memory.importance_score
            })
            
            # Create relationships with participants
            if memory.participants:
                for participant in memory.participants:
                    session.run("""
                        MERGE (p:Person {name: $participant})
                        MERGE (e:Episode {id: $episode_id})
                        MERGE (e)-[:INVOLVES]->(p)
                    """, {
                        "participant": participant,
                        "episode_id": memory.id
                    })
    
    def _store_in_chroma(self, memory: EpisodicMemory) -> None:
        """Store memory in ChromaDB for vector search"""
        if not self.chroma_client:
            raise Exception("ChromaDB connection not available")
        
        # Get embeddings for the content
        embeddings = get_embeddings([memory.content])
        if not embeddings:
            return
        
        # Prepare metadata
        metadata = {
            "user_id": memory.user_id,
            "event_type": memory.event_type,
            "timestamp": memory.event_timestamp.isoformat(),
            "importance_score": memory.importance_score or 0.0,
            "emotional_valence": memory.emotional_valence or 0.0,
            "emotional_arousal": memory.emotional_arousal or 0.0,
            "location": memory.location or "",
            "participants": memory.participants or []
        }
        
        # Store in ChromaDB
        collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name
        )
        
        collection.upsert(
            embeddings=embeddings,
            documents=[memory.content],
            metadatas=[metadata],
            ids=[memory.id]
        )
    
    def calculate_importance_score(self, content: str, event_type: str, 
                                 emotional_valence: Optional[float] = None,
                                 emotional_arousal: Optional[float] = None) -> float:
        """
        Calculate importance score for an episodic memory
        
        Args:
            content: Memory content
            event_type: Type of event
            emotional_valence: Emotional valence (-1.0 to 1.0)
            emotional_arousal: Emotional arousal (0.0 to 1.0)
            
        Returns:
            float: Importance score (0.0 to 1.0)
        """
        base_score = 0.5  # Default baseline
        
        # Content length factor (longer = more important)
        content_length_factor = min(len(content) / 1000, 1.0) * 0.2
        
        # Event type factor
        important_types = ["milestone", "achievement", "celebration", "crisis", "travel"]
        type_factor = 0.3 if event_type.lower() in important_types else 0.1
        
        # Emotional intensity factor
        emotional_factor = 0.0
        if emotional_valence is not None and emotional_arousal is not None:
            # High arousal (positive or negative) = more important
            emotional_intensity = abs(emotional_valence) * emotional_arousal
            emotional_factor = min(emotional_intensity * 0.3, 0.3)
        
        # Combine factors
        importance_score = base_score + content_length_factor + type_factor + emotional_factor
        
        return min(importance_score, 1.0)
    
    def retrieve_memories(self, user_id: str, query: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         event_types: Optional[List[str]] = None,
                         limit: int = 10) -> List[EpisodicMemory]:
        """
        Retrieve episodic memories for a user
        
        Args:
            user_id: User ID
            query: Optional text query for semantic search
            start_time: Optional start time filter
            end_time: Optional end time filter
            event_types: Optional list of event types to filter
            limit: Maximum number of memories to return
            
        Returns:
            List[EpisodicMemory]: Retrieved memories
        """
        if query:
            return self._semantic_search(user_id, query, limit)
        else:
            return self._time_range_search(user_id, start_time, end_time, event_types, limit)
    
    def _semantic_search(self, user_id: str, query: str, limit: int) -> List[EpisodicMemory]:
        """Perform semantic search using ChromaDB"""
        if not self.chroma_client:
            return []
        
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            
            # Get query embeddings
            query_embeddings = get_embeddings([query])
            if not query_embeddings:
                return []
            
            # Search in ChromaDB
            results = collection.query(
                query_embeddings=query_embeddings,
                n_results=limit,
                where={"user_id": user_id}
            )
            
            # Convert results to EpisodicMemory objects
            memories = []
            if results and results.get('ids') and results['ids'][0]:
                for i, memory_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    memories.append(EpisodicMemory(
                        id=memory_id,
                        user_id=metadata['user_id'],
                        event_timestamp=datetime.fromisoformat(metadata['timestamp']),
                        event_type=metadata['event_type'],
                        content=results['documents'][0][i],
                        location=metadata.get('location'),
                        participants=metadata.get('participants', []),
                        emotional_valence=metadata.get('emotional_valence'),
                        emotional_arousal=metadata.get('emotional_arousal'),
                        importance_score=metadata.get('importance_score'),
                        tags=metadata.get('tags'),
                        metadata=metadata
                    ))
            
            return memories
            
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return []
    
    def _time_range_search(self, user_id: str, start_time: Optional[datetime],
                          end_time: Optional[datetime], event_types: Optional[List[str]],
                          limit: int) -> List[EpisodicMemory]:
        """Search memories by time range using TimescaleDB"""
        if not self.timescale_conn:
            return []
        
        try:
            with self.timescale_conn.cursor() as cur:
                # Build query
                query = """
                    SELECT id, user_id, event_timestamp, event_type, content,
                           location, participants, emotional_valence, emotional_arousal,
                           importance_score, tags, metadata
                    FROM episodic_memories
                    WHERE user_id = %s
                """
                params = [user_id]
                
                if start_time:
                    query += " AND event_timestamp >= %s"
                    params.append(start_time)
                
                if end_time:
                    query += " AND event_timestamp <= %s"
                    params.append(end_time)
                
                if event_types:
                    query += " AND event_type = ANY(%s)"
                    params.append(event_types)
                
                query += " ORDER BY event_timestamp DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                rows = cur.fetchall()
                
                # Convert to EpisodicMemory objects
                memories = []
                for row in rows:
                    memories.append(EpisodicMemory(
                        id=row['id'],
                        user_id=row['user_id'],
                        event_timestamp=row['event_timestamp'],
                        event_type=row['event_type'],
                        content=row['content'],
                        location=row['location'],
                        participants=row['participants'],
                        emotional_valence=row['emotional_valence'],
                        emotional_arousal=row['emotional_arousal'],
                        importance_score=row['importance_score'],
                        tags=row['tags'],
                        metadata=row['metadata']
                    ))
                
                return memories
                
        except Exception as e:
            print(f"Error in time range search: {e}")
            return []
    
    def get_memory_by_id(self, memory_id: str) -> Optional[EpisodicMemory]:
        """Get a specific memory by ID"""
        if not self.timescale_conn:
            return None
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, event_timestamp, event_type, content,
                           location, participants, emotional_valence, emotional_arousal,
                           importance_score, tags, metadata
                    FROM episodic_memories
                    WHERE id = %s
                """, (memory_id,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                return EpisodicMemory(
                    id=row['id'],
                    user_id=row['user_id'],
                    event_timestamp=row['event_timestamp'],
                    event_type=row['event_type'],
                    content=row['content'],
                    location=row['location'],
                    participants=row['participants'],
                    emotional_valence=row['emotional_valence'],
                    emotional_arousal=row['emotional_arousal'],
                    importance_score=row['importance_score'],
                    tags=row['tags'],
                    metadata=row['metadata']
                )
                
        except Exception as e:
            print(f"Error getting memory by ID: {e}")
            return None
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory from all storage systems"""
        try:
            # Delete from TimescaleDB
            if self.timescale_conn:
                with self.timescale_conn.cursor() as cur:
                    cur.execute("DELETE FROM episodic_memories WHERE id = %s", (memory_id,))
            
            # Delete from Neo4j
            if self.neo4j_driver:
                with self.neo4j_driver.session() as session:
                    session.run("MATCH (e:Episode {id: $id}) DETACH DELETE e", {"id": memory_id})
            
            # Delete from ChromaDB
            if self.chroma_client:
                collection = self.chroma_client.get_collection(self.collection_name)
                collection.delete(ids=[memory_id])
            
            return True
            
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False
