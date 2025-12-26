-- Epic 6 Story 6.1: Timezone Support
-- Add trigger_timezone column to scheduled_intents table

-- 1. Add timezone support column
ALTER TABLE scheduled_intents
ADD COLUMN trigger_timezone VARCHAR(64) DEFAULT 'America/Los_Angeles';

-- 2. Update trigger type constraint to include 'portfolio' and remove unused types
ALTER TABLE scheduled_intents
DROP CONSTRAINT IF EXISTS chk_trigger_type;

ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_trigger_type CHECK (
    trigger_type IN ('cron', 'interval', 'once', 'price', 'silence', 'portfolio')
);

-- 3. Add comment for the new column
COMMENT ON COLUMN scheduled_intents.trigger_timezone IS 'IANA timezone for trigger scheduling (e.g., America/Los_Angeles, Europe/London)';

-- Note: Existing records will automatically get 'America/Los_Angeles' as default
