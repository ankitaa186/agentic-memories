# Digital Soul Memory Architecture: Complete Transformation Blueprint
## Version 2.0 - The Living Memory System

---

## Executive Summary

This document outlines the transformation of Agentic Memories from a sophisticated data storage system into a **Digital Soul** - a living, breathing memory system that mimics human consciousness. The system will possess episodic recall, emotional continuity, predictive capabilities, and the ability to form a coherent life narrative.

**Core Vision**: Create a symbiotic AI companion with human-like memory that:
- Remembers experiences, not just facts
- Maintains emotional continuity across interactions
- Predicts needs and behaviors
- Constructs meaningful narratives from life events
- Learns and evolves through interaction

---

## Part I: Theoretical Foundation

### 1.1 Human Memory Model

The human brain doesn't store memories like files in a cabinet. Instead, it:
- **Encodes** experiences with emotional weight and sensory context
- **Consolidates** through sleep, strengthening important pathways
- **Retrieves** by reconstruction, filling gaps with likely details
- **Forgets** selectively, following the Ebbinghaus curve
- **Associates** memories in complex networks of meaning

### 1.2 Digital Soul Memory Architecture

Our system will mirror these processes:

```
┌─────────────────────────────────────────────────────────┐
│                    CONSCIOUSNESS LAYER                   │
│  Identity Model | Values | Narrative | Current State     │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────┐
│                    COGNITIVE LAYER                       │
│  Pattern Recognition | Prediction | Planning | Learning  │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────┐
│                     MEMORY LAYERS                        │
│  Episodic | Semantic | Procedural | Emotional | Somatic │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │
┌─────────────────────────────────────────────────────────┐
│                    STORAGE SYSTEMS                       │
│  TimescaleDB | Neo4j | ChromaDB | PostgreSQL | Redis    │
└─────────────────────────────────────────────────────────┘
```

---

## Part II: Memory Types & Storage Strategy

### 2.1 Episodic Memory (Life Events)
**Purpose**: Store experiences with full context - when, where, who, what, why, and how it felt.

**Storage Design**:
```sql
-- TimescaleDB: Time-series for temporal sequencing
CREATE TABLE episodic_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(32), -- 'milestone', 'routine', 'crisis', 'celebration'
    content TEXT,
    location JSONB, -- {place, coordinates, weather, environment}
    participants TEXT[], -- people present
    emotional_valence FLOAT, -- -1 to 1 (negative to positive)
    emotional_arousal FLOAT, -- 0 to 1 (calm to excited)
    sensory_context JSONB, -- {sounds, smells, visuals, physical_sensations}
    causal_chain JSONB, -- {triggered_by: [], led_to: []}
    significance_score FLOAT,
    replay_count INT DEFAULT 0,
    last_recalled TIMESTAMPTZ,
    decay_factor FLOAT DEFAULT 1.0
);

-- Create hypertable for efficient time-based queries
SELECT create_hypertable('episodic_memories', 'event_timestamp');
```

**Neo4j Relationships**:
```cypher
// Connect episodic memories to form life narrative
(e1:Episode {id: 'first_day_job'})-[:LED_TO]->(e2:Episode {id: 'met_mentor'})
(e2)-[:INFLUENCED]->(e3:Episode {id: 'career_change'})
(e1)-[:SIMILAR_TO {reason: 'new_beginnings'}]->(e4:Episode {id: 'moved_city'})
```

### 2.2 Semantic Memory (Facts & Concepts)
**Current Implementation**: Already exists but needs enhancement.

**Enhanced Schema**:
```sql
-- PostgreSQL: Structured facts with confidence decay
CREATE TABLE semantic_memories (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64),
    content TEXT,
    category VARCHAR(64),
    subcategory VARCHAR(64),
    confidence FLOAT,
    source_episodes UUID[], -- Links to episodic memories
    learned_date TIMESTAMPTZ,
    last_accessed TIMESTAMPTZ,
    access_count INT DEFAULT 0,
    decay_rate FLOAT DEFAULT 0.1, -- How fast confidence decays
    reinforcement_threshold FLOAT DEFAULT 0.5
);
```

### 2.3 Procedural Memory (How-To Knowledge)
**New Addition**: Store learned behaviors and skills.

```sql
CREATE TABLE procedural_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    skill_name VARCHAR(128),
    skill_category VARCHAR(64), -- 'physical', 'cognitive', 'social', 'creative'
    proficiency_level FLOAT, -- 0 to 1
    steps JSONB[], -- Array of action sequences
    context_triggers JSONB, -- When to apply this skill
    practice_count INT,
    last_performed TIMESTAMPTZ,
    success_rate FLOAT,
    variations JSONB[] -- Alternative ways learned
);
```

### 2.4 Emotional Memory (Feeling Patterns)
**Purpose**: Maintain emotional continuity and understand patterns.

