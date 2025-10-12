-- Rollback portfolio snapshots table
-- Removes hypertable, policies, and table

-- Drop retention policy first
SELECT remove_retention_policy('portfolio_snapshots', if_exists => TRUE);

-- Drop compression policy
SELECT remove_compression_policy('portfolio_snapshots', if_exists => TRUE);

-- Drop indexes
DROP INDEX IF EXISTS idx_snapshots_user_time;

-- Drop the table (hypertable is dropped automatically)
DROP TABLE IF EXISTS portfolio_snapshots CASCADE;

