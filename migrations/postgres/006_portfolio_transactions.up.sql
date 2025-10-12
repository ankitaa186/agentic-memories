-- Portfolio Transactions (PostgreSQL)
-- Immutable ledger of all portfolio transactions

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    ticker VARCHAR(16),
    asset_name VARCHAR(256),
    asset_type VARCHAR(32) NOT NULL,
    transaction_type VARCHAR(16) NOT NULL, -- 'buy', 'sell', 'dividend', 'split', 'transfer'
    shares FLOAT,
    price FLOAT,
    total_value FLOAT,
    fees FLOAT DEFAULT 0,
    transaction_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    source_memory_id VARCHAR(64),
    CONSTRAINT chk_transaction_type CHECK (transaction_type IN ('buy', 'sell', 'dividend', 'split', 'transfer'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_date
    ON portfolio_transactions (user_id, transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_ticker
    ON portfolio_transactions (ticker, transaction_date DESC);

