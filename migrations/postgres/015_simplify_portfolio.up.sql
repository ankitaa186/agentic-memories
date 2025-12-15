-- Portfolio Holdings Schema Simplification (Story 3.3)
-- Description: Simplify portfolio_holdings from 19 columns to 8 columns
-- Reason: All holdings are public_equity; unused columns add maintenance overhead

-- Step 1: Drop indexes that reference columns being removed
DROP INDEX IF EXISTS idx_holdings_user_asset_type;
DROP INDEX IF EXISTS idx_holdings_user_intent;
DROP INDEX IF EXISTS idx_holdings_user_asset_name_unique;

-- Step 2: Drop CHECK constraints (must drop before dropping columns)
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS chk_asset_type;
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS chk_position;
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS chk_intent;
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS chk_time_horizon;

-- Step 3: Drop unused columns (12 columns)
ALTER TABLE portfolio_holdings
    DROP COLUMN IF EXISTS asset_type,
    DROP COLUMN IF EXISTS current_price,
    DROP COLUMN IF EXISTS current_value,
    DROP COLUMN IF EXISTS cost_basis,
    DROP COLUMN IF EXISTS ownership_pct,
    DROP COLUMN IF EXISTS position,
    DROP COLUMN IF EXISTS intent,
    DROP COLUMN IF EXISTS time_horizon,
    DROP COLUMN IF EXISTS target_price,
    DROP COLUMN IF EXISTS stop_loss,
    DROP COLUMN IF EXISTS notes,
    DROP COLUMN IF EXISTS source_memory_id;

-- Step 4: Make ticker NOT NULL (all existing records have tickers)
-- First update any NULL tickers to a placeholder (safety)
UPDATE portfolio_holdings SET ticker = 'UNKNOWN' WHERE ticker IS NULL;
ALTER TABLE portfolio_holdings ALTER COLUMN ticker SET NOT NULL;

-- Step 5: Drop redundant index (unique index covers this use case)
DROP INDEX IF EXISTS idx_holdings_user_ticker;

-- Final schema:
-- portfolio_holdings (
--     id UUID PRIMARY KEY,
--     user_id VARCHAR(64) NOT NULL,
--     ticker VARCHAR(16) NOT NULL,
--     asset_name VARCHAR(256),
--     shares FLOAT,
--     avg_price FLOAT,
--     first_acquired TIMESTAMPTZ NOT NULL DEFAULT NOW(),
--     last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
--     UNIQUE(user_id, ticker) via idx_holdings_user_ticker_unique
-- )

-- Remaining indexes:
-- - portfolio_holdings_pkey (primary key)
-- - idx_holdings_user_ticker_unique (unique constraint)
-- - idx_holdings_last_updated (for queries)

COMMENT ON TABLE portfolio_holdings IS 'Simplified portfolio holdings table - public equities only (Story 3.3)';
