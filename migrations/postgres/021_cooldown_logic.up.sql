-- Epic 6 Story 6.3: Cooldown Logic
-- Add cooldown_hours, last_condition_fire, and claimed_at columns
-- for condition-based trigger cooldown and worker claim mechanism

-- 1. Add cooldown_hours column (range 1-168 hours, default 24)
ALTER TABLE scheduled_intents
ADD COLUMN cooldown_hours INT DEFAULT 24
CHECK (cooldown_hours >= 1 AND cooldown_hours <= 168);

-- 2. Add last_condition_fire column (nullable, updated on successful condition fires)
ALTER TABLE scheduled_intents
ADD COLUMN last_condition_fire TIMESTAMPTZ;

-- 3. Add claimed_at column (nullable, for worker claim mechanism)
ALTER TABLE scheduled_intents
ADD COLUMN claimed_at TIMESTAMPTZ;

-- 4. Add comments for the new columns
COMMENT ON COLUMN scheduled_intents.cooldown_hours IS 'Minimum hours between condition-based trigger fires (1-168, default 24)';
COMMENT ON COLUMN scheduled_intents.last_condition_fire IS 'Timestamp of last successful condition-based trigger fire';
COMMENT ON COLUMN scheduled_intents.claimed_at IS 'Timestamp when worker claimed this intent for processing (expires after 5 min)';

-- Note: All columns are nullable/have defaults for backward compatibility with existing triggers
