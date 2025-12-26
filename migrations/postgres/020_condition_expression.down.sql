-- Epic 6 Story 6.2: Condition Expression Support (Rollback)
-- Remove condition_type and condition_expression columns

ALTER TABLE scheduled_intents
DROP COLUMN IF EXISTS condition_expression;

ALTER TABLE scheduled_intents
DROP COLUMN IF EXISTS condition_type;
