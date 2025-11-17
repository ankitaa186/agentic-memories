-- Profile Fields (PostgreSQL)
-- Individual profile field values with category grouping
-- Stores all user profile data organized by category

CREATE TABLE IF NOT EXISTS profile_fields (
    user_id VARCHAR(255) NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    field_value TEXT NOT NULL,
    value_type VARCHAR(20) NOT NULL DEFAULT 'string',
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, category, field_name)
);

-- Add constraints
ALTER TABLE profile_fields
  ADD CONSTRAINT chk_category_valid
    CHECK (category IN ('basics', 'preferences', 'goals', 'interests', 'background')),
  ADD CONSTRAINT chk_value_type_valid
    CHECK (value_type IN ('string', 'int', 'float', 'bool', 'list', 'dict'));

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_profile_fields_user_category
  ON profile_fields (user_id, category);

CREATE INDEX IF NOT EXISTS idx_profile_fields_updated
  ON profile_fields (last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_profile_fields_category
  ON profile_fields (category);

-- Add comments for documentation
COMMENT ON TABLE profile_fields IS 'Individual profile field values grouped by category';
COMMENT ON COLUMN profile_fields.category IS 'Profile category: basics, preferences, goals, interests, background';
COMMENT ON COLUMN profile_fields.field_name IS 'Name of the field within the category';
COMMENT ON COLUMN profile_fields.field_value IS 'Serialized field value (TEXT for flexibility)';
COMMENT ON COLUMN profile_fields.value_type IS 'Original type for proper deserialization';
