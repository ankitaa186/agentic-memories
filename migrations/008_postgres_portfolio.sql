-- Active: 1760219202030@@127.0.0.1@5433@agentic_memories
-- Portfolio storage: holdings, transactions, preferences
-- PostgreSQL migration for structured financial tracking

-- Current portfolio holdings table
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    ticker VARCHAR(16), -- Can be NULL for private equity
    asset_name VARCHAR(256), -- For private equity/unlisted assets
    asset_type VARCHAR(32) NOT NULL, -- 'public_equity', 'private_equity', 'etf', 'mutual_fund', 'cash', 'bond', 'crypto', 'other'
    shares FLOAT, -- NULL for non-share-based assets
    avg_price FLOAT,
    current_price FLOAT,
    current_value FLOAT,
    cost_basis FLOAT,
    ownership_pct FLOAT, -- For private equity
    position VARCHAR(16), -- 'long', 'short'
    intent VARCHAR(16), -- 'buy', 'sell', 'hold', 'watch'
    time_horizon VARCHAR(16), -- 'days', 'weeks', 'months', 'years'
    target_price FLOAT,
    stop_loss FLOAT,
    notes TEXT,
    first_acquired TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_memory_id VARCHAR(64), -- Link back to originating memory
    CONSTRAINT chk_asset_type CHECK (asset_type IN ('public_equity', 'private_equity', 'etf', 'mutual_fund', 'cash', 'bond', 'crypto', 'other')),
    CONSTRAINT chk_position CHECK (position IS NULL OR position IN ('long', 'short')),
    CONSTRAINT chk_intent CHECK (intent IS NULL OR intent IN ('buy', 'sell', 'hold', 'watch')),
    CONSTRAINT chk_time_horizon CHECK (time_horizon IS NULL OR time_horizon IN ('days', 'weeks', 'months', 'years'))
);

-- Portfolio transactions ledger (immutable)
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

-- Portfolio goals and risk preferences
CREATE TABLE IF NOT EXISTS portfolio_preferences (
    user_id VARCHAR(64) PRIMARY KEY,
    risk_tolerance VARCHAR(16), -- 'low', 'medium', 'high'
    investment_goals JSONB[], -- [{goal: 'retirement', target_amount: 1000000, target_date: '2045-01-01'}]
    sector_preferences JSONB, -- {tech: 0.3, healthcare: 0.2, energy: 0.1}
    constraints JSONB, -- {max_single_position: 0.15, min_cash_reserve: 10000}
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_risk_tolerance CHECK (risk_tolerance IS NULL OR risk_tolerance IN ('low', 'medium', 'high'))
);

-- Holdings indexes
CREATE INDEX IF NOT EXISTS idx_holdings_user_ticker
ON portfolio_holdings (user_id, ticker);

CREATE INDEX IF NOT EXISTS idx_holdings_user_asset_type
ON portfolio_holdings (user_id, asset_type);

CREATE INDEX IF NOT EXISTS idx_holdings_user_intent
ON portfolio_holdings (user_id, intent) WHERE intent IN ('buy', 'watch');

CREATE INDEX IF NOT EXISTS idx_holdings_last_updated
ON portfolio_holdings (last_updated DESC);

-- Transactions indexes
CREATE INDEX IF NOT EXISTS idx_transactions_user_date
ON portfolio_transactions (user_id, transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_ticker
ON portfolio_transactions (ticker, transaction_date DESC);

