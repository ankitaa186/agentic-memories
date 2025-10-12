-- Migration: Create episodic memories table with TimescaleDB
-- Digital Soul Memory Architecture v2.0

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb";

-- Create episodic memories table
CREATE TABLE IF NOT EXISTS episodic_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(32) CHECK (event_type IN ('milestone', 'routine', 'crisis', 'celebration', 'transition', 'discovery')),
    content TEXT NOT NULL,
    
    -- Location and context
    location JSONB DEFAULT '{}',  -- {place, coordinates, weather, environment}
    participants TEXT[] DEFAULT '{}',  -- people present
    
    -- Emotional dimensions
    emotional_valence FLOAT CHECK (emotional_valence >= -1 AND emotional_valence <= 1),  -- negative to positive
    emotional_arousal FLOAT CHECK (emotional_arousal >= 0 AND emotional_arousal <= 1),  -- calm to excited
    emotional_tags TEXT[] DEFAULT '{}',  -- specific emotions present
    
    -- Sensory and experiential context
    sensory_context JSONB DEFAULT '{}',  -- {sounds, smells, visuals, physical_sensations}
    
    -- Causal relationships
    causal_chain JSONB DEFAULT '{}',  -- {triggered_by: [], led_to: []}
    
    -- Memory metadata
    significance_score FLOAT DEFAULT 0.5 CHECK (significance_score >= 0 AND significance_score <= 1),
    novelty_score FLOAT DEFAULT 0.5 CHECK (novelty_score >= 0 AND novelty_score <= 1),
    
    -- Memory dynamics
    replay_count INT DEFAULT 0,
    last_recalled TIMESTAMPTZ,
    decay_factor FLOAT DEFAULT 1.0 CHECK (decay_factor >= 0 AND decay_factor <= 1),
    consolidation_level INT DEFAULT 0,  -- 0: new, 1: consolidated, 2: integrated
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to TimescaleDB hypertable for efficient time-based queries
SELECT create_hypertable('episodic_memories', 'event_timestamp', 
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- Create indexes for efficient querying
CREATE INDEX idx_episodic_user_id ON episodic_memories(user_id);
CREATE INDEX idx_episodic_event_type ON episodic_memories(event_type);
CREATE INDEX idx_episodic_significance ON episodic_memories(significance_score DESC);
CREATE INDEX idx_episodic_emotional_valence ON episodic_memories(emotional_valence);
CREATE INDEX idx_episodic_participants ON episodic_memories USING GIN(participants);
CREATE INDEX idx_episodic_location ON episodic_memories USING GIN(location);
CREATE INDEX idx_episodic_last_recalled ON episodic_memories(last_recalled DESC);

-- Create update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_episodic_memories_updated_at 
    BEFORE UPDATE ON episodic_memories 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
