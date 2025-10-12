-- Fix for 004_timescale_emotional.sql
-- Add missing 'id' column as primary key

ALTER TABLE emotional_memories 
  ADD COLUMN IF NOT EXISTS id UUID;

-- Update existing rows to have UUIDs if needed
UPDATE emotional_memories SET id = gen_random_uuid() WHERE id IS NULL;

-- Make it NOT NULL
ALTER TABLE emotional_memories 
  ALTER COLUMN id SET NOT NULL;

-- Verify columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'emotional_memories' 
ORDER BY ordinal_position;

