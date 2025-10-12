-- Rollback episodic memories table
-- Removes hypertable, indexes, and table

-- Drop compression policy first
SELECT remove_compression_policy('episodic_memories', if_exists => TRUE);

-- Drop indexes
DROP INDEX IF EXISTS idx_episodic_importance;
DROP INDEX IF EXISTS idx_episodic_user_time;
DROP INDEX IF EXISTS uniq_episodic_id_time;

-- Drop the table (hypertable is dropped automatically)
DROP TABLE IF EXISTS episodic_memories CASCADE;

