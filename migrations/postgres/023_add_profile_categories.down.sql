-- Revert profile categories to original 5
-- WARNING: This will fail if any fields use health, personality, or values categories

-- Drop the extended constraint
ALTER TABLE profile_fields DROP CONSTRAINT IF EXISTS chk_category_valid;

-- Restore original constraint
ALTER TABLE profile_fields
  ADD CONSTRAINT chk_category_valid
    CHECK (category IN ('basics', 'preferences', 'goals', 'interests', 'background'));

-- Restore original comment
COMMENT ON COLUMN profile_fields.category IS 'Profile category: basics, preferences, goals, interests, background';
