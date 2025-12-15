-- Portfolio Holdings Unique Constraint Fix - ROLLBACK
-- Description: Restore partial unique index

-- Drop the regular unique constraint
ALTER TABLE portfolio_holdings DROP CONSTRAINT IF EXISTS portfolio_holdings_user_ticker_unique;

-- Recreate partial unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_user_ticker_unique
    ON portfolio_holdings (user_id, ticker)
    WHERE ticker IS NOT NULL;

COMMENT ON INDEX idx_holdings_user_ticker_unique IS 'Prevents duplicate holdings for same user+ticker';
