-- Up: emotional_memories (timeseries) and patterns (postgres)
-- Schema aligned with EmotionalMemoryService requirements
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

SELECT create_hypertable('emotional_memories', 'timestamp', if_not_exists => TRUE);

-- Add unique index with partition key
CREATE UNIQUE INDEX IF NOT EXISTS uniq_emotional_id_time ON emotional_memories (id, timestamp DESC);

-- Additional indexes
CREATE INDEX IF NOT EXISTS idx_emotions_user_time ON emotional_memories (user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_emotions_state ON emotional_memories (emotional_state, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_emotions_valence ON emotional_memories (valence, timestamp DESC);

-- Add constraints for dimensional ranges
ALTER TABLE emotional_memories
  ADD CONSTRAINT chk_emotional_valence_range CHECK (valence IS NULL OR valence BETWEEN -1.0 AND 1.0),
  ADD CONSTRAINT chk_emotional_arousal_range CHECK (arousal IS NULL OR arousal BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_emotional_dominance_range CHECK (dominance IS NULL OR dominance BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_intensity_range CHECK (intensity IS NULL OR intensity BETWEEN 0.0 AND 1.0);

SELECT set_chunk_time_interval('emotional_memories', INTERVAL '3 days');

ALTER TABLE emotional_memories
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('emotional_memories', INTERVAL '14 days');
-- SELECT add_retention_policy('emotional_memories', INTERVAL '180 days');

-- Patterns table (plain Postgres)
CREATE TABLE IF NOT EXISTS emotional_patterns (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64),
    pattern_name VARCHAR(128),
    trigger_conditions JSONB,
    typical_response JSONB,
    frequency FLOAT,
    interventions JSONB[],
    effectiveness_scores JSONB
);

-- Down
-- DROP TABLE IF EXISTS emotional_patterns;
-- DROP TABLE IF EXISTS emotional_memories;

