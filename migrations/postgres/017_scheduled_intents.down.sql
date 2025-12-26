-- Down migration for scheduled_intents
-- Run AFTER 018_intent_executions.down.sql (FK dependency removed)

DROP TABLE IF EXISTS scheduled_intents;
