-- Rollback procedural memories table

DROP INDEX IF EXISTS idx_procedural_proficiency;
DROP INDEX IF EXISTS idx_procedural_user_skill;
DROP TABLE IF EXISTS procedural_memories CASCADE;

