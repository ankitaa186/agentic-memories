-- Active: 1760219202030@@127.0.0.1@5433@agentic_memories
-- Up: create episodic_memories table and hypertable


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
    sensory_context JSONB,
    causal_chain JSONB,
    importance_score FLOAT,
    tags TEXT[],
    metadata JSONB,
    replay_count INT DEFAULT 0,
    last_recalled TIMESTAMPTZ,
    decay_factor FLOAT DEFAULT 1.0
);

-- If an old primary key exists that does not include the partition key, drop it
ALTER TABLE episodic_memories DROP CONSTRAINT IF EXISTS episodic_memories_pkey;

-- Ensure required columns are NOT NULL (idempotent if already set)
ALTER TABLE episodic_memories
  ALTER COLUMN id SET NOT NULL,
  ALTER COLUMN user_id SET NOT NULL,
  ALTER COLUMN event_timestamp SET NOT NULL;

SELECT create_hypertable('episodic_memories', 'event_timestamp', if_not_exists => TRUE);

-- Composite primary key must include the partitioning column per TimescaleDB rules
-- Simpler: no table-level primary key; enforce uniqueness with a composite unique index
-- Timescale requires the time partition key to be part of any unique index
CREATE UNIQUE INDEX IF NOT EXISTS uniq_episodic_id_time
ON episodic_memories (id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_episodic_user_time ON episodic_memories (user_id, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_event_type ON episodic_memories (event_type);
CREATE INDEX IF NOT EXISTS idx_episodic_location_gin ON episodic_memories USING GIN (location);
CREATE INDEX IF NOT EXISTS idx_episodic_sensory_gin ON episodic_memories USING GIN (sensory_context);

ALTER TABLE episodic_memories ADD CONSTRAINT chk_emotional_valence_range CHECK (emotional_valence IS NULL OR emotional_valence BETWEEN -1.0 AND 1.0);
ALTER TABLE episodic_memories ADD CONSTRAINT chk_emotional_arousal_range CHECK (emotional_arousal IS NULL OR emotional_arousal BETWEEN 0.0 AND 1.0);

SELECT set_chunk_time_interval('episodic_memories', INTERVAL '7 days');

ALTER TABLE episodic_memories
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'event_timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

SELECT add_compression_policy('episodic_memories', INTERVAL '30 days');
#SELECT add_retention_policy('episodic_memories', INTERVAL '365 days', cascade_to_materializations => TRUE);

-- Down: drop table
-- DROP TABLE IF EXISTS episodic_memories;

