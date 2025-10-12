-- Migration: Create procedural memories (skills and how-to knowledge)
-- Digital Soul Memory Architecture v2.0

CREATE TABLE IF NOT EXISTS procedural_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(64) NOT NULL,
    
    -- Skill identification
    skill_name VARCHAR(128) NOT NULL,
    skill_category VARCHAR(64) CHECK (skill_category IN ('physical', 'cognitive', 'social', 'creative', 'technical', 'emotional')),
    skill_domain VARCHAR(128),  -- e.g., "programming", "cooking", "communication"
    
    -- Skill proficiency
    proficiency_level FLOAT CHECK (proficiency_level >= 0 AND proficiency_level <= 1),
    expertise_stage VARCHAR(32) CHECK (expertise_stage IN ('novice', 'beginner', 'competent', 'proficient', 'expert')),
    
    -- Procedural knowledge
    steps JSONB[] NOT NULL,  -- Array of action sequences
    prerequisites TEXT[] DEFAULT '{}',  -- Required skills/knowledge
    tools_required TEXT[] DEFAULT '{}',  -- Physical or software tools
    
    -- Context and triggers
    context_triggers JSONB DEFAULT '{}',  -- When to apply this skill
    application_scenarios TEXT[] DEFAULT '{}',
    contraindications TEXT[] DEFAULT '{}',  -- When NOT to use
    
    -- Practice and performance
    practice_count INT DEFAULT 0,
    successful_applications INT DEFAULT 0,
    failed_attempts INT DEFAULT 0,
    last_performed TIMESTAMPTZ,
    average_duration INTERVAL,
    
    -- Performance metrics
    success_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN (successful_applications + failed_attempts) > 0 
        THEN successful_applications::FLOAT / (successful_applications + failed_attempts) 
        ELSE 0 END
    ) STORED,
    speed_percentile FLOAT,  -- Compared to baseline
    accuracy_score FLOAT CHECK (accuracy_score >= 0 AND accuracy_score <= 1),
    
    -- Variations and adaptations
    variations JSONB[] DEFAULT '{}',  -- Alternative ways learned
    optimizations TEXT[] DEFAULT '{}',  -- Improvements discovered
    common_errors TEXT[] DEFAULT '{}',  -- Mistakes to avoid
    
    -- Learning metadata
    acquisition_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acquisition_method VARCHAR(64),  -- e.g., "taught", "self-learned", "observed"
    teacher_or_source TEXT,
    learning_curve JSONB DEFAULT '{}',  -- Performance over time
    
    -- Decay and maintenance
    skill_decay_rate FLOAT DEFAULT 0.1,  -- How fast skill degrades without practice
    last_reinforcement TIMESTAMPTZ,
    reinforcement_needed BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sub-skills and components table
CREATE TABLE IF NOT EXISTS procedural_components (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_skill_id UUID REFERENCES procedural_memories(id) ON DELETE CASCADE,
    
    component_name VARCHAR(128) NOT NULL,
    component_type VARCHAR(32) CHECK (component_type IN ('substep', 'decision_point', 'checkpoint', 'error_handler')),
    
    -- Component details
    sequence_order INT NOT NULL,
    description TEXT,
    instructions JSONB NOT NULL,
    
    -- Performance tracking
    execution_time_avg INTERVAL,
    error_rate FLOAT CHECK (error_rate >= 0 AND error_rate <= 1),
    mastery_level FLOAT CHECK (mastery_level >= 0 AND mastery_level <= 1),
    
    -- Conditions
    preconditions JSONB DEFAULT '{}',
    postconditions JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skill relationships table (skills that work together)
CREATE TABLE IF NOT EXISTS skill_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    skill_a_id UUID REFERENCES procedural_memories(id) ON DELETE CASCADE,
    skill_b_id UUID REFERENCES procedural_memories(id) ON DELETE CASCADE,
    
    relationship_type VARCHAR(32) CHECK (relationship_type IN ('prerequisite', 'complementary', 'alternative', 'composite')),
    strength FLOAT CHECK (strength >= 0 AND strength <= 1),
    
    -- Usage patterns
    co_occurrence_count INT DEFAULT 0,
    sequence_pattern TEXT,  -- e.g., "A then B", "A or B", "A with B"
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(skill_a_id, skill_b_id)
);

-- Create indexes
CREATE INDEX idx_procedural_user_id ON procedural_memories(user_id);
CREATE INDEX idx_procedural_category ON procedural_memories(skill_category);
CREATE INDEX idx_procedural_proficiency ON procedural_memories(proficiency_level DESC);
CREATE INDEX idx_procedural_last_performed ON procedural_memories(last_performed DESC);
CREATE INDEX idx_procedural_success_rate ON procedural_memories(success_rate DESC);
CREATE INDEX idx_procedural_reinforcement ON procedural_memories(reinforcement_needed, last_reinforcement);

CREATE INDEX idx_components_parent ON procedural_components(parent_skill_id);
CREATE INDEX idx_components_order ON procedural_components(parent_skill_id, sequence_order);

CREATE INDEX idx_skill_rel_a ON skill_relationships(skill_a_id);
CREATE INDEX idx_skill_rel_b ON skill_relationships(skill_b_id);
CREATE INDEX idx_skill_rel_type ON skill_relationships(relationship_type);

-- Update trigger
CREATE TRIGGER update_procedural_memories_updated_at 
    BEFORE UPDATE ON procedural_memories 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