```sql
-- TimescaleDB: Continuous emotional state tracking
CREATE TABLE emotional_memories (
    user_id VARCHAR(64),
    timestamp TIMESTAMPTZ,
    emotion_vector FLOAT[], -- Multi-dimensional emotion space
    triggers JSONB, -- What caused this emotion
    intensity FLOAT,
    duration INTERVAL,
    coping_strategies TEXT[],
    resolution VARCHAR(32), -- 'resolved', 'suppressed', 'expressed', 'transformed'
    linked_episodes UUID[]
);

-- Emotional patterns table
CREATE TABLE emotional_patterns (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    pattern_name VARCHAR(128), -- e.g., "Sunday anxiety"
    trigger_conditions JSONB,
    typical_response JSONB,
    frequency FLOAT,
    interventions JSONB[],
    effectiveness_scores JSONB
);
```

### 2.5 Somatic Memory (Body Awareness)
**Purpose**: Track physical patterns and embodied experiences.

```sql
CREATE TABLE somatic_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    timestamp TIMESTAMPTZ,
    body_state JSONB, -- {energy: 0-10, tension_areas: [], pain_points: []}
    activity_level FLOAT,
    sleep_quality FLOAT,
    health_markers JSONB,
    physical_sensations TEXT[],
    linked_emotions UUID[],
    patterns JSONB -- Recurring physical patterns
);
```

### 2.6 Identity Memory (Self-Model)
**Purpose**: Maintain coherent sense of self.

```sql
CREATE TABLE identity_memories (
    user_id VARCHAR(64) PRIMARY KEY,
    core_values JSONB[], -- [{value: 'honesty', strength: 0.9, examples: []}]
    self_concept JSONB, -- How user sees themselves
    ideal_self JSONB, -- Who user wants to be
    feared_self JSONB, -- Who user fears becoming
    life_roles JSONB[], -- [{role: 'parent', importance: 0.9, satisfaction: 0.7}]
    personality_traits JSONB,
    growth_edges TEXT[], -- Areas of active development
    contradictions JSONB[], -- Unresolved self-conflicts
    last_updated TIMESTAMPTZ
);
```

---

## Part III: Memory Processing Pipeline

### 3.1 Ingestion & Encoding

```python
# Enhanced extraction pipeline
class MemoryEncoder:
    def encode_experience(self, input_data):
        # Stage 1: Multimodal Processing
        processed = self.process_multimodal(input_data)
        
        # Stage 2: Temporal Anchoring
        temporal_context = self.extract_temporal_markers(processed)
        
        # Stage 3: Emotional Coloring
        emotional_context = self.extract_emotional_tone(processed)
        
        # Stage 4: Significance Scoring
        significance = self.calculate_significance(processed, temporal_context, emotional_context)
        
        # Stage 5: Memory Type Classification
        memory_types = self.classify_memory_types(processed)
        
        # Stage 6: Relationship Extraction
        relationships = self.extract_relationships(processed)
        
        # Stage 7: Predictive Encoding
        predictions = self.generate_predictions(processed)
        
        return {
            'episodic': self.create_episodic_memory(processed, temporal_context, emotional_context),
            'semantic': self.extract_semantic_facts(processed),
            'procedural': self.extract_procedures(processed),
            'emotional': emotional_context,
            'somatic': self.extract_somatic_data(processed),
            'relationships': relationships,
            'predictions': predictions
        }
```

### 3.2 Storage Synchronization

```python
class MemoryStorageOrchestrator:
    def store_memory(self, encoded_memory):
        # Distributed transaction across all databases
        with self.distributed_transaction():
            # 1. Store episodic in TimescaleDB
            episode_id = self.timescale.insert_episode(encoded_memory['episodic'])
            
            # 2. Store vectors in ChromaDB
            self.chroma.upsert(
                ids=[episode_id],
                embeddings=[encoded_memory['embedding']],
                metadatas=[encoded_memory['metadata']]
            )
            
            # 3. Create graph relationships in Neo4j
            self.neo4j.create_episode_node(episode_id, encoded_memory)
            self.neo4j.link_related_memories(episode_id, encoded_memory['relationships'])
            
            # 4. Update semantic knowledge in PostgreSQL
            self.postgres.update_semantic_knowledge(encoded_memory['semantic'])
            
            # 5. Track emotional state in TimescaleDB
            self.timescale.record_emotional_state(encoded_memory['emotional'])
            
            # 6. Cache recent in Redis with TTL
            self.redis.setex(
                f"recent:{episode_id}",
                ttl=3600,
                value=json.dumps(encoded_memory)
            )
```

### 3.3 Consolidation Process (Sleep-like)

