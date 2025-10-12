-- Portfolio Preferences (PostgreSQL)
-- User investment goals, risk tolerance, and constraints

CREATE TABLE IF NOT EXISTS portfolio_preferences (
    user_id VARCHAR(64) PRIMARY KEY,
    risk_tolerance VARCHAR(16), -- 'low', 'medium', 'high'
    investment_goals JSONB[], -- [{goal: 'retirement', target_amount: 1000000, target_date: '2045-01-01'}]
    sector_preferences JSONB, -- {tech: 0.3, healthcare: 0.2, energy: 0.1}
    constraints JSONB, -- {max_single_position: 0.15, min_cash_reserve: 10000}
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_risk_tolerance CHECK (risk_tolerance IS NULL OR risk_tolerance IN ('low', 'medium', 'high'))
);

