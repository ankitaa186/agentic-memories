# 🧹 Clean Database Rebuild Plan

## Objective
Drop all existing tables and rebuild with clean schemas containing ONLY the columns the code actually uses. No extra v1 columns, no FIX files needed.

## Step 1: Backup Current Migrations (for reference)
```bash
mkdir -p migrations/old_v1
mv migrations/001_timescale_episodic.sql migrations/old_v1/
mv migrations/002_postgres_semantic.sql migrations/old_v1/
mv migrations/003_postgres_procedural.sql migrations/old_v1/
mv migrations/004_timescale_emotional.sql migrations/old_v1/
mv migrations/005_postgres_identity.sql migrations/old_v1/

# Remove all FIX files (no longer needed)
rm migrations/FIX_*.sql
```

## Step 2: Create Clean Migration Scripts

### migrations/001_timescale_episodic.sql (CLEAN)
```sql
-- Episodic Memories (TimescaleDB Hypertable)
-- CLEAN schema - only columns code actually uses

CREATE TABLE IF NOT EXISTS episodic_memories (
    id UUID NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type TEXT,
    content TEXT,
    location JSONB,
    participants TEXT[],
    emotional_valence FLOAT,
    emotional_arousal FLOAT,
    importance_score FLOAT,
    tags TEXT[],
    metadata JSONB
);

-- Convert to hypertable
SELECT create_hypertable('episodic_memories', 'event_timestamp', if_not_exists => TRUE);

-- Add unique index with partition key (required by TimescaleDB)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_episodic_id_time 
    ON episodic_memories (id, event_timestamp DESC);

-- Additional indexes for queries
CREATE INDEX IF NOT EXISTS idx_episodic_user_time 
    ON episodic_memories (user_id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_episodic_importance 
    ON episodic_memories (importance_score DESC, event_timestamp DESC);

-- Constraints
ALTER TABLE episodic_memories
  ADD CONSTRAINT IF NOT EXISTS chk_emotional_valence_range 
    CHECK (emotional_valence IS NULL OR emotional_valence BETWEEN -1.0 AND 1.0),
  ADD CONSTRAINT IF NOT EXISTS chk_emotional_arousal_range 
    CHECK (emotional_arousal IS NULL OR emotional_arousal BETWEEN 0.0 AND 1.0);

-- TimescaleDB optimizations
SELECT set_chunk_time_interval('episodic_memories', INTERVAL '7 days');

ALTER TABLE episodic_memories
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'event_timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('episodic_memories', INTERVAL '30 days');
-- SELECT add_retention_policy('episodic_memories', INTERVAL '730 days');  -- 2 years
```

### migrations/002_postgres_semantic.sql (CLEAN - for Phase 3)
```sql
-- Semantic Memories (PostgreSQL)
-- Placeholder for Phase 3 implementation

CREATE TABLE IF NOT EXISTS semantic_memories (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(64),
    confidence FLOAT,
    source TEXT,
    first_learned TIMESTAMPTZ DEFAULT NOW(),
    last_reinforced TIMESTAMPTZ DEFAULT NOW(),
    access_count INT DEFAULT 0,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_semantic_user_category 
    ON semantic_memories (user_id, category);
```

### migrations/003_postgres_procedural.sql (CLEAN)
```sql
-- Procedural Memories (PostgreSQL)
-- CLEAN schema - only columns code actually uses

CREATE TABLE IF NOT EXISTS procedural_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    proficiency_level VARCHAR(32),  -- beginner, intermediate, advanced, expert, master
    steps JSONB,
    prerequisites JSONB,
    last_practiced TIMESTAMPTZ,
    practice_count INT DEFAULT 0,
    success_rate FLOAT,
    difficulty_rating FLOAT,
    context TEXT,
    tags TEXT[],
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_procedural_user_skill 
    ON procedural_memories (user_id, skill_name);

CREATE INDEX IF NOT EXISTS idx_procedural_proficiency 
    ON procedural_memories (proficiency_level);

ALTER TABLE procedural_memories
  ADD CONSTRAINT IF NOT EXISTS chk_practice_nonneg 
    CHECK (practice_count IS NULL OR practice_count >= 0),
  ADD CONSTRAINT IF NOT EXISTS chk_success_rate_range 
    CHECK (success_rate IS NULL OR success_rate BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT IF NOT EXISTS chk_difficulty_range 
    CHECK (difficulty_rating IS NULL OR difficulty_rating BETWEEN 0.0 AND 1.0);
```

