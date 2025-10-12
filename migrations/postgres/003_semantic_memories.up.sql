-- Up: semantic_memories table
CREATE TABLE IF NOT EXISTS semantic_memories (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64),
    content TEXT,
    category VARCHAR(64),
    subcategory VARCHAR(64),
    confidence FLOAT,
    source_episodes UUID[],
    learned_date TIMESTAMPTZ,
    last_accessed TIMESTAMPTZ,
    access_count INT DEFAULT 0,
    decay_rate FLOAT DEFAULT 0.1,
    reinforcement_threshold FLOAT DEFAULT 0.5
);

CREATE INDEX IF NOT EXISTS idx_semantic_user_category ON semantic_memories (user_id, category, subcategory);
CREATE INDEX IF NOT EXISTS idx_semantic_content_gin ON semantic_memories USING GIN (to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_semantic_source_episodes_gin ON semantic_memories USING GIN (source_episodes);
CREATE INDEX IF NOT EXISTS idx_semantic_last_accessed ON semantic_memories (last_accessed DESC);

ALTER TABLE semantic_memories
  ADD CONSTRAINT chk_category_len CHECK (char_length(category) <= 64),
  ADD CONSTRAINT chk_subcategory_len CHECK (char_length(subcategory) <= 64);

-- Down
-- DROP TABLE IF EXISTS semantic_memories;

