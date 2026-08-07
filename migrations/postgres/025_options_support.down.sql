-- Rollback PostgreSQL Migration: options_support
-- Description: Remove options contract support from portfolio_holdings.
-- WARNING: Deletes all option positions (rows with asset_class='option') because the
-- narrowed ticker column cannot hold OCC-style option symbols.

DROP INDEX IF EXISTS idx_holdings_option_key;

DELETE FROM portfolio_holdings WHERE asset_class = 'option';

ALTER TABLE portfolio_holdings
    DROP CONSTRAINT IF EXISTS chk_ticker_format,
    DROP CONSTRAINT IF EXISTS chk_option_no_equity_fields,
    DROP CONSTRAINT IF EXISTS chk_equity_no_option_fields,
    DROP CONSTRAINT IF EXISTS chk_option_fields,
    DROP CONSTRAINT IF EXISTS chk_collateral_non_negative,
    DROP CONSTRAINT IF EXISTS chk_strike_positive,
    DROP CONSTRAINT IF EXISTS chk_contracts_positive,
    DROP CONSTRAINT IF EXISTS chk_action_type,
    DROP CONSTRAINT IF EXISTS chk_option_type,
    DROP CONSTRAINT IF EXISTS chk_asset_class;

ALTER TABLE portfolio_holdings
    DROP COLUMN IF EXISTS collateral_required,
    DROP COLUMN IF EXISTS premium,
    DROP COLUMN IF EXISTS contracts,
    DROP COLUMN IF EXISTS expiration_date,
    DROP COLUMN IF EXISTS strike_price,
    DROP COLUMN IF EXISTS action_type,
    DROP COLUMN IF EXISTS option_type,
    DROP COLUMN IF EXISTS underlying_ticker,
    DROP COLUMN IF EXISTS asset_class;

ALTER TABLE portfolio_holdings ALTER COLUMN ticker TYPE VARCHAR(16);