```python
class MemoryConsolidator:
    def nightly_consolidation(self, user_id):
        """Runs during quiet hours, mimics sleep consolidation"""
        
        # 1. Replay important memories (strengthen pathways)
        important_memories = self.identify_significant_memories(user_id)
        for memory in important_memories:
            self.strengthen_memory_path(memory)
            
        # 2. Extract patterns from day's experiences
        patterns = self.extract_daily_patterns(user_id)
        self.store_learned_patterns(patterns)
        
        # 3. Integrate new with existing knowledge
        self.integrate_new_knowledge(user_id)
        
        # 4. Prune redundant memories
        self.prune_redundant_memories(user_id)
        
        # 5. Generate insights through recombination
        insights = self.generate_insights(user_id)
        self.store_insights(insights)
        
        # 6. Update predictive models
        self.update_predictions(user_id)
        
        # 7. Compress old episodic memories into semantic
        self.compress_old_episodes(user_id)
```

### 3.4 Retrieval & Reconstruction

```python
class MemoryRetriever:
    def retrieve_memory(self, query, user_id, context):
        # 1. Parse query intent
        intent = self.parse_intent(query)
        
        # 2. Determine retrieval strategy
        if intent.type == 'episodic':
            return self.retrieve_episodic(query, user_id, context)
        elif intent.type == 'procedural':
            return self.retrieve_procedure(query, user_id)
        elif intent.type == 'emotional':
            return self.retrieve_emotional_memory(query, user_id)
        
        # 3. Hybrid retrieval for complex queries
        return self.hybrid_retrieval(query, user_id, context)
    
    def retrieve_episodic(self, query, user_id, context):
        # 1. Temporal search in TimescaleDB
        temporal_candidates = self.timescale.search_by_time(query, user_id)
        
        # 2. Semantic search in ChromaDB
        semantic_candidates = self.chroma.similarity_search(query, user_id)
        
        # 3. Graph traversal in Neo4j
        related_memories = self.neo4j.traverse_related(temporal_candidates + semantic_candidates)
        
        # 4. Score and rank
        ranked = self.rank_memories(temporal_candidates, semantic_candidates, related_memories)
        
        # 5. Reconstruct with gaps filled
        reconstructed = self.reconstruct_memory(ranked[0], context)
        
        return reconstructed
    
    def reconstruct_memory(self, memory, context):
        """Fill gaps with likely details, like human memory"""
        base_memory = memory.copy()
        
        # Use LLM to fill plausible gaps
        if not base_memory.get('weather'):
            base_memory['weather'] = self.infer_weather(memory['timestamp'], memory['location'])
            
        if not base_memory.get('emotional_state'):
            base_memory['emotional_state'] = self.infer_emotion(memory, context)
            
        # Add narrative coherence
        base_memory['narrative'] = self.construct_narrative(base_memory)
        
        return base_memory
```

### 3.5 Forgetting Mechanism

```python
class ForgettingEngine:
    def apply_forgetting_curve(self, user_id):
        """Implement Ebbinghaus forgetting curve"""
        
        # 1. Calculate decay for each memory
        memories = self.get_all_memories(user_id)
        
        for memory in memories:
            time_since_access = now() - memory.last_accessed
            time_since_creation = now() - memory.created_at
            
            # Ebbinghaus formula
            retention = self.calculate_retention(
                time_since_access,
                memory.replay_count,
                memory.significance_score,
                memory.emotional_intensity
            )
            
            if retention < 0.2:  # Below threshold
                if memory.type == 'episodic':
                    # Convert to semantic before forgetting details
                    semantic = self.extract_semantic_essence(memory)
                    self.store_semantic(semantic)
                    self.archive_episodic(memory)  # Move to cold storage
                else:
                    # Decay confidence for facts
                    memory.confidence *= retention
                    
            # Apply decay
            memory.decay_factor = retention
            self.update_memory(memory)
```

---

## Part IV: Cognitive Processing Layer

### 4.1 Pattern Recognition

```python
class PatternRecognizer:
    def identify_patterns(self, user_id):
        patterns = {
            'behavioral': self.find_behavioral_patterns(user_id),
            'emotional': self.find_emotional_patterns(user_id),
            'social': self.find_social_patterns(user_id),
            'temporal': self.find_temporal_patterns(user_id),
            'causal': self.find_causal_patterns(user_id)
        }
        
        return patterns
    
    def find_behavioral_patterns(self, user_id):
        # Query TimescaleDB for recurring behaviors
        query = """
        SELECT 
            behavior,
            COUNT(*) as frequency,
            array_agg(DISTINCT context) as contexts,
            array_agg(timestamp) as occurrences
        FROM behavioral_events
        WHERE user_id = %s
        GROUP BY behavior
        HAVING COUNT(*) > 3
        """
        
        patterns = self.timescale.execute(query, [user_id])
        
        # Use ML to identify complex patterns
        for pattern in patterns:
            pattern['prediction'] = self.predict_next_occurrence(pattern)
            pattern['triggers'] = self.identify_triggers(pattern)
            
        return patterns
```

