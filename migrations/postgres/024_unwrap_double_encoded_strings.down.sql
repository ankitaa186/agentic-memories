-- 024_unwrap_double_encoded_strings.down.sql
--
-- Restore field_value from the backup table created by the up migration.
-- Drops the backup table after restoration.

BEGIN;

UPDATE profile_fields pf
SET field_value = b.field_value
FROM profile_fields_backup_024 b
WHERE pf.user_id   = b.user_id
  AND pf.category  = b.category
  AND pf.field_name = b.field_name;

DROP TABLE IF EXISTS profile_fields_backup_024;

COMMIT;
