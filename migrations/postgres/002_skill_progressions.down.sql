-- Rollback skill progressions table

DROP INDEX IF EXISTS idx_skill_progression_timestamp;
DROP INDEX IF EXISTS idx_skill_progression_user_skill;
DROP TABLE IF EXISTS skill_progressions CASCADE;