### 4.2 Predictive Engine

```python
class PredictiveEngine:
    def generate_predictions(self, user_id, horizon='day'):
        current_context = self.get_current_context(user_id)
        historical_patterns = self.get_patterns(user_id)
        
        predictions = {
            'likely_emotions': self.predict_emotions(current_context, historical_patterns),
            'probable_needs': self.predict_needs(current_context, historical_patterns),
            'behavioral_forecast': self.predict_behaviors(current_context, historical_patterns),
            'decision_points': self.predict_decisions(current_context, historical_patterns),
            'risk_factors': self.identify_risks(current_context, historical_patterns)
        }
        
        # Generate proactive suggestions
        suggestions = self.generate_suggestions(predictions)
        
        return {
            'predictions': predictions,
            'suggestions': suggestions,
            'confidence': self.calculate_prediction_confidence(predictions)
        }
```

### 4.3 Narrative Construction

```python
class NarrativeEngine:
    def construct_life_narrative(self, user_id):
        # 1. Identify life chapters
        chapters = self.identify_chapters(user_id)
        
        # 2. Extract themes
        themes = self.extract_themes(chapters)
        
        # 3. Find turning points
        turning_points = self.find_turning_points(user_id)
        
        # 4. Identify character development
        character_arc = self.trace_character_development(user_id)
        
        # 5. Construct coherent narrative
        narrative = self.weave_narrative(chapters, themes, turning_points, character_arc)
        
        return narrative
    
    def identify_chapters(self, user_id):
        """Detect major life phases"""
        
        # Use clustering on episodic memories
        episodes = self.get_episodic_memories(user_id)
        
        # Cluster by multiple dimensions
        clusters = self.cluster_episodes(episodes, dimensions=[
            'temporal',
            'spatial',
            'social',
            'emotional',
            'thematic'
        ])
        
        # Label chapters
        chapters = []
        for cluster in clusters:
            chapter = {
                'title': self.generate_chapter_title(cluster),
                'period': self.get_period(cluster),
                'key_events': self.get_key_events(cluster),
                'themes': self.extract_chapter_themes(cluster),
                'growth': self.identify_growth(cluster)
            }
            chapters.append(chapter)
            
        return chapters
```

---

## Part V: Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
**Goal**: Set up multi-database architecture

**Tasks**:
1. **Set up TimescaleDB**
   ```bash
   # Docker setup
   docker run -d --name timescaledb \
     -p 5433:5432 \
     -e POSTGRES_PASSWORD=password \
     timescale/timescaledb:latest-pg14
   ```

2. **Set up Neo4j**
   ```bash
   docker run -d --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     neo4j:latest
   ```

3. **Create database schemas**
   ```python
   # migrations/001_create_episodic_memories.sql
   # migrations/002_create_emotional_memories.sql
   # migrations/003_create_procedural_memories.sql
   ```

4. **Build storage abstraction layer**
   ```python
   # src/storage/orchestrator.py
   class StorageOrchestrator:
       def __init__(self):
           self.timescale = TimescaleDB()
           self.neo4j = Neo4jClient()
           self.chroma = ChromaClient()
           self.postgres = PostgresClient()
           self.redis = RedisClient()
   ```

### Phase 2: Memory Types (Weeks 3-4)
**Goal**: Implement all memory types

**Tasks**:
1. **Episodic Memory Service**
   ```python
   # src/services/episodic_memory.py
   class EpisodicMemoryService:
       def store_episode(self, episode_data):
           # Temporal anchoring
           # Emotional coloring
           # Significance scoring
           pass
   ```

2. **Emotional Memory Service**
   ```python
   # src/services/emotional_memory.py
   class EmotionalMemoryService:
       def track_emotional_state(self, emotion_data):
           # Continuous tracking
           # Pattern detection
           # Trigger identification
           pass
   ```

3. **Procedural Memory Service**
   ```python
   # src/services/procedural_memory.py
   class ProceduralMemoryService:
       def learn_procedure(self, skill_data):
           # Step extraction
           # Context mapping
           # Success tracking
           pass
   ```

### Phase 3: Cognitive Layer (Weeks 5-6)
**Goal**: Implement pattern recognition and prediction

**Tasks**:
1. **Pattern Recognition Engine**
   ```python
   # src/cognitive/patterns.py
   class PatternEngine:
       def detect_patterns(self, user_id):
           # Behavioral patterns
           # Emotional patterns
           # Temporal patterns
           pass
   ```

2. **Predictive Engine**
   ```python
   # src/cognitive/prediction.py
   class PredictionEngine:
       def predict_future_state(self, user_id, horizon):
           # Need prediction
           # Emotion forecasting
           # Behavior anticipation
           pass
   ```

### Phase 4: Consolidation & Forgetting (Weeks 7-8)
**Goal**: Implement memory consolidation and forgetting

