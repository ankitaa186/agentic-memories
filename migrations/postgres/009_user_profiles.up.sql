-- User Profiles (PostgreSQL)
-- Core profile metadata and completeness tracking
-- Stores aggregated profile information with completeness scores

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(255) PRIMARY KEY,
    completeness_pct DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    total_fields INT NOT NULL DEFAULT 0,
    populated_fields INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add constraints
ALTER TABLE user_profiles
  ADD CONSTRAINT chk_completeness_range
    CHECK (completeness_pct >= 0 AND completeness_pct <= 100),
  ADD CONSTRAINT chk_total_fields_positive
    CHECK (total_fields >= 0),
  ADD CONSTRAINT chk_populated_fields_positive
    CHECK (populated_fields >= 0),
  ADD CONSTRAINT chk_populated_lte_total
    CHECK (populated_fields <= total_fields);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_user_profiles_updated
  ON user_profiles (last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_user_profiles_completeness
  ON user_profiles (completeness_pct DESC);

CREATE INDEX IF NOT EXISTS idx_user_profiles_created
  ON user_profiles (created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE user_profiles IS 'User profile metadata and completeness tracking';
COMMENT ON COLUMN user_profiles.completeness_pct IS 'Percentage of profile fields populated (0-100)';
COMMENT ON COLUMN user_profiles.total_fields IS 'Total number of expected profile fields (default: 25)';
COMMENT ON COLUMN user_profiles.populated_fields IS 'Number of fields with values';
