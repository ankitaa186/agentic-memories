-- Intent Executions (PostgreSQL)
-- Audit trail for scheduled intent execution attempts
-- Tracks success, failure, gate blocks, and timing metrics

CREATE TABLE IF NOT EXISTS intent_executions (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id UUID NOT NULL,
    user_id VARCHAR(64) NOT NULL,

    -- Execution Details
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger_type VARCHAR(32) NOT NULL,
    trigger_data JSONB,
    status VARCHAR(32) NOT NULL,

    -- Gate and Message Results
    gate_result JSONB,
    message_id VARCHAR(128),
    message_preview TEXT,

    -- Timing Metrics (milliseconds)
    evaluation_ms INT,
    generation_ms INT,
    delivery_ms INT,

    -- Error Tracking
    error_message TEXT,

    -- Foreign Key Constraint
    CONSTRAINT fk_intent_executions_intent
        FOREIGN KEY (intent_id)
        REFERENCES scheduled_intents(id)
        ON DELETE CASCADE
);

-- Add CHECK constraint for status values
ALTER TABLE intent_executions
    ADD CONSTRAINT chk_execution_status CHECK (
        status IN ('success', 'failed', 'gate_blocked', 'condition_not_met')
    ),
    ADD CONSTRAINT chk_evaluation_ms_positive CHECK (
        evaluation_ms IS NULL OR evaluation_ms >= 0
    ),
    ADD CONSTRAINT chk_generation_ms_positive CHECK (
        generation_ms IS NULL OR generation_ms >= 0
    ),
    ADD CONSTRAINT chk_delivery_ms_positive CHECK (
        delivery_ms IS NULL OR delivery_ms >= 0
    );

-- Indexes for efficient queries
-- Index for querying executions by intent (most common query)
CREATE INDEX IF NOT EXISTS idx_executions_intent
    ON intent_executions (intent_id, executed_at DESC);

-- Index for querying executions by user
CREATE INDEX IF NOT EXISTS idx_executions_user
    ON intent_executions (user_id, executed_at DESC);

-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_executions_status
    ON intent_executions (status, executed_at DESC);

-- Documentation comments
COMMENT ON TABLE intent_executions IS 'Audit trail for scheduled intent execution attempts';
COMMENT ON COLUMN intent_executions.id IS 'Unique identifier for the execution record';
COMMENT ON COLUMN intent_executions.intent_id IS 'Reference to the scheduled intent that was executed';
COMMENT ON COLUMN intent_executions.user_id IS 'Owner of the intent (denormalized for query efficiency)';
COMMENT ON COLUMN intent_executions.executed_at IS 'Timestamp when execution was attempted';
COMMENT ON COLUMN intent_executions.trigger_type IS 'Type of trigger that caused this execution';
COMMENT ON COLUMN intent_executions.trigger_data IS 'Snapshot of trigger data at execution time';
COMMENT ON COLUMN intent_executions.status IS 'Execution result: success, failed, gate_blocked, condition_not_met';
COMMENT ON COLUMN intent_executions.gate_result IS 'Result from Annie subconscious gate evaluation';
COMMENT ON COLUMN intent_executions.message_id IS 'ID of delivered message (if successful)';
COMMENT ON COLUMN intent_executions.message_preview IS 'Preview of generated message content';
COMMENT ON COLUMN intent_executions.evaluation_ms IS 'Time spent evaluating trigger condition';
COMMENT ON COLUMN intent_executions.generation_ms IS 'Time spent generating message via LLM';
COMMENT ON COLUMN intent_executions.delivery_ms IS 'Time spent delivering message';
COMMENT ON COLUMN intent_executions.error_message IS 'Error details if execution failed';