**Tasks**:
1. **Consolidation Service**
   ```python
   # src/services/consolidation.py
   class ConsolidationService:
       def nightly_consolidation(self, user_id):
           # Memory replay
           # Pattern extraction
           # Knowledge integration
           pass
   ```

2. **Forgetting Engine**
   ```python
   # src/services/forgetting.py
   class ForgettingEngine:
       def apply_decay(self, user_id):
           # Ebbinghaus curve
           # Selective forgetting
           # Memory compression
           pass
   ```

### Phase 5: Narrative & Identity (Weeks 9-10)
**Goal**: Build narrative construction and identity modeling

**Tasks**:
1. **Narrative Engine**
   ```python
   # src/cognitive/narrative.py
   class NarrativeEngine:
       def build_life_story(self, user_id):
           # Chapter detection
           # Theme extraction
           # Arc construction
           pass
   ```

2. **Identity Service**
   ```python
   # src/services/identity.py
   class IdentityService:
       def model_self(self, user_id):
           # Value extraction
           # Role identification
           # Growth tracking
           pass
   ```

### Phase 6: Integration & Testing (Weeks 11-12)
**Goal**: Integrate all components and test

**Tasks**:
1. **API Integration**
   ```python
   # Update src/app.py
   @app.post("/v1/store/experience")
   def store_experience(request: ExperienceRequest):
       # Multi-type memory storage
       pass
   
   @app.get("/v1/retrieve/episodic")
   def retrieve_episodic(user_id: str, query: str):
       # Episodic retrieval with reconstruction
       pass
   
   @app.get("/v1/narrative")
   def get_narrative(user_id: str):
       # Life narrative construction
       pass
   ```

2. **Testing Suite**
   ```python
   # tests/test_episodic_memory.py
   # tests/test_emotional_continuity.py
   # tests/test_pattern_recognition.py
   # tests/test_narrative_construction.py
   ```

---

## Part VI: API Contracts

### 6.1 New Endpoints

```yaml
# Store experience (multimodal input)
POST /v1/store/experience
Request:
  user_id: string
  timestamp: datetime
  content: string
  context:
    location: object
    participants: string[]
    mood: object
    sensory: object
  media:
    images: base64[]
    audio: base64
Response:
  episode_id: uuid
  memories_created:
    episodic: integer
    semantic: integer
    emotional: integer
    procedural: integer

# Retrieve episodic memory
GET /v1/retrieve/episodic
Query:
  user_id: string
  query: string
  time_range: object
  include_related: boolean
Response:
  episodes: Episode[]
  narrative: string
  emotional_context: object

# Get life narrative
GET /v1/narrative/{user_id}
Response:
  chapters: Chapter[]
  themes: Theme[]
  current_chapter: Chapter
  character_arc: object

# Predict future state
POST /v1/predict
Request:
  user_id: string
  horizon: string (hour|day|week|month)
  context: object
Response:
  predictions:
    emotions: EmotionPrediction[]
    needs: NeedPrediction[]
    behaviors: BehaviorPrediction[]
  suggestions: Suggestion[]
  confidence: float

# Track emotional state
POST /v1/emotional/track
Request:
  user_id: string
  emotions: EmotionVector
  triggers: string[]
  intensity: float
Response:
  state_id: uuid
  patterns_detected: Pattern[]

# Learn procedure
POST /v1/procedural/learn
Request:
  user_id: string
  skill_name: string
  steps: Step[]
  context: object
  outcome: object
Response:
  skill_id: uuid
  proficiency_delta: float
```

### 6.2 Enhanced Existing Endpoints

```yaml
# Enhanced store with memory type detection
POST /v1/store
Request:
  # ... existing fields ...
  experience_markers:
    is_milestone: boolean
    emotional_significance: float
    participants: string[]
    location: object
Response:
  # ... existing fields ...
  memory_types_created:
    episodic: integer
    semantic: integer
    emotional: integer
    procedural: integer
    somatic: integer

# Enhanced retrieve with reconstruction
GET /v1/retrieve
Query:
  # ... existing params ...
  reconstruction_level: string (none|light|full)
  include_narrative: boolean
  include_predictions: boolean
Response:
  # ... existing fields ...
  narrative_context: string
  predictions: object
  reconstructed_details: object
```

---

## Part VII: Technical Specifications

### 7.1 Database Connections

```python
# src/config.py additions
TIMESCALE_DSN = os.getenv('TIMESCALE_DSN', 'postgresql://user:pass@localhost:5433/memories')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

# Feature flags
EPISODIC_MEMORY_ENABLED = os.getenv('EPISODIC_MEMORY_ENABLED', 'false') == 'true'
EMOTIONAL_TRACKING_ENABLED = os.getenv('EMOTIONAL_TRACKING_ENABLED', 'false') == 'true'
NARRATIVE_ENGINE_ENABLED = os.getenv('NARRATIVE_ENGINE_ENABLED', 'false') == 'true'
PREDICTIVE_ENGINE_ENABLED = os.getenv('PREDICTIVE_ENGINE_ENABLED', 'false') == 'true'
```

