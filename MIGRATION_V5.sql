-- ============================================================
-- Migration v5: Fix jsonb columns to allow empty string from GORM
-- Sets proper DEFAULT for validation_results and deployment_results
-- ============================================================

BEGIN;

-- Set DEFAULT for jsonb columns that lack one, so GORM's empty-string
-- inserts don't violate the jsonb type (SQLSTATE 22P02).
ALTER TABLE pipelines
  ALTER COLUMN validation_results SET DEFAULT '{}'::jsonb,
  ALTER COLUMN deployment_results SET DEFAULT '{}'::jsonb;

-- Backfill any existing rows with empty string to '{}' (defensive)
UPDATE pipelines
  SET validation_results = '{}'::jsonb
  WHERE validation_results IS NULL OR validation_results::text = '';
UPDATE pipelines
  SET deployment_results = '{}'::jsonb
  WHERE deployment_results IS NULL OR deployment_results::text = '';

COMMIT;
