-- Portfolio Holdings (PostgreSQL)
-- Current portfolio positions and holdings

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

CREATE INDEX IF NOT EXISTS idx_holdings_user_ticker
    ON portfolio_holdings (user_id, ticker);

CREATE INDEX IF NOT EXISTS idx_holdings_user_asset_type
    ON portfolio_holdings (user_id, asset_type);

CREATE INDEX IF NOT EXISTS idx_holdings_user_intent
    ON portfolio_holdings (user_id, intent) WHERE intent IN ('buy', 'watch');

CREATE INDEX IF NOT EXISTS idx_holdings_last_updated
    ON portfolio_holdings (last_updated DESC);

