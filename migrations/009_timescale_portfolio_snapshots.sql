-- Portfolio snapshots over time (TimescaleDB)
-- Track portfolio value history for performance analysis

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    user_id VARCHAR(64) NOT NULL,
    snapshot_timestamp TIMESTAMPTZ NOT NULL,
    total_value FLOAT NOT NULL,
    cash_value FLOAT,
    equity_value FLOAT,
    holdings_snapshot JSONB, -- Full holdings array at this point in time
    returns_1d FLOAT,
    returns_7d FLOAT,
    returns_30d FLOAT,
    returns_ytd FLOAT
);

-- Create hypertable for time-series data
SELECT create_hypertable('portfolio_snapshots', 'snapshot_timestamp', if_not_exists => TRUE);

-- Indexes for time-series queries
CREATE INDEX IF NOT EXISTS idx_snapshots_user_time
ON portfolio_snapshots (user_id, snapshot_timestamp DESC);

-- Timescale chunk configuration
SELECT set_chunk_time_interval('portfolio_snapshots', INTERVAL '30 days');

-- Enable compression
ALTER TABLE portfolio_snapshots
  SET (timescaledb.compress,
       timescaledb.compress_orderby = 'snapshot_timestamp DESC',
       timescaledb.compress_segmentby = 'user_id');

-- Compression policy: compress after 90 days
SELECT add_compression_policy('portfolio_snapshots', INTERVAL '90 days', if_not_exists => TRUE);

-- Retention policy: keep 5 years
SELECT add_retention_policy('portfolio_snapshots', INTERVAL '5 years', if_not_exists => TRUE);

