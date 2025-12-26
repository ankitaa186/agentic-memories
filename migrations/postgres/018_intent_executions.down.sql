-- Down migration for intent_executions
-- Must be run BEFORE 017_scheduled_intents.down.sql due to FK dependency

DROP TABLE IF EXISTS intent_executions;
