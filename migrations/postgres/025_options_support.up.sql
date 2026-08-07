-- PostgreSQL Migration: options_support
-- Description: Extend portfolio_holdings to support options contracts (CSPs, covered calls,
-- long/short option positions) alongside standard equity holdings, including collateral tracking.
--
-- New columns:
--   asset_class          'equity' | 'option' (default 'equity' for backwards compatibility)
--   underlying_ticker    Underlying symbol for options (e.g., TLN for a TLN put)
--   option_type          'put' | 'call'
--   action_type          'sell_to_open' | 'buy_to_open' | 'sell_to_close' | 'buy_to_close'
--   strike_price         Strike price per share
--   expiration_date      Contract expiration date
--   contracts            Number of contracts (1 contract = 100 shares)
--   premium              Net option premium
--   collateral_required  Cash or margin locked up (e.g., 30000 for one $300-strike CSP)
--
-- Option positions store an OCC-style symbol in `ticker` (e.g., TLN260821P00300000),
-- so the existing UNIQUE (user_id, ticker) constraint enforces one row per
-- (underlying, expiration, option_type, strike) per user and UPSERT keeps working.

-- Step 1: Widen ticker to fit OCC-style option symbols (underlying + YYMMDD + C/P + 8-digit strike)
ALTER TABLE portfolio_holdings ALTER COLUMN ticker TYPE VARCHAR(32);

-- Step 2: Add option columns (existing equity rows pick up asset_class='equity' via the default)
ALTER TABLE portfolio_holdings
    ADD COLUMN IF NOT EXISTS asset_class VARCHAR(16) NOT NULL DEFAULT 'equity',
    ADD COLUMN IF NOT EXISTS underlying_ticker VARCHAR(16),
    ADD COLUMN IF NOT EXISTS option_type VARCHAR(8),
    ADD COLUMN IF NOT EXISTS action_type VARCHAR(16),
    ADD COLUMN IF NOT EXISTS strike_price DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS expiration_date DATE,
    ADD COLUMN IF NOT EXISTS contracts INTEGER,
    ADD COLUMN IF NOT EXISTS premium DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS collateral_required DOUBLE PRECISION;

-- Step 3: Enum and integrity constraints (watertight per asset class)
ALTER TABLE portfolio_holdings
    ADD CONSTRAINT chk_asset_class CHECK (asset_class IN ('equity', 'option')),
    ADD CONSTRAINT chk_option_type CHECK (option_type IS NULL OR option_type IN ('put', 'call')),
    ADD CONSTRAINT chk_action_type CHECK (action_type IS NULL OR action_type IN ('sell_to_open', 'buy_to_open', 'sell_to_close', 'buy_to_close')),
    ADD CONSTRAINT chk_contracts_positive CHECK (contracts IS NULL OR contracts > 0),
    ADD CONSTRAINT chk_strike_positive CHECK (strike_price IS NULL OR strike_price > 0),
    ADD CONSTRAINT chk_collateral_non_negative CHECK (collateral_required IS NULL OR collateral_required >= 0),
    -- Options MUST have their defining fields (premium/collateral stay optional:
    -- long positions have no collateral, premium may be unknown at logging time)
    ADD CONSTRAINT chk_option_fields CHECK (
        asset_class <> 'option'
        OR (underlying_ticker IS NOT NULL
            AND underlying_ticker ~ '^[A-Z0-9\.]{1,10}$'
            AND option_type IS NOT NULL
            AND action_type IS NOT NULL
            AND strike_price IS NOT NULL
            AND expiration_date IS NOT NULL
            AND contracts IS NOT NULL)
    ),
    -- Equities MUST NOT carry any option fields
    ADD CONSTRAINT chk_equity_no_option_fields CHECK (
        asset_class <> 'equity'
        OR (underlying_ticker IS NULL
            AND option_type IS NULL
            AND action_type IS NULL
            AND strike_price IS NULL
            AND expiration_date IS NULL
            AND contracts IS NULL
            AND premium IS NULL
            AND collateral_required IS NULL)
    ),
    -- Options MUST NOT carry equity quantity fields (contracts is the quantity)
    ADD CONSTRAINT chk_option_no_equity_fields CHECK (
        asset_class <> 'option'
        OR (shares IS NULL AND avg_price IS NULL)
    ),
    -- Ticker shape per asset class: plain symbol for equities, OCC symbol for options
    ADD CONSTRAINT chk_ticker_format CHECK (
        (asset_class = 'equity' AND ticker ~ '^[A-Z0-9\.]{1,10}$')
        OR (asset_class = 'option' AND ticker ~ '^[A-Z0-9\.]{1,10}[0-9]{6}[CP][0-9]{8}$')
    );

-- Step 4: Lookup index for the options key tuple
CREATE INDEX IF NOT EXISTS idx_holdings_option_key
    ON portfolio_holdings (user_id, underlying_ticker, strike_price, expiration_date, option_type)
    WHERE asset_class = 'option';

COMMENT ON COLUMN portfolio_holdings.asset_class IS 'equity | option (options support migration 025)';
COMMENT ON COLUMN portfolio_holdings.collateral_required IS 'Cash/margin committed for short options (CSP/CC collateral)';
