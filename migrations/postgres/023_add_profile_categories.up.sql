-- Add new profile categories: health, personality, values
-- These categories support comprehensive user profiling

-- Drop the existing constraint
ALTER TABLE profile_fields DROP CONSTRAINT IF EXISTS chk_category_valid;

-- Add updated constraint with new categories
ALTER TABLE profile_fields
  ADD CONSTRAINT chk_category_valid
    CHECK (category IN ('basics', 'preferences', 'goals', 'interests', 'background', 'health', 'personality', 'values'));

-- Update the column comment to reflect new categories
COMMENT ON COLUMN profile_fields.category IS 'Profile category: basics, preferences, goals, interests, background, health, personality, values';
