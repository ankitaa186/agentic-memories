-- Fix for 001_timescale_episodic.sql
-- Run these statements to fix the episodic_memories table

-- 1. Rename significance_score to importance_score (if not already done)
ALTER TABLE episodic_memories 
  RENAME COLUMN significance_score TO importance_score;

-- 2. Add missing columns
ALTER TABLE episodic_memories 
  ADD COLUMN IF NOT EXISTS tags TEXT[];

ALTER TABLE episodic_memories 
  ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Verify columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'episodic_memories' 
ORDER BY ordinal_position;