### migrations/003b_postgres_skill_progressions.sql (NEW)
```sql
-- Skill Progressions Tracking (PostgreSQL)
-- Tracks practice sessions and skill improvement over time

CREATE TABLE IF NOT EXISTS skill_progressions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    proficiency_level VARCHAR(32),
    practice_session_duration INT,  -- minutes
    success_rate FLOAT,
    notes TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_skill_progression_user_skill 
    ON skill_progressions (user_id, skill_name, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_skill_progression_timestamp 
    ON skill_progressions (timestamp DESC);

ALTER TABLE skill_progressions
  ADD CONSTRAINT IF NOT EXISTS chk_progression_success_rate 
    CHECK (success_rate IS NULL OR success_rate BETWEEN 0.0 AND 1.0);
```

### migrations/004_timescale_emotional.sql (CLEAN)
```sql
-- Emotional Memories (TimescaleDB Hypertable)
-- CLEAN schema - only columns code actually uses

CREATE TABLE IF NOT EXISTS emotional_memories (
    id UUID NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    emotional_state VARCHAR(64),
    valence FLOAT,
    arousal FLOAT,
    dominance FLOAT,
    context TEXT,
    trigger_event TEXT,
    intensity FLOAT,
    duration_minutes INT,
    metadata JSONB
);

-- Convert to hypertable
SELECT create_hypertable('emotional_memories', 'timestamp', if_not_exists => TRUE);

-- Add unique index with partition key
CREATE UNIQUE INDEX IF NOT EXISTS uniq_emotional_id_time 
    ON emotional_memories (id, timestamp DESC);

-- Additional indexes
CREATE INDEX IF NOT EXISTS idx_emotional_user_time 
    ON emotional_memories (user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_emotional_state 
    ON emotional_memories (emotional_state, timestamp DESC);

-- Constraints
ALTER TABLE emotional_memories
  ADD CONSTRAINT IF NOT EXISTS chk_emotional_valence_range 
    CHECK (valence IS NULL OR valence BETWEEN -1.0 AND 1.0),
  ADD CONSTRAINT IF NOT EXISTS chk_emotional_arousal_range 
    CHECK (arousal IS NULL OR arousal BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT IF NOT EXISTS chk_emotional_dominance_range 
    CHECK (dominance IS NULL OR dominance BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT IF NOT EXISTS chk_intensity_range 
    CHECK (intensity IS NULL OR intensity BETWEEN 0.0 AND 1.0);

-- TimescaleDB optimizations
SELECT set_chunk_time_interval('emotional_memories', INTERVAL '3 days');

ALTER TABLE emotional_memories
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('emotional_memories', INTERVAL '14 days');
```

### migrations/004b_postgres_emotional_patterns.sql (CLEAN)
```sql
-- Emotional Patterns (PostgreSQL)
-- Placeholder - not actively used yet

CREATE TABLE IF NOT EXISTS emotional_patterns (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    pattern_name VARCHAR(128),
    trigger_conditions JSONB,
    typical_response JSONB,
    frequency FLOAT,
    interventions JSONB[],
    effectiveness_scores JSONB
);

CREATE INDEX IF NOT EXISTS idx_emotional_patterns_user 
    ON emotional_patterns (user_id);
```

### migrations/005_postgres_identity.sql (CLEAN - for Phase 3)
```sql
-- Identity Memories (PostgreSQL)
-- Placeholder for Phase 3 implementation

CREATE TABLE IF NOT EXISTS identity_memories (
    user_id VARCHAR(64) PRIMARY KEY,
    core_values TEXT[],
    self_concept TEXT,
    personality_traits JSONB,
    life_goals TEXT[],
    beliefs JSONB,
    preferences JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### migrations/006_neo4j_graph.cql (UNCHANGED - already clean)
```cypher
-- Neo4j Graph Constraints

CREATE CONSTRAINT episode_id_unique IF NOT EXISTS
FOR (e:Episode) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT emotion_id_unique IF NOT EXISTS
FOR (em:EmotionalState) REQUIRE em.id IS UNIQUE;