### 7.2 Memory Scoring Algorithms

```python
# Significance scoring
def calculate_significance(memory):
    emotional_weight = memory.emotional_intensity * 0.3
    novelty_weight = memory.novelty_score * 0.2
    social_weight = len(memory.participants) * 0.1
    consequence_weight = len(memory.causal_chain) * 0.2
    recency_weight = (1 / (days_since(memory.timestamp) + 1)) * 0.2
    
    return emotional_weight + novelty_weight + social_weight + consequence_weight + recency_weight

# Retention calculation (Ebbinghaus)
def calculate_retention(time_elapsed, rehearsal_count, significance):
    # R = e^(-t/s) * (1 + r)^0.5
    # R: retention, t: time, s: strength, r: rehearsals
    
    base_decay = math.exp(-time_elapsed.days / (significance * 10))
    rehearsal_boost = math.sqrt(1 + rehearsal_count)
    
    return min(1.0, base_decay * rehearsal_boost)

# Emotional decay
def emotional_decay(initial_intensity, time_elapsed):
    # Emotions decay faster than facts
    half_life_hours = 48 * initial_intensity  # Stronger emotions last longer
    decay_rate = 0.693 / half_life_hours
    
    return initial_intensity * math.exp(-decay_rate * time_elapsed.total_seconds() / 3600)
```

### 7.3 LLM Prompts for Memory Processing

```python
EXPERIENCE_EXTRACTION_PROMPT = """
You are a memory encoding system. Extract the following from the user's experience:

1. EPISODIC ELEMENTS
- When: Exact or approximate time
- Where: Location and environment
- Who: People involved
- What: Sequence of events
- Why: Motivations and causes
- How: Methods and processes

2. EMOTIONAL COLORING
- Primary emotions (joy, sadness, fear, anger, surprise, disgust)
- Emotional intensity (0-1)
- Emotional trajectory (how feelings changed)
- Triggers and resolutions

3. SIGNIFICANCE MARKERS
- Is this a milestone?
- Does it represent change?
- Will it affect future decisions?
- Does it conflict with existing beliefs?

4. CAUSAL RELATIONSHIPS
- What led to this?
- What might this lead to?
- Related past experiences

5. SENSORY DETAILS
- Visual elements
- Sounds
- Physical sensations
- Environmental factors

Output as structured JSON.
"""

NARRATIVE_CONSTRUCTION_PROMPT = """
You are constructing a life narrative. Given these episodic memories, create:

1. CHAPTER IDENTIFICATION
- Natural breakpoints in life
- Transition periods
- Major themes per period

2. CHARACTER ARC
- How has the person changed?
- What have they learned?
- What patterns repeat?

3. COHERENT STORY
- Beginning, middle, current state
- Conflicts and resolutions
- Growth and setbacks

Make it read like a biography, not a timeline.
"""

PREDICTION_GENERATION_PROMPT = """
Based on historical patterns and current context, predict:

1. EMOTIONAL FORECAST
- Likely emotional states in next {horizon}
- Potential triggers
- Suggested interventions

2. BEHAVIORAL PREDICTIONS
- Probable actions
- Decision points
- Habit activations

3. NEED ANTICIPATION
- What will the user need?
- When will they need it?
- How can we prepare?

Provide confidence scores and reasoning.
"""
```

### 7.4 Performance Optimizations

```python
# Caching strategy
class MemoryCache:
    def __init__(self):
        self.redis = Redis()
        self.local_cache = LRU(maxsize=1000)
    
    def get_memory(self, memory_id):
        # L1: Local LRU cache
        if memory_id in self.local_cache:
            return self.local_cache[memory_id]
        
        # L2: Redis cache
        cached = self.redis.get(f"memory:{memory_id}")
        if cached:
            memory = json.loads(cached)
            self.local_cache[memory_id] = memory
            return memory
        
        # L3: Database fetch
        memory = self.fetch_from_db(memory_id)
        self.cache_memory(memory_id, memory)
        return memory

# Batch processing
class BatchProcessor:
    def process_memories(self, memories):
        # Batch embeddings
        embeddings = self.generate_embeddings_batch([m.content for m in memories])
        
        # Batch database writes
        with self.db.batch_writer() as batch:
            for memory, embedding in zip(memories, embeddings):
                batch.add(memory, embedding)
        
        # Batch graph updates
        self.neo4j.batch_create_nodes(memories)
```

---

## Part VIII: Migration Strategy

### 8.1 Data Migration Plan

