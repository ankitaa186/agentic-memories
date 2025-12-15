-- Portfolio Holdings Schema Simplification - ROLLBACK (Story 3.3)
-- Description: Restore original 19-column schema
-- WARNING: Dropped column data cannot be restored

-- Step 1: Remove NOT NULL constraint from ticker
ALTER TABLE portfolio_holdings ALTER COLUMN ticker DROP NOT NULL;

-- Step 2: Re-add dropped columns (without original data)
ALTER TABLE portfolio_holdings
    ADD COLUMN IF NOT EXISTS asset_type VARCHAR(32),
    ADD COLUMN IF NOT EXISTS current_price FLOAT,
    ADD COLUMN IF NOT EXISTS current_value FLOAT,
    ADD COLUMN IF NOT EXISTS cost_basis FLOAT,
    ADD COLUMN IF NOT EXISTS ownership_pct FLOAT,
    ADD COLUMN IF NOT EXISTS position VARCHAR(16),
    ADD COLUMN IF NOT EXISTS intent VARCHAR(16),
    ADD COLUMN IF NOT EXISTS time_horizon VARCHAR(16),
    ADD COLUMN IF NOT EXISTS target_price FLOAT,
    ADD COLUMN IF NOT EXISTS stop_loss FLOAT,
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS source_memory_id VARCHAR(64);

-- Step 3: Set default value for asset_type (required in old schema)
UPDATE portfolio_holdings SET asset_type = 'public_equity' WHERE asset_type IS NULL;
ALTER TABLE portfolio_holdings ALTER COLUMN asset_type SET NOT NULL;

-- Step 4: Re-add CHECK constraints
ALTER TABLE portfolio_holdings
    ADD CONSTRAINT chk_asset_type CHECK (asset_type IN ('public_equity', 'private_equity', 'etf', 'mutual_fund', 'cash', 'bond', 'crypto', 'other')),
    ADD CONSTRAINT chk_position CHECK (position IS NULL OR position IN ('long', 'short')),
    ADD CONSTRAINT chk_intent CHECK (intent IS NULL OR intent IN ('buy', 'sell', 'hold', 'watch')),
    ADD CONSTRAINT chk_time_horizon CHECK (time_horizon IS NULL OR time_horizon IN ('days', 'weeks', 'months', 'years'));

-- Step 5: Re-create dropped indexes
CREATE INDEX IF NOT EXISTS idx_holdings_user_ticker
    ON portfolio_holdings (user_id, ticker);

CREATE INDEX IF NOT EXISTS idx_holdings_user_asset_type
    ON portfolio_holdings (user_id, asset_type);

CREATE INDEX IF NOT EXISTS idx_holdings_user_intent
    ON portfolio_holdings (user_id, intent) WHERE intent IN ('buy', 'watch');

CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_user_asset_name_unique
    ON portfolio_holdings (user_id, asset_name)
    WHERE asset_name IS NOT NULL AND ticker IS NULL;

COMMENT ON TABLE portfolio_holdings IS 'Portfolio holdings table with full 19-column schema (rollback from Story 3.3)';
