-- Up: identity_memories
CREATE TABLE IF NOT EXISTS identity_memories (
    user_id VARCHAR(64) PRIMARY KEY,
    core_values JSONB[],
    self_concept JSONB,
    ideal_self JSONB,
    feared_self JSONB,
    life_roles JSONB[],
    personality_traits JSONB,
    growth_edges TEXT[],
    contradictions JSONB[],
    last_updated TIMESTAMPTZ
);

ALTER TABLE identity_memories
  ADD CONSTRAINT chk_user_id_len CHECK (char_length(user_id) <= 64);

-- Down
-- DROP TABLE IF EXISTS identity_memories;