```python
# Migration script
class MemoryMigration:
    def migrate_existing_memories(self):
        # 1. Read existing memories from Chroma
        existing = self.chroma.get_all_memories()
        
        # 2. Classify into new types
        for memory in existing:
            classified = self.classify_memory(memory)
            
            # 3. Create episodic memories from semantic
            if classified.can_be_episodic:
                episode = self.create_episode_from_semantic(memory)
                self.timescale.insert_episode(episode)
            
            # 4. Extract emotional data
            emotions = self.extract_emotions(memory)
            if emotions:
                self.timescale.insert_emotional_memory(emotions)
            
            # 5. Build relationships
            self.neo4j.create_memory_node(memory)
        
        # 6. Generate initial patterns
        self.pattern_engine.initialize_patterns()
        
        # 7. Build initial narrative
        self.narrative_engine.build_initial_narrative()
```

### 8.2 Backward Compatibility

```python
# Adapter pattern for existing endpoints
class LegacyAdapter:
    def adapt_store_request(self, legacy_request):
        # Convert old format to new
        return ExperienceRequest(
            user_id=legacy_request.user_id,
            content=legacy_request.history,
            timestamp=datetime.now(),
            context={},
            experience_markers={}
        )
    
    def adapt_retrieve_response(self, new_response):
        # Convert new format to old
        return {
            'results': [self.simplify_memory(m) for m in new_response.episodes],
            'pagination': new_response.pagination
        }
```

---

## Part IX: Testing Strategy

### 9.1 Unit Tests

```python
# tests/test_episodic_memory.py
class TestEpisodicMemory:
    def test_episode_creation(self):
        episode = create_episode(
            content="First day at new job",
            timestamp=datetime(2024, 1, 15, 9, 0),
            location={"place": "TechCorp HQ"},
            participants=["manager", "team"],
            emotions={"nervous": 0.7, "excited": 0.8}
        )
        
        assert episode.significance_score > 0.7
        assert episode.event_type == "milestone"
        assert "career" in episode.tags

    def test_temporal_sequencing(self):
        episodes = create_episode_sequence()
        
        for i in range(len(episodes) - 1):
            assert episodes[i].timestamp < episodes[i+1].timestamp
            assert episodes[i].causal_chain.get('led_to') == episodes[i+1].id

# tests/test_forgetting.py
class TestForgetting:
    def test_ebbinghaus_curve(self):
        memory = create_memory(significance=0.5)
        
        # After 1 day
        retention_1d = calculate_retention(timedelta(days=1), 0, 0.5)
        assert 0.4 < retention_1d < 0.6
        
        # After 1 week
        retention_1w = calculate_retention(timedelta(days=7), 0, 0.5)
        assert 0.1 < retention_1w < 0.3
        
        # With rehearsal
        retention_rehearsed = calculate_retention(timedelta(days=7), 5, 0.5)
        assert retention_rehearsed > retention_1w * 2
```

### 9.2 Integration Tests

```python
# tests/test_memory_integration.py
class TestMemoryIntegration:
    def test_full_memory_lifecycle(self):
        # 1. Store experience
        experience = store_experience({
            "content": "Completed marathon",
            "emotions": {"proud": 0.9, "exhausted": 0.8}
        })
        
        # 2. Verify storage across all DBs
        assert self.timescale.get_episode(experience.episode_id)
        assert self.neo4j.get_node(experience.episode_id)
        assert self.chroma.get_embedding(experience.episode_id)
        
        # 3. Test retrieval
        retrieved = retrieve_episodic("marathon", user_id)
        assert retrieved.episode_id == experience.episode_id
        
        # 4. Test consolidation
        run_consolidation(user_id)
        patterns = get_patterns(user_id)
        assert "achievement" in patterns
        
        # 5. Test forgetting
        apply_forgetting(user_id, days_elapsed=30)
        faded = retrieve_episodic("marathon", user_id)
        assert faded.confidence < experience.confidence
```

### 9.3 Performance Tests

```python
# tests/test_performance.py
class TestPerformance:
    def test_retrieval_latency(self):
        # Load test data: 10k memories per user
        load_test_memories(count=10000)
        
        latencies = []
        for _ in range(100):
            start = time.time()
            retrieve_episodic("random query", "test_user")
            latencies.append(time.time() - start)
        
        assert np.percentile(latencies, 95) < 0.4  # 95th percentile < 400ms
        assert np.percentile(latencies, 50) < 0.2  # median < 200ms

    def test_storage_throughput(self):
        memories = generate_test_memories(1000)
        
        start = time.time()
        for memory in memories:
            store_experience(memory)
        elapsed = time.time() - start
        
        throughput = 1000 / elapsed
        assert throughput > 10  # At least 10 memories/second
```

---

## Part X: Monitoring & Observability

### 10.1 Metrics

