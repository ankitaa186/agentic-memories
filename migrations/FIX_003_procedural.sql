-- Fix for 003_postgres_procedural.sql
-- The original migration had wrong column names and types
-- This fixes the schema to match ProceduralMemoryService expectations

-- 1. Rename last_performed -> last_practiced
ALTER TABLE procedural_memories 
  RENAME COLUMN last_performed TO last_practiced;

-- 2. Change proficiency_level from FLOAT to VARCHAR
ALTER TABLE procedural_memories 
  ALTER COLUMN proficiency_level TYPE VARCHAR(32);

-- 3. Change steps from ARRAY to JSONB
ALTER TABLE procedural_memories 
  ALTER COLUMN steps TYPE JSONB USING steps::text::jsonb;

-- 4. Drop unused columns
ALTER TABLE procedural_memories 
  DROP COLUMN IF EXISTS context_triggers CASCADE;

ALTER TABLE procedural_memories 
  DROP COLUMN IF EXISTS skill_category CASCADE;

ALTER TABLE procedural_memories 
  DROP COLUMN IF EXISTS variations CASCADE;

-- 5. Add missing columns
ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS prerequisites JSONB;

ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS difficulty_rating FLOAT;

ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS context TEXT;

ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS tags TEXT[];

ALTER TABLE procedural_memories 
  ADD COLUMN IF NOT EXISTS metadata JSONB;

-- 6. Add constraints
ALTER TABLE procedural_memories 
  DROP CONSTRAINT IF EXISTS chk_proficiency_range CASCADE;

ALTER TABLE procedural_memories 
  ADD CONSTRAINT chk_difficulty_range 
  CHECK (difficulty_rating IS NULL OR difficulty_rating BETWEEN 0.0 AND 1.0);

-- 7. Verify final schema
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'procedural_memories' 
ORDER BY ordinal_position;

