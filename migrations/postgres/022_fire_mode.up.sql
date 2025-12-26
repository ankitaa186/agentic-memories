-- Epic 6 Story 6.4: Fire Mode Support
-- Add fire_mode column for condition-based triggers
-- Allows 'once' (disable after first success) or 'recurring' (default, keep firing)

-- 1. Add fire_mode column with default 'recurring'
ALTER TABLE scheduled_intents
ADD COLUMN fire_mode VARCHAR(16) DEFAULT 'recurring';

-- 2. Add CHECK constraint for valid values
ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_fire_mode CHECK (fire_mode IN ('once', 'recurring'));

-- 3. Add comment for documentation
COMMENT ON COLUMN scheduled_intents.fire_mode IS 'Fire mode for condition triggers: once (disable after first success) or recurring (default)';

-- Note: Column has default 'recurring' for backward compatibility with existing triggers