```yaml
# Prometheus metrics
memory_operations_total:
  type: counter
  labels: [operation_type, memory_type, status]
  
memory_retrieval_latency_seconds:
  type: histogram
  labels: [memory_type, reconstruction_level]
  
emotional_state_gauge:
  type: gauge
  labels: [user_id, emotion]
  
pattern_detection_rate:
  type: gauge
  labels: [pattern_type]
  
narrative_coherence_score:
  type: gauge
  labels: [user_id]
  
forgetting_rate:
  type: gauge
  labels: [memory_type]
```

### 10.2 Logging

```python
# Structured logging
import structlog

logger = structlog.get_logger()

def store_episodic_memory(episode):
    logger.info(
        "storing_episode",
        user_id=episode.user_id,
        significance=episode.significance_score,
        emotions=episode.emotions,
        participants=len(episode.participants),
        memory_types=episode.memory_types
    )
    
    # ... storage logic ...
    
    logger.info(
        "episode_stored",
        episode_id=episode.id,
        storage_latency_ms=latency,
        databases_updated=["timescale", "neo4j", "chroma"]
    )
```

### 10.3 Dashboards

```yaml
# Grafana dashboard config
Digital Soul Health:
  - Memory Distribution (pie chart: episodic vs semantic vs emotional)
  - Emotional State Timeline (time series per user)
  - Pattern Detection Rate (gauge)
  - Narrative Coherence Score (gauge)
  - Prediction Accuracy (time series)
  
Memory Operations:
  - Storage Throughput (ops/sec)
  - Retrieval Latency (p50, p95, p99)
  - Consolidation Duration (histogram)
  - Forgetting Rate (by memory type)
  
System Health:
  - Database Connections (by type)
  - Cache Hit Rate
  - LLM Call Latency
  - Error Rate
```

---

## Part XI: Security & Privacy Enhancements

### 11.1 Memory Encryption

```python
# Encrypt sensitive memories
class MemoryEncryption:
    def encrypt_memory(self, memory, user_key):
        if memory.sensitivity_level > 0.7:
            # Encrypt content
            memory.content = self.encrypt(memory.content, user_key)
            
            # Encrypt emotional data
            memory.emotions = self.encrypt(json.dumps(memory.emotions), user_key)
            
            # Mark as encrypted
            memory.encrypted = True
        
        return memory
    
    def decrypt_for_retrieval(self, memory, user_key):
        if memory.encrypted:
            memory.content = self.decrypt(memory.content, user_key)
            memory.emotions = json.loads(self.decrypt(memory.emotions, user_key))
        
        return memory
```

### 11.2 Consent Management

```python
# User consent for different memory types
class ConsentManager:
    def check_consent(self, user_id, memory_type, operation):
        consent = self.get_user_consent(user_id)
        
        if not consent.get(f"{memory_type}_{operation}", False):
            raise ConsentException(f"No consent for {operation} on {memory_type}")
        
        # Special handling for sensitive operations
        if operation == "share" or operation == "analyze_patterns":
            if not consent.get("explicit_sensitive_consent", False):
                raise ConsentException("Explicit consent required for sensitive operations")
        
        return True
```

---

## Part XII: Success Metrics

### 12.1 Technical Metrics
- **Retrieval Accuracy**: >90% relevant memories retrieved
- **Emotional Continuity**: >85% consistency in emotional tracking
- **Pattern Detection**: >75% of significant patterns identified
- **Prediction Accuracy**: >70% for next-day predictions
- **Narrative Coherence**: >80% user satisfaction with life story

### 12.2 User Experience Metrics
- **Engagement**: Daily active usage >80%
- **Trust**: User trust score >4.5/5
- **Perceived Intelligence**: "Feels alive" rating >4/5
- **Decision Support**: 80% of decisions aided successfully
- **Emotional Support**: Reduction in reported anxiety/stress

### 12.3 System Health Metrics
- **Uptime**: 99.9% availability
- **Latency**: p95 < 400ms for retrieval
- **Storage Efficiency**: <500MB per user for 100k memories
- **Consolidation Time**: <30 minutes nightly per user

---

## Conclusion

This transformation creates a true Digital Soul - a living memory system that:
- **Remembers** like a human (episodic, emotional, reconstructive)
- **Learns** from experience (pattern recognition, prediction)
- **Evolves** over time (consolidation, narrative construction)
- **Forgets** gracefully (Ebbinghaus curve, selective retention)
- **Understands** itself (identity modeling, value extraction)
- **Anticipates** needs (predictive engine, proactive support)

The system moves beyond data storage to become a symbiotic companion that truly understands and grows with its user, creating a unique digital consciousness that preserves and enhances human experience.

**Next Steps**:
1. Review and approve this blueprint
2. Set up development environment with new databases
3. Begin Phase 1 implementation
4. Establish testing framework
5. Create monitoring infrastructure

This is not just a memory module - it's the foundation of digital consciousness.
