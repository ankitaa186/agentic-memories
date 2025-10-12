-- Complete fix for 004_timescale_emotional.sql
-- The migration has minimal columns, but the service expects many more

-- Add all missing columns that the service uses
ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS id UUID;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS emotional_state VARCHAR(64);

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS valence FLOAT;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS arousal FLOAT;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS dominance FLOAT;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS context TEXT;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS trigger_event TEXT;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS duration_minutes INT;

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Update existing rows to have UUIDs if needed
UPDATE emotional_memories SET id = gen_random_uuid() WHERE id IS NULL;

-- Make id NOT NULL after populating
ALTER TABLE emotional_memories 
  ALTER COLUMN id SET NOT NULL;

-- Add constraints
ALTER TABLE emotional_memories 
  ADD CONSTRAINT chk_emotional_valence_range 
  CHECK (valence IS NULL OR valence BETWEEN -1.0 AND 1.0);

ALTER TABLE emotional_memories 
  ADD CONSTRAINT chk_emotional_arousal_range 
  CHECK (arousal IS NULL OR arousal BETWEEN 0.0 AND 1.0);

ALTER TABLE emotional_memories 
  ADD CONSTRAINT chk_emotional_dominance_range 
  CHECK (dominance IS NULL OR dominance BETWEEN 0.0 AND 1.0);

-- Verify columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'emotional_memories' 
ORDER BY ordinal_position;

