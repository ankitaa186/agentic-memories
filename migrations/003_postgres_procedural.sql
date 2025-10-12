-- Up: procedural_memories table
-- Schema aligned with ProceduralMemoryService requirements
CREATE TABLE IF NOT EXISTS procedural_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    skill_name VARCHAR(128) NOT NULL,
    proficiency_level VARCHAR(32),  -- beginner, intermediate, advanced, expert, master
    steps JSONB,  -- Array of step descriptions
    prerequisites JSONB,  -- Array of prerequisite skills
    last_practiced TIMESTAMPTZ,  -- Changed from last_performed to last_practiced
    practice_count INT DEFAULT 0,
    success_rate FLOAT,  -- 0.0 to 1.0
    difficulty_rating FLOAT,  -- 0.0 to 1.0
    context TEXT,
    tags TEXT[],
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_procedural_user_skill ON procedural_memories (user_id, skill_name);
CREATE INDEX IF NOT EXISTS idx_procedural_proficiency ON procedural_memories (proficiency_level);
CREATE INDEX IF NOT EXISTS idx_procedural_last_practiced ON procedural_memories (last_practiced DESC);

ALTER TABLE procedural_memories
  ADD CONSTRAINT chk_practice_nonneg CHECK (practice_count IS NULL OR practice_count >= 0),
  ADD CONSTRAINT chk_success_rate_range CHECK (success_rate IS NULL OR success_rate BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_difficulty_range CHECK (difficulty_rating IS NULL OR difficulty_rating BETWEEN 0.0 AND 1.0);

-- Down
-- DROP TABLE IF EXISTS procedural_memories;

