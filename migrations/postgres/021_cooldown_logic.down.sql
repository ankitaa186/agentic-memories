-- Rollback: Remove cooldown and claim columns added in Story 6.3

ALTER TABLE scheduled_intents DROP COLUMN IF EXISTS cooldown_hours;
ALTER TABLE scheduled_intents DROP COLUMN IF EXISTS last_condition_fire;
ALTER TABLE scheduled_intents DROP COLUMN IF EXISTS claimed_at;
