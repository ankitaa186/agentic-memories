"""
Procedural Memory Service

Handles procedural memories - skills, habits, and learned behaviors.
Stores in PostgreSQL for structured skill data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from src.dependencies.timescale import get_timescale_conn  # Using Timescale for time-series skill progression
from src.dependencies.neo4j_client import get_neo4j_driver
from src.dependencies.chroma import get_chroma_client


class SkillLevel(Enum):
    """Skill proficiency levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    MASTER = "master"


@dataclass
class ProceduralMemory:
    """Procedural memory data structure"""
    id: str
    user_id: str
    skill_name: str
    proficiency_level: str
    steps: List[str]
    prerequisites: Optional[List[str]] = None
    last_practiced: Optional[datetime] = None
    practice_count: int = 0
    success_rate: Optional[float] = None  # 0.0 to 1.0
    difficulty_rating: Optional[float] = None  # 0.0 to 1.0
    context: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SkillProgression:
    """Skill progression tracking"""
    id: str
    user_id: str
    skill_name: str
    timestamp: datetime
    proficiency_level: str
    practice_session_duration: Optional[int] = None  # minutes
    success_rate: Optional[float] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProceduralMemoryService:
    """Service for managing procedural memories and skill development"""
    
    def __init__(self):
        self.timescale_conn = get_timescale_conn()
        self.neo4j_driver = get_neo4j_driver()
        self.chroma_client = get_chroma_client()
        self.collection_name = "procedural_memories"
    
    def learn_skill(self, user_id: str, skill_name: str, steps: List[str],
                   proficiency_level: str = "beginner",
                   prerequisites: Optional[List[str]] = None,
                   context: Optional[str] = None,
                   tags: Optional[List[str]] = None) -> str:
        """
        Learn a new skill or update existing skill
        
        Args:
            user_id: User ID
            skill_name: Name of the skill
            steps: List of steps to perform the skill
            proficiency_level: Current proficiency level
            prerequisites: Optional list of prerequisite skills
            context: Optional context for the skill
            tags: Optional tags for categorization
            
        Returns:
            str: Skill ID
        """
        skill_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Create procedural memory
        memory = ProceduralMemory(
            id=skill_id,
            user_id=user_id,
            skill_name=skill_name,
            proficiency_level=proficiency_level,
            steps=steps,
            prerequisites=prerequisites,
            last_practiced=timestamp,
            practice_count=1,
            context=context,
            tags=tags,
            metadata={"learned_at": timestamp.isoformat()}
        )
        
        # Store in PostgreSQL
        self._store_procedural_memory(memory)
        
        # Store in Neo4j for skill relationships
        self._store_skill_relationships(memory)
        
        # Store in ChromaDB for semantic search
        self._store_in_chroma(memory)
        
        # Record initial progression (now with explicit parameters)
        self._record_skill_progression(user_id, skill_name, proficiency_level, timestamp, None, None, None)
        
        return skill_id
    
    def _store_procedural_memory(self, memory: ProceduralMemory) -> None:
        """Store procedural memory in PostgreSQL"""
        if not self.timescale_conn:
            raise Exception("Database connection not available")
        
        try:
            import json
            with self.timescale_conn.cursor() as cur:
                # Check if skill already exists
                cur.execute("""
                    SELECT id, practice_count, success_rate FROM procedural_memories 
                    WHERE user_id = %s AND skill_name = %s
                """, (memory.user_id, memory.skill_name))
                
                existing = cur.fetchone()
                
                if existing:
                    # Update existing skill
                    new_practice_count = existing['practice_count'] + 1
                    cur.execute("""
                        UPDATE procedural_memories SET
                            proficiency_level = %s,
                            steps = %s,
                            prerequisites = %s,
                            last_practiced = %s,
                            practice_count = %s,
                            context = %s,
                            tags = %s,
                            metadata = %s
                        WHERE id = %s
                    """, (
                        memory.proficiency_level,
                        json.dumps(memory.steps) if memory.steps else None,
                        json.dumps(memory.prerequisites) if memory.prerequisites else None,
                        memory.last_practiced,
                        new_practice_count,
                        memory.context,
                        memory.tags,
                        json.dumps(memory.metadata) if memory.metadata else None,
                        existing['id']
                    ))
                else:
                    # Insert new skill
                    cur.execute("""
                        INSERT INTO procedural_memories (
                            id, user_id, skill_name, proficiency_level, steps,
                            prerequisites, last_practiced, practice_count, success_rate,
                            difficulty_rating, context, tags, metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        memory.id,
                        memory.user_id,
                        memory.skill_name,
                        memory.proficiency_level,
                        json.dumps(memory.steps) if memory.steps else None,
                        json.dumps(memory.prerequisites) if memory.prerequisites else None,
                        memory.last_practiced,
                        memory.practice_count,
                        memory.success_rate,
                        memory.difficulty_rating,
                        memory.context,
                        memory.tags,
                        json.dumps(memory.metadata) if memory.metadata else None,
                    ))
            
            # Commit the transaction
            self.timescale_conn.commit()
            
        except Exception as e:
            # Rollback on error
            self.timescale_conn.rollback()
            print(f"Error storing procedural memory: {e}")
            raise
    
    def _store_skill_relationships(self, memory: ProceduralMemory) -> None:
        """Store skill relationships in Neo4j"""
        if not self.neo4j_driver:
            return
        
        try:
            with self.neo4j_driver.session() as session:
                # Create skill node
                session.run("""
                    MERGE (s:Skill {id: $id, user_id: $user_id, name: $skill_name})
                    SET s.proficiency_level = $proficiency_level,
                        s.practice_count = $practice_count,
                        s.last_practiced = $last_practiced
                """, {
                    "id": memory.id,
                    "user_id": memory.user_id,
                    "skill_name": memory.skill_name,
                    "proficiency_level": memory.proficiency_level,
                    "practice_count": memory.practice_count,
                    "last_practiced": memory.last_practiced.isoformat() if memory.last_practiced else None
                })
                
                # Create prerequisite relationships
                if memory.prerequisites:
                    for prereq in memory.prerequisites:
                        session.run("""
                            MERGE (p:Skill {name: $prereq_name, user_id: $user_id})
                            MERGE (s:Skill {id: $skill_id})
                            MERGE (p)-[:PREREQUISITE_FOR]->(s)
                        """, {
                            "prereq_name": prereq,
                            "user_id": memory.user_id,
                            "skill_id": memory.id
                        })
                
                # Create context relationships
                if memory.context:
                    session.run("""
                        MERGE (c:Context {name: $context, user_id: $user_id})
                        MERGE (s:Skill {id: $skill_id})
                        MERGE (s)-[:USED_IN]->(c)
                    """, {
                        "context": memory.context,
                        "user_id": memory.user_id,
                        "skill_id": memory.id
                    })
                
        except Exception as e:
            print(f"Error storing skill relationships: {e}")
    
    def _store_in_chroma(self, memory: ProceduralMemory) -> None:
        """Store procedural memory in ChromaDB for semantic search"""
        if not self.chroma_client:
            return
        
        try:
            # Create searchable text
            search_text = f"{memory.skill_name} {' '.join(memory.steps)} {memory.context or ''}"
            
            # Get embeddings
            from src.services.embedding_utils import get_embeddings
            embeddings = get_embeddings([search_text])
            if not embeddings:
                return
            
            # Prepare metadata
            metadata = {
                "user_id": memory.user_id,
                "skill_name": memory.skill_name,
                "proficiency_level": memory.proficiency_level,
                "practice_count": memory.practice_count,
                "success_rate": memory.success_rate or 0.0,
                "last_practiced": memory.last_practiced.isoformat() if memory.last_practiced else "",
                "context": memory.context or "",
                "tags": memory.tags or []
            }
            
            # Store in ChromaDB
            collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name
            )
            
            collection.add(
                embeddings=embeddings,
                documents=[search_text],
                metadatas=[metadata],
                ids=[memory.id]
            )
            
        except Exception as e:
            print(f"Error storing procedural memory in ChromaDB: {e}")
    
    def _record_skill_progression(self, user_id: str, skill_name: str, 
                                proficiency_level: str, timestamp: datetime,
                                session_duration: Optional[int] = None,
                                success_rate: Optional[float] = None,
                                notes: Optional[str] = None) -> None:
        """Record skill progression in TimescaleDB"""
        if not self.timescale_conn:
            return
        
        try:
            import json
            progression_id = str(uuid.uuid4())
            
            with self.timescale_conn.cursor() as cur:
                metadata = {"recorded_at": timestamp.isoformat()}
                cur.execute("""
                    INSERT INTO skill_progressions (
                        id, user_id, skill_name, timestamp, proficiency_level,
                        practice_session_duration, success_rate, notes, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    progression_id,
                    user_id,
                    skill_name,
                    timestamp,
                    proficiency_level,
                    session_duration,
                    success_rate,
                    notes,
                    json.dumps(metadata),
                ))
            
            # Commit the transaction
            self.timescale_conn.commit()
                
        except Exception as e:
            # Rollback on error
            self.timescale_conn.rollback()
            print(f"Error recording skill progression: {e}")
    
    def practice_skill(self, user_id: str, skill_name: str, 
                      session_duration: Optional[int] = None,
                      success_rate: Optional[float] = None,
                      notes: Optional[str] = None) -> bool:
        """
        Record a practice session for a skill
        
        Args:
            user_id: User ID
            skill_name: Name of the skill practiced
            session_duration: Duration in minutes
            success_rate: Success rate (0.0 to 1.0)
            notes: Optional practice notes
            
        Returns:
            bool: True if successful
        """
        try:
            timestamp = datetime.now(timezone.utc)
            
            # Update skill in PostgreSQL
            if self.timescale_conn:
                with self.timescale_conn.cursor() as cur:
                    cur.execute("""
                        UPDATE procedural_memories SET
                            last_practiced = %s,
                            practice_count = practice_count + 1,
                            success_rate = CASE 
                                WHEN success_rate IS NULL THEN %s
                                ELSE (success_rate + %s) / 2
                            END
                        WHERE user_id = %s AND skill_name = %s
                    """, (timestamp, success_rate, success_rate, user_id, skill_name))
            
            # Record progression
            self._record_skill_progression(user_id, skill_name, 
                                         self._get_current_proficiency(user_id, skill_name), 
                                         timestamp)
            
            # Update progression with session details
            if session_duration or success_rate or notes:
                self._update_progression_session(user_id, skill_name, timestamp,
                                               session_duration, success_rate, notes)
            
            return True
            
        except Exception as e:
            print(f"Error practicing skill: {e}")
            return False
    
    def _get_current_proficiency(self, user_id: str, skill_name: str) -> str:
        """Get current proficiency level for a skill"""
        if not self.timescale_conn:
            return "beginner"
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    SELECT proficiency_level FROM procedural_memories 
                    WHERE user_id = %s AND skill_name = %s
                """, (user_id, skill_name))
                
                row = cur.fetchone()
                return row['proficiency_level'] if row else "beginner"
                
        except Exception as e:
            print(f"Error getting proficiency level: {e}")
            return "beginner"
    
    def _update_progression_session(self, user_id: str, skill_name: str, 
                                 timestamp: datetime, session_duration: Optional[int],
                                 success_rate: Optional[float], notes: Optional[str]) -> None:
        """Update progression record with session details"""
        if not self.timescale_conn:
            return
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    UPDATE skill_progressions SET
                        practice_session_duration = %s,
                        success_rate = %s,
                        notes = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE user_id = %s AND skill_name = %s AND timestamp = %s
                """, (
                    session_duration,
                    success_rate,
                    notes,
                    '{"session_updated": true}',
                    user_id,
                    skill_name,
                    timestamp
                ))
                
        except Exception as e:
            print(f"Error updating progression session: {e}")
    
    def get_skills(self, user_id: str, proficiency_level: Optional[str] = None,
                  context: Optional[str] = None) -> List[ProceduralMemory]:
        """Get skills for a user with optional filters"""
        if not self.timescale_conn:
            return []
        
        try:
            with self.timescale_conn.cursor() as cur:
                query = """
                    SELECT id, user_id, skill_name, proficiency_level, steps,
                           prerequisites, last_practiced, practice_count, success_rate,
                           difficulty_rating, context, tags, metadata
                    FROM procedural_memories
                    WHERE user_id = %s
                """
                params = [user_id]
                
                if proficiency_level:
                    query += " AND proficiency_level = %s"
                    params.append(proficiency_level)
                
                if context:
                    query += " AND context ILIKE %s"
                    params.append(f"%{context}%")
                
                query += " ORDER BY last_practiced DESC, practice_count DESC"
                
                cur.execute(query, params)
                rows = cur.fetchall()
                
                skills = []
                for row in rows:
                    skills.append(ProceduralMemory(
                        id=row['id'],
                        user_id=row['user_id'],
                        skill_name=row['skill_name'],
                        proficiency_level=row['proficiency_level'],
                        steps=row['steps'],
                        prerequisites=row['prerequisites'],
                        last_practiced=row['last_practiced'],
                        practice_count=row['practice_count'],
                        success_rate=row['success_rate'],
                        difficulty_rating=row['difficulty_rating'],
                        context=row['context'],
                        tags=row['tags'],
                        metadata=row['metadata']
                    ))
                
                return skills
                
        except Exception as e:
            print(f"Error getting skills: {e}")
            return []
    
    def get_skill_progression(self, user_id: str, skill_name: str, 
                            days: int = 30) -> List[SkillProgression]:
        """Get skill progression history"""
        if not self.timescale_conn:
            return []
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, skill_name, timestamp, proficiency_level,
                           practice_session_duration, success_rate, notes, metadata
                    FROM skill_progressions
                    WHERE user_id = %s AND skill_name = %s 
                    AND timestamp >= %s
                    ORDER BY timestamp DESC
                """, (user_id, skill_name, datetime.now(timezone.utc) - timedelta(days=days)))
                
                rows = cur.fetchall()
                progressions = []
                
                for row in rows:
                    progressions.append(SkillProgression(
                        id=row['id'],
                        user_id=row['user_id'],
                        skill_name=row['skill_name'],
                        timestamp=row['timestamp'],
                        proficiency_level=row['proficiency_level'],
                        practice_session_duration=row['practice_session_duration'],
                        success_rate=row['success_rate'],
                        notes=row['notes'],
                        metadata=row['metadata']
                    ))
                
                return progressions
                
        except Exception as e:
            print(f"Error getting skill progression: {e}")
            return []
    
    def recommend_next_skills(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recommend next skills to learn based on current skills and prerequisites
        
        Args:
            user_id: User ID
            limit: Maximum number of recommendations
            
        Returns:
            List of skill recommendations with reasons
        """
        if not self.timescale_conn:
            return []
        
        try:
            # Get current skills
            current_skills = self.get_skills(user_id)
            current_skill_names = {skill.skill_name for skill in current_skills}
            
            # Find skills that have prerequisites met
            recommendations = []
            
            with self.timescale_conn.cursor() as cur:
                # Get all skills with prerequisites
                cur.execute("""
                    SELECT skill_name, prerequisites, proficiency_level, practice_count
                    FROM procedural_memories
                    WHERE user_id = %s AND prerequisites IS NOT NULL
                """, (user_id,))
                
                all_skills = cur.fetchall()
                
                for skill in all_skills:
                    if skill['skill_name'] not in current_skill_names:
                        # Check if prerequisites are met
                        prereqs = skill['prerequisites'] or []
                        met_prereqs = [prereq for prereq in prereqs if prereq in current_skill_names]
                        
                        if len(met_prereqs) == len(prereqs):
                            # All prerequisites met
                            recommendations.append({
                                "skill_name": skill['skill_name'],
                                "reason": f"Prerequisites met: {', '.join(met_prereqs)}",
                                "confidence": len(met_prereqs) / len(prereqs) if prereqs else 1.0,
                                "prerequisites": prereqs,
                                "met_prerequisites": met_prereqs
                            })
            
            # Sort by confidence and return top recommendations
            recommendations.sort(key=lambda x: x['confidence'], reverse=True)
            return recommendations[:limit]
            
        except Exception as e:
            print(f"Error recommending skills: {e}")
            return []
    
    def search_skills(self, user_id: str, query: str, limit: int = 10) -> List[ProceduralMemory]:
        """Search skills using semantic search"""
        if not self.chroma_client:
            return []
        
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            
            # Get query embeddings
            from src.services.embedding_utils import get_embeddings
            query_embeddings = get_embeddings([query])
            if not query_embeddings:
                return []
            
            # Search in ChromaDB
            results = collection.query(
                query_embeddings=query_embeddings,
                n_results=limit,
                where={"user_id": user_id}
            )
            
            # Convert results to ProceduralMemory objects
            skills = []
            if results and results.get('ids') and results['ids'][0]:
                for i, skill_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    
                    # Get full skill data from PostgreSQL
                    skill = self._get_skill_by_id(skill_id)
                    if skill:
                        skills.append(skill)
            
            return skills
            
        except Exception as e:
            print(f"Error searching skills: {e}")
            return []
    
    def _get_skill_by_id(self, skill_id: str) -> Optional[ProceduralMemory]:
        """Get skill by ID from PostgreSQL"""
        if not self.timescale_conn:
            return None
        
        try:
            with self.timescale_conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, skill_name, proficiency_level, steps,
                           prerequisites, last_practiced, practice_count, success_rate,
                           difficulty_rating, context, tags, metadata
                    FROM procedural_memories
                    WHERE id = %s
                """, (skill_id,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                return ProceduralMemory(
                    id=row['id'],
                    user_id=row['user_id'],
                    skill_name=row['skill_name'],
                    proficiency_level=row['proficiency_level'],
                    steps=row['steps'],
                    prerequisites=row['prerequisites'],
                    last_practiced=row['last_practiced'],
                    practice_count=row['practice_count'],
                    success_rate=row['success_rate'],
                    difficulty_rating=row['difficulty_rating'],
                    context=row['context'],
                    tags=row['tags'],
                    metadata=row['metadata']
                )
                
        except Exception as e:
            print(f"Error getting skill by ID: {e}")
            return None
