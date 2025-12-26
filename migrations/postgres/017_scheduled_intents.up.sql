-- Scheduled Intents (PostgreSQL)
-- Stores trigger definitions for Annie's proactive messaging system
-- Supports cron, interval, one-time, price, silence, event, calendar, and news triggers

CREATE TABLE IF NOT EXISTS scheduled_intents (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    intent_name VARCHAR(256) NOT NULL,
    description TEXT,

    -- Trigger Definition
    trigger_type VARCHAR(32) NOT NULL,
    trigger_schedule JSONB,
    trigger_condition JSONB,

    -- Action Configuration
    action_type VARCHAR(64) NOT NULL DEFAULT 'notify',
    action_context TEXT NOT NULL,
    action_priority VARCHAR(16) NOT NULL DEFAULT 'normal',

    -- Scheduling State (managed by agentic-memories)
    next_check TIMESTAMPTZ,
    last_checked TIMESTAMPTZ,
    last_executed TIMESTAMPTZ,
    execution_count INT NOT NULL DEFAULT 0,

    -- Execution Results
    last_execution_status VARCHAR(32),
    last_execution_error TEXT,
    last_message_id VARCHAR(128),

    -- Control
    enabled BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ,
    max_executions INT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64),
    metadata JSONB DEFAULT '{}'
);

-- Add CHECK constraints
ALTER TABLE scheduled_intents
    ADD CONSTRAINT chk_trigger_type CHECK (
        trigger_type IN ('cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news')
    ),
    ADD CONSTRAINT chk_action_type CHECK (
        action_type IN ('notify', 'check_in', 'briefing', 'analysis', 'reminder')
    ),
    ADD CONSTRAINT chk_action_priority CHECK (
        action_priority IN ('low', 'normal', 'high', 'critical')
    ),
    ADD CONSTRAINT chk_execution_count_positive CHECK (
        execution_count >= 0
    ),
    ADD CONSTRAINT chk_max_executions_positive CHECK (
        max_executions IS NULL OR max_executions > 0
    );

-- Indexes for efficient queries
-- Index for listing user's enabled intents
CREATE INDEX IF NOT EXISTS idx_intents_user_enabled
    ON scheduled_intents (user_id, enabled)
    WHERE enabled = true;

-- Index for pending query (intents due for checking)
CREATE INDEX IF NOT EXISTS idx_intents_pending
    ON scheduled_intents (next_check)
    WHERE enabled = true AND next_check IS NOT NULL;

-- Index for filtering by trigger type
CREATE INDEX IF NOT EXISTS idx_intents_type
    ON scheduled_intents (user_id, trigger_type);

-- Index for user lookups
CREATE INDEX IF NOT EXISTS idx_intents_user_id
    ON scheduled_intents (user_id);

-- Index for created_at ordering
CREATE INDEX IF NOT EXISTS idx_intents_created
    ON scheduled_intents (created_at DESC);

-- Documentation comments
COMMENT ON TABLE scheduled_intents IS 'Trigger definitions for Annie proactive messaging system';
COMMENT ON COLUMN scheduled_intents.id IS 'Unique identifier for the scheduled intent';
COMMENT ON COLUMN scheduled_intents.user_id IS 'Owner of this intent';
COMMENT ON COLUMN scheduled_intents.intent_name IS 'Human-readable name for the intent';
COMMENT ON COLUMN scheduled_intents.trigger_type IS 'Type of trigger: cron, interval, once, price, silence, event, calendar, news';
COMMENT ON COLUMN scheduled_intents.trigger_schedule IS 'Schedule configuration as JSONB (cron expression, interval_minutes, datetime)';
COMMENT ON COLUMN scheduled_intents.trigger_condition IS 'Condition configuration as JSONB (ticker, operator, value, keywords, threshold)';
COMMENT ON COLUMN scheduled_intents.action_type IS 'Type of action: notify, check_in, briefing, analysis, reminder';
COMMENT ON COLUMN scheduled_intents.action_context IS 'Context passed to LLM when firing the intent';
COMMENT ON COLUMN scheduled_intents.action_priority IS 'Priority level: low, normal, high, critical';
COMMENT ON COLUMN scheduled_intents.next_check IS 'Next scheduled time to check this intent';
COMMENT ON COLUMN scheduled_intents.last_checked IS 'Last time this intent was checked';
COMMENT ON COLUMN scheduled_intents.last_executed IS 'Last time this intent fired successfully';
COMMENT ON COLUMN scheduled_intents.execution_count IS 'Total number of successful executions';
COMMENT ON COLUMN scheduled_intents.last_execution_status IS 'Status of last execution attempt';
COMMENT ON COLUMN scheduled_intents.enabled IS 'Whether this intent is active';
COMMENT ON COLUMN scheduled_intents.expires_at IS 'Optional expiration timestamp';
COMMENT ON COLUMN scheduled_intents.max_executions IS 'Optional maximum number of executions before auto-disable';
COMMENT ON COLUMN scheduled_intents.metadata IS 'Additional metadata as JSONB';
