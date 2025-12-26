-- Epic 6 Story 6.1: Timezone Support (Rollback)
-- Remove trigger_timezone column from scheduled_intents table

-- 1. Drop the timezone column
ALTER TABLE scheduled_intents
DROP COLUMN IF EXISTS trigger_timezone;

-- 3. Restore original trigger type constraint
ALTER TABLE scheduled_intents
DROP CONSTRAINT IF EXISTS chk_trigger_type;

ALTER TABLE scheduled_intents
ADD CONSTRAINT chk_trigger_type CHECK (
    trigger_type IN ('cron', 'interval', 'once', 'price', 'silence', 'event', 'calendar', 'news')
);
