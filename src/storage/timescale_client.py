"""TimescaleDB client for episodic and emotional memories."""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import uuid4
import logging

from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)


class TimescaleClient:
    """Client for TimescaleDB operations on time-series memory data."""
    
    def __init__(self, connection_string: Optional[str] = None):
        """Initialize TimescaleDB client with connection pooling."""
        self.connection_string = connection_string or os.getenv('TIMESCALE_DSN')
        if not self.connection_string:
            raise ValueError(
                "TIMESCALE_DSN environment variable is required. "
                "Set it to a PostgreSQL connection string, e.g.: "
                "postgresql://user:pass@localhost:5433/agentic_memories"
            )
        
        # Create connection pool
        self.pool = SimpleConnectionPool(
            1, 20,  # min and max connections
            self.connection_string
        )
        
        # Initialize database if needed
        self._initialize_database()
    
    def _initialize_database(self):
        """Run initialization/migration scripts if needed."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Check if tables exist
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'episodic_memories'
                    );
                """)
                
                if not cursor.fetchone()[0]:
                    logger.info("Initializing TimescaleDB schema...")
                    # Run migration scripts
                    migration_files = [
                        '001_create_episodic_memories.sql',
                        '002_create_emotional_memories.sql',
                        '003_create_procedural_memories.sql'
                    ]
                    
                    for migration_file in migration_files:
                        migration_path = f'migrations/{migration_file}'
                        if os.path.exists(migration_path):
                            with open(migration_path, 'r') as f:
                                cursor.execute(f.read())
                    
                    conn.commit()
                    logger.info("TimescaleDB schema initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize TimescaleDB: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def insert_episodic_memory(self, memory: Dict[str, Any]) -> str:
        """Insert a new episodic memory and return its ID."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                memory_id = str(uuid4())
                
                cursor.execute("""
                    INSERT INTO episodic_memories (
                        id, user_id, event_timestamp, event_type, content,
                        location, participants, emotional_valence, emotional_arousal,
                        sensory_context, causal_chain, significance_score, novelty_score
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    memory_id,
                    memory['user_id'],
                    memory.get('event_timestamp', datetime.now()),
                    memory.get('event_type', 'routine'),
                    memory['content'],
                    Json(memory.get('location', {})),
                    memory.get('participants', []),
                    memory.get('emotional_valence', 0),
                    memory.get('emotional_arousal', 0.5),
                    Json(memory.get('sensory_context', {})),
                    Json(memory.get('causal_chain', {})),
                    memory.get('significance_score', 0.5),
                    memory.get('novelty_score', 0.5)
                ))
                
                conn.commit()
                logger.info(f"Inserted episodic memory {memory_id}")
                return memory_id
        
        except Exception as e:
            logger.error(f"Failed to insert episodic memory: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def search_episodic_by_time(self, 
                                user_id: str,
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None,
                                limit: int = 10) -> List[Dict[str, Any]]:
        """Search episodic memories within a time range."""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Default to last 30 days if no time range specified
                if not start_time:
                    start_time = datetime.now() - timedelta(days=30)
                if not end_time:
                    end_time = datetime.now()
                
                cursor.execute("""
                    SELECT * FROM episodic_memories
                    WHERE user_id = %s 
                    AND event_timestamp BETWEEN %s AND %s
                    ORDER BY event_timestamp DESC
                    LIMIT %s
                """, (user_id, start_time, end_time, limit))
                
                results = cursor.fetchall()
                return [dict(row) for row in results]
        
        except Exception as e:
            logger.error(f"Failed to search episodic memories: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    def insert_emotional_state(self, emotion_data: Dict[str, Any]) -> str:
        """Record an emotional state."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                emotion_id = str(uuid4())
                
                cursor.execute("""
                    INSERT INTO emotional_memories (
                        id, user_id, timestamp, emotion_vector,
                        valence, arousal, dominance, primary_emotion,
                        intensity, triggers, context
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    emotion_id,
                    emotion_data['user_id'],
                    emotion_data.get('timestamp', datetime.now()),
                    emotion_data.get('emotion_vector', [0] * 8),
                    emotion_data.get('valence', 0),
                    emotion_data.get('arousal', 0.5),
                    emotion_data.get('dominance', 0.5),
                    emotion_data.get('primary_emotion'),
                    emotion_data.get('intensity', 0.5),
                    Json(emotion_data.get('triggers', {})),
                    Json(emotion_data.get('context', {}))
                ))
                
                conn.commit()
                logger.info(f"Inserted emotional state {emotion_id}")
                return emotion_id
        
        except Exception as e:
            logger.error(f"Failed to insert emotional state: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def get_emotional_pattern(self, user_id: str, pattern_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific emotional pattern."""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM emotional_patterns
                    WHERE user_id = %s AND pattern_name = %s
                """, (user_id, pattern_name))
                
                result = cursor.fetchone()
                return dict(result) if result else None
        
        except Exception as e:
            logger.error(f"Failed to get emotional pattern: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    def update_memory_recall(self, memory_id: str):
        """Update recall statistics for a memory."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE episodic_memories 
                    SET replay_count = replay_count + 1,
                        last_recalled = NOW()
                    WHERE id = %s
                """, (memory_id,))
                
                conn.commit()
                logger.debug(f"Updated recall for memory {memory_id}")
        
        except Exception as e:
            logger.error(f"Failed to update memory recall: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def apply_decay(self, user_id: str, decay_rate: float = 0.01):
        """Apply decay to memories based on time and access patterns."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Apply exponential decay based on time since last recall
                cursor.execute("""
                    UPDATE episodic_memories 
                    SET decay_factor = decay_factor * (1 - %s * EXTRACT(
                        EPOCH FROM (NOW() - COALESCE(last_recalled, created_at))
                    ) / 86400)
                    WHERE user_id = %s 
                    AND decay_factor > 0.1
                """, (decay_rate, user_id))
                
                conn.commit()
                logger.info(f"Applied decay to memories for user {user_id}")
        
        except Exception as e:
            logger.error(f"Failed to apply decay: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def close(self):
        """Close all connections in the pool."""
        if hasattr(self, 'pool'):
            self.pool.closeall()
