-- 024_unwrap_double_encoded_strings.up.sql
--
-- One-time data fix: some profile_fields rows for value_type='string' were
-- written by the LLM extractor with already-JSON-encoded values, producing
-- stored strings like '"Employee at Intuit"' (with literal embedded quotes).
-- The accompanying source fix in src/services/profile_extraction.py
-- prevents new occurrences; this migration cleans the existing rows.
--
-- Strategy: use Postgres' jsonb parser to safely decode one layer of
-- JSON-string encoding. Only rows whose field_value parses as a JSON string
-- are updated, so legitimate values containing quotes are untouched.
--
-- Idempotent: a second run finds zero matching rows.

BEGIN;

-- Snapshot affected rows for rollback
CREATE TABLE IF NOT EXISTS profile_fields_backup_024 AS
SELECT *
FROM profile_fields
WHERE value_type = 'string'
  AND field_value LIKE '"%"';

-- Apply: jsonb #>> '{}' extracts the underlying string from a JSON string.
-- The jsonb_typeof guard ensures we only touch rows that actually parse as
-- a JSON string (not e.g. a JSON object that happens to start/end with ").
UPDATE profile_fields
SET field_value = (field_value::jsonb #>> '{}')
WHERE value_type = 'string'
  AND field_value LIKE '"%"'
  AND jsonb_typeof(field_value::jsonb) = 'string';

COMMIT;

-- Verification (run manually after commit):
--   SELECT count(*) FROM profile_fields_backup_024;       -- rows snapshotted
--   SELECT count(*) FROM profile_fields
--    WHERE value_type='string' AND field_value LIKE '"%"';  -- should now be ~0
