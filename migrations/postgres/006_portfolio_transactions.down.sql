-- Rollback portfolio transactions table

DROP INDEX IF EXISTS idx_transactions_user_time;
DROP INDEX IF EXISTS idx_transactions_user_ticker;
DROP TABLE IF EXISTS portfolio_transactions CASCADE;

