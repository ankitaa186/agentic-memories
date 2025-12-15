-- Portfolio Holdings Unique Constraint Fix (Story 3.3 follow-up)
-- Description: Replace partial unique index with regular unique constraint
-- Reason: Partial index (WHERE ticker IS NOT NULL) doesn't work with ON CONFLICT
--         Now that ticker is NOT NULL (from migration 015), we can use a regular constraint

-- Drop the partial unique index
DROP INDEX IF EXISTS idx_holdings_user_ticker_unique;

-- Add regular unique constraint (works with ON CONFLICT)
ALTER TABLE portfolio_holdings ADD CONSTRAINT portfolio_holdings_user_ticker_unique UNIQUE (user_id, ticker);

COMMENT ON CONSTRAINT portfolio_holdings_user_ticker_unique ON portfolio_holdings IS 'Unique constraint for user+ticker (Story 3.3)';
