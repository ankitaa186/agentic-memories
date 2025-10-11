-- Up: emotional_memories (timeseries) and patterns (postgres)
CREATE TABLE IF NOT EXISTS emotional_memories (
    user_id VARCHAR(64),
    timestamp TIMESTAMPTZ,
    emotion_vector FLOAT[],
    triggers JSONB,
    intensity FLOAT,
    duration INTERVAL,
    coping_strategies TEXT[],
    resolution VARCHAR(32),
    linked_episodes UUID[]
);

SELECT create_hypertable('emotional_memories', 'timestamp', if_not_exists => TRUE);

CREATE INDEX idx_emotions_user_time ON emotional_memories (user_id, timestamp DESC);
CREATE INDEX idx_emotions_triggers_gin ON emotional_memories USING GIN (triggers);

ALTER TABLE emotional_memories
  ADD CONSTRAINT chk_intensity_range CHECK (intensity IS NULL OR intensity BETWEEN 0.0 AND 1.0),
  ADD CONSTRAINT chk_duration_positive CHECK (duration IS NULL OR duration >= INTERVAL '0');

SELECT set_chunk_time_interval('emotional_memories', INTERVAL '3 days');

ALTER TABLE emotional_memories
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('emotional_memories', INTERVAL '14 days');
#SELECT add_retention_policy('emotional_memories', INTERVAL '180 days');

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

