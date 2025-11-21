-- Profile Sources (PostgreSQL)
-- Audit trail linking profile fields to source memories
-- Tracks which memories contributed to each profile field

CREATE TABLE IF NOT EXISTS profile_sources (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    source_memory_id VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id, category, field_name)
      REFERENCES profile_fields(user_id, category, field_name)
      ON DELETE CASCADE
);

-- Add constraints
ALTER TABLE profile_sources
  ADD CONSTRAINT chk_source_type_valid
    CHECK (source_type IN ('explicit', 'implicit', 'inferred'));

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_profile_sources_user_field
  ON profile_sources (user_id, category, field_name);

CREATE INDEX IF NOT EXISTS idx_profile_sources_memory
  ON profile_sources (source_memory_id);

CREATE INDEX IF NOT EXISTS idx_profile_sources_extracted
  ON profile_sources (extracted_at DESC);

CREATE INDEX IF NOT EXISTS idx_profile_sources_user
  ON profile_sources (user_id);

-- Add comments for documentation
COMMENT ON TABLE profile_sources IS 'Audit trail linking profile fields to source memories';
COMMENT ON COLUMN profile_sources.source_memory_id IS 'ChromaDB memory ID (mem_xxx format)';
COMMENT ON COLUMN profile_sources.source_type IS 'Extraction confidence: explicit > implicit > inferred';
COMMENT ON COLUMN profile_sources.extracted_at IS 'When this source was linked to the field';
