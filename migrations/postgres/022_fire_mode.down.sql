-- Rollback: Remove fire_mode column added in Story 6.4

-- Drop constraint first, then column
ALTER TABLE scheduled_intents DROP CONSTRAINT IF EXISTS chk_fire_mode;
ALTER TABLE scheduled_intents DROP COLUMN IF EXISTS fire_mode;
