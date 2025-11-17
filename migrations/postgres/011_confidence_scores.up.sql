-- Profile Confidence Scores (PostgreSQL)
-- Field-level confidence tracking with weighted algorithm breakdown
-- Stores confidence scores for each profile field

CREATE TABLE IF NOT EXISTS profile_confidence_scores (
    user_id VARCHAR(255) NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    overall_confidence DECIMAL(5,2) NOT NULL,
    frequency_score DECIMAL(5,2) NOT NULL,
    recency_score DECIMAL(5,2) NOT NULL,
    explicitness_score DECIMAL(5,2) NOT NULL,
    source_diversity_score DECIMAL(5,2) NOT NULL,
    mention_count INT NOT NULL DEFAULT 1,
    last_mentioned TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, category, field_name),
    FOREIGN KEY (user_id, category, field_name)
      REFERENCES profile_fields(user_id, category, field_name)
      ON DELETE CASCADE
);

-- Add constraints
ALTER TABLE profile_confidence_scores
  ADD CONSTRAINT chk_overall_confidence_range
    CHECK (overall_confidence >= 0 AND overall_confidence <= 100),
  ADD CONSTRAINT chk_frequency_score_range
    CHECK (frequency_score >= 0 AND frequency_score <= 100),
  ADD CONSTRAINT chk_recency_score_range
    CHECK (recency_score >= 0 AND recency_score <= 100),
  ADD CONSTRAINT chk_explicitness_score_range
    CHECK (explicitness_score >= 0 AND explicitness_score <= 100),
  ADD CONSTRAINT chk_source_diversity_score_range
    CHECK (source_diversity_score >= 0 AND source_diversity_score <= 100),
  ADD CONSTRAINT chk_mention_count_positive
    CHECK (mention_count > 0);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_confidence_scores_user
  ON profile_confidence_scores (user_id);

CREATE INDEX IF NOT EXISTS idx_confidence_scores_overall
  ON profile_confidence_scores (overall_confidence DESC);

CREATE INDEX IF NOT EXISTS idx_confidence_scores_user_overall
  ON profile_confidence_scores (user_id, overall_confidence DESC);

CREATE INDEX IF NOT EXISTS idx_confidence_scores_low
  ON profile_confidence_scores (user_id, overall_confidence ASC)
  WHERE overall_confidence < 50;

-- Add comments for documentation
COMMENT ON TABLE profile_confidence_scores IS 'Field-level confidence tracking with weighted algorithm breakdown';
COMMENT ON COLUMN profile_confidence_scores.overall_confidence IS 'Weighted confidence: (freq×0.30) + (rec×0.25) + (exp×0.25) + (div×0.20)';
COMMENT ON COLUMN profile_confidence_scores.frequency_score IS 'Score based on mention frequency (max 10 mentions = 100%)';
COMMENT ON COLUMN profile_confidence_scores.recency_score IS 'Score based on how recent (30 days = 100%)';
COMMENT ON COLUMN profile_confidence_scores.explicitness_score IS 'Score based on source type (explicit=100%, implicit=70%, inferred=40%)';
COMMENT ON COLUMN profile_confidence_scores.source_diversity_score IS 'Score based on unique sources (max 5 sources = 100%)';