CREATE CONSTRAINT skill_id_unique IF NOT EXISTS
FOR (s:Skill) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT holding_id_unique IF NOT EXISTS
FOR (h:Holding) REQUIRE h.id IS UNIQUE;
```

### migrations/007_chroma_collections.py (UNCHANGED - already clean)
```python
# ChromaDB Collections - no changes needed
```

### migrations/008_postgres_portfolio.sql (ALREADY CLEAN)
```sql
-- Portfolio tables are already clean - no changes needed
```

### migrations/009_timescale_portfolio_snapshots.sql (ALREADY CLEAN)
```sql
-- Portfolio snapshots already clean - no changes needed
```

### migrations/010_neo4j_portfolio_graph.cql (UNCHANGED)
```cypher
-- Portfolio graph constraints - no changes needed
```

## Step 3: Drop All Existing Tables

Create drop script: `migrations/DROP_ALL.sql`

```sql
-- Drop all tables for clean rebuild
-- WARNING: This deletes all data!

DROP TABLE IF EXISTS episodic_memories CASCADE;
DROP TABLE IF EXISTS emotional_memories CASCADE;
DROP TABLE IF EXISTS emotional_patterns CASCADE;
DROP TABLE IF EXISTS procedural_memories CASCADE;
DROP TABLE IF EXISTS skill_progressions CASCADE;
DROP TABLE IF EXISTS semantic_memories CASCADE;
DROP TABLE IF EXISTS identity_memories CASCADE;
DROP TABLE IF EXISTS portfolio_holdings CASCADE;
DROP TABLE IF EXISTS portfolio_transactions CASCADE;
DROP TABLE IF EXISTS portfolio_preferences CASCADE;
DROP TABLE IF EXISTS portfolio_snapshots CASCADE;

-- Verify all tables dropped
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

## Step 4: Execution Order

```bash
# 1. Drop all tables
psql $TIMESCALE_DSN < migrations/DROP_ALL.sql

# 2. Run clean migrations in order
psql $TIMESCALE_DSN < migrations/001_timescale_episodic.sql
psql $TIMESCALE_DSN < migrations/002_postgres_semantic.sql
psql $TIMESCALE_DSN < migrations/003_postgres_procedural.sql
psql $TIMESCALE_DSN < migrations/003b_postgres_skill_progressions.sql
psql $TIMESCALE_DSN < migrations/004_timescale_emotional.sql
psql $TIMESCALE_DSN < migrations/004b_postgres_emotional_patterns.sql
psql $TIMESCALE_DSN < migrations/005_postgres_identity.sql
psql $TIMESCALE_DSN < migrations/008_postgres_portfolio.sql
psql $TIMESCALE_DSN < migrations/009_timescale_portfolio_snapshots.sql

# 3. Neo4j
docker exec agentic-memories-neo4j-1 cypher-shell -u neo4j -p password < migrations/006_neo4j_graph.cql
docker exec agentic-memories-neo4j-1 cypher-shell -u neo4j -p password < migrations/010_neo4j_portfolio_graph.cql

# 4. ChromaDB (if needed)
python migrations/007_chroma_collections.py
```

## Step 5: Verify Clean Schema

```bash
# Check all tables
psql $TIMESCALE_DSN -c "\dt"

# Verify episodic schema
psql $TIMESCALE_DSN -c "\d episodic_memories"

# Verify emotional schema
psql $TIMESCALE_DSN -c "\d emotional_memories"

# Verify procedural schema
psql $TIMESCALE_DSN -c "\d procedural_memories"

# Verify skill_progressions exists
psql $TIMESCALE_DSN -c "\d skill_progressions"

# Verify portfolio schemas
psql $TIMESCALE_DSN -c "\d portfolio_holdings"
psql $TIMESCALE_DSN -c "\d portfolio_snapshots"
```

## Expected Column Counts After Rebuild

| Table | Columns | Notes |
|-------|---------|-------|
| episodic_memories | 12 | Clean (was 17) |
| emotional_memories | 12 | Clean (was 18) |
| procedural_memories | 13 | Clean (unchanged) |
| skill_progressions | 9 | NEW TABLE |
| portfolio_holdings | 20 | Clean (unchanged) |
| portfolio_snapshots | 10 | Clean (unchanged) |

## Benefits

✅ **No more FIX files** - clean schema from start  
✅ **No extra columns** - only what code uses  
✅ **New skill_progressions table** - fixes missing table issue  
✅ **Simpler migrations** - easier to understand  
✅ **Dev env only** - safe to drop/rebuild  
✅ **Future-proof** - clean foundation for Phase 3

## Next Steps After Rebuild

1. Test all storage operations
2. Complete connection pooling for remaining services
3. Test multi-type storage (should work without cascading failures)
4. Proceed to Phase 3 (Semantic & Identity memories)

