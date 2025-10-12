-- Skill Progressions Tracking (PostgreSQL)
-- Tracks practice sessions and skill improvement over time
-- NEW TABLE - fixes "relation skill_progressions does not exist" error

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
  ADD CONSTRAINT chk_progression_success_rate 
    CHECK (success_rate IS NULL OR success_rate BETWEEN 0.0 AND 1.0);

