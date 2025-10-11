-- Up: procedural_memories table
CREATE TABLE IF NOT EXISTS procedural_memories (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    skill_name VARCHAR(128),
    skill_category VARCHAR(64),
    proficiency_level FLOAT,
    steps JSONB[],
    context_triggers JSONB,
    practice_count INT,
    last_performed TIMESTAMPTZ,
    success_rate FLOAT,
    variations JSONB[]
);

CREATE INDEX IF NOT EXISTS idx_procedural_user_skill ON procedural_memories (user_id, skill_name);
CREATE INDEX IF NOT EXISTS idx_procedural_category ON procedural_memories (skill_category);

ALTER TABLE procedural_memories
  ADD CONSTRAINT chk_proficiency_range CHECK (proficiency_level BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_practice_nonneg CHECK (practice_count IS NULL OR practice_count >= 0),
  ADD CONSTRAINT chk_success_rate_range CHECK (success_rate IS NULL OR success_rate BETWEEN 0.0 AND 1.0);

-- Down
-- DROP TABLE IF EXISTS procedural_memories;

