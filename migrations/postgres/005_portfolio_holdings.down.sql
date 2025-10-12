-- Rollback portfolio holdings table

DROP INDEX IF EXISTS idx_holdings_last_updated;
DROP INDEX IF EXISTS idx_holdings_user_intent;
DROP INDEX IF EXISTS idx_holdings_user_asset_type;
DROP INDEX IF EXISTS idx_holdings_user_ticker;
DROP TABLE IF EXISTS portfolio_holdings CASCADE;

