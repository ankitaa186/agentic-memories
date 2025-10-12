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
  ADD CONSTRAINT chk_practice_nonneg 
    CHECK (practice_count IS NULL OR practice_count >= 0),
  ADD CONSTRAINT chk_success_rate_range 
    CHECK (success_rate IS NULL OR success_rate BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_difficulty_range 
    CHECK (difficulty_rating IS NULL OR difficulty_rating BETWEEN 0.0 AND 1.0);
