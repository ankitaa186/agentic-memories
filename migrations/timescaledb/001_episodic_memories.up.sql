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
  ADD CONSTRAINT chk_emotional_valence_range 
    CHECK (emotional_valence IS NULL OR emotional_valence BETWEEN -1.0 AND 1.0),
  ADD CONSTRAINT chk_emotional_arousal_range 
    CHECK (emotional_arousal IS NULL OR emotional_arousal BETWEEN 0.0 AND 1.0);

-- TimescaleDB optimizations
SELECT set_chunk_time_interval('episodic_memories', INTERVAL '7 days');

ALTER TABLE episodic_memories
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'event_timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('episodic_memories', INTERVAL '30 days');
-- SELECT add_retention_policy('episodic_memories', INTERVAL '730 days');  -- 2 years
