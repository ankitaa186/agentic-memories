-- Rollback emotional memories table
-- Removes hypertable, indexes, and table

-- Drop compression policy first
SELECT remove_compression_policy('emotional_memories', if_exists => TRUE);

-- Drop indexes
DROP INDEX IF EXISTS idx_emotional_state;
DROP INDEX IF EXISTS idx_emotional_user_time;
DROP INDEX IF EXISTS uniq_emotional_id_time;

-- Drop the table (hypertable is dropped automatically)
DROP TABLE IF EXISTS emotional_memories CASCADE;

