-- Migration: Create emotional memories and patterns tables
-- Digital Soul Memory Architecture v2.0

-- Emotional state tracking (continuous time-series)
CREATE TABLE IF NOT EXISTS emotional_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Multi-dimensional emotion space (Plutchik's wheel + custom dimensions)
    emotion_vector FLOAT[] NOT NULL,  -- [joy, sadness, fear, anger, surprise, disgust, trust, anticipation]
    
    -- Core affect dimensions
    valence FLOAT CHECK (valence >= -1 AND valence <= 1),  -- negative to positive
    arousal FLOAT CHECK (arousal >= 0 AND arousal <= 1),  -- low to high energy
    dominance FLOAT CHECK (dominance >= 0 AND dominance <= 1),  -- submissive to dominant
    
    -- Emotional metadata
    primary_emotion VARCHAR(32),
    secondary_emotions TEXT[] DEFAULT '{}',
    intensity FLOAT CHECK (intensity >= 0 AND intensity <= 1),
    duration INTERVAL,
    
    -- Triggers and context
    triggers JSONB DEFAULT '{}',  -- What caused this emotion
    context JSONB DEFAULT '{}',  -- Situational context
    physical_sensations TEXT[] DEFAULT '{}',  -- Body sensations
    thoughts TEXT[] DEFAULT '{}',  -- Associated thoughts
    
    -- Response and resolution
    coping_strategies TEXT[] DEFAULT '{}',
    resolution VARCHAR(32) CHECK (resolution IN ('resolved', 'suppressed', 'expressed', 'transformed', 'ongoing')),
    effectiveness_score FLOAT CHECK (effectiveness_score >= 0 AND effectiveness_score <= 1),
    
    -- Links to other memories
    linked_episodes UUID[] DEFAULT '{}',
    linked_semantic UUID[] DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('emotional_memories', 'timestamp',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE);

-- Emotional patterns table (learned patterns over time)
CREATE TABLE IF NOT EXISTS emotional_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL,
    
    -- Pattern identification
    pattern_name VARCHAR(128) NOT NULL,  -- e.g., "Sunday anxiety", "pre-meeting stress"
    pattern_type VARCHAR(32) CHECK (pattern_type IN ('cyclical', 'triggered', 'reactive', 'baseline')),
    
    -- Pattern characteristics
    trigger_conditions JSONB NOT NULL,  -- Conditions that trigger this pattern
    typical_sequence JSONB DEFAULT '{}',  -- Sequence of emotions
    typical_duration INTERVAL,
    typical_intensity FLOAT CHECK (typical_intensity >= 0 AND typical_intensity <= 1),
    
    -- Pattern metrics
    frequency FLOAT,  -- Occurrences per time unit
    predictability FLOAT CHECK (predictability >= 0 AND predictability <= 1),
    stability FLOAT CHECK (stability >= 0 AND stability <= 1),  -- How consistent the pattern is
    
    -- Interventions and management
    interventions JSONB[] DEFAULT '{}',  -- Attempted interventions
    effectiveness_scores JSONB DEFAULT '{}',  -- Success rates of interventions
    recommended_strategies TEXT[] DEFAULT '{}',
    
    -- Pattern evolution
    first_observed TIMESTAMPTZ NOT NULL,
    last_observed TIMESTAMPTZ,
    observation_count INT DEFAULT 1,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Emotional regulation strategies table
CREATE TABLE IF NOT EXISTS emotional_regulation_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL,
    
    strategy_name VARCHAR(128) NOT NULL,
    strategy_type VARCHAR(32) CHECK (strategy_type IN ('cognitive', 'behavioral', 'somatic', 'social', 'creative')),
    description TEXT,
    
    -- Usage and effectiveness
    usage_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    effectiveness_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN usage_count > 0 THEN success_count::FLOAT / usage_count ELSE 0 END
    ) STORED,
    
    -- Context for application
    best_for_emotions TEXT[] DEFAULT '{}',
    best_for_intensity_range FLOAT[] DEFAULT '{0, 1}',  -- [min, max]
    contraindications TEXT[] DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_emotional_user_timestamp ON emotional_memories(user_id, timestamp DESC);
CREATE INDEX idx_emotional_primary ON emotional_memories(primary_emotion);
CREATE INDEX idx_emotional_intensity ON emotional_memories(intensity DESC);
CREATE INDEX idx_emotional_triggers ON emotional_memories USING GIN(triggers);
CREATE INDEX idx_emotional_resolution ON emotional_memories(resolution);

CREATE INDEX idx_patterns_user_id ON emotional_patterns(user_id);
CREATE INDEX idx_patterns_type ON emotional_patterns(pattern_type);
CREATE INDEX idx_patterns_frequency ON emotional_patterns(frequency DESC);
CREATE INDEX idx_patterns_confidence ON emotional_patterns(confidence_score DESC);

CREATE INDEX idx_strategies_user_id ON emotional_regulation_strategies(user_id);
CREATE INDEX idx_strategies_effectiveness ON emotional_regulation_strategies(effectiveness_rate DESC);

-- Update triggers
CREATE TRIGGER update_emotional_patterns_updated_at 
    BEFORE UPDATE ON emotional_patterns 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at 
    BEFORE UPDATE ON emotional_regulation_strategies 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
